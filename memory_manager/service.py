import datetime
import uuid
from pathlib import Path

from langchain.messages import AIMessage, HumanMessage
from langchain_core.embeddings import Embeddings

from core.LLM import init_embedding_model
from core.utils import cosine_similarity
from memory_manager.base import MemoryBackend, MemoryRetrievalStrategy
from memory_manager.file_backend import FilesystemJsonlMemoryBackend
from memory_manager.strategies import KeywordMemoryStrategy
from memory_manager.types import MemoryQuery, MemoryRecord, MemoryScope


class MemoryService:
    def __init__(
        self,
        backend: MemoryBackend,
        retrieval_strategy: MemoryRetrievalStrategy,
        embedding_model: Embeddings | None = None,
    ):
        self.backend = backend
        self.retrieval_strategy = retrieval_strategy
        self.embedding_model = embedding_model

    # 统一保存接口：外部只需要给 scope 和 record 列表，不依赖具体 agent 框架。
    def save_records(self, scope: MemoryScope, records: list[MemoryRecord]) -> None:
        self.backend.append_records(scope, records)

    # 统一检索接口：先做规则检索，再补充 embedding 相似性召回。
    def retrieve_records(self, scope: MemoryScope, query_text: str, limit: int = 5) -> list[MemoryRecord]:
        query = MemoryQuery(
            user_id=scope.user_id,
            session_id=scope.session_id,
            agent_id=scope.agent_id,
            memory_type=scope.memory_type,
            query_text=query_text,
            limit=limit,
        )
        records = self.backend.load_records(scope)
        keyword_records = self.retrieval_strategy.retrieve(records, query)
        semantic_records = self._semantic_retrieve(records, query)
        return self._merge_results(keyword_records, semantic_records, limit)

    # 给中间件/智能体直接用的 prompt 格式化入口。
    def get_prompt_memory(self, scope: MemoryScope, query_text: str, limit: int = 5) -> str:
        records = self.retrieve_records(scope, query_text, limit=limit)
        if not records:
            return ""

        title = "## 短期记忆" if scope.memory_type == "short_term" else "## 长期记忆"
        lines = [
            title,
            "以下内容来自记忆管理系统，请仅在有帮助时参考，不要当作绝对事实。",
            "",
        ]
        for record in records:
            lines.append(f"- [{record.created_at}] {record.category}: {record.content}")
        return "\n".join(lines)

    def extract_last_turn_messages(self, messages: list) -> list:
        latest_ai_index = None
        latest_human_index = None

        for index in range(len(messages) - 1, -1, -1):
            message = messages[index]
            if latest_ai_index is None and isinstance(message, AIMessage) and message.content:
                latest_ai_index = index
                continue
            if latest_ai_index is not None and isinstance(message, HumanMessage) and message.content:
                latest_human_index = index
                break

        if latest_human_index is None:
            latest_human = next(
                (message for message in reversed(messages) if isinstance(message, HumanMessage) and message.content),
                None,
            )
            return [latest_human] if latest_human else []

        if latest_ai_index is None:
            return [messages[latest_human_index]]

        return [messages[latest_human_index], messages[latest_ai_index]]

    # 从最后一轮消息提炼短期记忆，避免被框架内部重复拼接的消息污染。
    def build_short_term_records(self, scope: MemoryScope, messages: list) -> list[MemoryRecord]:
        return self._build_conversation_records(scope, messages, memory_type="short_term")

    # 从最后一轮消息提炼长期记忆。当前先做一个稳定、可解释的实现：仅提取用户消息中的长期事实。
    def build_long_term_records(self, scope: MemoryScope, messages: list) -> list[MemoryRecord]:
        records = []
        session_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for msg in messages:
            if not isinstance(msg, HumanMessage):
                continue
            content = str(msg.content).strip()
            if not content:
                continue
            if not self._looks_like_long_term_memory(content):
                continue
            records.append(
                MemoryRecord(
                    id=str(uuid.uuid4()),
                    user_id=scope.user_id,
                    session_id=scope.session_id,
                    agent_id=scope.agent_id,
                    created_at=session_time,
                    memory_type="long_term",
                    category="preference_or_fact",
                    content=content,
                    role="user",
                    metadata={"captured_from": "human_message"},
                )
            )
        return records

    def _build_conversation_records(self, scope: MemoryScope, messages: list, memory_type: str) -> list[MemoryRecord]:
        session_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        records: list[MemoryRecord] = []

        for msg in messages:
            if isinstance(msg, HumanMessage) and msg.content:
                records.append(
                    MemoryRecord(
                        id=str(uuid.uuid4()),
                        user_id=scope.user_id,
                        session_id=scope.session_id,
                        agent_id=scope.agent_id,
                        created_at=session_time,
                        memory_type=memory_type,
                        category="conversation_user",
                        content=str(msg.content),
                        role="user",
                    )
                )
            elif isinstance(msg, AIMessage) and msg.content:
                records.append(
                    MemoryRecord(
                        id=str(uuid.uuid4()),
                        user_id=scope.user_id,
                        session_id=scope.session_id,
                        agent_id=scope.agent_id,
                        created_at=session_time,
                        memory_type=memory_type,
                        category="conversation_assistant",
                        content=str(msg.content),
                        role="assistant",
                    )
                )

        return records

    def _semantic_retrieve(self, records: list[MemoryRecord], query: MemoryQuery) -> list[MemoryRecord]:
        if self.embedding_model is None or not query.query_text.strip():
            return []

        filtered_records = [record for record in records if self._matches_scope(record, query)]
        if not filtered_records:
            return []

        query_vector = self.embedding_model.embed_query(query.query_text)
        doc_vectors = self.embedding_model.embed_documents([record.content for record in filtered_records])
        scored_records: list[tuple[float, MemoryRecord]] = []

        for record, doc_vector in zip(filtered_records, doc_vectors, strict=False):
            score = cosine_similarity(query_vector, doc_vector)
            if score <= 0:
                continue
            scored_records.append((score, record))

        scored_records.sort(key=lambda item: item[0], reverse=True)
        return [record for score, record in scored_records[: query.limit] if score > 0.5]

    def _merge_results(
        self,
        keyword_records: list[MemoryRecord],
        semantic_records: list[MemoryRecord],
        limit: int,
    ) -> list[MemoryRecord]:
        merged: list[MemoryRecord] = []
        seen_ids: set[str] = set()
        for record in keyword_records + semantic_records:
            if record.id in seen_ids:
                continue
            seen_ids.add(record.id)
            merged.append(record)
            if len(merged) >= limit:
                break
        return merged

    def _matches_scope(self, record: MemoryRecord, query: MemoryQuery) -> bool:
        if record.user_id != query.user_id:
            return False
        if record.memory_type != query.memory_type:
            return False
        if query.session_id and record.session_id != query.session_id:
            return False
        if query.agent_id and record.agent_id != query.agent_id:
            return False
        return True

    def _looks_like_long_term_memory(self, content: str) -> bool:
        keywords = ["我喜欢", "我不喜欢", "我通常", "以后", "请你", "记住", "我的", "我是"]
        return any(keyword in content for keyword in keywords)


def build_memory_service(base_dir: Path) -> MemoryService:
    backend = FilesystemJsonlMemoryBackend(base_dir / "workspace" / "memory")
    strategy = KeywordMemoryStrategy()
    embedding_model = init_embedding_model()
    return MemoryService(
        backend=backend,
        retrieval_strategy=strategy,
        embedding_model=embedding_model,
    )
