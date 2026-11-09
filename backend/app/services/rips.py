"""Generación de RIPS en JSON según la Resolución 2275 de 2023 (Ministerio de Salud).

Desde 2024 los RIPS son SOPORTE de la Factura Electrónica de Venta (FEV) en salud y se
envían al Mecanismo Único de Validación (MUV) del Ministerio, que devuelve el
Código Único de Validación (CUV).

Servicios generados: consultas, procedimientos, urgencias, hospitalizacion y medicamentos.
(recienNacidos y otrosServicios: ver docs/05-rips.md)

IMPORTANTE: los códigos de las tablas de referencia (finalidad, causa, modalidad,
grupo de servicio, etc.) deben validarse contra las tablas vigentes publicadas en
SISPRO (web.sispro.gov.co -> Tablas de referencia), porque el Ministerio las actualiza.
"""
from collections import OrderedDict
from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.models import Atencion
from app.services.cie10 import codigo_valido
from app.services.ledger import a_utc

TZ = ZoneInfo(settings.ZONA_HORARIA)


def _fecha_hora(dt: datetime | None) -> str | None:
    return a_utc(dt).astimezone(TZ).strftime("%Y-%m-%d %H:%M") if dt else None


def _num(valor) -> float | int:
    v = float(valor or 0)
    return int(v) if v.is_integer() else round(v, 2)


def edad_en(fecha_nacimiento: date, en: date | None = None) -> int:
    en = en or date.today()
    return en.year - fecha_nacimiento.year - ((en.month, en.day) < (fecha_nacimiento.month, fecha_nacimiento.day))


class _Usuario:
    def __init__(self, paciente):
        self.paciente = paciente
        self.servicios: dict[str, list] = {}

    def agregar(self, tipo: str, registro: dict) -> None:
        lista = self.servicios.setdefault(tipo, [])
        registro["consecutivo"] = len(lista) + 1
        lista.append(registro)


