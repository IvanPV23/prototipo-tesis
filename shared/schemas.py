"""Contratos REST compartidos entre la capa de campo y la capa central (P5/P7)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator

from .crdt import LWW_FIELDS


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


TipoVale = Literal["SALIDA", "INGRESO"]
EstadoVale = Literal["ACTIVO", "ANULADO"]
EventType = Literal["VALE_REGISTRADO", "VALE_ANULADO", "VALE_REASIGNADO", "VALE_OBSERVADO"]


class ValeState(BaseModel):
    """Estado CRDT completo de un vale; viaja como payload de cada evento (state-based)."""
    id: str
    codigo: str
    tipo: TipoVale
    material: str
    cantidad: float = Field(gt=0)
    unidad_medida: str = "UND"
    nodo_origen: str
    estado: EstadoVale = "ACTIVO"
    proyecto: str = "GENERAL"
    observacion: str = ""
    field_versions: dict[str, list[Any]]
    version_vector: dict[str, int]

    @model_validator(mode="after")
    def _versions_complete(self):
        missing = [f for f in LWW_FIELDS if f not in self.field_versions]
        if missing:
            raise ValueError(f"field_versions incompleto: faltan {missing}")
        return self


class EventoSync(BaseModel):
    event_id: UUID = Field(default_factory=uuid4)
    aggregate_id: str
    event_type: EventType
    payload: dict[str, Any]
    vector_clock: dict[str, int]
    device_id: str
    actor_id: str = "SIMULADOR"
    created_at: datetime = Field(default_factory=utcnow)


class EventoRemoto(EventoSync):
    seq: int
    estado: str


class SyncRequest(BaseModel):
    device_id: str
    events: list[EventoSync]
    lote_id: UUID = Field(default_factory=uuid4)
    enviado_en: datetime = Field(default_factory=utcnow)


class SyncResponse(BaseModel):
    lote_id: UUID
    applied: list[str]
    duplicates: list[str]
    conflicts: list[str]
    recibido_en: datetime
    confirmado_en: datetime
    duracion_servidor_ms: float
    espera_cola_ms: float = 0
    conciliacion_ms: float = 0


class ItemData(BaseModel):
    id: str
    descripcion: str
    unidad_medida: str = "UND"
    stock_referencia: float = 0


class ChangesResponse(BaseModel):
    events: list[EventoRemoto]
    last_seq: int
    items: list[ItemData]
