"""Lógica de urgencias, hospitalización, laboratorio y consentimientos."""
import re

from app.services.ledger import a_utc, json_canonico, sha256
from app.services.texto import normalizar

# Resolución 5596 de 2015: Triage I = atención inmediata; Triage II = máximo 30 minutos.
# Para III, IV y V la norma deja los tiempos al protocolo institucional: valores sugeridos, ajústelos.
TIEMPO_MAXIMO_MIN = {1: 0, 2: 30, 3: 120, 4: 240, 5: 480}
DESCRIPCION_TRIAGE = {
    1: "Triage I - Requiere atención inmediata (riesgo vital)",
    2: "Triage II - Riesgo de deterioro rápido; atención en máximo 30 minutos",
    3: "Triage III - Requiere medidas diagnósticas y terapéuticas en urgencias; estable",
    4: "Triage IV - Condición que no compromete el estado general; sin riesgo evidente",
    5: "Triage V - Problema clínico agudo o crónico sin evidencia de deterioro (puede remitirse a consulta)",
}

_PALABRAS = {
    1: ["paro", "inconsciente", "no responde", "convulsionando", "convulsion activa", "apnea", "politraumatismo grave"],
    2: ["dolor toracico", "dolor en el pecho", "dificultad respiratoria", "hemorragia", "sangrado abundante",
        "deficit neurologico", "hemiparesia", "intento suicida", "intento de suicidio", "quemadura extensa",
        "dolor 10 10", "trabajo de parto", "anafilaxia"],
    3: ["fractura", "dolor abdominal", "vomito persistente", "deshidratacion", "herida", "fiebre alta", "crisis asmatica"],
    5: ["formula", "certificado", "incapacidad", "control", "resultado", "renovar"],
}


def _v(signos: dict | None, clave: str) -> float | None:
    try:
        valor = (signos or {}).get(clave)
        return float(valor) if valor not in (None, "") else None
    except (TypeError, ValueError):
        return None


def sugerir_triage(motivo: str, signos: dict | None) -> tuple[int, list[str]]:
    """Sugiere un nivel de triage. La clasificación final la decide el profesional entrenado."""
    razones: list[str] = []
    spo2, tas, tad, fc, fr, temp, glasgow = (_v(signos, k) for k in
                                             ("spo2", "ta_sistolica", "ta_diastolica", "fc", "fr", "temperatura", "glasgow"))
    texto = normalizar(motivo)

    def regla(cond, nivel, razon):
        if cond:
            razones.append(f"[{nivel}] {razon}")
            return nivel
        return 9

    niveles = [
        regla(spo2 is not None and spo2 < 85, 1, f"SpO2 {spo2}%"),
        regla(tas is not None and tas < 80, 1, f"TAS {tas}"),
        regla(fc is not None and (fc > 150 or fc < 40), 1, f"FC {fc}"),
        regla(fr is not None and (fr > 35 or fr < 8), 1, f"FR {fr}"),
        regla(glasgow is not None and glasgow <= 8, 1, f"Glasgow {glasgow}"),
        regla(spo2 is not None and spo2 < 90, 2, f"SpO2 {spo2}%"),
        regla(tas is not None and (tas >= 180 or (tad or 0) >= 120), 2, f"TA {tas}/{tad}"),
        regla(fc is not None and fc > 120, 2, f"FC {fc}"),
        regla(fr is not None and fr > 28, 2, f"FR {fr}"),
        regla(temp is not None and temp >= 40, 2, f"Temperatura {temp}"),
        regla(glasgow is not None and glasgow < 14, 2, f"Glasgow {glasgow}"),
        regla(temp is not None and temp >= 38.5, 3, f"Temperatura {temp}"),
        regla(fc is not None and fc > 100, 3, f"FC {fc}"),
    ]
    for nivel, palabras in _PALABRAS.items():
        for p in palabras:
            if p in texto:
                niveles.append(regla(True, nivel, f"motivo: '{p}'"))
    nivel = min(niveles)
    if nivel == 9:
        nivel = 4
        razones.append("[4] Sin criterios de mayor prioridad")
    return nivel, razones


def hash_epicrisis(h) -> str:
    return sha256(json_canonico({
        "id": str(h.id), "paciente_id": str(h.paciente_id), "ingreso": a_utc(h.fecha_ingreso).isoformat(),
        "egreso": a_utc(h.fecha_egreso).isoformat() if h.fecha_egreso else None, "dx_ingreso": h.dx_ingreso,
        "dx_egreso": h.dx_egreso, "condicion": h.condicion_egreso, "causa_muerte": h.dx_causa_muerte,
        "relacionados": h.dx_relacionados_egreso, "epicrisis": h.epicrisis, "medico_id": str(h.medico_id),
    }))


