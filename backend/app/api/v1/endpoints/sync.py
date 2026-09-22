from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session
from shared.schemas import SyncRequest, SyncResponse
from ....core.database import get_db
from ....services.sync_service import apply_event, all_events, validate_event_payload
from ....models.nodo_campo import NodoCampo
from ..dependencies import current_subject
from ....core.security import Subject, require_write
router = APIRouter(prefix="/sync", tags=["sincronización"])
@router.post("/bulk", response_model=SyncResponse)
def bulk_sync(request: SyncRequest, subject: Subject = Depends(current_subject), db: Session = Depends(get_db)):
    result = {"applied": [], "duplicates": [], "conflicts": []}
    try:
        validated = [(event, validate_event_payload(event)) for event in request.events]
        for event, data in validated:
            require_write(subject, data.proyecto)
            status = apply_event(db, event, lote_id=str(request.lote_id))
            result[{"applied":"applied", "duplicate":"duplicates", "conflict":"conflicts"}[status]].append(str(event.event_id))
        node = db.query(NodoCampo).filter_by(device_id=request.device_id).one_or_none()
        if node is None:
            db.add(NodoCampo(device_id=request.device_id, estado_conexion="EN_LINEA", ultima_sincronizacion=datetime.now(timezone.utc)))
        else:
            node.estado_conexion, node.ultima_sincronizacion = "EN_LINEA", datetime.now(timezone.utc)
        db.commit()
    except (ValidationError, ValueError) as exc:
        db.rollback()
        raise HTTPException(422, str(exc)) from exc
    except Exception:
        db.rollback()
        raise
    remote = all_events(db)
    return SyncResponse(**result, remote_events=remote, lote_id=request.lote_id, confirmado_en=datetime.now(timezone.utc))
