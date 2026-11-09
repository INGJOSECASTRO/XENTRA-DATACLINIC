"""Portal del paciente: su historia, citas, resultados, documentos, quién consultó su HC y descarga FHIR.

Derechos del titular (Ley 1581 de 2012): conocer, acceder y obtener copia de su información; y saber
quién ha accedido a ella (trazabilidad).
"""
import secrets
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import ip_cliente, requiere_rol
from app.core.security import hash_password
from app.models import Atencion, BloqueLedger, Paciente, Usuario
from app.models_ext import Cita, Hospitalizacion, OrdenServicio
from app.services import fhir
from app.services.ledger import registrar_evento
from app.services.rips import edad_en
from app.services.resumen import resumen

router = APIRouter(tags=["Portal del paciente"])
paciente_actual = requiere_rol("paciente")

ACCIONES_ACCESO = ("CONSULTA_PACIENTE", "CONSULTA_HC", "CONSULTA_ATENCION", "CONSULTA_HOSPITALIZACION", "DESCARGA_PDF",
                   "FHIR_EXPORTACION", "RESUMEN_HC")


def _mi_paciente(db: Session, usuario: Usuario) -> Paciente:
    p = db.get(Paciente, usuario.paciente_id) if usuario.paciente_id else None
    if not p:
        raise HTTPException(403, "La cuenta no está vinculada a un paciente")
    return p


@router.post("/api/pacientes/{paciente_id}/acceso-portal", status_code=201)
def crear_acceso(paciente_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
                 admin: Usuario = Depends(requiere_rol("admisiones", "admin"))):
    """Crea el usuario del portal. Devuelve una clave temporal UNA sola vez (entréguela de forma segura)."""
    p = db.get(Paciente, paciente_id)
    if not p:
        raise HTTPException(404, "Paciente no encontrado")
    if not p.email:
        raise HTTPException(422, "Registre el correo del paciente antes de crear el acceso")
    if not p.autoriza_tratamiento_datos:
        raise HTTPException(422, "El paciente debe autorizar el tratamiento de datos (Ley 1581)")
    if db.scalars(select(Usuario).where(Usuario.paciente_id == p.id)).first() or \
            db.scalars(select(Usuario).where(Usuario.email == p.email.lower())).first():
        raise HTTPException(409, "Ya existe un acceso con ese correo")
    clave = secrets.token_urlsafe(9) + "A1"
    u = Usuario(tipo_documento=p.tipo_documento, numero_documento=p.numero_documento, nombres=p.primer_nombre,
                apellidos=p.primer_apellido, email=p.email.lower(), hashed_password=hash_password(clave), rol="paciente",
                paciente_id=p.id)
    db.add(u)
    db.flush()
    registrar_evento(db, accion="PORTAL_ACCESO_CREADO", entidad="paciente", entidad_id=p.id, usuario_id=admin.id,
                     ip=ip_cliente(request))
    db.commit()
    return {"usuario": u.email, "clave_temporal": clave,
            "mensaje": "Entregue la clave al paciente y pídale cambiarla en su primer ingreso."}


@router.get("/api/portal/resumen")
def mi_resumen(db: Session = Depends(get_db), usuario: Usuario = Depends(paciente_actual)):
    p = _mi_paciente(db, usuario)
    atenciones = db.scalars(select(Atencion).where(Atencion.paciente_id == p.id, Atencion.estado == "firmada")
                            .order_by(Atencion.fecha_inicio)).all()
    hosp = db.scalars(select(Hospitalizacion).where(Hospitalizacion.paciente_id == p.id)).all()
    labs = db.scalars(select(OrdenServicio).where(OrdenServicio.paciente_id == p.id, OrdenServicio.estado == "validada")).all()
    r = resumen(p, list(atenciones), list(hosp), list(labs), edad_en(p.fecha_nacimiento))
    return {"paciente": {"nombre": p.nombre_completo, "documento": f"{p.tipo_documento} {p.numero_documento}",
                         "fecha_nacimiento": p.fecha_nacimiento, "eps": p.cod_eapb}, **r}


@router.get("/api/portal/atenciones")
def mis_atenciones(db: Session = Depends(get_db), usuario: Usuario = Depends(paciente_actual)):
    p = _mi_paciente(db, usuario)
    filas = db.scalars(select(Atencion).where(Atencion.paciente_id == p.id, Atencion.estado == "firmada")
                       .order_by(Atencion.fecha_inicio.desc())).all()
    return [{"id": str(a.id), "fecha": a.fecha_inicio, "tipo": a.tipo, "profesional": a.profesional.nombre_completo,
             "motivo": a.motivo_consulta, "diagnosticos": [f"{d.codigo_cie10} {d.descripcion}" for d in a.diagnosticos],
             "plan": a.plan, "tiene_formula": bool(a.prescripciones)} for a in filas]


