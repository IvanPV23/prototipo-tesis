from datetime import datetime
from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column
from ..core.database import Base
class MovimientoInventario(Base):
    __tablename__ = "movimientos_inventario"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    vale_id: Mapped[str]; delta: Mapped[float]
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
