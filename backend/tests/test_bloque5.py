"""RDA (Res. 1888/2025), inteligencia de negocio, módulos dinámicos y continuidad de negocio."""
from datetime import date

import pytest
from sqlalchemy import text

from app.core.database import engine
from app.services.rda import validar
from tests.conftest import token


@pytest.fixture(scope="module")
def jose(client, medico):
    return client.get("/api/pacientes", params={"q": "79888777"}, headers=medico).json()[0]


def test_rda_automatico_al_firmar(client, medico, auditor, jose):
    a = client.post("/api/atenciones", json={"paciente_id": jose["id"], "motivo_consulta": "Control HTA",
                    "signos_vitales": {"ta_sistolica": 140, "ta_diastolica": 90},
                    "diagnosticos": [{"codigo_cie10": "I10X", "tipo_diagnostico": "03"}],
                    "prescripciones": [{"medicamento": "Losartán 50 mg", "dosis": "1", "frecuencia": "c/12h",
                                        "duracion_dias": 30, "cantidad": 60}]}, headers=medico).json()
    client.post(f"/api/atenciones/{a['id']}/firmar", headers=medico)
    cola = client.get("/api/rda", headers=auditor).json()
    envio = next(e for e in cola if e["entidad_id"] == a["id"])
    assert envio["tipo"] == "consulta" and envio["estado"] == "simulado" and not envio["errores_validacion"]
    bundle = client.get(f"/api/rda/{envio['id']}", headers=medico).json()
    assert bundle["type"] == "document" and bundle["entry"][0]["resource"]["resourceType"] == "Composition"
    tipos = {e["resource"]["resourceType"] for e in bundle["entry"]}
    assert {"Patient", "Practitioner", "Organization", "Encounter", "Condition", "MedicationRequest", "DocumentReference"} <= tipos
    comp = bundle["entry"][0]["resource"]
    codigos = {s["code"]["coding"][0]["code"] for s in comp["section"]}
    assert {"48768-6", "10160-0", "48765-2", "11450-4"} <= codigos  # secciones oficiales de CompositionAmbulatoryRDA
    assert comp["attester"][0]["mode"] == "legal"
    assert validar(bundle) == []
    assert client.get("/api/rda/resumen", headers=auditor).json()["por_estado"]["simulado"] >= 1


def test_rda_validacion_detecta_errores():
    malo = {"resourceType": "Bundle", "type": "collection",
            "entry": [{"fullUrl": "urn:uuid:1", "resource": {"resourceType": "Patient", "id": "1", "managingOrganization": {"reference": "urn:uuid:x"}}}]}
    errores = validar(malo)
    assert any("document" in e for e in errores) and any("Composition" in e for e in errores)
    assert any("Referencias" in e for e in errores)


def test_rda_paciente(client, medico, jose):
    r = client.post(f"/api/rda/paciente/{jose['id']}", headers=medico).json()
    assert not r["errores_validacion"], r
    assert r["estado"] == "pendiente"


def test_bi(client, auditor, medico, facturacion):
    ds = {d["clave"]: d for d in client.get("/api/bi/datasets", headers=auditor).json()}
    assert {"atenciones", "citas", "facturacion", "hospitalizacion", "farmacia", "urgencias", "laboratorio"} <= set(ds)
    assert "facturacion" not in {d["clave"] for d in client.get("/api/bi/datasets", headers=medico).json()}
    c = {"dataset": "atenciones", "dimensiones": ["capitulo_cie10", "sexo"], "medidas": ["conteo", "pacientes", "valor"],
         "desde": "2020-01-01", "hasta": date.today().isoformat()}
    r = client.post("/api/bi/consultar", json=c, headers=auditor).json()
    assert r["filas"] and any(f["capitulo_cie10"] == "IX Circulatorio" for f in r["filas"])
    assert r["registros_analizados"] >= 1
    # Seguridad: dimensiones no declaradas y conjuntos sin permiso
    assert client.post("/api/bi/consultar", json={**c, "dimensiones": ["numero_documento"]}, headers=auditor).status_code == 422
    assert client.post("/api/bi/consultar", json={"dataset": "facturacion"}, headers=medico).status_code == 403
    # Filtros y exportación
    f = client.post("/api/bi/consultar", json={**c, "dimensiones": ["sexo"], "filtros": {"sexo": "H"}}, headers=auditor).json()
    assert all(x["sexo"] == "H" for x in f["filas"])
    x = client.post("/api/bi/exportar", params={"formato": "xlsx"}, json=c, headers=auditor)
    assert x.status_code == 200 and x.content[:2] == b"PK"
    assert "Capítulo CIE-10" in client.post("/api/bi/exportar", params={"formato": "csv"}, json=c, headers=auditor).content.decode("utf-8-sig")
    # Reporte guardado y compartido con facturación
    g = client.post("/api/bi/reportes", json={"nombre": "Atenciones por capítulo", "definicion": c, "roles": ["medico"]},
                    headers=auditor)
    assert g.status_code == 201
    rid = g.json()["id"]
    assert any(r["id"] == rid for r in client.get("/api/bi/reportes", headers=medico).json())
    assert not any(r["id"] == rid for r in client.get("/api/bi/reportes", headers=facturacion).json())
    assert client.get(f"/api/bi/reportes/{rid}/ejecutar", headers=medico).json()["nombre"] == "Atenciones por capítulo"


