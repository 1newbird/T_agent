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
