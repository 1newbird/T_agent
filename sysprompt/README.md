# Sysprompt 示例文档

## 1. 模块概览

`sysprompt` 当前由 4 个文件组成：

- `types.py`：定义核心数据结构（`PromptBlock`、`SessionPromptState`）。
- `file_backend.py`：文件型后端，按 user + session 读写 JSON 状态文件。
- `service.py`：统一入口 `SyspromptService`，负责 block 的增删和最终 prompt 组装；工厂函数 `build_sysprompt_service()`。
- `__init__.py`：空文件。


## 2. 设计背景

智能体的 system prompt 通常由多个部分拼接而成，其中一部分是**静态的**（如安全规则、人设），另一部分是**动态的**（如记忆、技能）。

动态部分的关键问题：**当使用 checkpointer 恢复历史对话时，旧的动态内容（如上一轮匹配的 skills）不应残留在 prompt 中。** 每次进入对话都应该根据当前上下文重新生成。

`sysprompt` 的解决方式：
- 将 system prompt 拆成多个**命名 block**（如 `safety`、`profile`、`memory`、`skills`）。
- 动态模块（如 skills 中间件）每次运行时通过 `set_block` / `clear_block` 覆写自己的 block。
- 最终由 `compose_prompt` 按固定顺序拼接，保证 prompt 结构稳定、动态内容始终是最新的。

```
┌─────────────────────────────────────────────────────┐
│                  最终 System Prompt                   │
├─────────────────────────────────────────────────────┤
│  base_system_prompt（基础人设，由调用方传入）            │
├─────────────────────────────────────────────────────┤
│  [safety]   安全规则        ← 静态，设置一次不再变       │
│  [profile]  用户画像        ← 静态或低频更新             │
│  [memory]   记忆上下文      ← 动态，每轮由记忆中间件覆写   │
│  [skills]   技能指令        ← 动态，每轮由技能中间件覆写   │
└─────────────────────────────────────────────────────┘
```


## 3. 关键对象说明

### `PromptBlock`
单个 prompt 片段：
- `key`：唯一标识（如 `"safety"`、`"skills"`）
- `content`：实际文本内容
- `source`：来源标记，便于追踪（如 `"skills_middleware"`、`"admin"`）
- `updated_at`：最后更新时间

### `SessionPromptState`
一个会话下所有 block 的集合：
- `session_id`：会话 ID
- `user_id`：用户 ID
- `blocks`：该会话的全部 `PromptBlock` 列表


## 4. Block 排序规则

`compose_prompt` 按以下固定顺序拼接 block：

```python
DEFAULT_BLOCK_ORDER = ["safety", "profile", "memory", "skills"]
```

- 已知 key 按定义顺序排列（safety 最优先）。
- 未知 key 排在已知 key 之后，按字母序排列。
- 保证无论 block 写入顺序如何，最终 prompt 结构始终一致。


## 5. 存储结构（文件后端）

`FilesystemPromptBackend` 将状态保存为 JSON 文件：

```
<root_dir>/<user_id>_<session_id>.json
```

文件内容示例：
```json
{
  "session_id": "s_001",
  "user_id": "u_001",
  "blocks": [
    {
      "key": "safety",
      "content": "你必须遵守以下安全规则...",
      "source": "admin",
      "updated_at": "2026-03-29 10:00:00"
    },
    {
      "key": "skills",
      "content": "## 当前匹配到的技能\n...",
      "source": "skills_middleware",
      "updated_at": "2026-03-29 10:05:00"
    }
  ]
}
```


## 6. 核心 API

### `set_block` — 写入/覆写一个 block
```python
service.set_block(
    user_id="u_001",
    session_id="s_001",
    key="skills",
    content="## 当前匹配到的技能\n...",
    source="skills_middleware",
)
```
- 如果该 key 已存在：**原地替换**内容和时间戳。
- 如果该 key 不存在：追加到 blocks 列表末尾。
- 这是动态 block 每轮"刷新"自己的核心操作。

