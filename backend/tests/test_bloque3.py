"""Urgencias/triage, hospitalización completa, farmacia FEFO, laboratorio y consentimientos."""
import pytest
from sqlalchemy import text

from app.core.database import engine
from app.services.hospital import marcar_anormales, sugerir_triage
from tests.conftest import token

FIRMA = "data:image/png;base64," + "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==" * 2


@pytest.fixture(scope="module")
def h(client):
    return {r: token(client, f"{r}@xentra.co") for r in ("medico", "enfermeria", "farmacia", "laboratorio", "facturacion")}


@pytest.fixture(scope="module")
def jose(client, h):
    return client.get("/api/pacientes", params={"q": "79888777"}, headers=h["medico"]).json()[0]


def test_reglas_triage():
    assert sugerir_triage("dolor en el pecho", {"spo2": 96})[0] == 2
    assert sugerir_triage("caída", {"spo2": 82})[0] == 1
    assert sugerir_triage("renovar fórmula", {})[0] == 5
    assert sugerir_triage("tos leve", {})[0] == 4
    r = marcar_anormales([{"analito": "Glucosa", "valor": "180", "referencia": "70 - 100"},
                          {"analito": "Hb", "valor": "13,5", "referencia": "12-16"}, {"analito": "Aspecto", "valor": "claro"}])
    assert [x["anormal"] for x in r] == [True, False, None]


def test_urgencias(client, h, jose):
    s = client.post("/api/urgencias/triage/sugerir", json={"paciente_id": jose["id"], "motivo": "Dolor torácico opresivo",
                                                           "signos_vitales": {"ta_sistolica": 150}}, headers=h["enfermeria"]).json()
    assert s["nivel"] == 2 and s["tiempo_maximo_min"] == 30
    t1 = client.post("/api/urgencias/triage", json={"paciente_id": jose["id"], "motivo": "Tos leve"}, headers=h["enfermeria"]).json()
    t2 = client.post("/api/urgencias/triage", json={"paciente_id": jose["id"], "motivo": "Dolor torácico"},
                     headers=h["enfermeria"]).json()
    cola = client.get("/api/urgencias/cola", headers=h["medico"]).json()
    orden = [c["id"] for c in cola]
    assert orden.index(t2["id"]) < orden.index(t1["id"])  # el nivel II pasa primero
    assert client.post(f"/api/urgencias/triage/{t2['id']}/finalizar", headers=h["medico"]).status_code == 409
    assert client.post(f"/api/urgencias/triage/{t2['id']}/atender", headers=h["medico"]).json()["estado"] == "en_atencion"
    assert client.post(f"/api/urgencias/triage/{t2['id']}/finalizar", headers=h["medico"]).json()["estado"] == "finalizado"
    assert client.post("/api/urgencias/triage", json={"paciente_id": jose["id"], "motivo": "x x"},
                       headers=h["facturacion"]).status_code == 403


