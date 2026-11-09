"""Folios de historia clínica: crear (borrador), editar, firmar, notas aclaratorias y verificación."""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CLINICOS, FACTURACION, LECTURA_HC, ip_cliente, requiere_rol
from app.models import CIE10, Atencion, BloqueLedger, Diagnostico, NotaAclaratoria, Paciente, Prescripcion, Procedimiento, Usuario
from app.schemas import AtencionCrear, AtencionGuardar, AtencionOut, AtencionResumen, NotaIn, NotaOut
from app.services import historia
from app.services.cie10 import pertinente
from app.services.ia import alertas_clinicas
from app.services.ledger import json_canonico, registrar_evento, sha256
from app.services.rips import edad_en

router = APIRouter(prefix="/api/atenciones", tags=["Historia clínica"])


def obtener(db: Session, atencion_id: uuid.UUID) -> Atencion:
    a = db.get(Atencion, atencion_id)
    if not a:
        raise HTTPException(404, "Atención no encontrada")
    return a


def salida(a: Atencion) -> AtencionOut:
    out = AtencionOut.model_validate(a)
    out.alertas = alertas_clinicas(a.signos_vitales, edad_en(a.paciente.fecha_nacimiento))
    return out


def _aplicar(db: Session, a: Atencion, datos: AtencionGuardar, paciente: Paciente) -> None:
    edad = edad_en(paciente.fecha_nacimiento)
    for campo in ("tipo", "motivo_consulta", "enfermedad_actual", "antecedentes", "revision_sistemas", "examen_fisico",
                  "analisis", "plan", "cod_consulta_cups", "finalidad_tecnologia", "causa_motivo_atencion",
                  "cod_servicio", "num_autorizacion", "valor_servicio", "valor_pago_moderador"):
        setattr(a, campo, getattr(datos, campo))
    a.signos_vitales = datos.signos_vitales.model_dump(exclude_none=True) if datos.signos_vitales else None

    hay_catalogo = (db.scalar(select(func.count()).select_from(CIE10)) or 0) > 0
    codigos = [d.codigo_cie10 for d in datos.diagnosticos]
    if len(codigos) != len(set(codigos)):
        raise HTTPException(422, "Hay diagnósticos repetidos")
    nuevos = []
    for orden, d in enumerate(datos.diagnosticos):
        fila = db.get(CIE10, d.codigo_cie10)
        if hay_catalogo and not fila:
            raise HTTPException(422, f"El código {d.codigo_cie10} no existe en el catálogo CIE-10")
        if fila and not pertinente(fila, paciente.sexo, edad):
            raise HTTPException(422, f"El código {d.codigo_cie10} no es pertinente para el sexo/edad del paciente")
        nuevos.append(Diagnostico(orden=orden, codigo_cie10=d.codigo_cie10,
                                  descripcion=fila.descripcion if fila else d.descripcion,
                                  tipo_diagnostico=d.tipo_diagnostico, sugerido_por_ia=d.sugerido_por_ia))
    a.diagnosticos = nuevos
    a.procedimientos = [Procedimiento(**p.model_dump()) for p in datos.procedimientos]
    a.prescripciones = [Prescripcion(**r.model_dump()) for r in datos.prescripciones]


@router.get("", response_model=list[AtencionResumen])
def listar(
    estado: str | None = None,
    desde: datetime | None = None,
    hasta: datetime | None = None,
    limite: int = Query(100, le=500),
    db: Session = Depends(get_db),
    _: Usuario = Depends(requiere_rol(*set(LECTURA_HC) | set(FACTURACION))),
):
    q = select(Atencion).order_by(Atencion.fecha_inicio.desc()).limit(limite)
    if estado:
        q = q.where(Atencion.estado == estado)
    if desde:
        q = q.where(Atencion.fecha_inicio >= desde)
    if hasta:
        q = q.where(Atencion.fecha_inicio <= hasta)
    return db.scalars(q).all()


@router.post("", response_model=AtencionOut, status_code=201)
def crear(datos: AtencionCrear, request: Request, db: Session = Depends(get_db),
          usuario: Usuario = Depends(requiere_rol(*CLINICOS))):
    paciente = db.get(Paciente, datos.paciente_id)
    if not paciente:
        raise HTTPException(404, "Paciente no encontrado")
    ultimo = db.scalar(select(func.max(Atencion.consecutivo)).where(Atencion.paciente_id == paciente.id)) or 0
    a = Atencion(paciente_id=paciente.id, profesional_id=usuario.id, consecutivo=ultimo + 1, paciente=paciente)
    _aplicar(db, a, datos, paciente)
    db.add(a)
    db.flush()
    registrar_evento(db, accion="ATENCION_CREADA", entidad="atencion", entidad_id=a.id,
                     datos={"paciente_id": str(paciente.id)}, usuario_id=usuario.id, ip=ip_cliente(request))
    db.commit()
    db.refresh(a)
    return salida(a)


