"""Continuidad de negocio y soporte: estado del sistema, avisos, mesa de ayuda con ANS y modo contingencia."""
import os
import shutil
import time
import uuid
from datetime import date, datetime, time as hora, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import ADMIN_GESTION, AUDITORIA_SEGURIDAD, PERSONAL, es_admin, ip_cliente, requiere_rol, usuario_actual
from app.models import Atencion, BloqueLedger, Usuario
from app.models_ext import AnclajeLedger, AvisoSistema, Cita, Hospitalizacion, RdaEnvio, Ticket
from app.services.ledger import a_utc, registrar_evento

router = APIRouter(prefix="/api/sistema", tags=["Continuidad y soporte"])
TZ = ZoneInfo(settings.ZONA_HORARIA)
INICIO = time.time()
VERSION = "0.3.0"
ANS_HORAS = {"critica": 4, "alta": 8, "media": 24, "baja": 72}  # acuerdos de nivel de servicio por prioridad
RUTA_RESPALDOS = Path(os.environ.get("RUTA_RESPALDOS", "/backups"))


# ============================================================================ ESTADO
def _ultimo_respaldo() -> dict:
    if not RUTA_RESPALDOS.exists():
        return {"disponible": False, "detalle": "Carpeta de respaldos no montada en el backend"}
    archivos = sorted(RUTA_RESPALDOS.glob("xentra_*.dump"), key=lambda p: p.stat().st_mtime)
    verificacion = RUTA_RESPALDOS / "ultima_verificacion.txt"
    salida = {"disponible": bool(archivos), "cantidad": len(archivos)}
    if archivos:
        ultimo = archivos[-1]
        horas = (time.time() - ultimo.stat().st_mtime) / 3600
        salida.update(ultimo=ultimo.name, horas_desde_ultimo=round(horas, 1), tamano_mb=round(ultimo.stat().st_size / 1e6, 2),
                      alerta=horas > 26)
    if verificacion.exists():
        salida["ultima_prueba_restauracion"] = verificacion.read_text(encoding="utf-8").strip()[:300]
    return salida


@router.get("/estado")
def estado(db: Session = Depends(get_db), _: Usuario = Depends(requiere_rol(*AUDITORIA_SEGURIDAD))):
    t0 = time.perf_counter()
    db.execute(text("SELECT 1"))
    latencia = round((time.perf_counter() - t0) * 1000, 1)
    disco = shutil.disk_usage("/")
    ancla = db.scalars(select(AnclajeLedger).order_by(AnclajeLedger.id.desc()).limit(1)).first()
    rda = dict(db.execute(select(RdaEnvio.estado, func.count()).group_by(RdaEnvio.estado)).all())
    tickets = db.scalars(select(Ticket).where(Ticket.estado.in_(("abierto", "en_proceso")))).all()
    ahora = datetime.now(timezone.utc)
    respaldo = _ultimo_respaldo()
    alertas = []
    if latencia > 500:
        alertas.append(f"La base de datos responde lento ({latencia} ms)")
    if disco.free / disco.total < 0.1:
        alertas.append("Menos del 10 % de disco libre")
    if respaldo.get("alerta"):
        alertas.append("El último respaldo tiene más de 26 horas")
    if rda.get("error"):
        alertas.append(f"{rda['error']} RDA con error de envío a la IHCE")
    if (vencidos := sum(1 for t in tickets if a_utc(t.vence_en) < ahora)):
        alertas.append(f"{vencidos} ticket(s) de soporte con ANS vencido")
    return {
        "version": VERSION, "activo_desde_horas": round((time.time() - INICIO) / 3600, 1),
        "base_datos": {"estado": "ok", "latencia_ms": latencia},
        "disco": {"libre_gb": round(disco.free / 1e9, 1), "total_gb": round(disco.total / 1e9, 1),
                  "libre_pct": round(100 * disco.free / disco.total, 1)},
        "respaldos": respaldo,
        "ledger": {"bloques": db.scalar(select(func.count()).select_from(BloqueLedger)),
                   "ultimo_anclaje": ancla.creado_en if ancla else None},
        "integraciones": {"dian": settings.DIAN_MODO, "muv": settings.MUV_MODO, "rda_ihce": settings.RDA_MODO,
                          "ia": settings.IA_PROVEEDOR, "anclaje": settings.ANCLAJE_MODO},
        "rda": rda,
        "soporte": {"tickets_abiertos": len(tickets), "criticos": sum(1 for t in tickets if t.prioridad == "critica")},
        "alertas": alertas,
        "estado_general": "degradado" if alertas else "operativo",
    }


# ============================================================================ AVISOS
class AvisoIn(BaseModel):
    nivel: str = Field("info", pattern="^(info|aviso|critico)$")
    mensaje: str = Field(min_length=5, max_length=500)
    desde: datetime | None = None
    hasta: datetime | None = None


