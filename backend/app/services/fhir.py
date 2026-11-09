"""Mapeo a HL7 FHIR R4 para interoperabilidad (Ley 2015 de 2020 / Resolución 866 de 2021).

Recursos: Patient, Practitioner, Encounter, Condition, MedicationRequest, Procedure, Observation,
AllergyIntolerance y Bundle ($everything).

NOTA: el Ministerio de Salud publica guías de implementación (perfiles) para la IHCE. Cuando defina los
perfiles oficiales colombianos, ajuste los 'system' y extensiones de este archivo a esos perfiles.
"""
from app.core.config import settings
from app.services.ledger import a_utc

BASE = settings.URL_PUBLICA.rstrip("/") + "/fhir"
SIS_DOCUMENTO = "https://www.minsalud.gov.co/fhir/CodeSystem/tipo-documento"
SIS_CIE10 = "http://hl7.org/fhir/sid/icd-10"
SIS_CIE10_CO = "https://www.minsalud.gov.co/fhir/CodeSystem/cie10-rips"
SIS_CUPS = "https://www.minsalud.gov.co/fhir/CodeSystem/cups"
SIS_CUM = "https://www.invima.gov.co/fhir/CodeSystem/cum"
LOINC = "http://loinc.org"
UCUM = "http://unitsofmeasure.org"

SIGNOS = {  # clave interna -> (LOINC, nombre, unidad UCUM)
    "ta_sistolica": ("8480-6", "Presión arterial sistólica", "mm[Hg]"),
    "ta_diastolica": ("8462-4", "Presión arterial diastólica", "mm[Hg]"),
    "fc": ("8867-4", "Frecuencia cardiaca", "/min"),
    "fr": ("9279-1", "Frecuencia respiratoria", "/min"),
    "temperatura": ("8310-5", "Temperatura corporal", "Cel"),
    "spo2": ("59408-5", "Saturación de oxígeno por oximetría de pulso", "%"),
    "peso": ("29463-7", "Peso corporal", "kg"),
    "talla": ("8302-2", "Talla", "cm"),
}


def _fecha(dt) -> str | None:
    return a_utc(dt).isoformat() if dt else None


def cie10_internacional(codigo: str) -> str:
    """'I10X' -> 'I10' ; 'E119' -> 'E11.9' (formato FHIR/OMS)."""
    if codigo.endswith("X"):
        return codigo[:3]
    return f"{codigo[:3]}.{codigo[3:]}"


def ref(tipo: str, id_) -> dict:
    return {"reference": f"{tipo}/{id_}"}


def patient(p) -> dict:
    nombres = [n for n in (p.primer_nombre, p.segundo_nombre) if n]
    recurso = {
        "resourceType": "Patient", "id": str(p.id),
        "identifier": [{"type": {"coding": [{"system": SIS_DOCUMENTO, "code": p.tipo_documento}]},
                        "system": f"{SIS_DOCUMENTO}/{p.tipo_documento}", "value": p.numero_documento}],
        "name": [{"use": "official", "family": " ".join(x for x in (p.primer_apellido, p.segundo_apellido) if x),
                  "given": nombres, "text": p.nombre_completo}],
        "gender": {"H": "male", "M": "female"}.get(p.sexo, "other"),
        "birthDate": p.fecha_nacimiento.isoformat(),
        "address": [{"use": "home", "text": p.direccion, "city": p.cod_municipio_residencia, "country": "CO"}],
    }
    telecom = []
    if p.telefono:
        telecom.append({"system": "phone", "value": p.telefono})
    if p.email:
        telecom.append({"system": "email", "value": p.email})
    if telecom:
        recurso["telecom"] = telecom
    return recurso


def practitioner(u) -> dict:
    r = {"resourceType": "Practitioner", "id": str(u.id),
         "identifier": [{"system": f"{SIS_DOCUMENTO}/{u.tipo_documento}", "value": u.numero_documento}],
         "name": [{"family": u.apellidos, "given": [u.nombres]}]}
    if u.registro_profesional:
        r["qualification"] = [{"identifier": [{"system": "https://web.sispro.gov.co/rethus", "value": u.registro_profesional}],
                               "code": {"text": u.especialidad or u.rol}}]
    return r


