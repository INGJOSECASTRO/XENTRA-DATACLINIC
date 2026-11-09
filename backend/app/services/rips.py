"""Generación de RIPS en JSON según la Resolución 2275 de 2023 (Ministerio de Salud).

Desde 2024 los RIPS son SOPORTE de la Factura Electrónica de Venta (FEV) en salud y se
envían al Mecanismo Único de Validación (MUV) del Ministerio, que devuelve el
Código Único de Validación (CUV).

Estructura generada:
{
  numDocumentoIdObligado, numFactura, tipoNota, numNota,
  usuarios: [ { datos del usuario..., servicios: { consultas: [...], procedimientos: [...] } } ]
}

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


def _fecha_hora(dt: datetime) -> str:
    return a_utc(dt).astimezone(TZ).strftime("%Y-%m-%d %H:%M")


def _num(valor) -> float | int:
    v = float(valor or 0)
    return int(v) if v.is_integer() else round(v, 2)


def edad_en(fecha_nacimiento: date, en: date | None = None) -> int:
    en = en or date.today()
    return en.year - fecha_nacimiento.year - ((en.month, en.day) < (fecha_nacimiento.month, fecha_nacimiento.day))


def generar_rips(
    atenciones: list[Atencion],
    num_factura: str,
    tipo_nota: str | None = None,
    num_nota: str | None = None,
) -> tuple[dict, list[str]]:
    """Devuelve (json_rips, lista_de_errores). Si hay errores, NO debe enviarse al MUV."""
    errores: list[str] = []
    if not num_factura:
        errores.append("El número de factura es obligatorio")

    por_paciente: "OrderedDict[str, list[Atencion]]" = OrderedDict()
    for a in sorted(atenciones, key=lambda x: x.fecha_inicio):
        if a.estado != "firmada":
            errores.append(f"La atención {a.id} no está firmada; solo se facturan atenciones cerradas")
        por_paciente.setdefault(str(a.paciente_id), []).append(a)

    usuarios = []
    for consecutivo_usuario, lista in enumerate(por_paciente.values(), start=1):
        p = lista[0].paciente
        if p.sexo not in ("H", "M", "I"):
            errores.append(f"Paciente {p.numero_documento}: sexo inválido '{p.sexo}' (H, M o I)")
        if len(p.cod_municipio_residencia or "") != 5:
            errores.append(f"Paciente {p.numero_documento}: código de municipio DIVIPOLA debe tener 5 dígitos")

        consultas, procedimientos = [], []
        for a in lista:
            prof = a.profesional
            dx = [d for d in sorted(a.diagnosticos, key=lambda d: d.orden)]
            if not dx:
                errores.append(f"Atención {a.consecutivo} de {p.numero_documento}: falta diagnóstico principal")
            for d in dx:
                if not codigo_valido(d.codigo_cie10):
                    errores.append(f"Código CIE-10 inválido '{d.codigo_cie10}' en atención {a.consecutivo}")
            principal = dx[0].codigo_cie10 if dx else None
            rel = [d.codigo_cie10 for d in dx[1:4]] + [None, None, None]

            consultas.append(
                {
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
                    "consecutivo": len(consultas) + 1,
                }
            )
            for proc in a.procedimientos:
                procedimientos.append(
                    {
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
                        "consecutivo": len(procedimientos) + 1,
                    }
                )

        servicios: dict = {"consultas": consultas}
        if procedimientos:
            servicios["procedimientos"] = procedimientos
        usuarios.append(
            {
                "tipoDocumentoIdentificacion": p.tipo_documento,
                "numDocumentoIdentificacion": p.numero_documento,
                "tipoUsuario": p.tipo_usuario,
                "fechaNacimiento": p.fecha_nacimiento.isoformat(),
                "codSexo": p.sexo,
                "codPaisResidencia": p.cod_pais_residencia,
                "codMunicipioResidencia": p.cod_municipio_residencia,
                "codZonaTerritorialResidencia": p.zona_territorial,
                "incapacidad": "NO",
                "consecutivo": consecutivo_usuario,
                "codPaisOrigen": "170",
                "servicios": servicios,
            }
        )

    rips = {
        "numDocumentoIdObligado": settings.PRESTADOR_NIT,
        "numFactura": num_factura,
        "tipoNota": tipo_nota,
        "numNota": num_nota,
        "usuarios": usuarios,
    }
    return rips, errores
