"""Protecciones del paso a producción: arranque seguro y lista de verificación."""
from pathlib import Path

from app.core.config import Settings

SEGURO = dict(ENTORNO="produccion", SECRET_KEY="x" * 64, LEDGER_HMAC_KEY="y" * 64, ADMIN_PASSWORD="ClaveReal2026*xyz",
              DATABASE_URL="postgresql+psycopg://xentra_app:k3yAleatoria@db/xentra_hce", CARGAR_DATOS_DEMO=False,
              AUTO_CREAR_TABLAS=False)


def test_configuracion_de_ejemplo_es_insegura():
    s = Settings(_env_file=None, ENTORNO="produccion")
    problemas = " ".join(s.problemas_produccion())
    for clave in ("SECRET_KEY", "LEDGER_HMAC_KEY", "ADMIN_PASSWORD", "CARGAR_DATOS_DEMO", "AUTO_CREAR_TABLAS"):
        assert clave in problemas


def test_configuracion_segura_no_tiene_problemas():
    s = Settings(_env_file=None, **SEGURO)
    assert s.es_produccion and s.problemas_produccion() == []


def test_clave_con_cambiar_es_rechazada():
    s = Settings(_env_file=None, **{**SEGURO, "SECRET_KEY": "CAMBIAR_clave_jwt_aleatoria_de_64_caracteres_xxxxxxxx"})
    assert any("SECRET_KEY" in p for p in s.problemas_produccion())


def test_verificador_detecta_lo_que_falta(client, tmp_path: Path):
    from app.verificar_produccion import CRITICO, revisar

    resultado = revisar(carpeta_respaldos=tmp_path)          # entorno de pruebas: debe encontrar pendientes
    criticos = " ".join(t for n, t in resultado if n == CRITICO)
    assert "ENTORNO" in criticos                              # no está en producción
    assert "demostración" in criticos                         # usuarios demo activos
    assert "CIE-10" in criticos                               # solo el catálogo de muestra
    assert "respaldo" in criticos                             # carpeta vacía
    assert any("ledger" in t for n, t in resultado)           # siempre informa el estado de la cadena


def test_admin_inicial_debe_cambiar_clave(client):
    from sqlalchemy import select

    from app.core.config import settings
    from app.core.database import SessionLocal
    from app.models import Usuario

    with SessionLocal() as db:
        admin = db.scalars(select(Usuario).where(Usuario.email == settings.ADMIN_EMAIL.lower())).one()
        assert admin.debe_cambiar_clave is True
