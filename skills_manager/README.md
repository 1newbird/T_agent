# Skills Manager 示例文档

## 1. 模块概览

`skills_manager` 当前由 8 个文件组成：

- `types.py`：定义全部数据结构（`SkillMetadata`、`SkillSelectionRequest`、各阶段 Result）。
- `base.py`：定义五个阶段的协议接口（`Protocol`）。
- `loaders.py`：文件系统目录扫描（技能发现）与 Markdown 文件读取。
- `screening_strategies.py`：5 种检索策略 + 1 个 LLM 选择器。
- `integrators.py`：将选中的技能组装成最终 prompt 文本和结构化 payload。
- `service.py`：统一入口 `SkillsService`，串联五阶段流水线；工厂函数 `build_skills_service()`。
- `similarity.py`：预留（当前未使用）。
- `__init__.py`：空文件。


## 2. 核心流水线（5 阶段）

```
用户查询
  │
  ▼
┌────────────────────┐
│ 1. Catalog (发现)   │  SkillCatalogBackend → CatalogResult
│ 扫描 skills/ 目录    │  找到所有 SKILL.md 文件
└─────────┬──────────┘
          ▼
┌────────────────────┐
│ 2. Retrieve (粗筛)  │  SkillRetriever → RetrievalResult
│ 关键词/向量/混合/LLM │  从全量候选中缩小范围（默认 top_k=8）
└─────────┬──────────┘
          ▼
┌────────────────────┐
│ 3. Select (精选)    │  SkillSelector → SelectionResult
│ LLM 精判           │  默认只选出 1 个最匹配的主技能
└─────────┬──────────┘
          ▼
┌────────────────────┐
│ 4. Load (加载)      │  SkillContentLoader → LoadResult
│ 读取 SKILL.md 全文   │  获取选中技能的完整内容
└─────────┬──────────┘
          ▼
┌────────────────────┐
│ 5. Integrate (组装) │  SkillIntegrator → IntegrationResult
│ "1 主 + N 辅" 注入  │  主技能完整注入，备选仅列名称
└────────────────────┘
```

### 设计理念：1 主 + N 辅

- **精选阶段默认只选 1 个主技能**（`top_k_selection=1`），完整内容注入 prompt。
- 如果调用方通过 `top_k_selection > 1` 请求多技能，第 2 个及之后的技能只注入名称和描述，不注入完整内容。
- 好处：prompt token 可控、无多技能指令冲突、保留灵活性。


## 3. 关键对象说明

### `SkillMetadata`
单个技能的元信息：
- `name`：技能名称（如 `"github_pr"`）
- `description`：技能描述
- `path`：对应 `SKILL.md` 文件路径
- `metadata`：附加键值对

### `SkillSelectionRequest`
一次技能解析请求的输入：
- `query_text`：用户查询文本
- `screening_mode`：检索模式（见下方策略说明）
- `top_k_retrieval`：粗筛阶段保留数量，默认 8
- `top_k_selection`：精选阶段保留数量，**默认 1**
- `context`：附加上下文信息

### `SkillResolutionResult`
聚合五个阶段的完整结果，便于调试和追踪：
- `catalog`、`retrieval`、`selection`、`load`、`integration`


## 4. 检索策略（screening_mode）

| 模式 | 类 | 说明 |
|------|-----|------|
| `passthrough` | `PassThroughRetriever` | 不过滤，全量传递给 Selector |
| `keyword` | `KeywordRetriever` | token overlap + 完整匹配 bonus(+3)，按分数排序 |
| `embedding` | `EmbeddingRetriever` | 向量余弦相似度排序 |
| `hybrid` | `HybridRetriever` | 关键词 + 向量并行，recall-first 合并（双命中优先，再交替补充） |
| `keyword_llm` | `KeywordLLMRetriever` | 先关键词粗筛 3× 候选，再 LLM 精选 |

精选阶段固定使用 `LLMSelector`：
- 当 `top_k_selection == 1` 时，prompt 要求 LLM 返回"1 个最匹配的 skill"。
- 当 `top_k_selection > 1` 时，prompt 要求 LLM 返回"最合适的 N 个，按相关性从高到低排列"。
- LLM 返回无法解析时，回退到候选列表的前 N 个。


## 5. 最终输出（IntegrationResult.payload）

