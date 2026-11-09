"""Farmacia e inventarios: productos, lotes, entradas, ajustes, alertas y dispensación FEFO."""
import uuid
from datetime import date, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import FARMACIA, ip_cliente, requiere_rol
from app.models import Atencion, Prescripcion, Usuario
from app.models_ext import Hospitalizacion, Lote, MovimientoInventario, OrdenMedica, Producto
from app.schemas_ext import AjusteIn, DispensarIn, EntradaIn, MovimientoOut, ProductoIn, ProductoOut
from app.services.ledger import registrar_evento

router = APIRouter(prefix="/api/farmacia", tags=["Farmacia e inventario"])
DIAS_POR_VENCER = 90


def _salida(p: Producto) -> ProductoOut:
    out = ProductoOut.model_validate(p)
    out.lotes = [lote for lote in out.lotes if lote.cantidad > 0]
    out.stock = sum(lote.cantidad for lote in p.lotes if lote.vencimiento >= date.today())
    return out


def _dispensado(db: Session, campo, valor) -> int:
    return -(db.scalar(select(func.coalesce(func.sum(MovimientoInventario.cantidad), 0))
                       .where(campo == valor, MovimientoInventario.tipo == "dispensacion")) or 0)


@router.get("/productos", response_model=list[ProductoOut])
def productos(q: str | None = None, db: Session = Depends(get_db),
              _: Usuario = Depends(requiere_rol(*FARMACIA, "medico", "enfermeria"))):
    consulta = select(Producto).where(Producto.activo.is_(True)).order_by(Producto.nombre).limit(300)
    if q:
        consulta = consulta.where(Producto.nombre.ilike(f"%{q}%"))
    return [_salida(p) for p in db.scalars(consulta).all()]


@router.post("/productos", response_model=ProductoOut, status_code=201)
def crear_producto(datos: ProductoIn, db: Session = Depends(get_db), _: Usuario = Depends(requiere_rol(*FARMACIA))):
    p = Producto(**datos.model_dump())
    db.add(p)
    db.commit()
    db.refresh(p)
    return _salida(p)


@router.put("/productos/{producto_id}", response_model=ProductoOut)
def editar_producto(producto_id: uuid.UUID, datos: ProductoIn, db: Session = Depends(get_db),
                    _: Usuario = Depends(requiere_rol(*FARMACIA))):
    p = db.get(Producto, producto_id)
    if not p:
        raise HTTPException(404, "Producto no encontrado")
    for k, v in datos.model_dump().items():
        setattr(p, k, v)
    db.commit()
    return _salida(p)


@router.post("/entradas", response_model=ProductoOut, status_code=201)
def entrada(datos: EntradaIn, request: Request, db: Session = Depends(get_db),
            usuario: Usuario = Depends(requiere_rol(*FARMACIA))):
    p = db.get(Producto, datos.producto_id)
    if not p:
        raise HTTPException(404, "Producto no encontrado")
    if datos.vencimiento <= date.today():
        raise HTTPException(422, "No se reciben productos vencidos")
    lote = db.scalars(select(Lote).where(Lote.producto_id == p.id, Lote.numero == datos.lote)).first()
    if lote and lote.vencimiento != datos.vencimiento:
        raise HTTPException(422, "El lote ya existe con otra fecha de vencimiento")
    if not lote:
        lote = Lote(producto_id=p.id, numero=datos.lote, vencimiento=datos.vencimiento,
                    registro_invima=datos.registro_invima, cantidad=0)
        db.add(lote)
        db.flush()
    lote.cantidad += datos.cantidad
    db.add(MovimientoInventario(producto_id=p.id, lote_id=lote.id, tipo="entrada", cantidad=datos.cantidad,
                                usuario_id=usuario.id, motivo=datos.motivo))
    registrar_evento(db, accion="INVENTARIO_ENTRADA", entidad="producto", entidad_id=p.id,
                     datos=datos.model_dump(mode="json"), usuario_id=usuario.id, ip=ip_cliente(request))
    db.commit()
    db.refresh(p)
    return _salida(p)


