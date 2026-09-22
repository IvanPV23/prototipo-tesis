from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app import models
from backend.app.core.database import Base
from backend.app.services.sync_service import apply_event
from shared.crdt import merge_clock, merge_component_maps
from shared.schemas import EventoSync


def test_joins_are_commutative_associative_and_idempotent():
    a, b, c = {"A": 2}, {"B": 3}, {"A": 1, "C": 4}
    assert merge_clock(a, b) == merge_clock(b, a)
    assert merge_clock(merge_clock(a, b), c) == merge_clock(a, merge_clock(b, c))
    assert merge_component_maps(a, a) == a


def test_concurrent_field_edits_and_counter_converge_without_lost_update():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    when = datetime(2026, 1, 1, tzinfo=timezone.utc)
    first = EventoSync(aggregate_id="V", event_type="VALE_CREADO", device_id="A", vector_clock={"A": 1}, created_at=when,
      payload={"id": "V", "codigo": "V", "material": "Cemento", "cantidad": 5, "estado": "ACTIVO", "pn_counter": {"p": {"A": 5}, "n": {}}, "field_versions": {"codigo": ["2026-01-01T00:00:00+00:00", "A", "1"], "material": ["2026-01-01T00:00:00+00:00", "A", "1"], "proyecto": ["2026-01-01T00:00:00+00:00", "A", "1"], "estado": ["2026-01-01T00:00:00+00:00", "A", "1"]}})
    second = EventoSync(aggregate_id="V", event_type="VALE_MODIFICADO", device_id="B", vector_clock={"B": 1}, created_at=when,
      payload={"id": "V", "codigo": "V", "material": "Acero", "cantidad": 2, "estado": "ACTIVO", "pn_counter": {"p": {"A": 5, "B": 2}, "n": {}}, "field_versions": {"material": ["2026-01-01T00:00:01+00:00", "B", "2"]}})
    assert apply_event(session, first) == "applied"
    assert apply_event(session, second) == "applied"
    vale = session.get(models.Vale, "V")
    assert vale.cantidad == 7
    assert vale.material == "Acero"
    assert vale.vector_clock == {"A": 1, "B": 1}


def test_server_events_cannot_be_updated_or_deleted():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    event = EventoSync(aggregate_id="V", event_type="VALE_CREADO", device_id="A", vector_clock={"A": 1},
      payload={"id": "V", "codigo": "V", "material": "Arena", "cantidad": 1})
    apply_event(session, event)
    session.commit()
    row = session.get(models.EventoSyncModel, str(event.event_id))
    row.device_id = "ALTERADO"
    with pytest.raises(ValueError, match="append-only"):
        session.commit()
    session.rollback()
    session.delete(row)
    with pytest.raises(ValueError, match="append-only"):
        session.commit()