`StateInjectionIntegrator` 构建的 payload 包含 6 个字段：

| 字段 | 内容 |
|------|------|
| `skills_prompt` | 格式化后的 prompt 文本，可直接拼入 system message |
| `primary_skill` | 主技能（含 name、description、path、content），可为 None |
| `auxiliary_skills` | 备选技能列表（含 name、description、path、content） |
| `skill_candidates` | 粗筛阶段的全部候选（含 score、reason、source） |
| `selected_skills` | 精选后的最终技能列表（含 score、reason） |
| `loaded_skills` | 选中技能的完整 Markdown 内容 |

其中 `skills_prompt` 的格式：
```
## 当前匹配到的技能
以下技能是根据当前用户问题动态检索出的，请优先参考并遵循。

### 主技能：github_pr
{完整 SKILL.md 内容}

### 备选技能（仅供参考）
- **risk_summary**：输出变更风险总结

## 技能使用规则
- 以主技能的要求为核心，严格遵循其指令。
- 备选技能仅在主技能未覆盖且与用户意图相关时参考。
- 如果主技能与备选技能冲突，以主技能为准。
```


## 6. 最小可运行示例

```python
from pathlib import Path

from skills_manager.service import build_skills_service
from skills_manager.types import SkillSelectionRequest

BASE_DIR = Path(".")

# 1) 创建服务（screening_mode 可选：passthrough / keyword / embedding / hybrid / keyword_llm）
service = build_skills_service(BASE_DIR, screening_mode="hybrid")

# 2) 构造请求（默认精选 1 个主技能）
request = SkillSelectionRequest(
    query_text="帮我 review 一个 github PR，并总结风险",
    screening_mode="hybrid",
)

# 3) 一键执行完整流水线
result = service.resolve_skills(request)

# 4) 获取可直接注入提示词的文本
skills_prompt = result.integration.payload["skills_prompt"]
print(skills_prompt)

# 5) 直接获取主技能信息
primary = result.integration.payload["primary_skill"]
if primary:
    print(f"主技能：{primary['name']}")

# 6) 如果需要多技能，在请求中覆盖 top_k_selection
multi_request = SkillSelectionRequest(
    query_text="帮我 review 一个 github PR，并总结风险",
    screening_mode="hybrid",
    top_k_selection=3,  # 显式指定选 3 个
)
```


## 7. payload 示例数据

用户问："帮我 review 一个 github PR，并总结风险"（默认 `top_k_selection=1`）

```json
{
    "primary_skill": {
        "name": "github_pr",
        "description": "处理 GitHub PR 相关任务",
        "path": ".../skills/github_pr/SKILL.md",
        "content": "这里是完整 SKILL.md 内容..."
    },
    "auxiliary_skills": [],
    "skill_candidates": [
        {
            "name": "github_pr",
            "description": "处理 GitHub PR 相关任务",
            "path": ".../skills/github_pr/SKILL.md",
            "score": 6.0,
            "reason": "hybrid keyword + embedding",
            "source": "hybrid"
        },
        {
            "name": "code_review",
            "description": "做通用代码审查",
            "path": ".../skills/code_review/SKILL.md",
            "score": 4.0,
            "reason": "keyword overlap",
            "source": "keyword"
        },
        {
            "name": "risk_summary",
            "description": "输出变更风险总结",
            "path": ".../skills/risk_summary/SKILL.md",
            "score": 0.84,
            "reason": "embedding similarity",
            "source": "embedding"
        }
    ],
    "selected_skills": [
        {
            "name": "github_pr",
            "description": "处理 GitHub PR 相关任务",
            "path": ".../skills/github_pr/SKILL.md",
            "score": 6.0,
            "reason": "llm fine selection"
        }
    ],
    "loaded_skills": [
        {
            "name": "github_pr",
            "description": "处理 GitHub PR 相关任务",
            "path": ".../skills/github_pr/SKILL.md",
            "content": "这里是完整 SKILL.md 内容..."
        }
    ],
    "skills_prompt": "## 当前匹配到的技能\n以下技能是根据当前用户问题动态检索出的...\n"
}
```


## 8. 当前实现注意点

