"""
把 markdown 会话日志保存和结构化记忆保存拆开，避免职责混在一起。
同一件事由一个 middleware 类统一管理 before/after 生命周期。
"""
from datetime import datetime
from pathlib import Path

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langgraph.runtime import Runtime

from tools.messages_save_md import format_messages_to_md, save_conversation_to_md

BASE_DIR = Path(__file__).resolve().parent.parent


class MarkdownMemoryMiddleware(AgentMiddleware):
    def __init__(self, agent_id: str = "langchain_agent"):
        self.agent_id = agent_id

    def after_agent(self, state: AgentState, runtime: Runtime) -> dict | None:
        messages = list(state["messages"])
        last_turn_messages = [message for message in self._extract_last_turn_messages(messages) if message]
        if not last_turn_messages:
            return None

        log_dir = BASE_DIR / "workspace" / "memory" / runtime.context.user_id / "short_term" / runtime.context.session_id / self.agent_id
        log_dir.mkdir(parents=True, exist_ok=True)
        file_path = log_dir / "conversation.md"
        session_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        md_content = format_messages_to_md(last_turn_messages, session_time)
        save_conversation_to_md(md_content, str(file_path))
        return None

    def _extract_last_turn_messages(self, messages: list) -> list:
        latest_ai_index = None
        latest_human_index = None

        for index in range(len(messages) - 1, -1, -1):
            message = messages[index]
            if latest_ai_index is None and getattr(message, "type", None) == "ai" and getattr(message, "content", None):
                latest_ai_index = index
                continue
            if latest_ai_index is not None and getattr(message, "type", None) == "human" and getattr(message, "content", None):
                latest_human_index = index
                break

        if latest_human_index is None:
            for message in reversed(messages):
                if getattr(message, "type", None) == "human" and getattr(message, "content", None):
                    return [message]
            return []

        if latest_ai_index is None:
            return [messages[latest_human_index]]

        return [messages[latest_human_index], messages[latest_ai_index]]
