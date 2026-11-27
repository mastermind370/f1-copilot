"""Grounded answering: retrieve -> gate on confidence -> generate -> validate citations.

The LLM is treated as an untrusted component. Its output is post-processed:
  1. Any sentence without a citation to a passage we actually supplied is dropped.
  2. Citations to IDs we did not supply (hallucinated IDs) are removed.
  3. If nothing survives, we refuse instead of showing an unsupported answer.

This enforces citation *presence*, not entailment: a sentence can cite a passage that
doesn't actually support it. Measuring that (faithfulness) is the job of the Stage 3 eval.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from copilot.config import RetrievalConfig
from copilot.llm import LLMClient
from copilot.models import Answer, ScoredChunk
from copilot.retrieval import HybridRetriever

INSUFFICIENT = "INSUFFICIENT_CONTEXT"

SYSTEM_PROMPT = f"""You are F-1 Compliance Copilot, an information tool for international \
students in the United States. You are not a lawyer and you do not give legal advice.

Rules:
1. Answer ONLY from the context passages provided. Never use outside knowledge.
2. End every sentence with one or more citations in square brackets, using the passage IDs \
exactly as given, for example [3f9a0c12b7de]. Multiple citations look like [id1, id2].
3. Do not calculate a person's deadlines or decide whether they are eligible. Say that the \
timeline tool or their DSO can help with that.
4. If the passages do not contain the answer, reply with exactly: {INSUFFICIENT}
5. Be concise. Reply in the same language as the question."""

CITATION_RE = re.compile(r"\[\s*([0-9a-f]{12}(?:\s*,\s*[0-9a-f]{12})*)\s*\]")
# Split after sentence punctuation or a closing citation bracket, unless another
# citation follows immediately.
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?。！？\]])\s+(?!\[)")


def build_user_prompt(question: str, hits: list[ScoredChunk]) -> str:
    blocks = []
    for h in hits:
        c = h.chunk
        blocks.append(f"[{c.chunk_id}] (source: {c.url} | section: {c.heading})\n{c.text}")
    context = "\n\n".join(blocks)
    return f"Context passages:\n\n{context}\n\nQuestion: {question}"


@dataclass
class ValidatedOutput:
    text: str
    cited_ids: list[str]
    dropped: list[str]


def validate_citations(raw: str, allowed_ids: set[str]) -> ValidatedOutput:
    kept: list[str] = []
    dropped: list[str] = []
    cited: list[str] = []

    for line in raw.strip().splitlines():
        line_kept: list[str] = []
        for sentence in SENTENCE_SPLIT_RE.split(line.strip()):
            if not sentence:
                continue
            ids_in_sentence = [
                i.strip() for group in CITATION_RE.findall(sentence) for i in group.split(",")
            ]
            valid = [i for i in ids_in_sentence if i in allowed_ids]
            if not valid:
                dropped.append(sentence)
                continue

            def _rewrite(m: re.Match[str]) -> str:
                ids = [i.strip() for i in m.group(1).split(",") if i.strip() in allowed_ids]
                return f"[{', '.join(ids)}]" if ids else ""

            clean = " ".join(CITATION_RE.sub(_rewrite, sentence).split())
            line_kept.append(clean)
            for i in valid:
                if i not in cited:
                    cited.append(i)
        if line_kept:
            kept.append(" ".join(line_kept))

    return ValidatedOutput(text="\n".join(kept), cited_ids=cited, dropped=dropped)


def _first_sentences(text: str, n: int = 2) -> str:
    parts = re.split(r"(?<=[.!?])\s+", text)
    return " ".join(parts[:n])


class QAPipeline:
    def __init__(
        self,
        retriever: HybridRetriever,
        llm: LLMClient | None,
        cfg: RetrievalConfig,
        dso_message: str,
    ) -> None:
        self.retriever = retriever
        self.llm = llm
        self.cfg = cfg
        self.dso_message = dso_message

    def _refuse(self, question: str, reason: str, confidence: float, dropped: list[str] | None = None) -> Answer:
        text = (
            "I couldn't find a reliable answer to this in the official sources I've indexed, "
            f"so I won't guess. {self.dso_message}"
        )
        return Answer(
            question=question, text=text, refused=True, confidence=confidence,
            reason=reason, dropped_sentences=dropped or [],
        )

    def ask(self, question: str, exclude_sources: set[str] | None = None) -> Answer:
        result = self.retriever.search(question, exclude_sources=exclude_sources)
        conf = result.confidence
        if not result.hits or conf < self.cfg.min_confidence:
            return self._refuse(question, "low_retrieval_confidence", conf)

        by_id = {h.chunk.chunk_id: h.chunk for h in result.hits}

        if self.llm is None:  # extractive mode: quote the top passages, no generation
            top = result.hits[:3]
            text = "\n".join(f"- {_first_sentences(h.chunk.text)} [{h.chunk.chunk_id}]" for h in top)
            return Answer(question=question, text=text, refused=False, confidence=conf,
                          citations=[h.chunk for h in top])

        raw = self.llm.complete(SYSTEM_PROMPT, build_user_prompt(question, result.hits))
        if INSUFFICIENT in raw:
            return self._refuse(question, "llm_insufficient_context", conf)

        validated = validate_citations(raw, set(by_id))
        if not validated.cited_ids:
            return self._refuse(question, "no_supported_claims", conf, validated.dropped)

        return Answer(
            question=question,
            text=validated.text,
            refused=False,
            confidence=conf,
            citations=[by_id[i] for i in validated.cited_ids],
            dropped_sentences=validated.dropped,
        )