@router.get("/avisos")
def avisos(db: Session = Depends(get_db), _: Usuario = Depends(usuario_actual)):
    ahora = datetime.now(timezone.utc)
    filas = db.scalars(select(AvisoSistema).order_by(AvisoSistema.id.desc()).limit(50)).all()
    return [{"id": a.id, "nivel": a.nivel, "mensaje": a.mensaje, "hasta": a.hasta} for a in filas
            if a_utc(a.desde) <= ahora and (a.hasta is None or a_utc(a.hasta) >= ahora)]


@router.post("/avisos", status_code=201)
def crear_aviso(datos: AvisoIn, db: Session = Depends(get_db), admin: Usuario = Depends(requiere_rol(*ADMIN_GESTION))):
    a = AvisoSistema(nivel=datos.nivel, mensaje=datos.mensaje, desde=datos.desde or datetime.now(timezone.utc),
                     hasta=datos.hasta, creado_por=admin.id)
    db.add(a)
    db.commit()
    return {"id": a.id}


@router.delete("/avisos/{aviso_id}", status_code=204)
def quitar_aviso(aviso_id: int, db: Session = Depends(get_db), _: Usuario = Depends(requiere_rol(*ADMIN_GESTION))):
    a = db.get(AvisoSistema, aviso_id)
    if a:
        a.hasta = datetime.now(timezone.utc)
        db.commit()


# ============================================================================ MESA DE AYUDA
class TicketIn(BaseModel):
    titulo: str = Field(min_length=5, max_length=200)
    descripcion: str = Field(min_length=10)
    categoria: str = Field("incidente", pattern="^(incidente|solicitud|mejora|seguridad)$")
    prioridad: str = Field("media", pattern="^(critica|alta|media|baja)$")
    modulo: str | None = None
    codigo_error: str | None = None


class TicketAccion(BaseModel):
    estado: str | None = Field(None, pattern="^(abierto|en_proceso|resuelto|cerrado)$")
    comentario: str | None = None
    solucion: str | None = None
    asignado_a: uuid.UUID | None = None


def _ticket(t: Ticket) -> dict:
    ahora = datetime.now(timezone.utc)
    return {"id": t.id, "titulo": t.titulo, "descripcion": t.descripcion, "categoria": t.categoria, "prioridad": t.prioridad,
            "modulo": t.modulo, "codigo_error": t.codigo_error, "estado": t.estado, "autor": t.autor.nombre_completo,
            "asignado_a": str(t.asignado_a) if t.asignado_a else None, "creado_en": t.creado_en, "vence_en": t.vence_en,
            "resuelto_en": t.resuelto_en, "solucion": t.solucion, "comentarios": t.comentarios,
            "vencido": t.estado in ("abierto", "en_proceso") and a_utc(t.vence_en) < ahora}


@router.get("/tickets")
def tickets(estado: str | None = None, db: Session = Depends(get_db), usuario: Usuario = Depends(requiere_rol(*PERSONAL))):
    q = select(Ticket).order_by(Ticket.id.desc()).limit(300)
    if estado:
        q = q.where(Ticket.estado == estado)
    if not es_admin(usuario):
        q = q.where(Ticket.creado_por == usuario.id)
    return [_ticket(t) for t in db.scalars(q).all()]


@router.post("/tickets", status_code=201)
def crear_ticket(datos: TicketIn, request: Request, db: Session = Depends(get_db),
                 usuario: Usuario = Depends(requiere_rol(*PERSONAL))):
    ahora = datetime.now(timezone.utc)
    t = Ticket(**datos.model_dump(), creado_por=usuario.id, creado_en=ahora,
               vence_en=ahora + timedelta(hours=ANS_HORAS[datos.prioridad]), comentarios=[])
    db.add(t)
    db.flush()
    registrar_evento(db, accion="TICKET_CREADO", entidad="ticket", entidad_id=None,
                     datos={"id": t.id, "prioridad": t.prioridad, "categoria": t.categoria}, usuario_id=usuario.id,
                     ip=ip_cliente(request))
    db.commit()
    db.refresh(t)
    return _ticket(t)


@router.patch("/tickets/{ticket_id}")
def actualizar_ticket(ticket_id: int, datos: TicketAccion, db: Session = Depends(get_db),
                      usuario: Usuario = Depends(requiere_rol(*PERSONAL))):
    t = db.get(Ticket, ticket_id)
    if not t or (not es_admin(usuario) and t.creado_por != usuario.id):
        raise HTTPException(404, "Ticket no encontrado")
    if (datos.estado or datos.asignado_a or datos.solucion) and not es_admin(usuario):
        raise HTTPException(403, "Solo soporte (administrador) cambia el estado o la asignación")
    if datos.comentario:
        t.comentarios = [*t.comentarios, {"autor": usuario.nombre_completo, "fecha": datetime.now(timezone.utc).isoformat(),
                                          "texto": datos.comentario}]
    if datos.asignado_a:
        t.asignado_a = datos.asignado_a
    if datos.solucion:
        t.solucion = datos.solucion
    if datos.estado:
        if datos.estado in ("resuelto", "cerrado") and not (t.solucion or datos.solucion):
            raise HTTPException(422, "Registre la solución antes de resolver el ticket (base de conocimiento)")
        t.estado = datos.estado
        if datos.estado == "resuelto":
            t.resuelto_en = datetime.now(timezone.utc)
    db.commit()
    db.refresh(t)
    return _ticket(t)


