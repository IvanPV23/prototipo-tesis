from datetime import datetime
from sqlalchemy import JSON, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from ..core.database import Base
class Auditoria(Base):
    __tablename__ = "auditoria"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    accion: Mapped[str]; aggregate_id: Mapped[str]
    detalle: Mapped[dict] = mapped_column(JSON)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
