"""Esquemas de los módulos hospitalarios."""
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.cie10 import codigo_valido, formatear_codigo


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


def _dx(v: str | None) -> str | None:
    if v is None or v == "":
        return None
    v = formatear_codigo(v)
    if not codigo_valido(v):
        raise ValueError("Código CIE-10 inválido")
    return v


class PersonaMin(ORM):
    id: uuid.UUID
    nombre_completo: str


class PacienteMin(PersonaMin):
    tipo_documento: str
    numero_documento: str
    fecha_nacimiento: date
    sexo: str
    alergias: str | None


# ---------------- Urgencias
class TriageIn(BaseModel):
    paciente_id: uuid.UUID
    motivo: str = Field(min_length=3)
    signos_vitales: dict | None = None
    nivel: int | None = Field(None, ge=1, le=5)  # si se omite se usa el sugerido
    observaciones: str | None = None
    llegada: datetime | None = None
    sede_id: uuid.UUID | None = None


class TriageOut(ORM):
    id: uuid.UUID
    paciente: PacienteMin
    llegada: datetime
    clasificado_en: datetime
    nivel: int
    nivel_sugerido: int | None
    motivo: str
    signos_vitales: dict | None
    observaciones: str | None
    estado: str
    inicio_atencion: datetime | None
    atencion_id: uuid.UUID | None
    minutos_espera: int | None = None
    tiempo_maximo: int | None = None
    vencido: bool = False
    razones: list[str] = []


# ---------------- Hospitalización
class CamaIn(BaseModel):
    codigo: str = Field(min_length=1, max_length=20)
    servicio: Literal["adultos", "pediatria", "obstetricia", "uci", "intermedios", "observacion", "neonatos"]
    sede_id: uuid.UUID | None = None


class CamaOut(ORM):
    id: uuid.UUID
    codigo: str
    servicio: str
    estado: str
    sede_id: uuid.UUID | None
    paciente: str | None = None
    hospitalizacion_id: uuid.UUID | None = None


class IngresoIn(BaseModel):
    paciente_id: uuid.UUID
    cama_id: uuid.UUID
    motivo: str = Field(min_length=3)
    dx_ingreso: str
    via_ingreso: str = "03"
    causa_motivo_atencion: str = "38"
    num_autorizacion: str | None = None
    valor_estancia_dia: Decimal = Decimal(0)

    @field_validator("dx_ingreso")
    @classmethod
    def validar_dx(cls, v):
        return _dx(v)


class EvolucionIn(BaseModel):
    tipo: Literal["medica", "enfermeria"]
    texto: str = Field(min_length=3)
    signos_vitales: dict | None = None


class EvolucionOut(ORM):
    id: uuid.UUID
    fecha: datetime
    tipo: str
    texto: str
    signos_vitales: dict | None
    hash_contenido: str
    autor: PersonaMin


class OrdenIn(BaseModel):
    tipo: Literal["medicamento", "dieta", "cuidado", "laboratorio", "imagen", "procedimiento", "interconsulta"]
    descripcion: str = Field(min_length=2)
    producto_id: uuid.UUID | None = None
    dosis: str | None = None
    via: str | None = None
    frecuencia: str | None = None
    confirmar_alertas: bool = False


class AdministracionIn(BaseModel):
    estado: Literal["administrado", "omitido"] = "administrado"
    dosis_administrada: str | None = None
    observacion: str | None = None


class AdministracionOut(ORM):
    id: uuid.UUID
    fecha: datetime
    estado: str
    dosis_administrada: str | None
    observacion: str | None
    enfermero_id: uuid.UUID


class OrdenOut(ORM):
    id: uuid.UUID
    fecha: datetime
    tipo: str
    descripcion: str
    producto_id: uuid.UUID | None
    dosis: str | None
    via: str | None
    frecuencia: str | None
    estado: str
    administraciones: list[AdministracionOut]


class BalanceIn(BaseModel):
    tipo: Literal["ingreso", "egreso"]
    via: str = Field(min_length=2)
    cantidad_ml: int = Field(gt=0, le=20000)


class BalanceOut(ORM):
    id: uuid.UUID
    fecha: datetime
    tipo: str
    via: str
    cantidad_ml: int


class EgresoIn(BaseModel):
    condicion_egreso: str = Field(pattern=r"^\d{2}$")
    dx_egreso: str
    dx_relacionados_egreso: list[str] = Field(default_factory=list, max_length=3)
    dx_complicacion: str | None = None
    dx_causa_muerte: str | None = None
    epicrisis: str = Field(min_length=20)

    @field_validator("dx_egreso", "dx_complicacion", "dx_causa_muerte")
    @classmethod
    def validar_dx(cls, v):
        return _dx(v)

    @field_validator("dx_relacionados_egreso")
    @classmethod
    def _rel(cls, v):
        return [_dx(x) for x in v if x]


