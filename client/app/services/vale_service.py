"""Operaciones de negocio del técnico de campo. Funcionan sin red (P1).

Los hechos físicos del vale (tipo, ítem, cantidad, unidad) son inmutables: una cantidad
mal registrada se corrige anulando el vale y registrando uno nuevo, de modo que el
histórico nunca se sobrescribe (objetivo de diseño c, P3/P6).
"""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from shared.crdt import LWW_FIELDS, field_version
from shared.schemas import EventoSync, ValeState, utcnow


class ValeService:
    def __init__(self, db, device_id: str, actor_id: str | None = None):
        self.db, self.device_id, self.actor_id = db, device_id, actor_id or device_id

    def _emit(self, event_type: str, state: dict, changed: tuple[str, ...], timestamp: datetime | None) -> EventoSync:
        event_id = uuid4()
        clock = dict(state.get("version_vector") or {})
        clock[self.device_id] = clock.get(self.device_id, 0) + 1
        state = dict(state, version_vector=clock, field_versions={f: list(v) for f, v in (state.get("field_versions") or {}).items()})
        for field in changed:
            state["field_versions"][field] = field_version(clock, self.device_id, str(event_id))
        payload = ValeState.model_validate(state).model_dump(mode="json")
        event = EventoSync(event_id=event_id, aggregate_id=payload["id"], event_type=event_type, payload=payload, vector_clock=clock,
                           device_id=self.device_id, actor_id=self.actor_id, created_at=timestamp or utcnow())
        self.db.apply_state(payload, event, origen="LOCAL", synced=False)
        return event

    def registrar(self, tipo: str, material: str, cantidad: float, proyecto: str = "GENERAL", observacion: str = "",
                  vale_id: str | None = None, codigo: str | None = None, unidad_medida: str | None = None,
                  timestamp: datetime | None = None) -> EventoSync:
        item = self.db.get_item(material)
        if item is None:
            raise ValueError(f"ítem {material} no existe en el catálogo local")
        vale_id = vale_id or str(uuid4())
        if self.db.get_vale(vale_id):
            raise ValueError(f"el vale {vale_id} ya existe; los hechos físicos no se sobrescriben")
        state = {"id": vale_id, "codigo": codigo or vale_id, "tipo": tipo, "material": material, "cantidad": cantidad,
                 "unidad_medida": unidad_medida or item["unidad_medida"], "nodo_origen": self.device_id, "estado": "ACTIVO",
                 "proyecto": proyecto, "observacion": observacion, "field_versions": {}, "version_vector": {}}
        return self._emit("VALE_REGISTRADO", state, LWW_FIELDS, timestamp)

    def _existing(self, vale_id: str) -> dict:
        state = self.db.get_vale(vale_id)
        if state is None:
            raise ValueError(f"vale {vale_id} desconocido en esta réplica")
        return state

    def anular(self, vale_id: str, timestamp: datetime | None = None) -> EventoSync:
        state = self._existing(vale_id)
        return self._emit("VALE_ANULADO", dict(state, estado="ANULADO"), (), timestamp)

    def reasignar_proyecto(self, vale_id: str, proyecto: str, timestamp: datetime | None = None) -> EventoSync:
        state = self._existing(vale_id)
        return self._emit("VALE_REASIGNADO", dict(state, proyecto=proyecto), ("proyecto",), timestamp)

    def observar(self, vale_id: str, observacion: str, timestamp: datetime | None = None) -> EventoSync:
        state = self._existing(vale_id)
        return self._emit("VALE_OBSERVADO", dict(state, observacion=observacion), ("observacion",), timestamp)
