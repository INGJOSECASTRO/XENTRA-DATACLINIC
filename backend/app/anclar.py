"""Ancla el ledger. Programe una vez al día (cron):  python -m app.anclar"""
from app.core.database import SessionLocal
from app.services.anclaje import anclar

if __name__ == "__main__":
    import app.models_ext  # noqa: F401

    with SessionLocal() as db:
        a = anclar(db)
        print(f"Bloque {a.bloque_id} anclado ({a.proveedor}): {a.estado} {a.hash_raiz}")
