from dataclasses import dataclass

from langchain_core.embeddings import Embeddings


@dataclass(frozen=True)
class SimilaritySearchResult:
    score: float
    content: str
