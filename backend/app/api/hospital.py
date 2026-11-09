"""Urgencias (triage) y hospitalización: camas, ingresos, evoluciones, órdenes, kárdex, balance y egreso."""
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CLINICOS, LECTURA_HC, MEDICOS, ip_cliente, requiere_rol
from app.models import Paciente, Usuario
from app.models_ext import (AdministracionMedicamento, BalanceLiquidos, Cama, Evolucion, Hospitalizacion, OrdenMedica,
                            Producto, Triage)
from app.schemas_ext import (AdministracionIn, BalanceIn, CamaIn, CamaOut, EgresoIn, EvolucionIn, EvolucionOut,
                             HospitalizacionDetalle, HospitalizacionOut, IngresoIn, OrdenIn, OrdenOut, TriageIn, TriageOut)
from app.services import hospital as srv
from app.services import seguridad_clinica
from app.services.ia import alertas_clinicas
from app.services.ledger import a_utc, registrar_evento
from app.services.rips import edad_en

router = APIRouter(prefix="/api", tags=["Urgencias y hospitalización"])


# ============================================================================ URGENCIAS
def _triage_out(t: Triage) -> TriageOut:
    out = TriageOut.model_validate(t)
    fin = a_utc(t.inicio_atencion) if t.inicio_atencion else datetime.now(timezone.utc)
    out.minutos_espera = int((fin - a_utc(t.llegada)).total_seconds() // 60)
    out.tiempo_maximo = srv.TIEMPO_MAXIMO_MIN[t.nivel]
    out.vencido = t.estado == "en_espera" and out.minutos_espera > out.tiempo_maximo
    out.razones = srv.sugerir_triage(t.motivo, t.signos_vitales)[1]
    return out


@router.post("/urgencias/triage/sugerir")
def sugerir(datos: TriageIn, _: Usuario = Depends(requiere_rol(*CLINICOS))):
    nivel, razones = srv.sugerir_triage(datos.motivo, datos.signos_vitales)
    return {"nivel": nivel, "descripcion": srv.DESCRIPCION_TRIAGE[nivel], "tiempo_maximo_min": srv.TIEMPO_MAXIMO_MIN[nivel],
            "razones": razones}


@router.post("/urgencias/triage", response_model=TriageOut, status_code=201)
def clasificar(datos: TriageIn, request: Request, db: Session = Depends(get_db),
               usuario: Usuario = Depends(requiere_rol(*CLINICOS))):
    if not db.get(Paciente, datos.paciente_id):
        raise HTTPException(404, "Paciente no encontrado")
    sugerido, _ = srv.sugerir_triage(datos.motivo, datos.signos_vitales)
    t = Triage(paciente_id=datos.paciente_id, motivo=datos.motivo, signos_vitales=datos.signos_vitales,
               nivel=datos.nivel or sugerido, nivel_sugerido=sugerido, observaciones=datos.observaciones,
               sede_id=datos.sede_id, clasificado_por=usuario.id,
               llegada=datos.llegada or datetime.now(timezone.utc))
    db.add(t)
    db.flush()
    registrar_evento(db, accion="TRIAGE", entidad="triage", entidad_id=t.id,
                     datos={"nivel": t.nivel, "sugerido": sugerido}, usuario_id=usuario.id, ip=ip_cliente(request))
    db.commit()
    db.refresh(t)
    return _triage_out(t)


@router.get("/urgencias/cola", response_model=list[TriageOut])
def cola(db: Session = Depends(get_db), _: Usuario = Depends(requiere_rol(*CLINICOS, "admisiones"))):
    """Pacientes en espera y en atención, ordenados por prioridad y tiempo de llegada."""
    filas = db.scalars(select(Triage).where(Triage.estado.in_(("en_espera", "en_atencion")))).all()
    return sorted((_triage_out(t) for t in filas), key=lambda t: (t.estado != "en_espera", t.nivel, t.llegada))


@router.post("/urgencias/triage/{triage_id}/{accion}", response_model=TriageOut)
def avanzar(triage_id: uuid.UUID, accion: str, request: Request, atencion_id: uuid.UUID | None = None,
            db: Session = Depends(get_db), usuario: Usuario = Depends(requiere_rol(*CLINICOS))):
    t = db.get(Triage, triage_id)
    if not t:
        raise HTTPException(404, "Triage no encontrado")
    if accion == "atender" and t.estado == "en_espera":
        t.estado, t.inicio_atencion = "en_atencion", datetime.now(timezone.utc)
    elif accion == "finalizar" and t.estado == "en_atencion":
        t.estado, t.atencion_id = "finalizado", atencion_id
    else:
        raise HTTPException(409, f"No se puede '{accion}' un triage en estado '{t.estado}'")
    registrar_evento(db, accion=f"TRIAGE_{accion.upper()}", entidad="triage", entidad_id=t.id, usuario_id=usuario.id,
                     ip=ip_cliente(request))
    db.commit()
    return _triage_out(t)


# ============================================================================ CAMAS
@router.get("/camas", response_model=list[CamaOut])
def camas(db: Session = Depends(get_db), _: Usuario = Depends(requiere_rol(*CLINICOS, "admisiones", "auditor"))):
    activas = {h.cama_id: h for h in db.scalars(select(Hospitalizacion).where(Hospitalizacion.estado == "activa")).all()}
    salida = []
    for c in db.scalars(select(Cama).order_by(Cama.servicio, Cama.codigo)).all():
        out = CamaOut.model_validate(c)
        if h := activas.get(c.id):
            out.paciente, out.hospitalizacion_id = h.paciente.nombre_completo, h.id
        salida.append(out)
    return salida


@router.post("/camas", response_model=CamaOut, status_code=201)
def crear_cama(datos: CamaIn, db: Session = Depends(get_db), _: Usuario = Depends(requiere_rol("admin"))):
    if db.scalars(select(Cama).where(Cama.codigo == datos.codigo)).first():
        raise HTTPException(409, "Ya existe una cama con ese código")
    c = Cama(**datos.model_dump())
    db.add(c)
    db.commit()
    return c


@router.patch("/camas/{cama_id}", response_model=CamaOut)
def estado_cama(cama_id: uuid.UUID, estado: str, db: Session = Depends(get_db),
                _: Usuario = Depends(requiere_rol("admin", "enfermeria"))):
    c = db.get(Cama, cama_id)
    if not c or estado not in ("disponible", "mantenimiento"):
        raise HTTPException(422, "Cama o estado inválido")
    if c.estado == "ocupada":
        raise HTTPException(409, "La cama está ocupada")
    c.estado = estado
    db.commit()
    return c


# ============================================================================ HOSPITALIZACIÓN
def _hosp(db: Session, hosp_id: uuid.UUID, activa: bool = False) -> Hospitalizacion:
    h = db.get(Hospitalizacion, hosp_id)
    if not h:
        raise HTTPException(404, "Hospitalización no encontrada")
    if activa and h.estado != "activa":
        raise HTTPException(409, "La hospitalización ya tiene egreso; no admite nuevos registros")
    return h


def _detalle(h: Hospitalizacion) -> HospitalizacionDetalle:
    out = HospitalizacionDetalle.model_validate(h)
    desde = datetime.now(timezone.utc) - timedelta(hours=24)
    ultimos = [b for b in h.balances if a_utc(b.fecha) >= desde]
    ing = sum(b.cantidad_ml for b in ultimos if b.tipo == "ingreso")
    egr = sum(b.cantidad_ml for b in ultimos if b.tipo == "egreso")
    out.balance_24h = {"ingresos_ml": ing, "egresos_ml": egr, "balance_ml": ing - egr}
    signos = next((e.signos_vitales for e in reversed(h.evoluciones) if e.signos_vitales), None)
    out.alertas = alertas_clinicas(signos, edad_en(h.paciente.fecha_nacimiento))
    return out


@router.get("/hospitalizaciones", response_model=list[HospitalizacionOut])
def censo(estado: str = "activa", db: Session = Depends(get_db),
          _: Usuario = Depends(requiere_rol(*LECTURA_HC, "facturacion", "admisiones"))):
    return db.scalars(select(Hospitalizacion).where(Hospitalizacion.estado == estado)
                      .order_by(Hospitalizacion.fecha_ingreso.desc()).limit(300)).all()


@router.post("/hospitalizaciones", response_model=HospitalizacionDetalle, status_code=201)
def ingresar(datos: IngresoIn, request: Request, db: Session = Depends(get_db),
             usuario: Usuario = Depends(requiere_rol(*MEDICOS))):
    if not db.get(Paciente, datos.paciente_id):
        raise HTTPException(404, "Paciente no encontrado")
    if db.scalars(select(Hospitalizacion).where(Hospitalizacion.paciente_id == datos.paciente_id,
                                                Hospitalizacion.estado == "activa")).first():
        raise HTTPException(409, "El paciente ya está hospitalizado")
    cama = db.get(Cama, datos.cama_id)
    if not cama or cama.estado != "disponible":
        raise HTTPException(409, "La cama no está disponible")
    h = Hospitalizacion(**datos.model_dump(), medico_id=usuario.id)
    cama.estado = "ocupada"
    db.add(h)
    db.flush()
    registrar_evento(db, accion="HOSPITALIZACION_INGRESO", entidad="hospitalizacion", entidad_id=h.id,
                     datos={"paciente_id": str(h.paciente_id), "cama": cama.codigo}, usuario_id=usuario.id,
                     ip=ip_cliente(request))
    db.commit()
    db.refresh(h)
    return _detalle(h)


@router.get("/hospitalizaciones/{hosp_id}", response_model=HospitalizacionDetalle)
def detalle(hosp_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
            usuario: Usuario = Depends(requiere_rol(*LECTURA_HC))):
    h = _hosp(db, hosp_id)
    registrar_evento(db, accion="CONSULTA_HOSPITALIZACION", entidad="hospitalizacion", entidad_id=h.id,
                     usuario_id=usuario.id, ip=ip_cliente(request))
    db.commit()
    return _detalle(h)


@router.post("/hospitalizaciones/{hosp_id}/evoluciones", response_model=EvolucionOut, status_code=201)
def evolucionar(hosp_id: uuid.UUID, datos: EvolucionIn, request: Request, db: Session = Depends(get_db),
                usuario: Usuario = Depends(requiere_rol(*CLINICOS))):
    h = _hosp(db, hosp_id, activa=True)
    if datos.tipo == "medica" and usuario.rol not in MEDICOS:
        raise HTTPException(403, "Solo el personal médico registra evoluciones médicas")
    e = Evolucion(hospitalizacion_id=h.id, autor_id=usuario.id, tipo=datos.tipo, texto=datos.texto,
                  signos_vitales=datos.signos_vitales,
                  hash_contenido=srv.hash_evolucion(usuario.id, h.id, datos.tipo, datos.texto, datos.signos_vitales))
    db.add(e)
    db.flush()
    registrar_evento(db, accion="EVOLUCION", entidad="hospitalizacion", entidad_id=h.id,
                     datos={"evolucion": str(e.id), "hash": e.hash_contenido}, usuario_id=usuario.id, ip=ip_cliente(request))
    db.commit()
    db.refresh(e)
    return e


@router.post("/hospitalizaciones/{hosp_id}/ordenes", response_model=OrdenOut, status_code=201)
def ordenar(hosp_id: uuid.UUID, datos: OrdenIn, request: Request, db: Session = Depends(get_db),
            usuario: Usuario = Depends(requiere_rol(*MEDICOS))):
    h = _hosp(db, hosp_id, activa=True)
    if datos.tipo == "medicamento":
        nombre = datos.descripcion
        if datos.producto_id:
            prod = db.get(Producto, datos.producto_id)
            if not prod:
                raise HTTPException(404, "Producto no encontrado")
            nombre = f"{prod.nombre} {datos.descripcion}"
        activos = [o.descripcion for o in h.ordenes if o.tipo == "medicamento" and o.estado == "activa"]
        alertas = seguridad_clinica.revisar_prescripcion(h.paciente.alergias, activos + [nombre])
        alertas = [a for a in alertas if nombre in str(a)]
        if any(a["severidad"] in ("alta", "contraindicada") for a in alertas) and not datos.confirmar_alertas:
            raise HTTPException(409, {"alertas": alertas, "mensaje": "Confirme para ordenar a pesar de las alertas"})
    o = OrdenMedica(hospitalizacion_id=h.id, autor_id=usuario.id, **datos.model_dump(exclude={"confirmar_alertas"}))
    db.add(o)
    db.flush()
    registrar_evento(db, accion="ORDEN_MEDICA", entidad="hospitalizacion", entidad_id=h.id,
                     datos={"orden": str(o.id), "tipo": o.tipo, "descripcion": o.descripcion,
                            "confirmo_alertas": datos.confirmar_alertas}, usuario_id=usuario.id, ip=ip_cliente(request))
    db.commit()
    db.refresh(o)
    return o


@router.post("/ordenes-medicas/{orden_id}/suspender", response_model=OrdenOut)
def suspender(orden_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
              usuario: Usuario = Depends(requiere_rol(*MEDICOS))):
    o = db.get(OrdenMedica, orden_id)
    if not o or o.estado != "activa":
        raise HTTPException(409, "La orden no está activa")
    o.estado, o.suspendida_en, o.suspendida_por = "suspendida", datetime.now(timezone.utc), usuario.id
    registrar_evento(db, accion="ORDEN_SUSPENDIDA", entidad="hospitalizacion", entidad_id=o.hospitalizacion_id,
                     datos={"orden": str(o.id)}, usuario_id=usuario.id, ip=ip_cliente(request))
    db.commit()
    return o


@router.post("/ordenes-medicas/{orden_id}/administrar", response_model=OrdenOut)
def administrar(orden_id: uuid.UUID, datos: AdministracionIn, request: Request, db: Session = Depends(get_db),
                usuario: Usuario = Depends(requiere_rol("enfermeria", "medico", "admin"))):
    """Registro en el kárdex de enfermería."""
    o = db.get(OrdenMedica, orden_id)
    if not o or o.tipo != "medicamento" or o.estado != "activa":
        raise HTTPException(409, "Solo se administran órdenes de medicamento activas")
    if datos.estado == "omitido" and not datos.observacion:
        raise HTTPException(422, "Indique el motivo de la omisión")
    db.add(AdministracionMedicamento(orden_id=o.id, enfermero_id=usuario.id, **datos.model_dump()))
    registrar_evento(db, accion="KARDEX", entidad="hospitalizacion", entidad_id=o.hospitalizacion_id,
                     datos={"orden": str(o.id), **datos.model_dump()}, usuario_id=usuario.id, ip=ip_cliente(request))
    db.commit()
    db.refresh(o)
    return o


@router.post("/hospitalizaciones/{hosp_id}/balance", status_code=201)
def balance(hosp_id: uuid.UUID, datos: BalanceIn, db: Session = Depends(get_db),
            usuario: Usuario = Depends(requiere_rol(*CLINICOS))):
    h = _hosp(db, hosp_id, activa=True)
    db.add(BalanceLiquidos(hospitalizacion_id=h.id, registrado_por=usuario.id, **datos.model_dump()))
    db.commit()
    db.refresh(h)
    return _detalle(h).balance_24h


@router.post("/hospitalizaciones/{hosp_id}/trasladar", response_model=HospitalizacionOut)
def trasladar(hosp_id: uuid.UUID, cama_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
              usuario: Usuario = Depends(requiere_rol(*CLINICOS))):
    h = _hosp(db, hosp_id, activa=True)
    nueva = db.get(Cama, cama_id)
    if not nueva or nueva.estado != "disponible":
        raise HTTPException(409, "La cama destino no está disponible")
    if h.cama:
        h.cama.estado = "mantenimiento"  # requiere limpieza antes de reutilizar
    nueva.estado, h.cama_id = "ocupada", nueva.id
    registrar_evento(db, accion="TRASLADO_CAMA", entidad="hospitalizacion", entidad_id=h.id,
                     datos={"cama": nueva.codigo}, usuario_id=usuario.id, ip=ip_cliente(request))
    db.commit()
    db.refresh(h)
    return h


@router.post("/hospitalizaciones/{hosp_id}/egreso", response_model=HospitalizacionOut)
def egresar(hosp_id: uuid.UUID, datos: EgresoIn, request: Request, tareas: BackgroundTasks, db: Session = Depends(get_db),
            usuario: Usuario = Depends(requiere_rol(*MEDICOS))):
    h = _hosp(db, hosp_id, activa=True)
    if datos.condicion_egreso == "02" and not datos.dx_causa_muerte:
        raise HTTPException(422, "Paciente fallecido: registre el diagnóstico de causa de muerte")
    for o in h.ordenes:
        if o.estado == "activa":
            o.estado = "cumplida"
    for campo, valor in datos.model_dump().items():
        setattr(h, campo, valor)
    h.fecha_egreso = datetime.now(timezone.utc)
    h.medico_id = h.medico_id or usuario.id
    h.hash_epicrisis = srv.hash_epicrisis(h)
    h.estado = "egresada"
    if h.cama:
        h.cama.estado = "mantenimiento"
    registrar_evento(db, accion="HOSPITALIZACION_EGRESO", entidad="hospitalizacion", entidad_id=h.id,
                     datos={"hash_epicrisis": h.hash_epicrisis, "condicion": h.condicion_egreso},
                     usuario_id=usuario.id, ip=ip_cliente(request))
    from app.api.rda import generar_y_encolar

    generar_y_encolar(db, "hospitalizacion", h, tareas)  # RDA - Resolución 1888 de 2025
    db.commit()
    db.refresh(h)
    return h


@router.get("/hospitalizaciones/{hosp_id}/epicrisis.pdf")
def epicrisis_pdf(hosp_id: uuid.UUID, db: Session = Depends(get_db), _: Usuario = Depends(requiere_rol(*LECTURA_HC))):
    from app.services.pdf import pdf_epicrisis

    h = _hosp(db, hosp_id)
    if not h.hash_epicrisis:
        raise HTTPException(409, "La epicrisis se genera al dar el egreso")
    return Response(pdf_epicrisis(h, edad_en(h.paciente.fecha_nacimiento)), media_type="application/pdf",
                    headers={"Content-Disposition": 'inline; filename="epicrisis.pdf"'})
