"""
tools/registry.py
==================
全局 Tool 注册表。

所有 tools 在应用启动时通过 register_tools() 注册到模块级字典，
create_agent(tools=get_all_tools()) 传入全量；
中间件的 wrap_model_call 根据 skill 声明的 tool names 调用
get_tools_by_names() 筛选子集。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logger import get_logger

if TYPE_CHECKING:
    from langchain_core.tools import BaseTool

logger = get_logger(__name__)

_TOOL_REGISTRY: dict[str, BaseTool] = {}


def register_tools(tools: list[BaseTool]) -> None:
    """批量注册 tools，按 tool.name 索引。重复注册同名 tool 会覆盖。"""
    for t in tools:
        _TOOL_REGISTRY[t.name] = t
    logger.info(
        "已注册 %d 个 tool：%s",
        len(tools),
        [t.name for t in tools],
    )


def get_all_tools() -> list[BaseTool]:
    """返回注册表中全部 tools（用于 create_agent 全量传入）。"""
    return list(_TOOL_REGISTRY.values())


def get_tools_by_names(names: list[str]) -> list[BaseTool]:
    """
    按名称列表查找 tools。

    - 名称在注册表中 → 返回对应 BaseTool
    - 名称不在注册表中 → 记 warning，跳过（容错，不报错）
    """
    result: list[BaseTool] = []
    for name in names:
        tool = _TOOL_REGISTRY.get(name)
        if tool is not None:
            result.append(tool)
        else:
            logger.warning("Tool '%s' 在 SKILL.md 中声明但未注册，跳过", name)
    return result
