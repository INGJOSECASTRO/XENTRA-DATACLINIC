"""Tablas de los módulos de gestión hospitalaria.

Sedes · Catálogos · Agenda · Facturación · Urgencias/Triage · Hospitalización ·
Farmacia/Inventario · Laboratorio/Imágenes · Consentimientos · Anclaje del ledger.
"""
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models import JSONType, Paciente, Usuario, ahora_utc


def _id() -> Mapped[uuid.UUID]:
    return mapped_column(Uuid, primary_key=True, default=uuid.uuid4)


# ----------------------------------------------------------------------------- Sedes y catálogos
class Sede(Base):
    __tablename__ = "sedes"
    id: Mapped[uuid.UUID] = _id()
    nombre: Mapped[str] = mapped_column(String(120))
    cod_habilitacion: Mapped[str] = mapped_column(String(12))  # código REPS de la sede
    cod_municipio: Mapped[str] = mapped_column(String(5), default="11001")
    direccion: Mapped[str | None] = mapped_column(String(200))
    telefono: Mapped[str | None] = mapped_column(String(30))
    activa: Mapped[bool] = mapped_column(Boolean, default=True)


class Catalogo(Base):
    """Tablas de referencia (CUPS, CUM, DIVIPOLA, EAPB, tablas RIPS de SISPRO...)."""

    __tablename__ = "catalogos"
    __table_args__ = (UniqueConstraint("tipo", "codigo", name="uq_catalogo_tipo_codigo"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tipo: Mapped[str] = mapped_column(String(40), index=True)
    codigo: Mapped[str] = mapped_column(String(30))
    descripcion: Mapped[str] = mapped_column(String(300))
    texto_busqueda: Mapped[str] = mapped_column(Text, default="")
    datos: Mapped[dict | None] = mapped_column(JSONType)  # valores extra (precio, concentración...)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


# ----------------------------------------------------------------------------- Agenda
class Cita(Base):
    __tablename__ = "citas"
    id: Mapped[uuid.UUID] = _id()
    paciente_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pacientes.id"), index=True)
    profesional_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuarios.id"), index=True)
    sede_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sedes.id"))
    inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    duracion_min: Mapped[int] = mapped_column(Integer, default=20)
    cod_cups: Mapped[str] = mapped_column(String(6), default="890201")
    modalidad: Mapped[str] = mapped_column(String(15), default="presencial")  # presencial | telemedicina
    estado: Mapped[str] = mapped_column(String(15), default="programada")
    # programada | confirmada | en_sala | atendida | cancelada | no_asistio
    motivo: Mapped[str | None] = mapped_column(Text)
    sala_virtual: Mapped[str | None] = mapped_column(String(300))
    fecha_solicitud: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)
    fecha_deseada: Mapped[date | None] = mapped_column(Date)  # para indicador de oportunidad
    motivo_cancelacion: Mapped[str | None] = mapped_column(String(200))
    num_autorizacion: Mapped[str | None] = mapped_column(String(30))
    atencion_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("atenciones.id"))
    creado_por: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuarios.id"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)

    paciente: Mapped[Paciente] = relationship(foreign_keys=[paciente_id])
    profesional: Mapped[Usuario] = relationship(foreign_keys=[profesional_id])


# ----------------------------------------------------------------------------- Facturación
class Factura(Base):
    __tablename__ = "facturas"
    __table_args__ = (UniqueConstraint("prefijo", "consecutivo", name="uq_factura_numero"),)
    id: Mapped[uuid.UUID] = _id()
    prefijo: Mapped[str] = mapped_column(String(10), default="FEV")
    consecutivo: Mapped[int | None] = mapped_column(Integer)  # se asigna al emitir
    fecha_emision: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    tipo_pagador: Mapped[str] = mapped_column(String(15), default="eps")  # eps | particular | soat | arl | otro
    cod_eapb: Mapped[str | None] = mapped_column(String(10))
    nit_pagador: Mapped[str | None] = mapped_column(String(20))
    nombre_pagador: Mapped[str] = mapped_column(String(200))
    modalidad_pago: Mapped[str] = mapped_column(String(20), default="evento")  # evento | capitacion | pgp
    num_contrato: Mapped[str | None] = mapped_column(String(40))
    subtotal: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)
    pagos_moderadores: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)
    estado: Mapped[str] = mapped_column(String(15), default="borrador")
    # borrador | emitida | validada | rechazada | anulada
    cufe: Mapped[str | None] = mapped_column(String(120))
    cuv: Mapped[str | None] = mapped_column(String(120))
    respuesta_dian: Mapped[dict | None] = mapped_column(JSONType)
    respuesta_muv: Mapped[dict | None] = mapped_column(JSONType)
    rips: Mapped[dict | None] = mapped_column(JSONType)
    hallazgos_auditoria: Mapped[list | None] = mapped_column(JSONType)
    creado_por: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuarios.id"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)

    items: Mapped[list["FacturaItem"]] = relationship(back_populates="factura", cascade="all, delete-orphan")

    @property
    def numero(self) -> str | None:
        return f"{self.prefijo}{self.consecutivo}" if self.consecutivo else None


