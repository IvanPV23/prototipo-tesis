import pytest
pytest.importorskip("sqlalchemy", reason="dependencia declarada en backend/requirements.txt no disponible en este entorno")
from fastapi.testclient import TestClient
from backend.app.main import app
from time import perf_counter
from .conftest import write_json, now

def test_p7_rest_salud_y_no_encontrado(output_dir):
    client=TestClient(app)
    start=perf_counter(); health=client.get("/health"); health_ms=round((perf_counter()-start)*1000, 2)
    assert health.status_code == 200
    assert client.get("/api/v1/vales/no-existe").status_code == 404
    payload={"id":"REST-001","codigo":"REST-001","material":"LAPTOP-001","cantidad":5,"proyecto":"GENERAL"}
    start=perf_counter(); created=client.post("/api/v1/vales",json=payload); create_ms=round((perf_counter()-start)*1000, 2)
    assert created.status_code == 201
    start=perf_counter(); synced=client.post("/api/v1/sync/bulk",json={"device_id":"SIMULADOR","events":[]}); sync_ms=round((perf_counter()-start)*1000, 2)
    assert synced.status_code == 200
    write_json(output_dir / "api_test.json", {"test":"P7 - API REST","fecha":now(),"endpoints":[{"metodo":"GET","url":"/health","status":200,"tiempo_ms":health_ms,"contrato":"OK"},{"metodo":"POST","url":"/api/v1/vales","status":201,"tiempo_ms":create_ms,"contrato":"OK"},{"metodo":"POST","url":"/api/v1/sync/bulk","status":200,"tiempo_ms":sync_ms,"contrato":"OK"},{"metodo":"GET","url":"/api/v1/vales/no-existe","status":404,"contrato":"OK"}],"tasa_exito":1.0,"estado":"APROBADO"})
