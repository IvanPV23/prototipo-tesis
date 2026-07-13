from uuid import uuid4
from datetime import datetime
from shared.schemas import EventoSync, ValeData, utcnow

class ValeService:
    def __init__(self, db, device_id: str): self.db, self.device_id = db, device_id
    def guardar(self, vale_id: str | None, codigo: str, material: str, cantidad: float, cancelar=False, timestamp: datetime | None = None) -> EventoSync:
        vale_id = vale_id or str(uuid4()); current = self.db.get_vale(vale_id)
        clock = (current[1] if current else {}).copy(); clock[self.device_id] = clock.get(self.device_id, 0) + 1
        timestamp = timestamp or utcnow()
        vale = ValeData(id=vale_id, codigo=codigo, material=material, cantidad=cantidad, estado="CANCELADO" if cancelar else "ACTIVO", actualizado_en=timestamp)
        kind = "VALE_CANCELADO" if cancelar else ("VALE_MODIFICADO" if current else "VALE_CREADO")
        event = EventoSync(aggregate_id=vale_id, event_type=kind, payload=vale.model_dump(mode="json"), vector_clock=clock, device_id=self.device_id, created_at=timestamp)
        self.db.save_vale(vale, clock, self.device_id); self.db.add_event(event)
        return event