- `build_skills_service()` 会初始化 LLM 和 embedding 模型（通过 `core.LLM`），若模型不可用，`embedding` / `hybrid` / `keyword_llm` 模式可能报错，建议退回 `keyword` 或 `passthrough`。
- `HybridRetriever` 采用 recall-first 合并策略（双命中优先），有意过度召回，精度由下游 `LLMSelector` 把控。
- 技能文件需放在 `{base_dir}/skills/{技能名}/SKILL.md`，由外部 `tools.load_skills.load_skills()` 扫描发现。
- `__init__.py` 为空，使用时需用完整路径 import，如 `from skills_manager.service import build_skills_service`。
- 精选阶段默认 `top_k_selection=1`，只选 1 个主技能完整注入 prompt；需要多技能时显式覆盖该参数。


## 9. Skill 编写完整指南

### 目录结构

一个标准 skill 的推荐目录结构如下。只有 `SKILL.md` 是必须的，其余均为可选：

```
skills/
└── web_search/
    ├── SKILL.md              ← 必须：元数据 + 指令正文
    ├── scripts/              ← 可选：可执行脚本（Python/Bash）
    │   └── deep_search.py
    ├── references/           ← 可选：参考文档，按需读入上下文
    │   └── search_api_spec.md
    └── assets/               ← 可选：模板、示例文件等静态资源
        └── report_template.html
```

| 目录 | 作用 | 是否进入上下文 |
|------|------|----------------|
| `SKILL.md` | 核心指令，触发后完整注入 system prompt | **是**（全文注入） |
| `scripts/` | 可执行脚本，LLM 通过 tool 调用运行 | **否**（只有脚本的输出进入上下文） |
| `references/` | 参考文档，LLM 按需读取 | **按需**（LLM 决定是否读取，读了才进上下文） |
| `assets/` | 模板、图片等静态资源 | **否**（LLM 引用路径使用，不读入上下文） |

#### 设计原则：渐进式披露（Progressive Disclosure）

像一本好手册先有目录、再有章节、最后才是附录——Skill 让 LLM **按需加载信息**：

1. **第一层**：SKILL.md 正文注入 prompt，告诉 LLM "你有什么能力、怎么做"
2. **第二层**：LLM 判断需要时，主动读取 `references/` 下的详细文档
3. **第三层**：LLM 判断需要时，通过 tool 执行 `scripts/` 下的脚本

这样做的好处：**SKILL.md 保持精简**（建议不超过 5000 词），避免每次调用都淹没上下文窗口，同时通过 references 和 scripts 提供几乎无限的扩展能力。

### SKILL.md 文件格式

SKILL.md 由两部分组成：**YAML frontmatter**（元数据）+ **Markdown 正文**（注入 prompt 的内容）。

```markdown
---
name: <技能名称>
description: <一句话描述，用于检索匹配>
tools:                          # 可选：绑定的 tool 列表
  - <tool_name_1>
  - <tool_name_2>
<其他扩展字段>:                  # 可选：自动收入 metadata
---

正文内容（会被完整注入 system prompt）
```

### Frontmatter 字段说明

| 字段 | 必填 | 类型 | 说明 |
|------|------|------|------|
| `name` | **是** | `str` | 技能唯一标识，建议用英文 snake_case |
| `description` | **是** | `str` | 一句话描述技能能力，粗筛和精选阶段用来匹配用户意图 |
| `tools` | 否 | `list[str]` | 绑定的 tool 名称列表，名称须和 `registry.py` 中注册的 `tool.name` 一致。声明后中间件会在 `wrap_model_call` 中自动筛选，LLM 只看到这些工具；不声明则保留全量工具 |
| 其他字段 | 否 | 任意 | 自动收入 `SkillMetadata.metadata` 字典，供业务逻辑自行消费 |

### 正文编写要点

正文会被**完整注入** system prompt 的技能区块，LLM 会严格遵循。写法建议：

1. **明确告诉 LLM "做什么"**——用祈使句描述任务步骤
2. **明确告诉 LLM "用什么工具"**——如果绑定了 tools，正文中说明每个工具的用途和调用顺序
3. **指向 references**——详细规范、API 文档等拆到 `references/` 下，正文中告诉 LLM 路径和何时去读
4. **指向 scripts**——自动化脚本放 `scripts/` 下，正文中告诉 LLM 脚本路径和调用方式
5. **明确告诉 LLM "不做什么"**——约束边界，避免越权
6. **保持精练**——正文越长占的 token 越多，只写必要的指令；详细内容拆到 references

