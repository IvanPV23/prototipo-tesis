"""Registro JSONL append-only, seguro para hilos en el proceso actual."""
import json
from pathlib import Path
from threading import Lock

_lock = Lock()

def append_jsonl(path: str | Path, payload: dict) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with _lock, target.open("a", encoding="utf-8") as output:
        output.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
