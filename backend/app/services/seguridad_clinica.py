"""Reglas de seguridad del paciente: alergias, interacciones y eventos de notificación obligatoria.

IMPORTANTE: son tablas de APOYO, no exhaustivas. Para producción se recomienda integrar una base
farmacológica licenciada y validada; la responsabilidad final es del profesional.
"""
from app.services.texto import normalizar

# Alergia registrada (palabra clave) -> principios activos que la disparan
ALERGIAS_CRUZADAS: dict[str, list[str]] = {
    "penicilina": ["penicilina", "amoxicilina", "ampicilina", "dicloxacilina", "oxacilina", "piperacilina",
                   "benzatinica", "sultamicilina"],
    "cefalosporina": ["cefalexina", "cefazolina", "cefuroxima", "ceftriaxona", "cefotaxima", "cefepime", "cefadroxilo"],
    "sulfa": ["sulfametoxazol", "sulfadiazina", "sulfasalazina"],
    "aine": ["ibuprofeno", "naproxeno", "diclofenaco", "ketorolaco", "aspirina", "acido acetilsalicilico",
             "meloxicam", "celecoxib", "piroxicam", "dipirona", "metamizol"],
    "aspirina": ["aspirina", "acido acetilsalicilico", "ibuprofeno", "naproxeno", "diclofenaco", "ketorolaco"],
    "dipirona": ["dipirona", "metamizol"],
    "yodo": ["medio de contraste yodado", "amiodarona", "povidona"],
    "macrolido": ["azitromicina", "claritromicina", "eritromicina"],
    "quinolona": ["ciprofloxacina", "levofloxacina", "moxifloxacina", "norfloxacina"],
    "latex": [],
}
# Posibilidad de reactividad cruzada (advertencia de menor nivel)
CRUZADA_PARCIAL = {"penicilina": ALERGIAS_CRUZADAS["cefalosporina"]}

# (fármaco A, fármaco B, severidad, efecto/recomendación)
INTERACCIONES: list[tuple[str, str, str, str]] = [
    ("warfarina", "ibuprofeno", "alta", "Aumenta el riesgo de sangrado. Evitar AINE; preferir acetaminofén."),
    ("warfarina", "naproxeno", "alta", "Aumenta el riesgo de sangrado."),
    ("warfarina", "diclofenaco", "alta", "Aumenta el riesgo de sangrado."),
    ("warfarina", "aspirina", "alta", "Aumenta el riesgo de sangrado."),
    ("warfarina", "metronidazol", "alta", "Potencia el efecto anticoagulante (vigilar INR)."),
    ("warfarina", "fluconazol", "alta", "Potencia el efecto anticoagulante (vigilar INR)."),
    ("sildenafil", "nitroglicerina", "contraindicada", "Hipotensión grave. No combinar con nitratos."),
    ("sildenafil", "dinitrato de isosorbida", "contraindicada", "Hipotensión grave. No combinar con nitratos."),
    ("enalapril", "espironolactona", "alta", "Riesgo de hiperpotasemia. Vigilar potasio y función renal."),
    ("losartan", "espironolactona", "alta", "Riesgo de hiperpotasemia. Vigilar potasio y función renal."),
    ("enalapril", "losartan", "alta", "Doble bloqueo del sistema renina-angiotensina: hiperpotasemia e insuficiencia renal."),
    ("simvastatina", "claritromicina", "alta", "Riesgo de miopatía/rabdomiólisis."),
    ("atorvastatina", "claritromicina", "moderada", "Aumenta niveles de la estatina (miopatía)."),
    ("tramadol", "fluoxetina", "alta", "Riesgo de síndrome serotoninérgico y convulsiones."),
    ("tramadol", "sertralina", "alta", "Riesgo de síndrome serotoninérgico."),
    ("litio", "ibuprofeno", "alta", "Aumenta niveles de litio (toxicidad)."),
    ("litio", "enalapril", "alta", "Aumenta niveles de litio (toxicidad)."),
    ("clopidogrel", "omeprazol", "moderada", "Puede disminuir el efecto antiagregante; preferir pantoprazol."),
    ("metformina", "medio de contraste yodado", "moderada", "Riesgo de acidosis láctica; suspender según función renal."),
    ("ciprofloxacina", "teofilina", "alta", "Aumenta niveles de teofilina (toxicidad)."),
    ("ketorolaco", "ibuprofeno", "alta", "Duplicidad de AINE: riesgo gastrointestinal y renal."),
    ("haloperidol", "azitromicina", "moderada", "Prolongación del intervalo QT."),
]

