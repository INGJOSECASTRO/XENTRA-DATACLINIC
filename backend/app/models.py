"""Modelos de base de datos (tablas).

Referencias normativas principales:
- Resolución 1995 de 1999: historia clínica (integralidad, secuencialidad, inalterabilidad).
- Resolución 866 de 2021 / Ley 2015 de 2020: elementos de datos de la HCE interoperable.
- Resolución 2275 de 2023: RIPS como soporte de la factura electrónica.
- Ley 1581 de 2012: protección de datos personales (datos sensibles de salud).
"""
import enum
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

JSONType = JSON().with_variant(JSONB(), "postgresql")


def ahora_utc() -> datetime:
    return datetime.now(timezone.utc)


class Rol(str, enum.Enum):
    ADMIN = "admin"
    MEDICO = "medico"
    ENFERMERIA = "enfermeria"
    FACTURACION = "facturacion"
    AUDITOR = "auditor"
    ADMISIONES = "admisiones"


class EstadoAtencion(str, enum.Enum):
    BORRADOR = "borrador"
    FIRMADA = "firmada"


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tipo_documento: Mapped[str] = mapped_column(String(3), default="CC")
    numero_documento: Mapped[str] = mapped_column(String(20))
    nombres: Mapped[str] = mapped_column(String(100))
    apellidos: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    rol: Mapped[str] = mapped_column(String(20), default=Rol.MEDICO.value)
    registro_profesional: Mapped[str | None] = mapped_column(String(30))  # ReTHUS / tarjeta profesional
    especialidad: Mapped[str | None] = mapped_column(String(100))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    intentos_fallidos: Mapped[int] = mapped_column(Integer, default=0)
    bloqueado_hasta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)

    @property
    def nombre_completo(self) -> str:
        return f"{self.nombres} {self.apellidos}"


class Paciente(Base):
    __tablename__ = "pacientes"
    __table_args__ = (UniqueConstraint("tipo_documento", "numero_documento", name="uq_paciente_documento"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # Tipos RIPS: CC, TI, RC, CE, PA, PE, PT, CD, SC, MS, AS, CN, DE, SI
    tipo_documento: Mapped[str] = mapped_column(String(3))
    numero_documento: Mapped[str] = mapped_column(String(20), index=True)
    primer_nombre: Mapped[str] = mapped_column(String(60))
    segundo_nombre: Mapped[str | None] = mapped_column(String(60))
    primer_apellido: Mapped[str] = mapped_column(String(60))
    segundo_apellido: Mapped[str | None] = mapped_column(String(60))
    fecha_nacimiento: Mapped[date] = mapped_column(Date)
    sexo: Mapped[str] = mapped_column(String(1))  # H, M, I (codSexo RIPS)
    identidad_genero: Mapped[str | None] = mapped_column(String(40))
    telefono: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(150))
    direccion: Mapped[str | None] = mapped_column(String(200))
    cod_pais_residencia: Mapped[str] = mapped_column(String(3), default="170")  # 170 = Colombia
    cod_municipio_residencia: Mapped[str] = mapped_column(String(5), default="11001")  # DIVIPOLA
    zona_territorial: Mapped[str] = mapped_column(String(2), default="02")  # 01 rural, 02 urbana
    tipo_usuario: Mapped[str] = mapped_column(String(2), default="01")  # régimen (tabla RIPS)
    cod_eapb: Mapped[str | None] = mapped_column(String(10))  # EPS / entidad responsable de pago
    grupo_sanguineo: Mapped[str | None] = mapped_column(String(3))
    alergias: Mapped[str | None] = mapped_column(Text)
    ocupacion: Mapped[str | None] = mapped_column(String(100))
    acompanante_nombre: Mapped[str | None] = mapped_column(String(120))
    acompanante_telefono: Mapped[str | None] = mapped_column(String(20))
    # Ley 1581 de 2012: autorización expresa para tratar datos sensibles
    autoriza_tratamiento_datos: Mapped[bool] = mapped_column(Boolean, default=False)
    fecha_autorizacion_datos: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)

    atenciones: Mapped[list["Atencion"]] = relationship(back_populates="paciente", order_by="Atencion.fecha_inicio")

    @property
    def nombre_completo(self) -> str:
        partes = [self.primer_nombre, self.segundo_nombre, self.primer_apellido, self.segundo_apellido]
        return " ".join(p for p in partes if p)


