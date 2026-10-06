from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import DATABASE_URL


class Base(DeclarativeBase):
    pass


def make_engine(url: str):
    is_sqlite = url.startswith("sqlite")
    engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30} if is_sqlite else {})
    if is_sqlite:
        @event.listens_for(engine, "connect")
        def _pragmas(dbapi_connection, _):
            cursor = dbapi_connection.cursor()
            # WAL: lectores no bloquean al escritor único; synchronous=FULL conserva la durabilidad ACID.
            if ":memory:" not in url:
                cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=FULL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    return engine


APPEND_ONLY_TABLES = ("evento_sincronizacion", "movimiento_inventario", "bitacora_auditoria")


def init_db(engine) -> None:
    """Crea el esquema y blinda las tablas append-only también a nivel de motor SQL."""
    from .. import models  # noqa: F401  registra los modelos
    Base.metadata.create_all(bind=engine)
    if engine.dialect.name != "sqlite":
        return
    with engine.begin() as connection:
        for table in APPEND_ONLY_TABLES:
            for op in ("UPDATE", "DELETE"):
                connection.execute(text(
                    f"CREATE TRIGGER IF NOT EXISTS {table}_no_{op.lower()} BEFORE {op} ON {table} "
                    f"BEGIN SELECT RAISE(ABORT, '{table} append-only'); END"))


engine = make_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
