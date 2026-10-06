"""Consultas de verificación (Plan, secc. 4) sobre la base central y las réplicas de una corrida.

Calcula, por corrida, los indicadores de la Tabla 1 del plan:
  Id = registros conciliados sin error / vales transmitidos x 100
  Tr = movimientos con registro inmutable en bitácora / total de movimientos x 100
  Do = registros offline exitosos / intentos de registro en campo x 100
  Tp = tiempo de conciliación del lote / n.º de vales (se deriva de lotes.csv)
"""
from __future__ import annotations

import json
import sqlite3
from collections import Counter
from pathlib import Path

from shared.crdt import vale_digest

from .dataset import DEVICES
from .nodo import snapshot_hash


def _rows(conn, sql, *args):
    return conn.execute(sql, args).fetchall()


def central_snapshot(conn) -> dict:
    vales = []
    for r in _rows(conn, "SELECT vale_id, codigo, tipo, item_id, cantidad, unidad_medida, nodo_origen_id, estado, proyecto_id, "
                         "observacion FROM vale_inventario"):
        vales.append(vale_digest({"id": r[0], "codigo": r[1], "tipo": r[2], "material": r[3], "cantidad": r[4], "unidad_medida": r[5],
                                  "nodo_origen": r[6], "estado": r[7], "proyecto": r[8], "observacion": r[9]}))
    stocks = {r[0]: round(r[1], 6) for r in _rows(conn, "SELECT item_id, stock_actual FROM item_inventario ORDER BY item_id")}
    return {"vales": sorted(vales), "stocks": stocks}


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def verify_run(run_dir: Path, dataset: dict, nodes: list[dict]) -> dict:
    conn = sqlite3.connect(run_dir / "central.db")
    oracle = dataset["oraculo"]
    snap = central_snapshot(conn)
    central_hash = snapshot_hash(snap)
    node_by_id = {n["device"]: n for n in nodes}

    # ------------------------------------------------ Do (EP01)
    ops = [r for d in DEVICES for r in _jsonl(run_dir / f"ep01-{d}.jsonl")]
    do_ok = sum(r["resultado"] == "EXITO" for r in ops)
    sondas = [r for d in DEVICES for r in _jsonl(run_dir / f"sondas-{d}.jsonl")]

    # ------------------------------------------------ Id (integridad por vale transmitido)
    central_vales = {r[0]: {"tipo": r[1], "material": r[2], "cantidad": r[3], "estado": r[4], "proyecto": r[5], "observacion": r[6],
                            "nodo_origen": r[7]}
                     for r in _rows(conn, "SELECT vale_id, tipo, item_id, cantidad, estado, proyecto_id, observacion, nodo_origen_id "
                                          "FROM vale_inventario")}
    replicas = {}
    for d in DEVICES:
        rc = sqlite3.connect(run_dir / f"{d}.sqlite")
        replicas[d] = {r[0]: {"tipo": r[1], "material": r[2], "cantidad": r[3], "estado": r[4], "proyecto": r[5], "observacion": r[6],
                              "nodo_origen": r[7]}
                       for r in _rows(rc, "SELECT id, tipo, material, cantidad, estado, proyecto, observacion, nodo_origen FROM vales")}
        replicas[d]["__stocks__"] = {r[0]: round(r[1], 6) for r in _rows(rc, "SELECT item_id, stock_actual FROM items")}
        rc.close()
    events = {r[0]: {"vale_id": r[1], "estado": r[2], "n": r[3]}
              for r in _rows(conn, "SELECT evento_id, vale_id, estado, COUNT(*) FROM evento_sincronizacion GROUP BY evento_id")}
    transmitted = [r for r in ops if r["resultado"] == "EXITO"]
    consistent, inconsistencias = 0, Counter()
    for r in transmitted:
        expected = oracle["vales"][r["vale_id"]]
        ev = events.get(r["event_id"])
        checks = {
            "evento_conciliado_una_vez": ev is not None and ev["n"] == 1 and ev["estado"] == "APLICADO",
            "estado_central_igual_oraculo": central_vales.get(r["vale_id"]) == expected,
            "replicas_iguales_central": all(replicas[d].get(r["vale_id"]) == central_vales.get(r["vale_id"]) for d in DEVICES),
        }
        if all(checks.values()):
            consistent += 1
        for name, ok in checks.items():
            inconsistencias[name] += not ok

    # ------------------------------------------------ saldos e invariante 4.3
    items = []
    for item_id, ref, actual in _rows(conn, "SELECT item_id, stock_referencia, stock_actual FROM item_inventario ORDER BY item_id"):
        suma = conn.execute("SELECT COALESCE(SUM(cantidad_conciliada), 0) FROM movimiento_inventario WHERE item_id=?", (item_id,)).fetchone()[0]
        replica_stocks = [replicas[d]["__stocks__"].get(item_id) for d in DEVICES]
        items.append({"item_id": item_id, "stock_referencia": ref, "stock_esperado": oracle["stocks"][item_id], "stock_central": round(actual, 6),
                      "suma_movimientos": round(suma, 6), "invariante_ok": round(ref + suma, 6) == round(actual, 6),
                      "central_igual_oraculo": round(actual, 6) == oracle["stocks"][item_id],
                      "replicas_iguales_central": all(s == round(actual, 6) for s in replica_stocks),
                      "stock_replica_min": min(replica_stocks), "stock_replica_max": max(replica_stocks)})

    # ------------------------------------------------ Tr (trazabilidad)
    movimientos = conn.execute("SELECT COUNT(*) FROM movimiento_inventario").fetchone()[0]
    mov_trazados = conn.execute(
        "SELECT COUNT(*) FROM movimiento_inventario m WHERE EXISTS (SELECT 1 FROM bitacora_auditoria b WHERE b.movimiento_id = m.movimiento_id "
        "AND b.evento_id = m.evento_id) AND EXISTS (SELECT 1 FROM evento_sincronizacion e WHERE e.evento_id = m.evento_id)").fetchone()[0]
    eventos_central = conn.execute("SELECT COUNT(*) FROM evento_sincronizacion").fetchone()[0]
    eventos_con_bitacora = conn.execute("SELECT COUNT(*) FROM evento_sincronizacion e WHERE EXISTS "
                                        "(SELECT 1 FROM bitacora_auditoria b WHERE b.evento_id = e.evento_id)").fetchone()[0]
    triggers = {r[0] for r in _rows(conn, "SELECT name FROM sqlite_master WHERE type='trigger'")}
    inmutabilidad = {}
    for table in ("evento_sincronizacion", "movimiento_inventario", "bitacora_auditoria"):
        try:
            conn.execute(f"DELETE FROM {table} WHERE rowid = (SELECT MIN(rowid) FROM {table})")
            inmutabilidad[table] = False
        except sqlite3.DatabaseError:
            inmutabilidad[table] = True
        conn.rollback()
    concurrentes = conn.execute("SELECT COUNT(*) FROM bitacora_auditoria WHERE json_extract(detalles, '$.concurrente') = 1").fetchone()[0]
    conflictos = conn.execute("SELECT COUNT(*) FROM evento_sincronizacion WHERE estado='CONFLICTO'").fetchone()[0]
    acciones = dict(_rows(conn, "SELECT accion, COUNT(*) FROM bitacora_auditoria GROUP BY accion"))
    conn.close()

    # ------------------------------------------------ resiliencia / convergencia
    lotes = [l for n in nodes for l in n.get("lotes", [])]
    fallas = [f for n in nodes for f in n.get("fallas_inyectadas", [])]
    start = min(n["reconexion_inicio"] for n in nodes)
    hashes = {d: node_by_id[d]["snapshot_hash"] for d in DEVICES}
    return {
        "Do": {"exitos": do_ok, "intentos": len(ops), "pct": 100 * do_ok / len(ops) if ops else None,
               "sondas": len(sondas), "sondas_sin_red": sum(s["resultado"] == "SIN_RED" for s in sondas)},
        "Id": {"consistentes": consistent, "transmitidos": len(transmitted), "pct": 100 * consistent / len(transmitted) if transmitted else None,
               "fallas_por_criterio": dict(inconsistencias)},
        "Tr": {"movimientos_trazados": mov_trazados, "movimientos": movimientos, "pct": 100 * mov_trazados / movimientos if movimientos else None,
               "eventos_con_bitacora": eventos_con_bitacora, "eventos_central": eventos_central, "triggers": sorted(triggers),
               "rechazo_delete_append_only": inmutabilidad},
        "saldos": items,
        "duplicidad": {"eventos_central": eventos_central, "eventos_esperados": oracle["eventos_esperados"],
                       "movimientos": movimientos, "movimientos_esperados": oracle["movimientos_esperados"],
                       "eventos_duplicados": eventos_central - oracle["eventos_esperados"],
                       "movimientos_duplicados": movimientos - oracle["movimientos_esperados"]},
        "convergencia": {"hash_central": central_hash, "replicas_convergentes": sum(h == central_hash for h in hashes.values()),
                         "replicas": len(hashes), "tiempo_convergencia_ms": round((max(n["convergencia_fin"] for n in nodes) - start) * 1000, 3),
                         "tiempo_reconexion_push_ms": round((max(n["push_fin"] for n in nodes) - start) * 1000, 3)},
        "crdt": {"actualizaciones_concurrentes_resueltas": concurrentes, "conflictos_inmutables": conflictos, "acciones_bitacora": acciones},
        "resiliencia": {"lotes": len(lotes), "lotes_confirmados": sum(1 for l in lotes if l.get("confirmado_en")),
                        "fallas_inyectadas": len(fallas), "fallas_por_tipo": dict(Counter(f["falla"] for f in fallas)),
                        "reintentos": sum(l["intentos"] - 1 for l in lotes), "duplicados_detectados": sum(l["duplicados"] for l in lotes),
                        "pendientes_finales": sum(n["pendientes_despues_push"] for n in nodes)},
    }
