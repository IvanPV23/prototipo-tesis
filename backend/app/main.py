from fastapi import FastAPI

from .api.v1.endpoints import sync, vales
from .core.database import engine, init_db

init_db(engine)
app = FastAPI(title="ARDPOL - vales offline-first", version="0.2.0")
app.include_router(sync.router, prefix="/api/v1")
app.include_router(vales.router, prefix="/api/v1")


@app.get("/health")
def health():
    return {"status": "ok"}
