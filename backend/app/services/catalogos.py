"""Tablas de referencia. Los valores de muestra deben reemplazarse por las tablas oficiales
vigentes de SISPRO (web.sispro.gov.co -> Tablas de referencia) con:
    python -m app.cargar_catalogo <tipo> archivo.csv     (columnas: codigo;descripcion[;datos_json])
"""
import csv
import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models_ext import Catalogo
from app.services.texto import normalizar

RUTA = Path(__file__).resolve().parent.parent / "data" / "catalogos_muestra.csv"

TIPOS = {
    "cups": "Procedimientos y servicios (CUPS)",
    "cum": "Medicamentos (CUM)",
    "divipola": "Municipios (DIVIPOLA)",
    "eapb": "EPS / entidades administradoras de planes de beneficios",
    "tipo_usuario": "Tipo de usuario (régimen)",
    "modalidad": "Modalidad de realización de la tecnología",
    "grupo_servicio": "Grupo de servicios",
    "servicio": "Servicios habilitados (REPS)",
    "finalidad": "Finalidad de la tecnología en salud",
    "causa_atencion": "Causa / motivo de atención",
    "via_ingreso": "Vía de ingreso al servicio",
    "condicion_egreso": "Condición y destino del usuario al egreso",
    "concepto_recaudo": "Concepto de recaudo",
    "tipo_medicamento": "Tipo de medicamento",
}


def _fila(tipo: str, codigo: str, descripcion: str, datos: dict | None) -> Catalogo:
    return Catalogo(tipo=tipo, codigo=codigo.strip(), descripcion=descripcion.strip().upper()[:300],
                    texto_busqueda=normalizar(f"{codigo} {descripcion}"), datos=datos)


def cargar_muestra(db: Session) -> int:
    if db.scalars(select(Catalogo).limit(1)).first():
        return 0
    n = 0
    with open(RUTA, encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter=";"):
            datos = json.loads(r["datos"]) if r.get("datos") else None
            db.add(_fila(r["tipo"], r["codigo"], r["descripcion"], datos))
            n += 1
    db.commit()
    return n


def cargar_csv(db: Session, tipo: str, ruta: Path, reemplazar: bool = False) -> int:
    if reemplazar:
        db.query(Catalogo).filter(Catalogo.tipo == tipo).delete()
    existentes = set(db.scalars(select(Catalogo.codigo).where(Catalogo.tipo == tipo)).all())
    n = 0
    with open(ruta, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f, delimiter=";"):
            codigo = (r.get("codigo") or "").strip()
            if not codigo or codigo in existentes:
                continue
            datos = json.loads(r["datos"]) if r.get("datos") else None
            db.add(_fila(tipo, codigo, r.get("descripcion") or "", datos))
            existentes.add(codigo)
            n += 1
    db.commit()
    return n


def buscar(db: Session, tipo: str, q: str | None = None, limite: int = 50) -> list[Catalogo]:
    consulta = select(Catalogo).where(Catalogo.tipo == tipo, Catalogo.activo.is_(True)).order_by(Catalogo.codigo)
    if q:
        for termino in normalizar(q).split():
            consulta = consulta.where(Catalogo.texto_busqueda.contains(termino))
    return list(db.scalars(consulta.limit(limite)).all())


def obtener(db: Session, tipo: str, codigo: str) -> Catalogo | None:
    return db.scalars(select(Catalogo).where(Catalogo.tipo == tipo, Catalogo.codigo == codigo)).first()


def existe_o_sin_catalogo(db: Session, tipo: str, codigo: str | None) -> bool:
    """True si el código existe, o si ese catálogo aún no se ha cargado (no bloquea la operación)."""
    if not codigo:
        return True
    if not db.scalars(select(Catalogo.id).where(Catalogo.tipo == tipo).limit(1)).first():
        return True
    return obtener(db, tipo, codigo) is not None
