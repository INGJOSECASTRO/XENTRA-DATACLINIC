"""Sedes, catálogos de referencia, plantillas y revisión de seguridad de la fórmula."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import ADMIN_GESTION, CLINICOS_FORMACION, PERSONAL, ip_cliente, requiere_rol
from app.models import Paciente, Usuario
from app.models_ext import Sede
from app.services import catalogos, seguridad_clinica
from app.services.ledger import registrar_evento

router = APIRouter(prefix="/api", tags=["Administración y catálogos"])


class SedeIn(BaseModel):
    nombre: str = Field(min_length=2)
    cod_habilitacion: str = Field(pattern=r"^\d{12}$")
    cod_municipio: str = Field("11001", pattern=r"^\d{5}$")
    direccion: str | None = None
    telefono: str | None = None
    activa: bool = True


class SedeOut(SedeIn):
    id: uuid.UUID
    model_config = {"from_attributes": True}


class CatalogoOut(BaseModel):
    codigo: str
    descripcion: str
    datos: dict | None
    model_config = {"from_attributes": True}


class RevisionIn(BaseModel):
    paciente_id: uuid.UUID
    medicamentos: list[str]


@router.get("/sedes", response_model=list[SedeOut])
def sedes(db: Session = Depends(get_db), _: Usuario = Depends(requiere_rol(*PERSONAL))):
    return db.scalars(select(Sede).order_by(Sede.nombre)).all()


@router.post("/sedes", response_model=SedeOut, status_code=201)
def crear_sede(datos: SedeIn, request: Request, db: Session = Depends(get_db), admin: Usuario = Depends(requiere_rol(*ADMIN_GESTION))):
    sede = Sede(**datos.model_dump())
    db.add(sede)
    db.flush()
    registrar_evento(db, accion="SEDE_CREADA", entidad="sede", entidad_id=sede.id, datos=datos.model_dump(),
                     usuario_id=admin.id, ip=ip_cliente(request))
    db.commit()
    return sede


@router.put("/sedes/{sede_id}", response_model=SedeOut)
def editar_sede(sede_id: uuid.UUID, datos: SedeIn, db: Session = Depends(get_db), _: Usuario = Depends(requiere_rol(*ADMIN_GESTION))):
    sede = db.get(Sede, sede_id)
    if not sede:
        raise HTTPException(404, "Sede no encontrada")
    for k, v in datos.model_dump().items():
        setattr(sede, k, v)
    db.commit()
    return sede


@router.get("/catalogos")
def tipos_catalogo(_: Usuario = Depends(requiere_rol(*PERSONAL))):
    return catalogos.TIPOS


@router.get("/catalogos/{tipo}", response_model=list[CatalogoOut])
def catalogo(tipo: str, q: str | None = None, limite: int = Query(100, le=500), db: Session = Depends(get_db),
             _: Usuario = Depends(requiere_rol(*PERSONAL))):
    if tipo not in catalogos.TIPOS:
        raise HTTPException(404, "Catálogo no existe")
    return catalogos.buscar(db, tipo, q, limite)


@router.get("/clinica/plantillas")
def plantillas(_: Usuario = Depends(requiere_rol(*CLINICOS_FORMACION))):
    return seguridad_clinica.PLANTILLAS


@router.post("/clinica/revisar-prescripcion")
def revisar(datos: RevisionIn, db: Session = Depends(get_db), _: Usuario = Depends(requiere_rol(*CLINICOS_FORMACION))):
    """Alergias e interacciones en tiempo real mientras el médico formula."""
    p = db.get(Paciente, datos.paciente_id)
    if not p:
        raise HTTPException(404, "Paciente no encontrado")
    return seguridad_clinica.revisar_prescripcion(p.alergias, [m for m in datos.medicamentos if m.strip()])
