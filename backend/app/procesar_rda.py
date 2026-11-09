"""Procesa la cola de RDA pendientes (reintentos). Programe cada 5-10 minutos: python -m app.procesar_rda"""
from app.core.database import SessionLocal
from app.services.rda import procesar_pendientes

if __name__ == "__main__":
    import app.models_ext  # noqa: F401

    with SessionLocal() as db:
        print(procesar_pendientes(db))
