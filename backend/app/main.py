from fastapi import FastAPI
from sqlalchemy import inspect, text
from .core.database import Base, engine
from . import models  # registra modelos
from .api.v1.endpoints import sync, vales
Base.metadata.create_all(bind=engine)

def _upgrade_sqlite_schema() -> None:
    """Compatibilidad para la base SQLite del prototipo sin introducir Alembic."""
    if engine.dialect.name != "sqlite":
        return
    wanted = {
        "vales": {"field_versions": "JSON NOT NULL DEFAULT '{}'", "counter_p": "JSON NOT NULL DEFAULT '{}'", "counter_n": "JSON NOT NULL DEFAULT '{}'", "version_vector": "JSON"},
        "eventos_sync": {"version_vector": "JSON"},
        "auditoria": {"device_id": "VARCHAR NOT NULL DEFAULT 'DESCONOCIDO'", "movimiento_id": "INTEGER"},
        "movimientos_inventario": {"event_id": "VARCHAR", "device_id": "VARCHAR NOT NULL DEFAULT 'DESCONOCIDO'"},
    }
    inspector = inspect(engine)
    with engine.begin() as connection:
        for table, columns in wanted.items():
            existing = {column["name"] for column in inspector.get_columns(table)}
            for name, declaration in columns.items():
                if name not in existing:
                    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {declaration}"))
        for table in ("vales", "eventos_sync"):
            columns = {column["name"] for column in inspector.get_columns(table)}
            if "vector_clock" in columns and "version_vector" in columns:
                connection.execute(text(f"UPDATE {table} SET version_vector = vector_clock WHERE version_vector IS NULL"))
        connection.execute(text("CREATE TRIGGER IF NOT EXISTS eventos_sync_no_update BEFORE UPDATE ON eventos_sync BEGIN SELECT RAISE(ABORT, 'eventos_sync append-only'); END"))
        connection.execute(text("CREATE TRIGGER IF NOT EXISTS eventos_sync_no_delete BEFORE DELETE ON eventos_sync BEGIN SELECT RAISE(ABORT, 'eventos_sync append-only'); END"))

_upgrade_sqlite_schema()
app = FastAPI(title="Vales offline-first", version="0.1.0")
app.include_router(sync.router, prefix="/api/v1")
app.include_router(vales.router, prefix="/api/v1")
@app.get("/health")
def health(): return {"status": "ok"}
