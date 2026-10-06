"""Funciones CRDT puras compartidas por todas las réplicas (cliente y central).

Modelo aplicado (tesis, secc. 4.3 y 4.8; informe de avance, capa de sincronización):

* El **vale** es un documento logístico (SALIDA o INGRESO) identificado por un UUID
  generado en el nodo de origen. Sus campos de hecho físico (tipo, ítem, cantidad,
  unidad, nodo de origen) son *inmutables*: una corrección de cantidad se registra
  como anulación + nuevo vale, nunca sobrescribiendo el histórico (objetivo de
  diseño c).
* ``estado`` es un registro monótono ACTIVO < ANULADO (join = máximo): una anulación
  concurrente gana y es idempotente.
* ``proyecto`` y ``observacion`` son registros LWW por campo. El orden total usa un
  sello lógico derivado del vector de versiones (Lamport), con desempate por nodo y
  event_id, de modo que respeta la causalidad y no depende de relojes de pared.
* El **saldo de cada ítem** es un PN-Counter. Cada componente se indexa por el
  movimiento que lo origina (``V:<vale>`` para el efecto del vale y ``A:<vale>``
  para su compensación por anulación). Como el valor de cada componente es fijo, el
  join por máximo puntual es conmutativo, asociativo e idempotente: dos anulaciones
  concurrentes del mismo vale compensan una sola vez.

La política de negocio (p. ej. qué hacer ante un intento de modificar un campo
inmutable) no vive aquí: esta capa sólo define joins y detecta violaciones.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

ClockRelation = Literal["before", "after", "equal", "concurrent"]

IMMUTABLE_FIELDS = ("id", "codigo", "tipo", "material", "cantidad", "unidad_medida", "nodo_origen")
LWW_FIELDS = ("proyecto", "observacion")
ESTADOS = ("ACTIVO", "ANULADO")  # orden del semirretículo de estado


class ImmutableFieldConflict(ValueError):
    """Dos réplicas afirman hechos físicos distintos para el mismo vale."""


def as_utc(value: datetime) -> datetime:
    """SQLite suele devolver datetimes naive; se interpretan como UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


# --------------------------------------------------------------------------- relojes
def compare(left: dict[str, int], right: dict[str, int]) -> ClockRelation:
    left, right = left or {}, right or {}
    keys = set(left) | set(right)
    le = all(left.get(k, 0) <= right.get(k, 0) for k in keys)
    ge = all(left.get(k, 0) >= right.get(k, 0) for k in keys)
    if le and ge:
        return "equal"
    return "before" if le else "after" if ge else "concurrent"


def merge_clock(left: dict[str, int], right: dict[str, int]) -> dict[str, int]:
    left, right = left or {}, right or {}
    return {key: max(left.get(key, 0), right.get(key, 0)) for key in sorted(set(left) | set(right))}


def lamport(clock: dict[str, int]) -> int:
    """Sello lógico escalar compatible con la causalidad: si a < b entonces lamport(a) < lamport(b)."""
    return sum((clock or {}).values())


def field_version(clock: dict[str, int], device_id: str, event_id: str) -> list:
    return [lamport(clock), device_id, str(event_id)]


# ------------------------------------------------------------------------ contadores
def merge_component_maps(left: dict[str, float], right: dict[str, float]) -> dict[str, float]:
    """Join de un G-Counter (máximo puntual); sirve para los componentes P y N."""
    left, right = left or {}, right or {}
    return {key: max(float(left.get(key, 0)), float(right.get(key, 0))) for key in sorted(set(left) | set(right))}


def counter_value(positive: dict[str, float], negative: dict[str, float]) -> float:
    return round(sum((positive or {}).values()) - sum((negative or {}).values()), 6)


def vale_counter_components(vale: dict[str, Any]) -> tuple[dict[str, float], dict[str, float]]:
    """Componentes PN que un vale aporta al saldo de su ítem."""
    q, vid = float(vale["cantidad"]), vale["id"]
    p: dict[str, float] = {}
    n: dict[str, float] = {}
    effect, compensation = (p, n) if vale["tipo"] == "INGRESO" else (n, p)
    effect[f"V:{vid}"] = q
    if vale.get("estado") == "ANULADO":
        compensation[f"A:{vid}"] = q
    return p, n


def vale_contribution(vale: dict[str, Any] | None) -> float:
    """Aporte neto de un vale al saldo (0 si está anulado o no existe)."""
    if not vale or vale.get("estado") == "ANULADO":
        return 0.0
    sign = 1.0 if vale["tipo"] == "INGRESO" else -1.0
    return sign * float(vale["cantidad"])


def merge_item_counter(p: dict, n: dict, vale: dict[str, Any]) -> tuple[dict[str, float], dict[str, float]]:
    vp, vn = vale_counter_components(vale)
    return merge_component_maps(p, vp), merge_component_maps(n, vn)


# ------------------------------------------------------------------------------ vale
def merge_vale(current: dict[str, Any] | None, incoming: dict[str, Any]) -> dict[str, Any]:
    """Join del CRDT compuesto del vale. ``current`` puede ser None (primer evento).

    Los estados tienen la forma::

        {id, codigo, tipo, material, cantidad, unidad_medida, nodo_origen,
         estado, proyecto, observacion, field_versions: {campo: [lamport, nodo, event_id]},
         version_vector: {nodo: contador}}
    """
    if current is None:
        merged = {key: incoming.get(key) for key in IMMUTABLE_FIELDS + LWW_FIELDS + ("estado",)}
        merged["field_versions"] = {f: list(incoming["field_versions"][f]) for f in LWW_FIELDS}
        merged["version_vector"] = dict(incoming.get("version_vector") or {})
        return merged
    for key in IMMUTABLE_FIELDS:
        left, right = current.get(key), incoming.get(key)
        if key == "cantidad":
            left, right = float(left), float(right)
        if left != right:
            raise ImmutableFieldConflict(f"campo inmutable '{key}' divergente en vale {current['id']}: {left!r} != {right!r}")
    merged = dict(current)
    merged["estado"] = max(current["estado"], incoming["estado"], key=ESTADOS.index)
    versions = {f: list(v) for f, v in current["field_versions"].items()}
    for field in LWW_FIELDS:
        candidate = list(incoming["field_versions"][field])
        if tuple(candidate) > tuple(versions[field]):
            merged[field], versions[field] = incoming[field], candidate
    merged["field_versions"] = versions
    merged["version_vector"] = merge_clock(current.get("version_vector"), incoming.get("version_vector"))
    return merged


def vale_digest(vale: dict[str, Any]) -> tuple:
    """Representación canónica para comparar réplicas (convergencia)."""
    return (vale["id"], vale["tipo"], vale["material"], round(float(vale["cantidad"]), 6), vale["unidad_medida"],
            vale["nodo_origen"], vale["estado"], vale["proyecto"], vale.get("observacion") or "")
