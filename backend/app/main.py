"""Punto de entrada de la API. Ejecutar:  uvicorn app.main:app --reload"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api import atenciones, auditoria, auth, cie10, pacientes, rips
from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.core.inmutabilidad import instalar_triggers
from app.seed import inicializar

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    # En producción se recomienda Alembic para migraciones (ver docs/07-hoja-de-ruta.md).
    Base.metadata.create_all(engine)
    instalar_triggers(engine)
    with SessionLocal() as db:
        inicializar(db)
    yield


app = FastAPI(
    title=f"{settings.APP_NOMBRE} API",
    description="Historia Clínica Electrónica y gestión hospitalaria - normatividad colombiana.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_lista,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def cabeceras_seguridad(request: Request, call_next):
    respuesta = await call_next(request)
    respuesta.headers["X-Content-Type-Options"] = "nosniff"
    respuesta.headers["X-Frame-Options"] = "DENY"
    respuesta.headers["Referrer-Policy"] = "no-referrer"
    respuesta.headers["Cache-Control"] = "no-store"  # datos clínicos: no guardar en caché
    return respuesta


for modulo in (auth, pacientes, atenciones, cie10, rips, auditoria):
    app.include_router(modulo.router)


@app.get("/api/salud", tags=["Sistema"])
def salud():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"estado": "ok", "ia": settings.IA_PROVEEDOR}
