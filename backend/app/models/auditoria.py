from datetime import datetime
from sqlalchemy import JSON, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from ..core.database import Base
class Auditoria(Base):
    __tablename__ = "auditoria"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    accion: Mapped[str]; aggregate_id: Mapped[str]
    detalle: Mapped[dict] = mapped_column(JSON)
    device_id: Mapped[str] = mapped_column(index=True)
    movimiento_id: Mapped[int | None] = mapped_column(ForeignKey("movimientos_inventario.id"), nullable=True, index=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
