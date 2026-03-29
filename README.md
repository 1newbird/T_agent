<p align="center">
  <strong>T-Agent</strong>
</p>

<p align="center">
  <em>一个模块化、可插拔的通用智能体基础框架，开箱即用，按需扩展。</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.12+-blue?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/framework-LangChain-green" alt="LangChain">
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="License">
</p>

---

## Overview

T-Agent 不是一个具体的智能体应用，而是一套**通用基础架构**——提供记忆管理、技能匹配、提示词动态组装等核心能力，让你在接到任何项目时都可以基于此快速开发，而不是从零搭建。

核心理念：**框架负责基础设施，业务只需扩展中间件。**

## Design Principles

- **可插拔**：每个模块（记忆、技能、提示词）都通过 Protocol 接口解耦，可独立替换后端实现。
- **不侵入**：中间件模式挂载到 agent 生命周期，失败时静默降级，不影响主流程。
- **业务无关**：框架不预设任何具体业务逻辑，skills 目录、记忆策略、prompt 结构都由项目自行定义。

## ✨ Key Features

- 🧠 **记忆管理** — 短期（session 级）+ 长期（跨 session）双层记忆，关键词 + 向量混合检索，JSONL 文件持久化。
- 🎯 **技能匹配** — 5 阶段流水线（发现 → 粗筛 → 精选 → 加载 → 组装），支持 5 种检索策略，LLM 精判，"1 主 + N 辅"注入。
- 📝 **提示词管理** — Block 化动态组装 system prompt，解决 checkpointer 恢复时旧内容残留问题。
- 🔌 **中间件架构** — before_agent / wrap_model_call / after_agent 生命周期钩子，业务逻辑通过中间件扩展，自带错误兜底。
- 🔧 **动态 Tool 筛选** — Skill 声明绑定的 tools，中间件在每次 model 调用前自动筛选工具子集，LLM 只看到相关工具；未声明则保留全量。
- ⚙️ **统一基础设施** — 单例 LLM 初始化、统一日志工厂、公共工具函数、全局 Tool 注册表，避免重复造轮子。

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Agent (入口)                       │
│         create_agent + checkpointer + middleware     │
└──────────────────────┬──────────────────────────────┘
                       │
          ┌────────────▼────────────┐
          │      Middleware Layer    │
          │  before_agent    技能注入 + prompt 组装    │
          │  wrap_model_call 动态 Tool 筛选           │
          │  after_agent     后处理                   │
          └──┬──────────┬───────────┘
             │          │
   ┌─────────▼──┐  ┌───▼────────────┐
   │  skills_   │  │   sysprompt/   │
   │  manager/  │  │ Block 动态组装  │
   │  5 阶段流水线│  │ prompt         │
   └────────────┘  └────────────────┘
             │
   ┌─────────▼──────────┐
   │  memory_manager/   │  (独立模块，按项目需求接入)
   │  短期 + 长期记忆     │
   └────────────────────┘
             │
   ┌─────────▼──────────┐     ┌───────────────────┐
   │      core/         │     │     tools/        │
   │  LLM · logger ·    │     │  registry 注册表   │
   │  config · utils    │     │  web_tools · ...  │
   └────────────────────┘     └───────────────────┘
```

## 📦 Project Structure

```
T_agent/
├── core/                       # 基础设施层
│   ├── config.py               #   pydantic-settings 配置（读取 .env）
│   ├── LLM.py                  #   LLM / Embedding 单例工厂
│   ├── logger.py               #   统一日志工厂
│   └── utils.py                #   公共工具函数（tokenize, cosine_similarity）
│
├── memory_manager/             # 记忆管理模块
│   ├── types.py                #   MemoryScope / MemoryRecord / MemoryQuery
│   ├── base.py                 #   Protocol 接口（Backend, RetrievalStrategy）
│   ├── file_backend.py         #   JSONL 文件后端
│   ├── strategies.py           #   检索策略（最近优先、关键词匹配）
│   ├── service.py              #   MemoryService + build_memory_service()
│   └── MEMORY_MANAGER_EXAMPLE.md
│
├── skills_manager/             # 技能匹配模块
│   ├── types.py                #   SkillMetadata / Request / 各阶段 Result
│   ├── base.py                 #   Protocol 接口（5 阶段）
│   ├── loaders.py              #   技能目录扫描 + Markdown 文件加载
│   ├── screening_strategies.py #   5 种检索策略 + LLMSelector
│   ├── integrators.py          #   "1 主 + N 辅" prompt 组装
│   ├── service.py              #   SkillsService 流水线 + build_skills_service()
│   └── README.md
│
├── sysprompt/                  # 提示词管理模块
│   ├── types.py                #   PromptBlock / SessionPromptState
│   ├── file_backend.py         #   JSON 文件后端（按 session 持久化）
│   ├── service.py              #   SyspromptService + build_sysprompt_service()
│   └── README.md
│
├── middwares/                  # 中间件层
│   └── load_skills_hooks.py    #   SkillsMiddleware（技能注入 + 动态 Tool 筛选 + 错误兜底）
│
├── tools/                      # 工具层
│   ├── registry.py             #   全局 Tool 注册表（register / get_all / get_by_names）
│   ├── web_tools.py            #   网络工具集（http_get, fetch_webpage, http_post）
│   ├── load_skills.py          #   扫描 skills/ 目录，解析 SKILL.md frontmatter
│   └── README.md               #   Tool 注册表与动态筛选使用说明
│
├── skills/                     # 技能定义目录（按项目填充）
│   └── <skill_name>/SKILL.md   #   每个技能一个子目录 + SKILL.md
│
├── Agent/                      # 智能体入口
│   └── main.py                 #   run_agent() — 组装 agent + middleware + checkpointer
│
├── workspace/                  # 运行时数据（自动生成，勿提交）
│   ├── store/                  #   SQLite checkpoint 文件
│   ├── memory/                 #   JSONL 记忆数据
│   └── sysprompt/              #   JSON prompt 状态
│
├── .env                        # 环境变量（API Key 等，勿提交）
└── pyproject.toml              # 项目依赖（uv 管理）
```

## 🚀 Quick Start

### 1. 安装依赖

```bash
git clone https://github.com/T-Agent/T-Agent.git
cd T-Agent
uv sync
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入你的 API Key 和模型配置
```

`.env` 示例：
```env
MODEL_PROVIDER=openai
CHAT_API_KEY=sk-xxx
BASE_URL=https://api.openai.com/v1
CHAT_MODEL_NAME=gpt-4o
EMBED_API_KEY=sk-xxx
EMBED_MODEL_NAME=text-embedding-3-large
```

### 3. 运行

```python
from Agent.main import run_agent

