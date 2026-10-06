"""Pruebas funcionales de los principios de diseño P1-P8 sobre el artefacto completo."""
import sqlite3

import httpx
import pytest
from sqlalchemy import func, select, text

from backend.app.core.security import Subject, can_read, can_write
from backend.app.models import (BitacoraAuditoria, EventoSincronizacion, ItemInventario, MovimientoInventario,
                                ValeInventario)
from client.app.sync import sync_engine as engine_module
from client.app.sync.sync_engine import SyncEngine, SyncError
from shared.schemas import SyncRequest


class SinRed(httpx.BaseTransport):
    def handle_request(self, request):
        raise httpx.ConnectError("sin cobertura", request=request)


def _engine(api, db, device, **kw):
    return SyncEngine(db, device, "http://testserver", transport=api._transport, backoff_base=0, **kw)


def test_p1_registro_local_sin_red(replica):
    db, service = replica("CLI-1")
    for i in range(20):
        service.registrar("SALIDA", "CEMENTO", i + 1)
    assert db.count_pending() == 20
    assert db.stocks()["CEMENTO"] == 500 - sum(range(1, 21))
    with pytest.raises(SyncError):
        SyncEngine(db, "CLI-1", "http://offline", transport=SinRed(), max_retries=2, backoff_base=0).push()
    assert db.count_pending() == 20  # la cola sobrevive al fallo de red


def test_p2_p4_convergencia_de_cinco_replicas_via_central(api, replica, central):
    nodes = [replica(f"CLI-{i}") for i in range(1, 6)]
    seed_db, seed = replica("LOGISTICA")
    shared = [seed.registrar("INGRESO", "ARENA", 10, vale_id=f"S-{k}").aggregate_id for k in range(3)]
    _engine(api, seed_db, "LOGISTICA").sync()
    for i, (db, _) in enumerate(nodes, 1):
        _engine(api, db, f"CLI-{i}").pull()
    for i, (db, service) in enumerate(nodes, 1):  # operaciones offline concurrentes
        service.registrar("SALIDA", "CEMENTO", i)
        service.anular(shared[0])  # anulación concurrente en todos los nodos
        service.reasignar_proyecto(shared[1], f"PROY-{i}")  # LWW concurrente
    for i, (db, _) in enumerate(nodes, 1):
        _engine(api, db, f"CLI-{i}").push()
    for i, (db, _) in enumerate(nodes, 1):
        _engine(api, db, f"CLI-{i}").pull()
    snapshots = [db.snapshot() for db, _ in nodes]
    assert all(s == snapshots[0] for s in snapshots)
    with central() as s:
        assert s.get(ItemInventario, "CEMENTO").stock_actual == 500 - 15
        assert s.get(ItemInventario, "ARENA").stock_actual == 200 + 20  # S-0 compensado una sola vez
        assert s.get(ValeInventario, shared[1]).proyecto_id == "PROY-5"  # mayor desempate determinista
        concurrentes = s.scalar(select(func.count()).select_from(BitacoraAuditoria)
                                .where(BitacoraAuditoria.detalles["concurrente"].as_boolean()))
        assert concurrentes > 0
    assert snapshots[0]["stocks"] == {"ACERO": 300, "ARENA": 220, "CEMENTO": 485}


def test_p3_reintento_idempotente_y_lote_atomico(api, replica, central):
    db, service = replica("CLI-1")
    for i in range(5):
        service.registrar("SALIDA", "ACERO", 2)
    request = SyncRequest(device_id="CLI-1", events=db.pending()).model_dump(mode="json")
    first = api.post("/api/v1/sync/bulk", json=request).json()
    retry = api.post("/api/v1/sync/bulk", json=request).json()  # mismo lote tras perder la respuesta
    assert len(first["applied"]) == 5 and len(retry["duplicates"]) == 5
    service.registrar("SALIDA", "ACERO", 1)
    bad = SyncRequest(device_id="CLI-1", events=db.pending()).model_dump(mode="json")
    bad["events"][-1]["payload"]["material"] = "NO-EXISTE"
    assert api.post("/api/v1/sync/bulk", json=bad).status_code == 422
    with central() as s:
        assert s.scalar(select(func.count()).select_from(EventoSincronizacion)) == 5  # nada del lote inválido
        assert s.scalar(select(func.count()).select_from(MovimientoInventario)) == 5
        assert s.get(ItemInventario, "ACERO").stock_actual == 290