### `clear_block` — 移除一个 block
```python
service.clear_block(user_id="u_001", session_id="s_001", key="skills")
```
- 当某个动态模块判断"本轮没有需要注入的内容"时调用。
- 确保旧内容不会残留在下一次 `compose_prompt` 的输出中。

### `compose_prompt` — 组装最终 system prompt
```python
final_prompt = service.compose_prompt(
    user_id="u_001",
    session_id="s_001",
    base_system_prompt="你是一个通用 AI 助手。",
)
```
- 以 `base_system_prompt` 开头。
- 按 `DEFAULT_BLOCK_ORDER` 顺序追加所有非空 block。
- 各部分之间用 `\n\n` 分隔。


## 7. 与中间件的配合方式

以 `SkillsMiddleware` 为例（`middwares/load_skills_hooks.py`），展示动态 block 的典型生命周期：

```python
class SkillsMiddleware(AgentMiddleware):
    def before_agent(self, state, runtime):
        # 1) 根据用户最新消息匹配技能
        resolution = self.skills_service.resolve_skills(request)
        skills_prompt = resolution.integration.payload.get("skills_prompt", "")

        # 2) 有技能 → set_block 覆写；无技能 → clear_block 清除旧内容
        if skills_prompt:
            self.sysprompt_service.set_block(
                user_id=user_id, session_id=session_id,
                key="skills", content=skills_prompt, source="skills_middleware",
            )
        else:
            self.sysprompt_service.clear_block(
                user_id=user_id, session_id=session_id, key="skills",
            )

        # 3) 组装最终 prompt，替换 messages 中的 system message
        final_prompt = self.sysprompt_service.compose_prompt(
            user_id=user_id, session_id=session_id,
            base_system_prompt=self.base_system_prompt,
        )
        return {"messages": [SystemMessage(content=final_prompt), ...]}
```

这样即使通过 checkpointer 恢复旧对话，skills block 也会在 `before_agent` 中被重新写入或清除，不会有上一轮的残留。


## 8. 最小可运行示例

```python
from pathlib import Path
from sysprompt.service import build_sysprompt_service

service = build_sysprompt_service(Path("."))

# 1) 写入静态 block
service.set_block("u_001", "s_001", key="safety", content="请遵守安全规则。", source="admin")
service.set_block("u_001", "s_001", key="profile", content="用户偏好中文回复。", source="profile_loader")

# 2) 写入动态 block（每轮由中间件覆写）
service.set_block("u_001", "s_001", key="skills", content="## 主技能：github_pr\n...", source="skills_middleware")

# 3) 组装最终 prompt
prompt = service.compose_prompt("u_001", "s_001", base_system_prompt="你是一个通用 AI 助手。")
print(prompt)
# 输出：
# 你是一个通用 AI 助手。
#
# 请遵守安全规则。
#
# 用户偏好中文回复。
#
# ## 主技能：github_pr
# ...

# 4) 下一轮没有匹配到技能 → 清除 skills block
service.clear_block("u_001", "s_001", key="skills")
prompt = service.compose_prompt("u_001", "s_001", base_system_prompt="你是一个通用 AI 助手。")
print(prompt)
# 输出中不再包含 skills 部分
```


## 9. 当前实现注意点

- 存储路径为 `{base_dir}/workspace/sysprompt/{user_id}_{session_id}.json`，user_id 和 session_id 中不应包含 `_` 以外的特殊字符，否则可能导致文件名冲突。
- `set_block` / `clear_block` 每次都会读写磁盘（load → mutate → save），高并发场景下可能需要加锁或换后端。
- `DEFAULT_BLOCK_ORDER` 定义在 `service.py` 中，新增 block 类型时需同步更新排序列表，否则会排到末尾。
- `__init__.py` 为空，使用时需用完整路径 import，如 `from sysprompt.service import build_sysprompt_service`。