@router.get("/base-conocimiento")
def base_conocimiento(q: str | None = None, db: Session = Depends(get_db), _: Usuario = Depends(requiere_rol(*PERSONAL))):
    """Soluciones de tickets resueltos: el personal resuelve solo los problemas repetidos."""
    filas = db.scalars(select(Ticket).where(Ticket.estado.in_(("resuelto", "cerrado")), Ticket.solucion.is_not(None))
                       .order_by(Ticket.id.desc()).limit(200)).all()
    if q:
        filas = [t for t in filas if q.lower() in f"{t.titulo} {t.descripcion} {t.solucion} {t.modulo}".lower()]
    return [{"id": t.id, "titulo": t.titulo, "modulo": t.modulo, "solucion": t.solucion} for t in filas]


# ============================================================================ MODO CONTINGENCIA
@router.get("/contingencia")
def contingencia(request: Request, fecha: date | None = None, db: Session = Depends(get_db),
                 usuario: Usuario = Depends(requiere_rol("admin", "medico", "enfermeria", "admisiones"))):
    """PDF para operar en papel si se cae la red o el servidor: agenda del día con alergias, problemas y
    medicamentos de cada paciente, y censo hospitalario con órdenes activas. Descárguelo al iniciar cada turno."""
    from app.services.pdf import Documento, fecha as f_fecha
    from app.services.resumen import resumen_estructurado
    from app.services.rips import edad_en

    fecha = fecha or date.today()
    ini = datetime.combine(fecha, hora.min, TZ).astimezone(timezone.utc)
    fin = datetime.combine(fecha, hora.max, TZ).astimezone(timezone.utc)
    citas = db.scalars(select(Cita).where(Cita.inicio >= ini, Cita.inicio <= fin, Cita.estado.notin_(("cancelada",)))
                       .order_by(Cita.inicio)).all()
    hosp = db.scalars(select(Hospitalizacion).where(Hospitalizacion.estado == "activa")).all()
    doc = Documento(f"PLAN DE CONTINGENCIA - {fecha.isoformat()} (generado {f_fecha(datetime.now(timezone.utc))})")
    doc.seccion("Instrucciones", "Use este documento SOLO si el sistema no está disponible. Registre las atenciones en los "
                "formatos de contingencia en papel y transcríbalas al sistema cuando se restablezca, indicando "
                "'registro diferido por contingencia'. Custodie este documento: contiene datos sensibles (Ley 1581).")

    def bloque_paciente(p, titulo):
        atenciones = db.scalars(select(Atencion).where(Atencion.paciente_id == p.id, Atencion.estado == "firmada")
                                .order_by(Atencion.fecha_inicio)).all()
        r = resumen_estructurado(p, list(atenciones), [], [], edad_en(p.fecha_nacimiento))
        problemas = ", ".join(f"{x['codigo']} {x['descripcion'][:40]}" for x in r["problemas_activos"][:5]) or "-"
        meds = "; ".join(r["medicamentos_recientes"][-5:]) or "-"
        doc.seccion(titulo, f"{p.tipo_documento} {p.numero_documento} · {edad_en(p.fecha_nacimiento)} años · "
                    f"EPS {p.cod_eapb or '-'} · Tel {p.telefono or '-'}\nALERGIAS: {p.alergias or 'No conocidas'}\n"
                    f"Problemas: {problemas}\nMedicamentos recientes: {meds}")

    for c in citas:
        bloque_paciente(c.paciente, f"{a_utc(c.inicio).astimezone(TZ):%H:%M} · {c.paciente.nombre_completo} · "
                                    f"{c.profesional.nombre_completo} ({c.modalidad})")
    if hosp:
        doc.add_page()
        doc.seccion("CENSO HOSPITALARIO", f"{len(hosp)} pacientes hospitalizados")
        for h in hosp:
            ordenes = "\n".join(f"- {o.tipo}: {o.descripcion} {o.dosis or ''} {o.via or ''} {o.frecuencia or ''}"
                                for o in h.ordenes if o.estado == "activa") or "- Sin órdenes activas"
            doc.seccion(f"Cama {h.cama.codigo if h.cama else '-'} · {h.paciente.nombre_completo}",
                        f"Ingreso {f_fecha(h.fecha_ingreso)} · Dx {h.dx_ingreso} · ALERGIAS: {h.paciente.alergias or 'No conocidas'}\n"
                        f"Órdenes activas:\n{ordenes}")
    if not citas and not hosp:
        doc.seccion("Sin datos", "No hay citas para la fecha ni pacientes hospitalizados.")
    registrar_evento(db, accion="CONTINGENCIA_DESCARGA", entidad="sistema", datos={"fecha": fecha.isoformat()},
                     usuario_id=usuario.id, ip=ip_cliente(request))
    db.commit()
    return Response(doc.bytes(), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="contingencia_{fecha.isoformat()}.pdf"'})