@router.get("/api/portal/atenciones/{atencion_id}/pdf")
def mi_pdf(atencion_id: uuid.UUID, documento: str = "historia", db: Session = Depends(get_db),
           usuario: Usuario = Depends(paciente_actual)):
    from app.services import pdf as generador

    p = _mi_paciente(db, usuario)
    a = db.get(Atencion, atencion_id)
    if not a or a.paciente_id != p.id or a.estado != "firmada":
        raise HTTPException(404, "Documento no encontrado")
    contenido = generador.pdf_formula(a, edad_en(p.fecha_nacimiento)) if documento == "formula" and a.prescripciones \
        else generador.pdf_atencion(a, edad_en(p.fecha_nacimiento))
    return Response(contenido, media_type="application/pdf", headers={"Content-Disposition": 'inline; filename="documento.pdf"'})


@router.get("/api/portal/citas")
def mis_citas(db: Session = Depends(get_db), usuario: Usuario = Depends(paciente_actual)):
    p = _mi_paciente(db, usuario)
    filas = db.scalars(select(Cita).where(Cita.paciente_id == p.id).order_by(Cita.inicio.desc()).limit(50)).all()
    return [{"id": str(c.id), "inicio": c.inicio, "profesional": c.profesional.nombre_completo, "estado": c.estado,
             "modalidad": c.modalidad, "sala_virtual": c.sala_virtual if c.estado in ("programada", "confirmada", "en_sala") else None}
            for c in filas]


@router.get("/api/portal/resultados")
def mis_resultados(db: Session = Depends(get_db), usuario: Usuario = Depends(paciente_actual)):
    p = _mi_paciente(db, usuario)
    filas = db.scalars(select(OrdenServicio).where(OrdenServicio.paciente_id == p.id, OrdenServicio.estado == "validada")
                       .order_by(OrdenServicio.fecha_resultado.desc())).all()
    return [{"id": str(o.id), "fecha": o.fecha_resultado, "examen": o.descripcion, "resultados": o.resultados,
             "informe": o.informe, "hash": o.hash_resultado} for o in filas]


@router.get("/api/portal/accesos")
def quien_vio_mi_historia(db: Session = Depends(get_db), usuario: Usuario = Depends(paciente_actual)):
    """Transparencia: quién consultó la historia clínica del paciente, cuándo y con qué rol."""
    p = _mi_paciente(db, usuario)
    atenciones = [str(x) for x in db.scalars(select(Atencion.id).where(Atencion.paciente_id == p.id)).all()]
    hosp = [str(x) for x in db.scalars(select(Hospitalizacion.id).where(Hospitalizacion.paciente_id == p.id)).all()]
    filas = db.scalars(select(BloqueLedger).where(BloqueLedger.accion.in_(ACCIONES_ACCESO),
                                                  BloqueLedger.entidad_id.in_([str(p.id), *atenciones, *hosp]))
                       .order_by(BloqueLedger.id.desc()).limit(200)).all()
    personas = {}
    salida = []
    for b in filas:
        if b.usuario_id and b.usuario_id not in personas:
            u = db.get(Usuario, uuid.UUID(b.usuario_id))
            personas[b.usuario_id] = (u.nombre_completo, u.rol) if u else ("Desconocido", "-")
        nombre, rol = personas.get(b.usuario_id, ("Sistema", "-"))
        salida.append({"fecha": b.marca_tiempo, "accion": b.accion, "persona": nombre, "rol": rol})
    return salida


@router.get("/api/portal/exportar")
def exportar(request: Request, db: Session = Depends(get_db), usuario: Usuario = Depends(paciente_actual)):
    """Copia completa de la información clínica en formato estándar FHIR (portabilidad)."""
    from app.api.fhir import datos_paciente

    p = _mi_paciente(db, usuario)
    registrar_evento(db, accion="PORTAL_EXPORTACION", entidad="paciente", entidad_id=p.id, usuario_id=usuario.id,
                     ip=ip_cliente(request))
    db.commit()
    contenido = fhir.everything(p, *datos_paciente(db, p.id))
    contenido["meta"] = {"lastUpdated": datetime.now(timezone.utc).isoformat()}
    return JSONResponse(contenido, media_type="application/fhir+json",
                        headers={"Content-Disposition": 'attachment; filename="mi_historia_clinica.json"'})