def encounter_atencion(a) -> dict:
    clase = {"urgencias": ("EMER", "emergency"), "hospitalizacion": ("IMP", "inpatient encounter")}.get(a.tipo, ("AMB", "ambulatory"))
    r = {"resourceType": "Encounter", "id": str(a.id), "status": "finished" if a.estado == "firmada" else "in-progress",
         "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": clase[0], "display": clase[1]},
         "type": [{"coding": [{"system": SIS_CUPS, "code": a.cod_consulta_cups}]}],
         "subject": ref("Patient", a.paciente_id), "participant": [{"individual": ref("Practitioner", a.profesional_id)}],
         "period": {"start": _fecha(a.fecha_inicio)}, "reasonCode": [{"text": a.motivo_consulta}],
         "serviceProvider": {"display": settings.PRESTADOR_RAZON_SOCIAL,
                             "identifier": {"system": "https://prestadores.minsalud.gov.co/habilitacion",
                                            "value": settings.PRESTADOR_COD_HABILITACION}}}
    if a.fecha_egreso:
        r["period"]["end"] = _fecha(a.fecha_egreso)
    return r


def encounter_hospitalizacion(h) -> dict:
    r = {"resourceType": "Encounter", "id": str(h.id), "status": "finished" if h.estado == "egresada" else "in-progress",
         "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "IMP", "display": "inpatient encounter"},
         "subject": ref("Patient", h.paciente_id), "participant": [{"individual": ref("Practitioner", h.medico_id)}],
         "period": {"start": _fecha(h.fecha_ingreso)}, "reasonCode": [{"text": h.motivo}]}
    if h.fecha_egreso:
        r["period"]["end"] = _fecha(h.fecha_egreso)
    return r


def condition(d, a) -> dict:
    estado = "provisional" if d.tipo_diagnostico == "01" else "confirmed"
    return {"resourceType": "Condition", "id": str(d.id),
            "clinicalStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical", "code": "active"}]},
            "verificationStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
                                               "code": estado}]},
            "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-category",
                                      "code": "encounter-diagnosis"}]}],
            "code": {"coding": [{"system": SIS_CIE10, "code": cie10_internacional(d.codigo_cie10), "display": d.descripcion},
                                {"system": SIS_CIE10_CO, "code": d.codigo_cie10}], "text": d.descripcion},
            "subject": ref("Patient", a.paciente_id), "encounter": ref("Encounter", a.id), "recordedDate": _fecha(a.fecha_inicio)}


def medication_request(r, a) -> dict:
    return {"resourceType": "MedicationRequest", "id": str(r.id), "status": "completed" if a.estado == "firmada" else "draft",
            "intent": "order", "medicationCodeableConcept": {
                **({"coding": [{"system": SIS_CUM, "code": r.cum}]} if r.cum else {}), "text": r.medicamento},
            "subject": ref("Patient", a.paciente_id), "encounter": ref("Encounter", a.id), "authoredOn": _fecha(a.fecha_inicio),
            "requester": ref("Practitioner", a.profesional_id),
            "dosageInstruction": [{"text": f"{r.dosis} vía {r.via} {r.frecuencia} por {r.duracion_dias} días",
                                   "route": {"text": r.via}}],
            "dispenseRequest": {"quantity": {"value": r.cantidad},
                                "expectedSupplyDuration": {"value": r.duracion_dias, "unit": "d", "system": UCUM, "code": "d"}}}


def procedure(p, a) -> dict:
    return {"resourceType": "Procedure", "id": str(p.id), "status": "completed",
            "code": {"coding": [{"system": SIS_CUPS, "code": p.cod_cups}], "text": p.descripcion},
            "subject": ref("Patient", a.paciente_id), "encounter": ref("Encounter", a.id),
            "performedDateTime": _fecha(a.fecha_inicio)}


