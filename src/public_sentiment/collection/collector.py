import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from ..core.sources import matches, normalize_source
from .database import collect_database
from .feeds import read_feed


def collect(payload: dict) -> dict:
    if payload["config"]["collection"]["mode"] == "database":
        return collect_database(payload)
    config = payload["config"]
    root = Path(payload["root"])
    selected = payload["source_types"]
    collection = config["collection"]
    sources = []
    warnings = []
    internal_file = collection["internal_file"]
    if internal_file:
        path = (root / internal_file).resolve()
        if not path.is_relative_to(root):
            raise ValueError("内部数据路径超出数据目录")
        if path.exists():
            if path.stat().st_size > 10 * 1024 * 1024:
                raise ValueError("内部数据文件不能超过 10 MiB")
            items = json.loads(path.read_text(encoding="utf-8-sig"))
            if not isinstance(items, list) or len(items) > 10000:
                raise ValueError("内部数据应为最多 10000 项的 JSON 数组")
            normalized = [normalize_source(item, index) for index, item in enumerate(items)]
            sources.extend(item for item in normalized if collection["mode"] == "demo" or (item["source_type"] == "internal_data" and not item["demo"]))
        else:
            warnings.append(f"数据文件不存在：{internal_file}")
    if collection["mode"] == "live":
        feeds = [feed for feed in collection["rss_feeds"] if feed["source_type"] in selected]
        with ThreadPoolExecutor(max_workers=4) as executor:
            tasks = {executor.submit(read_feed, feed, config["system"]["request_timeout"]): feed for feed in feeds}
            for task in as_completed(tasks):
                try:
                    sources.extend(task.result())
                except Exception as error:
                    warnings.append(f"采集失败 {tasks[task]['url']}：{error}")
        if not feeds and any(source_type != "internal_data" for source_type in selected):
            warnings.append("所选公开来源未配置 RSS；未使用示例数据补充真实采集结果")
    unique = {}
    for source in sources:
        if source["source_type"] in selected and (not payload["query"] or matches(payload["query"], source)):
            unique.setdefault(source["id"], source)
    results = sorted(unique.values(), key=lambda source: source["published_at"], reverse=True)[:config["system"]["max_results"]]
    return {"sources": results, "warnings": warnings, "mode": collection["mode"]}
