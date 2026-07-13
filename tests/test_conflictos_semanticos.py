import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.main import app
from backend.app.core.database import Base, get_db
from backend.app.models.vale import Vale
from backend.app.services.inventario_service import set_resolution_rule
from shared.schemas import EventoSync, SyncRequest
from .conftest import record_integrity, log, now

@pytest.fixture
def backend_db_session(tmp_path):
    # Asegurar regla por defecto al empezar
    set_resolution_rule("mayor_cantidad")
    
    db_file = tmp_path / "backend_conflicts_test.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    
    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()
            
    app.dependency_overrides[get_db] = override_get_db
    yield Session
    
    # Limpieza
    app.dependency_overrides.pop(get_db, None)
    set_resolution_rule("mayor_cantidad")

def test_consumos_concurrentes_dentro_del_stock_no_generan_conflicto(output_dir, backend_db_session):
    test_client = TestClient(app)
    logs = ["INFO: Iniciando Test de Regla Semántica: consumo concurrente dentro del stock"]

    ev_a = EventoSync(
        aggregate_id="LAPTOP-001",
        event_type="VALE_CREADO",
        device_id="CLI-A",
        vector_clock={"CLI-A": 1},
        payload={"id": "LAPTOP-001", "codigo": "LAPTOP-001", "material": "Laptop", "cantidad": 10.0, "estado": "ACTIVO"}
    )
    ev_b = EventoSync(
        aggregate_id="LAPTOP-001",
        event_type="VALE_MODIFICADO",
        device_id="CLI-B",
        vector_clock={"CLI-B": 1},
        payload={"id": "LAPTOP-001", "codigo": "LAPTOP-001", "material": "Laptop", "cantidad": 8.0, "estado": "ACTIVO"}
    )

    req_1 = SyncRequest(device_id="CLI-A", events=[ev_a])
    res_1 = test_client.post("/api/v1/sync/bulk", json=req_1.model_dump(mode="json"))
    assert res_1.status_code == 200
    assert str(ev_a.event_id) in res_1.json()["applied"]

    req_2 = SyncRequest(device_id="CLI-B", events=[ev_b])
    res_2 = test_client.post("/api/v1/sync/bulk", json=req_2.model_dump(mode="json"))
    assert res_2.status_code == 200
    assert str(ev_b.event_id) in res_2.json()["applied"]
    assert res_2.json()["conflicts"] == []

    db = backend_db_session()
    try:
        vale = db.get(Vale, "LAPTOP-001")
        assert vale.cantidad == 8.0, f"Se esperaba cantidad 8.0, pero se obtuvo {vale.cantidad}"
    finally:
        db.close()

    logs.append("SUCCESS: Consumo concurrente dentro del stock aplicado sin conflicto semántico.")
    log(output_dir, "test_consumos_concurrentes_dentro_del_stock.log", logs)


def test_conflicto_al_agotar_stock(output_dir, backend_db_session):
    test_client = TestClient(app)
    logs = ["INFO: Iniciando Test de Regla Semántica: agotamiento de stock"]

    ev_a = EventoSync(
        aggregate_id="VAL-C-004",
        event_type="VALE_CREADO",
        device_id="CLI-A",
        vector_clock={"CLI-A": 1},
        payload={"id": "VAL-C-004", "codigo": "VAL-C-004", "material": "Pintura", "cantidad": 5.0, "estado": "ACTIVO"}
    )
    ev_b = EventoSync(
        aggregate_id="VAL-C-004",
        event_type="VALE_MODIFICADO",
        device_id="CLI-B",
        vector_clock={"CLI-B": 1},
        payload={"id": "VAL-C-004", "codigo": "VAL-C-004", "material": "Pintura", "cantidad": -1.0, "estado": "ACTIVO"}
    )

    req_1 = SyncRequest(device_id="CLI-A", events=[ev_a])
    res_1 = test_client.post("/api/v1/sync/bulk", json=req_1.model_dump(mode="json"))
    assert res_1.status_code == 200
    assert str(ev_a.event_id) in res_1.json()["applied"]

    req_2 = SyncRequest(device_id="CLI-B", events=[ev_b])
    res_2 = test_client.post("/api/v1/sync/bulk", json=req_2.model_dump(mode="json"))
    assert res_2.status_code == 200
    assert str(ev_b.event_id) in res_2.json()["conflicts"]

    logs.append("SUCCESS: El agotamiento de stock se detecta como conflicto semántico.")
    log(output_dir, "test_conflicto_al_agotar_stock.log", logs)


def test_conflicto_mayor_cantidad(output_dir, backend_db_session):
    test_client = TestClient(app)
    logs = ["INFO: Iniciando Test de Regla Semántica: mayor_cantidad (Default)"]
    
    ev_a = EventoSync(
        aggregate_id="VAL-C-001",
        event_type="VALE_CREADO",
        device_id="CLI-A",
        vector_clock={"CLI-A": 1},
        payload={"id": "VAL-C-001", "codigo": "VAL-C-001", "material": "Cemento", "cantidad": 10.0, "estado": "ACTIVO"}
    )
    ev_b = EventoSync(
        aggregate_id="VAL-C-001",
        event_type="VALE_CREADO",
        device_id="CLI-B",
        vector_clock={"CLI-B": 1},
        payload={"id": "VAL-C-001", "codigo": "VAL-C-001", "material": "Cemento", "cantidad": 18.0, "estado": "ACTIVO"}
    )
    
    req_1 = SyncRequest(device_id="CLI-A", events=[ev_a])
    res_1 = test_client.post("/api/v1/sync/bulk", json=req_1.model_dump(mode="json"))
    assert res_1.status_code == 200
    assert str(ev_a.event_id) in res_1.json()["applied"]
    
    req_2 = SyncRequest(device_id="CLI-B", events=[ev_b])
    res_2 = test_client.post("/api/v1/sync/bulk", json=req_2.model_dump(mode="json"))
    assert res_2.status_code == 200
    assert str(ev_b.event_id) in res_2.json()["applied"]
    
    db = backend_db_session()
    try:
        vale = db.get(Vale, "VAL-C-001")
        assert vale.cantidad == 18.0, f"Se esperaba cantidad 18.0, pero se obtuvo {vale.cantidad}"
    finally:
        db.close()
        
    logs.append("SUCCESS: Escenario mayor_cantidad exitoso. Prevaleció la cantidad mayor (18.0 > 10.0).")
    log(output_dir, "test_conflictos_semanticos_mayor.log", logs)