def generar_rips(
    atenciones: list[Atencion],
    num_factura: str,
    tipo_nota: str | None = None,
    num_nota: str | None = None,
    hospitalizaciones: list | None = None,
    medicamentos: list | None = None,
) -> tuple[dict, list[str]]:
    """Devuelve (json_rips, lista_de_errores). Si hay errores, NO debe enviarse al MUV.

    medicamentos: movimientos de inventario de tipo 'dispensacion' (con producto y lote).
    """
    errores: list[str] = []
    if not num_factura:
        errores.append("El número de factura es obligatorio")
    usuarios: "OrderedDict[str, _Usuario]" = OrderedDict()

    def usuario_de(paciente) -> _Usuario:
        return usuarios.setdefault(str(paciente.id), _Usuario(paciente))

    def validar_dx(codigo: str | None, contexto: str, obligatorio: bool = True) -> None:
        if not codigo:
            if obligatorio:
                errores.append(f"{contexto}: falta diagnóstico principal")
        elif not codigo_valido(codigo):
            errores.append(f"{contexto}: código CIE-10 inválido '{codigo}'")

    # --- Atenciones: consultas, procedimientos y urgencias ---
    for a in sorted(atenciones, key=lambda x: x.fecha_inicio):
        p, prof = a.paciente, a.profesional
        contexto = f"Atención {a.consecutivo} de {p.numero_documento}"
        if a.estado != "firmada":
            errores.append(f"{contexto}: no está firmada; solo se facturan atenciones cerradas")
        dx = sorted(a.diagnosticos, key=lambda d: d.orden)
        principal = dx[0].codigo_cie10 if dx else None
        validar_dx(principal, contexto)
        for d in dx[1:]:
            validar_dx(d.codigo_cie10, contexto)
        rel = [d.codigo_cie10 for d in dx[1:4]] + [None, None, None]
        u = usuario_de(p)
        u.agregar("consultas", {
            "codPrestador": settings.PRESTADOR_COD_HABILITACION,
            "fechaInicioAtencion": _fecha_hora(a.fecha_inicio),
            "numAutorizacion": a.num_autorizacion,
            "codConsulta": a.cod_consulta_cups,
            "modalidadGrupoServicioTecSal": a.modalidad_grupo_servicio,
            "grupoServicios": a.grupo_servicios,
            "codServicio": a.cod_servicio,
            "finalidadTecnologiaSalud": a.finalidad_tecnologia,
            "causaMotivoAtencion": a.causa_motivo_atencion,
            "codDiagnosticoPrincipal": principal,
            "codDiagnosticoRelacionado1": rel[0],
            "codDiagnosticoRelacionado2": rel[1],
            "codDiagnosticoRelacionado3": rel[2],
            "tipoDiagnosticoPrincipal": dx[0].tipo_diagnostico if dx else None,
            "tipoDocumentoIdentificacion": prof.tipo_documento,
            "numDocumentoIdentificacion": prof.numero_documento,
            "vrServicio": _num(a.valor_servicio),
            "conceptoRecaudo": a.concepto_recaudo,
            "valorPagoModerador": _num(a.valor_pago_moderador),
            "numFEVPagoModerador": None,
        })
        for proc in a.procedimientos:
            u.agregar("procedimientos", {
                "codPrestador": settings.PRESTADOR_COD_HABILITACION,
                "fechaInicioAtencion": _fecha_hora(a.fecha_inicio),
                "idMIPRES": None,
                "numAutorizacion": a.num_autorizacion,
                "codProcedimiento": proc.cod_cups,
                "viaIngresoServicioSalud": proc.via_ingreso,
                "modalidadGrupoServicioTecSal": a.modalidad_grupo_servicio,
                "grupoServicios": a.grupo_servicios,
                "codServicio": a.cod_servicio,
                "finalidadTecnologiaSalud": proc.finalidad_tecnologia,
                "tipoDocumentoIdentificacion": prof.tipo_documento,
                "numDocumentoIdentificacion": prof.numero_documento,
                "codDiagnosticoPrincipal": principal,
                "codDiagnosticoRelacionado": rel[0],
                "codComplicacion": None,
                "vrServicio": _num(proc.valor),
                "conceptoRecaudo": a.concepto_recaudo,
                "valorPagoModerador": 0,
                "numFEVPagoModerador": None,
            })
        if a.tipo == "urgencias" and a.fecha_egreso:
            if not a.condicion_egreso:
                errores.append(f"{contexto}: urgencias sin condición de egreso")
            if a.condicion_egreso == "02" and not a.dx_causa_muerte:
                errores.append(f"{contexto}: paciente fallecido sin diagnóstico de causa de muerte")
            u.agregar("urgencias", {
                "codPrestador": settings.PRESTADOR_COD_HABILITACION,
                "fechaInicioAtencion": _fecha_hora(a.fecha_inicio),
                "causaMotivoAtencion": a.causa_motivo_atencion,
                "codDiagnosticoPrincipal": principal,
                "codDiagnosticoPrincipalE": principal,
                "codDiagnosticoRelacionadoE1": rel[0],
                "codDiagnosticoRelacionadoE2": rel[1],
                "codDiagnosticoRelacionadoE3": rel[2],
                "condicionDestinoUsuarioEgreso": a.condicion_egreso,
                "codDiagnosticoCausaMuerte": a.dx_causa_muerte,
                "fechaEgreso": _fecha_hora(a.fecha_egreso),
            })

    # --- Hospitalizaciones ---
    for h in hospitalizaciones or []:
        contexto = f"Hospitalización de {h.paciente.numero_documento}"
        if h.estado != "egresada":
            errores.append(f"{contexto}: el paciente aún no tiene egreso")
        validar_dx(h.dx_ingreso, contexto)
        validar_dx(h.dx_egreso, contexto + " (egreso)")
        if h.condicion_egreso == "02" and not h.dx_causa_muerte:
            errores.append(f"{contexto}: fallecido sin diagnóstico de causa de muerte")
        rel = list(h.dx_relacionados_egreso or []) + [None, None, None]
        usuario_de(h.paciente).agregar("hospitalizacion", {
            "codPrestador": settings.PRESTADOR_COD_HABILITACION,
            "viaIngresoServicioSalud": h.via_ingreso,
            "fechaInicioAtencion": _fecha_hora(h.fecha_ingreso),
            "numAutorizacion": h.num_autorizacion,
            "causaMotivoAtencion": h.causa_motivo_atencion,
            "codDiagnosticoPrincipal": h.dx_ingreso,
            "codDiagnosticoPrincipalE": h.dx_egreso,
            "codDiagnosticoRelacionadoE1": rel[0],
            "codDiagnosticoRelacionadoE2": rel[1],
            "codDiagnosticoRelacionadoE3": rel[2],
            "codComplicacion": h.dx_complicacion,
            "condicionDestinoUsuarioEgreso": h.condicion_egreso,
            "codDiagnosticoCausaMuerte": h.dx_causa_muerte,
            "fechaEgreso": _fecha_hora(h.fecha_egreso),
        })

    # --- Medicamentos dispensados ---
    for m in medicamentos or []:
        prod = m.producto
        cantidad = abs(m.cantidad)
        if not prod.cum:
            errores.append(f"Medicamento '{prod.nombre}': falta el código CUM")
        usuario_de(m.paciente).agregar("medicamentos", {
            "codPrestador": settings.PRESTADOR_COD_HABILITACION,
            "numAutorizacion": None,
            "idMIPRES": None,
            "fechaDispensAdmon": _fecha_hora(m.fecha),
            "codDiagnosticoPrincipal": m.dx_principal,
            "codDiagnosticoRelacionado": None,
            "tipoMedicamento": "01",
            "codTecnologiaSalud": prod.cum,
            "nomTecnologiaSalud": prod.nombre,
            "concentracionMedicamento": prod.concentracion,
            "unidadMedida": prod.unidad,
            "formaFarmaceutica": prod.forma_farmaceutica,
            "unidadMinDispensa": prod.unidad,
            "cantidadMedicamento": cantidad,
            "diasTratamiento": m.dias_tratamiento,
            "tipoDocumentoIdentificacion": m.usuario.tipo_documento,
            "numDocumentoIdentificacion": m.usuario.numero_documento,
            "vrUnitMedicamento": _num(prod.precio_unitario),
            "vrServicio": _num(prod.precio_unitario * cantidad),
            "conceptoRecaudo": "05",
            "valorPagoModerador": 0,
            "numFEVPagoModerador": None,
        })

    salida_usuarios = []
    for consecutivo, u in enumerate(usuarios.values(), start=1):
        p = u.paciente
        if p.sexo not in ("H", "M", "I"):
            errores.append(f"Paciente {p.numero_documento}: sexo inválido '{p.sexo}' (H, M o I)")
        if len(p.cod_municipio_residencia or "") != 5:
            errores.append(f"Paciente {p.numero_documento}: código de municipio DIVIPOLA debe tener 5 dígitos")
        salida_usuarios.append({
            "tipoDocumentoIdentificacion": p.tipo_documento,
            "numDocumentoIdentificacion": p.numero_documento,
            "tipoUsuario": p.tipo_usuario,
            "fechaNacimiento": p.fecha_nacimiento.isoformat(),
            "codSexo": p.sexo,
            "codPaisResidencia": p.cod_pais_residencia,
            "codMunicipioResidencia": p.cod_municipio_residencia,
            "codZonaTerritorialResidencia": p.zona_territorial,
            "incapacidad": "NO",
            "consecutivo": consecutivo,
            "codPaisOrigen": "170",
            "servicios": u.servicios,
        })

    rips = {
        "numDocumentoIdObligado": settings.PRESTADOR_NIT,
        "numFactura": num_factura,
        "tipoNota": tipo_nota,
        "numNota": num_nota,
        "usuarios": salida_usuarios,
    }
    return rips, errores
