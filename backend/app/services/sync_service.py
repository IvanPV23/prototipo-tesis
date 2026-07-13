from sqlalchemy.orm import Session
from shared.schemas import EventoSync, ValeData
from ..crdt.vector_clock import compare, merge
from ..models.evento_sync import EventoSyncModel
from ..models.vale import Vale
from .auditoria_service import registrar
from .inventario_service import registrar_movimiento, incoming_wins


def _is_stock_reduction(event: EventoSync, current: Vale) -> bool:
    try:
        current_amount = float(current.cantidad)
        incoming_amount = float(event.payload.get("cantidad", current_amount))
    except (TypeError, ValueError):
        return False
    return current_amount > 0 and incoming_amount >= 0 and incoming_amount < current_amount


def _wins(event: EventoSync, current: Vale) -> bool:
    relation = compare(current.vector_clock, event.vector_clock)
    if relation == "before": return True
    if relation in ("after", "equal"): return False
    # Política semántica explícita: cancelar prevalece; después LWW determinista.
    cancelled = event.payload.get("estado") == "CANCELADO"
    if cancelled != (current.estado == "CANCELADO"): return cancelled
    # Las reducciones concurrentes dentro del stock no representan un conflicto semántico.
    if _is_stock_reduction(event, current):
        return True
    # La política de inventario es intercambiable y no pertenece al transporte/sincronización.
    return incoming_wins(current.cantidad, float(event.payload["cantidad"]))

def apply_event(db: Session, event: EventoSync) -> str:
    if db.get(EventoSyncModel, str(event.event_id)): return "duplicate"
    db.add(EventoSyncModel(event_id=str(event.event_id), aggregate_id=event.aggregate_id, event_type=event.event_type,
        payload=event.payload, vector_clock=event.vector_clock, device_id=event.device_id, created_at=event.created_at))
    current = db.get(Vale, event.aggregate_id)
    if current is not None and not _wins(event, current):
        registrar(db, "CONFLICTO_RESUELTO", event.aggregate_id, {"event_id": str(event.event_id)})
        return "conflict"
    data, previous = ValeData.model_validate(event.payload), (current.cantidad if current else 0)
    if current is None:
        db.add(Vale(id=data.id, codigo=data.codigo, material=data.material, cantidad=data.cantidad, estado=data.estado, proyecto=data.proyecto,
          vector_clock=event.vector_clock, device_id=event.device_id, actualizado_en=data.actualizado_en))
    else:
        current.codigo, current.material, current.cantidad, current.estado, current.proyecto = data.codigo, data.material, data.cantidad, data.estado, data.proyecto
        current.vector_clock, current.device_id, current.actualizado_en = merge(current.vector_clock, event.vector_clock), event.device_id, data.actualizado_en
    registrar_movimiento(db, data.id, data.cantidad - previous)
    registrar(db, "EVENTO_APLICADO", data.id, {"event_id": str(event.event_id), "type": event.event_type})
    return "applied"

def all_events(db: Session) -> list[EventoSync]:
    rows = db.query(EventoSyncModel).order_by(EventoSyncModel.created_at).all()
    return [EventoSync(event_id=r.event_id, aggregate_id=r.aggregate_id, event_type=r.event_type, payload=r.payload,
      vector_clock=r.vector_clock, device_id=r.device_id, created_at=r.created_at) for r in rows]