class FacturaItem(Base):
    __tablename__ = "factura_items"
    id: Mapped[uuid.UUID] = _id()
    factura_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("facturas.id"), index=True)
    atencion_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("atenciones.id"), index=True)
    hospitalizacion_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("hospitalizaciones.id"))
    tipo: Mapped[str] = mapped_column(String(20), default="consulta")
    codigo: Mapped[str] = mapped_column(String(20))
    descripcion: Mapped[str] = mapped_column(String(255))
    cantidad: Mapped[int] = mapped_column(Integer, default=1)
    valor_unitario: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)
    valor_total: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)

    factura: Mapped[Factura] = relationship(back_populates="items")


# ----------------------------------------------------------------------------- Urgencias
class Triage(Base):
    """Clasificación de urgencias (Resolución 5596 de 2015): categorías I a V."""

    __tablename__ = "triages"
    id: Mapped[uuid.UUID] = _id()
    paciente_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pacientes.id"), index=True)
    sede_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sedes.id"))
    llegada: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)
    clasificado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)
    nivel: Mapped[int] = mapped_column(Integer)
    nivel_sugerido: Mapped[int | None] = mapped_column(Integer)
    motivo: Mapped[str] = mapped_column(Text)
    signos_vitales: Mapped[dict | None] = mapped_column(JSONType)
    observaciones: Mapped[str | None] = mapped_column(Text)
    estado: Mapped[str] = mapped_column(String(15), default="en_espera")  # en_espera | en_atencion | finalizado
    inicio_atencion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    atencion_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("atenciones.id"))
    clasificado_por: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuarios.id"))

    paciente: Mapped[Paciente] = relationship()


# ----------------------------------------------------------------------------- Hospitalización
class Cama(Base):
    __tablename__ = "camas"
    id: Mapped[uuid.UUID] = _id()
    sede_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sedes.id"))
    codigo: Mapped[str] = mapped_column(String(20), unique=True)
    servicio: Mapped[str] = mapped_column(String(40))  # adultos | pediatria | obstetricia | uci | observacion
    estado: Mapped[str] = mapped_column(String(15), default="disponible")  # disponible | ocupada | mantenimiento


class Hospitalizacion(Base):
    __tablename__ = "hospitalizaciones"
    id: Mapped[uuid.UUID] = _id()
    paciente_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pacientes.id"), index=True)
    cama_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("camas.id"))
    medico_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuarios.id"))
    fecha_ingreso: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)
    via_ingreso: Mapped[str] = mapped_column(String(2), default="03")
    causa_motivo_atencion: Mapped[str] = mapped_column(String(2), default="38")
    num_autorizacion: Mapped[str | None] = mapped_column(String(30))
    motivo: Mapped[str] = mapped_column(Text)
    dx_ingreso: Mapped[str] = mapped_column(String(4))
    estado: Mapped[str] = mapped_column(String(10), default="activa")  # activa | egresada
    fecha_egreso: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    condicion_egreso: Mapped[str | None] = mapped_column(String(2))
    dx_egreso: Mapped[str | None] = mapped_column(String(4))
    dx_relacionados_egreso: Mapped[list | None] = mapped_column(JSONType)
    dx_complicacion: Mapped[str | None] = mapped_column(String(4))
    dx_causa_muerte: Mapped[str | None] = mapped_column(String(4))
    epicrisis: Mapped[str | None] = mapped_column(Text)
    hash_epicrisis: Mapped[str | None] = mapped_column(String(64))
    valor_estancia_dia: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)

    paciente: Mapped[Paciente] = relationship()
    cama: Mapped[Cama | None] = relationship()
    medico: Mapped[Usuario] = relationship()
    evoluciones: Mapped[list["Evolucion"]] = relationship(order_by="Evolucion.fecha")
    ordenes: Mapped[list["OrdenMedica"]] = relationship(order_by="OrdenMedica.fecha")
    balances: Mapped[list["BalanceLiquidos"]] = relationship(order_by="BalanceLiquidos.fecha")


