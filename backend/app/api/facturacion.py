"""Facturas: borrador -> pre-auditoría -> emisión (DIAN) -> validación RIPS (MUV/CUV)."""
import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import FACTURACION, ip_cliente, requiere_rol
from app.models import Atencion, Usuario
from app.models_ext import Factura, Hospitalizacion
from app.services import facturacion as srv
from app.services.integraciones import ErrorIntegracion, dian, muv
from app.services.ledger import registrar_evento

router = APIRouter(prefix="/api/facturas", tags=["Facturación electrónica"])


class FacturaIn(BaseModel):
    tipo_pagador: str = Field("eps", pattern="^(eps|particular|soat|arl|otro)$")
    cod_eapb: str | None = None
    nit_pagador: str | None = None
    nombre_pagador: str = Field(min_length=2)
    modalidad_pago: str = Field("evento", pattern="^(evento|capitacion|pgp|otro)$")
    num_contrato: str | None = None
    atencion_ids: list[uuid.UUID] = []
    hospitalizacion_ids: list[uuid.UUID] = []


class ItemOut(BaseModel):
    tipo: str
    codigo: str
    descripcion: str
    cantidad: int
    valor_unitario: Decimal
    valor_total: Decimal
    atencion_id: uuid.UUID | None
    hospitalizacion_id: uuid.UUID | None
    model_config = {"from_attributes": True}


class FacturaOut(BaseModel):
    id: uuid.UUID
    numero: str | None
    fecha_emision: datetime | None
    tipo_pagador: str
    cod_eapb: str | None
    nit_pagador: str | None
    nombre_pagador: str
    modalidad_pago: str
    num_contrato: str | None
    subtotal: Decimal
    pagos_moderadores: Decimal
    total: Decimal
    estado: str
    cufe: str | None
    cuv: str | None
    respuesta_muv: dict | None
    hallazgos_auditoria: list | None
    creado_en: datetime
    items: list[ItemOut]
    model_config = {"from_attributes": True}


class AnularIn(BaseModel):
    motivo: str = Field(min_length=5)


def _obtener(db: Session, factura_id: uuid.UUID) -> Factura:
    f = db.get(Factura, factura_id)
    if not f:
        raise HTTPException(404, "Factura no encontrada")
    return f


@router.get("", response_model=list[FacturaOut])
def listar(estado: str | None = None, db: Session = Depends(get_db), _: Usuario = Depends(requiere_rol(*FACTURACION, "auditor"))):
    q = select(Factura).order_by(Factura.creado_en.desc()).limit(200)
    if estado:
        q = q.where(Factura.estado == estado)
    return db.scalars(q).all()


@router.get("/pendientes")
def pendientes(db: Session = Depends(get_db), _: Usuario = Depends(requiere_rol(*FACTURACION))):
    """Atenciones firmadas y hospitalizaciones egresadas que aún no están facturadas."""
    usados = srv.ya_facturadas(db, [x for x in db.scalars(select(Atencion.id)).all()],
                               [x for x in db.scalars(select(Hospitalizacion.id)).all()])
    at = db.scalars(select(Atencion).where(Atencion.estado == "firmada").order_by(Atencion.fecha_inicio.desc()).limit(300)).all()
    ho = db.scalars(select(Hospitalizacion).where(Hospitalizacion.estado == "egresada").limit(300)).all()
    return {
        "atenciones": [{"id": str(a.id), "fecha": a.fecha_inicio, "paciente": a.paciente.nombre_completo,
                        "documento": a.paciente.numero_documento, "eps": a.paciente.cod_eapb, "consecutivo": a.consecutivo,
                        "motivo": a.motivo_consulta, "valor": float(a.valor_servicio),
                        "dx": a.diagnosticos[0].codigo_cie10 if a.diagnosticos else None}
                       for a in at if a.id not in usados],
        "hospitalizaciones": [{"id": str(h.id), "ingreso": h.fecha_ingreso, "egreso": h.fecha_egreso,
                               "paciente": h.paciente.nombre_completo, "documento": h.paciente.numero_documento,
                               "eps": h.paciente.cod_eapb, "dx": h.dx_egreso}
                              for h in ho if h.id not in usados],
    }


@router.post("", response_model=FacturaOut, status_code=201)
def crear(datos: FacturaIn, request: Request, db: Session = Depends(get_db), usuario: Usuario = Depends(requiere_rol(*FACTURACION))):
    if not datos.atencion_ids and not datos.hospitalizacion_ids:
        raise HTTPException(422, "Seleccione al menos una atención u hospitalización")
    atenciones = db.scalars(select(Atencion).where(Atencion.id.in_(datos.atencion_ids))).all() if datos.atencion_ids else []
    hosp = db.scalars(select(Hospitalizacion).where(Hospitalizacion.id.in_(datos.hospitalizacion_ids))).all() \
        if datos.hospitalizacion_ids else []
    if len(atenciones) != len(set(datos.atencion_ids)) or len(hosp) != len(set(datos.hospitalizacion_ids)):
        raise HTTPException(404, "Uno o más servicios no existen")
    try:
        f = srv.crear_factura(db, datos.model_dump(exclude={"atencion_ids", "hospitalizacion_ids"}), list(atenciones),
                              list(hosp), usuario.id)
    except srv.ErrorFactura as exc:
        raise HTTPException(422, str(exc))
    f.hallazgos_auditoria = srv.preauditar(db, f)
    registrar_evento(db, accion="FACTURA_CREADA", entidad="factura", entidad_id=f.id,
                     datos={"total": str(f.total), "items": len(f.items)}, usuario_id=usuario.id, ip=ip_cliente(request))
    db.commit()
    db.refresh(f)
    return f


