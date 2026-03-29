"""
通用工具函数，供 skills_manager / memory_manager 等模块复用。
"""
import math
import re

_WORD_RE = re.compile(r"\w+")


def tokenize(text: str) -> set[str]:
    """将文本拆成小写 token 集合（按 \\w+ 切分）。"""
    return set(_WORD_RE.findall(text.lower()))


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """计算两个向量的余弦相似度。"""
    numerator = sum(a * b for a, b in zip(left, right, strict=False))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return numerator / (left_norm * right_norm)
