"""Prueba de punta a punta: paciente -> atención -> IA CIE-10 -> firma -> inmutabilidad -> RIPS -> ledger."""
import pytest
from sqlalchemy import text

from app.core.database import engine

PACIENTE = {
    "tipo_documento": "CC", "numero_documento": "123456789", "primer_nombre": "Pedro",
    "primer_apellido": "Prueba", "fecha_nacimiento": "1970-05-10", "sexo": "H",
    "cod_municipio_residencia": "11001", "autoriza_tratamiento_datos": True,
}


@pytest.fixture(scope="module")
def paciente(client, medico):
    r = client.post("/api/pacientes", json=PACIENTE, headers=medico)
    assert r.status_code == 201, r.text
    return r.json()


def test_salud(client):
    assert client.get("/api/salud").json()["estado"] == "ok"


def test_login_incorrecto(client):
    r = client.post("/api/auth/login", data={"username": "medico@xentra.co", "password": "malo"})
    assert r.status_code == 401


def test_sin_token_no_hay_acceso(client):
    assert client.get("/api/pacientes").status_code == 401


def test_paciente_duplicado(client, medico, paciente):
    assert client.post("/api/pacientes", json=PACIENTE, headers=medico).status_code == 409


def test_buscar_cie10(client, medico):
    r = client.get("/api/cie10", params={"q": "hipertension"}, headers=medico)
    assert any(c["codigo"] == "I10X" for c in r.json())
    r = client.get("/api/cie10", params={"q": "E11"}, headers=medico)
    assert r.json()[0]["codigo"].startswith("E11")


@pytest.mark.parametrize("texto,esperado", [
    ("Paciente con gripa, mocos y estornudos hace 2 días", "J00X"),
    ("Consulta por presión alta, cifras de 160/100 en casa", "I10X"),
    ("Ardor al orinar y polaquiuria desde ayer", "N390"),
    ("Dolor lumbar tras levantar peso", "M545"),
])
def test_ia_local_sugiere(client, medico, paciente, texto, esperado):
    r = client.post("/api/cie10/sugerir", json={"texto": texto, "paciente_id": paciente["id"]}, headers=medico)
    assert r.status_code == 200, r.text
    codigos = [s["codigo"] for s in r.json()["sugerencias"]]
    assert esperado in codigos[:3], codigos


def test_ia_respeta_sexo(client, medico, paciente):
    r = client.post("/api/cie10/sugerir", json={"texto": "control prenatal embarazo", "paciente_id": paciente["id"]},
                    headers=medico)
    assert not any(s["codigo"].startswith(("O", "Z34")) for s in r.json()["sugerencias"])


def test_rbac(client, facturacion, auditor, paciente):
    datos = {"paciente_id": paciente["id"], "motivo_consulta": "dolor"}
    assert client.post("/api/atenciones", json=datos, headers=facturacion).status_code == 403
    assert client.post("/api/atenciones", json=datos, headers=auditor).status_code == 403


