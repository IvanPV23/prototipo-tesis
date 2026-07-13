from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from shared.schemas import ValeData, EventoSync
from ....core.database import get_db
from ....models.vale import Vale
from ....models.auditoria import Auditoria
from ....services.sync_service import apply_event
from ..dependencies import current_subject
from ....core.security import Subject, require_read, require_write
router = APIRouter(prefix="/vales", tags=["vales"])
@router.get("/{vale_id}")
def obtener_vale(vale_id: str, db: Session = Depends(get_db)):
    vale = db.get(Vale, vale_id)
    if not vale: raise HTTPException(404, "Vale no encontrado")
    return {"id": vale.id, "codigo": vale.codigo, "material": vale.material, "cantidad": vale.cantidad,
      "estado": vale.estado, "proyecto": vale.proyecto, "vector_clock": vale.vector_clock}

@router.post("", status_code=status.HTTP_201_CREATED)
def crear_vale(data: ValeData, subject: Subject = Depends(current_subject), db: Session = Depends(get_db)):
    require_write(subject, data.proyecto)
    event = EventoSync(aggregate_id=data.id, event_type="VALE_CREADO", payload=data.model_dump(mode="json"), vector_clock={subject.actor_id: 1}, device_id=subject.actor_id)
    apply_event(db, event); db.commit()
    return {"id": data.id, "event_id": str(event.event_id)}

@router.get("/inventario/{material}")
def inventario(material: str, proyecto: str = "GENERAL", subject: Subject = Depends(current_subject), db: Session = Depends(get_db)):
    require_read(subject, proyecto)
    total = sum(v.cantidad for v in db.query(Vale).filter_by(material=material, proyecto=proyecto, estado="ACTIVO"))
    return {"material": material, "proyecto": proyecto, "cantidad": total}

@router.get("/auditoria/{vale_id}")
def auditoria(vale_id: str, subject: Subject = Depends(current_subject), db: Session = Depends(get_db)):
    vale = db.get(Vale, vale_id)
    if not vale: raise HTTPException(404, "Vale no encontrado")
    require_read(subject, vale.proyecto)
    return [{"accion": a.accion, "detalle": a.detalle, "creado_en": a.creado_en} for a in db.query(Auditoria).filter_by(aggregate_id=vale_id).all()]
