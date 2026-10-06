"""Almacén local del nodo de campo (P1): SQLite con transacciones ACID locales.

Cada operación de negocio (estado del vale + saldo del ítem + evento en la cola) se
confirma en **una sola transacción**: no puede quedar un vale sin su evento ni viceversa.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from shared.crdt import counter_value, merge_item_counter, merge_vale, vale_digest
from shared.schemas import EventoSync, ItemData

_VALE_COLUMNS = ("id", "codigo", "tipo", "material", "cantidad", "unidad_medida", "nodo_origen", "estado", "proyecto",
                 "observacion", "field_versions", "version_vector")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class LocalDB:
    def __init__(self, path: str, device_id: str | None = None):
        self.path = path
        self.conn = sqlite3.connect(path, check_same_thread=False, timeout=30)
        self.conn.executescript(Path(__file__).with_name("schema.sql").read_text(encoding="utf-8"))
        if device_id:
            with self.conn:
                self.conn.execute("INSERT OR IGNORE INTO nodo_campo(device_id, estado_conexion) VALUES(?, 'FUERA_DE_LINEA')", (device_id,))

    # ------------------------------------------------------------------ lectura
    def get_vale(self, vale_id: str) -> dict | None:
        row = self.conn.execute(f"SELECT {', '.join(_VALE_COLUMNS)} FROM vales WHERE id=?", (vale_id,)).fetchone()
        if not row:
            return None
        state = dict(zip(_VALE_COLUMNS, row))
        state["field_versions"], state["version_vector"] = json.loads(state["field_versions"]), json.loads(state["version_vector"])
        return state

    def get_item(self, item_id: str) -> dict | None:
        row = self.conn.execute("SELECT item_id, descripcion, unidad_medida, stock_referencia, counter_p, counter_n, stock_actual "
                                "FROM items WHERE item_id=?", (item_id,)).fetchone()
        if not row:
            return None
        return {"id": row[0], "descripcion": row[1], "unidad_medida": row[2], "stock_referencia": row[3],
                "counter_p": json.loads(row[4]), "counter_n": json.loads(row[5]), "stock_actual": row[6]}

    def stocks(self) -> dict[str, float]:
        return {r[0]: round(r[1], 6) for r in self.conn.execute("SELECT item_id, stock_actual FROM items ORDER BY item_id")}

    def vale_ids(self) -> list[str]:
        return [r[0] for r in self.conn.execute("SELECT id FROM vales ORDER BY id")]

    def snapshot(self) -> dict:
        """Estado observable completo, para verificar convergencia entre réplicas."""
        vales = sorted(vale_digest(self.get_vale(vid)) for vid in self.vale_ids())
        return {"vales": vales, "stocks": self.stocks()}

    def has_event(self, event_id: str) -> bool:
        return self.conn.execute("SELECT 1 FROM eventos WHERE event_id=?", (event_id,)).fetchone() is not None

    def pending(self, limit: int | None = None) -> list[EventoSync]:
        sql = ("SELECT event_id, aggregate_id, event_type, payload, vector_clock, device_id, actor_id, created_at FROM eventos "
               "WHERE synced=0 AND origen='LOCAL' ORDER BY rowid")
        rows = self.conn.execute(sql + (f" LIMIT {int(limit)}" if limit else "")).fetchall()
        return [EventoSync(event_id=r[0], aggregate_id=r[1], event_type=r[2], payload=json.loads(r[3]), vector_clock=json.loads(r[4]),
                           device_id=r[5], actor_id=r[6], created_at=r[7]) for r in rows]

    def count_pending(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM eventos WHERE synced=0 AND origen='LOCAL'").fetchone()[0]

    def last_seq(self, device_id: str) -> int:
        row = self.conn.execute("SELECT last_seq FROM nodo_campo WHERE device_id=?", (device_id,)).fetchone()
        return row[0] if row else 0

    # ---------------------------------------------------------------- escritura
    def upsert_catalog(self, items: list[ItemData]) -> None:
        with self.conn:
            for item in items:
                self.conn.execute("INSERT OR IGNORE INTO items(item_id, descripcion, unidad_medida, stock_referencia, stock_actual) "
                                  "VALUES(?,?,?,?,?)", (item.id, item.descripcion, item.unidad_medida, item.stock_referencia,
                                                         item.stock_referencia))

    def apply_state(self, incoming: dict, event: EventoSync, origen: str, synced: bool) -> dict:
        """Join CRDT del vale y del saldo + registro del evento, atómicamente."""
        with self.conn:
            current = self.get_vale(incoming["id"])
            merged = merge_vale(current, incoming)
            item = self.get_item(merged["material"])
            if item is None:
                raise ValueError(f"ítem {merged['material']} no existe en el catálogo local")
            p, n = merge_item_counter(item["counter_p"], item["counter_n"], merged)
            stock = round(item["stock_referencia"] + counter_value(p, n), 6)
            self.conn.execute("UPDATE items SET counter_p=?, counter_n=?, stock_actual=? WHERE item_id=?",
                              (json.dumps(p), json.dumps(n), stock, item["id"]))
            values = [merged[c] for c in _VALE_COLUMNS[:10]] + [json.dumps(merged["field_versions"]),
                                                                 json.dumps(merged["version_vector"]), _now()]
            self.conn.execute(
                "INSERT INTO vales VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET estado=excluded.estado, "
                "proyecto=excluded.proyecto, observacion=excluded.observacion, field_versions=excluded.field_versions, "
                "version_vector=excluded.version_vector, actualizado_en=excluded.actualizado_en", values)
            self._insert_event(event, origen, synced)
        return merged

    def record_event_only(self, event: EventoSync, origen: str, synced: bool) -> None:
        with self.conn:
            self._insert_event(event, origen, synced)

    def _insert_event(self, event: EventoSync, origen: str, synced: bool) -> None:
        self.conn.execute("INSERT OR IGNORE INTO eventos VALUES(?,?,?,?,?,?,?,?,?,?,NULL)",
                          (str(event.event_id), event.aggregate_id, event.event_type, json.dumps(event.payload),
                           json.dumps(event.vector_clock), event.device_id, event.actor_id, event.created_at.isoformat(),
                           origen, int(synced)))

    def mark_synced(self, event_ids: list[str], lote_id: str) -> None:
        with self.conn:
            self.conn.executemany("UPDATE eventos SET synced=1, lote_id=? WHERE event_id=?", [(lote_id, x) for x in event_ids])

    def registrar_sync(self, device_id: str, last_seq: int | None = None, estado: str = "EN_LINEA") -> None:
        with self.conn:
            self.conn.execute("INSERT INTO nodo_campo(device_id, estado_conexion, ultima_sincronizacion, last_seq) VALUES(?,?,?,?) "
                              "ON CONFLICT(device_id) DO UPDATE SET estado_conexion=excluded.estado_conexion, "
                              "ultima_sincronizacion=excluded.ultima_sincronizacion, "
                              "last_seq=MAX(nodo_campo.last_seq, excluded.last_seq)",
                              (device_id, estado, _now(), last_seq or 0))

    def close(self) -> None:
        self.conn.close()
