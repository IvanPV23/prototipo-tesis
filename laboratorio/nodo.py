"""Proceso de un nodo de campo simulado (un dispositivo = un proceso del SO).

Fases sincronizadas con barreras entre los 5 procesos:
  0. Arranque en línea: descarga del catálogo y de los vales compartidos.
  1. EP01: 200 operaciones sin red; cada 50 operaciones se sondea la conectividad.
  2. EP02/EP03/EP04: reconexión simultánea y push de la cola en lotes de 100.
  3. Convergencia: pull incremental de los cambios del resto de nodos.
"""
from __future__ import annotations

import hashlib
import json
import random
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from client.app.services.vale_service import ValeService
from client.app.storage.local_db import LocalDB
from client.app.sync.sync_engine import SyncEngine, SyncError
from shared.structured_log import append_jsonl

from .faults import FaultTransport, OfflineTransport, plan_for

PROBE_EVERY = 50


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def snapshot_hash(snapshot: dict) -> str:
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True, default=str).encode()).hexdigest()


def run_node(cfg: dict, barrier, results) -> None:
    device, run_dir = cfg["device"], Path(cfg["run_dir"])
    out = {"device": device, "ok": False}
    try:
        db = LocalDB(str(run_dir / f"{device}.sqlite"), device)
        service = ValeService(db, device)
        engine_kw = dict(batch_size=cfg["batch_size"], max_retries=cfg["max_retries"], log_path=run_dir / f"cliente-{device}.jsonl",
                         seed=cfg["seed"])
        online = SyncEngine(db, device, cfg["base_url"], **engine_kw)
        out["bootstrap"] = online.pull()

        # ---------------- EP01: operación sin red
        barrier.wait()
        offline = SyncEngine(db, device, cfg["base_url"], transport=OfflineTransport(), max_retries=1, batch_size=cfg["batch_size"])
        ops_log = run_dir / f"ep01-{device}.jsonl"
        ep01_start = perf_counter()
        for spec in cfg["ops"]:
            started_at, started = _iso(), perf_counter()
            record = {"device_id": device, "seq": spec["seq"], "op": spec["op"], "vale_id": spec["vale_id"], "overlap": spec["overlap"],
                      "intentado_en": started_at}
            try:
                if spec["op"] == "REGISTRAR":
                    event = service.registrar(spec["tipo"], spec["material"], spec["cantidad"], spec["proyecto"], vale_id=spec["vale_id"])
                elif spec["op"] == "ANULAR":
                    event = service.anular(spec["vale_id"])
                elif spec["op"] == "REASIGNAR":
                    event = service.reasignar_proyecto(spec["vale_id"], spec["proyecto"])
                else:
                    event = service.observar(spec["vale_id"], spec["observacion"])
                persisted = db.has_event(str(event.event_id)) and db.get_vale(spec["vale_id"]) is not None
                append_jsonl(ops_log, dict(record, resultado="EXITO" if persisted else "NO_PERSISTIDO", event_id=str(event.event_id),
                                           latencia_ms=round((perf_counter() - started) * 1000, 3), confirmado_en=_iso()))
            except Exception as exc:  # se registra el intento fallido; cuenta en el denominador de Do
                append_jsonl(ops_log, dict(record, resultado="ERROR", error=repr(exc)[:300],
                                           latencia_ms=round((perf_counter() - started) * 1000, 3)))
            if (spec["seq"] + 1) % PROBE_EVERY == 0:  # el nodo monitorea conectividad (Fig. 5, paso 3)
                probe_started = perf_counter()
                try:
                    offline.push()
                    probe = "CONECTADO"
                except SyncError:
                    probe = "SIN_RED"
                append_jsonl(run_dir / f"sondas-{device}.jsonl", {"device_id": device, "despues_de_op": spec["seq"] + 1,
                             "resultado": probe, "pendientes": db.count_pending(),
                             "duracion_ms": round((perf_counter() - probe_started) * 1000, 3), "instante": _iso()})
        out["ep01_duracion_ms"] = round((perf_counter() - ep01_start) * 1000, 3)
        out["pendientes_antes_de_reconexion"] = db.count_pending()

        # ---------------- EP02/EP03/EP04: reconexión masiva simultánea
        transport = None
        if cfg["condicion"] == "fallos":
            n_lotes = -(-db.count_pending() // cfg["batch_size"])
            plan = plan_for(cfg["device_index"], cfg["repeticion"], n_lotes, random.Random(cfg["seed"] * 31 + cfg["device_index"]))
            transport = FaultTransport(plan)
            out["plan_fallas"] = plan
        pusher = SyncEngine(db, device, cfg["base_url"], transport=transport, **engine_kw)
        barrier.wait()
        out["reconexion_inicio"] = time.time()
        push_start = perf_counter()
        out["lotes"] = pusher.push()
        out["push_duracion_ms"] = round((perf_counter() - push_start) * 1000, 3)
        out["push_fin"] = time.time()
        out["fallas_inyectadas"] = transport.injected if transport else []
        out["pendientes_despues_push"] = db.count_pending()

        # ---------------- Convergencia
        barrier.wait()
        pull = online.pull()
        out["pull"] = pull
        out["convergencia_fin"] = time.time()
        snap = db.snapshot()
        out["snapshot_hash"] = snapshot_hash(snap)
        out["stocks"] = snap["stocks"]
        out["n_vales"] = len(snap["vales"])
        online.close(); pusher.close(); offline.close(); db.close()
        out["ok"] = True
    except Exception:
        out["error"] = traceback.format_exc()
        try:
            barrier.abort()
        except Exception:
            pass
    results.put(out)
