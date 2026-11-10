"""Roles normativos y controles de acceso: admin técnico sin HC, auditor de sistemas, estudiante con refrendo,
auxiliar de laboratorio, registro profesional, cambio de clave obligatorio, MFA por rol y portal desactivable."""
import pytest

from app.core.config import settings
from app.services import mfa
from tests.conftest import token

CLAVE = "Temporal123*"


def crear(client, admin, email, rol, registro=None, doc="1"):
    r = client.post("/api/auth/usuarios", json={"numero_documento": doc, "nombres": rol.title(), "apellidos": "Prueba",
                    "email": email, "password": CLAVE, "rol": rol, "registro_profesional": registro}, headers=admin)
    assert r.status_code in (201, 409), r.text
    return token(client, email, CLAVE)


@pytest.fixture(scope="module")
def jose(client, medico):
    return client.get("/api/pacientes", params={"q": "79888777"}, headers=medico).json()[0]


def test_registro_profesional_obligatorio(client, admin):
    for rol in ("enfermeria", "laboratorio", "farmacia", "auditor", "medico"):
        r = client.post("/api/auth/usuarios", json={"numero_documento": "9", "nombres": "Sin", "apellidos": "Registro",
                        "email": f"sinreg.{rol}@xentra.co", "password": CLAVE, "rol": rol}, headers=admin)
        assert r.status_code == 422, rol


def test_admin_tecnico_sin_historia_clinica(client, admin, jose):
    h = crear(client, admin, "sistemas.prueba@xentra.co", "admin_tecnico", doc="101")
    # Gestiona usuarios, sedes, módulos, avisos y seguridad
    assert client.get("/api/auth/usuarios", headers=h).status_code == 200
    assert client.post("/api/sedes", json={"nombre": "Sede Sur", "cod_habilitacion": "110010000099"}, headers=h).status_code == 201
    assert client.get("/api/auditoria/verificar-cadena", headers=h).status_code == 200
    assert client.get("/api/sistema/estado", headers=h).status_code == 200
    # No accede a pacientes, historias, FHIR ni RDA con contenido clínico
    for url in ("/api/pacientes", f"/api/pacientes/{jose['id']}/historia", f"/fhir/Patient/{jose['id']}",
                f"/api/pacientes/{jose['id']}/resumen-ia"):
        assert client.get(url, headers=h).status_code == 403, url
    # Ve la ocupación de camas sin identificar pacientes
    camas = client.get("/api/camas", headers=h).json()
    assert all(c["paciente"] in (None, "Ocupada") for c in camas)
    # No puede crear un 'admin' completo (escalamiento de privilegios)
    r = client.post("/api/auth/usuarios", json={"numero_documento": "102", "nombres": "Escala", "apellidos": "Privilegio",
                    "email": "escala@xentra.co", "password": CLAVE, "rol": "admin"}, headers=h)
    assert r.status_code == 403


def test_auditor_sistemas(client, admin, jose):
    h = crear(client, admin, "auditoria.ti@xentra.co", "auditor_sistemas", doc="103")
    assert client.get("/api/auditoria/ledger", headers=h).status_code == 200
    assert client.get("/api/reportes/indicadores", headers=h).status_code == 200
    assert client.get(f"/api/pacientes/{jose['id']}", headers=h).status_code == 403
    assert client.get("/api/reportes/sivigila", headers=h).status_code == 403  # identifica pacientes


