import copy
from pathlib import Path
from urllib.parse import urlsplit

from ..core.constants import SOURCE_TYPES
from .database import validate_database
from .llm import validate_llm_config

def merge_config(base: dict, updates: dict) -> dict:
    result = copy.deepcopy(base)
    if not isinstance(updates, dict):
        raise ValueError("配置必须是 JSON 对象")
    for key, value in updates.items():
        if key not in base:
            raise ValueError(f"未知配置项：{key}")
        result[key] = merge_config(base[key], value) if isinstance(base[key], dict) else value
    return result


def validate_config(config: dict, root: Path) -> None:
    system = config["system"]
    collection = config["collection"]
    if not isinstance(system["name"], str) or not 1 <= len(system["name"]) <= 100:
        raise ValueError("系统名称长度须为 1–100")
    if not isinstance(system["auto_start"], bool):
        raise ValueError("auto_start 必须为布尔值")
    for value, minimum, maximum, label in (
        (system["max_results"], 1, 500, "max_results"),
        (system["request_timeout"], 1, 60, "request_timeout"),
        (collection["forum_interval"], 2, 3600, "forum_interval"),
    ):
        if type(value) is not int or not minimum <= value <= maximum:
            raise ValueError(f"{label} 必须为 {minimum}–{maximum} 的整数")
    if collection["mode"] not in ("demo", "live", "database"):
        raise ValueError("采集模式必须为 database、demo 或 live")
    validate_database(config["database"])
    feeds = collection["rss_feeds"]
    if not isinstance(feeds, list) or len(feeds) > 20:
        raise ValueError("rss_feeds 必须为最多 20 项的列表")
    for feed in feeds:
        if not isinstance(feed, dict) or set(feed) - {"url", "source_type"}:
            raise ValueError("RSS 配置只支持 url、source_type")
        if not isinstance(feed.get("url"), str):
            raise ValueError("RSS url 必须为字符串")
        parsed = urlsplit(feed["url"])
        if parsed.scheme not in ("https", "http") or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("RSS 地址须为不带凭据的 HTTP(S) 地址")
        if feed.get("source_type") not in SOURCE_TYPES[:-1]:
            raise ValueError("RSS source_type 须为 news、image、video 或 forum_post")
    internal_file = collection["internal_file"]
    if not isinstance(internal_file, str):
        raise ValueError("internal_file 必须为相对路径")
    if internal_file and (Path(internal_file).is_absolute() or not (root / internal_file).resolve().is_relative_to(root)):
        raise ValueError("内部数据路径不能超出数据目录")
    validate_llm_config(config["llm"])
    if not all(isinstance(value, bool) for value in config["apps"].values()):
        raise ValueError("应用开关必须为布尔值")
