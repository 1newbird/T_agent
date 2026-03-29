# Tools 模块

## 设计思路

LangChain v1 的限制：**tools 必须在 `create_agent()` 时全量注册，中间件只能筛选不能新增。**

因此采用 **全量注册 + 动态筛选** 的两层架构：

| 层 | 职责 | 时机 |
|---|---|---|
| `registry.py` | 全局注册表，`name → BaseTool` 映射 | 应用启动时 |
| `SkillsMiddleware.wrap_model_call` | 根据 skill 声明的 tools 筛选子集 | 每次 model 调用前 |

## 核心文件

```
tools/
├── registry.py      # 全局 Tool 注册表
├── web_tools.py     # 网络工具集（http_get, fetch_webpage, http_post）
├── load_skills.py   # 扫描 skills/ 目录，解析 SKILL.md frontmatter
└── README.md
```

## Registry 用法

### 基础用法

```python
# Agent/main.py 启动时
from tools.web_tools import WEB_TOOLS
from tools.registry import register_tools, get_all_tools

register_tools(WEB_TOOLS)                       # 注册进注册表
create_agent(tools=get_all_tools(), ...)        # 全量传给 agent
```

注册后的内部状态：

```python
_TOOL_REGISTRY = {
    "http_get":      <BaseTool>,
    "fetch_webpage": <BaseTool>,
    "http_post":     <BaseTool>,
}
```

### 扩展新项目的 tools

例如新增一个数据分析项目，写了 `tools/db_tools.py`：

```python
# tools/db_tools.py
@tool
def query_sql(sql: str) -> str: ...

@tool
def list_tables() -> str: ...

DB_TOOLS = [query_sql, list_tables]
```

在 `Agent/main.py` 只需加一行：

```python
from tools.web_tools import WEB_TOOLS
from tools.db_tools import DB_TOOLS              # 新加的

register_tools(WEB_TOOLS)
register_tools(DB_TOOLS)                          # <- 就这一行

create_agent(tools=get_all_tools(), ...)          # 自动拿到 5 个 tool
```

## 配合 Skill 动态筛选

### Skill 绑定 tools

在 SKILL.md 的 frontmatter 中声明 `tools` 字段：

```yaml
# skills/web_search/SKILL.md
---
name: web_search
description: 网络检索技能
tools:
  - http_get
  - fetch_webpage
  - http_post
---

# skills/data_analysis/SKILL.md
---
name: data_analysis
description: 数据分析技能
tools:
  - query_sql
  - list_tables
---
```

### 运行时筛选效果

用户问 "上网查一下xxx" -> 命中 `web_search`：

```python
get_tools_by_names(["http_get", "fetch_webpage", "http_post"])
# -> LLM 只看到网络工具，不会看到 query_sql
```

用户问 "分析一下数据库的销售表" -> 命中 `data_analysis`：

```python
get_tools_by_names(["query_sql", "list_tables"])
# -> LLM 只看到数据库工具，不会看到 http_get
```

### 不绑定 tools 的 skill

如果 SKILL.md 的 frontmatter 中没有 `tools` 字段，不做任何筛选，LLM 看到全量 tools。完全向后兼容。

## API 速查

| 函数 | 说明 |
|------|------|
| `register_tools(tools: list[BaseTool])` | 批量注册，按 `tool.name` 索引，重复注册会覆盖 |
| `get_all_tools() -> list[BaseTool]` | 返回注册表全量（用于 `create_agent`） |
| `get_tools_by_names(names: list[str]) -> list[BaseTool]` | 按名称取子集，未注册的名称记 warning 跳过 |

## 数据流全景

```
SKILL.md frontmatter: tools: [http_get, fetch_webpage]
    | load_skills.py (yaml.safe_load)
    v
SkillMetadata.metadata = {"tools": ["http_get", "fetch_webpage"]}
    | integrators.py
    v
payload["loaded_skills"][0]["metadata"]["tools"]
    | before_agent 返回 state
    v
request.state["loaded_skills"][0]["metadata"]["tools"]
    | wrap_model_call 读取
    v
get_tools_by_names(["http_get", "fetch_webpage"])
    | registry.py 查表
    v
request.override(tools=[...])  ->  LLM 只看到这 2 个 tool
```
