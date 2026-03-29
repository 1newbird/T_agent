"""
my_claw/tools/web_tools.py
===========================
网络工具：HTTP 请求 + 网页内容提取。

不内置搜索引擎（需要 API key），只提供：
  - http_get     : 发送 GET 请求，返回响应内容
  - fetch_webpage: 抓取网页并提取可读文本（去除 HTML 标签）
  - http_post    : 发送 POST 请求（JSON body）
"""

import re
import json
from langchain.tools import tool

DEFAULT_TIMEOUT = 15
MAX_CONTENT_CHARS = 12_000


def _strip_html(html: str) -> str:
    """粗粒度 HTML → 纯文本：去标签、压缩空白。"""
    # 去掉 script / style 块
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    # 去掉所有标签
    text = re.sub(r"<[^>]+>", " ", html)
    # 压缩空白
    text = re.sub(r"\s+", " ", text).strip()
    return text


@tool
def http_get(url: str, headers: str = "{}") -> str:
    """
    发送 HTTP GET 请求，返回响应状态码和内容。
    headers 参数为 JSON 字符串，如 '{"Authorization": "Bearer token"}'。
    响应内容超过 12000 字符时自动截断。
    """
    try:
        import urllib.request
        import urllib.error
        hdrs = json.loads(headers) if headers.strip() != "{}" else {}
        req = urllib.request.Request(url, headers=hdrs)
        with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as resp:
            content = resp.read().decode("utf-8", errors="replace")
            status = resp.status
        if len(content) > MAX_CONTENT_CHARS:
            content = content[:MAX_CONTENT_CHARS] + "\n… [截断]"
        return f"HTTP {status}\n{content}"
    except Exception as e:
        return f"❌ 请求失败: {e}"


@tool
def fetch_webpage(url: str) -> str:
    """
    抓取网页并提取可读正文（去除 HTML 标签、脚本、样式）。
    适合让 Agent 阅读文章、文档、公开页面内容。
    """
    try:
        import urllib.request
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0 (compatible; MyClaw/1.0)"}
        )
        with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        text = _strip_html(html)
        if len(text) > MAX_CONTENT_CHARS:
            text = text[:MAX_CONTENT_CHARS] + "\n… [截断]"
        return text
    except Exception as e:
        return f"❌ 抓取失败: {e}"


@tool
def http_post(url: str, body: str, headers: str = "{}") -> str:
    """
    发送 HTTP POST 请求（JSON body）。
    body 为 JSON 字符串，headers 为 JSON 字符串。
    """
    try:
        import urllib.request
        hdrs = json.loads(headers) if headers.strip() != "{}" else {}
        hdrs.setdefault("Content-Type", "application/json")
        data = body.encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=hdrs, method="POST")
        with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as resp:
            content = resp.read().decode("utf-8", errors="replace")
            status = resp.status
        if len(content) > MAX_CONTENT_CHARS:
            content = content[:MAX_CONTENT_CHARS] + "\n… [截断]"
        return f"HTTP {status}\n{content}"
    except Exception as e:
        return f"❌ 请求失败: {e}"


# 导出工具列表
WEB_TOOLS = [http_get, fetch_webpage, http_post]