def test_modulos_dinamicos(client, admin, medico, auditor, jose):
    enf = token(client, "enfermeria@xentra.co")
    assert client.post("/api/modulos/plantillas/riesgo_caidas/instalar", headers=medico).status_code == 403
    m = client.post("/api/modulos/plantillas/riesgo_caidas/instalar", headers=admin)
    assert m.status_code == 201 and m.json()["sellar_al_guardar"]
    # Módulo propio creado desde cero
    nuevo = {"clave": "tamizaje_visual", "nombre": "Tamizaje visual escolar", "categoria": "asistencial",
             "roles_lectura": ["medico"], "roles_escritura": ["enfermeria"],
             "campos": [{"clave": "agudeza_od", "etiqueta": "Agudeza OD", "tipo": "seleccion", "requerido": True,
                         "opciones": ["20/20", "20/40", "20/80"]},
                        {"clave": "remitido", "etiqueta": "Remitido a optometría", "tipo": "si_no"}]}
    assert client.post("/api/modulos", json=nuevo, headers=admin).status_code == 201
    malo = {**nuevo, "clave": "malo", "campos": [{"clave": "X Mal", "tipo": "texto"}]}
    assert client.post("/api/modulos", json=malo, headers=admin).status_code == 422
    # Registro con validación
    base = {"paciente_id": jose["id"]}
    assert client.post("/api/modulos/riesgo_caidas/registros", json={**base, "datos": {"puntaje": 50}},
                       headers=enf).status_code == 422  # faltan obligatorios
    assert client.post("/api/modulos/riesgo_caidas/registros", json={**base, "datos": {
        "antecedente_caidas": True, "puntaje": 999, "nivel_riesgo": "Alto"}}, headers=enf).status_code == 422  # fuera de rango
    r = client.post("/api/modulos/riesgo_caidas/registros", json={**base, "datos": {
        "antecedente_caidas": True, "puntaje": 55, "nivel_riesgo": "Alto", "medidas": ["Barandas arriba"]}}, headers=enf)
    assert r.status_code == 201 and r.json()["sellado"]
    assert client.put(f"/api/modulos/riesgo_caidas/registros/{r.json()['id']}", json={**base, "datos": {
        "antecedente_caidas": False, "puntaje": 10, "nivel_riesgo": "Bajo"}}, headers=enf).status_code == 409
    assert client.post("/api/modulos/tamizaje_visual/registros", json={**base, "datos": {"agudeza_od": "20/40"}},
                       headers=medico).status_code == 403  # médico solo lectura
    assert client.post("/api/modulos/tamizaje_visual/registros", json={**base, "datos": {"agudeza_od": "20/40", "remitido": True}},
                       headers=enf).status_code == 201
    assert len(client.get("/api/modulos/tamizaje_visual/registros", headers=medico).json()) == 1
    # El módulo aparece en el BI automáticamente
    q = client.post("/api/bi/consultar", json={"dataset": "modulo:riesgo_caidas", "dimensiones": ["nivel_riesgo"],
                    "medidas": ["conteo", "prom_puntaje"], "desde": "2020-01-01"}, headers=auditor).json()
    assert q["filas"][0]["nivel_riesgo"] == "Alto" and q["filas"][0]["prom_puntaje"] == 55
    if engine.dialect.name == "postgresql":
        with pytest.raises(Exception):
            with engine.begin() as conn:
                conn.execute(text("UPDATE registros_modulo SET sellado=false WHERE sellado"))


