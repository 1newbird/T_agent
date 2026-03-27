import json
from dataclasses import asdict
from pathlib import Path

from sysprompt.types import PromptBlock, SessionPromptState


class FilesystemPromptBackend:
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir

    def load_state(self, user_id: str, session_id: str) -> SessionPromptState:
        state_path = self.state_path(user_id, session_id)
        if not state_path.exists():
            return SessionPromptState(session_id=session_id, user_id=user_id, blocks=[])

        payload = json.loads(state_path.read_text(encoding="utf-8"))
        return SessionPromptState(
            session_id=payload["session_id"],
            user_id=payload.get("user_id"),
            blocks=[PromptBlock(**block) for block in payload.get("blocks", [])],
        )

    def save_state(self, state: SessionPromptState) -> None:
        state_path = self.state_path(state.user_id or "", state.session_id)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(asdict(state), ensure_ascii=False, indent=2), encoding="utf-8")

    def state_path(self, user_id: str, session_id: str) -> Path:
        return self.root_dir / f"{user_id}_{session_id}.json"
