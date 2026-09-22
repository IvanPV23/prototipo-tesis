from datetime import datetime
from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column
from ..core.database import Base


class NodoCampo(Base):
    __tablename__ = "nodos_campo"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(unique=True, index=True)
    estado_conexion: Mapped[str] = mapped_column(default="EN_LINEA")
    ultima_sincronizacion: Mapped[datetime] = mapped_column(DateTime(timezone=True))
