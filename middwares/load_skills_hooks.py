from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain.agents.middleware.types import ModelRequest
from langchain.messages import SystemMessage
from langgraph.runtime import Runtime

from core.logger import get_logger
from skills_manager.service import SkillsService
from skills_manager.types import SkillSelectionRequest
from sysprompt.service import SyspromptService
from tools.registry import get_tools_by_names

logger = get_logger(__name__)


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

        try:
            task = str(messages[-1].content)
            request = SkillSelectionRequest(
                query_text=task,
                screening_mode=self.screening_mode,
                context={"runtime": type(runtime).__name__},
            )
            resolution = self.skills_service.resolve_skills(request)
            payload = resolution.integration.payload
            skills_prompt = payload.get("skills_prompt", "")

            # 有新 skill → 覆写；没召回到 → 保留旧的，不清空。
            # 旧 skill 会在下次召回到新 skill 时被 set_block 自然替换。
            if skills_prompt:
                self.sysprompt_service.set_block(
                    user_id=user_id,
                    session_id=session_id,
                    key="skills",
                    content=skills_prompt,
                    source="skills_middleware",
                )
                for skill in payload.get("selected_skills", []):
                    logger.info(f"本次激活skill：{skill['name']}")
            else:
                logger.info("本次回复无关联skill，延续以前版本")

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
        except Exception:
            logger.exception("SkillsMiddleware 执行失败，跳过技能注入，使用原始 prompt 继续")
            return None

    # ── 动态 Tool 筛选 ──────────────────────────────────
    # 每次 model 调用前，根据选中 skill 声明的 tools 字段筛选工具子集。
    # - skill 未声明 tools → 不筛选，LLM 看到全量 tools
    # - skill 声明了 tools → 只保留声明的 tools
    # - request.override() 返回新实例，不影响下一轮
    def wrap_model_call(self, request: ModelRequest, handler):
        loaded_skills = request.state.get("loaded_skills", [])

        if loaded_skills:
            primary = loaded_skills[0]
            skill_tool_names = primary.get("metadata", {}).get("tools", [])

            if skill_tool_names:
                skill_tools = get_tools_by_names(skill_tool_names)
                if skill_tools:
                    logger.info(
                        "skill '%s' 声明了 tools %s，动态筛选工具列表",
                        primary.get("name", "unknown"),
                        skill_tool_names,
                    )
                    request = request.override(tools=skill_tools)
                else:
                    logger.warning(
                        "skill '%s' 声明的 tools %s 全部未注册，保留全量工具",
                        primary.get("name", "unknown"),
                        skill_tool_names,
                    )
            # else: skill 没声明 tools → 不做筛选，LLM 看到全量 tools

        return handler(request)
