# Memory Manager 示例文档

## 1. 模块概览

`memory_manager` 当前由 7 个文件组成：

- `types.py`：定义核心数据结构（`MemoryScope`、`MemoryRecord`、`MemoryQuery`）。
- `base.py`：定义后端与检索策略协议（接口约束）。
- `file_backend.py`：文件型后端，按作用域写入/读取 `records.jsonl`。
- `strategies.py`：检索策略（最近优先、关键词匹配）。
- `service.py`：统一入口，负责保存、检索、构建记忆记录、拼接 prompt 文本。
- `similarity.py`：预留语义检索结果结构（当前未在主流程中使用）。
- `__init__.py`：空文件。


## 2. 关键对象说明

### `MemoryScope`
用于限定“记忆空间”，维度包括：
- `user_id`
- `session_id`（可选）
- `agent_id`（可选）
- `memory_type`：`"short_term"` 或 `"long_term"`

### `MemoryRecord`
单条记忆记录，包含：
- 基本标识：`id`、`user_id`、`created_at`、`memory_type`
- 语义字段：`category`、`content`、`role`
- 辅助字段：`source`、`session_id`、`agent_id`、`metadata`

### `MemoryQuery`
检索请求对象，包含查询文本、limit 和作用域过滤条件。


## 3. 存储结构（文件后端）

`FilesystemJsonlMemoryBackend` 会将数据按 scope 分目录：

`<root_dir>/<user_id>/<memory_type>/<session_id?>/<agent_id?>/records.jsonl`

每条记录是一行 JSON（JSONL），append-only 写入。


## 4. 检索流程

`MemoryService.retrieve_records(...)` 的流程：

1. 读取作用域下全部记录。
2. 先走规则检索（默认 `KeywordMemoryStrategy`）。
3. 再走语义检索（若配置了 embedding 模型）。
4. 将规则结果 + 语义结果去重合并，按 `limit` 截断。

其中关键词策略打分逻辑：
- token overlap 数量 + 命中完整 query 的额外 bonus。
- 最终按 `(score, created_at)` 倒序。


## 5. 最小可运行示例

```python
from pathlib import Path
from langchain.messages import HumanMessage, AIMessage

from memory_manager.service import build_memory_service
from memory_manager.types import MemoryScope


def demo():
    service = build_memory_service(Path("."))

    # 1) 短期记忆 scope
    short_scope = MemoryScope(
        user_id="u_001",
        session_id="s_001",
        agent_id="agent_main",
        memory_type="short_term",
    )

    # 2) 构造最近一轮对话消息 -> 生成短期记录 -> 保存
    last_turn = [
        HumanMessage(content="我在准备日本旅行，预算 1 万。"),
        AIMessage(content="可以先把预算拆成机票、住宿和交通。"),
    ]
    short_records = service.build_short_term_records(short_scope, last_turn)
    service.save_records(short_scope, short_records)

    # 3) 检索短期记忆
    hits = service.retrieve_records(short_scope, "旅行预算", limit=3)
    for item in hits:
        print(item.created_at, item.category, item.content)

    # 4) 生成可直接拼到提示词里的文本
    prompt_memory = service.get_prompt_memory(short_scope, "旅行预算", limit=3)
    print(prompt_memory)

    # 5) 长期记忆示例（从用户消息提取“偏好/事实”）
    long_scope = MemoryScope(
        user_id="u_001",
        session_id="s_001",
        agent_id="agent_main",
        memory_type="long_term",
    )
    long_records = service.build_long_term_records(
        long_scope,
        [HumanMessage(content="请记住，我以后希望你都用中文回复。")],
    )
    service.save_records(long_scope, long_records)


if __name__ == "__main__":
    demo()
```


## 6. 当前实现注意点

- `build_memory_service()` 默认会初始化 embedding 模型（`core.LLM.init_embedding_model()`），若模型不可用，语义检索部分可能退化或报错，需按你的运行环境确认。
- `build_long_term_records()` 使用关键词启发式判断“是否像长期记忆”，规则较简单。
- `service.py` 里部分中文注释和关键词字符串存在编码异常（乱码），建议后续统一成 UTF-8 正常文本，避免长期记忆提取规则失效。
