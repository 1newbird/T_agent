import datetime
from pathlib import Path

from sysprompt.file_backend import FilesystemPromptBackend
from sysprompt.types import PromptBlock, SessionPromptState


DEFAULT_BLOCK_ORDER = ["safety", "profile", "memory", "skills"]


class SyspromptService:
    def __init__(self, backend: FilesystemPromptBackend):
        self.backend = backend

    def set_block(
        self,
        user_id: str,
        session_id: str,
        key: str,
        content: str,
        source: str | None = None,
    ) -> None:
        state = self.backend.load_state(user_id, session_id)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for index, block in enumerate(state.blocks):
            if block.key != key:
                continue
            state.blocks[index] = PromptBlock(
                key=key,
                content=content,
                source=source,
                updated_at=timestamp,
            )
            self.backend.save_state(state)
            return

        state.blocks.append(
            PromptBlock(
                key=key,
                content=content,
                source=source,
                updated_at=timestamp,
            )
        )
        self.backend.save_state(state)

    def clear_block(self, user_id: str, session_id: str, key: str) -> None:
        state = self.backend.load_state(user_id, session_id)
        state.blocks = [block for block in state.blocks if block.key != key]
        self.backend.save_state(state)

    def get_blocks(self, user_id: str, session_id: str) -> list[PromptBlock]:
        return self.backend.load_state(user_id, session_id).blocks

    def compose_prompt(self, user_id: str, session_id: str, base_system_prompt: str) -> str:
        blocks = self.get_blocks(user_id, session_id)
        ordered_blocks = self._ordered_blocks(blocks)
        sections = [base_system_prompt.strip()]
        for block in ordered_blocks:
            if not block.content.strip():
                continue
            sections.append(block.content.strip())
        return "\n\n".join(section for section in sections if section)

    def _ordered_blocks(self, blocks: list[PromptBlock]) -> list[PromptBlock]:
        order_map = {key: index for index, key in enumerate(DEFAULT_BLOCK_ORDER)}
        return sorted(blocks, key=lambda block: (order_map.get(block.key, len(order_map)), block.key))


def build_sysprompt_service(base_dir: Path) -> SyspromptService:
    backend = FilesystemPromptBackend(base_dir / "workspace" / "sysprompt")
    return SyspromptService(backend=backend)
