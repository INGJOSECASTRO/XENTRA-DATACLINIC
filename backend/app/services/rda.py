"""Resumen Digital de Atención en Salud (RDA) - Resolución 1888 de 2025.

El RDA es un documento HL7 FHIR R4 (Bundle de tipo "document") cuya PRIMERA entrada es un único recurso
Composition, seguido de todos los recursos que referencia (Patient, Practitioner, Organization, Encounter,
Condition, MedicationRequest, Procedure, Observation, AllergyIntolerance). Se genera por evento de atención
(consulta externa, urgencias, hospitalización) y existe el RDA de paciente (antecedentes).

Fuentes de los identificadores (revisión de noviembre de 2026):
- Perfiles: guía FHIR RDA de la IHCE (vulcano.ihcecol.gov.co). URL canónica base
  https://fhir.minsalud.gov.co/rda/StructureDefinition/ con CompositionAmbulatoryRDA (consulta externa),
  CompositionEmergencyRDA (urgencias), CompositionHospitalizationRDA (hospitalización) y
  CompositionPatientStatementRDA (paciente).
- Operaciones: Manual de Operaciones de Interoperabilidad IHCE v1.3 (POST /Composition/$enviar-rda-...).
- Plazos: Res. 1888/2025 obligatoria desde el 15/04/2026; Res. 1799/2026 (dispensación) hasta el 01/03/2027.
POR CONFIRMAR en la guía vigente: el perfil y la operación del RDA de dispensación (Res. 1799 de 2026), y los
códigos de tipo de documento y de secciones. Todo es configurable (PERFILES / OPERACIONES / .env).
"""
import logging
import uuid
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Atencion, Paciente
from app.models_ext import Hospitalizacion, OrdenServicio, RdaEnvio
from app.services import fhir
from app.services.ledger import a_utc, json_canonico, sha256

log = logging.getLogger(__name__)

TIPOS = {
    "consulta": ("RDA-consulta-externa", "Resumen Digital de Atención - Consulta externa"),
    "urgencias": ("RDA-urgencias", "Resumen Digital de Atención - Urgencias"),
    "hospitalizacion": ("RDA-hospitalizacion", "Resumen Digital de Atención - Hospitalización"),
    "paciente": ("RDA-paciente", "Resumen Digital de Atención - Paciente (antecedentes)"),
    "dispensacion": ("RDA-dispensacion", "Resumen Digital de Atención - Dispensación de medicamentos"),
}
# Perfil Composition por tipo (guía FHIR RDA, IHCE)
PERFILES = {
    "consulta": "CompositionAmbulatoryRDA",
    "urgencias": "CompositionEmergencyRDA",
    "hospitalizacion": "CompositionHospitalizationRDA",
    "paciente": "CompositionPatientStatementRDA",
    "dispensacion": "CompositionDispensationRDA",  # POR CONFIRMAR en la guía vigente (Res. 1799 de 2026)
}
# Manual de Operaciones de Interoperabilidad IHCE v1.3
OPERACIONES = {
    "consulta": "Composition/$enviar-rda-consulta-externa",
    "urgencias": "Composition/$enviar-rda-urgencias",
    "hospitalizacion": "Composition/$enviar-rda-hospitalizacion",
    "paciente": "Composition/$enviar-rda-paciente",
    "dispensacion": "Composition/$enviar-rda-dispensacion",  # POR CONFIRMAR (convención de la Res. 1799)
}
PLAZOS = {
    "rda_clinico": {"norma": "Resolución 1888 de 2025", "obligatorio_desde": "2026-04-15"},
    "rda_dispensacion": {"norma": "Resolución 1799 de 2026", "obligatorio_desde": "2027-03-01"},
}
SIS_TIPO_RDA = "https://fhir.minsalud.gov.co/rda/CodeSystem/tipo-rda"  # verificar
LOINC_SECCIONES = {
    "motivo": ("29299-5", "Motivo de consulta"),
    "enfermedad": ("10164-2", "Enfermedad actual"),
    "alergias": ("48765-2", "Alergias e intolerancias"),
    "diagnosticos": ("29548-5", "Diagnósticos"),
    "medicamentos": ("10160-0", "Medicamentos"),
    "procedimientos": ("47519-4", "Procedimientos"),
    "signos": ("8716-3", "Signos vitales"),
    "resultados": ("30954-2", "Resultados de exámenes"),
    "plan": ("18776-5", "Plan de manejo"),
    "egreso": ("8648-8", "Curso hospitalario / epicrisis"),
    "dispensacion": ("60590-7", "Medicamentos dispensados"),
}


def _url(tipo: str, id_) -> str:
    return f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, f'xentra/{tipo}/{id_}')}"


