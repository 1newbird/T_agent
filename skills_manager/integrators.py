from skills_manager.base import SkillIntegrator
from skills_manager.types import IntegrationResult, LoadResult, RetrievalResult, SelectionResult, SkillSelectionRequest


class StateInjectionIntegrator(SkillIntegrator):
    def integrate(
        self,
        retrieval: RetrievalResult,
        selection: SelectionResult,
        load: LoadResult,
        request: SkillSelectionRequest,
    ) -> IntegrationResult:
        loaded_skills = [
            {
                "name": loaded.skill.name,
                "description": loaded.skill.description,
                "path": loaded.skill.path,
                "content": loaded.content,
            }
            for loaded in load.loaded
        ]
        return IntegrationResult(
            payload={
                "skills_prompt": self._build_skills_prompt(loaded_skills),
                "skill_candidates": [
                    {
                        "name": candidate.skill.name,
                        "description": candidate.skill.description,
                        "path": candidate.skill.path,
                        "score": candidate.score,
                        "reason": candidate.reason,
                        "source": candidate.source,
                    }
                    for candidate in retrieval.candidates
                ],
                "selected_skills": [
                    {
                        "name": item.skill.name,
                        "description": item.skill.description,
                        "path": item.skill.path,
                        "score": item.score,
                        "reason": item.reason,
                    }
                    for item in selection.selected
                ],
                "loaded_skills": loaded_skills,
            }
        )

    def _build_skills_prompt(self, loaded_skills: list[dict]) -> str:
        if not loaded_skills:
            return ""

        sections = [
            "## 当前匹配到的技能",
            "以下技能是根据当前用户问题动态检索出的，请优先参考并遵循。",
            "",
        ]
        for index, skill in enumerate(loaded_skills, start=1):
            sections.extend(
                [
                    f"### 技能 {index}：{skill['name']}",
                    skill["content"],
                    "",
                ]
            )

        sections.extend(
            [
                "## 技能使用规则",
                "- 优先遵循与当前任务最直接相关的技能要求。",
                "- 更具体的技能要求优先于更通用的技能要求。",
                "- 如果多个技能要求冲突，请选择最贴近当前用户意图的做法。",
            ]
        )
        return "\n".join(sections)
