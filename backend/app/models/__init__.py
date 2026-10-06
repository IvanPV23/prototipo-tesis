"""Modelo de información central (tesis, Figura 7: vista de información)."""
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, event
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base


class Actor(Base):
    __tablename__ = "actor"
    actor_id: Mapped[str] = mapped_column(String, primary_key=True)
    nombre: Mapped[str]
    rol: Mapped[str] = mapped_column(default="tecnico")
    email: Mapped[str | None] = mapped_column(nullable=True)
    atributos_abac: Mapped[dict] = mapped_column(JSON, default=dict)
    estado_activo: Mapped[bool] = mapped_column(default=True)


class NodoCampo(Base):
    __tablename__ = "nodo_campo"
    nodo_id: Mapped[str] = mapped_column(String, primary_key=True)
    nombre: Mapped[str | None] = mapped_column(nullable=True)
    ubicacion: Mapped[str | None] = mapped_column(nullable=True)
    estado_conexion: Mapped[str] = mapped_column(default="EN_LINEA")
    ultima_sincronizacion: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ItemInventario(Base):
    """Saldo del ítem como PN-Counter (componentes indexados por movimiento)."""
    __tablename__ = "item_inventario"
    item_id: Mapped[str] = mapped_column(String, primary_key=True)
    descripcion: Mapped[str]
    unidad_medida: Mapped[str] = mapped_column(default="UND")
    stock_referencia: Mapped[float] = mapped_column(Float, default=0)
    counter_p: Mapped[dict] = mapped_column(JSON, default=dict)
    counter_n: Mapped[dict] = mapped_column(JSON, default=dict)
    stock_actual: Mapped[float] = mapped_column(Float, default=0)


class ValeInventario(Base):
    __tablename__ = "vale_inventario"
    vale_id: Mapped[str] = mapped_column(String, primary_key=True)
    codigo: Mapped[str]
    tipo: Mapped[str]  # SALIDA | INGRESO
    item_id: Mapped[str] = mapped_column(ForeignKey("item_inventario.item_id"), index=True)
    cantidad: Mapped[float] = mapped_column(Float)
    unidad_medida: Mapped[str]
    proyecto_id: Mapped[str]
    estado: Mapped[str]  # ACTIVO | ANULADO
    observacion: Mapped[str] = mapped_column(default="")
    nodo_origen_id: Mapped[str] = mapped_column(index=True)
    field_versions: Mapped[dict] = mapped_column(JSON)
    version_vector: Mapped[dict] = mapped_column(JSON)
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    def state(self) -> dict:
        return {"id": self.vale_id, "codigo": self.codigo, "tipo": self.tipo, "material": self.item_id,
                "cantidad": self.cantidad, "unidad_medida": self.unidad_medida, "nodo_origen": self.nodo_origen_id,
                "estado": self.estado, "proyecto": self.proyecto_id, "observacion": self.observacion,
                "field_versions": self.field_versions, "version_vector": self.version_vector}


class EventoSincronizacion(Base):
    """Registro append-only de cada operación transmitida (Event Sourcing, P3)."""
    __tablename__ = "evento_sincronizacion"
    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    evento_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    vale_id: Mapped[str] = mapped_column(index=True)
    tipo_evento: Mapped[str]
    nodo_origen_id: Mapped[str] = mapped_column(index=True)
    actor_id: Mapped[str]
    sello_tiempo_logico: Mapped[int]
    estado: Mapped[str]  # APLICADO | CONFLICTO
    payload: Mapped[dict] = mapped_column(JSON)
    version_vector: Mapped[dict] = mapped_column(JSON)
    lote_id: Mapped[str | None] = mapped_column(index=True, nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    recibido_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class MovimientoInventario(Base):
    """Cambio conciliado del saldo de un ítem; su suma reconstruye el saldo (invariante 4.3)."""
    __tablename__ = "movimiento_inventario"
    movimiento_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vale_id: Mapped[str] = mapped_column(index=True)
    item_id: Mapped[str] = mapped_column(ForeignKey("item_inventario.item_id"), index=True)
    evento_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    cantidad_conciliada: Mapped[float] = mapped_column(Float)
    unidad_medida: Mapped[str]
    proyecto_id: Mapped[str]
    estado: Mapped[str]  # CONCILIADO | COMPENSACION
    saldo_resultante: Mapped[float] = mapped_column(Float)
    version_vector: Mapped[dict] = mapped_column(JSON)
    fecha_conciliacion: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class BitacoraAuditoria(Base):
    __tablename__ = "bitacora_auditoria"
    auditoria_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    movimiento_id: Mapped[int | None] = mapped_column(ForeignKey("movimiento_inventario.movimiento_id"), nullable=True, index=True)
    evento_id: Mapped[str] = mapped_column(index=True)
    vale_id: Mapped[str] = mapped_column(index=True)
    actor_id: Mapped[str]
    nodo_id: Mapped[str]
    accion: Mapped[str]  # CREACION | CONCILIACION | CORRECCION | ANULACION | CONFLICTO
    sello_tiempo: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sello_logico: Mapped[int]
    detalles: Mapped[dict] = mapped_column(JSON)


APPEND_ONLY = (EventoSincronizacion, MovimientoInventario, BitacoraAuditoria)


def _forbid(operation: str):
    def listener(mapper, connection, target):
        raise ValueError(f"{target.__tablename__} es append-only: no se permite {operation}")
    return listener


for _model in APPEND_ONLY:
    event.listen(_model, "before_update", _forbid("UPDATE"))
    event.listen(_model, "before_delete", _forbid("DELETE"))