def observaciones_signos(a) -> list[dict]:
    salida = []
    for clave, valor in (a.signos_vitales or {}).items():
        if clave not in SIGNOS or valor in (None, ""):
            continue
        loinc, nombre, unidad = SIGNOS[clave]
        salida.append({"resourceType": "Observation", "id": f"{a.id}-{clave}", "status": "final",
                       "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category",
                                                 "code": "vital-signs"}]}],
                       "code": {"coding": [{"system": LOINC, "code": loinc, "display": nombre}], "text": nombre},
                       "subject": ref("Patient", a.paciente_id), "encounter": ref("Encounter", a.id),
                       "effectiveDateTime": _fecha(a.fecha_inicio),
                       "valueQuantity": {"value": valor, "unit": unidad, "system": UCUM, "code": unidad}})
    return salida


def observaciones_laboratorio(o) -> list[dict]:
    salida = []
    for i, r in enumerate(o.resultados or []):
        obs = {"resourceType": "Observation", "id": f"{o.id}-{i}", "status": "final",
               "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category",
                                         "code": "laboratory" if o.tipo == "laboratorio" else "imaging"}]}],
               "code": {"coding": [{"system": SIS_CUPS, "code": o.cod_cups}], "text": r.get("analito")},
               "subject": ref("Patient", o.paciente_id), "effectiveDateTime": _fecha(o.fecha_toma or o.fecha),
               "issued": _fecha(o.fecha_resultado)}
        try:
            obs["valueQuantity"] = {"value": float(str(r.get("valor")).replace(",", ".")), "unit": r.get("unidad")}
        except (TypeError, ValueError):
            obs["valueString"] = str(r.get("valor"))
        if r.get("referencia"):
            obs["referenceRange"] = [{"text": r["referencia"]}]
        if r.get("anormal") is not None:
            obs["interpretation"] = [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation",
                                                  "code": "A" if r["anormal"] else "N"}]}]
        salida.append(obs)
    return salida


def alergia(p) -> dict | None:
    if not p.alergias:
        return None
    return {"resourceType": "AllergyIntolerance", "id": f"{p.id}-alergias",
            "clinicalStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/allergyintolerance-clinical",
                                           "code": "active"}]},
            "code": {"text": p.alergias}, "patient": ref("Patient", p.id)}


def bundle(recursos: list[dict], tipo: str = "searchset") -> dict:
    return {"resourceType": "Bundle", "type": tipo, "total": len(recursos),
            "entry": [{"fullUrl": f"{BASE}/{r['resourceType']}/{r['id']}", "resource": r} for r in recursos]}


def everything(paciente, atenciones, hospitalizaciones, ordenes_servicio) -> dict:
    recursos = [patient(paciente)]
    if al := alergia(paciente):
        recursos.append(al)
    profesionales = {}
    for a in atenciones:
        profesionales[a.profesional_id] = a.profesional
        recursos.append(encounter_atencion(a))
        recursos += [condition(d, a) for d in a.diagnosticos]
        recursos += [medication_request(r, a) for r in a.prescripciones]
        recursos += [procedure(p, a) for p in a.procedimientos]
        recursos += observaciones_signos(a)
    for h in hospitalizaciones:
        profesionales[h.medico_id] = h.medico
        recursos.append(encounter_hospitalizacion(h))
    for o in ordenes_servicio:
        recursos += observaciones_laboratorio(o)
    recursos += [practitioner(u) for u in profesionales.values()]
    return bundle(recursos, "collection")


def capability() -> dict:
    tipos = ["Patient", "Practitioner", "Encounter", "Condition", "MedicationRequest", "Procedure", "Observation",
             "AllergyIntolerance"]
    return {"resourceType": "CapabilityStatement", "status": "active", "kind": "instance", "fhirVersion": "4.0.1",
            "format": ["application/fhir+json"], "software": {"name": "XENTRA DATACLINIC", "version": "0.2.0"},
            "rest": [{"mode": "server", "security": {"service": [{"text": "OAuth2 Bearer (JWT)"}]},
                      "resource": [{"type": t, "interaction": [{"code": "read"}, {"code": "search-type"}]} for t in tipos],
                      "operation": [{"name": "everything", "definition": "http://hl7.org/fhir/OperationDefinition/Patient-everything"}]}]}
