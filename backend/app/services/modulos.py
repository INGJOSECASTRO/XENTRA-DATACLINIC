"""Módulos dinámicos: el administrador crea formularios nuevos (escalas, seguimientos, registros de calidad,
PQRS...) sin programar. Cada campo tiene un tipo validado; los registros pueden sellarse (inalterables),
quedan en el ledger y alimentan automáticamente el constructor de reportes (BI)."""
import re
from datetime import date, datetime

from app.services import cie10

TIPOS_CAMPO = {
    "texto": "Texto corto", "texto_largo": "Texto largo", "numero": "Número decimal", "entero": "Número entero",
    "fecha": "Fecha", "fecha_hora": "Fecha y hora", "seleccion": "Lista (una opción)", "multiple": "Lista (varias opciones)",
    "si_no": "Sí / No", "cie10": "Diagnóstico CIE-10",
}
CLAVE = re.compile(r"^[a-z][a-z0-9_]{1,39}$")


class ErrorModulo(ValueError):
    pass


def validar_definicion(campos: list[dict]) -> list[dict]:
    if not campos:
        raise ErrorModulo("El módulo debe tener al menos un campo")
    if len(campos) > 60:
        raise ErrorModulo("Máximo 60 campos por módulo")
    vistos, limpios = set(), []
    for c in campos:
        clave, tipo = c.get("clave", ""), c.get("tipo", "")
        if not CLAVE.match(clave):
            raise ErrorModulo(f"Clave de campo inválida '{clave}': minúsculas, números y _ (ej. puntaje_total)")
        if clave in vistos:
            raise ErrorModulo(f"Campo repetido: {clave}")
        if tipo not in TIPOS_CAMPO:
            raise ErrorModulo(f"Tipo de campo no soportado: {tipo}")
        opciones = [str(o).strip() for o in c.get("opciones") or [] if str(o).strip()]
        if tipo in ("seleccion", "multiple") and len(opciones) < 2:
            raise ErrorModulo(f"El campo '{clave}' necesita al menos dos opciones")
        vistos.add(clave)
        limpios.append({"clave": clave, "etiqueta": (c.get("etiqueta") or clave).strip()[:120], "tipo": tipo,
                        "requerido": bool(c.get("requerido")), "opciones": opciones or None,
                        "min": c.get("min"), "max": c.get("max"), "ayuda": (c.get("ayuda") or None)})
    return limpios


def validar_registro(campos: list[dict], datos: dict) -> dict:
    """Devuelve los datos normalizados o lanza ErrorModulo con un mensaje claro para el usuario."""
    salida, errores = {}, []
    desconocidos = set(datos) - {c["clave"] for c in campos}
    if desconocidos:
        errores.append(f"Campos no definidos en el módulo: {', '.join(sorted(desconocidos))}")
    for c in campos:
        v, etq = datos.get(c["clave"]), c["etiqueta"]
        if v in (None, "", []):
            if c["requerido"]:
                errores.append(f"'{etq}' es obligatorio")
            continue
        try:
            t = c["tipo"]
            if t in ("texto", "texto_largo"):
                v = str(v).strip()[: 255 if t == "texto" else 20000]
            elif t in ("numero", "entero"):
                v = int(v) if t == "entero" else float(v)
                if t == "entero" and float(datos[c["clave"]]) != v:
                    raise ValueError
                if c.get("min") is not None and v < c["min"] or c.get("max") is not None and v > c["max"]:
                    errores.append(f"'{etq}' debe estar entre {c.get('min')} y {c.get('max')}")
            elif t == "fecha":
                v = date.fromisoformat(str(v)[:10]).isoformat()
            elif t == "fecha_hora":
                v = datetime.fromisoformat(str(v)).isoformat()
            elif t == "seleccion":
                if v not in c["opciones"]:
                    errores.append(f"'{etq}': opción no válida")
            elif t == "multiple":
                v = list(v) if isinstance(v, list) else [v]
                if any(x not in c["opciones"] for x in v):
                    errores.append(f"'{etq}': opción no válida")
            elif t == "si_no":
                if not isinstance(v, bool):
                    v = str(v).lower() in ("true", "si", "sí", "1")
            elif t == "cie10":
                v = cie10.formatear_codigo(str(v))
                if not cie10.codigo_valido(v):
                    errores.append(f"'{etq}': código CIE-10 inválido")
        except (TypeError, ValueError):
            errores.append(f"'{etq}': valor inválido para {TIPOS_CAMPO[c['tipo']].lower()}")
            continue
        salida[c["clave"]] = v
    if errores:
        raise ErrorModulo(" · ".join(errores))
    return salida


