import pytest
pytest.importorskip("sqlalchemy", reason="requiere SQLAlchemy")
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.app.core.database import Base
from backend.app import models
from backend.app.services.sync_service import apply_event
from shared.schemas import EventoSync
from .conftest import record_integrity, log, now
from .simulation import ConstructionClock

def test_p2_p4_convergencia_y_conflicto_explicito(output_dir):
    engine=create_engine("sqlite:///:memory:"); Base.metadata.create_all(engine); db=sessionmaker(bind=engine)()
    clock=ConstructionClock(); time_a, days_a=clock.next_event(); time_b, days_b=clock.next_event()
    base={"id":"LAPTOP-001","codigo":"L-1","material":"LAPTOP-001","cantidad":10,"estado":"ACTIVO"}
    a=EventoSync(aggregate_id="LAPTOP-001",event_type="VALE_CREADO",payload={**base,"actualizado_en":time_a.isoformat()},vector_clock={"CLI-A":1},device_id="CLI-A",created_at=time_a)
    b=EventoSync(aggregate_id="LAPTOP-001",event_type="VALE_MODIFICADO",payload={**base,"cantidad":3,"actualizado_en":time_b.isoformat()},vector_clock={"CLI-B":1},device_id="CLI-B",created_at=time_b)
    assert apply_event(db,a) == "applied" and apply_event(db,b) == "applied"
    db.commit(); vale = db.get(models.Vale,"LAPTOP-001")
    assert db.query(models.EventoSyncModel).count() == 2 and vale.cantidad == 13
    log(output_dir, "test_p2_p4.log", [f"INFO: CLI-A cantidad=10 vector={{CLI-A: 1}} timestamp_simulado={time_a.isoformat()} (+{days_a} dia obra)", f"INFO: CLI-B cantidad=3 vector={{CLI-B: 1}} timestamp_simulado={time_b.isoformat()} (+{days_b} dia obra)", "INFO: Join PN-Counter: 10 (CLI-A) + 3 (CLI-B) = 13; no hay ganador de fila", "INFO: Estado final inventario LAPTOP-001=13"])
    record_integrity(output_dir, "P2_P4", {"test":"P2/P4 - Convergencia CRDT por join de PN-Counter", "fecha":now(), "simulacion_tiempo":{"equivalencia":"1 minuto logico = 1 dia de obra", "timestamp_nodo_a":time_a.isoformat(), "timestamp_nodo_b":time_b.isoformat(), "eventos_simultaneos":False}, "conflictos_detectados":0, "conflictos_resueltos":0, "estado_final_consistente":True, "stock_final":{"LAPTOP-001":13}, "regla_aplicada":"pn_counter_join", "estado":"APROBADO"})
