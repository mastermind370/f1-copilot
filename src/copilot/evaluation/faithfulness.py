"""Sentence-level faithfulness: is each cited sentence actually supported by what it cites?

Stage 1 guarantees every sentence *has* a citation. This measures whether the cited text
*entails* the sentence, using a small local NLI (natural language inference) cross-encoder
instead of another LLM as judge. That keeps it cheap, deterministic, and free of the
"LLM grading itself" problem.

A sentence counts as supported if ANY of the chunks it cites entails it with probability
>= 0.5. The NLI model is English-only, so faithfulness is reported for English answers
only. That limitation is reported in the results, not hidden.
"""

from __future__ import annotations

from typing import Protocol

import numpy as np

from copilot.answer import CITATION_RE, SENTENCE_SPLIT_RE


class Judge(Protocol):
    def entailment(self, premise: str, hypothesis: str) -> float: ...


class NLIJudge:
    def __init__(self, model_name: str) -> None:
        from sentence_transformers import CrossEncoder

        self._model = CrossEncoder(model_name)
        id2label = {int(k): str(v).lower() for k, v in self._model.model.config.id2label.items()}
        matches = [i for i, label in id2label.items() if "entail" in label]
        if not matches:
            raise ValueError(f"{model_name} has no entailment label: {id2label}")
        self._entail_idx = matches[0]

    def entailment(self, premise: str, hypothesis: str) -> float:
        logits = np.asarray(self._model.predict([(premise, hypothesis)]))[0]
        probs = np.exp(logits - logits.max())
        probs /= probs.sum()
        return float(probs[self._entail_idx])


def cited_sentences(answer: str) -> list[tuple[str, list[str]]]:
    out: list[tuple[str, list[str]]] = []
    for line in answer.splitlines():
        for sentence in SENTENCE_SPLIT_RE.split(line.strip()):
            ids = [i.strip() for g in CITATION_RE.findall(sentence) for i in g.split(",")]
            claim = CITATION_RE.sub("", sentence).strip(" -•\t")
            if claim and ids:
                out.append((claim, ids))
    return out


def faithfulness(answer: str, chunk_text: dict[str, str], judge: Judge, threshold: float = 0.5) -> float | None:
    sentences = cited_sentences(answer)
    if not sentences:
        return None
    supported = 0
    for claim, ids in sentences:
        scores = [judge.entailment(chunk_text[i], claim) for i in ids if i in chunk_text]
        supported += bool(scores) and max(scores) >= threshold
    return supported / len(sentences)
