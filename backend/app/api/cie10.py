from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import usuario_actual, requiere_rol, CLINICOS
from app.models import CIE10, Paciente, Usuario
from app.schemas import CIE10Out, SugerenciaIn, SugerenciasOut
from app.services import cie10 as catalogo
from app.services.ia import sugerir_cie10
from app.services.rips import edad_en

router = APIRouter(prefix="/api/cie10", tags=["CIE-10 e inteligencia artificial"])


@router.get("", response_model=list[CIE10Out])
def buscar(q: str = Query(..., min_length=1), limite: int = Query(20, le=100),
           db: Session = Depends(get_db), _: Usuario = Depends(usuario_actual)):
    return catalogo.buscar(db, q, limite)


@router.get("/{codigo}", response_model=CIE10Out)
def obtener(codigo: str, db: Session = Depends(get_db), _: Usuario = Depends(usuario_actual)):
    fila = db.get(CIE10, catalogo.formatear_codigo(codigo))
    if not fila:
        raise HTTPException(404, "Código no encontrado")
    return fila


@router.post("/sugerir", response_model=SugerenciasOut)
def sugerir(datos: SugerenciaIn, db: Session = Depends(get_db), _: Usuario = Depends(requiere_rol(*CLINICOS))):
    """Sugiere diagnósticos CIE-10 a partir del texto clínico (motivo, enfermedad actual, análisis)."""
    sexo = edad = None
    nombres: list[str] = []
    if datos.paciente_id:
        p = db.get(Paciente, datos.paciente_id)
        if p:
            sexo, edad = p.sexo, edad_en(p.fecha_nacimiento)
            nombres = [p.primer_nombre, p.segundo_nombre, p.primer_apellido, p.segundo_apellido]
    return sugerir_cie10(db, datos.texto, sexo, edad, nombres)