@router.get("/{factura_id}", response_model=FacturaOut)
def detalle(factura_id: uuid.UUID, db: Session = Depends(get_db), _: Usuario = Depends(requiere_rol(*FACTURACION, "auditor"))):
    return _obtener(db, factura_id)


@router.post("/{factura_id}/auditar", response_model=FacturaOut)
def auditar(factura_id: uuid.UUID, db: Session = Depends(get_db), _: Usuario = Depends(requiere_rol(*FACTURACION, "auditor"))):
    f = _obtener(db, factura_id)
    f.hallazgos_auditoria = srv.preauditar(db, f)
    db.commit()
    return f


@router.post("/{factura_id}/emitir", response_model=FacturaOut)
def emitir(factura_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
           usuario: Usuario = Depends(requiere_rol(*FACTURACION))):
    f = _obtener(db, factura_id)
    if f.estado != "borrador":
        raise HTTPException(409, "Solo se emiten facturas en borrador")
    hallazgos = srv.preauditar(db, f)
    f.hallazgos_auditoria = hallazgos
    if any(x["nivel"] == "error" for x in hallazgos):
        db.commit()
        raise HTTPException(422, {"errores": [x["mensaje"] for x in hallazgos if x["nivel"] == "error"]})
    f.consecutivo = srv.siguiente_consecutivo(db, f.prefijo)
    f.fecha_emision = datetime.now(timezone.utc)
    try:
        resp = dian().emitir(f)
    except ErrorIntegracion as exc:
        db.rollback()
        raise HTTPException(502, str(exc))
    rips, _ = srv.construir_rips(db, f, f.numero)
    f.cufe, f.respuesta_dian, f.rips, f.estado = resp["cufe"], resp, rips, "emitida"
    registrar_evento(db, accion="FACTURA_EMITIDA", entidad="factura", entidad_id=f.id,
                     datos={"numero": f.numero, "cufe": f.cufe, "rips": rips}, usuario_id=usuario.id, ip=ip_cliente(request))
    db.commit()
    return f


@router.post("/{factura_id}/enviar-muv", response_model=FacturaOut)
def enviar_muv(factura_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
               usuario: Usuario = Depends(requiere_rol(*FACTURACION))):
    f = _obtener(db, factura_id)
    if f.estado not in ("emitida", "rechazada"):
        raise HTTPException(409, "Primero emita la factura ante la DIAN")
    try:
        resp = muv().validar(f.rips, (f.respuesta_dian or {}).get("xml_base64"))
    except ErrorIntegracion as exc:
        raise HTTPException(502, str(exc))
    f.respuesta_muv = resp
    if resp.get("ResultState") and resp.get("CodigoUnicoValidacion"):
        f.cuv, f.estado = resp["CodigoUnicoValidacion"], "validada"
    else:
        f.estado = "rechazada"
    registrar_evento(db, accion="FACTURA_MUV_" + f.estado.upper(), entidad="factura", entidad_id=f.id,
                     datos={"cuv": f.cuv}, usuario_id=usuario.id, ip=ip_cliente(request))
    db.commit()
    return f


@router.post("/{factura_id}/anular", response_model=FacturaOut)
def anular(factura_id: uuid.UUID, datos: AnularIn, request: Request, db: Session = Depends(get_db),
           usuario: Usuario = Depends(requiere_rol(*FACTURACION))):
    """Anula un borrador. Una factura ya emitida se corrige con NOTA CRÉDITO ante la DIAN (tipoNota NC en RIPS)."""
    f = _obtener(db, factura_id)
    if f.estado == "anulada":
        raise HTTPException(409, "La factura ya está anulada")
    if f.estado != "borrador":
        raise HTTPException(409, "Una factura emitida no se anula: genere una nota crédito con su proveedor DIAN")
    f.estado = "anulada"
    registrar_evento(db, accion="FACTURA_ANULADA", entidad="factura", entidad_id=f.id, datos={"motivo": datos.motivo},
                     usuario_id=usuario.id, ip=ip_cliente(request))
    db.commit()
    return f


@router.get("/{factura_id}/rips")
def descargar_rips(factura_id: uuid.UUID, db: Session = Depends(get_db), _: Usuario = Depends(requiere_rol(*FACTURACION))):
    f = _obtener(db, factura_id)
    if not f.rips:
        raise HTTPException(409, "La factura aún no se ha emitido")
    return Response(json.dumps(f.rips, ensure_ascii=False, indent=2), media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="RIPS_{f.numero}.json"'})
