from datetime import datetime, timezone
from sqlalchemy.orm import Session
from ..models.auditoria import Auditoria
def registrar(db: Session, accion: str, aggregate_id: str, detalle: dict) -> None:
    db.add(Auditoria(accion=accion, aggregate_id=aggregate_id, detalle=detalle, creado_en=datetime.now(timezone.utc)))
