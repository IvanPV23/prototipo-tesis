from shared.crdt import (as_utc, counter_value, event_counter, event_field_versions,
                         merge_clock, merge_component_maps, merge_fields)
from shared.schemas import EventoSync, ValeData

def apply_remote(db, event: EventoSync) -> None:
    current = db.get_vale(event.aggregate_id)
    if current is None:
        data = ValeData.model_validate(event.payload)
        p, n = event_counter(event.payload, event.device_id, data.cantidad)
        versions = event_field_versions(event.payload, event.created_at.isoformat(), event.device_id, str(event.event_id))
        data.cantidad = counter_value(p, n)
        db.save_vale(data, event.vector_clock, event.device_id, versions, p, n)
    else:
        vale, clock, device = current
        data = ValeData.model_validate(event.payload)
        versions, old_p, old_n = db.get_crdt(event.aggregate_id)
        incoming_versions = event_field_versions(event.payload, event.created_at.isoformat(), event.device_id, str(event.event_id))
        fields, versions = merge_fields({key: getattr(vale, key) for key in ("codigo", "material", "proyecto", "estado")}, versions, data.model_dump(mode="json"), incoming_versions)
        p, n = event_counter(event.payload, event.device_id, data.cantidad)
        p, n = merge_component_maps(old_p, p), merge_component_maps(old_n, n)
        merged = ValeData(id=vale.id, cantidad=counter_value(p, n), actualizado_en=max(as_utc(vale.actualizado_en), as_utc(data.actualizado_en)), **fields)
        db.save_vale(merged, merge_clock(clock, event.vector_clock), event.device_id, versions, p, n)
    db.add_event(event, synced=True)