class HospitalizacionOut(ORM):
    id: uuid.UUID
    paciente: PacienteMin
    cama: CamaOut | None
    medico: PersonaMin
    fecha_ingreso: datetime
    via_ingreso: str
    causa_motivo_atencion: str
    num_autorizacion: str | None
    motivo: str
    dx_ingreso: str
    estado: str
    fecha_egreso: datetime | None
    condicion_egreso: str | None
    dx_egreso: str | None
    dx_relacionados_egreso: list | None
    dx_causa_muerte: str | None
    epicrisis: str | None
    hash_epicrisis: str | None
    valor_estancia_dia: Decimal


class HospitalizacionDetalle(HospitalizacionOut):
    evoluciones: list[EvolucionOut]
    ordenes: list[OrdenOut]
    balances: list[BalanceOut]
    balance_24h: dict = {}
    alertas: list[str] = []


# ---------------- Farmacia
class ProductoIn(BaseModel):
    nombre: str = Field(min_length=2)
    cum: str | None = None
    concentracion: str | None = None
    forma_farmaceutica: str | None = None
    unidad: str = "unidad"
    tipo: Literal["medicamento", "dispositivo", "insumo"] = "medicamento"
    stock_minimo: int = Field(0, ge=0)
    precio_unitario: Decimal = Field(Decimal(0), ge=0)
    cadena_frio: bool = False
    controlado: bool = False
    activo: bool = True


class LoteOut(ORM):
    id: uuid.UUID
    numero: str
    vencimiento: date
    registro_invima: str | None
    cantidad: int


class ProductoOut(ProductoIn, ORM):
    id: uuid.UUID
    stock: int = 0
    lotes: list[LoteOut] = []


class EntradaIn(BaseModel):
    producto_id: uuid.UUID
    lote: str = Field(min_length=1)
    vencimiento: date
    cantidad: int = Field(gt=0)
    registro_invima: str | None = None
    motivo: str | None = "Compra"


class AjusteIn(BaseModel):
    lote_id: uuid.UUID
    cantidad: int  # positiva o negativa
    motivo: str = Field(min_length=3)


class DispensarIn(BaseModel):
    producto_id: uuid.UUID
    cantidad: int = Field(gt=0)
    prescripcion_id: uuid.UUID | None = None
    orden_id: uuid.UUID | None = None


class MovimientoOut(ORM):
    id: uuid.UUID
    fecha: datetime
    tipo: str
    cantidad: int
    lote_id: uuid.UUID | None
    motivo: str | None
    paciente_id: uuid.UUID | None


# ---------------- Laboratorio e imágenes
class OrdenServicioIn(BaseModel):
    paciente_id: uuid.UUID
    atencion_id: uuid.UUID | None = None
    hospitalizacion_id: uuid.UUID | None = None
    tipo: Literal["laboratorio", "imagen"]
    cod_cups: str = Field(pattern=r"^[0-9A-Za-z]{6}$")
    descripcion: str = Field(min_length=2)
    prioridad: Literal["rutina", "urgente"] = "rutina"
    indicaciones: str | None = None


class ResultadoItem(BaseModel):
    analito: str
    valor: str
    unidad: str | None = None
    referencia: str | None = None
    anormal: bool | None = None


class ResultadoIn(BaseModel):
    resultados: list[ResultadoItem] = []
    informe: str | None = None


class OrdenServicioOut(ORM):
    id: uuid.UUID
    paciente: PacienteMin
    atencion_id: uuid.UUID | None
    hospitalizacion_id: uuid.UUID | None
    tipo: str
    cod_cups: str
    descripcion: str
    prioridad: str
    indicaciones: str | None
    estado: str
    fecha: datetime
    fecha_toma: datetime | None
    resultados: list | None
    informe: str | None
    fecha_resultado: datetime | None
    hash_resultado: str | None


# ---------------- Consentimientos
class ConsentimientoIn(BaseModel):
    paciente_id: uuid.UUID
    atencion_id: uuid.UUID | None = None
    plantilla: str
    titulo: str = Field(min_length=3)
    texto: str = Field(min_length=20)
    decision: Literal["acepta", "rechaza", "revoca"] = "acepta"
    firmante_nombre: str = Field(min_length=3)
    firmante_documento: str = Field(min_length=3)
    parentesco: str = "paciente"
    firma_imagen: str = Field(min_length=100, max_length=600_000)

    @field_validator("firma_imagen")
    @classmethod
    def _png(cls, v: str) -> str:
        if not v.startswith("data:image/png;base64,"):
            raise ValueError("La firma debe ser una imagen PNG")
        return v


class ConsentimientoOut(ORM):
    id: uuid.UUID
    paciente_id: uuid.UUID
    atencion_id: uuid.UUID | None
    plantilla: str
    titulo: str
    texto: str
    decision: str
    firmante_nombre: str
    firmante_documento: str
    parentesco: str
    fecha: datetime
    hash_contenido: str
    profesional: PersonaMin
