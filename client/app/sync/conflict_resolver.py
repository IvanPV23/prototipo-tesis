from backend.app.crdt.vector_clock import compare, merge
from shared.schemas import EventoSync, ValeData

def should_apply(incoming: EventoSync, local_clock: dict[str, int], local: ValeData, local_device: str) -> bool:
    relation = compare(local_clock, incoming.vector_clock)
    if relation == "before": return True
    if relation in ("after", "equal"): return False
    if (incoming.payload.get("estado") == "CANCELADO") != (local.estado == "CANCELADO"):
        return incoming.payload.get("estado") == "CANCELADO"
    # Misma semántica replicable del dominio por defecto: conservar la cantidad mayor.
    return float(incoming.payload["cantidad"]) >= local.cantidad

def apply_remote(db, event: EventoSync) -> None:
    current = db.get_vale(event.aggregate_id)
    if current is None:
        db.save_vale(ValeData.model_validate(event.payload), event.vector_clock, event.device_id)
    else:
        vale, clock, device = current
        if should_apply(event, clock, vale, device):
            db.save_vale(ValeData.model_validate(event.payload), merge(clock, event.vector_clock), event.device_id)
    db.add_event(event, synced=True)
