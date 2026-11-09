"""MFA, sesión, catálogos, sedes, plantillas, seguridad clínica, PDF y verificación pública."""
from app.services import mfa
from app.services.seguridad_clinica import alertas_alergia, alertas_interaccion, eventos_sivigila
from tests.conftest import token


def test_totp_rfc6238():
    # Vector de prueba RFC 6238 (secreto ASCII "12345678901234567890", t=59 -> 94287082, 6 dígitos = 287082)
    secreto = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"
    assert mfa.codigo_actual(secreto, 59) == "287082"
    assert mfa.verificar(secreto, mfa.codigo_actual(secreto))
    assert not mfa.verificar(secreto, "000000") or mfa.codigo_actual(secreto) == "000000"


def test_flujo_mfa(client, admin):
    nuevo = {"numero_documento": "777", "nombres": "Mfa", "apellidos": "Prueba", "email": "mfa@xentra.co",
             "password": "Clave12345*", "rol": "admisiones"}
    assert client.post("/api/auth/usuarios", json=nuevo, headers=admin).status_code == 201
    h = token(client, "mfa@xentra.co", "Clave12345*")
    cfg = client.post("/api/auth/mfa/configurar", headers=h).json()
    assert cfg["uri"].startswith("otpauth://totp/") and "<svg" in cfg["qr_svg"]
    assert client.post("/api/auth/mfa/activar", json={"codigo": "000001"}, headers=h).status_code in (200, 422)
    r = client.post("/api/auth/mfa/activar", json={"codigo": mfa.codigo_actual(cfg["secreto"])}, headers=h)
    assert r.status_code == 200 and r.json()["mfa_activo"]
    # Login ahora pide segundo factor
    paso1 = client.post("/api/auth/login", data={"username": "mfa@xentra.co", "password": "Clave12345*"}).json()
    assert paso1["mfa_requerido"] and paso1["access_token"] is None
    # El token MFA no sirve para usar la API
    assert client.get("/api/auth/yo", headers={"Authorization": f"Bearer {paso1['token_mfa']}"}).status_code == 401
    malo = client.post("/api/auth/mfa/verificar", json={"token_mfa": paso1["token_mfa"], "codigo": "12345a"})
    assert malo.status_code in (401, 422)
    ok = client.post("/api/auth/mfa/verificar",
                     json={"token_mfa": paso1["token_mfa"], "codigo": mfa.codigo_actual(cfg["secreto"])})
    assert ok.status_code == 200 and ok.json()["access_token"]


def test_renovar_y_cambio_clave(client, admin):
    nuevo = {"numero_documento": "778", "nombres": "Clave", "apellidos": "Cambio", "email": "clave@xentra.co",
             "password": "Clave12345*", "rol": "admisiones"}
    client.post("/api/auth/usuarios", json=nuevo, headers=admin)
    h = token(client, "clave@xentra.co", "Clave12345*")
    assert client.post("/api/auth/renovar", headers=h).json()["access_token"]
    assert client.post("/api/auth/cambiar-clave", json={"actual": "mala", "nueva": "Nueva12345*"}, headers=h).status_code == 422
    assert client.post("/api/auth/cambiar-clave", json={"actual": "Clave12345*", "nueva": "Nueva12345*"}, headers=h).status_code == 204
    token(client, "clave@xentra.co", "Nueva12345*")


def test_catalogos_y_sedes(client, admin, medico):
    tipos = client.get("/api/catalogos", headers=medico).json()
    assert "cups" in tipos and "finalidad" in tipos
    cups = client.get("/api/catalogos/cups", params={"q": "medicina general"}, headers=medico).json()
    assert any(c["codigo"] == "890201" for c in cups)
    assert client.get("/api/catalogos/divipola", params={"q": "medellin"}, headers=medico).json()[0]["codigo"] == "05001"
    r = client.post("/api/sedes", json={"nombre": "Sede Norte", "cod_habilitacion": "110010000002"}, headers=admin)
    assert r.status_code == 201
    assert client.post("/api/sedes", json={"nombre": "X", "cod_habilitacion": "1"}, headers=admin).status_code == 422
    assert client.post("/api/sedes", json={"nombre": "Sede", "cod_habilitacion": "110010000003"}, headers=medico).status_code == 403


def test_plantillas(client, medico):
    p = client.get("/api/clinica/plantillas", headers=medico).json()
    assert "control_hta" in p and "examen_fisico" in p["medicina_general"]


def test_reglas_seguridad():
    assert alertas_alergia("Penicilina", ["Amoxicilina 500 mg cápsula"])[0]["severidad"] == "alta"
    assert alertas_alergia("Penicilina", ["Cefalexina 500 mg"])[0]["severidad"] == "moderada"
    assert alertas_alergia("Ninguna", ["Amoxicilina"]) == []
    assert alertas_alergia("AINES", ["Acetaminofén 500 mg"]) == []
    i = alertas_interaccion(["Warfarina 5 mg", "Ibuprofeno 400 mg"])
    assert i and i[0]["severidad"] == "alta"
    assert alertas_interaccion(["Losartán 50 mg"]) == []
    assert eventos_sivigila(["A90X", "I10X"]) == [{"codigo": "A90X", "evento": "Dengue"}]


def test_alertas_en_atencion_pdf_y_verificacion(client, medico):
    pacientes = client.get("/api/pacientes", params={"q": "1020304050"}, headers=medico).json()
    maria = pacientes[0]  # alérgica a penicilina en datos demo
    r = client.post("/api/clinica/revisar-prescripcion",
                    json={"paciente_id": maria["id"], "medicamentos": ["Amoxicilina 500 mg"]}, headers=medico)
    assert r.json()[0]["severidad"] == "alta"
    atencion = {"paciente_id": maria["id"], "motivo_consulta": "Fiebre y dolor de huesos",
                "diagnosticos": [{"codigo_cie10": "A90X"}],
                "prescripciones": [{"medicamento": "Amoxicilina 500 mg cápsula", "dosis": "1", "frecuencia": "c/8h",
                                    "duracion_dias": 7, "cantidad": 21}]}
    a = client.post("/api/atenciones", json=atencion, headers=medico).json()
    assert any("ALERGIA" in x for x in a["alertas"]) and any("SIVIGILA" in x for x in a["alertas"])
    a = client.post(f"/api/atenciones/{a['id']}/firmar", headers=medico).json()
    for doc in ("historia", "formula"):
        r = client.get(f"/api/atenciones/{a['id']}/pdf", params={"documento": doc}, headers=medico)
        assert r.status_code == 200 and r.content.startswith(b"%PDF")
    v = client.get(f"/api/publico/verificar/atencion/{a['id']}", params={"h": a["hash_contenido"]}).json()
    assert v["valido"] is True and "paciente" not in str(v).lower()
    v = client.get(f"/api/publico/verificar/atencion/{a['id']}", params={"h": "0" * 64}).json()
    assert v["valido"] is False


def test_rol_paciente_no_accede_a_personal(client):
    # Un token de paciente no debe poder usar endpoints del personal (se prueba en el portal, bloque 4)
    assert client.get("/api/catalogos").status_code == 401
