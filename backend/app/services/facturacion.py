"""Facturación en salud: armado de la factura, pre-auditoría (reduce glosas), RIPS, DIAN y MUV."""
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Atencion
from app.models_ext import Factura, FacturaItem, Hospitalizacion, MovimientoInventario
from app.services import catalogos
from app.services.ledger import a_utc
from app.services.rips import generar_rips


class ErrorFactura(Exception):
    pass


def _dispensaciones(db: Session, *, prescripciones=(), ordenes=()) -> list[MovimientoInventario]:
    filtros = []
    if prescripciones:
        filtros.append(MovimientoInventario.prescripcion_id.in_(prescripciones))
    if ordenes:
        filtros.append(MovimientoInventario.orden_id.in_(ordenes))
    if not filtros:
        return []
    from sqlalchemy import or_

    return list(db.scalars(select(MovimientoInventario).where(MovimientoInventario.tipo == "dispensacion", or_(*filtros))).all())


def items_y_medicamentos(db: Session, atenciones: list[Atencion], hospitalizaciones: list[Hospitalizacion]):
    """Devuelve (items de factura, medicamentos para RIPS)."""
    items: list[FacturaItem] = []
    meds = []
    for a in atenciones:
        cat = catalogos.obtener(db, "cups", a.cod_consulta_cups)
        items.append(FacturaItem(atencion_id=a.id, tipo="consulta", codigo=a.cod_consulta_cups,
                                 descripcion=cat.descripcion if cat else "CONSULTA", cantidad=1,
                                 valor_unitario=a.valor_servicio, valor_total=a.valor_servicio))
        for p in a.procedimientos:
            items.append(FacturaItem(atencion_id=a.id, tipo="procedimiento", codigo=p.cod_cups, descripcion=p.descripcion,
                                     cantidad=1, valor_unitario=p.valor, valor_total=p.valor))
        duracion = {r.id: r.duracion_dias for r in a.prescripciones}
        dx = a.diagnosticos[0].codigo_cie10 if a.diagnosticos else None
        for m in _dispensaciones(db, prescripciones=list(duracion)):
            meds.append(SimpleNamespace(producto=m.producto, paciente=a.paciente, usuario=a.profesional, fecha=m.fecha,
                                        cantidad=m.cantidad, dx_principal=dx, dias_tratamiento=duracion.get(m.prescripcion_id, 1)))
            items.append(_item_medicamento(m, atencion_id=a.id))
    for h in hospitalizaciones:
        fin = a_utc(h.fecha_egreso) if h.fecha_egreso else datetime.now(timezone.utc)
        dias = max(1, (fin - a_utc(h.fecha_ingreso)).days)
        items.append(FacturaItem(hospitalizacion_id=h.id, tipo="estancia", codigo="ESTANCIA",
                                 descripcion=f"Estancia hospitalaria ({h.cama.servicio if h.cama else 'general'})",
                                 cantidad=dias, valor_unitario=h.valor_estancia_dia, valor_total=h.valor_estancia_dia * dias))
        for m in _dispensaciones(db, ordenes=[o.id for o in h.ordenes]):
            meds.append(SimpleNamespace(producto=m.producto, paciente=h.paciente, usuario=h.medico, fecha=m.fecha,
                                        cantidad=m.cantidad, dx_principal=h.dx_ingreso, dias_tratamiento=1))
            items.append(_item_medicamento(m, hospitalizacion_id=h.id))
    return items, meds


def _item_medicamento(m: MovimientoInventario, **ref) -> FacturaItem:
    cantidad = abs(m.cantidad)
    return FacturaItem(tipo="medicamento", codigo=m.producto.cum or "SIN-CUM", descripcion=m.producto.nombre,
                       cantidad=cantidad, valor_unitario=m.producto.precio_unitario,
                       valor_total=m.producto.precio_unitario * cantidad, **ref)


def atenciones_de(f: Factura, db: Session) -> list[Atencion]:
    ids = {i.atencion_id for i in f.items if i.atencion_id}
    return list(db.scalars(select(Atencion).where(Atencion.id.in_(ids))).all()) if ids else []


def hospitalizaciones_de(f: Factura, db: Session) -> list[Hospitalizacion]:
    ids = {i.hospitalizacion_id for i in f.items if i.hospitalizacion_id}
    return list(db.scalars(select(Hospitalizacion).where(Hospitalizacion.id.in_(ids))).all()) if ids else []


def ya_facturadas(db: Session, atencion_ids: list, hosp_ids: list) -> set:
    q = select(FacturaItem.atencion_id, FacturaItem.hospitalizacion_id).join(Factura).where(Factura.estado != "anulada")
    filas = db.execute(q).all()
    usados = {x for fila in filas for x in fila if x}
    return usados & (set(atencion_ids) | set(hosp_ids))


