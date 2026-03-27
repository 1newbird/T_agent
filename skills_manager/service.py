from pathlib import Path

from core.LLM import init_embedding_model, init_llm
from skills_manager.base import (
    SkillCatalogBackend,
    SkillContentLoader,
    SkillIntegrator,
    SkillRetriever,
    SkillSelector,
)
from skills_manager.integrators import StateInjectionIntegrator
from skills_manager.loaders import FilesystemSkillCatalogBackend, MarkdownSkillContentLoader
from skills_manager.screening_strategies import (
    EmbeddingRetriever,
    HybridRetriever,
    KeywordLLMRetriever,
    KeywordRetriever,
    LLMSelector,
    PassThroughRetriever,
)
from skills_manager.types import (
    CatalogResult,
    IntegrationResult,
    LoadResult,
    RetrievalResult,
    SelectionResult,
    SkillResolutionResult,
    SkillSelectionRequest,
)


class SkillsService:
    def __init__(
        self,
        catalog_backend: SkillCatalogBackend,
        retriever: SkillRetriever,
        selector: SkillSelector,
        content_loader: SkillContentLoader,
        integrator: SkillIntegrator,
    ):
        self.catalog_backend = catalog_backend
        self.retriever = retriever
        self.selector = selector
        self.content_loader = content_loader
        self.integrator = integrator

    def load_catalog(self) -> CatalogResult:
        return CatalogResult(skills=self.catalog_backend.load_metadata())

    def retrieve_skills(self, catalog: CatalogResult, request: SkillSelectionRequest) -> RetrievalResult:
        return self.retriever.retrieve(catalog.skills, request)

    def select_skills(self, retrieval: RetrievalResult, request: SkillSelectionRequest) -> SelectionResult:
        return self.selector.select(retrieval.candidates, request)

    def load_skills_content(self, selection: SelectionResult, request: SkillSelectionRequest) -> LoadResult:
        return self.content_loader.load([item.skill for item in selection.selected], request)

    def integrate_skills(
        self,
        retrieval: RetrievalResult,
        selection: SelectionResult,
        load: LoadResult,
        request: SkillSelectionRequest,
    ) -> IntegrationResult:
        return self.integrator.integrate(retrieval, selection, load, request)

    def resolve_skills(self, request: SkillSelectionRequest) -> SkillResolutionResult:
        catalog = self.load_catalog()
        retrieval = self.retrieve_skills(catalog, request)
        selection = self.select_skills(retrieval, request)
        load = self.load_skills_content(selection, request)
        integration = self.integrate_skills(retrieval, selection, load, request)
        return SkillResolutionResult(
            catalog=catalog,
            retrieval=retrieval,
            selection=selection,
            load=load,
            integration=integration,
        )


def build_skills_service(base_dir: Path, screening_mode: str = "passthrough") -> SkillsService:
    llm = init_llm()
    embedding_model = init_embedding_model()
    catalog_backend = FilesystemSkillCatalogBackend(base_dir / "skills")
    keyword_retriever = KeywordRetriever()
    embedding_retriever = EmbeddingRetriever(embedding_model)

    retriever: SkillRetriever = PassThroughRetriever()
    if screening_mode == "keyword":
        retriever = keyword_retriever
    elif screening_mode == "embedding":
        retriever = embedding_retriever
    elif screening_mode == "hybrid":
        retriever = HybridRetriever(keyword_retriever, embedding_retriever)
    elif screening_mode == "keyword_llm":
        retriever = KeywordLLMRetriever(llm)

    selector = LLMSelector(llm)
    content_loader = MarkdownSkillContentLoader()
    integrator = StateInjectionIntegrator()
    return SkillsService(
        catalog_backend=catalog_backend,
        retriever=retriever,
        selector=selector,
        content_loader=content_loader,
        integrator=integrator,
    )