def test_soporte_y_continuidad(client, admin, medico):
    # Código de error trazable en todas las respuestas
    assert len(client.get("/api/auth/yo", headers=medico).headers["X-Codigo-Error"]) == 10
    # Mesa de ayuda con ANS
    t = client.post("/api/sistema/tickets", json={"titulo": "No imprime la fórmula", "descripcion": "Al dar PDF fórmula sale error",
                    "prioridad": "critica", "modulo": "Historia clínica", "codigo_error": "ABC123"}, headers=medico).json()
    horas = (__import__("datetime").datetime.fromisoformat(t["vence_en"]) - __import__("datetime").datetime.fromisoformat(t["creado_en"]))
    assert round(horas.total_seconds() / 3600) == 4
    assert client.patch(f"/api/sistema/tickets/{t['id']}", json={"estado": "resuelto"}, headers=medico).status_code == 403
    assert client.patch(f"/api/sistema/tickets/{t['id']}", json={"estado": "resuelto"}, headers=admin).status_code == 422
    ok = client.patch(f"/api/sistema/tickets/{t['id']}", json={"estado": "resuelto", "solucion": "Habilitar ventanas emergentes"},
                      headers=admin).json()
    assert ok["estado"] == "resuelto"
    assert any("emergentes" in k["solucion"] for k in client.get("/api/sistema/base-conocimiento", params={"q": "fórmula"},
                                                                      headers=medico).json())
    # Avisos
    client.post("/api/sistema/avisos", json={"nivel": "aviso", "mensaje": "Mantenimiento el sábado 10 p. m."}, headers=admin)
    assert any("Mantenimiento" in a["mensaje"] for a in client.get("/api/sistema/avisos", headers=medico).json())
    # Estado del sistema
    e = client.get("/api/sistema/estado", headers=admin).json()
    assert e["base_datos"]["estado"] == "ok" and "respaldos" in e and "integraciones" in e
    assert client.get("/api/sistema/estado", headers=medico).status_code == 403
    # Modo contingencia
    pdf = client.get("/api/sistema/contingencia", headers=medico)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")


def test_rda_perfiles_oficiales_y_dispensacion(client, medico, auditor, jose):
    farmacia = token(client, "farmacia@xentra.co")
    # Consulta externa usa el perfil oficial CompositionAmbulatoryRDA
    cola = client.get("/api/rda", headers=auditor).json()
    consulta = next(e for e in cola if e["tipo"] == "consulta")
    comp = client.get(f"/api/rda/{consulta['id']}", headers=medico).json()["entry"][0]["resource"]
    assert comp["meta"]["profile"] == ["https://fhir.minsalud.gov.co/rda/StructureDefinition/CompositionAmbulatoryRDA"]
    # Dispensar una fórmula genera el RDA de dispensación (Res. 1799 de 2026)
    a = client.post("/api/atenciones", json={"paciente_id": jose["id"], "motivo_consulta": "Dolor", "diagnosticos": [{"codigo_cie10": "R529"}],
                    "prescripciones": [{"medicamento": "Acetaminofén 500 mg tableta", "dosis": "1", "frecuencia": "c/8h",
                                        "duracion_dias": 3, "cantidad": 9}]}, headers=medico).json()
    client.post(f"/api/atenciones/{a['id']}/firmar", headers=medico)
    prod = next(p for p in client.get("/api/farmacia/productos", headers=farmacia).json() if p["nombre"].startswith("Acetaminofén"))
    r = client.post("/api/farmacia/dispensar", json={"producto_id": prod["id"], "cantidad": 9,
                    "prescripcion_id": a["prescripciones"][0]["id"]}, headers=farmacia)
    assert r.status_code == 201
    disp = next(e for e in client.get("/api/rda", headers=auditor).json() if e["tipo"] == "dispensacion")
    assert not disp["errores_validacion"], disp
    recurso = client.get(f"/api/rda/{disp['id']}", headers=medico).json()
    assert recurso["resourceType"] == "MedicationDispense"
    assert recurso["meta"]["profile"] == ["https://fhir.minsalud.gov.co/rda/StructureDefinition/MedicationDispenseRDA"]
    assert recurso["quantity"]["value"] == 9 and recurso["authorizingPrescription"] and recurso["contained"][0]["batch"]
    resumen = client.get("/api/rda/resumen", headers=auditor).json()
    assert resumen["plazos"]["rda_dispensacion"]["obligatorio_desde"] == "2027-03-01"


def test_estado_blockchain_visible_para_personal(client, medico, facturacion):
    for h in (medico, facturacion):
        r = client.get("/api/auditoria/estado-cadena", headers=h).json()
        assert "valida" in r and r["total_bloques"] > 0 and "folios_sellados" in r