# Plantillas listas para instalar con un clic (se pueden editar después)
PLANTILLAS = {
    "riesgo_caidas": {
        "nombre": "Valoración de riesgo de caídas", "categoria": "asistencial", "por_paciente": True, "sellar_al_guardar": True,
        "roles_lectura": ["medico", "enfermeria", "auditor"], "roles_escritura": ["enfermeria", "medico"],
        "descripcion": "Registro de valoración del riesgo de caídas según la escala adoptada por la institución.",
        "campos": [
            {"clave": "antecedente_caidas", "etiqueta": "Caídas en los últimos 3 meses", "tipo": "si_no", "requerido": True},
            {"clave": "puntaje", "etiqueta": "Puntaje de la escala", "tipo": "entero", "requerido": True, "min": 0, "max": 200},
            {"clave": "nivel_riesgo", "etiqueta": "Nivel de riesgo", "tipo": "seleccion", "requerido": True,
             "opciones": ["Bajo", "Medio", "Alto"]},
            {"clave": "medidas", "etiqueta": "Medidas implementadas", "tipo": "multiple",
             "opciones": ["Barandas arriba", "Timbre al alcance", "Acompañante permanente", "Calzado antideslizante",
                          "Señalización en cama", "Revisión de medicamentos"]},
            {"clave": "observaciones", "etiqueta": "Observaciones", "tipo": "texto_largo"},
        ],
    },
    "eventos_adversos": {
        "nombre": "Reporte de eventos adversos e incidentes", "categoria": "calidad", "por_paciente": True, "sellar_al_guardar": True,
        "roles_lectura": ["auditor"], "roles_escritura": ["medico", "enfermeria", "farmacia", "laboratorio", "admisiones"],
        "descripcion": "Programa de seguridad del paciente: reporte no punitivo de incidentes y eventos adversos.",
        "campos": [
            {"clave": "fecha_evento", "etiqueta": "Fecha y hora del evento", "tipo": "fecha_hora", "requerido": True},
            {"clave": "tipo", "etiqueta": "Clasificación", "tipo": "seleccion", "requerido": True,
             "opciones": ["Incidente (sin daño)", "Evento adverso prevenible", "Evento adverso no prevenible", "Evento centinela"]},
            {"clave": "categoria", "etiqueta": "Categoría", "tipo": "seleccion", "requerido": True,
             "opciones": ["Medicación", "Caída", "Identificación del paciente", "Infección asociada a la atención",
                          "Procedimiento", "Úlcera por presión", "Otro"]},
            {"clave": "servicio", "etiqueta": "Servicio", "tipo": "texto", "requerido": True},
            {"clave": "descripcion", "etiqueta": "¿Qué pasó?", "tipo": "texto_largo", "requerido": True},
            {"clave": "acciones", "etiqueta": "Acciones inmediatas", "tipo": "texto_largo"},
        ],
    },
    "pqrs": {
        "nombre": "PQRS (peticiones, quejas, reclamos y sugerencias)", "categoria": "administrativo", "por_paciente": False,
        "sellar_al_guardar": False, "roles_lectura": ["auditor", "admisiones"], "roles_escritura": ["admisiones"],
        "descripcion": "Registro y seguimiento de PQRS de usuarios con tiempos de respuesta.",
        "campos": [
            {"clave": "tipo", "etiqueta": "Tipo", "tipo": "seleccion", "requerido": True,
             "opciones": ["Petición", "Queja", "Reclamo", "Sugerencia", "Felicitación"]},
            {"clave": "canal", "etiqueta": "Canal", "tipo": "seleccion", "opciones": ["Presencial", "Teléfono", "Correo", "Web", "Buzón"]},
            {"clave": "servicio", "etiqueta": "Servicio relacionado", "tipo": "texto"},
            {"clave": "descripcion", "etiqueta": "Descripción", "tipo": "texto_largo", "requerido": True},
            {"clave": "estado", "etiqueta": "Estado", "tipo": "seleccion", "requerido": True,
             "opciones": ["Recibida", "En trámite", "Respondida", "Cerrada"]},
            {"clave": "dias_respuesta", "etiqueta": "Días hábiles para responder", "tipo": "entero", "min": 0, "max": 60},
        ],
    },
    "seguimiento_gestante": {
        "nombre": "Seguimiento de gestantes (ruta materno-perinatal)", "categoria": "asistencial", "por_paciente": True,
        "sellar_al_guardar": True, "roles_lectura": ["medico", "enfermeria", "auditor"], "roles_escritura": ["medico", "enfermeria"],
        "descripcion": "Control de la ruta materno-perinatal (Resolución 3280 de 2018).",
        "campos": [
            {"clave": "semanas", "etiqueta": "Semanas de gestación", "tipo": "entero", "requerido": True, "min": 1, "max": 45},
            {"clave": "riesgo", "etiqueta": "Clasificación del riesgo", "tipo": "seleccion", "requerido": True,
             "opciones": ["Bajo", "Alto"]},
            {"clave": "tension_sistolica", "etiqueta": "TA sistólica", "tipo": "entero", "min": 50, "max": 250},
            {"clave": "tamizajes_completos", "etiqueta": "Tamizajes del trimestre completos", "tipo": "si_no"},
            {"clave": "proximo_control", "etiqueta": "Próximo control", "tipo": "fecha"},
            {"clave": "observaciones", "etiqueta": "Observaciones", "tipo": "texto_largo"},
        ],
    },
}
