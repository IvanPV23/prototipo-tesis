import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from backend.app.core.database import get_db, init_db, make_engine
from backend.app.main import app
from backend.app.services.sync_service import register_item
from client.app.services.vale_service import ValeService
from client.app.storage.local_db import LocalDB
from shared.schemas import ItemData

CATALOGO = [ItemData(id="CEMENTO", descripcion="Cemento Portland", unidad_medida="BOLSA", stock_referencia=500),
            ItemData(id="ARENA", descripcion="Arena gruesa", unidad_medida="M3", stock_referencia=200),
            ItemData(id="ACERO", descripcion="Acero corrugado", unidad_medida="VARILLA", stock_referencia=300)]


@pytest.fixture
def central(tmp_path):
    """Base central aislada por prueba (nunca toca central.db)."""
    engine = make_engine(f"sqlite:///{tmp_path / 'central.db'}")
    init_db(engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with Session() as db:
        for item in CATALOGO:
            register_item(db, item)
    yield Session
    engine.dispose()


@pytest.fixture
def api(central):
    def override():
        db = central()
        try:
            yield db
        finally:
            db.close()
    app.dependency_overrides[get_db] = override
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def replica(tmp_path):
    """Fábrica de réplicas de campo con catálogo ya descargado."""
    created = []

    def make(device_id: str):
        db = LocalDB(str(tmp_path / f"{device_id}.sqlite"), device_id)
        db.upsert_catalog(CATALOGO)
        created.append(db)
        return db, ValeService(db, device_id)
    yield make
    for db in created:
        db.close()
