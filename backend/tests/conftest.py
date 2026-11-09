"""Configuración de pruebas.

Por defecto usa SQLite (no requiere nada instalado). Para probar contra PostgreSQL real
(incluye los triggers de inmutabilidad):
    TEST_DATABASE_URL=postgresql+psycopg://usuario:clave@localhost:5432/xentra_test pytest
"""
import os
import tempfile

_ruta = os.path.join(tempfile.gettempdir(), "xentra_test.sqlite3")
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", f"sqlite:///{_ruta}")
os.environ["CARGAR_DATOS_DEMO"] = "true"
os.environ["IA_PROVEEDOR"] = "local"
os.environ["ADMIN_PASSWORD"] = "Admin12345*"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    Base.metadata.drop_all(engine)
    with TestClient(app) as c:
        yield c


def token(client, email, password="Demo12345*"):
    r = client.post("/api/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="session")
def medico(client):
    return token(client, "medico@xentra.co")


@pytest.fixture(scope="session")
def facturacion(client):
    return token(client, "facturacion@xentra.co")


@pytest.fixture(scope="session")
def auditor(client):
    return token(client, "auditor@xentra.co")


@pytest.fixture(scope="session")
def admin(client):
    return token(client, "admin@xentra.co", "Admin12345*")
