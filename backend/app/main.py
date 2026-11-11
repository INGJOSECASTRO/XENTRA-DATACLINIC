"""Punto de entrada de la API. Ejecutar:  uvicorn app.main:app --reload"""
import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

import app.models_ext  # noqa: F401  (registra las tablas de los módulos)
from app.api import (administracion, agenda, bi, modulos, sistema, atenciones, auditoria, auth, cie10, facturacion, farmacia, fhir, hospital,
                     laboratorio, pacientes, portal, publico, rda, reportes, rips)
from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.core.inmutabilidad import instalar_triggers
from app.seed import inicializar

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.es_produccion and (problemas := settings.problemas_produccion()):
        for p in problemas:
            logging.critical("PRODUCCIÓN INSEGURA: %s", p)
        raise RuntimeError("XENTRA no arranca en ENTORNO=produccion con configuración insegura. Corrija el .env "
                           "(ver docs/15-paso-a-produccion.md) o ejecute scripts/preparar_produccion.py")
    if settings.AUTO_CREAR_TABLAS:  # desarrollo y pruebas; en producción las tablas las crea Alembic
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
    # En producción no se publica la documentación técnica de la API (reduce información para un atacante)
    docs_url=None if settings.es_produccion else "/docs",
    redoc_url=None if settings.es_produccion else "/redoc",
    openapi_url=None if settings.es_produccion else "/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_lista,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


log = logging.getLogger("xentra")


@app.exception_handler(Exception)
async def error_no_controlado(request: Request, exc: Exception):
    """Nunca muestra detalles técnicos al usuario; entrega un código para que soporte encuentre el error en el log."""
    codigo = getattr(request.state, "codigo", uuid.uuid4().hex[:10].upper())
    log.exception("ERROR %s en %s %s: %s", codigo, request.method, request.url.path, exc)
    return JSONResponse(status_code=500, content={
        "detail": f"Ocurrió un error inesperado. Reporte este código a soporte: {codigo}", "codigo_error": codigo},
        headers={"X-Codigo-Error": codigo})


@app.middleware("http")
async def cabeceras_seguridad(request: Request, call_next):
    request.state.codigo = uuid.uuid4().hex[:10].upper()  # ID de la petición (trazabilidad para soporte)
    respuesta = await call_next(request)
    respuesta.headers["X-Codigo-Error"] = request.state.codigo
    respuesta.headers["X-Content-Type-Options"] = "nosniff"
    respuesta.headers["X-Frame-Options"] = "DENY"
    respuesta.headers["Referrer-Policy"] = "no-referrer"
    respuesta.headers["Cache-Control"] = "no-store"  # datos clínicos: no guardar en caché
    return respuesta


for modulo in (auth, pacientes, atenciones, cie10, rips, auditoria, administracion, publico, agenda, facturacion,
               hospital, farmacia, laboratorio, fhir, portal, reportes, rda, bi, modulos, sistema):
    app.include_router(modulo.router)


@app.get("/api/salud", tags=["Sistema"])
def salud():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"estado": "ok", "ia": settings.IA_PROVEEDOR, "portal_paciente": settings.PORTAL_PACIENTE_ACTIVO}
