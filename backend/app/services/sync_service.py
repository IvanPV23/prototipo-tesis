"""Servicio de conciliación central (capa de sincronización + capa central).

Cada lote se procesa como **una única transacción ACID local** (BASE entre nodos, ACID
dentro del nodo central): o se concilian todos sus eventos o ninguno. Un corte de red a
mitad de la transmisión no deja lotes parciales y el reintento del mismo lote es
idempotente porque cada evento se identifica por su ``evento_id``.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from threading import Lock
from time import perf_counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.crdt import (ImmutableFieldConflict, compare, counter_value, lamport, merge_item_counter, merge_vale,
                         vale_contribution)
from shared.schemas import EventoRemoto, EventoSync, ItemData, SyncRequest, SyncResponse, ValeState
from shared.structured_log import append_jsonl

from ..models import (BitacoraAuditoria, EventoSincronizacion, ItemInventario, MovimientoInventario, NodoCampo,
                      ValeInventario)

# SQLite admite un único escritor: serializar la lectura-join-escritura del lote completo evita
# lecturas obsoletas entre hilos de uvicorn. En despliegues multi-proceso este lock se sustituye
# por PostgreSQL con SELECT ... FOR UPDATE sobre item/vale.
_writer_lock = Lock()


class LoteInvalido(ValueError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def validate_event(event: EventoSync) -> ValeState:
    state = ValeState.model_validate(event.payload)
    if state.id != event.aggregate_id:
        raise LoteInvalido("payload.id debe coincidir con aggregate_id")
    if state.version_vector != event.vector_clock:
        raise LoteInvalido("payload.version_vector debe coincidir con vector_clock del evento")
    return state


def _accion(event: EventoSync, before: dict | None, after: dict, delta: float) -> str:
    if before is None:
        return "CREACION"
    if before["estado"] != after["estado"]:
        return "ANULACION"
    if delta == 0 and event.event_type in ("VALE_REASIGNADO", "VALE_OBSERVADO"):
        return "CORRECCION"
    return "CONCILIACION"


def apply_event(db: Session, event: EventoSync, lote_id: str | None = None, recibido_en: datetime | None = None) -> str:
    """Aplica un evento dentro de la transacción en curso. Devuelve applied|duplicate|conflict."""
    incoming = validate_event(event).model_dump(mode="json")
    event_id = str(event.event_id)
    if db.scalar(select(EventoSincronizacion.seq).where(EventoSincronizacion.evento_id == event_id)) is not None:
        return "duplicate"
    item = db.get(ItemInventario, incoming["material"])
    if item is None:
        raise LoteInvalido(f"ítem desconocido: {incoming['material']}")
    recibido_en = recibido_en or _now()
    vale = db.get(ValeInventario, event.aggregate_id)
    before = vale.state() if vale else None
    sello = lamport(event.vector_clock)
    relation = compare(before["version_vector"], event.vector_clock) if before else "after"

    def record_event(estado: str) -> None:
        db.add(EventoSincronizacion(evento_id=event_id, vale_id=event.aggregate_id, tipo_evento=event.event_type,
                                    nodo_origen_id=event.device_id, actor_id=event.actor_id, sello_tiempo_logico=sello,
                                    estado=estado, payload=event.payload, version_vector=event.vector_clock,
                                    lote_id=lote_id, creado_en=event.created_at, recibido_en=recibido_en))

    try:
        after = merge_vale(before, incoming)
    except ImmutableFieldConflict as exc:
        record_event("CONFLICTO")
        db.add(BitacoraAuditoria(evento_id=event_id, vale_id=event.aggregate_id, actor_id=event.actor_id,
                                 nodo_id=event.device_id, accion="CONFLICTO", sello_tiempo=recibido_en, sello_logico=sello,
                                 detalles={"motivo": str(exc), "relacion_causal": relation}))
        db.flush()
        return "conflict"

    old_stock = item.stock_actual
    delta = round(vale_contribution(after) - vale_contribution(before), 6)
    p, n = merge_item_counter(item.counter_p, item.counter_n, after)
    item.counter_p, item.counter_n = p, n
    item.stock_actual = round(item.stock_referencia + counter_value(p, n), 6)
    if round(item.stock_actual - old_stock, 6) != delta:  # invariante 4.3 por construcción
        raise AssertionError(f"PN-Counter y movimiento divergen en {item.item_id}: {item.stock_actual - old_stock} != {delta}")

    if vale is None:
        vale = ValeInventario(vale_id=after["id"], codigo=after["codigo"], tipo=after["tipo"], item_id=after["material"],
                              cantidad=after["cantidad"], unidad_medida=after["unidad_medida"], nodo_origen_id=after["nodo_origen"],
                              fecha_creacion=event.created_at, proyecto_id=after["proyecto"], estado=after["estado"],
                              observacion=after["observacion"], field_versions=after["field_versions"],
                              version_vector=after["version_vector"], actualizado_en=recibido_en)
        db.add(vale)
    else:
        vale.estado, vale.proyecto_id, vale.observacion = after["estado"], after["proyecto"], after["observacion"]
        vale.field_versions, vale.version_vector, vale.actualizado_en = after["field_versions"], after["version_vector"], recibido_en
    record_event("APLICADO")

    movimiento_id = None
    if delta != 0:
        movement = MovimientoInventario(vale_id=after["id"], item_id=item.item_id, evento_id=event_id, cantidad_conciliada=delta,
                                        unidad_medida=after["unidad_medida"], proyecto_id=after["proyecto"],
                                        estado="COMPENSACION" if after["estado"] == "ANULADO" else "CONCILIADO",
                                        saldo_resultante=item.stock_actual, version_vector=after["version_vector"],
                                        fecha_conciliacion=recibido_en)
        db.add(movement)
        db.flush()
        movimiento_id = movement.movimiento_id
    db.add(BitacoraAuditoria(movimiento_id=movimiento_id, evento_id=event_id, vale_id=after["id"], actor_id=event.actor_id,
                             nodo_id=event.device_id, accion=_accion(event, before, after, delta), sello_tiempo=recibido_en,
                             sello_logico=sello, detalles={"tipo_evento": event.event_type, "relacion_causal": relation,
                                                           "concurrente": relation == "concurrent", "delta": delta,
                                                           "estado": after["estado"], "proyecto": after["proyecto"]}))
    db.flush()  # el siguiente evento del mismo lote ve este estado (identity map + unicidad de evento_id)
    return "applied"


def process_lote(db: Session, request: SyncRequest, authorize=None) -> SyncResponse:
    """Concilia un lote completo en una sola transacción."""
    started, recibido_en = perf_counter(), _now()
    states = [validate_event(event) for event in request.events]  # falla antes de tocar la BD
    if authorize:
        for state in states:
            authorize(state.proyecto)
    result = {"applied": [], "duplicate": [], "conflict": []}
    waiting = perf_counter()
    with _writer_lock:
        locked = perf_counter()
        try:
            for event in request.events:
                status = apply_event(db, event, str(request.lote_id), recibido_en)
                result[status].append(str(event.event_id))
            node = db.get(NodoCampo, request.device_id)
            if node is None:
                db.add(NodoCampo(nodo_id=request.device_id, estado_conexion="EN_LINEA", ultima_sincronizacion=recibido_en))
            else:
                node.estado_conexion, node.ultima_sincronizacion = "EN_LINEA", recibido_en
            db.commit()
        except Exception:
            db.rollback()
            raise
        committed = perf_counter()
    confirmado_en = _now()
    duration = round((committed - started) * 1000, 3)
    tiempos = {"espera_cola_ms": round((locked - waiting) * 1000, 3), "conciliacion_ms": round((committed - locked) * 1000, 3)}
    log_path = os.getenv("SERVER_SYNC_LOG")
    if log_path:
        append_jsonl(log_path, {"lote_id": str(request.lote_id), "device_id": request.device_id, "n_eventos": len(request.events),
                                "aplicados": len(result["applied"]), "duplicados": len(result["duplicate"]),
                                "conflictos": len(result["conflict"]), "recibido_en": recibido_en, "confirmado_en": confirmado_en,
                                "duracion_servidor_ms": duration, **tiempos})
    return SyncResponse(lote_id=request.lote_id, applied=result["applied"], duplicates=result["duplicate"],
                        conflicts=result["conflict"], recibido_en=recibido_en, confirmado_en=confirmado_en,
                        duracion_servidor_ms=duration, **tiempos)


def changes_since(db: Session, since: int, limit: int = 5000) -> tuple[list[EventoRemoto], int]:
    rows = db.scalars(select(EventoSincronizacion).where(EventoSincronizacion.seq > since)
                      .order_by(EventoSincronizacion.seq).limit(limit)).all()
    events = [EventoRemoto(seq=r.seq, estado=r.estado, event_id=r.evento_id, aggregate_id=r.vale_id, event_type=r.tipo_evento,
                           payload=r.payload, vector_clock=r.version_vector, device_id=r.nodo_origen_id, actor_id=r.actor_id,
                           created_at=r.creado_en) for r in rows]
    return events, (rows[-1].seq if rows else since)


def catalog(db: Session) -> list[ItemData]:
    return [ItemData(id=i.item_id, descripcion=i.descripcion, unidad_medida=i.unidad_medida, stock_referencia=i.stock_referencia)
            for i in db.scalars(select(ItemInventario).order_by(ItemInventario.item_id))]


def register_item(db: Session, item: ItemData) -> None:
    with _writer_lock:
        if db.get(ItemInventario, item.id) is None:
            db.add(ItemInventario(item_id=item.id, descripcion=item.descripcion, unidad_medida=item.unidad_medida,
                                  stock_referencia=item.stock_referencia, counter_p={}, counter_n={},
                                  stock_actual=item.stock_referencia))
            db.commit()
