from collections import defaultdict
from threading import Lock
from sqlalchemy.orm import Session
from shared.crdt import as_utc, counter_value, event_counter, event_field_versions, merge_clock, merge_component_maps, merge_fields
from shared.schemas import EventoSync, ValeData
from ..models.evento_sync import EventoSyncModel
from ..models.vale import Vale
from .auditoria_service import registrar
from .inventario_service import registrar_movimiento
from shared.structured_log import append_jsonl
from shared.schemas import utcnow
import os

_aggregate_locks: defaultdict[str, Lock] = defaultdict(Lock)
_locks_guard = Lock()

def _lock_for(aggregate_id: str) -> Lock:
    """Cierra la carrera lectura-decisión-escritura en el proceso SQLite."""
    with _locks_guard:
        return _aggregate_locks[aggregate_id]

def validate_event_payload(event: EventoSync) -> ValeData:
    data = ValeData.model_validate(event.payload)
    if data.id != event.aggregate_id:
        raise ValueError("payload.id debe coincidir con aggregate_id")
    return data

def _log_event(lote_id: str | None, event: EventoSync, result: str) -> None:
    append_jsonl(os.getenv("SERVER_SYNC_LOG", "outputs/plan/server-events.jsonl"), {"lote_id": lote_id, "event_id": str(event.event_id), "aggregate_id": event.aggregate_id, "device_id": event.device_id, "resultado": result, "timestamp_recibido": utcnow(), "timestamp_confirmado": utcnow(), "version_vector": event.vector_clock})

def apply_event(db: Session, event: EventoSync, commit: bool = True, lote_id: str | None = None) -> str:
    """Join CRDT: clocks, PN-counter y registros LWW por campo."""
    data = validate_event_payload(event)  # antes de tocar la sesión
    with _lock_for(event.aggregate_id):
        if db.get(EventoSyncModel, str(event.event_id)):
            _log_event(lote_id, event, "duplicate")
            return "duplicate"
        db.add(EventoSyncModel(event_id=str(event.event_id), aggregate_id=event.aggregate_id, event_type=event.event_type,
          payload=event.payload, vector_clock=event.vector_clock, device_id=event.device_id, created_at=event.created_at))
        current = db.get(Vale, event.aggregate_id)
        versions = event_field_versions(event.payload, event.created_at.isoformat(), event.device_id, str(event.event_id))
        incoming_p, incoming_n = event_counter(event.payload, event.device_id, data.cantidad)
        if current is None:
            fields, field_versions = merge_fields({}, {}, data.model_dump(mode="json"), versions)
            quantity = counter_value(incoming_p, incoming_n)
            db.add(Vale(id=data.id, cantidad=quantity, vector_clock=event.vector_clock, field_versions=field_versions,
              counter_p=incoming_p, counter_n=incoming_n, device_id=event.device_id, actualizado_en=data.actualizado_en, **fields))
            movement = registrar_movimiento(db, data.id, quantity, str(event.event_id), event.device_id)
            registrar(db, "EVENTO_APLICADO", data.id, {"event_id": str(event.event_id), "type": event.event_type}, event.device_id, movement.id)
            if commit:
                db.commit()
            else:
                db.flush()
            _log_event(lote_id, event, "applied")
            return "applied"
        old_quantity = current.cantidad
        fields, field_versions = merge_fields({key: getattr(current, key) for key in ("codigo", "material", "proyecto", "estado")},
          current.field_versions or {}, data.model_dump(mode="json"), versions)
        p = merge_component_maps(current.counter_p or {}, incoming_p)
        n = merge_component_maps(current.counter_n or {}, incoming_n)
        current.codigo, current.material, current.proyecto, current.estado = fields["codigo"], fields["material"], fields["proyecto"], fields["estado"]
        current.field_versions, current.counter_p, current.counter_n = field_versions, p, n
        current.cantidad, current.vector_clock = counter_value(p, n), merge_clock(current.vector_clock, event.vector_clock)
        current.device_id, current.actualizado_en = event.device_id, max(as_utc(current.actualizado_en), as_utc(data.actualizado_en))
        movement = registrar_movimiento(db, data.id, current.cantidad - old_quantity, str(event.event_id), event.device_id)
        registrar(db, "EVENTO_FUSIONADO", data.id, {"event_id": str(event.event_id), "type": event.event_type}, event.device_id, movement.id)
        # El commit ocurre aún bajo el lock: otro hilo no puede leer una versión
        # previa mientras esta decisión queda sin publicar en SQLite.
        if commit:
            db.commit()
        else:
            db.flush()
        _log_event(lote_id, event, "applied")
        return "applied"

def all_events(db: Session) -> list[EventoSync]:
    rows = db.query(EventoSyncModel).order_by(EventoSyncModel.created_at).all()
    return [EventoSync(event_id=r.event_id, aggregate_id=r.aggregate_id, event_type=r.event_type, payload=r.payload,
      vector_clock=r.vector_clock, device_id=r.device_id, created_at=r.created_at) for r in rows]
