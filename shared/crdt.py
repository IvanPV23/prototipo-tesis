"""Funciones CRDT puras compartidas por todas las réplicas.

La política de negocio no vive aquí: esta capa únicamente hace joins
conmutativos, asociativos e idempotentes.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

ClockRelation = Literal["before", "after", "equal", "concurrent"]
DESCRIPTIVE_FIELDS = ("codigo", "material", "proyecto", "estado")


def as_utc(value: datetime) -> datetime:
    """SQLite suele devolver datetimes naive; el join CRDT compara en UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def compare(left: dict[str, int], right: dict[str, int]) -> ClockRelation:
    keys = set(left) | set(right)
    le = all(left.get(k, 0) <= right.get(k, 0) for k in keys)
    ge = all(left.get(k, 0) >= right.get(k, 0) for k in keys)
    if le and ge:
        return "equal"
    return "before" if le else "after" if ge else "concurrent"


def merge_clock(left: dict[str, int], right: dict[str, int]) -> dict[str, int]:
    return {key: max(left.get(key, 0), right.get(key, 0)) for key in set(left) | set(right)}


def merge_component_maps(left: dict[str, float], right: dict[str, float]) -> dict[str, float]:
    """Join de un componente G-Counter; también sirve para P y N."""
    return {key: max(float(left.get(key, 0)), float(right.get(key, 0))) for key in set(left) | set(right)}


def counter_value(positive: dict[str, float], negative: dict[str, float]) -> float:
    return sum(positive.values()) - sum(negative.values())


def event_counter(payload: dict[str, Any], device_id: str, fallback_amount: float = 0) -> tuple[dict[str, float], dict[str, float]]:
    """Obtiene el PN-Counter de un evento; acepta snapshots heredados al crear."""
    raw = payload.get("pn_counter")
    if isinstance(raw, dict):
        return dict(raw.get("p", {})), dict(raw.get("n", {}))
    # Compatibilidad para eventos del prototipo anterior. Los nuevos nunca usan
    # esta ruta porque no representa un merge de contador entre réplicas.
    amount = float(payload.get("cantidad", fallback_amount))
    return ({device_id: max(amount, 0)}, {device_id: max(-amount, 0)})


def event_field_versions(payload: dict[str, Any], timestamp: str, device_id: str, event_id: str) -> dict[str, list[str]]:
    supplied = payload.get("field_versions", {})
    default = [timestamp, device_id, event_id]
    return {field: list(supplied.get(field, default)) for field in DESCRIPTIVE_FIELDS}


def merge_fields(current: dict[str, Any], current_versions: dict[str, list[str]], incoming: dict[str, Any], incoming_versions: dict[str, list[str]]) -> tuple[dict[str, Any], dict[str, list[str]]]:
    """LWW por campo, con desempate total timestamp/device/event id."""
    merged, versions = dict(current), dict(current_versions)
    for field in DESCRIPTIVE_FIELDS:
        candidate = incoming_versions[field]
        if field not in versions or tuple(candidate) > tuple(versions[field]):
            merged[field], versions[field] = incoming[field], candidate
    return merged, versions
