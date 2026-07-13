from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID, uuid4
from pydantic import BaseModel, Field

def utcnow() -> datetime: return datetime.now(timezone.utc)

class ValeData(BaseModel):
    id: str
    codigo: str
    material: str
    cantidad: float = Field(gt=0)
    estado: Literal["ACTIVO", "CANCELADO"] = "ACTIVO"
    proyecto: str = "GENERAL"
    actualizado_en: datetime = Field(default_factory=utcnow)

class EventoSync(BaseModel):
    event_id: UUID = Field(default_factory=uuid4)
    aggregate_id: str
    event_type: Literal["VALE_CREADO", "VALE_MODIFICADO", "VALE_CANCELADO"]
    payload: dict[str, Any]
    vector_clock: dict[str, int]
    device_id: str
    created_at: datetime = Field(default_factory=utcnow)

class SyncRequest(BaseModel):
    device_id: str
    events: list[EventoSync]

class SyncResponse(BaseModel):
    applied: list[str]
    duplicates: list[str]
    conflicts: list[str]
    remote_events: list[EventoSync]
