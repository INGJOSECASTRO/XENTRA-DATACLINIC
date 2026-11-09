"""Catálogo CIE-10 y motor LOCAL de sugerencia de diagnósticos (sin internet).

El motor local combina:
1. Un diccionario de sinónimos coloquiales colombianos ("gripa", "azúcar alta"...).
2. Puntuación TF-IDF entre el texto clínico y las descripciones oficiales CIE-10.
3. Filtros de pertinencia por sexo y edad (igual que el validador del Ministerio).

Para cargar el catálogo OFICIAL completo use:
    python -m app.cargar_cie10 ruta/al/archivo.csv
"""
import csv
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import CIE10
from app.services.texto import normalizar

RUTA_MUESTRA = Path(__file__).resolve().parent.parent / "data" / "cie10_muestra.csv"
_cache_indice: dict = {}
PATRON_CODIGO = re.compile(r"^[A-Z][0-9]{2}[0-9X]$")

STOPWORDS = set(
    "a al algo ante con contra de del desde el ella en entre es esta este hace han hasta la las le "
    "lo los mas me mi muy no nos o otra otro otras otros para pero por que se sin sobre su sus tiene "
    "un una uno y ya refiere paciente consulta cuadro clinico dias dia horas hora semanas meses años anos "
    "evolucion presenta asociado acompanado desde hace manifiesta niega actual tipo especificado "
    "especificada especificacion otra sitio parte".split()
)

# Sinónimos / lenguaje coloquial -> términos usados en las descripciones CIE-10
SINONIMOS: dict[str, str] = {
    "gripa": "rinofaringitis resfriado",
    "gripe": "rinofaringitis resfriado influenza",
    "resfriado": "rinofaringitis resfriado",
    "mocos": "rinofaringitis rinitis",
    "congestion nasal": "rinofaringitis rinitis",
    "estornudos": "rinitis alergica",
    "dolor de garganta": "faringitis",
    "odinofagia": "faringitis amigdalitis",
    "placas en amigdalas": "amigdalitis",
    "dolor de cabeza": "cefalea",
    "jaqueca": "migrana",
    "presion alta": "hipertension",
    "tension alta": "hipertension",
    "hta": "hipertension esencial",
    "azucar alta": "diabetes mellitus",
    "glucosa alta": "diabetes mellitus",
    "dm2": "diabetes mellitus no insulinodependiente",
    "diabetico": "diabetes mellitus",
    "diabetica": "diabetes mellitus",
    "colesterol alto": "hipercolesterolemia",
    "trigliceridos altos": "hipergliceridemia",
    "sobrepeso": "obesidad",
    "deposiciones liquidas": "diarrea gastroenteritis",
    "evacuaciones liquidas": "diarrea gastroenteritis",
    "soltura": "diarrea gastroenteritis",
    "vomito": "nausea vomito",
    "vomitos": "nausea vomito",
    "agrieras": "reflujo gastroesofagico dispepsia",
    "acidez": "reflujo gastroesofagico dispepsia",
    "pirosis": "reflujo gastroesofagico",
    "dolor de estomago": "dolor abdominal gastritis",
    "epigastralgia": "gastritis dispepsia dolor abdominal superior",
    "estrenimiento": "constipacion",
    "ardor al orinar": "infeccion vias urinarias cistitis",
    "disuria": "infeccion vias urinarias cistitis",
    "polaquiuria": "infeccion vias urinarias cistitis",
    "dolor de espalda": "lumbago dorsalgia",
    "dolor lumbar": "lumbago",
    "lumbalgia": "lumbago",
    "dolor de cuello": "cervicalgia",
    "ahogo": "disnea asma",
    "sibilancias": "asma bronquiolitis",
    "silbido en el pecho": "asma",
    "tos con flema": "bronquitis tos",
    "expectoracion": "bronquitis tos",
    "fiebre alta": "fiebre",
    "calentura": "fiebre",
    "dolor en el pecho": "dolor pecho precordial",
    "tristeza": "depresivo",
    "deprimido": "depresivo",
    "depresion": "episodio depresivo",
    "nervios": "ansiedad",
    "angustia": "ansiedad panico",
    "no puede dormir": "insomnio",
    "mareo": "mareo vertigo",
    "torcedura": "esguince torcedura",
    "esguince": "esguince torcedura",
    "ojo rojo": "conjuntivitis",
    "lagana": "conjuntivitis mucopurulenta",
    "dolor de oido": "otitis",
    "otalgia": "otitis",
    "rasquina": "dermatitis urticaria escabiosis",
    "picazon": "dermatitis urticaria",
    "prurito": "dermatitis urticaria",
    "ronchas": "urticaria",
    "granos": "acne",
    "hongos": "micosis tina",
    "embarazada": "embarazo supervision",
    "gestante": "embarazo supervision",
    "control prenatal": "supervision embarazo normal",
    "colico menstrual": "dismenorrea",
    "dolor menstrual": "dismenorrea",
    "chequeo": "examen medico general",
    "control de rutina": "examen medico general control salud rutina",
    "formula": "repeticion receta",
    "renovar formula": "repeticion receta",
    "zancudo": "dengue",
    "dolor de huesos": "dengue mialgia",
    "dolor muscular": "mialgia",
    "cansancio": "malestar fatiga",
    "anemico": "anemia",
}


@dataclass
class Sugerencia:
    codigo: str
    descripcion: str
    confianza: float
    justificacion: str
    fuente: str = "local"


def formatear_codigo(codigo: str) -> str:
    """'i10' -> 'I10X' ; 'J00.X' -> 'J00X' ; 'E11.9' -> 'E119' (formato RIPS Colombia, 4 caracteres)."""
    c = (codigo or "").upper().replace(".", "").replace(" ", "").strip()
    if len(c) == 3:
        c += "X"
    return c