class Atencion(Base):
    """Un folio de la historia clínica (consulta, urgencia, hospitalización...)."""

    __tablename__ = "atenciones"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    paciente_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pacientes.id"), index=True)
    profesional_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuarios.id"))
    consecutivo: Mapped[int] = mapped_column(Integer)  # número de folio dentro de la HC del paciente
    fecha_inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)
    tipo: Mapped[str] = mapped_column(String(20), default="consulta")  # consulta|urgencias|hospitalizacion
    # --- Datos clínicos (formato SOAP) ---
    motivo_consulta: Mapped[str] = mapped_column(Text)
    enfermedad_actual: Mapped[str | None] = mapped_column(Text)
    antecedentes: Mapped[dict | None] = mapped_column(JSONType)
    revision_sistemas: Mapped[str | None] = mapped_column(Text)
    signos_vitales: Mapped[dict | None] = mapped_column(JSONType)
    examen_fisico: Mapped[str | None] = mapped_column(Text)
    analisis: Mapped[str | None] = mapped_column(Text)
    plan: Mapped[str | None] = mapped_column(Text)
    # --- Datos RIPS ---
    cod_consulta_cups: Mapped[str] = mapped_column(String(6), default="890201")
    modalidad_grupo_servicio: Mapped[str] = mapped_column(String(2), default="01")
    grupo_servicios: Mapped[str] = mapped_column(String(2), default="01")
    cod_servicio: Mapped[int] = mapped_column(Integer, default=328)
    finalidad_tecnologia: Mapped[str] = mapped_column(String(2), default="44")
    causa_motivo_atencion: Mapped[str] = mapped_column(String(2), default="38")
    num_autorizacion: Mapped[str | None] = mapped_column(String(30))
    valor_servicio: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)
    concepto_recaudo: Mapped[str] = mapped_column(String(2), default="05")
    valor_pago_moderador: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)
    # --- Integridad ---
    estado: Mapped[str] = mapped_column(String(10), default=EstadoAtencion.BORRADOR.value)
    firmada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    hash_contenido: Mapped[str | None] = mapped_column(String(64))
    bloque_ledger_id: Mapped[int | None] = mapped_column(Integer)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)

    paciente: Mapped[Paciente] = relationship(back_populates="atenciones")
    profesional: Mapped[Usuario] = relationship()
    diagnosticos: Mapped[list["Diagnostico"]] = relationship(
        back_populates="atencion", cascade="all, delete-orphan", order_by="Diagnostico.orden"
    )
    procedimientos: Mapped[list["Procedimiento"]] = relationship(back_populates="atencion", cascade="all, delete-orphan")
    prescripciones: Mapped[list["Prescripcion"]] = relationship(back_populates="atencion", cascade="all, delete-orphan")
    notas_aclaratorias: Mapped[list["NotaAclaratoria"]] = relationship(
        back_populates="atencion", order_by="NotaAclaratoria.creado_en"
    )


class Diagnostico(Base):
    __tablename__ = "diagnosticos"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    atencion_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("atenciones.id"), index=True)
    orden: Mapped[int] = mapped_column(Integer, default=0)  # 0 = principal, 1..3 = relacionados
    codigo_cie10: Mapped[str] = mapped_column(String(4))
    descripcion: Mapped[str] = mapped_column(String(255))
    # 01 Impresión diagnóstica, 02 Confirmado nuevo, 03 Confirmado repetido
    tipo_diagnostico: Mapped[str] = mapped_column(String(2), default="01")
    sugerido_por_ia: Mapped[bool] = mapped_column(Boolean, default=False)

    atencion: Mapped[Atencion] = relationship(back_populates="diagnosticos")


class Procedimiento(Base):
    __tablename__ = "procedimientos"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    atencion_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("atenciones.id"), index=True)
    cod_cups: Mapped[str] = mapped_column(String(6))
    descripcion: Mapped[str] = mapped_column(String(255))
    via_ingreso: Mapped[str] = mapped_column(String(2), default="01")
    finalidad_tecnologia: Mapped[str] = mapped_column(String(2), default="16")
    valor: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)

    atencion: Mapped[Atencion] = relationship(back_populates="procedimientos")


class Prescripcion(Base):
    """Fórmula médica."""

    __tablename__ = "prescripciones"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    atencion_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("atenciones.id"), index=True)
    medicamento: Mapped[str] = mapped_column(String(200))  # denominación común internacional
    cum: Mapped[str | None] = mapped_column(String(20))  # código único de medicamento INVIMA
    concentracion: Mapped[str | None] = mapped_column(String(60))
    forma_farmaceutica: Mapped[str | None] = mapped_column(String(60))
    dosis: Mapped[str] = mapped_column(String(100))
    via: Mapped[str] = mapped_column(String(40), default="oral")
    frecuencia: Mapped[str] = mapped_column(String(60))
    duracion_dias: Mapped[int] = mapped_column(Integer, default=1)
    cantidad: Mapped[int] = mapped_column(Integer, default=1)
    indicaciones: Mapped[str | None] = mapped_column(Text)

    atencion: Mapped[Atencion] = relationship(back_populates="prescripciones")


class NotaAclaratoria(Base):
    """Una HC firmada NO se edita; los errores se corrigen con notas aclaratorias (Res. 1995/1999)."""

    __tablename__ = "notas_aclaratorias"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    atencion_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("atenciones.id"), index=True)
    autor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuarios.id"))
    texto: Mapped[str] = mapped_column(Text)
    hash_contenido: Mapped[str] = mapped_column(String(64))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)

    atencion: Mapped[Atencion] = relationship(back_populates="notas_aclaratorias")
    autor: Mapped[Usuario] = relationship()


class BloqueLedger(Base):
    """Libro mayor inmutable encadenado por hashes (seguridad tipo blockchain).

    Cada bloque guarda el hash del bloque anterior; si alguien altera un registro,
    la cadena se rompe y la verificación lo detecta. Además cada bloque se firma
    con HMAC usando una llave que NO está en la base de datos.
    """

    __tablename__ = "ledger_bloques"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    marca_tiempo: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    usuario_id: Mapped[str | None] = mapped_column(String(36))
    accion: Mapped[str] = mapped_column(String(40), index=True)
    entidad: Mapped[str] = mapped_column(String(40))
    entidad_id: Mapped[str | None] = mapped_column(String(36), index=True)
    hash_datos: Mapped[str] = mapped_column(String(64))
    hash_anterior: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64), unique=True)
    firma: Mapped[str] = mapped_column(String(64))
    ip_origen: Mapped[str | None] = mapped_column(String(45))


class CIE10(Base):
    __tablename__ = "cie10"

    codigo: Mapped[str] = mapped_column(String(4), primary_key=True)
    descripcion: Mapped[str] = mapped_column(String(255))
    texto_busqueda: Mapped[str] = mapped_column(Text)  # minúsculas sin tildes para búsquedas
    sexo: Mapped[str] = mapped_column(String(1), default="A")  # A ambos, H hombre, M mujer
    edad_minima: Mapped[int] = mapped_column(Integer, default=0)  # años
    edad_maxima: Mapped[int] = mapped_column(Integer, default=120)
