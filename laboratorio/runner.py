"""Orquestador de corridas experimentales (Fase 2 del cronograma: EP01-EP04).

Cada corrida levanta una central uvicorn **nueva** (base SQLite vacía), siembra el catálogo y
los vales compartidos, y lanza 5 nodos de campo como **procesos paralelos** del sistema
operativo. Las condiciones se intercalan (limpia, fallos, limpia, ...) para repartir entre
ambas cualquier deriva térmica o de carga del equipo.

Uso:
    .venv\\Scripts\\python -m laboratorio.runner --repeticiones 30 --salida resultados/01_recoleccion_en_bruto
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import platform
import socket
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

from client.app.services.vale_service import ValeService
from client.app.storage.local_db import LocalDB
from client.app.sync.sync_engine import SyncEngine

from . import dataset as ds
from .nodo import run_node
from .verificacion import verify_run

ROOT = Path(__file__).resolve().parents[1]
BATCH_SIZE, MAX_RETRIES = 100, 5


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start_server(run_dir: Path, port: int) -> subprocess.Popen:
    env = dict(os.environ, DATABASE_URL=f"sqlite:///{(run_dir / 'central.db').as_posix()}",
               SERVER_SYNC_LOG=str(run_dir / "servidor-lotes.jsonl"), PYTHONPATH=str(ROOT))
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", str(port),
                             "--workers", "1", "--log-level", "warning", "--no-access-log"], cwd=ROOT, env=env,
                            stdout=open(run_dir / "uvicorn.out.log", "w"), stderr=open(run_dir / "uvicorn.err.log", "w"))
    deadline = time.time() + 60
    while time.time() < deadline:
        try:
            if httpx.get(f"http://127.0.0.1:{port}/health", timeout=1).status_code == 200:
                return proc
        except httpx.HTTPError:
            time.sleep(0.2)
    proc.kill()
    raise RuntimeError("uvicorn no respondió /health")


def _seed(base_url: str, run_dir: Path, data: dict) -> None:
    for item in data["catalogo"]:
        response = httpx.post(f"{base_url}/api/v1/items", json={k: item[k] for k in ("id", "descripcion", "unidad_medida", "stock_referencia")},
                              headers={"x-actor-id": "LOGISTICA", "x-actor-role": "logistica"}, timeout=10)
        response.raise_for_status()
    db = LocalDB(str(run_dir / "LOGISTICA.sqlite"), ds.SEED_NODE)
    engine = SyncEngine(db, ds.SEED_NODE, base_url, actor_role="logistica", batch_size=BATCH_SIZE)
    engine.pull()
    service = ValeService(db, ds.SEED_NODE)
    for v in data["seed_vales"]:
        service.registrar(v["tipo"], v["material"], v["cantidad"], v["proyecto"], vale_id=v["vale_id"])
    engine.push()
    engine.close()
    db.close()


def run_once(out: Path, condicion: str, repeticion: int) -> dict:
    run_id = f"{condicion}_r{repeticion:02d}"
    run_dir = out / "corridas" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    seed = 20260000 + repeticion  # mismo dataset para ambas condiciones de una repetición (diseño pareado)
    data = ds.generate(seed)
    ds.write(data, run_dir / "dataset.json")
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    started = datetime.now(timezone.utc)
    server = _start_server(run_dir, port)
    try:
        _seed(base_url, run_dir, data)
        ctx = mp.get_context("spawn")
        barrier, results = ctx.Barrier(len(ds.DEVICES)), ctx.Queue()
        procs = []
        for index, device in enumerate(ds.DEVICES):
            cfg = {"device": device, "device_index": index, "run_dir": str(run_dir), "base_url": base_url, "ops": data["devices"][device],
                   "condicion": condicion, "repeticion": repeticion, "seed": seed, "batch_size": BATCH_SIZE, "max_retries": MAX_RETRIES}
            proc = ctx.Process(target=run_node, args=(cfg, barrier, results), name=device)
            proc.start()
            procs.append(proc)
        nodes = [results.get(timeout=900) for _ in procs]
        for proc in procs:
            proc.join(timeout=60)
    finally:
        server.terminate()
        server.wait(timeout=30)
    failed = [n for n in nodes if not n["ok"]]
    if failed:
        (run_dir / "error.txt").write_text("\n\n".join(n.get("error", "") for n in failed), encoding="utf-8")
        raise RuntimeError(f"{run_id}: fallaron nodos {[n['device'] for n in failed]}")
    nodes.sort(key=lambda n: n["device"])
    (run_dir / "nodos.json").write_text(json.dumps(nodes, indent=1, default=str), encoding="utf-8")
    verification = verify_run(run_dir, data, nodes)
    meta = {"run_id": run_id, "condicion": condicion, "repeticion": repeticion, "semilla_dataset": seed, "inicio": started.isoformat(),
            "fin": datetime.now(timezone.utc).isoformat(), "puerto": port}
    (run_dir / "verificacion.json").write_text(json.dumps({"meta": meta, **verification}, indent=1, default=str), encoding="utf-8")
    return {"meta": meta, **verification}


def environment() -> dict:
    import fastapi, pydantic, sqlalchemy, uvicorn  # noqa: E401
    info = {"sistema_operativo": platform.platform(), "procesador": platform.processor(), "nucleos_logicos": os.cpu_count(),
            "python": sys.version.split()[0], "sqlite": sqlite3.sqlite_version, "fastapi": fastapi.__version__,
            "uvicorn": uvicorn.__version__, "sqlalchemy": sqlalchemy.__version__, "pydantic": pydantic.__version__,
            "httpx": httpx.__version__, "red": "loopback 127.0.0.1 (misma máquina)", "tamano_lote": BATCH_SIZE, "max_reintentos": MAX_RETRIES}
    try:
        out = subprocess.run(["wmic", "computersystem", "get", "totalphysicalmemory"], capture_output=True, text=True).stdout
        info["memoria_gb"] = round(int(out.split()[1]) / 1024 ** 3, 1)
        info["procesador"] = subprocess.run(["wmic", "cpu", "get", "name"], capture_output=True, text=True).stdout.split("\n", 1)[1].strip()
    except Exception:
        pass
    return info


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeticiones", type=int, default=30)
    parser.add_argument("--desde", type=int, default=1)
    parser.add_argument("--condiciones", nargs="+", default=["limpia", "fallos"])
    parser.add_argument("--salida", default="resultados/01_recoleccion_en_bruto")
    args = parser.parse_args()
    out = ROOT / args.salida
    out.mkdir(parents=True, exist_ok=True)
    (out / "ambiente.json").write_text(json.dumps(environment(), indent=1, ensure_ascii=False), encoding="utf-8")
    for rep in range(args.desde, args.repeticiones + 1):
        for condicion in args.condiciones:
            run_dir = out / "corridas" / f"{condicion}_r{rep:02d}"
            if (run_dir / "verificacion.json").exists():
                continue
            t0 = time.time()
            result = run_once(out, condicion, rep)
            print(f"[{datetime.now():%H:%M:%S}] {result['meta']['run_id']}: Do={result['Do']['pct']:.2f}% Id={result['Id']['pct']:.2f}% "
                  f"Tr={result['Tr']['pct']:.2f}% conv={result['convergencia']['replicas_convergentes']}/5 "
                  f"dup={result['duplicidad']['eventos_duplicados']} fallas={result['resiliencia']['fallas_inyectadas']} "
                  f"({time.time() - t0:.1f}s)", flush=True)


if __name__ == "__main__":
    main()
