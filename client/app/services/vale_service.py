from uuid import uuid4
from datetime import datetime
from shared.schemas import EventoSync, ValeData, utcnow
from shared.crdt import counter_value, event_field_versions

class ValeService:
    def __init__(self, db, device_id: str): self.db, self.device_id = db, device_id
    def guardar(self, vale_id: str | None, codigo: str, material: str, cantidad: float, cancelar=False, timestamp: datetime | None = None) -> EventoSync:
        vale_id = vale_id or str(uuid4()); current = self.db.get_vale(vale_id)
        clock = (current[1] if current else {}).copy(); clock[self.device_id] = clock.get(self.device_id, 0) + 1
        timestamp = timestamp or utcnow()
        versions, p, n = self.db.get_crdt(vale_id)
        local = float(p.get(self.device_id, 0)) - float(n.get(self.device_id, 0))
        delta = cantidad - local
        if delta >= 0: p[self.device_id] = p.get(self.device_id, 0) + delta
        else: n[self.device_id] = n.get(self.device_id, 0) + (-delta)
        vale = ValeData(id=vale_id, codigo=codigo, material=material, cantidad=counter_value(p, n), estado="CANCELADO" if cancelar else "ACTIVO", actualizado_en=timestamp)
        kind = "VALE_CANCELADO" if cancelar else ("VALE_MODIFICADO" if current else "VALE_CREADO")
        event_id = uuid4()
        payload = vale.model_dump(mode="json")
        payload["pn_counter"] = {"p": p, "n": n}
        payload["field_versions"] = event_field_versions({}, timestamp.isoformat(), self.device_id, str(event_id))
        event = EventoSync(event_id=event_id, aggregate_id=vale_id, event_type=kind, payload=payload, vector_clock=clock, device_id=self.device_id, created_at=timestamp)
        self.db.save_vale(vale, clock, self.device_id, payload["field_versions"], p, n); self.db.add_event(event)
        return event
