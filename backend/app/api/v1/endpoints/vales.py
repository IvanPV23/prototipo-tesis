from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from shared.schemas import ItemData

from ....core.database import get_db
from ....core.security import Subject, require_read, require_write
from ....models import BitacoraAuditoria, ItemInventario, MovimientoInventario, ValeInventario
from ....services.sync_service import register_item
from ..dependencies import current_subject

router = APIRouter(tags=["inventario"])


@router.post("/items", status_code=status.HTTP_201_CREATED)
def crear_item(item: ItemData, subject: Subject = Depends(current_subject), db: Session = Depends(get_db)):
    """Alta de ítem con stock de referencia (rol logística)."""
    if subject.role != "logistica":
        raise HTTPException(403, "Solo logística registra ítems")
    register_item(db, item)
    return {"id": item.id}


@router.get("/items/{item_id}")
def obtener_item(item_id: str, db: Session = Depends(get_db)):
    """Saldo PN-Counter y verificación de la invariante Σ movimientos = saldo − referencia."""
    item = db.get(ItemInventario, item_id)
    if not item:
        raise HTTPException(404, "Ítem no encontrado")
    suma = db.scalar(select(func.coalesce(func.sum(MovimientoInventario.cantidad_conciliada), 0))
                     .where(MovimientoInventario.item_id == item_id))
    return {"id": item.item_id, "stock_referencia": item.stock_referencia, "stock_actual": item.stock_actual,
            "suma_movimientos": suma, "invariante_ok": round(item.stock_referencia + suma, 6) == round(item.stock_actual, 6)}


@router.get("/vales/{vale_id}")
def obtener_vale(vale_id: str, db: Session = Depends(get_db)):
    vale = db.get(ValeInventario, vale_id)
    if not vale:
        raise HTTPException(404, "Vale no encontrado")
    return vale.state()


@router.get("/vales/{vale_id}/auditoria")
def auditoria(vale_id: str, subject: Subject = Depends(current_subject), db: Session = Depends(get_db)):
    vale = db.get(ValeInventario, vale_id)
    if not vale:
        raise HTTPException(404, "Vale no encontrado")
    require_read(subject, vale.proyecto_id)
    rows = db.scalars(select(BitacoraAuditoria).where(BitacoraAuditoria.vale_id == vale_id).order_by(BitacoraAuditoria.auditoria_id))
    return [{"accion": a.accion, "evento_id": a.evento_id, "movimiento_id": a.movimiento_id, "actor_id": a.actor_id,
             "nodo_id": a.nodo_id, "sello_logico": a.sello_logico, "sello_tiempo": a.sello_tiempo, "detalles": a.detalles} for a in rows]