response = run_agent(
    user_id="user_001",
    session_id="session_001",
    query="你好，介绍一下自己",
)
print(response["messages"][-1].content)
```

## 🔌 How to Extend

T-Agent 的扩展方式是**添加中间件**和**填充技能**，不需要修改框架代码。

### 添加一个技能

在 `skills/` 下创建子目录，放入 `SKILL.md`：

```
skills/
└── code_review/
    └── SKILL.md
```

```markdown
---
name: code_review
description: 代码审查，检查代码质量和潜在问题
tools:
  - read_file
  - lint_check
---

## 代码审查技能

当用户要求审查代码时，请按以下步骤执行：
1. 检查代码风格和规范
2. 识别潜在 bug 和安全问题
3. 给出改进建议
```

- `tools` 字段可选：声明后中间件会自动筛选，LLM 只看到这些工具；不声明则保留全量工具。
- 声明的 tool 名称必须和 `registry.py` 中注册的 `tool.name` 一致。

框架会自动发现并在用户查询匹配时注入。

### 添加一个中间件

```python
from langchain.agents.middleware import AgentMiddleware

class MyCustomMiddleware(AgentMiddleware):
    def before_agent(self, state, runtime):
        # 在 agent 执行前做一些事情（注入上下文、修改 prompt 等）
        ...
        return {"messages": modified_messages}

    def wrap_model_call(self, request, handler):
        # 在每次 model 调用时拦截（修改 tools、重试、缓存等）
        ...
        return handler(request)

    def after_agent(self, state, runtime):
        # 在 agent 执行后做一些事情（保存记忆、记录日志等）
        ...
        return None
```

### 添加新的 tools

1. 在 `tools/` 下新建文件，定义 tool 并导出列表：

```python
# tools/my_tools.py
from langchain.tools import tool

@tool
def my_tool(arg: str) -> str:
    """工具描述"""
    ...

MY_TOOLS = [my_tool]
```

2. 在 `Agent/main.py` 注册：

```python
from tools.my_tools import MY_TOOLS
register_tools(MY_TOOLS)
```

3. （可选）在 SKILL.md 中绑定：

```yaml
---
name: my_skill
description: xxx
tools:
  - my_tool
---
```

详细说明参见 [`tools/README.md`](tools/README.md)。

## 📚 Module Docs

每个核心模块都有独立的详细文档：

| 模块 | 文档 | 说明 |
|------|------|------|
| 记忆管理 | [`memory_manager/MEMORY_MANAGER_EXAMPLE.md`](memory_manager/MEMORY_MANAGER_EXAMPLE.md) | 数据结构、存储、检索流程、可运行示例 |
| 技能匹配 | [`skills_manager/README.md`](skills_manager/README.md) | 5 阶段流水线、检索策略、payload 格式 |
| 提示词管理 | [`sysprompt/README.md`](sysprompt/README.md) | Block 组装、动态 vs 静态、中间件配合 |
| 工具层 | [`tools/README.md`](tools/README.md) | Tool 注册表、动态筛选机制、扩展方法 |

## 🛣️ Roadmap

- [x] 记忆管理模块（短期 + 长期，关键词 + 向量检索）
- [x] 技能匹配模块（5 阶段流水线，5 种检索策略）
- [x] 提示词管理模块（Block 动态组装）
- [x] 中间件错误兜底
- [x] 统一日志 / LLM 单例 / 公共工具函数
- [x] 动态 Tool 筛选（Skill 绑定 tools + wrap_model_call 筛选）
- [ ] 记忆中间件（接入 agent 生命周期）
- [ ] API Server（FastAPI 接入层）
- [ ] 更多检索后端（Redis / ChromaDB）
- [ ] 单元测试覆盖

## Contributing

欢迎提交 Issue 和 Pull Request。

1. Fork 本仓库
2. 创建你的分支 (`git checkout -b feature/my-feature`)
3. 提交改动 (`git commit -m 'Add my feature'`)
4. Push (`git push origin feature/my-feature`)
5. 创建 Pull Request

## License

[MIT](LICENSE)