@router.post("/ajustes", response_model=ProductoOut)
def ajuste(datos: AjusteIn, request: Request, db: Session = Depends(get_db), usuario: Usuario = Depends(requiere_rol(*FARMACIA))):
    lote = db.get(Lote, datos.lote_id)
    if not lote:
        raise HTTPException(404, "Lote no encontrado")
    if lote.cantidad + datos.cantidad < 0:
        raise HTTPException(422, "El ajuste deja el lote en negativo")
    lote.cantidad += datos.cantidad
    db.add(MovimientoInventario(producto_id=lote.producto_id, lote_id=lote.id, tipo="ajuste", cantidad=datos.cantidad,
                                usuario_id=usuario.id, motivo=datos.motivo))
    registrar_evento(db, accion="INVENTARIO_AJUSTE", entidad="producto", entidad_id=lote.producto_id,
                     datos=datos.model_dump(mode="json"), usuario_id=usuario.id, ip=ip_cliente(request))
    db.commit()
    return _salida(db.get(Producto, lote.producto_id))


@router.get("/alertas")
def alertas(db: Session = Depends(get_db), _: Usuario = Depends(requiere_rol(*FARMACIA))):
    hoy = date.today()
    salida = {"stock_bajo": [], "vencidos": [], "por_vencer": []}
    for p in db.scalars(select(Producto).where(Producto.activo.is_(True))).all():
        stock = sum(lote.cantidad for lote in p.lotes if lote.vencimiento >= hoy)
        if stock <= p.stock_minimo:
            salida["stock_bajo"].append({"producto": p.nombre, "stock": stock, "minimo": p.stock_minimo})
        for lote in p.lotes:
            if lote.cantidad <= 0:
                continue
            item = {"producto": p.nombre, "lote": lote.numero, "vencimiento": lote.vencimiento.isoformat(), "cantidad": lote.cantidad}
            if lote.vencimiento < hoy:
                salida["vencidos"].append(item)
            elif lote.vencimiento <= hoy + timedelta(days=DIAS_POR_VENCER):
                salida["por_vencer"].append(item)
    return salida


@router.get("/pendientes")
def pendientes(db: Session = Depends(get_db), _: Usuario = Depends(requiere_rol(*FARMACIA))):
    """Fórmulas de consulta firmadas aún no entregadas completas y órdenes hospitalarias activas."""
    formulas = []
    for r, a in db.execute(select(Prescripcion, Atencion).join(Atencion).where(Atencion.estado == "firmada")
                           .order_by(Atencion.fecha_inicio.desc()).limit(300)).all():
        entregado = _dispensado(db, MovimientoInventario.prescripcion_id, r.id)
        if entregado < r.cantidad:
            formulas.append({"prescripcion_id": str(r.id), "paciente": a.paciente.nombre_completo,
                             "documento": a.paciente.numero_documento, "medicamento": r.medicamento, "dosis": r.dosis,
                             "cantidad": r.cantidad, "entregado": entregado, "fecha": a.fecha_inicio})
    ordenes = []
    for o, h in db.execute(select(OrdenMedica, Hospitalizacion).join(Hospitalizacion)
                           .where(OrdenMedica.tipo == "medicamento", OrdenMedica.estado == "activa")).all():
        ordenes.append({"orden_id": str(o.id), "paciente": h.paciente.nombre_completo, "cama": h.cama.codigo if h.cama else None,
                        "descripcion": o.descripcion, "dosis": o.dosis, "frecuencia": o.frecuencia,
                        "producto_id": str(o.producto_id) if o.producto_id else None,
                        "entregado": _dispensado(db, MovimientoInventario.orden_id, o.id)})
    return {"formulas": formulas, "ordenes": ordenes}


