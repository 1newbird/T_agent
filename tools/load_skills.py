import os
import re

from core.logger import get_logger

logger = get_logger(__name__)


def load_skills(skills_dir: str) -> list[dict]:
    """
    扫描 skills 目录，读取每个子文件夹下的 SKILL.md，
    提取 frontmatter 中的 name、description 组成元数据列表。

    Args:
        skills_dir: skills 根目录的绝对路径，例如 /home/user/project/skills

    Returns:
        [
            {
                "name": "1password",
                "description": "1Password password manager integration",
                "path": "/home/user/project/skills/1password/SKILL.md"
            },
            ...
        ]
    """
    if not os.path.exists(skills_dir):
        logger.warning("目录不存在：%s", skills_dir)
        return []

    skills_des = []

    for folder_name in sorted(os.listdir(skills_dir)):
        folder_path = os.path.join(skills_dir, folder_name)

        if not os.path.isdir(folder_path):
            continue

        skill_md_path = os.path.join(folder_path, "SKILL.md")

        if not os.path.exists(skill_md_path):
            logger.debug("跳过（无 SKILL.md）：%s", folder_name)
            continue

        with open(skill_md_path, "r", encoding="utf-8") as f:
            content = f.read()

        metadata = _parse_frontmatter(content)

        # frontmatter 解析失败则跳过
        if not metadata.get("name") or not metadata.get("description"):
            logger.warning("跳过（frontmatter 缺少 name/description）：%s", folder_name)
            continue

        skills_des.append({
            "name": metadata["name"],
            "description": metadata["description"],
            "path": skill_md_path,
        })

    logger.info("检测到 %d 个 skill：%s", len(skills_des), [s['name'] for s in skills_des])
    return skills_des


def _parse_frontmatter(content: str) -> dict:
    """
    解析 SKILL.md 顶部的 frontmatter 块：
    ---
    name: 1password
    description: 1Password password manager integration
    ---
    """
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return {}

    metadata = {}
    for line in match.group(1).splitlines():
        line = line.strip()
        if not line:
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        metadata[key.strip()] = value.strip()

    return metadata