def _organizacion() -> dict:
    return {"resourceType": "Organization", "id": "prestador",
            "identifier": [{"system": "https://www.dian.gov.co/nit", "value": settings.PRESTADOR_NIT},
                           {"system": "https://prestadores.minsalud.gov.co/habilitacion",
                            "value": settings.PRESTADOR_COD_HABILITACION}],
            "name": settings.PRESTADOR_RAZON_SOCIAL}


def _seccion(clave: str, recursos: list[dict], texto: str | None = None) -> dict | None:
    if not recursos and not texto:
        return None
    codigo, titulo = LOINC_SECCIONES[clave]
    s = {"title": titulo, "code": {"coding": [{"system": fhir.LOINC, "code": codigo, "display": titulo}]}}
    if texto:
        from html import escape

        s["text"] = {"status": "generated", "div": f'<div xmlns="http://www.w3.org/1999/xhtml">{escape(texto)}</div>'}
    if recursos:
        s["entry"] = [{"reference": f"{r['resourceType']}/{r['id']}"} for r in recursos]
    else:
        s["emptyReason"] = {"text": "Sin datos"}
    return s


def _empaquetar(tipo: str, composicion: dict, recursos: list[dict]) -> dict:
    """Arma el Bundle document y reescribe todas las referencias a urn:uuid internas."""
    todos = [composicion] + recursos
    vistos, unicos = set(), []
    for r in todos:
        clave = (r["resourceType"], r["id"])
        if clave not in vistos:
            vistos.add(clave)
            unicos.append(r)
    mapa = {f"{r['resourceType']}/{r['id']}": _url(r["resourceType"], r["id"]) for r in unicos}

    def reescribir(obj):
        if isinstance(obj, dict):
            return {k: (mapa.get(v, v) if k == "reference" and isinstance(v, str) else reescribir(v)) for k, v in obj.items()}
        if isinstance(obj, list):
            return [reescribir(x) for x in obj]
        return obj

    ahora = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return {
        "resourceType": "Bundle",
        "identifier": {"system": "urn:ietf:rfc:3986", "value": _url("Bundle", composicion["id"] + ahora)},
        "type": "document",
        "timestamp": ahora,
        "entry": [{"fullUrl": mapa[f"{r['resourceType']}/{r['id']}"], "resource": reescribir(r)} for r in unicos],
    }


def _composicion(tipo: str, id_, paciente, autor_id, fecha, encuentro_id, secciones: list) -> dict:
    perfil, titulo = TIPOS[tipo]
    c = {"resourceType": "Composition", "id": f"rda-{tipo}-{id_}",
         "meta": {"profile": [f"{settings.RDA_PERFIL_BASE.rstrip('/')}/{PERFILES[tipo]}"]},
         "status": "final",
         "type": {"coding": [{"system": SIS_TIPO_RDA, "code": perfil, "display": titulo},
                             {"system": fhir.LOINC, "code": "60591-5", "display": "Patient summary Document"}]},
         "subject": fhir.ref("Patient", paciente.id),
         "date": fecha, "author": [fhir.ref("Practitioner", autor_id)] if autor_id else [fhir.ref("Organization", "prestador")],
         "title": titulo, "custodian": fhir.ref("Organization", "prestador"),
         "section": [s for s in secciones if s]}
    if encuentro_id:
        c["encounter"] = fhir.ref("Encounter", encuentro_id)
    return c


def rda_atencion(a: Atencion, laboratorios: list[OrdenServicio] = ()) -> tuple[str, dict]:
    tipo = "urgencias" if a.tipo == "urgencias" else "consulta"
    p = a.paciente
    condiciones = [fhir.condition(d, a) for d in a.diagnosticos]
    meds = [fhir.medication_request(r, a) for r in a.prescripciones]
    procs = [fhir.procedure(x, a) for x in a.procedimientos]
    signos = fhir.observaciones_signos(a)
    labs = [o for lab in laboratorios for o in fhir.observaciones_laboratorio(lab)]
    alergia = [x for x in [fhir.alergia(p)] if x]
    encuentro = fhir.encounter_atencion(a)
    secciones = [
        _seccion("motivo", [], a.motivo_consulta), _seccion("enfermedad", [], a.enfermedad_actual),
        _seccion("alergias", alergia, None if alergia else "No refiere alergias conocidas"),
        _seccion("diagnosticos", condiciones), _seccion("medicamentos", meds), _seccion("procedimientos", procs),
        _seccion("signos", signos), _seccion("resultados", labs), _seccion("plan", [], a.plan),
    ]
    if tipo == "urgencias" and a.fecha_egreso:
        secciones.append(_seccion("egreso", [], f"Egreso {a_utc(a.fecha_egreso).isoformat()} - condición {a.condicion_egreso}"))
    comp = _composicion(tipo, a.id, p, a.profesional_id, fhir._fecha(a.firmada_en or a.fecha_inicio), a.id, secciones)
    recursos = [fhir.patient(p), fhir.practitioner(a.profesional), _organizacion(), encuentro, *alergia, *condiciones,
                *meds, *procs, *signos, *labs]
    return tipo, _empaquetar(tipo, comp, recursos)


