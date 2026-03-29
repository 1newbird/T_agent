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
        primary_skill = loaded_skills[0] if loaded_skills else None
        auxiliary_skills = loaded_skills[1:] if len(loaded_skills) > 1 else []

        return IntegrationResult(
            payload={
                "skills_prompt": self._build_skills_prompt(primary_skill, auxiliary_skills),
                "primary_skill": primary_skill,
                "auxiliary_skills": auxiliary_skills,
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

    def _build_skills_prompt(self, primary_skill: dict | None, auxiliary_skills: list[dict]) -> str:
        if not primary_skill:
            return ""

        sections = [
            "## 当前匹配到的技能",
            "以下技能是根据当前用户问题动态检索出的，请优先参考并遵循。",
            "",
            "### 主技能：" + primary_skill["name"],
            primary_skill["content"],
            "",
        ]

        if auxiliary_skills:
            sections.append("### 备选技能（仅供参考）")
            for skill in auxiliary_skills:
                sections.append(f"- **{skill['name']}**：{skill['description']}")
            sections.append("")

        sections.extend(
            [
                "## 技能使用规则",
                "- 以主技能的要求为核心，严格遵循其指令。",
                "- 备选技能仅在主技能未覆盖且与用户意图相关时参考。",
                "- 如果主技能与备选技能冲突，以主技能为准。",
            ]
        )
        return "\n".join(sections)
