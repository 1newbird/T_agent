from dataclasses import dataclass, field


@dataclass
class PromptBlock:
    key: str
    content: str
    source: str | None = None
    updated_at: str | None = None


@dataclass
class SessionPromptState:
    session_id: str
    user_id: str | None = None
    blocks: list[PromptBlock] = field(default_factory=list)
