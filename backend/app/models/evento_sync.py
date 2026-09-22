from datetime import datetime
from sqlalchemy import JSON, DateTime, event
from sqlalchemy.orm import Mapped, mapped_column
from ..core.database import Base
class EventoSyncModel(Base):
    __tablename__ = "eventos_sync"
    event_id: Mapped[str] = mapped_column(primary_key=True)
    aggregate_id: Mapped[str] = mapped_column(index=True)
    event_type: Mapped[str]; payload: Mapped[dict] = mapped_column(JSON)
    vector_clock: Mapped[dict] = mapped_column("version_vector", JSON); device_id: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

@event.listens_for(EventoSyncModel, "before_update")
def _prevent_event_update(mapper, connection, target):
    raise ValueError("eventos_sync es append-only: no se permiten UPDATE")

@event.listens_for(EventoSyncModel, "before_delete")
def _prevent_event_delete(mapper, connection, target):
    raise ValueError("eventos_sync es append-only: no se permiten DELETE")
