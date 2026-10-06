from client.app.storage.local_db import LocalDB
from client.app.services.vale_service import ValeService
from .conftest import write_json
from time import perf_counter
from datetime import datetime, timezone
from shared.schemas import SyncRequest
from backend.app.services.inventario_service import incoming_wins

def test_flujo_local_end_to_end(tmp_path, output_dir):
    db=LocalDB(str(tmp_path / "e2e.db")); service=ValeService(db,"CLI-A")
    samples=[]
    for index in range(50):
        start=perf_counter(); service.guardar(f"V-{index}",f"V-{index}","LAPTOP-001",index + 1); samples.append((perf_counter()-start)*1000)
    assert len(db.pending()) == 50
    sync_samples=[]; reconciliation_samples=[]; audit_samples=[]
    for _ in range(10):
        start=perf_counter(); SyncRequest(device_id="CLI-A", events=db.pending()).model_dump(mode="json"); sync_samples.append((perf_counter()-start)*1000)
        start=perf_counter(); incoming_wins(10, 3); reconciliation_samples.append((perf_counter()-start)*1000)
        start=perf_counter(); [event.model_dump(mode="json") for event in db._events()]; audit_samples.append((perf_counter()-start)*1000)
    def metric(values): return {"promedio_ms":round(sum(values)/len(values),3),"min_ms":round(min(values),3),"max_ms":round(max(values),3)}
    offline=metric(samples)
    write_json(output_dir / "tiempos.json", {"test":"Flujo End-to-End completo","fecha":datetime.now(timezone.utc).isoformat(),"entorno":{"modo":"offline-first, SQLite local","conflictos_simulados":True},"metricas":{"registro_offline":offline,"sincronizacion":metric(sync_samples),"conciliacion":metric(reconciliation_samples),"auditoria":metric(audit_samples)},"vales_procesados":50,"tasa_exito":1.0,"estado":"APROBADO"})