def test_p3_p6_tablas_append_only_en_central_y_cliente(api, replica, central):
    db, service = replica("CLI-1")
    service.registrar("SALIDA", "ARENA", 3)
    _engine(api, db, "CLI-1").push()
    with central() as s:
        for table in ("evento_sincronizacion", "movimiento_inventario", "bitacora_auditoria"):
            with pytest.raises(Exception, match="append-only"):
                s.execute(text(f"UPDATE {table} SET vale_id='X'"))
            s.rollback()
            with pytest.raises(Exception, match="append-only"):
                s.execute(text(f"DELETE FROM {table}"))
            s.rollback()
    with pytest.raises(sqlite3.DatabaseError):
        db.conn.execute("UPDATE eventos SET payload='{}'")
    with pytest.raises(sqlite3.DatabaseError):
        db.conn.execute("DELETE FROM eventos")


def test_p6_trazabilidad_e_invariante_de_saldo(api, replica, central):
    db, service = replica("CLI-2")
    ids = [service.registrar(t, "CEMENTO", q).aggregate_id for t, q in [("SALIDA", 5), ("INGRESO", 8), ("SALIDA", 2)]]
    service.anular(ids[0])
    service.observar(ids[1], "guía 123")
    _engine(api, db, "CLI-2").push()
    item = api.get("/api/v1/items/CEMENTO").json()
    assert item["invariante_ok"] and item["stock_actual"] == 500 + 8 - 2
    with central() as s:
        movimientos = s.scalars(select(MovimientoInventario)).all()
        assert len(movimientos) == 4  # 3 vales + 1 compensación
        for m in movimientos:
            assert s.scalar(select(func.count()).select_from(BitacoraAuditoria).where(BitacoraAuditoria.movimiento_id == m.movimiento_id)) == 1
        acciones = [a["accion"] for a in api.get(f"/api/v1/vales/{ids[0]}/auditoria").json()]
        assert acciones == ["CREACION", "ANULACION"]


def test_conflicto_por_hecho_fisico_divergente(api, replica, central):
    db, service = replica("CLI-3")
    event = service.registrar("SALIDA", "ACERO", 4)
    _engine(api, db, "CLI-3").push()
    forged = SyncRequest(device_id="CLI-4", events=[event.model_copy(update={"event_id": __import__("uuid").uuid4(),
                         "payload": {**event.payload, "cantidad": 40}})]).model_dump(mode="json")
    response = api.post("/api/v1/sync/bulk", json=forged).json()
    assert len(response["conflicts"]) == 1
    with central() as s:
        assert s.get(ItemInventario, "ACERO").stock_actual == 296  # el conflicto no altera el saldo
        assert s.scalar(select(func.count()).select_from(BitacoraAuditoria).where(BitacoraAuditoria.accion == "CONFLICTO")) == 1


def test_p5_motor_de_sincronizacion_desacoplado_del_dominio():
    source = open(engine_module.__file__, encoding="utf-8").read()
    assert "backend" not in source and "stock" not in source.lower()


def test_p7_contrato_rest(api):
    assert api.get("/health").status_code == 200
    assert api.get("/api/v1/vales/no-existe").status_code == 404
    assert api.post("/api/v1/sync/bulk", json={"device_id": "X", "events": []}).status_code == 200
    assert api.get("/api/v1/sync/changes", params={"since": 0}).json()["last_seq"] == 0
    assert api.post("/api/v1/items", json={"id": "TUBO", "descripcion": "Tubo"}, headers={"x-actor-role": "tecnico"}).status_code == 403


def test_p8_abac_por_rol_y_proyecto(api, replica):
    tecnico_a = Subject("TEC-A", "tecnico", frozenset({"PROY-A"}))
    auditor = Subject("AUD", "auditor", frozenset({"PROY-A"}))
    assert can_write(tecnico_a, "PROY-A") and not can_write(tecnico_a, "PROY-B")
    assert not can_write(auditor, "PROY-A") and can_read(auditor, "PROY-A")
    db, service = replica("TEC-B")
    service.registrar("SALIDA", "ARENA", 1, proyecto="PROY-A")
    body = SyncRequest(device_id="TEC-B", events=db.pending()).model_dump(mode="json")
    denied = api.post("/api/v1/sync/bulk", json=body, headers={"x-actor-role": "tecnico", "x-actor-projects": "PROY-B"})
    assert denied.status_code == 403


def test_lote_con_creacion_y_anulacion_del_mismo_vale_y_entrega_desordenada(api, replica, central):
    db, service = replica("CLI-5")
    vid = service.registrar("SALIDA", "CEMENTO", 7).aggregate_id
    service.anular(vid)
    service.observar(vid, "devuelto")
    events = db.pending()
    reversed_body = SyncRequest(device_id="CLI-5", events=list(reversed(events))).model_dump(mode="json")
    assert len(api.post("/api/v1/sync/bulk", json=reversed_body).json()["applied"]) == 3
    with central() as s:
        assert s.get(ItemInventario, "CEMENTO").stock_actual == 500  # anulado: sin efecto neto
        assert s.get(ValeInventario, vid).observacion == "devuelto"
    assert api.get("/api/v1/items/CEMENTO").json()["invariante_ok"]