### 示例 1：网络检索技能（绑定 tools，最简结构）

```
skills/web_search/
└── SKILL.md
```

```markdown
---
name: web_search
description: 网络检索技能，当要上网查找东西时使用这个技能
tools:
  - http_get
  - fetch_webpage
  - http_post
---

当用户要求搜索或查找网络内容时，按以下步骤执行：

1. 使用 `fetch_webpage` 抓取目标网页的正文内容。
2. 如果需要调用 API 接口，使用 `http_get` 或 `http_post`。
3. 将获取到的内容进行总结，回答用户的问题。

注意：
- 优先使用 `fetch_webpage`，它会自动去除 HTML 标签。
- 响应内容超过 12000 字符会被截断，注意提取关键信息。
```

### 示例 2：代码审查技能（带 scripts + references）

```
skills/code_review/
├── SKILL.md
├── scripts/
│   └── lint_runner.py        # 调用 pylint/flake8 的封装脚本
└── references/
    └── review_checklist.md   # 详细的审查清单（50+ 条规则）
```

```markdown
---
name: code_review
description: 代码审查技能，审查代码质量和潜在问题
tools:
  - read_file
  - lint_check
---

当用户要求审查代码时，按以下步骤执行：

1. 使用 `read_file` 读取用户指定的代码文件。
2. 运行 `scripts/lint_runner.py <文件路径>` 做静态检查。
3. 如需详细审查标准，阅读 `references/review_checklist.md`。
4. 综合分析以下维度：
   - 代码风格和命名规范
   - 潜在 bug 和边界条件
   - 安全漏洞（SQL 注入、XSS 等）
   - 性能问题
5. 输出结构化的审查报告，按严重程度排序。

注意：
- 不要自行修改代码，只提供建议。
- 如果文件过大，分段审查。
```

> `scripts/lint_runner.py` 由 LLM 通过 tool 执行，**脚本代码本身不进上下文**，只有输出结果进入。
> `references/review_checklist.md` 由 LLM **按需读取**，不需要时不占 token。

### 示例 3：通用知识技能（不绑定 tools）

```markdown
---
name: general_qa
description: 通用知识问答，回答常识、百科、概念解释类问题
---

当用户提出常识性、概念性的问题时，根据已有知识直接回答。

要求：
- 回答简明扼要，先给结论再展开。
- 涉及专业领域时，标注信息来源的可信度。
- 不确定的内容如实说明，不编造。
```

> **不写 `tools` 字段** → 中间件不做工具筛选，LLM 看到全量 tools（向后兼容）。

### 示例 4：使用扩展 metadata

```markdown
---
name: customer_service
description: 客服话术技能，处理用户投诉和咨询
tools:
  - query_order
  - create_ticket
tags:
  - customer
  - support
priority: high
---

处理用户投诉和咨询时...
```

> `tags` 和 `priority` 会被收入 `SkillMetadata.metadata`，可在自定义中间件或检索策略中消费。

### description 编写技巧

`description` 是检索匹配的核心依据，直接影响技能能否被正确召回：

- **写用户会怎么问**，而不是写技能内部做了什么
  - ✅ `"网络检索技能，当要上网查找东西时使用这个技能"`
  - ❌ `"调用 http_get 和 fetch_webpage 工具的封装"`
- **包含关键词**，提升关键词检索的命中率
  - ✅ `"代码审查技能，审查代码质量和潜在问题"`（包含"代码""审查""质量"）
- **一句话概括**，不要太长（精选阶段 LLM 需要同时看多个 description 做对比）

### 什么时候该拆文件

| 场景 | 做法 |
|------|------|
| SKILL.md 超过 5000 词 | 把详细规范拆到 `references/` |
| 有可执行的自动化逻辑 | 放 `scripts/`，正文写调用命令 |
| 有模板/示例文件 | 放 `assets/`，正文写路径引用 |
| 内容互斥、很少同时使用 | 拆成多个 reference 文件，LLM 按需读 |
| SKILL.md 内容简短、独立 | 不需要拆，保持一个文件即可 |

### 端到端示例：从写 skill 到跑通

下面用一个完整的例子演示如何新增一个带 `scripts/` 和 `references/` 的 skill，以及框架是如何驱动整个流程的。