def hash_consentimiento(c) -> str:
    return sha256(json_canonico({
        "id": str(c.id), "paciente_id": str(c.paciente_id), "titulo": c.titulo, "texto": c.texto, "decision": c.decision,
        "firmante": c.firmante_nombre, "documento": c.firmante_documento, "parentesco": c.parentesco,
        "firma": sha256(c.firma_imagen), "profesional_id": str(c.profesional_id), "fecha": a_utc(c.fecha).isoformat(),
    }))


def hash_resultado(o) -> str:
    return sha256(json_canonico({
        "id": str(o.id), "paciente_id": str(o.paciente_id), "cups": o.cod_cups, "resultados": o.resultados,
        "informe": o.informe, "validado_por": str(o.validado_por),
        "fecha": a_utc(o.fecha_resultado).isoformat() if o.fecha_resultado else None,
    }))


def hash_evolucion(autor_id, hosp_id, tipo: str, texto: str, signos: dict | None) -> str:
    return sha256(json_canonico({"autor": str(autor_id), "hosp": str(hosp_id), "tipo": tipo, "texto": texto, "signos": signos}))


_RANGO = re.compile(r"^\s*(-?\d+(?:[.,]\d+)?)\s*-\s*(-?\d+(?:[.,]\d+)?)\s*$")


def marcar_anormales(resultados: list[dict]) -> list[dict]:
    """Marca como anormal un valor numérico fuera del rango de referencia 'min - max'."""
    for r in resultados:
        if r.get("anormal") is not None:
            continue
        m = _RANGO.match(str(r.get("referencia") or ""))
        try:
            valor = float(str(r.get("valor")).replace(",", "."))
        except (TypeError, ValueError):
            r["anormal"] = None
            continue
        if m:
            minimo, maximo = (float(x.replace(",", ".")) for x in m.groups())
            r["anormal"] = not (minimo <= valor <= maximo)
        else:
            r["anormal"] = None
    return resultados


PLANTILLAS_CONSENTIMIENTO = {
    "procedimiento": {
        "titulo": "Consentimiento informado para procedimiento",
        "texto": "Yo, el abajo firmante, declaro que el profesional me ha explicado en lenguaje claro el procedimiento "
                 "denominado: ________, su propósito, beneficios esperados, riesgos frecuentes y graves (________), "
                 "alternativas disponibles y las consecuencias de no realizarlo. He podido hacer preguntas y han sido "
                 "resueltas. Entiendo que puedo revocar este consentimiento en cualquier momento antes del procedimiento.",
    },
    "hospitalizacion": {
        "titulo": "Consentimiento informado para hospitalización",
        "texto": "Autorizo mi hospitalización (o la del paciente que represento) y la realización de los exámenes y "
                 "tratamientos que el equipo de salud considere necesarios, los cuales me serán informados. Conozco "
                 "mis derechos y deberes como paciente y las normas de la institución.",
    },
    "telemedicina": {
        "titulo": "Consentimiento informado para atención por telemedicina",
        "texto": "Acepto recibir atención en salud mediante telemedicina. Entiendo que la valoración se hace a distancia, "
                 "sus limitaciones frente a la consulta presencial, que la información se transmite por medios seguros "
                 "y que puedo solicitar atención presencial cuando lo considere necesario (Resolución 2654 de 2019).",
    },
    "transfusion": {
        "titulo": "Consentimiento informado para transfusión de componentes sanguíneos",
        "texto": "Se me ha explicado la necesidad de transfundir ________, los beneficios, los riesgos (reacciones "
                 "alérgicas, febriles, sobrecarga de volumen, transmisión de infecciones a pesar de las pruebas) y las "
                 "alternativas. Acepto / no acepto la transfusión de manera libre y voluntaria.",
    },
    "retiro_voluntario": {
        "titulo": "Retiro voluntario / alta contra consejo médico",
        "texto": "Decido retirarme de la institución en contra de la recomendación médica. Se me han explicado los "
                 "riesgos para mi salud, incluida la posibilidad de complicaciones graves o la muerte, y libero a la "
                 "institución y al equipo de salud de la responsabilidad derivada de esta decisión.",
    },
}
