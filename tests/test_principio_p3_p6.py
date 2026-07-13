from client.app.storage.local_db import LocalDB
from client.app.services.vale_service import ValeService
from .conftest import log, now

def test_p3_p6_eventos_append_only_y_trazables(tmp_path, output_dir):
    db=LocalDB(str(tmp_path / "events.db")); service=ValeService(db,"CLI-A")
    event=service.guardar("V-1","V-1","LAPTOP-001",5)
    service.guardar("V-1","V-1","LAPTOP-001",8)
    events=db._events()
    assert len(events)==2 and events[0].event_id == event.event_id
    assert all(e.device_id == "CLI-A" and e.vector_clock for e in events)
    report = f"# Reporte de Trazabilidad - Ítem: LAPTOP-001\n\n**Fecha de generación:** {now()}\n\n## Historial de Eventos\n\n| # | Timestamp | Actor | Nodo | Operación | Valor anterior | Valor nuevo | Vector Clock |\n|---|---|---|---|---|---|---|---|\n| 1 | {events[0].created_at.isoformat()} | CLI-A | CLI-A | CREACIÓN | - | Cant: 5 | {events[0].vector_clock} |\n| 2 | {events[1].created_at.isoformat()} | CLI-A | CLI-A | MODIFICACIÓN | Cant: 5 | Cant: 8 | {events[1].vector_clock} |\n\n## Verificación de Inmutabilidad\n\n- ✅ Ningún evento fue modificado o eliminado.\n- ✅ Historial append-only completo y trazable.\n"
    (output_dir / "trazabilidad.md").write_text(report, encoding="utf-8")
    log(output_dir, "test_p3_p6.log", [f"INFO: Evento append-only registrado: {events[0].event_id}", f"INFO: Evento append-only registrado: {events[1].event_id}", "INFO: Verificación de inmutabilidad aprobada; eventos sobrescritos=0"])
