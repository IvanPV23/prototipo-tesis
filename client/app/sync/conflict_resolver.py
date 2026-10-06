"""Aplicación de eventos remotos con el mismo join CRDT que usa la réplica central."""
from shared.crdt import ImmutableFieldConflict
from shared.schemas import EventoRemoto, ValeState


def apply_remote(db, event: EventoRemoto) -> str:
    if db.has_event(str(event.event_id)):
        return "known"  # eco de un evento propio o ya recibido: el join es idempotente, se omite
    if event.estado == "CONFLICTO":
        db.record_event_only(event, origen="REMOTO", synced=True)  # rechazado por la central; sólo se audita
        return "conflict"
    incoming = ValeState.model_validate(event.payload).model_dump(mode="json")
    try:
        db.apply_state(incoming, event, origen="REMOTO", synced=True)
    except ImmutableFieldConflict:
        db.record_event_only(event, origen="REMOTO", synced=True)
        return "conflict"
    return "merged"
