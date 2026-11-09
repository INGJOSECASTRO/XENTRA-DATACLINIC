import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import LECTURA_HC, REGISTRO_PACIENTES, ip_cliente, requiere_rol
from app.models import Atencion, Paciente, Usuario
from app.schemas import AtencionResumen, PacienteActualizar, PacienteCrear, PacienteOut
from app.services.ledger import registrar_evento
from app.services.rips import edad_en

router = APIRouter(prefix="/api/pacientes", tags=["Pacientes"])
LECTORES = tuple(set(LECTURA_HC) | set(REGISTRO_PACIENTES))


def a_salida(p: Paciente) -> PacienteOut:
    salida = PacienteOut.model_validate(p)
    salida.edad = edad_en(p.fecha_nacimiento)
    return salida


def obtener(db: Session, paciente_id: uuid.UUID) -> Paciente:
    p = db.get(Paciente, paciente_id)
    if not p:
        raise HTTPException(404, "Paciente no encontrado")
    return p


@router.get("", response_model=list[PacienteOut])
def listar(
    q: str | None = Query(None, description="Documento o nombre"),
    limite: int = Query(50, le=200),
    db: Session = Depends(get_db),
    _: Usuario = Depends(requiere_rol(*LECTORES)),
):
    consulta = select(Paciente).order_by(Paciente.creado_en.desc()).limit(limite)
    if q:
        patron = f"%{q.strip()}%"
        nombre = func.concat(Paciente.primer_nombre, " ", Paciente.primer_apellido, " ", func.coalesce(Paciente.segundo_apellido, ""))
        consulta = consulta.where(or_(Paciente.numero_documento.like(patron), nombre.ilike(patron)))
    return [a_salida(p) for p in db.scalars(consulta).all()]


@router.post("", response_model=PacienteOut, status_code=201)
def crear(datos: PacienteCrear, request: Request, db: Session = Depends(get_db),
          usuario: Usuario = Depends(requiere_rol(*REGISTRO_PACIENTES))):
    existe = db.scalars(select(Paciente).where(
        Paciente.tipo_documento == datos.tipo_documento, Paciente.numero_documento == datos.numero_documento)).first()
    if existe:
        raise HTTPException(409, "Ya existe un paciente con ese documento")
    p = Paciente(**datos.model_dump())
    if p.autoriza_tratamiento_datos:
        p.fecha_autorizacion_datos = datetime.now(timezone.utc)
    db.add(p)
    db.flush()
    registrar_evento(db, accion="PACIENTE_CREADO", entidad="paciente", entidad_id=p.id,
                     datos=datos.model_dump(mode="json"), usuario_id=usuario.id, ip=ip_cliente(request))
    db.commit()
    return a_salida(p)


@router.get("/{paciente_id}", response_model=PacienteOut)
def detalle(paciente_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
            usuario: Usuario = Depends(requiere_rol(*LECTORES))):
    p = obtener(db, paciente_id)
    # Trazabilidad de accesos: quién consultó la HC, cuándo y desde dónde.
    registrar_evento(db, accion="CONSULTA_PACIENTE", entidad="paciente", entidad_id=p.id,
                     usuario_id=usuario.id, ip=ip_cliente(request))
    db.commit()
    return a_salida(p)


@router.patch("/{paciente_id}", response_model=PacienteOut)
def actualizar(paciente_id: uuid.UUID, datos: PacienteActualizar, request: Request, db: Session = Depends(get_db),
               usuario: Usuario = Depends(requiere_rol(*REGISTRO_PACIENTES))):
    p = obtener(db, paciente_id)
    cambios = datos.model_dump(exclude_unset=True)
    for campo, valor in cambios.items():
        setattr(p, campo, valor)
    if cambios.get("autoriza_tratamiento_datos") and not p.fecha_autorizacion_datos:
        p.fecha_autorizacion_datos = datetime.now(timezone.utc)
    registrar_evento(db, accion="PACIENTE_ACTUALIZADO", entidad="paciente", entidad_id=p.id,
                     datos=datos.model_dump(mode="json", exclude_unset=True), usuario_id=usuario.id, ip=ip_cliente(request))
    db.commit()
    return a_salida(p)


@router.get("/{paciente_id}/historia", response_model=list[AtencionResumen])
def historia(paciente_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
             usuario: Usuario = Depends(requiere_rol(*LECTURA_HC))):
    obtener(db, paciente_id)
    registrar_evento(db, accion="CONSULTA_HC", entidad="paciente", entidad_id=paciente_id,
                     usuario_id=usuario.id, ip=ip_cliente(request))
    db.commit()
    return db.scalars(select(Atencion).where(Atencion.paciente_id == paciente_id)
                      .order_by(Atencion.fecha_inicio.desc())).all()
