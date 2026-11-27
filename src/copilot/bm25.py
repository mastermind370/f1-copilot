"""Okapi BM25, implemented from scratch with an inverted index.

Lexical search matters a lot in this domain. Users type exact identifiers like "I-20",
"I-765", "STEM OPT" and "CPT", and dense embeddings often blur those together. The
tokenizer keeps hyphenated identifiers as single tokens for that reason.
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict

import numpy as np

TOKEN_RE = re.compile(r"[a-z0-9]+(?:[-'][a-z0-9]+)*")
STOPWORDS = frozenset(
    "a an and are as at be by can do does for from has have how i if in is it its my of on "
    "or the their there this to was what when where which who will with you your".split()
)


def tokenize(text: str) -> list[str]:
    return [t for t in TOKEN_RE.findall(text.lower()) if t not in STOPWORDS]


class BM25:
    def __init__(self, docs: list[list[str]], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.n_docs = len(docs)
        self.doc_len = np.array([len(d) for d in docs], dtype=np.float64)
        self.avgdl = float(self.doc_len.mean()) if self.n_docs else 0.0

        self.postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
        for i, doc in enumerate(docs):
            for term, freq in Counter(doc).items():
                self.postings[term].append((i, freq))

        # The "+1" inside the log (Lucene's variant) keeps IDF positive even for very common terms.
        self.idf = {
            term: math.log(1.0 + (self.n_docs - len(p) + 0.5) / (len(p) + 0.5))
            for term, p in self.postings.items()
        }

    def scores(self, query_tokens: list[str]) -> np.ndarray:
        out = np.zeros(self.n_docs, dtype=np.float64)
        if self.n_docs == 0 or self.avgdl == 0:
            return out
        for term in set(query_tokens):
            postings = self.postings.get(term)
            if not postings:
                continue
            idf = self.idf[term]
            for doc_idx, freq in postings:
                norm = 1 - self.b + self.b * self.doc_len[doc_idx] / self.avgdl
                out[doc_idx] += idf * freq * (self.k1 + 1) / (freq + self.k1 * norm)
        return out