def codigo_valido(codigo: str) -> bool:
    return bool(PATRON_CODIGO.match(codigo or ""))


def cargar_csv(db: Session, ruta: Path = RUTA_MUESTRA, reemplazar: bool = False) -> int:
    """Carga un CSV separado por ';' con columnas codigo;descripcion[;sexo;edad_minima;edad_maxima]."""
    if reemplazar:
        db.query(CIE10).delete()
    existentes = set(db.scalars(select(CIE10.codigo)).all())
    n = 0
    with open(ruta, encoding="utf-8-sig") as f:
        for fila in csv.DictReader(f, delimiter=";"):
            codigo = formatear_codigo(fila.get("codigo", ""))
            if not codigo_valido(codigo) or codigo in existentes:
                continue
            desc = (fila.get("descripcion") or "").strip().upper()
            db.add(
                CIE10(
                    codigo=codigo,
                    descripcion=desc[:255],
                    texto_busqueda=normalizar(f"{codigo} {desc}"),
                    sexo=(fila.get("sexo") or "A").strip().upper()[:1] or "A",
                    edad_minima=int(fila.get("edad_minima") or 0),
                    edad_maxima=int(fila.get("edad_maxima") or 120),
                )
            )
            existentes.add(codigo)
            n += 1
    db.commit()
    _cache_indice.clear()
    return n


def buscar(db: Session, q: str, limite: int = 20) -> list[CIE10]:
    q = (q or "").strip()
    if not q:
        return []
    cod = formatear_codigo(q) if len(q) <= 5 else ""
    terminos = [t for t in normalizar(q).split() if t]
    condiciones = [CIE10.codigo.startswith(q.upper().replace(".", ""))]
    if terminos:
        condiciones.append(func.coalesce(CIE10.texto_busqueda, "").contains(terminos[0]))
    filas = db.scalars(select(CIE10).where(or_(*condiciones)).limit(500)).all()
    filas = [f for f in filas if all(t in f.texto_busqueda for t in terminos) or f.codigo.startswith(q.upper())]
    filas.sort(key=lambda f: (f.codigo != cod, not f.codigo.startswith(q.upper()), f.codigo))
    return filas[:limite]


# ---------------------------------------------------------------------------
# Motor local de sugerencias
# ---------------------------------------------------------------------------
def _tokens(texto: str) -> list[str]:
    toks = []
    for t in normalizar(texto).split():
        if t in STOPWORDS or len(t) < 3:
            continue
        toks.append(t[:-1] if len(t) > 5 and t.endswith("s") else t)  # plural simple
    return toks


def _construir_indice(db: Session) -> tuple[list[CIE10], dict[str, float], list[Counter]]:
    filas = db.scalars(select(CIE10)).all()
    docs = [Counter(_tokens(f.descripcion)) for f in filas]
    df: Counter = Counter()
    for d in docs:
        df.update(d.keys())
    n = max(len(docs), 1)
    idf = {t: math.log((n + 1) / (c + 0.5)) for t, c in df.items()}
    return filas, idf, docs


def _obtener_indice(db: Session):
    total = db.scalar(select(func.count()).select_from(CIE10)) or 0
    if _cache_indice.get("total") != total:
        _cache_indice.update(total=total, datos=_construir_indice(db))
    return _cache_indice["datos"]


def expandir_sinonimos(texto: str) -> tuple[str, dict[str, set[str]]]:
    """Agrega términos técnicos; devuelve {expresión coloquial: tokens técnicos que aportó}."""
    norm = f" {normalizar(texto)} "
    agregados, usados = [], {}
    for coloquial, tecnico in SINONIMOS.items():
        if f" {coloquial} " in norm:
            agregados.append(tecnico)
            usados[coloquial] = set(_tokens(tecnico))
    return texto + " " + " ".join(agregados), usados


def sugerir_local(db: Session, texto: str, sexo: str | None = None, edad: int | None = None, limite: int = 5) -> list[Sugerencia]:
    filas, idf, docs = _obtener_indice(db)
    if not filas:
        return []
    texto_exp, usados = expandir_sinonimos(texto)
    consulta = Counter(_tokens(texto_exp))
    if not consulta:
        return []
    resultados = []
    for fila, doc in zip(filas, docs):
        if not pertinente(fila, sexo, edad):
            continue
        comunes = set(consulta) & set(doc)
        if not comunes:
            continue
        puntaje = sum(idf.get(t, 0) for t in comunes)
        cobertura = len(comunes) / max(len(doc), 1)  # qué tanto de la descripción se explica
        resultados.append((puntaje * (0.6 + 0.4 * cobertura), fila, comunes))
    resultados.sort(key=lambda r: r[0], reverse=True)
    if not resultados:
        return []
    maximo = resultados[0][0]
    salida = []
    for puntaje, fila, comunes in resultados[:limite]:
        motivo = "Coincide con: " + ", ".join(sorted(comunes))
        relacionados = [c for c, toks in usados.items() if toks & comunes]
        if relacionados:
            motivo += f" (interpretado de: {', '.join(relacionados)})"
        salida.append(
            Sugerencia(fila.codigo, fila.descripcion, round(min(0.95, 0.4 + 0.5 * puntaje / maximo), 2), motivo)
        )
    return salida


def pertinente(fila: CIE10, sexo: str | None, edad: int | None) -> bool:
    """Valida sexo/edad igual que las reglas de pertinencia de los validadores RIPS."""
    if sexo and fila.sexo in ("H", "M") and fila.sexo != sexo:
        return False
    if edad is not None and not (fila.edad_minima <= edad <= fila.edad_maxima):
        return False
    return True
