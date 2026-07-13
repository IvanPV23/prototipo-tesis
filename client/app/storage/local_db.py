import json, sqlite3
from pathlib import Path
from shared.schemas import EventoSync, ValeData

class LocalDB:
    def __init__(self, path: str):
        self.conn = sqlite3.connect(path)
        schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
        self.conn.executescript(schema); self.conn.commit()
    def save_vale(self, vale: ValeData, clock: dict[str, int], device_id: str) -> None:
        self.conn.execute("""INSERT INTO vales VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
          codigo=excluded.codigo,material=excluded.material,cantidad=excluded.cantidad,estado=excluded.estado,
          proyecto=excluded.proyecto,vector_clock=excluded.vector_clock,device_id=excluded.device_id,actualizado_en=excluded.actualizado_en""",
          (vale.id, vale.codigo, vale.material, vale.cantidad, vale.estado, vale.proyecto, json.dumps(clock), device_id, vale.actualizado_en.isoformat()))
        self.conn.commit()
    def get_vale(self, vale_id: str):
        row = self.conn.execute("SELECT id,codigo,material,cantidad,estado,proyecto,vector_clock,device_id,actualizado_en FROM vales WHERE id=?", (vale_id,)).fetchone()
        if not row: return None
        return ValeData(id=row[0], codigo=row[1], material=row[2], cantidad=row[3], estado=row[4], proyecto=row[5], actualizado_en=row[8]), json.loads(row[6]), row[7]
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
