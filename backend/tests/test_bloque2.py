"""Agenda, telemedicina, facturación, pre-auditoría, DIAN y MUV (modo simulado)."""
from datetime import date, datetime, timedelta, timezone

import pytest

from tests.conftest import token


@pytest.fixture(scope="module")
def admisiones(client):
    return token(client, "admisiones@xentra.co")


@pytest.fixture(scope="module")
def ids(client, medico):
    yo = client.get("/api/auth/yo", headers=medico).json()
    jose = client.get("/api/pacientes", params={"q": "79888777"}, headers=medico).json()[0]
    sofia = client.get("/api/pacientes", params={"q": "1122334455"}, headers=medico).json()[0]
    return {"medico": yo["id"], "jose": jose["id"], "sofia": sofia["id"]}


def manana(hora: int) -> str:
    d = date.today() + timedelta(days=1)
    return f"{d.isoformat()}T{hora:02d}:00:00"


def test_agenda_completa(client, admisiones, medico, ids):
    base = {"paciente_id": ids["jose"], "profesional_id": ids["medico"], "inicio": manana(9), "motivo": "Control HTA"}
    r = client.post("/api/citas", json=base, headers=admisiones)
    assert r.status_code == 201, r.text
    cita = r.json()
    # Cruce de horario del profesional
    otro = {**base, "paciente_id": ids["sofia"], "inicio": manana(9).replace(":00:00", ":10:00")}
    assert client.post("/api/citas", json=otro, headers=admisiones).status_code == 409
    # Telemedicina genera sala virtual
    tele = client.post("/api/citas", json={**base, "paciente_id": ids["sofia"], "inicio": manana(10),
                                           "modalidad": "telemedicina"}, headers=admisiones).json()
    assert tele["sala_virtual"].startswith("https://meet.jit.si/xentra-")
    # Pasado no permitido
    assert client.post("/api/citas", json={**base, "inicio": "2020-01-01T08:00:00"}, headers=admisiones).status_code == 422
    # Disponibilidad excluye las 9:00
    disp = client.get("/api/citas/disponibilidad", params={"profesional_id": ids["medico"],
                      "fecha": (date.today() + timedelta(days=1)).isoformat()}, headers=admisiones).json()
    assert not any("T09:00" in x for x in disp["libres"]) and any("T11:00" in x for x in disp["libres"])
    # Lista del día
    lista = client.get("/api/citas", params={"desde": (date.today() + timedelta(days=1)).isoformat()}, headers=admisiones).json()
    assert len(lista) >= 2
    # Transiciones
    assert client.patch(f"/api/citas/{cita['id']}/estado", json={"estado": "atendida"}, headers=admisiones).status_code == 409
    assert client.patch(f"/api/citas/{tele['id']}/estado", json={"estado": "cancelada"}, headers=admisiones).status_code == 422
    assert client.patch(f"/api/citas/{tele['id']}/estado", json={"estado": "cancelada", "motivo_cancelacion": "Viaje"},
                        headers=admisiones).json()["estado"] == "cancelada"
    # Reprogramar
    r = client.post(f"/api/citas/{cita['id']}/reprogramar", json={"inicio": manana(14)}, headers=admisiones)
    assert r.status_code == 200
    # Recordatorios
    rec = client.post("/api/citas/recordatorios", headers=admisiones).json()
    assert rec["total"] >= 1
    # Llega a sala y el médico la atiende
    client.patch(f"/api/citas/{cita['id']}/estado", json={"estado": "en_sala"}, headers=admisiones)
    a = client.post("/api/atenciones", json={"paciente_id": ids["jose"], "cita_id": cita["id"], "motivo_consulta": "Control",
                                             "diagnosticos": [{"codigo_cie10": "I10X"}]}, headers=medico)
    assert a.status_code == 201
    estado = client.get("/api/citas", params={"desde": (date.today() + timedelta(days=1)).isoformat(),
                                              "paciente_id": ids["jose"]}, headers=admisiones).json()[0]
    assert estado["estado"] == "atendida" and estado["atencion_id"] == a.json()["id"]


