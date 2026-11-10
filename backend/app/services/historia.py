"""Reglas de la historia clínica: huella digital (hash) del folio, firma y verificación."""
from datetime import datetime, timezone

from app.models import Atencion
from app.services.ledger import a_utc, json_canonico, sha256


def contenido_clinico(a: Atencion) -> dict:
    """Todo lo que queda 'sellado' al firmar. Si algo cambia después, el hash no coincide."""
    return {
        "id": str(a.id),
        "paciente_id": str(a.paciente_id),
        "profesional_id": str(a.profesional_id),
        "consecutivo": a.consecutivo,
        "fecha_inicio": a_utc(a.fecha_inicio).isoformat(),
        "tipo": a.tipo,
        "motivo_consulta": a.motivo_consulta,
        "enfermedad_actual": a.enfermedad_actual,
        "antecedentes": a.antecedentes,
        "revision_sistemas": a.revision_sistemas,
        "signos_vitales": a.signos_vitales,
        "examen_fisico": a.examen_fisico,
        "analisis": a.analisis,
        "plan": a.plan,
        "cod_consulta_cups": a.cod_consulta_cups,
        "valor_servicio": str(float(a.valor_servicio or 0)),
        "diagnosticos": [
            {"orden": d.orden, "codigo": d.codigo_cie10, "tipo": d.tipo_diagnostico}
            for d in sorted(a.diagnosticos, key=lambda d: d.orden)
        ],
        "procedimientos": sorted(
            [{"cups": p.cod_cups, "valor": str(float(p.valor or 0))} for p in a.procedimientos],
            key=lambda x: x["cups"],
        ),
        "prescripciones": sorted(
            [
                {"medicamento": r.medicamento, "dosis": r.dosis, "via": r.via, "frecuencia": r.frecuencia,
                 "duracion_dias": r.duracion_dias, "cantidad": r.cantidad}
                for r in a.prescripciones
            ],
            key=lambda x: (x["medicamento"], x["dosis"]),
        ),
    }


def contenido_sellado(a: Atencion) -> dict:
    """Contenido que se sella al firmar; con refrendo docente incluye quién asumió la responsabilidad."""
    contenido = contenido_clinico(a)
    if a.supervisor_id:
        contenido["supervisor_id"] = str(a.supervisor_id)
    return contenido


def calcular_hash(a: Atencion) -> str:
    return sha256(json_canonico(contenido_sellado(a)))


def marcar_firmada(a: Atencion) -> str:
    a.hash_contenido = calcular_hash(a)
    a.estado = "firmada"
    a.firmada_en = datetime.now(timezone.utc)
    return a.hash_contenido
