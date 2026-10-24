import copy
import json
import os
import threading
import uuid
from pathlib import Path

from ..config.defaults import DEFAULT_CONFIG
from ..config.environment import load_env
from ..config.validation import merge_config, validate_config


class Storage:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        load_env(self.root)
        self.lock = threading.RLock()
        if not self.path("config.json").exists():
            self.write_json("config.json", DEFAULT_CONFIG)
        self.get_config()

    def path(self, relative: str) -> Path:
        path = (self.root / relative).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("路径不在数据目录中")
        return path

    def read_json(self, relative: str, default=None):
        with self.lock:
            path = self.path(relative)
            if not path.exists():
                return copy.deepcopy(default)
            return json.loads(path.read_text(encoding="utf-8-sig"))

    def write_text(self, relative: str, content: str) -> None:
        with self.lock:
            path = self.path(relative)
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
            try:
                temporary.write_text(content, encoding="utf-8")
                os.replace(temporary, path)
            finally:
                temporary.unlink(missing_ok=True)

    def write_json(self, relative: str, content) -> None:
        self.write_text(relative, json.dumps(content, ensure_ascii=False, indent=2))

    def read_text(self, relative: str) -> str:
        with self.lock:
            path = self.path(relative)
            return path.read_text(encoding="utf-8") if path.exists() else ""

    def tail_text(self, relative: str, limit: int = 65536) -> str:
        with self.lock:
            path = self.path(relative)
            if not path.exists():
                return ""
            with path.open("rb") as stream:
                stream.seek(0, 2)
                stream.seek(max(0, stream.tell() - limit))
                return stream.read().decode("utf-8", errors="replace")

    def append(self, relative: str, text: str) -> None:
        with self.lock:
            path = self.path(relative)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as stream:
                stream.write(text + "\n")

    def get_config(self) -> dict:
        stored = self.read_json("config.json", {})
        stored.pop("analysis", None)
        config = merge_config(DEFAULT_CONFIG, stored)
        validate_config(config, self.root)
        return config

    def update_config(self, updates: dict) -> dict:
        with self.lock:
            config = merge_config(self.get_config(), updates)
            validate_config(config, self.root)
            self.write_json("config.json", config)
            return config

    def reports(self, mode=None) -> list:
        with self.lock:
            results = []
            for path in sorted(self.path("reports").glob("*/result.json"), reverse=True):
                result = self.read_json(str(path.relative_to(self.root)))
                if mode is not None and result.get("mode") != mode:
                    continue
                results.append({key: result[key] for key in ("report_id", "query", "executed_at", "source_count", "mode", "risk_level")})
            return results