class Evolucion(Base):
    """Evolución médica o nota de enfermería. Solo inserción (inmutable)."""

    __tablename__ = "evoluciones"
    id: Mapped[uuid.UUID] = _id()
    hospitalizacion_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitalizaciones.id"), index=True)
    autor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuarios.id"))
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)
    tipo: Mapped[str] = mapped_column(String(15))  # medica | enfermeria
    texto: Mapped[str] = mapped_column(Text)
    signos_vitales: Mapped[dict | None] = mapped_column(JSONType)
    hash_contenido: Mapped[str] = mapped_column(String(64))

    autor: Mapped[Usuario] = relationship()


class OrdenMedica(Base):
    __tablename__ = "ordenes_medicas"
    id: Mapped[uuid.UUID] = _id()
    hospitalizacion_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitalizaciones.id"), index=True)
    autor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuarios.id"))
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)
    tipo: Mapped[str] = mapped_column(String(20))  # medicamento | dieta | cuidado | laboratorio | imagen | procedimiento
    descripcion: Mapped[str] = mapped_column(Text)
    producto_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("productos.id"))
    dosis: Mapped[str | None] = mapped_column(String(100))
    via: Mapped[str | None] = mapped_column(String(40))
    frecuencia: Mapped[str | None] = mapped_column(String(60))
    estado: Mapped[str] = mapped_column(String(15), default="activa")  # activa | suspendida | cumplida
    suspendida_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    suspendida_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))

    administraciones: Mapped[list["AdministracionMedicamento"]] = relationship(order_by="AdministracionMedicamento.fecha")


class AdministracionMedicamento(Base):
    """Kárdex de enfermería."""

    __tablename__ = "administraciones_medicamento"
    id: Mapped[uuid.UUID] = _id()
    orden_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ordenes_medicas.id"), index=True)
    enfermero_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuarios.id"))
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)
    estado: Mapped[str] = mapped_column(String(15), default="administrado")  # administrado | omitido
    dosis_administrada: Mapped[str | None] = mapped_column(String(100))
    observacion: Mapped[str | None] = mapped_column(Text)


class BalanceLiquidos(Base):
    __tablename__ = "balance_liquidos"
    id: Mapped[uuid.UUID] = _id()
    hospitalizacion_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitalizaciones.id"), index=True)
    registrado_por: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuarios.id"))
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)
    tipo: Mapped[str] = mapped_column(String(10))  # ingreso | egreso
    via: Mapped[str] = mapped_column(String(40))  # oral, intravenosa, sonda / orina, drenaje, vómito, deposición
    cantidad_ml: Mapped[int] = mapped_column(Integer)


# ----------------------------------------------------------------------------- Farmacia
class Producto(Base):
    __tablename__ = "productos"
    id: Mapped[uuid.UUID] = _id()
    nombre: Mapped[str] = mapped_column(String(200), index=True)
    cum: Mapped[str | None] = mapped_column(String(30))
    concentracion: Mapped[str | None] = mapped_column(String(60))
    forma_farmaceutica: Mapped[str | None] = mapped_column(String(60))
    unidad: Mapped[str] = mapped_column(String(30), default="unidad")
    tipo: Mapped[str] = mapped_column(String(20), default="medicamento")  # medicamento | dispositivo | insumo
    stock_minimo: Mapped[int] = mapped_column(Integer, default=0)
    precio_unitario: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)
    cadena_frio: Mapped[bool] = mapped_column(Boolean, default=False)
    controlado: Mapped[bool] = mapped_column(Boolean, default=False)  # medicamento de control especial (FNE)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)

    lotes: Mapped[list["Lote"]] = relationship(order_by="Lote.vencimiento")


class Lote(Base):
    __tablename__ = "lotes"
    id: Mapped[uuid.UUID] = _id()
    producto_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("productos.id"), index=True)
    numero: Mapped[str] = mapped_column(String(40))
    vencimiento: Mapped[date] = mapped_column(Date)
    registro_invima: Mapped[str | None] = mapped_column(String(40))
    cantidad: Mapped[int] = mapped_column(Integer, default=0)