def rda_hospitalizacion(h: Hospitalizacion) -> tuple[str, dict]:
    p = h.paciente
    from types import SimpleNamespace as N

    def cond(codigo, rol):
        d = N(id=f"{h.id}-{rol}-{codigo}", codigo_cie10=codigo, descripcion=rol, tipo_diagnostico="02")
        return fhir.condition(d, N(paciente_id=p.id, id=h.id, fecha_inicio=h.fecha_ingreso))

    dx = [cond(h.dx_ingreso, "ingreso")] + ([cond(h.dx_egreso, "egreso")] if h.dx_egreso else []) + \
         [cond(c, "relacionado") for c in (h.dx_relacionados_egreso or [])]
    alergia = [x for x in [fhir.alergia(p)] if x]
    secciones = [_seccion("motivo", [], h.motivo), _seccion("alergias", alergia, None if alergia else "No refiere alergias"),
                 _seccion("diagnosticos", dx), _seccion("egreso", [], h.epicrisis)]
    comp = _composicion("hospitalizacion", h.id, p, h.medico_id, fhir._fecha(h.fecha_egreso or h.fecha_ingreso), h.id, secciones)
    recursos = [fhir.patient(p), fhir.practitioner(h.medico), _organizacion(), fhir.encounter_hospitalizacion(h), *alergia, *dx]
    return "hospitalizacion", _empaquetar("hospitalizacion", comp, recursos)


def rda_paciente(p: Paciente, atenciones: list[Atencion]) -> tuple[str, dict]:
    alergia = [x for x in [fhir.alergia(p)] if x]
    condiciones, vistos = [], set()
    for a in atenciones:
        for d in a.diagnosticos:
            if d.codigo_cie10 not in vistos and d.tipo_diagnostico in ("02", "03"):
                vistos.add(d.codigo_cie10)
                c = fhir.condition(d, a)
                c.pop("encounter", None)  # antecedente del paciente: no se incluye la consulta de origen
                condiciones.append(c)
    antecedentes = "; ".join(f"{k}: {v}" for a in atenciones[-1:] for k, v in (a.antecedentes or {}).items() if v) or None
    secciones = [_seccion("alergias", alergia, None if alergia else "No refiere alergias"),
                 _seccion("diagnosticos", condiciones, None if condiciones else "Sin diagnósticos confirmados"),
                 _seccion("enfermedad", [], antecedentes)]
    comp = _composicion("paciente", p.id, p, None, datetime.now(timezone.utc).replace(microsecond=0).isoformat(), None, secciones)
    return "paciente", _empaquetar("paciente", comp, [fhir.patient(p), _organizacion(), *alergia, *condiciones])


def rda_dispensacion(movimientos: list, paciente, dispensador, prescripcion=None, atencion=None) -> tuple[str, dict]:
    """Res. 1799 de 2026: una entrega de farmacia (uno o varios lotes) ligada a la prescripción que la originó."""
    from types import SimpleNamespace as N

    primero = movimientos[0]
    dispensaciones, medicamentos = [], []
    for m in movimientos:
        prod = m.producto
        med = {"resourceType": "Medication", "id": f"med-{prod.id}",
               "code": {**({"coding": [{"system": fhir.SIS_CUM, "code": prod.cum}]} if prod.cum else {}), "text": prod.nombre},
               **({"batch": {"lotNumber": m.lote.numero, "expirationDate": m.lote.vencimiento.isoformat()}} if m.lote else {})}
        medicamentos.append(med)
        d = {"resourceType": "MedicationDispense", "id": str(m.id), "status": "completed",
             "medicationReference": fhir.ref("Medication", med["id"]), "subject": fhir.ref("Patient", paciente.id),
             "performer": [{"actor": fhir.ref("Practitioner", dispensador.id)}],
             "quantity": {"value": abs(m.cantidad), "unit": prod.unidad}, "whenHandedOver": fhir._fecha(m.fecha)}
        if prescripcion is not None and atencion is not None:
            d["authorizingPrescription"] = [fhir.ref("MedicationRequest", prescripcion.id)]
        dispensaciones.append(d)
    recursos = [fhir.patient(paciente), fhir.practitioner(dispensador), _organizacion(), *medicamentos, *dispensaciones]
    if prescripcion is not None and atencion is not None:
        orden = fhir.medication_request(prescripcion, atencion)
        orden.pop("encounter", None)  # la consulta de origen viaja en su propio RDA de consulta externa
        recursos += [orden, fhir.practitioner(atencion.profesional)]
    secciones = [_seccion("dispensacion", dispensaciones)]
    comp = _composicion("dispensacion", primero.id, paciente, dispensador.id, fhir._fecha(primero.fecha), None, secciones)
    return "dispensacion", _empaquetar("dispensacion", comp, recursos)


