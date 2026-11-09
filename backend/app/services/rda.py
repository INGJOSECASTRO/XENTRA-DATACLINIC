"""Resumen Digital de Atención en Salud (RDA) - Resolución 1888 de 2025 y Resolución 1799 de 2026.

RDA clínicos (paciente, consulta externa, urgencias, hospitalización): documento HL7 FHIR R4 (Bundle "document")
cuya PRIMERA entrada es un único Composition, seguido de todos los recursos que referencia.
RDA de dispensación: NO es un documento; se envía un recurso MedicationDispense con el perfil MedicationDispenseRDA
(operación "Enviar Dispensación" de Gestión Farmacéutica).

Fuentes oficiales verificadas (noviembre de 2026):
- Guía FHIR RDA v1.0.3 (vulcano.ihcecol.gov.co): URL canónica https://fhir.minsalud.gov.co/rda/StructureDefinition/,
  perfiles CompositionAmbulatoryRDA, CompositionEmergencyRDA, CompositionHospitalizationRDA,
  CompositionPatientStatementRDA y MedicationDispenseRDA, y las secciones con sus códigos LOINC (SECCIONES).
- Resolución 1888 de 2025 (art. 5): 6 meses desde el 15/10/2025 -> obligatoria desde el 15/04/2026.
- Manual de Operaciones de Interoperabilidad IHCE v1.3: POST /Composition/$enviar-rda-{tipo}.
Pendiente de confirmar con la IHCE al registrar la IPS: la ruta técnica de "Enviar Dispensación" (la guía describe
la operación pero no publica su OperationDefinition) -> variable RDA_OPERACION_DISPENSACION.
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
    "consulta": "Resumen Digital de Atención - Consulta externa",
    "urgencias": "Resumen Digital de Atención - Urgencias",
    "hospitalizacion": "Resumen Digital de Atención - Hospitalización",
    "paciente": "Resumen Digital de Atención - Paciente (antecedentes)",
    "dispensacion": "Resumen Digital de Atención - Dispensación de medicamentos",
}
PERFILES = {
    "consulta": "CompositionAmbulatoryRDA",
    "urgencias": "CompositionEmergencyRDA",
    "hospitalizacion": "CompositionHospitalizationRDA",
    "paciente": "CompositionPatientStatementRDA",
    "dispensacion": "MedicationDispenseRDA",
}
OPERACIONES = {
    "consulta": "Composition/$enviar-rda-consulta-externa",
    "urgencias": "Composition/$enviar-rda-urgencias",
    "hospitalizacion": "Composition/$enviar-rda-hospitalizacion",
    "paciente": "Composition/$enviar-rda-paciente",
    "dispensacion": None,  # settings.RDA_OPERACION_DISPENSACION (la asigna/confirma la IHCE)
}
PLAZOS = {
    "rda_clinico": {"norma": "Resolución 1888 de 2025 (art. 5)", "obligatorio_desde": "2026-04-15"},
    "rda_dispensacion": {"norma": "Resolución 1799 de 2026 (transitorio)", "obligatorio_desde": "2027-03-01"},
}
# Secciones oficiales de la guía: clave -> (slice, código LOINC, título)
SECCIONES = {
    "pagadores": ("sectionPayers", "48768-6", "Entidad(es) responsable(s) por el plan de beneficios en salud"),
    "medicamentos": ("sectionMedications", "10160-0", "Historial de medicamentos"),
    "alergias": ("sectionAllergies", "48765-2", "Historial de alergias, intolerancias y reacciones adversas"),
    "problemas": ("sectionProblems", "11450-4", "Historial de diagnósticos de problemas de salud"),
    "triage": ("sectionTriage", "54094-8", "Clasificación de triaje"),
    "procedimientos": ("sectionProceduresHx", "47519-4", "Historial de procedimientos"),
    "resultados": ("sectionResults", "30954-2", "Resultados del uso de las tecnologías en salud"),
    "ordenes": ("sectionServiceRequests", "61146-1", "Órdenes, prescripciones o solicitudes de servicio"),
    "notas": ("sectionClarificationNotes", "34109-9", "Notas aclaratorias"),
    "soportes": ("sectionAddendumDocuments", "55107-7", "Documentos de soporte"),
    "familiares": ("sectionFamilyMemberHistory", "10157-6", "Historial de antecedentes familiares"),
}
# Secciones que admite cada perfil (según la guía)
SECCIONES_POR_TIPO = {
    "consulta": ["pagadores", "medicamentos", "alergias", "problemas", "ordenes", "notas", "soportes"],
    "urgencias": ["pagadores", "medicamentos", "alergias", "problemas", "triage", "procedimientos", "resultados",
                  "ordenes", "notas", "soportes"],
    "hospitalizacion": ["pagadores", "medicamentos", "alergias", "problemas", "procedimientos", "resultados",
                        "ordenes", "notas", "soportes"],
    "paciente": ["medicamentos", "alergias", "problemas", "familiares"],
}
# Tipo de documento (Composition.type, ValueSet c80-doc-typecodes de LOINC)
TIPO_DOCUMENTO = {
    "consulta": ("34133-9", "Summary of episode note"), "urgencias": ("34133-9", "Summary of episode note"),
    "hospitalizacion": ("18842-5", "Discharge summary"), "paciente": ("60591-5", "Patient summary Document"),
}


def _url(tipo: str, id_) -> str:
    return f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, f'xentra/{tipo}/{id_}')}"


def _perfil(tipo: str) -> str:
    return f"{settings.RDA_PERFIL_BASE.rstrip('/')}/{PERFILES[tipo]}"


def _organizacion() -> dict:
    return {"resourceType": "Organization", "id": "prestador",
            "identifier": [{"system": "https://www.dian.gov.co/nit", "value": settings.PRESTADOR_NIT},
                           {"system": "https://prestadores.minsalud.gov.co/habilitacion",
                            "value": settings.PRESTADOR_COD_HABILITACION}],
            "name": settings.PRESTADOR_RAZON_SOCIAL}


def _eapb(paciente) -> list[dict]:
    if not paciente.cod_eapb:
        return []
    return [{"resourceType": "Organization", "id": f"eapb-{paciente.cod_eapb}",
             "identifier": [{"system": "https://www.minsalud.gov.co/eapb", "value": paciente.cod_eapb}],
             "type": [{"text": "Entidad Administradora de Planes de Beneficios"}], "name": paciente.cod_eapb}]


def _seccion(clave: str, recursos: list[dict], texto: str | None = None) -> dict:
    slice_, codigo, titulo = SECCIONES[clave]
    s = {"id": slice_, "title": titulo, "code": {"coding": [{"system": fhir.LOINC, "code": codigo, "display": titulo}]}}
    if texto:
        from html import escape

        s["text"] = {"status": "generated", "div": f'<div xmlns="http://www.w3.org/1999/xhtml">{escape(texto)}</div>'}
    if recursos:
        s["entry"] = [{"reference": f"{r['resourceType']}/{r['id']}"} for r in recursos]
    else:
        s["emptyReason"] = {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/list-empty-reason",
                                        "code": "nilknown", "display": "Nil Known"}]}
    return s


def _empaquetar(composicion: dict, recursos: list[dict]) -> dict:
    """Arma el Bundle document y reescribe todas las referencias a urn:uuid internas."""
    vistos, unicos = set(), []
    for r in [composicion] + recursos:
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
    return {"resourceType": "Bundle", "identifier": {"system": "urn:ietf:rfc:3986", "value": _url("Bundle", composicion["id"] + ahora)},
            "type": "document", "timestamp": ahora,
            "entry": [{"fullUrl": mapa[f"{r['resourceType']}/{r['id']}"], "resource": reescribir(r)} for r in unicos]}


def _composicion(tipo: str, id_, paciente, autor_id, fecha, encuentro_id, contenido: dict[str, tuple]) -> dict:
    """contenido: clave de sección -> (recursos, texto). Se incluyen todas las secciones del perfil."""
    codigo, display = TIPO_DOCUMENTO[tipo]
    autor = fhir.ref("Practitioner", autor_id) if autor_id else fhir.ref("Organization", "prestador")
    c = {"resourceType": "Composition", "id": f"rda-{tipo}-{id_}", "meta": {"profile": [_perfil(tipo)]},
         "status": "final", "confidentiality": "N",
         "type": {"coding": [{"system": fhir.LOINC, "code": codigo, "display": display}], "text": TIPOS[tipo]},
         "subject": fhir.ref("Patient", paciente.id), "date": fecha, "author": [autor], "title": TIPOS[tipo],
         "custodian": fhir.ref("Organization", "prestador"),
         "section": [_seccion(k, *contenido.get(k, ([], None))) for k in SECCIONES_POR_TIPO[tipo]]}
    if autor_id:
        c["attester"] = [{"mode": "legal", "time": fecha, "party": autor}]
    if encuentro_id:
        c["encounter"] = fhir.ref("Encounter", encuentro_id)
    return c


def _sin_encuentro(recurso: dict) -> dict:
    recurso.pop("encounter", None)
    return recurso


def _notas(a) -> tuple[list, str | None]:
    if not getattr(a, "notas_aclaratorias", None):
        return [], None
    return [], " | ".join(f"{n.creado_en:%Y-%m-%d}: {n.texto}" for n in a.notas_aclaratorias)


def _soporte(tipo_doc: str, id_, hash_, paciente_id, titulo: str) -> dict:
    """DocumentReference al PDF verificable (QR) del documento firmado."""
    from app.services.pdf import url_verificacion

    return {"resourceType": "DocumentReference", "id": f"soporte-{id_}", "status": "current",
            "type": {"text": titulo}, "subject": fhir.ref("Patient", paciente_id),
            "content": [{"attachment": {"contentType": "application/pdf", "title": titulo,
                                        "url": url_verificacion(tipo_doc, id_, hash_)}}]}


def rda_atencion(a: Atencion, laboratorios: list[OrdenServicio] = (), triage=None) -> tuple[str, dict]:
    tipo = "urgencias" if a.tipo == "urgencias" else "consulta"
    p = a.paciente
    condiciones = [fhir.condition(d, a) for d in a.diagnosticos]
    meds = [fhir.medication_request(r, a) for r in a.prescripciones]
    procs = [fhir.procedure(x, a) for x in a.procedimientos]
    resultados = [o for lab in laboratorios for o in fhir.observaciones_laboratorio(lab)] + fhir.observaciones_signos(a)
    alergia = [x for x in [fhir.alergia(p)] if x]
    eapb = _eapb(p)
    soporte = [_soporte("atencion", a.id, a.hash_contenido, p.id, "Historia clínica firmada")] if a.hash_contenido else []
    contenido = {"pagadores": (eapb, None), "medicamentos": (meds, None),
                 "alergias": (alergia, None if alergia else "No refiere alergias conocidas"),
                 "problemas": (condiciones, None), "notas": _notas(a), "soportes": (soporte, None)}
    recursos = [fhir.patient(p), fhir.practitioner(a.profesional), _organizacion(), fhir.encounter_atencion(a), *eapb,
                *alergia, *condiciones, *meds, *soporte]
    if tipo == "urgencias":
        trg = []
        if triage is not None:
            trg = [{"resourceType": "Observation", "id": f"triage-{triage.id}", "status": "final",
                    "code": {"coding": [{"system": fhir.LOINC, "code": "54094-8", "display": "Triage note"}]},
                    "subject": fhir.ref("Patient", p.id), "effectiveDateTime": fhir._fecha(triage.clasificado_en),
                    "valueCodeableConcept": {"text": f"Triage {['I', 'II', 'III', 'IV', 'V'][triage.nivel - 1]}"}}]
        contenido.update({"triage": (trg, None), "procedimientos": (procs, None), "resultados": (resultados, None)})
        recursos += [*trg, *procs, *resultados]
    comp = _composicion(tipo, a.id, p, a.profesional_id, fhir._fecha(a.firmada_en or a.fecha_inicio), a.id, contenido)
    return tipo, _empaquetar(comp, recursos)


def rda_hospitalizacion(h: Hospitalizacion) -> tuple[str, dict]:
    p = h.paciente
    from types import SimpleNamespace as N

    def cond(codigo, rol):
        d = N(id=f"{h.id}-{rol}-{codigo}", codigo_cie10=codigo, descripcion=rol, tipo_diagnostico="02")
        return fhir.condition(d, N(paciente_id=p.id, id=h.id, fecha_inicio=h.fecha_ingreso))

    dx = [cond(h.dx_ingreso, "ingreso")] + ([cond(h.dx_egreso, "egreso")] if h.dx_egreso else []) + \
         [cond(c, "relacionado") for c in (h.dx_relacionados_egreso or [])]
    alergia = [x for x in [fhir.alergia(p)] if x]
    eapb = _eapb(p)
    soporte = [_soporte("epicrisis", h.id, h.hash_epicrisis, p.id, "Epicrisis firmada")] if h.hash_epicrisis else []
    contenido = {"pagadores": (eapb, None), "alergias": (alergia, None if alergia else "No refiere alergias"),
                 "problemas": (dx, None), "soportes": (soporte, h.epicrisis)}
    comp = _composicion("hospitalizacion", h.id, p, h.medico_id, fhir._fecha(h.fecha_egreso or h.fecha_ingreso), h.id, contenido)
    recursos = [fhir.patient(p), fhir.practitioner(h.medico), _organizacion(), fhir.encounter_hospitalizacion(h), *eapb,
                *alergia, *dx, *soporte]
    return "hospitalizacion", _empaquetar(comp, recursos)


def rda_paciente(p: Paciente, atenciones: list[Atencion]) -> tuple[str, dict]:
    alergia = [x for x in [fhir.alergia(p)] if x]
    condiciones, vistos = [], set()
    for a in atenciones:
        for d in a.diagnosticos:
            if d.codigo_cie10 not in vistos and d.tipo_diagnostico in ("02", "03"):
                vistos.add(d.codigo_cie10)
                condiciones.append(_sin_encuentro(fhir.condition(d, a)))
    meds = [_sin_encuentro(fhir.medication_request(r, a)) for a in atenciones[-3:] for r in a.prescripciones]
    familiares_txt = next((a.antecedentes.get("familiares") for a in reversed(atenciones)
                           if a.antecedentes and a.antecedentes.get("familiares")), None)
    familiares = []
    if familiares_txt:
        familiares = [{"resourceType": "FamilyMemberHistory", "id": f"fam-{p.id}", "status": "completed",
                       "patient": fhir.ref("Patient", p.id),
                       "relationship": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/v3-RoleCode",
                                                    "code": "FAMMEMB", "display": "family member"}]},
                       "note": [{"text": familiares_txt}]}]
    profesionales = {a.profesional_id: a.profesional for a in atenciones[-3:]}
    contenido = {"medicamentos": (meds, None), "alergias": (alergia, None if alergia else "No refiere alergias"),
                 "problemas": (condiciones, None if condiciones else "Sin diagnósticos confirmados"),
                 "familiares": (familiares, None)}
    comp = _composicion("paciente", p.id, p, None, datetime.now(timezone.utc).replace(microsecond=0).isoformat(), None, contenido)
    recursos = [fhir.patient(p), _organizacion(), *alergia, *condiciones, *meds, *familiares,
                *[fhir.practitioner(u) for u in profesionales.values()]]
    return "paciente", _empaquetar(comp, recursos)


def _ident_paciente(p) -> dict:
    return {"identifier": {"system": f"{fhir.SIS_DOCUMENTO}/{p.tipo_documento}", "value": p.numero_documento},
            "display": p.nombre_completo}


def rda_dispensacion(movimientos: list, paciente, dispensador, prescripcion=None, atencion=None) -> list[tuple[str, dict]]:
    """Res. 1799 de 2026: un MedicationDispense (perfil MedicationDispenseRDA) por lote entregado.
    Las referencias a paciente, dispensador y prescripción van por identificador (el recurso viaja solo)."""
    salida = []
    for m in movimientos:
        prod = m.producto
        med = {"resourceType": "Medication", "id": "med",
               "code": {**({"coding": [{"system": fhir.SIS_CUM, "code": prod.cum}]} if prod.cum else {}), "text": prod.nombre}}
        if m.lote:
            med["batch"] = {"lotNumber": m.lote.numero, "expirationDate": m.lote.vencimiento.isoformat()}
        recurso = {"resourceType": "MedicationDispense", "id": str(m.id), "meta": {"profile": [_perfil("dispensacion")]},
                   "contained": [med], "status": "completed", "medicationReference": {"reference": "#med"},
                   "subject": _ident_paciente(paciente),
                   "performer": [{"actor": {"identifier": {"system": f"{fhir.SIS_DOCUMENTO}/{dispensador.tipo_documento}",
                                                           "value": dispensador.numero_documento},
                                            "display": dispensador.nombre_completo}}],
                   "location": {"identifier": {"system": "https://prestadores.minsalud.gov.co/habilitacion",
                                               "value": settings.PRESTADOR_COD_HABILITACION},
                                "display": settings.PRESTADOR_RAZON_SOCIAL},
                   "type": {"text": "Entrega total" if not prescripcion or abs(m.cantidad) >= prescripcion.cantidad else "Entrega parcial"},
                   "quantity": {"value": abs(m.cantidad), "unit": prod.unidad}, "whenHandedOver": fhir._fecha(m.fecha)}
        if prescripcion is not None:
            recurso["authorizingPrescription"] = [{"identifier": {"system": "urn:ietf:rfc:3986",
                                                                  "value": _url("MedicationRequest", prescripcion.id)}}]
            recurso["daysSupply"] = {"value": prescripcion.duracion_dias, "unit": "d", "system": fhir.UCUM, "code": "d"}
        salida.append(("dispensacion", recurso))
    return salida


def _validar_dispensacion(r: dict) -> list[str]:
    errores = []
    if r.get("status") not in ("completed", "declined", "in-progress"):
        errores.append("MedicationDispense.status inválido")
    if not (r.get("subject") or {}).get("identifier"):
        errores.append("Falta la identificación del paciente")
    if not r.get("quantity", {}).get("value"):
        errores.append("Falta la cantidad entregada")
    if not r.get("whenHandedOver"):
        errores.append("Falta la fecha de entrega")
    if not r.get("contained") and not r.get("medicationCodeableConcept"):
        errores.append("Falta el medicamento")
    return errores


def validar(bundle: dict) -> list[str]:
    """Reglas estructurales del Manual de Operaciones IHCE (no sustituye la validación oficial)."""
    if bundle.get("resourceType") == "MedicationDispense":
        return _validar_dispensacion(bundle)
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
    operacion = OPERACIONES[envio.tipo] or settings.RDA_OPERACION_DISPENSACION
    if not operacion:
        raise RuntimeError("Configure RDA_OPERACION_DISPENSACION con la ruta que indique la IHCE")
    r = httpx.post(f"{settings.IHCE_URL.rstrip('/')}/{operacion}", json=envio.bundle, timeout=60,
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
