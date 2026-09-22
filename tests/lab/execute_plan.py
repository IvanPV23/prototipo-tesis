"""Ejecuta EP01--EP04 contra un uvicorn ya disponible."""
from __future__ import annotations
import csv
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from client.app.services.vale_service import ValeService
from client.app.storage.local_db import LocalDB
from client.app.sync.sync_engine import SyncEngine
from shared.structured_log import append_jsonl
from .fault_injector import PostCommitDisconnectTransport
from .generar_dataset import generate

def execute(base_url: str, output: Path = Path("outputs/plan")) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    dataset = generate(output / "dataset.json")
    replicas = {}
    # EP01: 1,000 escrituras offline, registrando tanto intentos como éxitos.
    for device, operations in dataset["devices"].items():
        db = LocalDB(str(output / f"{device}.sqlite")); service = ValeService(db, device)
        for spec in operations:
            started = datetime.now(timezone.utc)
            try:
                service.guardar(spec["aggregate_id"], spec["codigo"], spec["material"], spec["cantidad"], cancelar=spec.get("cancelar", False))
                append_jsonl(output / "offline-attempts.jsonl", {"scenario": "EP01", "device_id": device, "aggregate_id": spec["aggregate_id"], "intentado_en": started, "confirmado_en": datetime.now(timezone.utc), "resultado": "success"})
            except Exception as exc:
                append_jsonl(output / "offline-attempts.jsonl", {"scenario": "EP01", "device_id": device, "aggregate_id": spec["aggregate_id"], "intentado_en": started, "resultado": "error", "error": str(exc)})
                raise
        replicas[device] = db
    # EP02/EP03: cinco lotes concurrentes hacia el mismo uvicorn.
    def sync_device(item):
        device, db = item
        return device, SyncEngine(db, device, base_url, log_path=output / "client-sync.jsonl").sync()
    with ThreadPoolExecutor(max_workers=5) as workers:
        responses = dict(workers.map(sync_device, replicas.items()))
    # EP04: se agrega un evento y se corta la respuesta ya confirmada; el retry
    # debe producir exactamente un evento central y al menos un intento fallido.
    ep04_db = replicas["CLI-1"]
    ValeService(ep04_db, "CLI-1").guardar("EP04-RECOVERY", "EP04-RECOVERY", "Material-EP04", 1)
    ep04 = SyncEngine(ep04_db, "CLI-1", base_url, transport=PostCommitDisconnectTransport(), max_retries=3, log_path=output / "client-sync.jsonl").sync()
    with (output / "lotes.csv").open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=["lote_id", "device_id", "n_vales", "enviado_en", "confirmado_en", "latencia_ms"])
        writer.writeheader()
        for line in (output / "client-sync.jsonl").read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if row.get("resultado_http") == 200:
                sent, confirmed = datetime.fromisoformat(row["enviado_en"]), datetime.fromisoformat(row["confirmado_en"])
                writer.writerow({"lote_id": row["lote_id"], "device_id": row["device_id"], "n_vales": row["n_vales"], "enviado_en": row["enviado_en"], "confirmado_en": row["confirmado_en"], "latencia_ms": round((confirmed - sent).total_seconds() * 1000, 3)})
    result = {"ep01_offline_operations": 1000, "ep02_batches": len(responses), "ep04": ep04, "generated_at": datetime.now(timezone.utc).isoformat()}
    (output / "summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
