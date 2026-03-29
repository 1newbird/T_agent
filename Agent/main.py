"""
智能体主入口
"""
from dataclasses import dataclass
from langchain.agents import AgentState
from langchain.agents import create_agent
from core.LLM import init_llm
from core.logger import get_logger
from middwares.load_skills_hooks import SkillsMiddleware
from langgraph.checkpoint.sqlite import SqliteSaver
from pathlib import Path
from skills_manager.service import build_skills_service
from sysprompt.service import build_sysprompt_service
from tools.web_tools import WEB_TOOLS
from tools.registry import register_tools, get_all_tools
logger = get_logger(__name__)


#自定义状态，在messages之外的状态（动态）
class CustomAgentstate(AgentState):
    preferences:str


#自定义上下文，静态，不变的
@dataclass
class CustomContext:
    user_id:str
    session_id:str


# ── 注册全量 tools 到注册表 ──────────────────────────
# 所有 tool 集在此统一注册，后续扩展只需增加 register_tools(XXX_TOOLS)
register_tools(WEB_TOOLS)



BASE_DIR = Path(__file__).resolve().parent.parent
BASE_SYSTEM_PROMPT = "你是一个人工智能助手"
skills_service = build_skills_service(BASE_DIR)
sysprompt_service = build_sysprompt_service(BASE_DIR)

def run_agent(user_id:str,session_id:str,query):
    data_file=f"{user_id}_{session_id}.db"
    state_store_path =  BASE_DIR / "workspace" / "store"/data_file
    state_store_path.parent.mkdir(parents=True, exist_ok=True)
    with SqliteSaver.from_conn_string(state_store_path) as checkpointer:
        main_agent = create_agent(
            model=init_llm(),
            system_prompt=BASE_SYSTEM_PROMPT,
            middleware=[
                SkillsMiddleware(
                    skills_service=skills_service,
                    sysprompt_service=sysprompt_service,
                    base_system_prompt=BASE_SYSTEM_PROMPT,
                )
            ],
            tools=get_all_tools(),
            checkpointer=checkpointer,
            state_schema=CustomAgentstate,
            context_schema=CustomContext
        )
        answer=main_agent.invoke({"messages": [{"role": "user", "content": query}]},
                                 config={"configurable": {"thread_id": f"{user_id}:{session_id}"}},
                                 context=CustomContext(user_id=user_id, session_id=session_id)
                                 )
        return answer





if __name__=="__main__":
    response=run_agent("小明","123","上网查一下：https://langchain-doc.cn/v1/python/langchain/releases/langchain-v1.html，最新的langchain特性干了啥")
    print(response["messages"][-1])