def validar(bundle: dict) -> list[str]:
    """Reglas estructurales del Manual de Operaciones IHCE (no sustituye la validación oficial)."""
    errores = []
    if bundle.get("resourceType") != "Bundle" or bundle.get("type") != "document":
        errores.append("Bundle.type debe ser 'document'")
    entradas = bundle.get("entry") or []
    if not entradas or entradas[0]["resource"].get("resourceType") != "Composition":
        errores.append("La primera entrada debe ser Composition")
    if sum(1 for e in entradas if e["resource"]["resourceType"] == "Composition") != 1:
        errores.append("Solo se permite un Composition por Bundle")
    urls = {e.get("fullUrl") for e in entradas}
    if None in urls:
        errores.append("Todas las entradas deben tener fullUrl")
    faltantes = set()

    def revisar(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == "reference" and isinstance(v, str) and v not in urls:
                    faltantes.add(v)
                else:
                    revisar(v)
        elif isinstance(obj, list):
            for x in obj:
                revisar(x)

    revisar([e["resource"] for e in entradas])
    if faltantes:
        errores.append(f"Referencias sin recurso en el Bundle: {sorted(faltantes)[:5]}")
    if not any(e["resource"]["resourceType"] == "Patient" for e in entradas):
        errores.append("Falta el recurso Patient")
    if entradas:
        comp = entradas[0]["resource"]
        if not comp.get("subject") or not comp.get("section"):
            errores.append("Composition sin subject o sin secciones")
        p = next((e["resource"] for e in entradas if e["resource"]["resourceType"] == "Patient"), {})
        if not p.get("identifier"):
            errores.append("El paciente no tiene identificación")
    return errores


def encolar(db: Session, tipo: str, entidad_id, paciente_id, bundle: dict) -> RdaEnvio | None:
    if settings.RDA_MODO == "desactivado":
        return None
    errores = validar(bundle)
    envio = RdaEnvio(tipo=tipo, entidad_id=str(entidad_id), paciente_id=paciente_id, bundle=bundle,
                     hash_bundle=sha256(json_canonico(bundle)), estado="error" if errores else "pendiente",
                     errores_validacion=errores or None)
    db.add(envio)
    db.flush()
    return envio


def _transmitir(envio: RdaEnvio) -> tuple[str, dict]:
    if settings.RDA_MODO == "simulado":
        return "simulado", {"resultado": "Aceptado (simulado: no se envió a la IHCE)",
                            "fecha": datetime.now(timezone.utc).isoformat()}
    if not settings.IHCE_URL:
        raise RuntimeError("Configure IHCE_URL e IHCE_TOKEN")
    r = httpx.post(f"{settings.IHCE_URL.rstrip('/')}/{OPERACIONES[envio.tipo]}", json=envio.bundle, timeout=60,
                   headers={"Authorization": f"Bearer {settings.IHCE_TOKEN}", "Content-Type": "application/fhir+json"})
    try:
        cuerpo = r.json()
    except ValueError:
        cuerpo = {"texto": r.text[:2000]}
    if r.status_code >= 400:
        raise RuntimeError(f"IHCE respondió {r.status_code}: {str(cuerpo)[:500]}")
    return "enviado", cuerpo


def procesar_pendientes(db: Session, forzar: bool = False) -> dict:
    """Envía la cola con reintentos y espera exponencial (2^intentos minutos). Seguro de ejecutar con cron."""
    ahora = datetime.now(timezone.utc)
    resumen = {"enviados": 0, "fallidos": 0, "omitidos": 0}
    for envio in db.scalars(select(RdaEnvio).where(RdaEnvio.estado == "pendiente").order_by(RdaEnvio.generado_en).limit(200)).all():
        if not forzar and envio.ultimo_intento and a_utc(envio.ultimo_intento) + timedelta(minutes=2 ** envio.intentos) > ahora:
            resumen["omitidos"] += 1
            continue
        envio.intentos += 1
        envio.ultimo_intento = ahora
        try:
            envio.estado, envio.respuesta = _transmitir(envio)
            resumen["enviados"] += 1
        except Exception as exc:  # la atención clínica nunca se bloquea por una falla de red
            envio.respuesta = {"error": str(exc)}
            if envio.intentos >= settings.RDA_MAX_INTENTOS:
                envio.estado = "error"
            resumen["fallidos"] += 1
            log.warning("RDA %s no enviado (intento %s): %s", envio.id, envio.intentos, exc)
    db.commit()
    return resumen