class MovimientoInventario(Base):
    __tablename__ = "movimientos_inventario"
    id: Mapped[uuid.UUID] = _id()
    producto_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("productos.id"), index=True)
    lote_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("lotes.id"))
    tipo: Mapped[str] = mapped_column(String(15))  # entrada | dispensacion | ajuste | devolucion
    cantidad: Mapped[int] = mapped_column(Integer)  # positiva entra, negativa sale
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)
    usuario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuarios.id"))
    paciente_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("pacientes.id"))
    prescripcion_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("prescripciones.id"))
    orden_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ordenes_medicas.id"))
    motivo: Mapped[str | None] = mapped_column(String(200))

    producto: Mapped["Producto"] = relationship()
    lote: Mapped["Lote | None"] = relationship()
    paciente: Mapped[Paciente | None] = relationship()
    usuario: Mapped[Usuario] = relationship()


# ----------------------------------------------------------------------------- Laboratorio e imágenes
class OrdenServicio(Base):
    __tablename__ = "ordenes_servicio"
    id: Mapped[uuid.UUID] = _id()
    paciente_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pacientes.id"), index=True)
    atencion_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("atenciones.id"))
    hospitalizacion_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("hospitalizaciones.id"))
    tipo: Mapped[str] = mapped_column(String(15))  # laboratorio | imagen
    cod_cups: Mapped[str] = mapped_column(String(6))
    descripcion: Mapped[str] = mapped_column(String(255))
    prioridad: Mapped[str] = mapped_column(String(10), default="rutina")  # rutina | urgente
    indicaciones: Mapped[str | None] = mapped_column(Text)
    estado: Mapped[str] = mapped_column(String(15), default="ordenada")  # ordenada | tomada | resultado | validada
    ordenado_por: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuarios.id"))
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)
    fecha_toma: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Resultado
    resultados: Mapped[list | None] = mapped_column(JSONType)  # [{analito, valor, unidad, referencia, anormal}]
    informe: Mapped[str | None] = mapped_column(Text)
    validado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    fecha_resultado: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    hash_resultado: Mapped[str | None] = mapped_column(String(64))

    paciente: Mapped[Paciente] = relationship()


# ----------------------------------------------------------------------------- Consentimientos
class Consentimiento(Base):
    __tablename__ = "consentimientos"
    id: Mapped[uuid.UUID] = _id()
    paciente_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pacientes.id"), index=True)
    atencion_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("atenciones.id"))
    plantilla: Mapped[str] = mapped_column(String(40))
    titulo: Mapped[str] = mapped_column(String(200))
    texto: Mapped[str] = mapped_column(Text)
    decision: Mapped[str] = mapped_column(String(10), default="acepta")  # acepta | rechaza | revoca
    firmante_nombre: Mapped[str] = mapped_column(String(150))
    firmante_documento: Mapped[str] = mapped_column(String(30))
    parentesco: Mapped[str] = mapped_column(String(40), default="paciente")
    firma_imagen: Mapped[str] = mapped_column(Text)  # data URL PNG de la firma manuscrita
    profesional_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuarios.id"))
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)
    hash_contenido: Mapped[str] = mapped_column(String(64))

    profesional: Mapped[Usuario] = relationship()


# ----------------------------------------------------------------------------- Anclaje del ledger
class AnclajeLedger(Base):
    __tablename__ = "anclajes_ledger"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)
    bloque_id: Mapped[int] = mapped_column(Integer)
    hash_raiz: Mapped[str] = mapped_column(String(64))
    proveedor: Mapped[str] = mapped_column(String(40))  # opentimestamps | local
    estado: Mapped[str] = mapped_column(String(15))  # enviado | fallido | local
    comprobante: Mapped[str | None] = mapped_column(Text)  # base64
    detalle: Mapped[str | None] = mapped_column(Text)


# ----------------------------------------------------------------------------- RDA (Resolución 1888 de 2025)
class RdaEnvio(Base):
    """Resumen Digital de Atención generado y su estado de transmisión a la IHCE (cola con reintentos)."""

    __tablename__ = "rda_envios"
    id: Mapped[uuid.UUID] = _id()
    tipo: Mapped[str] = mapped_column(String(20), index=True)  # consulta | urgencias | hospitalizacion | paciente
    entidad_id: Mapped[str] = mapped_column(String(36), index=True)
    paciente_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pacientes.id"), index=True)
    generado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)
    bundle: Mapped[dict] = mapped_column(JSONType)
    hash_bundle: Mapped[str] = mapped_column(String(64))
    estado: Mapped[str] = mapped_column(String(15), default="pendiente", index=True)  # pendiente|enviado|error|simulado
    intentos: Mapped[int] = mapped_column(Integer, default=0)
    ultimo_intento: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    respuesta: Mapped[dict | None] = mapped_column(JSONType)
    errores_validacion: Mapped[list | None] = mapped_column(JSONType)