def test_hospitalizacion_y_farmacia(client, h, jose):
    camas = client.get("/api/camas", headers=h["medico"]).json()
    libre = next(c for c in camas if c["estado"] == "disponible" and c["servicio"] == "adultos")
    r = client.post("/api/hospitalizaciones", json={"paciente_id": jose["id"], "cama_id": libre["id"], "motivo": "Neumonía",
                                                    "dx_ingreso": "J189", "valor_estancia_dia": 250000}, headers=h["medico"])
    assert r.status_code == 201, r.text
    hosp = r.json()
    assert client.post("/api/hospitalizaciones", json={"paciente_id": jose["id"], "cama_id": libre["id"], "motivo": "x x x",
                                                       "dx_ingreso": "J189"}, headers=h["medico"]).status_code == 409
    hid = hosp["id"]
    # Evoluciones
    assert client.post(f"/api/hospitalizaciones/{hid}/evoluciones", json={"tipo": "medica", "texto": "Evoluciona bien"},
                       headers=h["enfermeria"]).status_code == 403
    assert client.post(f"/api/hospitalizaciones/{hid}/evoluciones", json={"tipo": "enfermeria", "texto": "Paciente tranquilo",
                       "signos_vitales": {"spo2": 89}}, headers=h["enfermeria"]).status_code == 201
    # Órdenes con seguridad: José no tiene alergias; producto del inventario
    productos = client.get("/api/farmacia/productos", headers=h["farmacia"]).json()
    acet = next(p for p in productos if p["nombre"].startswith("Acetaminofén"))
    o = client.post(f"/api/hospitalizaciones/{hid}/ordenes", json={"tipo": "medicamento", "descripcion": "1 g",
                    "producto_id": acet["id"], "dosis": "1 g", "via": "oral", "frecuencia": "c/8h"}, headers=h["medico"]).json()
    # Kárdex
    assert client.post(f"/api/ordenes-medicas/{o['id']}/administrar", json={"estado": "omitido"},
                       headers=h["enfermeria"]).status_code == 422
    k = client.post(f"/api/ordenes-medicas/{o['id']}/administrar", json={"dosis_administrada": "1 g"}, headers=h["enfermeria"])
    assert len(k.json()["administraciones"]) == 1
    # Balance de líquidos
    client.post(f"/api/hospitalizaciones/{hid}/balance", json={"tipo": "ingreso", "via": "intravenosa", "cantidad_ml": 1000},
                headers=h["enfermeria"])
    b = client.post(f"/api/hospitalizaciones/{hid}/balance", json={"tipo": "egreso", "via": "orina", "cantidad_ml": 600},
                    headers=h["enfermeria"]).json()
    assert b["balance_ml"] == 400
    det = client.get(f"/api/hospitalizaciones/{hid}", headers=h["medico"]).json()
    assert any("Saturación" in a for a in det["alertas"])
    # Farmacia: pendientes y dispensación FEFO
    pend = client.get("/api/farmacia/pendientes", headers=h["farmacia"]).json()
    assert any(x["orden_id"] == o["id"] for x in pend["ordenes"])
    client.post("/api/farmacia/entradas", json={"producto_id": acet["id"], "lote": "PRONTO", "cantidad": 5,
                "vencimiento": "2030-01-01"}, headers=h["farmacia"])
    stock_antes = next(p for p in client.get("/api/farmacia/productos", headers=h["farmacia"]).json() if p["id"] == acet["id"])["stock"]
    movs = client.post("/api/farmacia/dispensar", json={"producto_id": acet["id"], "cantidad": 3, "orden_id": o["id"]},
                       headers=h["farmacia"])
    assert movs.status_code == 201, movs.text
    assert client.post("/api/farmacia/dispensar", json={"producto_id": acet["id"], "cantidad": 99999, "orden_id": o["id"]},
                       headers=h["farmacia"]).status_code == 409
    stock = next(p for p in client.get("/api/farmacia/productos", headers=h["farmacia"]).json() if p["id"] == acet["id"])["stock"]
    assert stock == stock_antes - 3
    assert client.post("/api/farmacia/dispensar", json={"producto_id": acet["id"], "cantidad": 1, "orden_id": o["id"]},
                       headers=h["medico"]).status_code == 403
    assert "stock_bajo" in client.get("/api/farmacia/alertas", headers=h["farmacia"]).json()
    # Egreso con epicrisis
    assert client.post(f"/api/hospitalizaciones/{hid}/egreso", json={"condicion_egreso": "02", "dx_egreso": "J189",
                       "epicrisis": "Paciente que fallece por complicaciones respiratorias."}, headers=h["medico"]).status_code == 422
    e = client.post(f"/api/hospitalizaciones/{hid}/egreso", json={"condicion_egreso": "01", "dx_egreso": "J189",
                    "dx_relacionados_egreso": ["I10X"], "epicrisis": "Paciente con neumonía que mejora con antibiótico IV. Egreso."},
                    headers=h["medico"]).json()
    assert e["estado"] == "egresada" and len(e["hash_epicrisis"]) == 64
    assert client.post(f"/api/hospitalizaciones/{hid}/evoluciones", json={"tipo": "enfermeria", "texto": "tarde"},
                       headers=h["enfermeria"]).status_code == 409
    pdf = client.get(f"/api/hospitalizaciones/{hid}/epicrisis.pdf", headers=h["medico"])
    assert pdf.content.startswith(b"%PDF")
    v = client.get(f"/api/publico/verificar/epicrisis/{hid}", params={"h": e["hash_epicrisis"]}).json()
    assert v["valido"] is True
    # La cama queda en limpieza
    cama = next(c for c in client.get("/api/camas", headers=h["medico"]).json() if c["id"] == libre["id"])
    assert cama["estado"] == "mantenimiento"
    # Facturar la hospitalización: estancia + medicamento dispensado -> RIPS con hospitalización y medicamentos
    f = client.post("/api/facturas", json={"nombre_pagador": "EPS Demo", "cod_eapb": "EPS002", "hospitalizacion_ids": [hid]},
                    headers=h["facturacion"]).json()
    tipos = sorted(i["tipo"] for i in f["items"])
    assert tipos == ["estancia", "medicamento"]
    em = client.post(f"/api/facturas/{f['id']}/emitir", headers=h["facturacion"])
    assert em.status_code == 200, em.text
    rips = client.get(f"/api/facturas/{f['id']}/rips", headers=h["facturacion"]).json()
    serv = rips["usuarios"][0]["servicios"]
    assert serv["hospitalizacion"][0]["codDiagnosticoPrincipalE"] == "J189"
    assert serv["medicamentos"][0]["cantidadMedicamento"] == 3
    if engine.dialect.name == "postgresql":
        with pytest.raises(Exception):
            with engine.begin() as conn:
                conn.execute(text("UPDATE hospitalizaciones SET epicrisis='alterada' WHERE estado='egresada'"))
        with pytest.raises(Exception):
            with engine.begin() as conn:
                conn.execute(text("DELETE FROM evoluciones"))


