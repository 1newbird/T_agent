"""
用来将详细历史存储到对应的记忆目录下的md里面
"""
from langchain.tools import tool
from langchain.messages import AIMessage,SystemMessage,HumanMessage,ToolMessage
import os
import datetime



def format_messages_to_md(messages: list, session_time: str) -> str:
    """将 state['messages'] 序列化成 Markdown 格式"""
    lines = [
        f"# 会话记录",
        f"",
        f"**记录时间：** {session_time}",
        f"",
        "---",
        "",
    ]
    for msg in messages:
        if isinstance(msg, SystemMessage):
            lines.append(f"### 🛠 System")
            lines.append(f"> {msg.content}")
        elif isinstance(msg, HumanMessage):
            lines.append(f"### 👤 User")
            lines.append(f"{msg.content}")
        elif isinstance(msg, AIMessage):
            lines.append(f"### 🤖 Assistant")
            # 处理 tool_calls（如果有）
            if msg.tool_calls:
                lines.append(f"{msg.content or '*(调用工具)*'}")
                for tc in msg.tool_calls:
                    lines.append(f"")
                    lines.append(f"**Tool Call** `{tc['name']}`")
                    lines.append(f"```json")
                    lines.append(f"{tc['args']}")
                    lines.append(f"```")
            else:
                lines.append(f"{msg.content}")
        elif isinstance(msg, ToolMessage):
            lines.append(f"### 🔧 Tool Result (`{msg.name or msg.tool_call_id}`)")
            lines.append(f"```")
            lines.append(f"{msg.content}")
            lines.append(f"```")
        lines.append("")  # 每条消息后空一行
    return "\n".join(lines)


def save_conversation_to_md(md_content: str, file_path: str) -> None:
    """
    将会话记录写入指定的 Markdown 文件。
    - 文件不存在则自动创建（含中间目录）
    - 每次追加写入，多轮之间用分隔线隔开
    """
    dir_name = os.path.dirname(file_path)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)

    content = md_content + "\n\n---\n\n"

    with open(file_path, "a", encoding="utf-8") as f:
        f.write(content)


