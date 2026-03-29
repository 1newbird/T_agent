"""
这个模块只负责结构化记忆系统：
- before_agent 注入短期/长期记忆
- after_agent 只保存本轮新增消息形成的结构化记忆

同一件事由一个 middleware 类统一管理 before/after 生命周期。
"""
from pathlib import Path

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain.messages import SystemMessage
from langgraph.runtime import Runtime

from memory_manager.types import MemoryScope
from memory_manager.service import build_memory_service

BASE_DIR = Path(__file__).resolve().parent.parent
memory_service = build_memory_service(BASE_DIR)
DEFAULT_AGENT_ID = "langchain_agent"


class MemoryRetrievalMiddleware(AgentMiddleware):
    def __init__(self, agent_id: str = DEFAULT_AGENT_ID):
        self.agent_id = agent_id

    def before_agent(self, state: AgentState, runtime: Runtime) -> dict | None:
        messages = list(state["messages"])
        if not messages:
            return None

        query = str(messages[-1].content)
        short_scope = MemoryScope(
            user_id=runtime.context.user_id,
            session_id=runtime.context.session_id,
            agent_id=self.agent_id,
            memory_type="short_term",
        )
        long_scope = MemoryScope(
            user_id=runtime.context.user_id,
            agent_id=self.agent_id,
            memory_type="long_term",
        )

        short_term_memory = memory_service.get_prompt_memory(short_scope, query, limit=5)
        long_term_memory = memory_service.get_prompt_memory(long_scope, query, limit=5)
        memory_sections = [section for section in [short_term_memory, long_term_memory] if section]

        if memory_sections:
            memory_prompt = "\n\n".join(memory_sections)
            if messages and messages[0].type == "system":
                messages[0] = SystemMessage(content=memory_prompt + "\n\n" + messages[0].content)
            else:
                messages.insert(0, SystemMessage(content=memory_prompt))

        return {
            "messages": messages,
        }


class StructuredMemoryPersistenceMiddleware(AgentMiddleware):
    def __init__(self, agent_id: str = DEFAULT_AGENT_ID):
        self.agent_id = agent_id

    def after_agent(self, state: AgentState, runtime: Runtime) -> dict | None:
        messages = list(state["messages"])
        last_turn_messages = memory_service.extract_last_turn_messages(messages)
        if not last_turn_messages:
            return None

        short_scope = MemoryScope(
            user_id=runtime.context.user_id,
            session_id=runtime.context.session_id,
            agent_id=self.agent_id,
            memory_type="short_term",
        )
        long_scope = MemoryScope(
            user_id=runtime.context.user_id,
            agent_id=self.agent_id,
            memory_type="long_term",
        )

        short_records = memory_service.build_short_term_records(short_scope, last_turn_messages)
        long_records = memory_service.build_long_term_records(long_scope, last_turn_messages)
        memory_service.save_records(short_scope, short_records)
        memory_service.save_records(long_scope, long_records)
        return None



