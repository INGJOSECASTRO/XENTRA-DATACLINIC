"""Órdenes y resultados de laboratorio clínico e imágenes diagnósticas; consentimientos informados."""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CLINICOS, LABORATORIO, LECTURA_HC, MEDICOS, ip_cliente, requiere_rol
from app.models import Paciente, Usuario
from app.models_ext import Consentimiento, OrdenServicio
from app.schemas_ext import ConsentimientoIn, ConsentimientoOut, OrdenServicioIn, OrdenServicioOut, ResultadoIn
from app.services import hospital as srv
from app.services.ledger import registrar_evento
from app.services.rips import edad_en

router = APIRouter(prefix="/api", tags=["Laboratorio, imágenes y consentimientos"])


def _orden(db: Session, orden_id: uuid.UUID) -> OrdenServicio:
    o = db.get(OrdenServicio, orden_id)
    if not o:
        raise HTTPException(404, "Orden no encontrada")
    return o


@router.post("/ordenes-servicio", response_model=OrdenServicioOut, status_code=201)
def ordenar(datos: OrdenServicioIn, request: Request, db: Session = Depends(get_db),
            usuario: Usuario = Depends(requiere_rol(*MEDICOS))):
    if not db.get(Paciente, datos.paciente_id):
        raise HTTPException(404, "Paciente no encontrado")
    o = OrdenServicio(**datos.model_dump(), ordenado_por=usuario.id)
    db.add(o)
    db.flush()
    registrar_evento(db, accion="ORDEN_SERVICIO", entidad="orden_servicio", entidad_id=o.id,
                     datos={"cups": o.cod_cups, "paciente_id": str(o.paciente_id)}, usuario_id=usuario.id, ip=ip_cliente(request))
    db.commit()
    db.refresh(o)
    return o


@router.get("/ordenes-servicio", response_model=list[OrdenServicioOut])
def listar(estado: str | None = None, tipo: str | None = None, paciente_id: uuid.UUID | None = None,
           db: Session = Depends(get_db), _: Usuario = Depends(requiere_rol(*LECTURA_HC, *LABORATORIO))):
    q = select(OrdenServicio).order_by(OrdenServicio.prioridad.desc(), OrdenServicio.fecha.desc()).limit(300)
    if estado:
        q = q.where(OrdenServicio.estado == estado)
    if tipo:
        q = q.where(OrdenServicio.tipo == tipo)
    if paciente_id:
        q = q.where(OrdenServicio.paciente_id == paciente_id)
    return db.scalars(q).all()


@router.post("/ordenes-servicio/{orden_id}/toma", response_model=OrdenServicioOut)
def toma(orden_id: uuid.UUID, db: Session = Depends(get_db), _: Usuario = Depends(requiere_rol(*LABORATORIO, "enfermeria"))):
    o = _orden(db, orden_id)
    if o.estado != "ordenada":
        raise HTTPException(409, "La muestra ya fue tomada")
    o.estado, o.fecha_toma = "tomada", datetime.now(timezone.utc)
    db.commit()
    return o


@router.post("/ordenes-servicio/{orden_id}/resultado", response_model=OrdenServicioOut)
def resultado(orden_id: uuid.UUID, datos: ResultadoIn, db: Session = Depends(get_db),
              _: Usuario = Depends(requiere_rol(*LABORATORIO, "medico"))):
    o = _orden(db, orden_id)
    if o.estado == "validada":
        raise HTTPException(409, "El resultado ya fue validado y es inalterable")
    if not datos.resultados and not datos.informe:
        raise HTTPException(422, "Registre valores o un informe")
    o.resultados = srv.marcar_anormales([r.model_dump() for r in datos.resultados])
    o.informe, o.estado = datos.informe, "resultado"
    db.commit()
    return o


@router.post("/ordenes-servicio/{orden_id}/validar", response_model=OrdenServicioOut)
def validar(orden_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
            usuario: Usuario = Depends(requiere_rol(*LABORATORIO, "medico"))):
    """El profesional responsable (bacteriólogo / radiólogo) valida y sella el resultado."""
    o = _orden(db, orden_id)
    if o.estado != "resultado":
        raise HTTPException(409, "No hay resultado pendiente de validar")
    o.validado_por, o.fecha_resultado = usuario.id, datetime.now(timezone.utc)
    o.hash_resultado = srv.hash_resultado(o)
    o.estado = "validada"
    registrar_evento(db, accion="RESULTADO_VALIDADO", entidad="orden_servicio", entidad_id=o.id,
                     datos={"hash": o.hash_resultado}, usuario_id=usuario.id, ip=ip_cliente(request))
    db.commit()
    return o


# ============================================================================ CONSENTIMIENTOS
@router.get("/consentimientos/plantillas")
def plantillas(_: Usuario = Depends(requiere_rol(*CLINICOS))):
    return srv.PLANTILLAS_CONSENTIMIENTO


@router.post("/consentimientos", response_model=ConsentimientoOut, status_code=201)
def firmar(datos: ConsentimientoIn, request: Request, db: Session = Depends(get_db),
           usuario: Usuario = Depends(requiere_rol(*CLINICOS))):
    if not db.get(Paciente, datos.paciente_id):
        raise HTTPException(404, "Paciente no encontrado")
    c = Consentimiento(**datos.model_dump(), profesional_id=usuario.id, id=uuid.uuid4(),
                       fecha=datetime.now(timezone.utc).replace(microsecond=0))
    c.hash_contenido = srv.hash_consentimiento(c)
    db.add(c)
    db.flush()
    registrar_evento(db, accion="CONSENTIMIENTO", entidad="consentimiento", entidad_id=c.id,
                     datos={"paciente_id": str(c.paciente_id), "decision": c.decision, "hash": c.hash_contenido},
                     usuario_id=usuario.id, ip=ip_cliente(request))
    db.commit()
    db.refresh(c)
    return c


@router.get("/pacientes/{paciente_id}/consentimientos", response_model=list[ConsentimientoOut])
def del_paciente(paciente_id: uuid.UUID, db: Session = Depends(get_db), _: Usuario = Depends(requiere_rol(*LECTURA_HC))):
    return db.scalars(select(Consentimiento).where(Consentimiento.paciente_id == paciente_id)
                      .order_by(Consentimiento.fecha.desc())).all()


@router.get("/consentimientos/{consentimiento_id}/pdf")
def consentimiento_pdf(consentimiento_id: uuid.UUID, db: Session = Depends(get_db),
                       _: Usuario = Depends(requiere_rol(*LECTURA_HC))):
    from app.services.pdf import pdf_consentimiento

    c = db.get(Consentimiento, consentimiento_id)
    if not c:
        raise HTTPException(404, "Consentimiento no encontrado")
    p = db.get(Paciente, c.paciente_id)
    return Response(pdf_consentimiento(c, p, edad_en(p.fecha_nacimiento)), media_type="application/pdf",
                    headers={"Content-Disposition": 'inline; filename="consentimiento.pdf"'})