#### 第一步：写 tools

在 `tools/` 下新建通用的文件读取和脚本执行工具：

```python
# tools/file_tools.py
from langchain.tools import tool

@tool
def read_file(file_path: str) -> str:
    """读取指定路径的文件内容，返回文本。"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        if len(content) > 12000:
            content = content[:12000] + "\n… [截断]"
        return content
    except Exception as e:
        return f"读取失败: {e}"

@tool
def run_script(command: str) -> str:
    """执行一条 shell 命令，返回标准输出。用于运行 scripts/ 下的脚本。"""
    import subprocess
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=30
        )
        output = result.stdout or result.stderr
        if len(output) > 12000:
            output = output[:12000] + "\n… [截断]"
        return output
    except Exception as e:
        return f"执行失败: {e}"

FILE_TOOLS = [read_file, run_script]
```

#### 第二步：注册 tools

在 `Agent/main.py` 中注册：

```python
from tools.web_tools import WEB_TOOLS
from tools.file_tools import FILE_TOOLS
from tools.registry import register_tools, get_all_tools

register_tools(WEB_TOOLS)
register_tools(FILE_TOOLS)      # <- 新增这一行

create_agent(tools=get_all_tools(), ...)  # 自动拿到 5 个 tool
```

#### 第三步：创建 skill 目录

```
skills/code_review/
├── SKILL.md
├── scripts/
│   └── lint_runner.py
└── references/
    └── review_checklist.md
```

`scripts/lint_runner.py`：
```python
#!/usr/bin/env python3
"""对指定 Python 文件执行 flake8 检查，输出问题列表。"""
import subprocess, sys

file_path = sys.argv[1]
result = subprocess.run(["flake8", file_path], capture_output=True, text=True)
print(result.stdout or "No issues found.")
```

`references/review_checklist.md`：
```markdown
# 代码审查清单

## 命名规范
- 变量名使用 snake_case
- 类名使用 PascalCase
- 常量使用 UPPER_SNAKE_CASE

## 安全检查
- 检查 SQL 拼接（是否使用参数化查询）
- 检查用户输入是否做了转义
- ...

（省略更多条目）
```

#### 第四步：编写 SKILL.md

```markdown
---
name: code_review
description: 代码审查技能，审查代码质量和潜在问题
tools:
  - read_file
  - run_script
---

当用户要求审查代码时，按以下步骤执行：

1. 使用 `read_file` 读取用户指定的代码文件。
2. 使用 `run_script` 执行 `python3 scripts/lint_runner.py <文件路径>` 做静态检查。
3. 如需详细审查标准，使用 `read_file` 阅读 `references/review_checklist.md`。
4. 综合分析以下维度并输出结构化审查报告。

注意：
- 不要自行修改代码，只提供建议。
- 如果文件过大，分段审查。
```

#### 运行效果

用户输入：`"帮我审查一下 src/main.py 这个文件"`

框架自动执行：

```
1. before_agent
   └─ skills_manager 匹配到 code_review skill
   └─ SKILL.md 正文注入 system prompt
   └─ state["loaded_skills"][0]["metadata"]["tools"] = ["read_file", "run_script"]

2. wrap_model_call
   └─ 读到 skill 声明的 tools: ["read_file", "run_script"]
   └─ request.override(tools=[read_file, run_script])
   └─ LLM 只看到这 2 个工具（http_get 等被过滤掉）

3. LLM 遵循 SKILL.md 指令执行
   └─ 调用 read_file("src/main.py")         → 文件内容进入上下文
   └─ 调用 run_script("python3 scripts/lint_runner.py src/main.py")
   │   → lint_runner.py 脚本代码本身不进上下文
   │   → 只有输出 "src/main.py:12:1 E302 ..." 进入上下文
   └─ 调用 read_file("references/review_checklist.md")  → 审查清单进入上下文
   └─ 综合以上信息输出审查报告

4. 下一轮对话
   └─ model_node 重新构造 ModelRequest(tools=全量 5 个)
   └─ wrap_model_call 根据新的 skill（或无 skill）重新筛选
   └─ 上一轮的筛选不影响这一轮
```

> **关键点**：框架层面不需要任何改动。写好 tools → 注册 → SKILL.md 里声明绑定 + 写清楚指令，渐进式披露就自然跑起来了。
