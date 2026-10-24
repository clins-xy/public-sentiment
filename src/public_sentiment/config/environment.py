import os
import re
from pathlib import Path

def load_env(root: Path) -> None:
    path = root / ".env"
    if not path.exists():
        return
    for index, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if not separator or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            raise ValueError(f".env 第 {index} 行须为 NAME=value")
        if value.startswith(('"', "'")):
            if len(value) < 2 or value[-1] != value[0]:
                raise ValueError(f".env 第 {index} 行引号未闭合")
            value = value[1:-1]
        os.environ.setdefault(key, value)