@router.post("/dispensar", response_model=list[MovimientoOut], status_code=201)
def dispensar(datos: DispensarIn, request: Request, tareas: BackgroundTasks, db: Session = Depends(get_db),
              usuario: Usuario = Depends(requiere_rol(*FARMACIA))):
    """Entrega medicamentos usando primero los lotes que vencen antes (FEFO)."""
    if bool(datos.prescripcion_id) == bool(datos.orden_id):
        raise HTTPException(422, "Indique la fórmula (prescripcion_id) o la orden hospitalaria (orden_id)")
    p = db.get(Producto, datos.producto_id)
    if not p or not p.activo:
        raise HTTPException(404, "Producto no encontrado")
    paciente_id = None
    if datos.prescripcion_id:
        r = db.get(Prescripcion, datos.prescripcion_id)
        if not r or r.atencion.estado != "firmada":
            raise HTTPException(409, "La fórmula no existe o la atención no está firmada")
        pendiente = r.cantidad - _dispensado(db, MovimientoInventario.prescripcion_id, r.id)
        if datos.cantidad > pendiente:
            raise HTTPException(422, f"Solo quedan {pendiente} unidades pendientes por entregar de esta fórmula")
        paciente_id = r.atencion.paciente_id
    else:
        o = db.get(OrdenMedica, datos.orden_id)
        if not o or o.estado != "activa" or o.tipo != "medicamento":
            raise HTTPException(409, "La orden no está activa")
        paciente_id = db.get(Hospitalizacion, o.hospitalizacion_id).paciente_id
    hoy = date.today()
    lotes = [lote for lote in p.lotes if lote.vencimiento >= hoy and lote.cantidad > 0]
    if sum(lote.cantidad for lote in lotes) < datos.cantidad:
        raise HTTPException(409, "Inventario insuficiente (no se entregan lotes vencidos)")
    faltante, movimientos = datos.cantidad, []
    for lote in sorted(lotes, key=lambda x: x.vencimiento):
        toma = min(faltante, lote.cantidad)
        lote.cantidad -= toma
        m = MovimientoInventario(producto_id=p.id, lote_id=lote.id, tipo="dispensacion", cantidad=-toma,
                                 usuario_id=usuario.id, paciente_id=paciente_id, prescripcion_id=datos.prescripcion_id,
                                 orden_id=datos.orden_id, motivo="Dispensación")
        db.add(m)
        movimientos.append(m)
        faltante -= toma
        if faltante == 0:
            break
    db.flush()
    registrar_evento(db, accion="DISPENSACION", entidad="producto", entidad_id=p.id,
                     datos=datos.model_dump(mode="json"), usuario_id=usuario.id, ip=ip_cliente(request))
    _rda_dispensacion(db, movimientos, paciente_id, usuario, datos.prescripcion_id, tareas)
    db.commit()
    return movimientos


def _rda_dispensacion(db: Session, movimientos, paciente_id, usuario, prescripcion_id, tareas) -> None:
    """RDA de dispensación (Res. 1799 de 2026). Nunca bloquea la entrega del medicamento."""
    import logging

    from app.api.rda import procesar_en_segundo_plano
    from app.models import Paciente
    from app.services import rda

    try:
        r = db.get(Prescripcion, prescripcion_id) if prescripcion_id else None
        for m in movimientos:
            db.refresh(m)
        for tipo, recurso in rda.rda_dispensacion(movimientos, db.get(Paciente, paciente_id), usuario, r, r.atencion if r else None):
            with db.begin_nested():
                rda.encolar(db, tipo, recurso["id"], paciente_id, recurso)
        tareas.add_task(procesar_en_segundo_plano)
    except Exception as exc:
        logging.getLogger(__name__).exception("No se pudo generar el RDA de dispensación: %s", exc)


@router.get("/kardex/{producto_id}", response_model=list[MovimientoOut])
def kardex(producto_id: uuid.UUID, db: Session = Depends(get_db), _: Usuario = Depends(requiere_rol(*FARMACIA, "auditor"))):
    return db.scalars(select(MovimientoInventario).where(MovimientoInventario.producto_id == producto_id)
                      .order_by(MovimientoInventario.fecha.desc()).limit(500)).all()
