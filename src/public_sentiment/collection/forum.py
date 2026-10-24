import hashlib
import threading
from datetime import date

from .collector import collect
from ..core.utils import now


class ForumMonitor:
    def __init__(self, storage, events, error_callback):
        self.storage = storage
        self.events = events
        self.error_callback = error_callback
        self.status = "idle"
        self.thread = None
        self.halt = threading.Event()
        self.lock = threading.RLock()
        self.seen = set(storage.read_json("runtime/forum/seen.json", []))
        self.persist()

    def persist(self):
        self.storage.write_json("runtime/forum/status.json", {"status": self.status})

    def log(self, event_type, message, source=None):
        record = {"time": now(), "event_type": event_type, "message_text": message, "task_status": self.status}
        if source:
            record["source"] = source
        with self.storage.lock:
            path = f"runtime/forum/history/{date.today().isoformat()}.json"
            records = self.storage.read_json(path, [])
            records.append(record)
            self.storage.write_json(path, records)
            self.storage.append("runtime/forum/latest.log", f"{record['time']} [{event_type}] [{self.status}] {message}")
        self.events.publish("forum_log", **record)

    def start(self):
        with self.lock:
            if self.status == "running":
                return {"status": self.status}
            self.halt.clear()
            self.status = "running"
            self.persist()
            self.log("start", "论坛监控启动（按配置读取数据库论坛表 / RSS / 示例记录）")
            self.thread = threading.Thread(target=self.run, daemon=True, name="forum-monitor")
            self.thread.start()
            return {"status": self.status}

    def run(self):
        try:
            while not self.halt.is_set():
                config = self.storage.get_config()
                result = collect({"config": config, "root": str(self.storage.root), "source_types": ["forum_post"], "query": ""})
                if self.halt.is_set():
                    return
                for warning in result["warnings"]:
                    self.log("warning", warning)
                new_count = 0
                for source in result["sources"]:
                    if self.halt.is_set():
                        return
                    fingerprint = source["id"] + ":" + hashlib.sha256(source["content"].encode()).hexdigest()[:16]
                    if fingerprint not in self.seen:
                        self.log("collected", source["title"], source)
                        self.seen.add(fingerprint)
                        new_count += 1
                self.storage.write_json("runtime/forum/seen.json", sorted(self.seen))
                self.log("poll", f"本轮匹配 {len(result['sources'])} 条，新增 {new_count} 条；模式 {result['mode']}")
                if self.halt.wait(config["collection"]["forum_interval"]):
                    return
        except Exception as error:
            with self.lock:
                self.status = "failed"
                self.persist()
                self.log("error", str(error))
                self.error_callback("forum", str(error))

    def stop(self):
        self.halt.set()
        thread = self.thread
        if thread and thread.is_alive():
            thread.join()
        with self.lock:
            if self.status != "stopped":
                self.status = "stopped"
                self.persist()
                self.log("stop", "论坛采集已停止，历史记录保留")
            return {"status": self.status}

    def history(self, day):
        try:
            if date.fromisoformat(day).isoformat() != day:
                raise ValueError()
        except (TypeError, ValueError) as error:
            raise ValueError("日期格式应为 YYYY-MM-DD") from error
        return self.storage.read_json(f"runtime/forum/history/{day}.json", [])
