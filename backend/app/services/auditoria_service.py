from datetime import datetime, timezone
from sqlalchemy.orm import Session
from ..models.auditoria import Auditoria
def registrar(db: Session, accion: str, aggregate_id: str, detalle: dict, device_id: str, movimiento_id: int | None = None) -> None:
    db.add(Auditoria(accion=accion, aggregate_id=aggregate_id, detalle=detalle, device_id=device_id, movimiento_id=movimiento_id, creado_en=datetime.now(timezone.utc)))
