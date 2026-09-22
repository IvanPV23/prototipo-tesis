from datetime import datetime
from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column
from ..core.database import Base
class MovimientoInventario(Base):
    __tablename__ = "movimientos_inventario"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    vale_id: Mapped[str]; delta: Mapped[float]
    # Identidad del componente que produjo el delta: evita reinterpretar una
    # cantidad como snapshot y permite auditar la suma conciliada.
    event_id: Mapped[str] = mapped_column(unique=True, index=True)
    device_id: Mapped[str] = mapped_column(index=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
