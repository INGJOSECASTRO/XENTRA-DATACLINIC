"""Esquemas Pydantic: validan lo que entra y lo que sale de la API."""
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.services.cie10 import codigo_valido, formatear_codigo

TipoDoc = Literal["CC", "TI", "RC", "CE", "PA", "PE", "PT", "CD", "SC", "MS", "AS", "CN", "DE", "SI"]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------- Autenticación / usuarios ----------------
class Token(BaseModel):
    access_token: str | None = None
    token_type: str = "bearer"
    mfa_requerido: bool = False
    token_mfa: str | None = None
    usuario: "UsuarioOut"


class MfaCodigo(BaseModel):
    codigo: str = Field(min_length=6, max_length=8)


class MfaVerificar(MfaCodigo):
    token_mfa: str


class CambioClave(BaseModel):
    actual: str
    nueva: str


class UsuarioCrear(BaseModel):
    tipo_documento: TipoDoc = "CC"
    numero_documento: str = Field(min_length=3, max_length=20)
    nombres: str = Field(min_length=2, max_length=100)
    apellidos: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str
    rol: Literal["admin", "admin_tecnico", "medico", "enfermeria", "estudiante", "facturacion", "auditor",
                 "auditor_sistemas", "admisiones", "farmacia", "laboratorio", "auxiliar_laboratorio"]
    registro_profesional: str | None = None
    especialidad: str | None = None
    sede_id: uuid.UUID | None = None


class UsuarioOut(ORM):
    id: uuid.UUID
    tipo_documento: str
    numero_documento: str
    nombres: str
    apellidos: str
    email: str
    rol: str
    registro_profesional: str | None
    especialidad: str | None
    activo: bool
    mfa_activo: bool = False
    mfa_obligatorio: bool = False
    debe_cambiar_clave: bool = False
    sede_id: uuid.UUID | None = None
    paciente_id: uuid.UUID | None = None


