from dataclasses import dataclass, field
from typing import Any, Literal


MemoryType = Literal["short_term", "long_term"]


@dataclass(frozen=True)
class MemoryScope:
    user_id: str
    session_id: str | None = None
    agent_id: str | None = None
    memory_type: MemoryType = "short_term"


@dataclass
class MemoryRecord:
    id: str
    user_id: str
    created_at: str
    memory_type: MemoryType
    category: str
    content: str
    source: str = "conversation_turn"
    session_id: str | None = None
    agent_id: str | None = None
    role: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MemoryQuery:
    user_id: str
    query_text: str
    limit: int = 5
    session_id: str | None = None
    agent_id: str | None = None
    memory_type: MemoryType = "short_term"
