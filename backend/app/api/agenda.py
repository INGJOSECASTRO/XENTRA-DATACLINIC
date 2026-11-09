"""Agenda de citas, disponibilidad, telemedicina y recordatorios."""
import secrets
import uuid
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import AGENDA, ip_cliente, requiere_rol
from app.models import Paciente, Usuario
from app.models_ext import Cita
from app.services.integraciones import notificar
from app.services.ledger import a_utc, registrar_evento

router = APIRouter(prefix="/api/citas", tags=["Agenda"])
TZ = ZoneInfo(settings.ZONA_HORARIA)
ESTADOS = ("programada", "confirmada", "en_sala", "atendida", "cancelada", "no_asistio")
TRANSICIONES = {
    "programada": {"confirmada", "en_sala", "cancelada", "no_asistio"},
    "confirmada": {"en_sala", "cancelada", "no_asistio"},
    "en_sala": {"atendida", "no_asistio"},
    "atendida": set(), "cancelada": set(), "no_asistio": set(),
}


class CitaIn(BaseModel):
    paciente_id: uuid.UUID
    profesional_id: uuid.UUID
    sede_id: uuid.UUID | None = None
    inicio: datetime
    duracion_min: int = Field(20, ge=5, le=240)
    cod_cups: str = Field("890201", pattern=r"^[0-9A-Za-z]{6}$")
    modalidad: str = Field("presencial", pattern="^(presencial|telemedicina)$")
    motivo: str | None = None
    fecha_deseada: date | None = None
    num_autorizacion: str | None = None


class EstadoIn(BaseModel):
    estado: str
    motivo_cancelacion: str | None = None


class ReprogramarIn(BaseModel):
    inicio: datetime


class PersonaMin(BaseModel):
    id: uuid.UUID
    nombre_completo: str
    model_config = {"from_attributes": True}


class PacienteMin(PersonaMin):
    tipo_documento: str
    numero_documento: str
    telefono: str | None


class CitaOut(BaseModel):
    id: uuid.UUID
    paciente: PacienteMin
    profesional: PersonaMin
    sede_id: uuid.UUID | None
    inicio: datetime
    duracion_min: int
    cod_cups: str
    modalidad: str
    estado: str
    motivo: str | None
    sala_virtual: str | None
    fecha_solicitud: datetime
    fecha_deseada: date | None
    motivo_cancelacion: str | None
    atencion_id: uuid.UUID | None
    model_config = {"from_attributes": True}


def _aware(dt: datetime) -> datetime:
    """Fechas sin zona se interpretan como hora de Colombia; todo se guarda en UTC."""
    return (dt.replace(tzinfo=TZ) if dt.tzinfo is None else dt).astimezone(timezone.utc)


def _dia(fecha: date, hora: time) -> datetime:
    return datetime.combine(fecha, hora, TZ).astimezone(timezone.utc)


def _cruces(db: Session, campo, valor, inicio: datetime, fin: datetime, excluir: uuid.UUID | None = None) -> list[Cita]:
    q = select(Cita).where(campo == valor, Cita.estado.notin_(("cancelada", "no_asistio")),
                           Cita.inicio < fin, Cita.inicio > inicio - timedelta(hours=4))
    if excluir:
        q = q.where(Cita.id != excluir)
    return [c for c in db.scalars(q).all() if a_utc(c.inicio) + timedelta(minutes=c.duracion_min) > inicio]


def _validar_horario(db: Session, cita: Cita, excluir: uuid.UUID | None = None) -> None:
    inicio = a_utc(cita.inicio)
    fin = inicio + timedelta(minutes=cita.duracion_min)
    if _cruces(db, Cita.profesional_id, cita.profesional_id, inicio, fin, excluir):
        raise HTTPException(409, "El profesional ya tiene una cita en ese horario")
    if _cruces(db, Cita.paciente_id, cita.paciente_id, inicio, fin, excluir):
        raise HTTPException(409, "El paciente ya tiene una cita en ese horario")


@router.get("", response_model=list[CitaOut])
def listar(desde: date | None = None, hasta: date | None = None, profesional_id: uuid.UUID | None = None,
           paciente_id: uuid.UUID | None = None, estado: str | None = None, db: Session = Depends(get_db),
           _: Usuario = Depends(requiere_rol(*AGENDA, "facturacion"))):
    desde = desde or date.today()
    hasta = hasta or desde
    q = select(Cita).where(Cita.inicio >= _dia(desde, time.min), Cita.inicio <= _dia(hasta, time.max)).order_by(Cita.inicio)
    if profesional_id:
        q = q.where(Cita.profesional_id == profesional_id)
    if paciente_id:
        q = q.where(Cita.paciente_id == paciente_id)
    if estado:
        q = q.where(Cita.estado == estado)
    return db.scalars(q).all()


