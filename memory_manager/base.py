from typing import Protocol

from memory_manager.types import MemoryQuery, MemoryRecord, MemoryScope


class MemoryBackend(Protocol):
    def append_records(self, scope: MemoryScope, records: list[MemoryRecord]) -> None:
        ...

    def load_records(self, scope: MemoryScope) -> list[MemoryRecord]:
        ...


class MemoryRetrievalStrategy(Protocol):
    def retrieve(self, records: list[MemoryRecord], query: MemoryQuery) -> list[MemoryRecord]:
        ...
