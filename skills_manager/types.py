from dataclasses import dataclass, field
from typing import Any, Literal


ScreeningMode = Literal["passthrough", "keyword", "embedding", "hybrid", "keyword_llm"]
CandidateSource = Literal["passthrough", "keyword", "embedding", "hybrid", "llm"]


@dataclass(frozen=True)
class SkillMetadata:
    name: str
    description: str
    path: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SkillSelectionRequest:
    query_text: str
    screening_mode: ScreeningMode = "passthrough"
    top_k_retrieval: int = 8
    top_k_selection: int = 1
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CatalogResult:
    skills: list[SkillMetadata]


@dataclass(frozen=True)
class RetrievalCandidate:
    skill: SkillMetadata
    score: float | None = None
    reason: str | None = None
    source: CandidateSource = "passthrough"


@dataclass(frozen=True)
class RetrievalResult:
    mode: ScreeningMode
    all_skills_count: int
    candidates: list[RetrievalCandidate]


@dataclass(frozen=True)
class SelectionItem:
    skill: SkillMetadata
    score: float | None = None
    reason: str | None = None


@dataclass(frozen=True)
class SelectionResult:
    input_candidates_count: int
    selected: list[SelectionItem]


@dataclass(frozen=True)
class LoadedSkillContent:
    skill: SkillMetadata
    content: str


@dataclass(frozen=True)
class LoadResult:
    loaded: list[LoadedSkillContent]


@dataclass(frozen=True)
class IntegrationResult:
    payload: dict[str, Any]


@dataclass(frozen=True)
class SkillResolutionResult:
    catalog: CatalogResult
    retrieval: RetrievalResult
    selection: SelectionResult
    load: LoadResult
    integration: IntegrationResult
