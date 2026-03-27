from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain.messages import SystemMessage
from langgraph.runtime import Runtime

from skills_manager.service import SkillsService
from skills_manager.types import SkillSelectionRequest
from sysprompt.service import SyspromptService


class SkillsMiddleware(AgentMiddleware):
    def __init__(
        self,
        skills_service: SkillsService,
        sysprompt_service: SyspromptService,
        base_system_prompt: str,
        screening_mode: str = "passthrough",
    ):
        self.skills_service = skills_service
        self.sysprompt_service = sysprompt_service
        self.base_system_prompt = base_system_prompt
        self.screening_mode = screening_mode

    def before_agent(self, state: AgentState, runtime: Runtime) -> dict | None:
        messages = list(state["messages"])
        if not messages:
            return None

        context = getattr(runtime, "context", None)
        user_id = getattr(context, "user_id", None) if context is not None else None
        session_id = getattr(context, "session_id", None) if context is not None else None
        if not user_id or not session_id:
            return None

        task = str(messages[-1].content)
        request = SkillSelectionRequest(
            query_text=task,
            screening_mode=self.screening_mode,
            context={"runtime": type(runtime).__name__},
        )
        resolution = self.skills_service.resolve_skills(request)
        payload = resolution.integration.payload
        skills_prompt = payload.get("skills_prompt", "")

        if skills_prompt:
            self.sysprompt_service.set_block(
                user_id=user_id,
                session_id=session_id,
                key="skills",
                content=skills_prompt,
                source="skills_middleware",
            )
        else:
            self.sysprompt_service.clear_block(user_id=user_id, session_id=session_id, key="skills")

        final_system_prompt = self.sysprompt_service.compose_prompt(
            user_id=user_id,
            session_id=session_id,
            base_system_prompt=self.base_system_prompt,
        )

        non_system_messages = [message for message in messages if message.type != "system"]
        updated_messages = [SystemMessage(content=final_system_prompt), *non_system_messages]

        return {
            "messages": updated_messages,
            "skills_prompt": skills_prompt,
            "skill_candidates": payload.get("skill_candidates", []),
            "selected_skills": payload.get("selected_skills", []),
            "loaded_skills": payload.get("loaded_skills", []),
        }