# Eventos de interés en salud pública (SIVIGILA - INS). Prefijo CIE-10 -> evento.
SIVIGILA: list[tuple[str, str]] = [
    ("A90", "Dengue"), ("A91", "Dengue grave"), ("A920", "Chikungunya"),
    ("A15", "Tuberculosis"), ("A16", "Tuberculosis"), ("A17", "Tuberculosis"), ("A18", "Tuberculosis"), ("A19", "Tuberculosis"),
    ("B20", "VIH/SIDA"), ("B21", "VIH/SIDA"), ("B22", "VIH/SIDA"), ("B23", "VIH/SIDA"), ("B24", "VIH/SIDA"),
    ("A50", "Sífilis congénita"), ("A51", "Sífilis gestacional/adquirida"), ("A53", "Sífilis"),
    ("B50", "Malaria"), ("B51", "Malaria"), ("B52", "Malaria"), ("B53", "Malaria"), ("B54", "Malaria"),
    ("U07", "COVID-19 / IRAG"), ("B05", "Sarampión"), ("B06", "Rubéola"), ("A37", "Tos ferina"),
    ("A33", "Tétanos neonatal"), ("A35", "Tétanos accidental"), ("A39", "Meningitis meningocócica"),
    ("A82", "Rabia humana"), ("A27", "Leptospirosis"), ("A01", "Fiebre tifoidea y paratifoidea"),
    ("A00", "Cólera"), ("B15", "Hepatitis A"), ("B16", "Hepatitis B"), ("B171", "Hepatitis C"),
    ("A30", "Lepra"), ("B55", "Leishmaniasis"), ("B57", "Enfermedad de Chagas"),
    ("O14", "Morbilidad materna extrema (evaluar)"), ("O15", "Morbilidad materna extrema (evaluar)"),
    ("T60", "Intoxicación por plaguicidas"), ("T40", "Intoxicación por sustancias psicoactivas"),
    ("T74", "Violencia de género e intrafamiliar"), ("X6", "Intento de suicidio"), ("X7", "Intento de suicidio"),
    ("X80", "Intento de suicidio"), ("X81", "Intento de suicidio"), ("X82", "Intento de suicidio"),
    ("X83", "Intento de suicidio"), ("X84", "Intento de suicidio"), ("W54", "Agresión por animal potencialmente transmisor de rabia"),
    ("E40", "Desnutrición aguda en menores de 5 años"), ("E41", "Desnutrición aguda en menores de 5 años"),
    ("E42", "Desnutrición aguda en menores de 5 años"), ("E43", "Desnutrición aguda en menores de 5 años"),
]


def eventos_sivigila(codigos: list[str]) -> list[dict]:
    salida, vistos = [], set()
    for codigo in codigos:
        for prefijo, evento in SIVIGILA:
            if codigo.startswith(prefijo) and (codigo, evento) not in vistos:
                vistos.add((codigo, evento))
                salida.append({"codigo": codigo, "evento": evento})
    return salida


def _contiene(texto_norm: str, termino: str) -> bool:
    return f" {normalizar(termino)} " in f" {texto_norm} "


def alertas_alergia(alergias: str | None, medicamentos: list[str]) -> list[dict]:
    if not alergias or normalizar(alergias) in ("", "ninguna", "ninguna conocida", "niega"):
        return []
    alergia_norm = normalizar(alergias)
    salida = []
    for med in medicamentos:
        med_norm = normalizar(med)
        for clave, farmacos in ALERGIAS_CRUZADAS.items():
            if clave in alergia_norm or any(f in alergia_norm for f in farmacos):
                if any(_contiene(med_norm, f) for f in farmacos + [clave]):
                    salida.append({"medicamento": med, "severidad": "alta",
                                   "mensaje": f"ALERGIA: el paciente reporta alergia a '{alergias}' y se formula {med}."})
                    break
                if any(_contiene(med_norm, f) for f in CRUZADA_PARCIAL.get(clave, [])):
                    salida.append({"medicamento": med, "severidad": "moderada",
                                   "mensaje": f"Posible reactividad cruzada: alergia a {clave} y se formula {med}."})
                    break
    return salida


