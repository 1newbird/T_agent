from pathlib import Path

from skills_manager.base import SkillCatalogBackend, SkillContentLoader
from skills_manager.types import LoadResult, LoadedSkillContent, SkillMetadata, SkillSelectionRequest
from tools.load_skills import load_skills


class FilesystemSkillCatalogBackend(SkillCatalogBackend):
    def __init__(self, skills_dir: Path | str):
        self.skills_dir = Path(skills_dir)

    def load_metadata(self) -> list[SkillMetadata]:
        skills = load_skills(str(self.skills_dir))
        return [
            SkillMetadata(
                name=skill["name"],
                description=skill["description"],
                path=skill["path"],
                metadata=skill.get("metadata", {}),
            )
            for skill in skills
        ]


class MarkdownSkillContentLoader(SkillContentLoader):
    def load(self, skills: list[SkillMetadata], request: SkillSelectionRequest) -> LoadResult:
        loaded = []
        for skill in skills:
            content = Path(skill.path).read_text(encoding="utf-8")
            loaded.append(LoadedSkillContent(skill=skill, content=content))
        return LoadResult(loaded=loaded)