def test_estudiante_y_refrendo_docente(client, admin, medico, auditor, jose):
    h = crear(client, admin, "interno@xentra.co", "estudiante", registro="COD-EST-2026", doc="104")
    a = client.post("/api/atenciones", json={"paciente_id": jose["id"], "motivo_consulta": "Cefalea tensional",
                    "diagnosticos": [{"codigo_cie10": "G442"}]}, headers=h)
    assert a.status_code == 201
    a = a.json()
    assert client.post(f"/api/atenciones/{a['id']}/firmar", headers=h).status_code == 403  # no firma
    assert client.post("/api/hospitalizaciones", json={}, headers=h).status_code in (403, 422)
    pend = client.get("/api/atenciones/refrendo/pendientes", headers=medico).json()
    assert any(p["id"] == a["id"] for p in pend)
    # El docente revisa, corrige y refrenda
    assert client.put(f"/api/atenciones/{a['id']}", json={"motivo_consulta": "Cefalea tensional episódica",
                      "diagnosticos": [{"codigo_cie10": "G442"}]}, headers=medico).status_code == 200
    f = client.post(f"/api/atenciones/{a['id']}/firmar", headers=medico).json()
    assert f["estado"] == "firmada" and f["supervisor"]["email"] == "medico@xentra.co"
    v = client.get(f"/api/atenciones/{a['id']}/verificar", headers=auditor).json()
    assert v["integra"] is True
    pdf = client.get(f"/api/atenciones/{a['id']}/pdf", headers=medico)
    assert pdf.status_code == 200
    # Otro estudiante no puede refrendar
    assert client.get("/api/atenciones/refrendo/pendientes", headers=h).status_code == 403


def test_auxiliar_laboratorio_no_valida(client, admin, medico, jose):
    aux = crear(client, admin, "aux.lab@xentra.co", "auxiliar_laboratorio", doc="105")
    o = client.post("/api/ordenes-servicio", json={"paciente_id": jose["id"], "tipo": "laboratorio", "cod_cups": "903841",
                    "descripcion": "Glucosa"}, headers=medico).json()
    assert client.post(f"/api/ordenes-servicio/{o['id']}/toma", headers=aux).status_code == 200
    assert client.post(f"/api/ordenes-servicio/{o['id']}/resultado", json={"resultados": [
        {"analito": "Glucosa", "valor": "95", "referencia": "70-100"}]}, headers=aux).status_code == 200
    assert client.post(f"/api/ordenes-servicio/{o['id']}/validar", headers=aux).status_code == 403
    assert client.post(f"/api/ordenes-servicio/{o['id']}/validar", headers=token(client, "laboratorio@xentra.co")).status_code == 200


def test_cambio_de_clave_obligatorio(client, admin, monkeypatch):
    monkeypatch.setattr(settings, "CAMBIO_CLAVE_PRIMER_INGRESO", True)
    h = crear(client, admin, "nuevo.ingreso@xentra.co", "admisiones", doc="106")
    yo = client.get("/api/auth/yo", headers=h).json()
    assert yo["debe_cambiar_clave"] is True
    bloqueado = client.get("/api/pacientes", headers=h)
    assert bloqueado.status_code == 403 and "contraseña temporal" in bloqueado.json()["detail"]
    assert client.post("/api/auth/cambiar-clave", json={"actual": CLAVE, "nueva": CLAVE}, headers=h).status_code == 422
    assert client.post("/api/auth/cambiar-clave", json={"actual": CLAVE, "nueva": "Definitiva123*"}, headers=h).status_code == 204
    assert client.get("/api/pacientes", headers=h).status_code == 200


def test_mfa_obligatorio_por_rol(client, admin, monkeypatch):
    monkeypatch.setattr(settings, "MFA_OBLIGATORIO_ROLES", "facturacion")
    h = crear(client, admin, "fact.mfa@xentra.co", "facturacion", doc="107")
    assert client.get("/api/auth/yo", headers=h).json()["mfa_obligatorio"] is True
    assert client.get("/api/facturas", headers=h).status_code == 403
    cfg = client.post("/api/auth/mfa/configurar", headers=h).json()
    client.post("/api/auth/mfa/activar", json={"codigo": mfa.codigo_actual(cfg["secreto"])}, headers=h)
    assert client.get("/api/facturas", headers=h).status_code == 200


def test_portal_desactivado(client, admin, monkeypatch, jose):
    monkeypatch.setattr(settings, "PORTAL_PACIENTE_ACTIVO", False)
    assert client.post(f"/api/pacientes/{jose['id']}/acceso-portal", headers=admin).status_code == 403
    assert client.get("/api/salud").json()["portal_paciente"] is False
