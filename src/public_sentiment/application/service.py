import os
import shutil
import threading
import time
import uuid
from datetime import datetime

from ..runtime.events import EventBus
from ..collection.forum import ForumMonitor
from ..runtime.tasks import CoroutineManager
from ..core.constants import SOURCE_TYPES
from ..core.utils import now, safe_id
from ..infrastructure.storage import Storage
from ..analysis.client import LLMClient, task_timeout


class Service:
    def __init__(self, root):
        self.storage = Storage(root)
        self.events = EventBus()
        self.errors = self.storage.read_json("runtime/errors.json", [])[-50:]
        self.lock = threading.RLock()
        self.analysis_lock = threading.Lock()
        self.started_clock = time.monotonic()
        self.system_status = "offline"
        self.manager = CoroutineManager(self.storage, self.events, self.record_error)
        self.forum = ForumMonitor(self.storage, self.events, self.record_error)
        if self.storage.get_config()["system"]["auto_start"]:
            self.start_system()

    def record_error(self, module_name, error_message):
        with self.storage.lock:
            record = {"time": now(), "module_name": module_name, "error_message": str(error_message)}
            self.errors.append(record)
            self.errors = self.errors[-50:]
            self.storage.write_json("runtime/errors.json", self.errors)
            self.storage.append("runtime/system.log", f"{record['time']} [error] {module_name}: {error_message}")
        self.events.publish("error", **record)

    def transition(self, status):
        self.system_status = status
        running = [name for name, app in self.manager.apps.items() if app.status == "running"]
        self.storage.write_json("runtime/system.json", {"system_status": status, "running_apps": running, "time": now()})
        self.storage.append("runtime/system.log", f"{now()} system_status={status}")
        self.events.publish("system_status", system_status=status, running_apps=running)

    def start_system(self):
        with self.lock:
            if self.system_status == "online":
                return self.status()
            self.transition("starting")
            try:
                for name, enabled in self.storage.get_config()["apps"].items():
                    if enabled:
                        self.manager.get(name).start()
                self.transition("online")
            except Exception:
                self.manager.stop_all()
                self.transition("offline")
                raise
            return self.status()

    def shutdown(self):
        with self.lock:
            self.transition("shutting_down")
            self.forum.stop()
            self.manager.stop_all()
            self.transition("offline")
            return self.status()

    def require_online(self):
        if self.system_status != "online":
            raise RuntimeError("分析服务未在线，请先启动系统")

    def start_app(self, name):
        with self.lock:
            self.require_online()
            return self.manager.get(name).start()

    def stop_app(self, name):
        with self.lock:
            return self.manager.get(name).stop()

    def status(self):
        disk = shutil.disk_usage(self.storage.root)
        apps = self.manager.snapshot()
        return {
            "system_status": self.system_status, "apps": apps,
            "running_apps": [name for name, app in apps.items() if app["status"] == "running"],
            "forum_status": self.forum.status, "recent_errors": list(self.errors[-10:]),
            "resources": {"uptime_seconds": round(time.monotonic() - self.started_clock), "pid": os.getpid(),
                          "cpu_count": os.cpu_count(), "active_threads": threading.active_count(),
                          "disk_free_bytes": disk.free, "disk_total_bytes": disk.total},
            "report_count": len(self.reports()), "mode": self.storage.get_config()["collection"]["mode"], "time": now(),
        }

    def update_config(self, updates):
        with self.lock:
            config = self.storage.update_config(updates)
            self.storage.append("runtime/system.log", f"{now()} 配置已更新，新任务与下一轮论坛采集使用新配置")
            return config

    def search(self, body, report_id=None):
        query = body.get("query")
        selected = body.get("source_types", list(SOURCE_TYPES))
        if not isinstance(query, str) or not query.strip() or len(query) > 200:
            raise ValueError("query 须为 1–200 字符的主题词")
        if not isinstance(selected, list) or not selected or not all(isinstance(item, str) and item in SOURCE_TYPES for item in selected):
            raise ValueError("source_types 须为非空的合法来源类型数组")
        selected = list(dict.fromkeys(selected))
        if not self.analysis_lock.acquire(blocking=False):
            raise RuntimeError("已有主题分析正在执行，请稍后重试")
        try:
            with self.lock:
                self.require_online()
                required = ["insight", "report", "graph"]
                public_types = [kind for kind in selected if kind not in ("image", "video")]
                media_types = [kind for kind in selected if kind in ("image", "video")]
                if public_types:
                    required.append("search")
                if media_types:
                    required.append("multimedia")
                for name in required:
                    if self.manager.get(name).status != "running":
                        raise RuntimeError(f"请先启动应用：{name}")
                config = self.storage.get_config()
            executed_at = now()
            LLMClient(config["llm"])
            identifier = safe_id(report_id or (datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:8]))
            payload = {"query": query.strip(), "source_types": selected, "config": config, "root": str(self.storage.root)}
            collected = self.manager.submit_many([
                (name, {**payload, "source_types": types}, 120)
                for name, types in (("search", public_types), ("multimedia", media_types)) if types
            ])
            sources = [source for batch in collected for source in batch["sources"]]
            merge_truncated = len(sources) > config["system"]["max_results"]
            sources = sorted(sources, key=lambda item: item["published_at"], reverse=True)[:config["system"]["max_results"]]
            if not sources:
                raise ValueError("没有匹配来源，无法执行有证据的模型分析；请调整主题或数据源")
            analysis = self.manager.get("insight").submit({"config": config, "sources": sources, "query": query.strip()},
                                                          timeout=task_timeout(config["llm"], len(sources), "analysis"))
            samples = analysis.pop("_training_samples", [])
            result = {"report_id": identifier, "query": query.strip(), "executed_at": executed_at,
                      "source_types": selected, "source_count": len(sources), "mode": config["collection"]["mode"],
                      "warnings": list(dict.fromkeys(warning for batch in collected for warning in batch["warnings"])), **analysis}
            result["provenance"] = {
                "mode": config["collection"]["mode"],
                "database": config["database"]["name"] if config["collection"]["mode"] == "database" else None,
                "tables": sorted({source["locator"]["table"] for source in sources if source.get("locator")}),
                "sample_limit": config["system"]["max_results"],
            }
            if merge_truncated:
                result["warnings"].append("跨来源合并后达到全局样本上限，按发布时间取最近样本；报告不是全库统计")
            if any(source["analysis_truncated"] for source in result["sources"]):
                result["warnings"].append("部分正文超过 llm.max_chars_per_source，模型只分析截取部分；完整采集文本保留在来源中")
            report, graph = self.manager.submit_many([
                ("report", {"result": result, "config": config}, task_timeout(config["llm"], len(sources), "report")),
                ("graph", {"result": result}, 120),
            ])
            samples.extend(report.pop("_training_samples", []))
            result.update(report)
            result["analysis_backend"] = "llm"
            result["graph_path"] = f"graphs/{identifier}/graph.json"
            with self.storage.lock:
                self.storage.write_json(result["graph_path"], graph)
                self.storage.write_text(f"reports/{identifier}/report.md", report["markdown"])
                self.storage.write_json(f"reports/{identifier}/config.snapshot.json", config)
                self.storage.write_json(f"reports/{identifier}/result.json", result)
                if samples:
                    self.storage.write_json(f"training/candidates/{identifier}.json", {"report_id": identifier, "query": query.strip(),
                                            "created_at": executed_at, "reviewed": False, "samples": samples})
                self.storage.write_json("runtime/latest_report.json", {"report_id": identifier})
            self.events.publish("graph_ready", report_id=identifier, graph_path=result["graph_path"])
            return result
        except Exception as error:
            self.record_error("search", str(error))
            raise
        finally:
            self.analysis_lock.release()

    def get_report(self, report_id):
        result = self.storage.read_json(f"reports/{safe_id(report_id)}/result.json")
        if result is None:
            raise KeyError("报告不存在")
        return result

    def reports(self):
        return self.storage.reports(mode=self.storage.get_config()["collection"]["mode"])

    def graph(self, report_id=None):
        if report_id is None:
            reports = self.reports()
            if not reports:
                raise KeyError("当前数据模式暂无图谱，请先执行主题分析；旧示例不会作为最新真实结果展示")
            report_id = reports[0]["report_id"]
        graph = self.storage.read_json(f"graphs/{safe_id(report_id)}/graph.json")
        if graph is None:
            raise KeyError("图谱不存在")
        return graph

    def query_graph(self, body):
        graph = self.graph(body.get("report_id") or None)
        for key in ("node", "node_type", "relation"):
            if not isinstance(body.get(key, ""), str):
                raise ValueError(f"{key} 必须为字符串")
        term = body.get("node", "").casefold()
        node_type = body.get("node_type", "")
        relation = body.get("relation", "")
        matching = {node["id"] for node in graph["nodes"] if (not term or term in node["id"].casefold() or term in node["label"].casefold()) and (not node_type or node["type"] == node_type)}
        edges = [edge for edge in graph["edges"] if (not relation or edge["type"] == relation) and (edge["source"] in matching or edge["target"] in matching)]
        visible = matching | {edge[key] for edge in edges for key in ("source", "target")}
        if relation and not term and not node_type:
            visible = {edge[key] for edge in edges for key in ("source", "target")}
        return {**graph, "nodes": [node for node in graph["nodes"] if node["id"] in visible], "edges": edges}