def crear_factura(db: Session, datos: dict, atenciones: list[Atencion], hosp: list[Hospitalizacion], usuario_id) -> Factura:
    errores = [f"La atención {a.consecutivo} de {a.paciente.numero_documento} no está firmada"
               for a in atenciones if a.estado != "firmada"]
    errores += [f"La hospitalización de {h.paciente.numero_documento} no tiene egreso" for h in hosp if h.estado != "egresada"]
    if repetidas := ya_facturadas(db, [a.id for a in atenciones], [h.id for h in hosp]):
        errores.append(f"{len(repetidas)} servicio(s) ya están en otra factura vigente")
    if errores:
        raise ErrorFactura(" · ".join(errores))
    items, _ = items_y_medicamentos(db, atenciones, hosp)
    f = Factura(**datos, prefijo=settings.FACTURA_PREFIJO, creado_por=usuario_id, items=items)
    recalcular(f, atenciones)
    db.add(f)
    db.flush()
    return f


def recalcular(f: Factura, atenciones: list[Atencion]) -> None:
    f.subtotal = sum((Decimal(i.valor_total or 0) for i in f.items), Decimal(0))
    f.pagos_moderadores = sum((Decimal(a.valor_pago_moderador or 0) for a in atenciones), Decimal(0))
    f.total = f.subtotal - f.pagos_moderadores


def construir_rips(db: Session, f: Factura, numero: str):
    atenciones, hosp = atenciones_de(f, db), hospitalizaciones_de(f, db)
    _, meds = items_y_medicamentos(db, atenciones, hosp)
    return generar_rips(atenciones, numero, hospitalizaciones=hosp, medicamentos=meds)


def preauditar(db: Session, f: Factura) -> list[dict]:
    """Revisión automática antes de radicar, con las causas de glosa más frecuentes."""
    hallazgos: list[dict] = []

    def h(nivel: str, mensaje: str):
        hallazgos.append({"nivel": nivel, "mensaje": mensaje})

    atenciones = atenciones_de(f, db)
    _, errores = construir_rips(db, f, f.numero or "BORRADOR")
    for e in errores:
        h("error", f"RIPS: {e}")
    for i in f.items:
        if not i.valor_total or i.valor_total <= 0:
            h("error", f"Ítem sin valor: {i.codigo} {i.descripcion}")
        if i.tipo in ("consulta", "procedimiento"):
            cat = catalogos.obtener(db, "cups", i.codigo)
            if catalogos.existe_o_sin_catalogo(db, "cups", i.codigo) is False:
                h("error", f"Código CUPS {i.codigo} no existe en el catálogo")
            elif cat and cat.datos and cat.datos.get("valor") and Decimal(str(cat.datos["valor"])) != i.valor_unitario:
                h("advertencia", f"{i.codigo}: valor {i.valor_unitario} difiere de la tarifa pactada {cat.datos['valor']}")
    for a in atenciones:
        p = a.paciente
        if f.tipo_pagador == "eps" and f.cod_eapb and p.cod_eapb and p.cod_eapb != f.cod_eapb:
            h("error", f"El paciente {p.numero_documento} pertenece a {p.cod_eapb}, no a {f.cod_eapb}")
        if f.tipo_pagador == "eps" and a.grupo_servicios != "05" and not a.num_autorizacion:
            h("advertencia", f"Atención {a.consecutivo} de {p.numero_documento} sin número de autorización (verifique si el contrato lo exige)")
        if a.diagnosticos:
            d = a.diagnosticos[0]
            if d.codigo_cie10.startswith("R") and d.tipo_diagnostico in ("02", "03"):
                h("advertencia", f"Dx principal {d.codigo_cie10} es un síntoma pero está marcado como confirmado")
            if d.codigo_cie10.startswith("Z") and a.finalidad_tecnologia in ("15", "16"):
                h("advertencia", f"Dx {d.codigo_cie10} (capítulo Z) con finalidad diagnóstica/terapéutica: revisar coherencia")
    claves = Counter((a.paciente_id, a.cod_consulta_cups, a_utc(a.fecha_inicio).date()) for a in atenciones)
    for (pid, cups, dia), n in claves.items():
        if n > 1:
            h("advertencia", f"Posible duplicidad: {n} consultas {cups} del mismo paciente el {dia}")
    if not hallazgos:
        h("ok", "Sin hallazgos. La cuenta está lista para emitir.")
    return hallazgos


def siguiente_consecutivo(db: Session, prefijo: str) -> int:
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(434343)"))
    return (db.scalar(select(func.max(Factura.consecutivo)).where(Factura.prefijo == prefijo)) or 0) + 1
