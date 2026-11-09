"""Asistente de codificación CIE-10 con inteligencia artificial.

Principios de seguridad clínica (IA como APOYO, nunca reemplazo del médico):
- La IA SOLO sugiere; el profesional decide y firma.
- Todo código sugerido se valida contra el catálogo oficial cargado en la BD y contra
  reglas de pertinencia sexo/edad (se descartan códigos inventados o no pertinentes).
- Antes de enviar texto a un servicio externo se anonimiza (sin nombres, documentos,
  teléfonos ni correos) - Ley 1581 de 2012. Por defecto se usa el motor local.
- Si el servicio externo falla, se usa automáticamente el motor local.
"""
import json
import logging

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import CIE10
from app.services import cie10 as cat
from app.services.texto import anonimizar

log = logging.getLogger(__name__)

PROMPT_SISTEMA = """Eres un codificador clínico experto en la CIE-10 tal como se usa en Colombia \
(RIPS, Resolución 2275 de 2023). Recibes un resumen clínico ANONIMIZADO y una lista de \
códigos candidatos del catálogo de la institución.

Reglas:
- Propón entre 1 y 5 códigos CIE-10, del más probable al menos probable.
- Usa el formato colombiano de 4 caracteres sin punto (ej. I10X, E119, J00X).
- Prefiere códigos de la lista de candidatos; si propones otro, debe existir en la CIE-10.
- Prefiere el código más específico que el texto soporte; no supongas hallazgos no escritos.
- Si es un síntoma sin diagnóstico establecido, usa códigos del capítulo R.
- Justifica cada código en una frase corta citando los hallazgos del texto.
- La confianza es un número entre 0 y 1."""

ESQUEMA = {
    "type": "object",
    "properties": {
        "sugerencias": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "codigo": {"type": "string"},
                    "confianza": {"type": "number"},
                    "justificacion": {"type": "string"},
                },
                "required": ["codigo", "confianza", "justificacion"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["sugerencias"],
    "additionalProperties": False,
}


def sugerir_cie10(
    db: Session,
    texto: str,
    sexo: str | None = None,
    edad: int | None = None,
    nombres_paciente: list[str] | None = None,
) -> dict:
    locales = cat.sugerir_local(db, texto, sexo, edad, limite=10)
    if settings.IA_PROVEEDOR == "claude" and settings.ANTHROPIC_API_KEY:
        try:
            return {"proveedor": "claude", "sugerencias": _sugerir_claude(db, texto, sexo, edad, nombres_paciente, locales)}
        except Exception as exc:  # cualquier falla -> motor local
            log.warning("Fallo IA externa, se usa motor local: %s", exc)
    return {"proveedor": "local", "sugerencias": [s.__dict__ for s in locales[:5]]}


def _sugerir_claude(db, texto, sexo, edad, nombres, locales) -> list[dict]:
    import anthropic  # importación diferida: solo si se usa

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, timeout=60, max_retries=2)
    texto_seguro = anonimizar(texto, nombres)
    candidatos = "\n".join(f"- {s.codigo}: {s.descripcion}" for s in locales) or "(sin candidatos)"
    contenido = (
        f"Sexo: {sexo or 'no registrado'} | Edad: {edad if edad is not None else 'no registrada'} años\n\n"
        f"Resumen clínico:\n{texto_seguro}\n\nCandidatos del catálogo:\n{candidatos}"
    )
    respuesta = client.beta.messages.create(
        model=settings.IA_MODELO,
        max_tokens=4000,
        system=PROMPT_SISTEMA,
        messages=[{"role": "user", "content": contenido}],
        thinking={"type": "adaptive"},
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": ESQUEMA}},
        # Si el modelo principal declina la solicitud, la API reintenta con un modelo alterno.
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if respuesta.stop_reason == "refusal":
        raise RuntimeError("La IA declinó la solicitud")
    bloque = next(b for b in respuesta.content if b.type == "text")
    datos = json.loads(bloque.text)

    salida = []
    for s in datos.get("sugerencias", []):
        codigo = cat.formatear_codigo(s.get("codigo", ""))
        fila = db.get(CIE10, codigo)
        # Anti-alucinación: solo códigos que existen en el catálogo y son pertinentes.
        if not fila or not cat.pertinente(fila, sexo, edad):
            continue
        salida.append(
            {
                "codigo": codigo,
                "descripcion": fila.descripcion,
                "confianza": round(max(0.0, min(1.0, float(s.get("confianza", 0)))), 2),
                "justificacion": s.get("justificacion", ""),
                "fuente": "claude",
            }
        )
    if not salida:
        raise RuntimeError("La IA no devolvió códigos válidos del catálogo")
    return salida[:5]


def alertas_clinicas(signos: dict | None, edad: int | None = None) -> list[str]:
    """Reglas simples de seguridad del paciente sobre signos vitales (adultos)."""
    if not signos:
        return []
    alertas = []

    def v(clave):
        try:
            return float(signos.get(clave)) if signos.get(clave) not in (None, "") else None
        except (TypeError, ValueError):
            return None

    tas, tad, fc, fr, temp, spo2 = (v(k) for k in ("ta_sistolica", "ta_diastolica", "fc", "fr", "temperatura", "spo2"))
    peso, talla = v("peso"), v("talla")
    adulto = edad is None or edad >= 18
    if adulto and tas is not None and tad is not None:
        if tas >= 180 or tad >= 120:
            alertas.append("CRISIS HIPERTENSIVA: TA ≥ 180/120. Evaluar daño de órgano blanco.")
        elif tas >= 140 or tad >= 90:
            alertas.append("Tensión arterial elevada (≥ 140/90).")
        elif tas < 90:
            alertas.append("Hipotensión (TAS < 90).")
    if spo2 is not None and spo2 < 92:
        alertas.append(f"Saturación de oxígeno baja ({spo2:.0f}%).")
    if temp is not None and temp >= 38:
        alertas.append(f"Fiebre ({temp:.1f} °C).")
    if adulto and fc is not None and (fc > 100 or fc < 50):
        alertas.append(f"Frecuencia cardiaca anormal ({fc:.0f} lpm).")
    if adulto and fr is not None and (fr > 22 or fr < 10):
        alertas.append(f"Frecuencia respiratoria anormal ({fr:.0f} rpm).")
    if peso and talla:
        metros = talla / 100 if talla > 3 else talla
        imc = peso / (metros**2)
        if adulto and imc >= 30:
            alertas.append(f"IMC {imc:.1f}: obesidad.")
        elif adulto and imc < 18.5:
            alertas.append(f"IMC {imc:.1f}: bajo peso.")
    return alertas
