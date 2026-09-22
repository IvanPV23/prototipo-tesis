from datetime import datetime
from sqlalchemy import JSON, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from ..core.database import Base
class Vale(Base):
    __tablename__ = "vales"
    id: Mapped[str] = mapped_column(primary_key=True)
    codigo: Mapped[str]; material: Mapped[str]; cantidad: Mapped[float]; estado: Mapped[str]
    proyecto: Mapped[str] = mapped_column(default="GENERAL")
    vector_clock: Mapped[dict] = mapped_column("version_vector", JSON, default=dict)
    field_versions: Mapped[dict] = mapped_column(JSON, default=dict)
    counter_p: Mapped[dict] = mapped_column(JSON, default=dict)
    counter_n: Mapped[dict] = mapped_column(JSON, default=dict)
    device_id: Mapped[str]
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
