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
        """Agent启动时执行一次：解析技能并存储到state中，不修改messages"""
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

            # 只返回状态更新，不修改messages（系统提示词在 wrap_model_call 中注入）
            return {
                "skills_prompt": skills_prompt,
                "skill_candidates": payload.get("skill_candidates", []),
                "selected_skills": payload.get("selected_skills", []),
                "loaded_skills": payload.get("loaded_skills", []),
                # 保存 user_id/session_id 供 wrap_model_call 使用
                "_user_id": user_id,
                "_session_id": session_id,
            }
        except Exception:
            logger.exception("SkillsMiddleware 执行失败，跳过技能注入")
            return None

    def _get_system_prompt(self, state: AgentState, runtime: Runtime) -> str | None:
        """获取完整的系统提示词（供 wrap_model_call 使用）"""
        context = getattr(runtime, "context", None)
        user_id = state.get("_user_id") or (getattr(context, "user_id", None) if context else None)
        session_id = state.get("_session_id") or (getattr(context, "session_id", None) if context else None)

        if not user_id or not session_id:
            return self.base_system_prompt

        return self.sysprompt_service.compose_prompt(
            user_id=user_id,
            session_id=session_id,
            base_system_prompt=self.base_system_prompt,
        )

    def _filter_tools_by_skill(self, request: ModelRequest) -> ModelRequest:
        """根据当前 skill 声明的 tools 字段筛选工具子集（sync/async 共用逻辑）。"""
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

        return request

    def _prepare_request(self, request: ModelRequest) -> ModelRequest:
        """统一处理请求：过滤旧 SystemMessage + 注入新系统提示词 + 筛选工具"""
        # 1. 过滤掉 messages 中已有的 SystemMessage（防止 Anthropic 报多个 system message 错误）
        non_system_messages = [m for m in request.messages if not isinstance(m, SystemMessage)]

        # 2. 动态获取系统提示词
        final_system_prompt = self._get_system_prompt(request.state, request.runtime)

        # 3. 筛选工具
        request = self._filter_tools_by_skill(request)

        # 4. 用 override 设置：清理后的 messages + 新的 system_message
        if final_system_prompt:
            request = request.override(
                messages=non_system_messages,
                system_message=SystemMessage(content=final_system_prompt)
            )
        else:
            # 即使没有新 prompt，也要清理 messages 中的 SystemMessage
            request = request.override(messages=non_system_messages)

        return request

    def wrap_model_call(self, request: ModelRequest, handler):
        """每次模型调用前：注入系统提示词 + 筛选工具"""
        request = self._prepare_request(request)
        return handler(request)

    async def awrap_model_call(self, request: ModelRequest, handler):
        """异步版本：每次模型调用前注入系统提示词 + 筛选工具"""
        request = self._prepare_request(request)
        return await handler(request)