@router.get("/disponibilidad")
def disponibilidad(profesional_id: uuid.UUID, fecha: date, duracion: int = Query(20, ge=5, le=240),
                   hora_inicio: int = Query(7, ge=0, le=23), hora_fin: int = Query(17, ge=1, le=24),
                   db: Session = Depends(get_db), _: Usuario = Depends(requiere_rol(*AGENDA))):
    """Horarios libres del profesional en la fecha (jornada configurable)."""
    libres = []
    actual = _dia(fecha, time(hora_inicio))
    fin_jornada = _dia(fecha, time(0)) + timedelta(hours=hora_fin)
    ahora = datetime.now(timezone.utc)
    while actual + timedelta(minutes=duracion) <= fin_jornada:
        fin = actual + timedelta(minutes=duracion)
        if actual > ahora and not _cruces(db, Cita.profesional_id, profesional_id, actual, fin):
            libres.append(actual.astimezone(TZ).isoformat())
        actual = fin
    return {"profesional_id": str(profesional_id), "fecha": fecha.isoformat(), "libres": libres}


@router.post("", response_model=CitaOut, status_code=201)
def crear(datos: CitaIn, request: Request, db: Session = Depends(get_db), usuario: Usuario = Depends(requiere_rol(*AGENDA))):
    paciente = db.get(Paciente, datos.paciente_id)
    profesional = db.get(Usuario, datos.profesional_id)
    if not paciente:
        raise HTTPException(404, "Paciente no encontrado")
    if not profesional or profesional.rol not in ("medico", "enfermeria") or not profesional.activo:
        raise HTTPException(422, "El profesional no existe o no atiende citas")
    inicio = _aware(datos.inicio)
    if inicio < datetime.now(timezone.utc) - timedelta(minutes=5):
        raise HTTPException(422, "No se pueden asignar citas en el pasado")
    cita = Cita(**datos.model_dump(exclude={"inicio"}), inicio=inicio, creado_por=usuario.id)
    _validar_horario(db, cita)
    if cita.modalidad == "telemedicina":
        cita.sala_virtual = f"{settings.JITSI_URL.rstrip('/')}/xentra-{secrets.token_urlsafe(12)}"
    db.add(cita)
    db.flush()
    registrar_evento(db, accion="CITA_ASIGNADA", entidad="cita", entidad_id=cita.id,
                     datos={"paciente_id": str(paciente.id), "inicio": inicio.isoformat()}, usuario_id=usuario.id,
                     ip=ip_cliente(request))
    db.commit()
    db.refresh(cita)
    return cita


@router.patch("/{cita_id}/estado", response_model=CitaOut)
def cambiar_estado(cita_id: uuid.UUID, datos: EstadoIn, request: Request, db: Session = Depends(get_db),
                   usuario: Usuario = Depends(requiere_rol(*AGENDA))):
    cita = db.get(Cita, cita_id)
    if not cita:
        raise HTTPException(404, "Cita no encontrada")
    if datos.estado not in TRANSICIONES.get(cita.estado, set()):
        raise HTTPException(409, f"No se puede pasar de '{cita.estado}' a '{datos.estado}'")
    if datos.estado == "cancelada" and not datos.motivo_cancelacion:
        raise HTTPException(422, "Indique el motivo de la cancelación")
    cita.estado = datos.estado
    cita.motivo_cancelacion = datos.motivo_cancelacion
    registrar_evento(db, accion=f"CITA_{datos.estado.upper()}", entidad="cita", entidad_id=cita.id,
                     usuario_id=usuario.id, ip=ip_cliente(request))
    db.commit()
    return cita


@router.post("/{cita_id}/reprogramar", response_model=CitaOut)
def reprogramar(cita_id: uuid.UUID, datos: ReprogramarIn, request: Request, db: Session = Depends(get_db),
                usuario: Usuario = Depends(requiere_rol(*AGENDA))):
    cita = db.get(Cita, cita_id)
    if not cita or cita.estado not in ("programada", "confirmada"):
        raise HTTPException(409, "Solo se reprograman citas programadas o confirmadas")
    cita.inicio = _aware(datos.inicio)
    _validar_horario(db, cita, excluir=cita.id)
    cita.estado = "programada"
    registrar_evento(db, accion="CITA_REPROGRAMADA", entidad="cita", entidad_id=cita.id,
                     datos={"inicio": cita.inicio.isoformat()}, usuario_id=usuario.id, ip=ip_cliente(request))
    db.commit()
    return cita


@router.post("/recordatorios")
def recordatorios(fecha: date | None = None, db: Session = Depends(get_db),
                  _: Usuario = Depends(requiere_rol("admisiones", "admin"))):
    """Envía recordatorios de las citas de la fecha (por defecto, mañana). Programable con cron."""
    fecha = fecha or date.today() + timedelta(days=1)
    citas = db.scalars(select(Cita).where(
        Cita.inicio >= _dia(fecha, time.min), Cita.inicio <= _dia(fecha, time.max),
        Cita.estado.in_(("programada", "confirmada")))).all()
    enviados = []
    for c in citas:
        hora = a_utc(c.inicio).astimezone(TZ).strftime("%d/%m/%Y %I:%M %p")
        texto = (f"{settings.PRESTADOR_RAZON_SOCIAL}: recordamos su cita el {hora} con {c.profesional.nombre_completo}."
                 + (f" Ingrese a la teleconsulta: {c.sala_virtual}" if c.sala_virtual else " Llegue 15 minutos antes."))
        enviados.append({"cita_id": str(c.id), **notificar(c.paciente.telefono or c.paciente.email, texto)})
    return {"fecha": fecha.isoformat(), "total": len(enviados), "resultados": enviados}