def test_conflicto_menor_cantidad(output_dir, backend_db_session):
    test_client = TestClient(app)
    logs = ["INFO: Iniciando Test de Regla Semántica: menor_cantidad"]
    set_resolution_rule("menor_cantidad")
    
    ev_c = EventoSync(
        aggregate_id="VAL-C-002",
        event_type="VALE_CREADO",
        device_id="CLI-A",
        vector_clock={"CLI-A": 1},
        payload={"id": "VAL-C-002", "codigo": "VAL-C-002", "material": "Acero", "cantidad": 10.0, "estado": "ACTIVO"}
    )
    ev_d = EventoSync(
        aggregate_id="VAL-C-002",
        event_type="VALE_CREADO",
        device_id="CLI-B",
        vector_clock={"CLI-B": 1},
        payload={"id": "VAL-C-002", "codigo": "VAL-C-002", "material": "Acero", "cantidad": 18.0, "estado": "ACTIVO"}
    )
    
    req_1 = SyncRequest(device_id="CLI-B", events=[ev_d])
    res_1 = test_client.post("/api/v1/sync/bulk", json=req_1.model_dump(mode="json"))
    assert res_1.status_code == 200
    assert str(ev_d.event_id) in res_1.json()["applied"]
    
    req_2 = SyncRequest(device_id="CLI-A", events=[ev_c])
    res_2 = test_client.post("/api/v1/sync/bulk", json=req_2.model_dump(mode="json"))
    assert res_2.status_code == 200
    assert str(ev_c.event_id) in res_2.json()["applied"]
    
    db = backend_db_session()
    try:
        vale = db.get(Vale, "VAL-C-002")
        assert vale.cantidad == 10.0, f"Se esperaba cantidad 10.0 (regla menor_cantidad), pero se obtuvo {vale.cantidad}"
    finally:
        db.close()
        
    logs.append("SUCCESS: Escenario menor_cantidad exitoso. Prevaleció la cantidad menor (10.0 < 18.0).")
    log(output_dir, "test_conflictos_semanticos_menor.log", logs)

def test_conflicto_cancelado_prevalece(output_dir, backend_db_session):
    test_client = TestClient(app)
    logs = ["INFO: Iniciando Test de Regla Semántica: Prevalencia del estado CANCELADO"]
    
    ev_e = EventoSync(
        aggregate_id="VAL-C-003",
        event_type="VALE_CREADO",
        device_id="CLI-A",
        vector_clock={"CLI-A": 1},
        payload={"id": "VAL-C-003", "codigo": "VAL-C-003", "material": "Piedra", "cantidad": 25.0, "estado": "ACTIVO"}
    )
    ev_f = EventoSync(
        aggregate_id="VAL-C-003",
        event_type="VALE_CANCELADO",
        device_id="CLI-B",
        vector_clock={"CLI-B": 1},
        payload={"id": "VAL-C-003", "codigo": "VAL-C-003", "material": "Piedra", "cantidad": 5.0, "estado": "CANCELADO"}
    )
    
    req_1 = SyncRequest(device_id="CLI-A", events=[ev_e])
    res_1 = test_client.post("/api/v1/sync/bulk", json=req_1.model_dump(mode="json"))
    assert res_1.status_code == 200
    assert str(ev_e.event_id) in res_1.json()["applied"]
    
    req_2 = SyncRequest(device_id="CLI-B", events=[ev_f])
    res_2 = test_client.post("/api/v1/sync/bulk", json=req_2.model_dump(mode="json"))
    assert res_2.status_code == 200
    assert str(ev_f.event_id) in res_2.json()["applied"]
    
    db = backend_db_session()
    try:
        vale = db.get(Vale, "VAL-C-003")
        assert vale.estado == "CANCELADO", f"Se esperaba estado CANCELADO, pero se obtuvo {vale.estado}"
        assert vale.cantidad == 5.0
    finally:
        db.close()
        
    logs.append("SUCCESS: Escenario CANCELADO prevalece exitoso. Estado final es CANCELADO.")
    log(output_dir, "test_conflictos_semanticos_cancelado.log", logs)
    
    record_integrity(
        output_dir,
        "CONFLICTOS_SEMANTICOS",
        {
            "test": "Resolución de conflictos concurrentes bajo múltiples reglas semánticas",
            "fecha": now(),
            "reglas_verificadas": ["mayor_cantidad", "menor_cantidad", "cancelado_prevalece"],
            "conflictos_resueltos": 3,
            "estado_final_consistente": True,
            "estado": "APROBADO"
        }
    )
