from typing import Protocol

from skills_manager.types import (
    CatalogResult,
    LoadResult,
    RetrievalCandidate,
    RetrievalResult,
    SelectionResult,
    SkillMetadata,
    SkillSelectionRequest,
    IntegrationResult,
)


class SkillCatalogBackend(Protocol):
    def load_metadata(self) -> list[SkillMetadata]:
        ...


class SkillRetriever(Protocol):
    def retrieve(self, skills: list[SkillMetadata], request: SkillSelectionRequest) -> RetrievalResult:
        ...


class SkillSelector(Protocol):
    def select(self, candidates: list[RetrievalCandidate], request: SkillSelectionRequest) -> SelectionResult:
        ...


class SkillContentLoader(Protocol):
    def load(self, skills: list[SkillMetadata], request: SkillSelectionRequest) -> LoadResult:
        ...


class SkillIntegrator(Protocol):
    def integrate(
        self,
        retrieval: RetrievalResult,
        selection: SelectionResult,
        load: LoadResult,
        request: SkillSelectionRequest,
    ) -> IntegrationResult:
        ...
