import json, sqlite3
from pathlib import Path
from datetime import datetime, timezone
from shared.schemas import EventoSync, ValeData

class LocalDB:
    def __init__(self, path: str):
        self.conn = sqlite3.connect(path, check_same_thread=False)
        schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
        self.conn.executescript(schema)
        # Actualización ligera para bases locales creadas con la versión anterior.
        columns = {row[1] for row in self.conn.execute("PRAGMA table_info(vales)")}
        for name in ("field_versions", "counter_p", "counter_n"):
            if name not in columns:
                self.conn.execute(f"ALTER TABLE vales ADD COLUMN {name} TEXT NOT NULL DEFAULT '{{}}'")
        self.conn.commit()
    def save_vale(self, vale: ValeData, clock: dict[str, int], device_id: str, field_versions=None, counter_p=None, counter_n=None) -> None:
        field_versions, counter_p, counter_n = field_versions or {}, counter_p or {}, counter_n or {}
        self.conn.execute("""INSERT INTO vales VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
          codigo=excluded.codigo,material=excluded.material,cantidad=excluded.cantidad,estado=excluded.estado,
          proyecto=excluded.proyecto,vector_clock=excluded.vector_clock,device_id=excluded.device_id,actualizado_en=excluded.actualizado_en,
          field_versions=excluded.field_versions,counter_p=excluded.counter_p,counter_n=excluded.counter_n""",
          (vale.id, vale.codigo, vale.material, vale.cantidad, vale.estado, vale.proyecto, json.dumps(clock), device_id, vale.actualizado_en.isoformat(), json.dumps(field_versions), json.dumps(counter_p), json.dumps(counter_n)))
        self.conn.commit()
    def get_vale(self, vale_id: str):
        row = self.conn.execute("SELECT id,codigo,material,cantidad,estado,proyecto,vector_clock,device_id,actualizado_en FROM vales WHERE id=?", (vale_id,)).fetchone()
        if not row: return None
        return ValeData(id=row[0], codigo=row[1], material=row[2], cantidad=row[3], estado=row[4], proyecto=row[5], actualizado_en=row[8]), json.loads(row[6]), row[7]
    def get_crdt(self, vale_id: str):
        row = self.conn.execute("SELECT field_versions,counter_p,counter_n FROM vales WHERE id=?", (vale_id,)).fetchone()
        return (json.loads(row[0]), json.loads(row[1]), json.loads(row[2])) if row else ({}, {}, {})
    def add_event(self, event: EventoSync, synced: bool = False) -> None:
        self.conn.execute("INSERT OR IGNORE INTO eventos VALUES(?,?,?,?,?,?,?,?)", (str(event.event_id), event.aggregate_id,
          event.event_type, json.dumps(event.payload, default=str), json.dumps(event.vector_clock), event.device_id, event.created_at.isoformat(), int(synced)))
        self.conn.commit()
    def pending(self) -> list[EventoSync]:
        return self._events("WHERE synced=0")
    def _events(self, clause="") -> list[EventoSync]:
        rows = self.conn.execute("SELECT event_id,aggregate_id,event_type,payload,vector_clock,device_id,created_at FROM eventos " + clause).fetchall()
        return [EventoSync(event_id=r[0],aggregate_id=r[1],event_type=r[2],payload=json.loads(r[3]),vector_clock=json.loads(r[4]),device_id=r[5],created_at=r[6]) for r in rows]
    def mark_synced(self, event_ids: list[str]) -> None:
        self.conn.executemany("UPDATE eventos SET synced=1 WHERE event_id=?", [(x,) for x in event_ids]); self.conn.commit()
    def registrar_sync(self, device_id: str) -> None:
        self.conn.execute("INSERT INTO nodo_campo VALUES(?,?,?) ON CONFLICT(device_id) DO UPDATE SET estado_conexion=excluded.estado_conexion, ultima_sincronizacion=excluded.ultima_sincronizacion", (device_id, "EN_LINEA", datetime.now(timezone.utc).isoformat()))
        self.conn.commit()
