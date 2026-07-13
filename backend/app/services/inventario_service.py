from datetime import datetime, timezone
from sqlalchemy.orm import Session
from ..models.movimiento_inventario import MovimientoInventario
RULE = "mayor_cantidad"

def set_resolution_rule(rule: str) -> None:
    """Configura la regla de dominio sin cambiar el motor de sincronización."""
    global RULE
    if rule not in {"mayor_cantidad", "menor_cantidad"}: raise ValueError("Regla no soportada")
    RULE = rule

def incoming_wins(current_amount: float, incoming_amount: float) -> bool:
    return incoming_amount >= current_amount if RULE == "mayor_cantidad" else incoming_amount <= current_amount

def registrar_movimiento(db: Session, vale_id: str, delta: float) -> None:
    db.add(MovimientoInventario(vale_id=vale_id, delta=delta, creado_en=datetime.now(timezone.utc)))
