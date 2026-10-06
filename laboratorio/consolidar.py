"""Fase 3a - Recolección: consolida los registros en bruto de todas las corridas en CSV planos.

No transforma ni resume: cada fila es un registro tal como lo emitió el instrumento
(logs JSONL append-only del cliente y del servidor, y extracción directa de las tablas
evento_sincronizacion, movimiento_inventario y bitacora_auditoria).

Uso:  python -m laboratorio.consolidar resultados/01_recoleccion_en_bruto
"""
from __future__ import annotations

import csv
import json
import sqlite3
import sys
from pathlib import Path

from .dataset import DEVICES


def _jsonl(path: Path):
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                yield json.loads(line)


class Writer:
    def __init__(self, path: Path, fields: list[str]):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.file = path.open("w", newline="", encoding="utf-8")
        self.writer = csv.DictWriter(self.file, fieldnames=fields, extrasaction="ignore")
        self.writer.writeheader()
        self.rows = 0

    def write(self, row: dict) -> None:
        self.writer.writerow({k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v) for k, v in row.items()})
        self.rows += 1

    def close(self) -> int:
        self.file.close()
        return self.rows


def consolidate(base: Path) -> dict:
    runs = sorted(p for p in (base / "corridas").iterdir() if (p / "verificacion.json").exists())
    key = ["run_id", "condicion", "repeticion"]
    W = {
        "corridas": Writer(base / "corridas.csv", key + [
            "inicio", "fin", "semilla_dataset", "do_exitos", "do_intentos", "do_pct", "id_consistentes", "id_transmitidos", "id_pct",
            "tr_movimientos_trazados", "tr_movimientos", "tr_pct", "eventos_central", "eventos_esperados", "eventos_duplicados",
            "movimientos_esperados", "movimientos_duplicados", "replicas_convergentes", "tiempo_convergencia_ms",
            "tiempo_reconexion_push_ms", "actualizaciones_concurrentes_resueltas", "conflictos_inmutables", "lotes",
            "lotes_confirmados", "fallas_inyectadas", "reintentos", "duplicados_detectados", "pendientes_finales",
            "invariante_items_ok", "saldos_iguales_oraculo", "append_only_rechaza_delete"]),
        "lotes": Writer(base / "lotes.csv", key + [
            "device_id", "lote_ordinal", "lote_id", "n_vales", "enviado_en", "confirmado_en", "latencia_e2e_ms",
            "latencia_ultimo_intento_ms", "duracion_servidor_ms", "espera_cola_ms", "conciliacion_ms", "intentos", "fallas_inyectadas",
            "aplicados", "duplicados", "conflictos"]),
        "intentos": Writer(base / "intentos.csv", key + [
            "device_id", "lote_id", "intento_num", "n_vales", "inicio", "duracion_ms", "resultado_http", "error_tipo", "falla_inyectada", "error"]),
        "servidor": Writer(base / "servidor_lotes.csv", key + [
            "device_id", "lote_id", "n_eventos", "aplicados", "duplicados", "conflictos", "recibido_en", "confirmado_en",
            "duracion_servidor_ms", "espera_cola_ms", "conciliacion_ms"]),
        "ops": Writer(base / "operaciones_offline.csv", key + [
            "device_id", "seq", "op", "vale_id", "overlap", "intentado_en", "confirmado_en", "latencia_ms", "resultado", "event_id", "error"]),
        "sondas": Writer(base / "sondas_conectividad.csv", key + ["device_id", "despues_de_op", "resultado", "pendientes", "duracion_ms", "instante"]),
        "nodos": Writer(base / "convergencia_nodos.csv", key + [
            "device_id", "ep01_duracion_ms", "pendientes_antes_de_reconexion", "push_duracion_ms", "pendientes_despues_push",
            "pull_eventos_fusionados", "pull_duracion_ms", "last_seq", "n_vales_replica", "snapshot_hash", "igual_a_central"]),
        "saldos": Writer(base / "saldos_items.csv", key + [
            "item_id", "stock_referencia", "stock_esperado", "stock_central", "suma_movimientos", "invariante_ok",
            "central_igual_oraculo", "replicas_iguales_central", "stock_replica_min", "stock_replica_max"]),
        "eventos": Writer(base / "tablas_centrales" / "evento_sincronizacion.csv", key + [
            "seq", "evento_id", "vale_id", "tipo_evento", "nodo_origen_id", "actor_id", "sello_tiempo_logico", "estado", "version_vector",
            "lote_id", "creado_en", "recibido_en"]),
        "movimientos": Writer(base / "tablas_centrales" / "movimiento_inventario.csv", key + [
            "movimiento_id", "vale_id", "item_id", "evento_id", "cantidad_conciliada", "unidad_medida", "proyecto_id", "estado",
            "saldo_resultante", "version_vector", "fecha_conciliacion"]),
        "bitacora": Writer(base / "tablas_centrales" / "bitacora_auditoria.csv", key + [
            "auditoria_id", "movimiento_id", "evento_id", "vale_id", "actor_id", "nodo_id", "accion", "sello_tiempo", "sello_logico", "detalles"]),
    }
    for run in runs:
        v = json.loads((run / "verificacion.json").read_text(encoding="utf-8"))
        meta = v["meta"]
        k = {"run_id": meta["run_id"], "condicion": meta["condicion"], "repeticion": meta["repeticion"]}
        W["corridas"].write({**k, "inicio": meta["inicio"], "fin": meta["fin"], "semilla_dataset": meta["semilla_dataset"],
                             "do_exitos": v["Do"]["exitos"], "do_intentos": v["Do"]["intentos"], "do_pct": v["Do"]["pct"],
                             "id_consistentes": v["Id"]["consistentes"], "id_transmitidos": v["Id"]["transmitidos"], "id_pct": v["Id"]["pct"],
                             "tr_movimientos_trazados": v["Tr"]["movimientos_trazados"], "tr_movimientos": v["Tr"]["movimientos"],
                             "tr_pct": v["Tr"]["pct"], **v["duplicidad"], **{x: v["convergencia"][x] for x in
                             ("replicas_convergentes", "tiempo_convergencia_ms", "tiempo_reconexion_push_ms")},
                             "actualizaciones_concurrentes_resueltas": v["crdt"]["actualizaciones_concurrentes_resueltas"],
                             "conflictos_inmutables": v["crdt"]["conflictos_inmutables"],
                             **{x: v["resiliencia"][x] for x in ("lotes", "lotes_confirmados", "fallas_inyectadas", "reintentos",
                                                                 "duplicados_detectados", "pendientes_finales")},
                             "invariante_items_ok": all(s["invariante_ok"] for s in v["saldos"]),
                             "saldos_iguales_oraculo": all(s["central_igual_oraculo"] and s["replicas_iguales_central"] for s in v["saldos"]),
                             "append_only_rechaza_delete": all(v["Tr"]["rechazo_delete_append_only"].values())})
        for s in v["saldos"]:
            W["saldos"].write({**k, **s})
        nodes = json.loads((run / "nodos.json").read_text(encoding="utf-8"))
        for n in nodes:
            W["nodos"].write({**k, "device_id": n["device"], "ep01_duracion_ms": n["ep01_duracion_ms"],
                              "pendientes_antes_de_reconexion": n["pendientes_antes_de_reconexion"], "push_duracion_ms": n["push_duracion_ms"],
                              "pendientes_despues_push": n["pendientes_despues_push"], "pull_eventos_fusionados": n["pull"]["eventos_fusionados"],
                              "pull_duracion_ms": n["pull"]["duracion_ms"], "last_seq": n["pull"]["last_seq"], "n_vales_replica": n["n_vales"],
                              "snapshot_hash": n["snapshot_hash"], "igual_a_central": n["snapshot_hash"] == v["convergencia"]["hash_central"]})
            faults_by_lote = {}
            for f in n.get("fallas_inyectadas", []):
                faults_by_lote.setdefault(f["lote_id"], []).append(f["falla"])
            for ordinal, lote in enumerate(n["lotes"]):
                W["lotes"].write({**k, **lote, "lote_ordinal": ordinal, "fallas_inyectadas": "|".join(faults_by_lote.get(lote["lote_id"], []))})
        for d in DEVICES:
            for r in _jsonl(run / f"cliente-{d}.jsonl"):
                if r["tipo"] == "intento":
                    W["intentos"].write({**k, **r})
            for r in _jsonl(run / f"ep01-{d}.jsonl"):
                W["ops"].write({**k, **r})
            for r in _jsonl(run / f"sondas-{d}.jsonl"):
                W["sondas"].write({**k, **r})
        for r in _jsonl(run / "servidor-lotes.jsonl"):
            if r["device_id"] in DEVICES:
                W["servidor"].write({**k, **r})
        conn = sqlite3.connect(run / "central.db")
        conn.row_factory = sqlite3.Row
        for table, name in (("evento_sincronizacion", "eventos"), ("movimiento_inventario", "movimientos"), ("bitacora_auditoria", "bitacora")):
            for row in conn.execute(f"SELECT * FROM {table} ORDER BY rowid"):
                W[name].write({**k, **dict(row)})
        conn.close()
    return {name: w.close() for name, w in W.items()}


if __name__ == "__main__":
    counts = consolidate(Path(sys.argv[1] if len(sys.argv) > 1 else "resultados/01_recoleccion_en_bruto"))
    print(json.dumps(counts, indent=1))
