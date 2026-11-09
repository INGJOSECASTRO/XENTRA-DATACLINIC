"""FHIR R4, portal del paciente, resumen IA, indicadores, SIVIGILA y anclaje del ledger."""
import pytest

from app.services.fhir import cie10_internacional
from tests.conftest import token


@pytest.fixture(scope="module")
def maria(client, medico):
    return client.get("/api/pacientes", params={"q": "1020304050"}, headers=medico).json()[0]


def test_cie10_fhir():
    assert cie10_internacional("I10X") == "I10" and cie10_internacional("E119") == "E11.9"


def test_fhir(client, medico, maria, facturacion):
    assert client.get("/fhir/metadata").json()["fhirVersion"] == "4.0.1"
    b = client.get("/fhir/Patient", params={"identifier": "CC|1020304050"}, headers=medico)
    assert b.headers["content-type"].startswith("application/fhir+json")
    pat = b.json()["entry"][0]["resource"]
    assert pat["gender"] == "female" and pat["identifier"][0]["value"] == "1020304050"
    todo = client.get(f"/fhir/Patient/{maria['id']}/$everything", headers=medico).json()
    tipos = {e["resource"]["resourceType"] for e in todo["entry"]}
    assert {"Patient", "Encounter", "Condition", "MedicationRequest", "AllergyIntolerance", "Practitioner"} <= tipos
    cond = client.get("/fhir/Condition", params={"patient": maria["id"]}, headers=medico).json()
    assert cond["entry"][0]["resource"]["code"]["coding"][0]["system"] == "http://hl7.org/fhir/sid/icd-10"
    assert client.get("/fhir/Patient/00000000-0000-0000-0000-000000000000", headers=medico).status_code == 404
    assert client.get(f"/fhir/Patient/{maria['id']}", headers=facturacion).status_code == 403


def test_portal_paciente(client, admin, medico, maria):
    # María (demo) no tiene correo: primero se registra
    assert client.post(f"/api/pacientes/{maria['id']}/acceso-portal", headers=admin).status_code == 422
    client.patch(f"/api/pacientes/{maria['id']}", json={"email": "maria.lopez@correo.co"}, headers=medico)
    r = client.post(f"/api/pacientes/{maria['id']}/acceso-portal", headers=admin)
    assert r.status_code == 201
    clave = r.json()["clave_temporal"]
    assert client.post(f"/api/pacientes/{maria['id']}/acceso-portal", headers=admin).status_code == 409
    yo = token(client, "maria.lopez@correo.co", clave)
    res = client.get("/api/portal/resumen", headers=yo).json()
    assert res["paciente"]["documento"] == "CC 1020304050" and res["estructurado"]["alergias"] == "Penicilina"
    atenciones = client.get("/api/portal/atenciones", headers=yo).json()
    assert atenciones
    assert client.get(f"/api/portal/atenciones/{atenciones[0]['id']}/pdf", headers=yo).content.startswith(b"%PDF")
    accesos = client.get("/api/portal/accesos", headers=yo).json()
    assert any(a["rol"] == "medico" for a in accesos)
    exp = client.get("/api/portal/exportar", headers=yo)
    assert exp.json()["resourceType"] == "Bundle"
    # El paciente NO puede usar endpoints del personal ni ver a otros pacientes
    for url in ("/api/pacientes", "/api/catalogos", "/api/auditoria/estadisticas", f"/fhir/Patient/{maria['id']}"):
        assert client.get(url, headers=yo).status_code == 403, url
    otra = client.get("/api/pacientes", params={"q": "79888777"}, headers=medico).json()[0]
    jose_atenciones = client.get(f"/api/pacientes/{otra['id']}/historia", headers=medico).json()
    if jose_atenciones:
        assert client.get(f"/api/portal/atenciones/{jose_atenciones[0]['id']}/pdf", headers=yo).status_code == 404


def test_resumen_ia_e_indicadores(client, medico, admin, auditor, maria):
    r = client.get(f"/api/pacientes/{maria['id']}/resumen-ia", headers=medico).json()
    assert r["proveedor"] == "local" and r["estructurado"]["problemas_activos"]
    ind = client.get("/api/reportes/indicadores", headers=auditor).json()
    for clave in ("agenda", "urgencias", "hospitalizacion", "consulta", "facturacion"):
        assert clave in ind
    assert ind["consulta"]["atenciones_firmadas"] > 0
    assert client.get("/api/reportes/indicadores", headers=medico).status_code == 403
    siv = client.get("/api/reportes/sivigila", headers=medico).json()
    assert any(x["evento"] == "Dengue" for x in siv)
    csv = client.get("/api/reportes/sivigila", params={"formato": "csv"}, headers=medico)
    assert "Dengue" in csv.content.decode("utf-8-sig")


def test_anclaje(client, auditor):
    a = client.post("/api/auditoria/anclar", headers=auditor).json()
    assert a["proveedor"] == "local" and len(a["hash"]) == 64
    lista = client.get("/api/auditoria/anclajes", headers=auditor).json()
    assert lista[-1]["coincide"] is True
