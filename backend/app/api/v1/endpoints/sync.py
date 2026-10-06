from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import ValidationError
from sqlalchemy.orm import Session

from shared.schemas import ChangesResponse, SyncRequest, SyncResponse

from ....core.database import get_db
from ....core.security import READ_ROLES, Subject, require_write
from ....services.sync_service import LoteInvalido, catalog, changes_since, process_lote
from ..dependencies import current_subject

router = APIRouter(prefix="/sync", tags=["sincronización"])


@router.post("/bulk", response_model=SyncResponse)
def bulk_sync(request: SyncRequest, subject: Subject = Depends(current_subject), db: Session = Depends(get_db)):
    """Push de un lote de eventos pendientes (idempotente por evento_id, atómico por lote)."""
    try:
        return process_lote(db, request, authorize=lambda project: require_write(subject, project))
    except (ValidationError, LoteInvalido) as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/changes", response_model=ChangesResponse)
def pull_changes(since: int = Query(0, ge=0), limit: int = Query(5000, ge=1, le=20000),
                 subject: Subject = Depends(current_subject), db: Session = Depends(get_db)):
    """Pull incremental: eventos con secuencia central mayor que ``since``."""
    if subject.role not in READ_ROLES:
        raise HTTPException(403, "Acceso denegado: lectura no autorizada")
    events, last_seq = changes_since(db, since, limit)
    return ChangesResponse(events=events, last_seq=last_seq, items=catalog(db))
