import json
from dataclasses import asdict
from pathlib import Path

from memory_manager.base import MemoryBackend
from memory_manager.types import MemoryRecord, MemoryScope


class FilesystemJsonlMemoryBackend(MemoryBackend):
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir

    def append_records(self, scope: MemoryScope, records: list[MemoryRecord]) -> None:
        if not records:
            return
        records_path = self.records_path(scope)
        records_path.parent.mkdir(parents=True, exist_ok=True)
        with records_path.open("a", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")

    def load_records(self, scope: MemoryScope) -> list[MemoryRecord]:
        records_path = self.records_path(scope)
        if not records_path.exists():
            return []

        records: list[MemoryRecord] = []
        with records_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                payload = json.loads(line)
                records.append(MemoryRecord(**payload))
        return records

    def scope_dir(self, scope: MemoryScope) -> Path:
        parts = [scope.user_id, scope.memory_type]
        if scope.session_id:
            parts.append(scope.session_id)
        if scope.agent_id:
            parts.append(scope.agent_id)
        path = self.root_dir
        for part in parts:
            path = path / part
        return path

    def conversation_path(self, scope: MemoryScope) -> Path:
        return self.scope_dir(scope) / "conversation.md"

    def records_path(self, scope: MemoryScope) -> Path:
        return self.scope_dir(scope) / "records.jsonl"
