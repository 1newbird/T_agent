import os
import re

import yaml

from core.logger import get_logger

logger = get_logger(__name__)

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)


def load_skills(skills_dir: str) -> list[dict]:
    """
    扫描 skills 目录，读取每个子文件夹下的 SKILL.md，
    提取 frontmatter 中的 name、description 及其他扩展字段组成元数据列表。

    Args:
        skills_dir: skills 根目录的绝对路径，例如 /home/user/project/skills

    Returns:
        [
            {
                "name": "web_search",
                "description": "网络检索技能",
                "path": "/home/user/project/skills/web_search/SKILL.md",
                "metadata": {"tags": ["search", "web"], ...}
            },
            ...
        ]
    """
    if not os.path.exists(skills_dir):
        logger.warning("目录不存在：%s", skills_dir)
        return []

    skills_list = []

    for folder_name in sorted(os.listdir(skills_dir)):
        folder_path = os.path.join(skills_dir, folder_name)

        if not os.path.isdir(folder_path):
            continue

        skill_md_path = os.path.join(folder_path, "SKILL.md")

        if not os.path.exists(skill_md_path):
            logger.debug("跳过（无 SKILL.md）：%s", folder_name)
            continue

        try:
            with open(skill_md_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception:
            logger.exception("读取文件失败：%s", skill_md_path)
            continue

        frontmatter = _parse_frontmatter(content)

        name = frontmatter.get("name")
        description = frontmatter.get("description")

        if not name or not description:
            logger.warning("跳过（frontmatter 缺少 name/description）：%s", folder_name)
            continue

        # name 和 description 之外的字段透传到 metadata
        metadata = {k: v for k, v in frontmatter.items() if k not in ("name", "description")}

        skills_list.append({
            "name": name,
            "description": description,
            "path": skill_md_path,
            "metadata": metadata,
        })

    logger.info("检测到 %d 个 skill：%s", len(skills_list), [s["name"] for s in skills_list])
    return skills_list


def _parse_frontmatter(content: str) -> dict:
    """
    解析 SKILL.md 顶部的 YAML frontmatter 块：

    ---
    name: web_search
    description: 网络检索技能，当要上网查找东西时使用
    tags:
      - search
      - web
    ---

    使用 yaml.safe_load 解析，支持多行 value、列表、嵌套等标准 YAML 语法。
    """
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return {}

    try:
        result = yaml.safe_load(match.group(1))
        return result if isinstance(result, dict) else {}
    except yaml.YAMLError as e:
        logger.warning("YAML frontmatter 解析失败：%s", e)
        return {}
