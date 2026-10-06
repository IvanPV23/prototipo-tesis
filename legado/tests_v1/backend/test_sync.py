from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.app.core.database import Base
from backend.app import models
from backend.app.services.sync_service import apply_event
from shared.schemas import EventoSync

def event(device, amount, state="ACTIVO"):
    return EventoSync(aggregate_id="v1", event_type="VALE_CREADO", device_id=device, vector_clock={device: 1},
      created_at=datetime(2026,1,1,tzinfo=timezone.utc), payload={"id":"v1","codigo":"V1","material":"Arena","cantidad":amount,"estado":state,"actualizado_en":"2026-01-01T00:00:00Z"})
def test_concurrent_cancel_wins_and_event_is_immutable():
    engine=create_engine("sqlite:///:memory:"); Base.metadata.create_all(engine); db=sessionmaker(bind=engine)()
    assert apply_event(db,event("a", 3)) == "applied"
    cancellation = event("b", 3, "CANCELADO")
    assert apply_event(db, cancellation) == "applied"
    assert db.get(models.Vale,"v1").estado == "CANCELADO"
    assert apply_event(db, cancellation) == "duplicate"
