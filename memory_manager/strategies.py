from core.utils import tokenize
from memory_manager.base import MemoryRetrievalStrategy
from memory_manager.types import MemoryQuery, MemoryRecord


class RecentMemoryStrategy(MemoryRetrievalStrategy):
    def retrieve(self, records: list[MemoryRecord], query: MemoryQuery) -> list[MemoryRecord]:
        filtered_records = [record for record in records if self._matches_scope(record, query)]
        return sorted(filtered_records, key=lambda record: record.created_at, reverse=True)[: query.limit]

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


class KeywordMemoryStrategy(MemoryRetrievalStrategy):
    def retrieve(self, records: list[MemoryRecord], query: MemoryQuery) -> list[MemoryRecord]:
        normalized_query = query.query_text.lower().strip()
        query_tokens = tokenize(query.query_text)
        scored_records: list[tuple[int, MemoryRecord]] = []

        for record in records:
            if not self._matches_scope(record, query):
                continue
            normalized_text = record.content.lower()
            record_tokens = tokenize(record.content)
            overlap = len(query_tokens & record_tokens)
            exact_bonus = 3 if normalized_query and normalized_query in normalized_text else 0
            score = overlap + exact_bonus
            if score == 0:
                continue
            scored_records.append((score, record))

        scored_records.sort(key=lambda item: (item[0], item[1].created_at), reverse=True)
        return [record for _, record in scored_records[: query.limit]]

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
