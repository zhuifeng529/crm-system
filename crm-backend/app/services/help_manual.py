# -*- coding: utf-8 -*-
"""系统使用说明书内容加载与目录解析。"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from app.config import BASE_DIR

MANUAL_PATH = BASE_DIR / "content" / "user_manual.md"
# 内容修订号：替换说明书正文并希望客户端感知版本变化时递增。
MANUAL_VERSION = "1.0.0"

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)

_cache: dict[str, Any] | None = None
_cache_mtime_ns: int | None = None


def _slugify(title: str) -> str:
    text = title.strip().lower()
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"[^\w\u4e00-\u9fff\-]+", "", text, flags=re.UNICODE)
    return text or "section"


def _extract_title(markdown: str) -> str:
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return "系统使用说明书"


def _extract_toc(markdown: str) -> list[dict[str, Any]]:
    toc: list[dict[str, Any]] = []
    seen: dict[str, int] = {}
    for match in _HEADING_RE.finditer(markdown):
        level = len(match.group(1))
        title = match.group(2).strip()
        # 跳过文首 H1，目录从章节开始
        if level == 1:
            continue
        base = _slugify(title)
        count = seen.get(base, 0)
        seen[base] = count + 1
        section_id = base if count == 0 else f"{base}-{count + 1}"
        toc.append({"level": level, "id": section_id, "title": title})
    return toc


def clear_manual_cache() -> None:
    global _cache, _cache_mtime_ns
    _cache = None
    _cache_mtime_ns = None


def load_user_manual() -> dict[str, Any]:
    """加载说明书；按文件 mtime 失效进程内缓存，updatedAt 取自 mtime。"""
    global _cache, _cache_mtime_ns
    path = MANUAL_PATH
    if not path.is_file():
        raise FileNotFoundError(f"User manual not found: {path}")
    mtime_ns = path.stat().st_mtime_ns
    if _cache is not None and _cache_mtime_ns == mtime_ns:
        return _cache

    content = path.read_text(encoding="utf-8")
    updated_at = datetime.fromtimestamp(mtime_ns / 1_000_000_000, tz=UTC).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    payload = {
        "title": _extract_title(content),
        "version": MANUAL_VERSION,
        "format": "markdown",
        "updatedAt": updated_at,
        "content": content,
        "toc": _extract_toc(content),
    }
    _cache = payload
    _cache_mtime_ns = mtime_ns
    return payload


def get_user_manual_meta() -> dict[str, Any]:
    manual = load_user_manual()
    return {
        "title": manual["title"],
        "version": manual["version"],
        "format": manual["format"],
        "updatedAt": manual["updatedAt"],
        "toc": manual["toc"],
    }
