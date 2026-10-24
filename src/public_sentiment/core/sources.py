import hashlib
import html
import json
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from .constants import SOURCE_TYPES

def plain_text(value: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", value or "")).strip()


def matches(query: str, source: dict) -> bool:
    haystack = f"{source['title']} {source['content']}".casefold()
    terms = [term for term in re.split(r"[\s,，;；]+", query.casefold()) if term]
    return any(term in haystack for term in terms)


def normalize_source(item: dict, index: int) -> dict:
    if not isinstance(item, dict) or item.get("source_type") not in SOURCE_TYPES:
        raise ValueError(f"第 {index + 1} 条来源的 source_type 无效")
    for field in ("title", "content"):
        if not isinstance(item.get(field), str) or not item[field].strip():
            raise ValueError(f"第 {index + 1} 条来源缺少 {field}")
    for field in ("url", "published_at", "author"):
        if field in item and not isinstance(item[field], str):
            raise ValueError(f"来源 {field} 必须为字符串")
    identity = hashlib.sha256(json.dumps(item, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]
    published_at = item.get("published_at", "")
    if published_at:
        try:
            try:
                timestamp = datetime.fromisoformat(published_at)
            except ValueError:
                timestamp = parsedate_to_datetime(published_at)
            published_at = timestamp.replace(tzinfo=timestamp.tzinfo or timezone.utc).astimezone(timezone.utc).isoformat(timespec="seconds")
        except (ValueError, TypeError, OverflowError):
            published_at = ""
    return {
        "id": str(item.get("id", f"source-{identity}"))[:100], "source_type": item["source_type"],
        "title": plain_text(item["title"])[:500], "content": plain_text(item["content"])[:10000],
        "url": item.get("url", ""), "published_at": published_at,
        "author": item.get("author", "未署名"), "demo": bool(item.get("demo", False)),
    }
