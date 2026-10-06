from client.app.storage.local_db import LocalDB
from client.app.services.vale_service import ValeService
from .conftest import record_integrity, log, now
from .simulation import ConstructionClock

def test_p1_escrituras_locales_siempre_exitosas(tmp_path, output_dir):
    db = LocalDB(str(tmp_path / "campo.db")); service = ValeService(db, "CLI-A")
    clock = ConstructionClock(); vales = []; lines = ["INFO: Iniciando cliente en modo OFFLINE"]
    for vale_id, item, cantidad in [("VAL-001", "LAPTOP-001", 5), ("VAL-002", "MONITOR-002", 3)]:
        timestamp, days = clock.next_event()
        event = service.guardar(vale_id, vale_id, item, cantidad, timestamp=timestamp)
        vales.append({"id": event.aggregate_id, "item": item, "cantidad": cantidad, "timestamp_simulado": timestamp.isoformat(), "dias_desconexion": days})
        lines.append(f"INFO: Vale local ID={event.aggregate_id}, item={item}, cantidad={cantidad}, timestamp_simulado={timestamp.isoformat()}, desconexion={days} dia(s) de obra")
    assert len(db.pending()) == 2 and all(db.get_vale(v["id"]) for v in vales)
    lines.append("INFO: Estado SQLite: vales_persistidos=2, pendientes=2")
    log(output_dir, "test_p1.log", lines)
    record_integrity(output_dir, "P1", {"test":"P1 - Escrituras locales siempre tienen exito", "fecha":now(), "simulacion_tiempo":{"equivalencia":"1 minuto logico = 1 dia de obra", "dias_desconexion_acumulados":clock.simulated_days}, "vales_registrados":vales, "vales_persistidos":2, "tasa_exito":1.0, "estado":"APROBADO"})