def test_flujo_completo(client, medico, facturacion, auditor, admin, paciente):
    atencion = {
        "paciente_id": paciente["id"],
        "motivo_consulta": "Control de presión alta",
        "enfermedad_actual": "Hipertenso conocido, cefalea ocasional",
        "signos_vitales": {"ta_sistolica": 150, "ta_diastolica": 95, "fc": 80, "peso": 80, "talla": 170},
        "analisis": "HTA no controlada",
        "plan": "Ajuste de medicación",
        "valor_servicio": 45000,
        "diagnosticos": [{"codigo_cie10": "I10"}, {"codigo_cie10": "R51X", "tipo_diagnostico": "02"}],
        "procedimientos": [{"cod_cups": "903841", "descripcion": "Glucosa en suero", "valor": 8000}],
        "prescripciones": [{"medicamento": "Losartán 50 mg tableta", "dosis": "1 tableta",
                            "frecuencia": "cada 12 horas", "duracion_dias": 30, "cantidad": 60}],
    }
    # Diagnóstico no pertinente por sexo -> rechazado
    malo = {**atencion, "diagnosticos": [{"codigo_cie10": "N760"}]}
    assert client.post("/api/atenciones", json=malo, headers=medico).status_code == 422

    r = client.post("/api/atenciones", json=atencion, headers=medico)
    assert r.status_code == 201, r.text
    a = r.json()
    assert a["estado"] == "borrador" and a["consecutivo"] == 1
    assert a["diagnosticos"][0]["codigo_cie10"] == "I10X"
    assert any("Tensión arterial elevada" in x for x in a["alertas"])

    # RIPS con atención en borrador -> errores
    r = client.post("/api/rips/generar", json={"num_factura": "FE100", "atencion_ids": [a["id"]]}, headers=facturacion)
    assert r.json()["valido"] is False

    # Firmar
    r = client.post(f"/api/atenciones/{a['id']}/firmar", headers=medico)
    assert r.status_code == 200, r.text
    firmada = r.json()
    assert firmada["estado"] == "firmada" and len(firmada["hash_contenido"]) == 64

    # Inmutable vía API
    assert client.put(f"/api/atenciones/{a['id']}", json=atencion, headers=medico).status_code == 409
    assert client.delete(f"/api/atenciones/{a['id']}", headers=medico).status_code == 409

    # Verificación de integridad
    v = client.get(f"/api/atenciones/{a['id']}/verificar", headers=auditor).json()
    assert v["integra"] is True

    # Nota aclaratoria
    r = client.post(f"/api/atenciones/{a['id']}/notas", json={"texto": "Se aclara: TA tomada en brazo izquierdo"},
                    headers=medico)
    assert r.status_code == 201

    # RIPS válido
    r = client.post("/api/rips/generar", json={"num_factura": "FE100", "atencion_ids": [a["id"]]}, headers=facturacion)
    cuerpo = r.json()
    assert cuerpo["valido"] is True, cuerpo["errores"]
    rips = cuerpo["rips"]
    usuario = rips["usuarios"][0]
    consulta = usuario["servicios"]["consultas"][0]
    assert rips["numFactura"] == "FE100" and usuario["codSexo"] == "H"
    assert consulta["codDiagnosticoPrincipal"] == "I10X" and consulta["codDiagnosticoRelacionado1"] == "R51X"
    assert consulta["vrServicio"] == 45000
    assert usuario["servicios"]["procedimientos"][0]["codProcedimiento"] == "903841"

    r = client.post("/api/rips/descargar", json={"num_factura": "FE100", "atencion_ids": [a["id"]]}, headers=facturacion)
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]

    # Cadena del ledger íntegra
    cadena = client.get("/api/auditoria/verificar-cadena", headers=auditor).json()
    assert cadena["valida"] is True and cadena["total_bloques"] > 5
    assert client.get("/api/auditoria/verificar-cadena", headers=medico).status_code == 403

    # Manipulación directa en la BD
    if engine.dialect.name == "postgresql":
        # PostgreSQL bloquea la alteración con triggers
        with pytest.raises(Exception):
            with engine.begin() as conn:
                conn.execute(text("UPDATE atenciones SET analisis='alterado' WHERE estado='firmada'"))
        with pytest.raises(Exception):
            with engine.begin() as conn:
                conn.execute(text("DELETE FROM ledger_bloques WHERE id = 1"))
    else:
        # Sin triggers (SQLite): la alteración se DETECTA por hash
        with engine.begin() as conn:
            conn.execute(text("UPDATE atenciones SET analisis='alterado' WHERE id=:i"), {"i": a["id"].replace("-", "")})
            conn.execute(text("UPDATE ledger_bloques SET accion='OTRA' WHERE id = 2"))
        v = client.get(f"/api/atenciones/{a['id']}/verificar", headers=auditor).json()
        assert v["integra"] is False
        cadena = client.get("/api/auditoria/verificar-cadena", headers=auditor).json()
        assert cadena["valida"] is False and cadena["bloque_con_error"] == 2


def test_bloqueo_por_intentos(client, admin):
    nuevo = {"numero_documento": "555", "nombres": "Test", "apellidos": "Bloqueo", "email": "bloqueo@xentra.co",
             "password": "Clave12345*", "rol": "admisiones"}
    assert client.post("/api/auth/usuarios", json=nuevo, headers=admin).status_code == 201
    for _ in range(5):
        client.post("/api/auth/login", data={"username": "bloqueo@xentra.co", "password": "mala"})
    r = client.post("/api/auth/login", data={"username": "bloqueo@xentra.co", "password": "Clave12345*"})
    assert r.status_code == 423


def test_password_debil(client, admin):
    nuevo = {"numero_documento": "556", "nombres": "Test", "apellidos": "Debil", "email": "debil@xentra.co",
             "password": "123", "rol": "admisiones"}
    assert client.post("/api/auth/usuarios", json=nuevo, headers=admin).status_code == 422
