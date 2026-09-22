import json
from pathlib import Path
from datetime import datetime, timezone
import pytest

@pytest.fixture
def output_dir():
    path = Path(__file__).parent / "outputs"
    path.mkdir(parents=True, exist_ok=True)
    (path / "logs").mkdir(parents=True, exist_ok=True)
    return path

def write_json(path, payload):
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

def now():
    return datetime.now(timezone.utc).isoformat()

def record_integrity(output_dir, key, payload):
    path = output_dir / "integridad.json"
    content = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"fecha_generacion": now(), "resultados": {}}
    if "resultados" not in content:
        content = {"fecha_generacion": now(), "resultados": {"legado": content}}
    content["resultados"][key] = payload
    write_json(path, content)

def log(output_dir, name, lines):
    stamp = datetime.now(timezone.utc).isoformat()
    (output_dir / "logs" / name).write_text("\n".join(f"[{stamp}] {line}" for line in lines) + "\n", encoding="utf-8")