def test_facturacion_completa(client, medico, facturacion, ids):
    atenciones = []
    for i in range(2):
        a = client.post("/api/atenciones", json={
            "paciente_id": ids["jose"], "motivo_consulta": f"Consulta {i}", "valor_servicio": 45000,
            "valor_pago_moderador": 4000 if i == 0 else 0, "num_autorizacion": "AUT-1",
            "diagnosticos": [{"codigo_cie10": "I10X", "tipo_diagnostico": "03"}],
            "procedimientos": [{"cod_cups": "903841", "descripcion": "Glucosa", "valor": 8000}]}, headers=medico).json()
        client.post(f"/api/atenciones/{a['id']}/firmar", headers=medico)
        atenciones.append(a["id"])
    pend = client.get("/api/facturas/pendientes", headers=facturacion).json()
    assert all(x in [p["id"] for p in pend["atenciones"]] for x in atenciones)
    datos = {"tipo_pagador": "eps", "cod_eapb": "EPS002", "nit_pagador": "800000002", "nombre_pagador": "EPS Demo",
             "atencion_ids": atenciones}
    r = client.post("/api/facturas", json=datos, headers=facturacion)
    assert r.status_code == 201, r.text
    f = r.json()
    assert f["estado"] == "borrador" and float(f["subtotal"]) == 106000 and float(f["total"]) == 102000
    assert any("duplicidad" in h["mensaje"] for h in f["hallazgos_auditoria"])
    # No se puede facturar dos veces lo mismo
    assert client.post("/api/facturas", json=datos, headers=facturacion).status_code == 422
    # Emitir (DIAN simulado) -> CUFE, consecutivo y RIPS
    e = client.post(f"/api/facturas/{f['id']}/emitir", headers=facturacion)
    assert e.status_code == 200, e.text
    e = e.json()
    assert e["estado"] == "emitida" and len(e["cufe"]) == 96 and e["numero"].startswith("FEV")
    rips = client.get(f"/api/facturas/{f['id']}/rips", headers=facturacion).json()
    assert rips["numFactura"] == e["numero"] and len(rips["usuarios"][0]["servicios"]["consultas"]) == 2
    # MUV simulado -> CUV
    m = client.post(f"/api/facturas/{f['id']}/enviar-muv", headers=facturacion).json()
    assert m["estado"] == "validada" and m["cuv"]
    # Emitida no se anula
    assert client.post(f"/api/facturas/{f['id']}/anular", json={"motivo": "error de prueba"}, headers=facturacion).status_code == 409
    # Médico no factura
    assert client.post("/api/facturas", json=datos, headers=medico).status_code == 403


def test_preauditoria_bloquea_errores(client, medico, facturacion, ids):
    a = client.post("/api/atenciones", json={"paciente_id": ids["sofia"], "motivo_consulta": "Tos", "valor_servicio": 0,
                                             "diagnosticos": [{"codigo_cie10": "R05X"}]}, headers=medico).json()
    client.post(f"/api/atenciones/{a['id']}/firmar", headers=medico)
    f = client.post("/api/facturas", json={"nombre_pagador": "EPS Demo", "cod_eapb": "EPS999", "atencion_ids": [a["id"]]},
                    headers=facturacion).json()
    niveles = [h["nivel"] for h in f["hallazgos_auditoria"]]
    assert "error" in niveles  # valor 0 y EPS distinta
    assert client.post(f"/api/facturas/{f['id']}/emitir", headers=facturacion).status_code == 422
    assert client.post(f"/api/facturas/{f['id']}/anular", json={"motivo": "Cuenta mal armada"},
                       headers=facturacion).json()["estado"] == "anulada"
    # Al anular, la atención vuelve a estar disponible
    pend = client.get("/api/facturas/pendientes", headers=facturacion).json()
    assert a["id"] in [p["id"] for p in pend["atenciones"]]


def test_rips_urgencias():
    from types import SimpleNamespace as N

    from app.services.rips import generar_rips
    pac = N(id="p1", tipo_documento="CC", numero_documento="1", tipo_usuario="01", fecha_nacimiento=date(1990, 1, 1),
            sexo="H", cod_pais_residencia="170", cod_municipio_residencia="11001", zona_territorial="02")
    prof = N(tipo_documento="CC", numero_documento="9")
    ahora = datetime.now(timezone.utc)
    a = N(id="a1", paciente_id="p1", paciente=pac, profesional=prof, consecutivo=1, estado="firmada", fecha_inicio=ahora,
          diagnosticos=[N(orden=0, codigo_cie10="S934", tipo_diagnostico="01")], procedimientos=[], tipo="urgencias",
          fecha_egreso=ahora + timedelta(hours=3), condicion_egreso="01", dx_causa_muerte=None, num_autorizacion=None,
          cod_consulta_cups="890701", modalidad_grupo_servicio="01", grupo_servicios="05", cod_servicio=501,
          finalidad_tecnologia="15", causa_motivo_atencion="26", valor_servicio=60000, concepto_recaudo="05",
          valor_pago_moderador=0)
    rips, errores = generar_rips([a], "FEV9")
    assert not errores
    urg = rips["usuarios"][0]["servicios"]["urgencias"][0]
    assert urg["condicionDestinoUsuarioEgreso"] == "01" and urg["codDiagnosticoPrincipalE"] == "S934"
    a.condicion_egreso = "02"
    _, errores = generar_rips([a], "FEV9")
    assert any("causa de muerte" in e for e in errores)