def test_formula_consulta_dispensacion(client, h, jose):
    a = client.post("/api/atenciones", json={"paciente_id": jose["id"], "motivo_consulta": "HTA", "diagnosticos": [{"codigo_cie10": "I10X"}],
                    "prescripciones": [{"medicamento": "Losartán 50 mg tableta", "dosis": "1", "frecuencia": "c/12h",
                                        "duracion_dias": 30, "cantidad": 60}]}, headers=h["medico"]).json()
    rx = a["prescripciones"]
    los = next(p for p in client.get("/api/farmacia/productos", headers=h["farmacia"]).json() if p["nombre"].startswith("Losartán"))
    # sin firmar no se dispensa
    pend = client.get("/api/farmacia/pendientes", headers=h["farmacia"]).json()["formulas"]
    assert not any(x["prescripcion_id"] == rx[0]["id"] for x in pend)
    client.post(f"/api/atenciones/{a['id']}/firmar", headers=h["medico"])
    pend = client.get("/api/farmacia/pendientes", headers=h["farmacia"]).json()["formulas"]
    item = next(x for x in pend if x["prescripcion_id"] == rx[0]["id"])
    assert item["cantidad"] == 60
    ok = client.post("/api/farmacia/dispensar", json={"producto_id": los["id"], "cantidad": 60, "prescripcion_id": item["prescripcion_id"]},
                     headers=h["farmacia"])
    assert ok.status_code == 201, ok.text
    assert client.post("/api/farmacia/dispensar", json={"producto_id": los["id"], "cantidad": 1,
                       "prescripcion_id": item["prescripcion_id"]}, headers=h["farmacia"]).status_code == 422


def test_laboratorio(client, h, jose):
    o = client.post("/api/ordenes-servicio", json={"paciente_id": jose["id"], "tipo": "laboratorio", "cod_cups": "903841",
                    "descripcion": "Glucosa", "prioridad": "urgente"}, headers=h["medico"]).json()
    assert client.post(f"/api/ordenes-servicio/{o['id']}/validar", headers=h["laboratorio"]).status_code == 409
    client.post(f"/api/ordenes-servicio/{o['id']}/toma", headers=h["laboratorio"])
    r = client.post(f"/api/ordenes-servicio/{o['id']}/resultado", json={"resultados": [
        {"analito": "Glucosa", "valor": "182", "unidad": "mg/dL", "referencia": "70-100"}]}, headers=h["laboratorio"]).json()
    assert r["resultados"][0]["anormal"] is True
    v = client.post(f"/api/ordenes-servicio/{o['id']}/validar", headers=h["laboratorio"]).json()
    assert v["estado"] == "validada"
    assert client.post(f"/api/ordenes-servicio/{o['id']}/resultado", json={"informe": "cambio"},
                       headers=h["laboratorio"]).status_code == 409
    assert client.get(f"/api/publico/verificar/resultado/{o['id']}", params={"h": v["hash_resultado"]}).json()["valido"]


def test_consentimiento(client, h, jose):
    pl = client.get("/api/consentimientos/plantillas", headers=h["medico"]).json()["telemedicina"]
    c = client.post("/api/consentimientos", json={"paciente_id": jose["id"], "plantilla": "telemedicina", "titulo": pl["titulo"],
                    "texto": pl["texto"], "firmante_nombre": "José Rodríguez", "firmante_documento": "79888777",
                    "firma_imagen": FIRMA}, headers=h["medico"])
    assert c.status_code == 201, c.text
    c = c.json()
    assert client.get(f"/api/consentimientos/{c['id']}/pdf", headers=h["medico"]).content.startswith(b"%PDF")
    assert client.get(f"/api/publico/verificar/consentimiento/{c['id']}", params={"h": c["hash_contenido"]}).json()["valido"]
    assert len(client.get(f"/api/pacientes/{jose['id']}/consentimientos", headers=h["medico"]).json()) >= 1
    malo = client.post("/api/consentimientos", json={"paciente_id": jose["id"], "plantilla": "x", "titulo": "xxx",
                       "texto": "x" * 30, "firmante_nombre": "abc", "firmante_documento": "123",
                       "firma_imagen": "data:image/jpeg;base64," + "A" * 200}, headers=h["medico"])
    assert malo.status_code == 422