# ----------------------------------------------------------------------------- Inteligencia de negocio
class ReporteGuardado(Base):
    __tablename__ = "reportes_guardados"
    id: Mapped[uuid.UUID] = _id()
    nombre: Mapped[str] = mapped_column(String(150))
    descripcion: Mapped[str | None] = mapped_column(Text)
    definicion: Mapped[dict] = mapped_column(JSONType)  # dataset, dimensiones, medidas, filtros, grafico
    roles: Mapped[list] = mapped_column(JSONType, default=list)  # roles que lo ven (vacío = solo el autor y admin)
    creado_por: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuarios.id"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)


# ----------------------------------------------------------------------------- Módulos dinámicos (sin programar)
class ModuloDinamico(Base):
    """Módulo creado por el administrador: formulario con campos tipados, roles y opción de sellado."""

    __tablename__ = "modulos_dinamicos"
    id: Mapped[uuid.UUID] = _id()
    clave: Mapped[str] = mapped_column(String(40), unique=True)
    nombre: Mapped[str] = mapped_column(String(120))
    descripcion: Mapped[str | None] = mapped_column(Text)
    categoria: Mapped[str] = mapped_column(String(40), default="asistencial")  # asistencial | administrativo | calidad
    campos: Mapped[list] = mapped_column(JSONType)  # [{clave, etiqueta, tipo, requerido, opciones, min, max}]
    roles_lectura: Mapped[list] = mapped_column(JSONType, default=list)
    roles_escritura: Mapped[list] = mapped_column(JSONType, default=list)
    por_paciente: Mapped[bool] = mapped_column(Boolean, default=True)
    sellar_al_guardar: Mapped[bool] = mapped_column(Boolean, default=False)  # registro inalterable (dato clínico)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    creado_por: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuarios.id"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)


class RegistroModulo(Base):
    __tablename__ = "registros_modulo"
    id: Mapped[uuid.UUID] = _id()
    modulo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("modulos_dinamicos.id"), index=True)
    version_modulo: Mapped[int] = mapped_column(Integer, default=1)
    paciente_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("pacientes.id"), index=True)
    datos: Mapped[dict] = mapped_column(JSONType)
    sellado: Mapped[bool] = mapped_column(Boolean, default=False)
    hash_contenido: Mapped[str] = mapped_column(String(64))
    autor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuarios.id"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)

    autor: Mapped[Usuario] = relationship()


# ----------------------------------------------------------------------------- Soporte y continuidad
class Ticket(Base):
    """Mesa de ayuda interna con acuerdos de nivel de servicio (ANS/SLA)."""

    __tablename__ = "tickets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    titulo: Mapped[str] = mapped_column(String(200))
    descripcion: Mapped[str] = mapped_column(Text)
    categoria: Mapped[str] = mapped_column(String(30), default="incidente")  # incidente | solicitud | mejora | seguridad
    prioridad: Mapped[str] = mapped_column(String(10), default="media")  # critica | alta | media | baja
    modulo: Mapped[str | None] = mapped_column(String(60))
    codigo_error: Mapped[str | None] = mapped_column(String(40))  # ID de error que muestra la pantalla
    estado: Mapped[str] = mapped_column(String(15), default="abierto")  # abierto | en_proceso | resuelto | cerrado
    creado_por: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuarios.id"))
    asignado_a: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)
    vence_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resuelto_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    solucion: Mapped[str | None] = mapped_column(Text)
    comentarios: Mapped[list] = mapped_column(JSONType, default=list)

    autor: Mapped[Usuario] = relationship(foreign_keys=[creado_por])


class AvisoSistema(Base):
    """Avisos visibles para todos: mantenimientos programados, contingencias, novedades."""

    __tablename__ = "avisos_sistema"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nivel: Mapped[str] = mapped_column(String(10), default="info")  # info | aviso | critico
    mensaje: Mapped[str] = mapped_column(String(500))
    desde: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)
    hasta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    creado_por: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuarios.id"))