@router.get("/{atencion_id}", response_model=AtencionOut)
def detalle(atencion_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
            usuario: Usuario = Depends(requiere_rol(*LECTURA_HC))):
    a = obtener(db, atencion_id)
    registrar_evento(db, accion="CONSULTA_ATENCION", entidad="atencion", entidad_id=a.id,
                     usuario_id=usuario.id, ip=ip_cliente(request))
    db.commit()
    return salida(a)


@router.put("/{atencion_id}", response_model=AtencionOut)
def actualizar(atencion_id: uuid.UUID, datos: AtencionGuardar, request: Request, db: Session = Depends(get_db),
               usuario: Usuario = Depends(requiere_rol(*CLINICOS))):
    a = obtener(db, atencion_id)
    if a.estado == "firmada":
        raise HTTPException(409, "La atención está firmada y es inalterable. Use una nota aclaratoria.")
    if a.profesional_id != usuario.id:
        raise HTTPException(403, "Solo el profesional que abrió la atención puede editarla")
    _aplicar(db, a, datos, a.paciente)
    registrar_evento(db, accion="ATENCION_EDITADA", entidad="atencion", entidad_id=a.id,
                     usuario_id=usuario.id, ip=ip_cliente(request))
    db.commit()
    db.refresh(a)
    return salida(a)


@router.delete("/{atencion_id}", status_code=204)
def eliminar_borrador(atencion_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
                      usuario: Usuario = Depends(requiere_rol(*CLINICOS))):
    a = obtener(db, atencion_id)
    if a.estado == "firmada":
        raise HTTPException(409, "Una atención firmada no se puede eliminar")
    if a.profesional_id != usuario.id:
        raise HTTPException(403, "Solo el autor puede eliminar el borrador")
    db.delete(a)
    registrar_evento(db, accion="BORRADOR_ELIMINADO", entidad="atencion", entidad_id=atencion_id,
                     usuario_id=usuario.id, ip=ip_cliente(request))
    db.commit()


@router.post("/{atencion_id}/firmar", response_model=AtencionOut)
def firmar(atencion_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
           usuario: Usuario = Depends(requiere_rol(*CLINICOS))):
    a = obtener(db, atencion_id)
    if a.estado == "firmada":
        raise HTTPException(409, "La atención ya fue firmada")
    if a.profesional_id != usuario.id:
        raise HTTPException(403, "Solo el profesional tratante puede firmar")
    if not a.diagnosticos:
        raise HTTPException(422, "Debe registrar al menos el diagnóstico principal antes de firmar")
    # 1) Sellar el contenido en el ledger  2) marcar la atención como firmada en un solo UPDATE
    # (después de firmada, PostgreSQL ya no permite modificar la fila).
    bloque = registrar_evento(db, accion="ATENCION_FIRMADA", entidad="atencion", entidad_id=a.id,
                              datos=historia.contenido_clinico(a), usuario_id=usuario.id, ip=ip_cliente(request))
    historia.marcar_firmada(a)
    a.bloque_ledger_id = bloque.id
    db.commit()
    return salida(a)


@router.post("/{atencion_id}/notas", response_model=NotaOut, status_code=201)
def nota_aclaratoria(atencion_id: uuid.UUID, datos: NotaIn, request: Request, db: Session = Depends(get_db),
                     usuario: Usuario = Depends(requiere_rol(*CLINICOS))):
    a = obtener(db, atencion_id)
    if a.estado != "firmada":
        raise HTTPException(409, "Las notas aclaratorias aplican a atenciones firmadas; edite el borrador")
    contenido = {"atencion_id": str(a.id), "autor_id": str(usuario.id), "texto": datos.texto}
    nota = NotaAclaratoria(atencion_id=a.id, autor_id=usuario.id, texto=datos.texto,
                           hash_contenido=sha256(json_canonico(contenido)))
    db.add(nota)
    db.flush()
    registrar_evento(db, accion="NOTA_ACLARATORIA", entidad="atencion", entidad_id=a.id, datos=contenido,
                     usuario_id=usuario.id, ip=ip_cliente(request))
    db.commit()
    db.refresh(nota)
    return nota


@router.get("/{atencion_id}/verificar")
def verificar(atencion_id: uuid.UUID, db: Session = Depends(get_db),
              _: Usuario = Depends(requiere_rol(*LECTURA_HC))):
    """Comprueba que el folio firmado no haya sido alterado (hash actual vs. hash sellado en el ledger)."""
    a = obtener(db, atencion_id)
    if a.estado != "firmada":
        return {"integra": None, "detalle": "La atención aún no está firmada"}
    actual = historia.calcular_hash(a)
    bloque = db.get(BloqueLedger, a.bloque_ledger_id) if a.bloque_ledger_id else None
    integra = actual == a.hash_contenido and bloque is not None and bloque.hash_datos == actual
    return {
        "integra": integra,
        "hash_actual": actual,
        "hash_firmado": a.hash_contenido,
        "hash_en_ledger": bloque.hash_datos if bloque else None,
        "bloque": bloque.id if bloque else None,
        "detalle": "El folio coincide con el sellado en el ledger" if integra
        else "ALERTA: el contenido del folio no coincide con el sellado al firmar",
    }
