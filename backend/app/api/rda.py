"""RDA (Resolución 1888 de 2025): consulta de la cola, reintentos y RDA de paciente."""
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, get_db
from app.core.deps import LECTURA_HC, ip_cliente, requiere_rol
from app.models import Atencion, Paciente, Usuario
from app.models_ext import RdaEnvio
from app.services import rda
from app.services.ledger import registrar_evento

router = APIRouter(prefix="/api/rda", tags=["RDA - Resolución 1888 de 2025"])


def procesar_en_segundo_plano() -> None:
    with SessionLocal() as db:
        rda.procesar_pendientes(db)


def generar_y_encolar(db: Session, tipo_entidad: str, objeto, tareas: BackgroundTasks | None = None) -> None:
    """Se llama al firmar una atención o al dar egreso. Nunca bloquea el acto clínico."""
    import logging

    try:
        if tipo_entidad == "atencion":
            tipo, bundle = rda.rda_atencion(objeto)
        else:
            tipo, bundle = rda.rda_hospitalizacion(objeto)
        with db.begin_nested():
            rda.encolar(db, tipo, objeto.id, objeto.paciente_id, bundle)
        if tareas is not None:
            tareas.add_task(procesar_en_segundo_plano)
    except Exception as exc:
        logging.getLogger(__name__).exception("No se pudo generar el RDA de %s %s: %s", tipo_entidad, objeto.id, exc)


@router.get("/resumen")
def resumen(db: Session = Depends(get_db), _: Usuario = Depends(requiere_rol("admin", "auditor", "medico"))):
    filas = db.execute(select(RdaEnvio.estado, func.count()).group_by(RdaEnvio.estado)).all()
    from app.core.config import settings

    return {"modo": settings.RDA_MODO, "por_estado": {e: n for e, n in filas}}


@router.get("")
def listar(estado: str | None = None, db: Session = Depends(get_db), _: Usuario = Depends(requiere_rol("admin", "auditor"))):
    q = select(RdaEnvio).order_by(RdaEnvio.generado_en.desc()).limit(300)
    if estado:
        q = q.where(RdaEnvio.estado == estado)
    return [{"id": str(e.id), "tipo": e.tipo, "entidad_id": e.entidad_id, "paciente_id": str(e.paciente_id),
             "generado_en": e.generado_en, "estado": e.estado, "intentos": e.intentos, "ultimo_intento": e.ultimo_intento,
             "respuesta": e.respuesta, "errores_validacion": e.errores_validacion, "hash": e.hash_bundle}
            for e in db.scalars(q).all()]


@router.get("/{envio_id}")
def documento(envio_id: uuid.UUID, db: Session = Depends(get_db), _: Usuario = Depends(requiere_rol(*LECTURA_HC))):
    e = db.get(RdaEnvio, envio_id)
    if not e:
        raise HTTPException(404, "RDA no encontrado")
    return e.bundle


@router.post("/procesar")
def procesar(db: Session = Depends(get_db), _: Usuario = Depends(requiere_rol("admin", "auditor"))):
    return rda.procesar_pendientes(db, forzar=True)


@router.post("/{envio_id}/reintentar")
def reintentar(envio_id: uuid.UUID, db: Session = Depends(get_db), _: Usuario = Depends(requiere_rol("admin", "auditor"))):
    e = db.get(RdaEnvio, envio_id)
    if not e:
        raise HTTPException(404, "RDA no encontrado")
    if e.errores_validacion:
        raise HTTPException(422, {"errores": e.errores_validacion})
    if e.estado in ("enviado", "simulado"):
        raise HTTPException(409, "El RDA ya fue transmitido")
    e.estado, e.intentos = "pendiente", 0
    db.commit()
    return rda.procesar_pendientes(db, forzar=True)


@router.post("/paciente/{paciente_id}")
def rda_de_paciente(paciente_id: uuid.UUID, request: Request, tareas: BackgroundTasks, db: Session = Depends(get_db),
                    usuario: Usuario = Depends(requiere_rol("medico", "admin"))):
    p = db.get(Paciente, paciente_id)
    if not p:
        raise HTTPException(404, "Paciente no encontrado")
    atenciones = db.scalars(select(Atencion).where(Atencion.paciente_id == p.id, Atencion.estado == "firmada")
                            .order_by(Atencion.fecha_inicio)).all()
    tipo, bundle = rda.rda_paciente(p, list(atenciones))
    envio = rda.encolar(db, tipo, p.id, p.id, bundle)
    registrar_evento(db, accion="RDA_PACIENTE", entidad="paciente", entidad_id=p.id, usuario_id=usuario.id,
                     ip=ip_cliente(request))
    db.commit()
    tareas.add_task(procesar_en_segundo_plano)
    return {"id": str(envio.id) if envio else None, "estado": envio.estado if envio else "desactivado",
            "errores_validacion": envio.errores_validacion if envio else None}