def alertas_interaccion(medicamentos: list[str]) -> list[dict]:
    norm = [(m, normalizar(m)) for m in medicamentos]
    salida = []
    for a, b, severidad, efecto in INTERACCIONES:
        con_a = [m for m, n in norm if _contiene(n, a)]
        con_b = [m for m, n in norm if _contiene(n, b)]
        pares = [(x, y) for x in con_a for y in con_b if x != y]  # deben ser medicamentos distintos
        if pares:
            con_a, con_b = [pares[0][0]], [pares[0][1]]
            salida.append({"medicamentos": [con_a[0], con_b[0]], "severidad": severidad, "mensaje": efecto})
    return salida


def revisar_prescripcion(alergias: str | None, medicamentos: list[str]) -> list[dict]:
    return alertas_alergia(alergias, medicamentos) + alertas_interaccion(medicamentos)


# ----------------------------------------------------------------------------- Plantillas de HC
PLANTILLAS: dict[str, dict] = {
    "medicina_general": {
        "nombre": "Consulta de medicina general",
        "revision_sistemas": "Niega síntomas cardiorrespiratorios, gastrointestinales, genitourinarios y neurológicos.",
        "examen_fisico": "Paciente en buen estado general, alerta, orientado, hidratado, afebril.\nCabeza y cuello: normal.\n"
                         "Tórax: ruidos cardiacos rítmicos sin soplos, murmullo vesicular conservado.\n"
                         "Abdomen: blando, no doloroso, sin masas ni megalias.\nExtremidades: sin edemas, pulsos presentes.\n"
                         "Neurológico: sin déficit aparente.",
        "plan": "Recomendaciones generales y signos de alarma explicados. Control según evolución.",
    },
    "control_hta": {
        "nombre": "Control de hipertensión arterial (ruta cardiovascular)",
        "motivo_consulta": "Control de hipertensión arterial",
        "enfermedad_actual": "Paciente con diagnóstico de HTA en manejo con ___. Adherencia: ___. Cifras en casa: ___. "
                             "Niega cefalea, dolor torácico, disnea, edemas o síntomas neurológicos.",
        "examen_fisico": "TA en ambos brazos. Fondo de ojo: ___. Ruidos cardiacos: ___. Pulsos periféricos: ___. Edemas: ___.",
        "plan": "Dieta hiposódica (<2 g de sodio/día), actividad física 150 min/semana, control de peso, "
                "cesación de tabaco. Paraclínicos: creatinina, perfil lipídico, glucemia, uroanálisis, EKG anual.",
    },
    "control_prenatal": {
        "nombre": "Control prenatal (Resolución 3280 de 2018)",
        "motivo_consulta": "Control prenatal",
        "enfermedad_actual": "Gestante de ___ semanas por FUM/ecografía. Movimientos fetales: ___. Niega sangrado, "
                             "pérdida de líquido, cefalea, fosfenos, tinnitus, epigastralgia o edemas.",
        "examen_fisico": "Altura uterina: ___ cm. FCF: ___ lpm. Presentación: ___. Edemas: ___.",
        "plan": "Micronutrientes (ácido fólico, hierro, calcio). Signos de alarma explicados. Próximo control: ___.",
    },
    "crecimiento_desarrollo": {
        "nombre": "Valoración integral primera infancia / infancia",
        "motivo_consulta": "Valoración integral (crecimiento y desarrollo)",
        "examen_fisico": "Peso: ___ Talla: ___ PC: ___. Indicadores antropométricos según OMS: ___. "
                         "Desarrollo (escala abreviada): ___. Esquema de vacunación: ___.",
        "plan": "Pautas de crianza, alimentación, salud oral, prevención de accidentes. Próxima valoración: ___.",
    },
    "urgencias": {
        "nombre": "Atención de urgencias",
        "enfermedad_actual": "Cuadro de ___ horas de evolución consistente en ___.",
        "examen_fisico": "Estado general: ___. Escala de Glasgow: ___/15. Hallazgos positivos: ___.",
        "plan": "Conducta: observación / hospitalización / remisión / egreso. Signos de alarma explicados.",
    },
}