# ---------------- Pacientes ----------------
class PacienteBase(BaseModel):
    tipo_documento: TipoDoc
    numero_documento: str = Field(min_length=3, max_length=20, pattern=r"^[A-Za-z0-9]+$")
    primer_nombre: str = Field(min_length=1, max_length=60)
    segundo_nombre: str | None = None
    primer_apellido: str = Field(min_length=1, max_length=60)
    segundo_apellido: str | None = None
    fecha_nacimiento: date
    sexo: Literal["H", "M", "I"]
    identidad_genero: str | None = None
    telefono: str | None = None
    email: EmailStr | None = None
    direccion: str | None = None
    cod_pais_residencia: str = "170"
    cod_municipio_residencia: str = Field("11001", pattern=r"^\d{5}$")
    zona_territorial: Literal["01", "02"] = "02"
    tipo_usuario: str = Field("01", pattern=r"^\d{2}$")
    cod_eapb: str | None = None
    grupo_sanguineo: str | None = None
    alergias: str | None = None
    ocupacion: str | None = None
    acompanante_nombre: str | None = None
    acompanante_telefono: str | None = None
    autoriza_tratamiento_datos: bool = False

    @field_validator("fecha_nacimiento")
    @classmethod
    def no_futura(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("La fecha de nacimiento no puede ser futura")
        return v


class PacienteCrear(PacienteBase):
    pass


class PacienteActualizar(BaseModel):
    telefono: str | None = None
    email: EmailStr | None = None
    direccion: str | None = None
    cod_municipio_residencia: str | None = Field(None, pattern=r"^\d{5}$")
    zona_territorial: Literal["01", "02"] | None = None
    tipo_usuario: str | None = None
    cod_eapb: str | None = None
    grupo_sanguineo: str | None = None
    alergias: str | None = None
    ocupacion: str | None = None
    acompanante_nombre: str | None = None
    acompanante_telefono: str | None = None
    autoriza_tratamiento_datos: bool | None = None


class PacienteOut(PacienteBase, ORM):
    id: uuid.UUID
    nombre_completo: str
    edad: int | None = None
    fecha_autorizacion_datos: datetime | None
    creado_en: datetime


# ---------------- Atenciones (folios de historia clínica) ----------------
class DiagnosticoIn(BaseModel):
    codigo_cie10: str
    descripcion: str = ""
    tipo_diagnostico: Literal["01", "02", "03"] = "01"
    sugerido_por_ia: bool = False

    @field_validator("codigo_cie10")
    @classmethod
    def validar_codigo(cls, v: str) -> str:
        v = formatear_codigo(v)
        if not codigo_valido(v):
            raise ValueError("Código CIE-10 inválido (ej: I10X, E119)")
        return v


class DiagnosticoOut(ORM):
    orden: int
    codigo_cie10: str
    descripcion: str
    tipo_diagnostico: str
    sugerido_por_ia: bool


class ProcedimientoIn(BaseModel):
    cod_cups: str = Field(pattern=r"^[0-9A-Za-z]{6}$")
    descripcion: str
    via_ingreso: str = "01"
    finalidad_tecnologia: str = "16"
    valor: Decimal = Decimal(0)


class ProcedimientoOut(ProcedimientoIn, ORM):
    pass


class PrescripcionIn(BaseModel):
    medicamento: str = Field(min_length=2)
    cum: str | None = None
    concentracion: str | None = None
    forma_farmaceutica: str | None = None
    dosis: str
    via: str = "oral"
    frecuencia: str
    duracion_dias: int = Field(1, ge=1, le=365)
    cantidad: int = Field(1, ge=1)
    indicaciones: str | None = None


class PrescripcionOut(PrescripcionIn, ORM):
    id: uuid.UUID


class SignosVitales(BaseModel):
    ta_sistolica: float | None = Field(None, ge=40, le=300)
    ta_diastolica: float | None = Field(None, ge=20, le=200)
    fc: float | None = Field(None, ge=20, le=250)
    fr: float | None = Field(None, ge=4, le=80)
    temperatura: float | None = Field(None, ge=30, le=45)
    spo2: float | None = Field(None, ge=40, le=100)
    peso: float | None = Field(None, ge=0.3, le=400)
    talla: float | None = Field(None, ge=20, le=250)  # cm


class AtencionGuardar(BaseModel):
    tipo: Literal["consulta", "urgencias", "hospitalizacion", "control"] = "consulta"
    motivo_consulta: str = Field(min_length=3)
    enfermedad_actual: str | None = None
    antecedentes: dict | None = None
    revision_sistemas: str | None = None
    signos_vitales: SignosVitales | None = None
    examen_fisico: str | None = None
    analisis: str | None = None
    plan: str | None = None
    cod_consulta_cups: str = Field("890201", pattern=r"^[0-9A-Za-z]{6}$")
    finalidad_tecnologia: str = "15"
    causa_motivo_atencion: str = "38"
    cod_servicio: int = 328
    num_autorizacion: str | None = None
    valor_servicio: Decimal = Decimal(0)
    valor_pago_moderador: Decimal = Decimal(0)
    modalidad_grupo_servicio: str = "01"
    grupo_servicios: str = "01"
    fecha_egreso: datetime | None = None
    condicion_egreso: str | None = None
    dx_causa_muerte: str | None = None
    sede_id: uuid.UUID | None = None
    diagnosticos: list[DiagnosticoIn] = Field(default_factory=list, max_length=4)
    procedimientos: list[ProcedimientoIn] = Field(default_factory=list)
    prescripciones: list[PrescripcionIn] = Field(default_factory=list)


class AtencionCrear(AtencionGuardar):
    paciente_id: uuid.UUID
    cita_id: uuid.UUID | None = None


class NotaIn(BaseModel):
    texto: str = Field(min_length=5)


class NotaOut(ORM):
    id: uuid.UUID
    texto: str
    hash_contenido: str
    creado_en: datetime
    autor: UsuarioOut


class AtencionResumen(ORM):
    id: uuid.UUID
    paciente_id: uuid.UUID
    consecutivo: int
    fecha_inicio: datetime
    tipo: str
    motivo_consulta: str
    estado: str
    profesional: UsuarioOut
    diagnosticos: list[DiagnosticoOut]


class AtencionOut(AtencionResumen):
    enfermedad_actual: str | None
    antecedentes: dict | None
    revision_sistemas: str | None
    signos_vitales: dict | None
    examen_fisico: str | None
    analisis: str | None
    plan: str | None
    cod_consulta_cups: str
    finalidad_tecnologia: str
    causa_motivo_atencion: str
    cod_servicio: int
    num_autorizacion: str | None
    valor_servicio: Decimal
    valor_pago_moderador: Decimal
    modalidad_grupo_servicio: str
    grupo_servicios: str
    fecha_egreso: datetime | None
    condicion_egreso: str | None
    dx_causa_muerte: str | None
    firmada_en: datetime | None
    supervisor: UsuarioOut | None = None
    hash_contenido: str | None
    bloque_ledger_id: int | None
    procedimientos: list[ProcedimientoOut]
    prescripciones: list[PrescripcionOut]
    notas_aclaratorias: list[NotaOut]
    alertas: list[str] = []


# ---------------- CIE-10 / IA ----------------
class CIE10Out(ORM):
    codigo: str
    descripcion: str
    sexo: str
    edad_minima: int
    edad_maxima: int


class SugerenciaIn(BaseModel):
    texto: str = Field(min_length=3, max_length=20000)
    paciente_id: uuid.UUID | None = None


class SugerenciaOut(BaseModel):
    codigo: str
    descripcion: str
    confianza: float
    justificacion: str
    fuente: str


class SugerenciasOut(BaseModel):
    proveedor: str
    sugerencias: list[SugerenciaOut]
    aviso: str = "Sugerencias de apoyo. La decisión diagnóstica es responsabilidad del profesional tratante."


# ---------------- RIPS ----------------
class RipsIn(BaseModel):
    num_factura: str = Field(min_length=1, max_length=20)
    atencion_ids: list[uuid.UUID] = Field(min_length=1)
    tipo_nota: Literal["NC", "ND", "NA"] | None = None
    num_nota: str | None = None


class RipsOut(BaseModel):
    valido: bool
    errores: list[str]
    rips: dict


# ---------------- Auditoría ----------------
class BloqueOut(ORM):
    id: int
    marca_tiempo: datetime
    usuario_id: str | None
    accion: str
    entidad: str
    entidad_id: str | None
    hash_datos: str
    hash_anterior: str
    hash: str
    ip_origen: str | None


Token.model_rebuild()
