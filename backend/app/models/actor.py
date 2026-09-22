from sqlalchemy.orm import Mapped, mapped_column
from ..core.database import Base
class Actor(Base):
    __tablename__ = "actors"
    id: Mapped[str] = mapped_column(primary_key=True)
    nombre: Mapped[str]
    rol: Mapped[str] = mapped_column(default="tecnico")
    proyecto: Mapped[str] = mapped_column(default="GENERAL")
