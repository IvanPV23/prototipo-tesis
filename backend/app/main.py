from fastapi import FastAPI
from .core.database import Base, engine
from . import models  # registra modelos
from .api.v1.endpoints import sync, vales
Base.metadata.create_all(bind=engine)
app = FastAPI(title="Vales offline-first", version="0.1.0")
app.include_router(sync.router, prefix="/api/v1")
app.include_router(vales.router, prefix="/api/v1")
@app.get("/health")
def health(): return {"status": "ok"}
