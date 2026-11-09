"""Resumen clínico del paciente (para interconsultas, ingreso a urgencias o el portal).

Motor local: extrae de forma determinista problemas, medicamentos, alergias, signos y resultados.
Con IA_PROVEEDOR=claude agrega una síntesis narrativa a partir de los datos ANONIMIZADOS.
"""
import json
import logging
from collections import Counter
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.services.ledger import a_utc

log = logging.getLogger(__name__)


def resumen_estructurado(paciente, atenciones, hospitalizaciones, laboratorios, edad: int) -> dict:
    hace_un_ano = datetime.now(timezone.utc) - timedelta(days=365)
    recientes = [a for a in atenciones if a_utc(a.fecha_inicio) >= hace_un_ano]
    problemas = Counter()
    descripciones = {}
    for a in recientes:
        for d in a.diagnosticos:
            if not d.codigo_cie10.startswith(("R", "Z")):
                problemas[d.codigo_cie10] += 1
                descripciones[d.codigo_cie10] = d.descripcion
    medicamentos = {}
    for a in sorted(recientes, key=lambda x: x.fecha_inicio):
        for r in a.prescripciones:
            medicamentos[r.medicamento.lower()] = f"{r.medicamento} {r.dosis} {r.frecuencia}"
    signos = next((a.signos_vitales for a in sorted(atenciones, key=lambda x: x.fecha_inicio, reverse=True)
                   if a.signos_vitales), None)
    anormales = [f"{r['analito']}: {r['valor']} {r.get('unidad') or ''} (ref {r.get('referencia')})"
                 for o in laboratorios for r in (o.resultados or []) if r.get("anormal")]
    return {
        "paciente": {"edad": edad, "sexo": paciente.sexo, "grupo_sanguineo": paciente.grupo_sanguineo},
        "alergias": paciente.alergias or "No conocidas",
        "problemas_activos": [{"codigo": c, "descripcion": descripciones[c], "consultas": n} for c, n in problemas.most_common(10)],
        "medicamentos_recientes": list(medicamentos.values())[-10:],
        "ultimos_signos_vitales": signos,
        "resultados_anormales": anormales[-10:],
        "hospitalizaciones": [{"ingreso": a_utc(h.fecha_ingreso).date().isoformat(), "dx": h.dx_egreso or h.dx_ingreso,
                               "estado": h.estado} for h in hospitalizaciones][-5:],
        "total_atenciones": len(atenciones),
        "ultima_atencion": a_utc(atenciones[-1].fecha_inicio).date().isoformat() if atenciones else None,
    }


def resumen(paciente, atenciones, hospitalizaciones, laboratorios, edad: int) -> dict:
    datos = resumen_estructurado(paciente, atenciones, hospitalizaciones, laboratorios, edad)
    salida = {"estructurado": datos, "narrativo": None, "proveedor": "local",
              "aviso": "Resumen de apoyo. Verifique contra la historia clínica completa."}
    if settings.IA_PROVEEDOR == "claude" and settings.ANTHROPIC_API_KEY and atenciones:
        try:
            salida["narrativo"] = _narrativo_claude(datos)
            salida["proveedor"] = "claude"
        except Exception as exc:  # cualquier falla: se entrega solo el resumen estructurado
            log.warning("Resumen IA no disponible: %s", exc)
    return salida


def _narrativo_claude(datos: dict) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, timeout=90, max_retries=2)
    respuesta = client.beta.messages.create(
        model=settings.IA_MODELO,
        max_tokens=4000,
        system="Eres un médico internista colombiano. Redacta un resumen clínico breve (máximo 150 palabras) en español "
               "para un colega, a partir de datos estructurados ANONIMIZADOS. No inventes datos; si algo falta, no lo "
               "menciones. Señala alergias y riesgos relevantes primero.",
        messages=[{"role": "user", "content": json.dumps(datos, ensure_ascii=False, default=str)}],
        thinking={"type": "adaptive"},
        output_config={"effort": "low"},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if respuesta.stop_reason == "refusal":
        raise RuntimeError("La IA declinó la solicitud")
    return "".join(b.text for b in respuesta.content if b.type == "text").strip()
