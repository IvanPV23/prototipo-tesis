from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from shared.schemas import SyncRequest, SyncResponse
from ....core.database import get_db
from ....services.sync_service import apply_event, all_events
from ..dependencies import current_subject
from ....core.security import Subject, require_write
router = APIRouter(prefix="/sync", tags=["sincronización"])
@router.post("/bulk", response_model=SyncResponse)
def bulk_sync(request: SyncRequest, subject: Subject = Depends(current_subject), db: Session = Depends(get_db)):
    result = {"applied": [], "duplicates": [], "conflicts": []}
    for event in request.events:
        require_write(subject, event.payload.get("proyecto", "GENERAL"))
        status = apply_event(db, event)
        result[{"applied":"applied", "duplicate":"duplicates", "conflict":"conflicts"}[status]].append(str(event.event_id))
    db.commit()
    remote = all_events(db)
    return SyncResponse(**result, remote_events=remote)
