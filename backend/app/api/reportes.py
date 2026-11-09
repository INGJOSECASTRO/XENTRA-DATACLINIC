"""Indicadores de calidad y gestión (inspirados en la Resolución 256 de 2016), SIVIGILA y resumen IA."""
import csv
import io
import uuid
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
from statistics import mean
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import LECTURA_HC, ip_cliente, requiere_rol
from app.models import Atencion, Paciente, Usuario
from app.models_ext import Cama, Cita, Factura, Hospitalizacion, OrdenServicio, Triage
from app.services.ledger import a_utc, registrar_evento
from app.services.resumen import resumen
from app.services.rips import edad_en
from app.services.seguridad_clinica import eventos_sivigila

router = APIRouter(prefix="/api", tags=["Reportes e indicadores"])
TZ = ZoneInfo(settings.ZONA_HORARIA)
GERENCIA = ("admin", "auditor")


def _rango(desde: date | None, hasta: date | None) -> tuple[datetime, datetime]:
    hasta = hasta or date.today()
    desde = desde or hasta - timedelta(days=30)
    return (datetime.combine(desde, time.min, TZ).astimezone(timezone.utc),
            datetime.combine(hasta, time.max, TZ).astimezone(timezone.utc))


def _prom(valores: list[float]) -> float | None:
    return round(mean(valores), 2) if valores else None


@router.get("/reportes/indicadores")
def indicadores(desde: date | None = None, hasta: date | None = None, db: Session = Depends(get_db),
                _: Usuario = Depends(requiere_rol(*GERENCIA))):
    ini, fin = _rango(desde, hasta)
    citas = db.scalars(select(Cita).where(Cita.inicio >= ini, Cita.inicio <= fin)).all()
    medicina_general = [c for c in citas if c.cod_cups in ("890201", "890301")]
    oportunidad = [(a_utc(c.inicio).astimezone(TZ).date() - (c.fecha_deseada or a_utc(c.fecha_solicitud).astimezone(TZ).date())).days
                   for c in medicina_general]
    triages = db.scalars(select(Triage).where(Triage.llegada >= ini, Triage.llegada <= fin)).all()
    espera_ii = [(a_utc(t.inicio_atencion) - a_utc(t.llegada)).total_seconds() / 60 for t in triages
                 if t.nivel == 2 and t.inicio_atencion]
    camas = db.scalars(select(Cama)).all()
    egresos = db.scalars(select(Hospitalizacion).where(Hospitalizacion.fecha_egreso >= ini,
                                                       Hospitalizacion.fecha_egreso <= fin)).all()
    atenciones = db.scalars(select(Atencion).where(Atencion.fecha_inicio >= ini, Atencion.fecha_inicio <= fin,
                                                   Atencion.estado == "firmada")).all()
    dx = Counter(f"{a.diagnosticos[0].codigo_cie10} {a.diagnosticos[0].descripcion}" for a in atenciones if a.diagnosticos)
    por_profesional = Counter(a.profesional.nombre_completo for a in atenciones)
    facturas = db.scalars(select(Factura).where(Factura.creado_en >= ini, Factura.creado_en <= fin)).all()
    total_citas = len(citas) or 1
    return {
        "periodo": {"desde": ini.astimezone(TZ).date(), "hasta": fin.astimezone(TZ).date()},
        "agenda": {
            "citas": len(citas),
            "oportunidad_medicina_general_dias": _prom(oportunidad),
            "cancelacion_pct": round(100 * sum(c.estado == "cancelada" for c in citas) / total_citas, 1),
            "inasistencia_pct": round(100 * sum(c.estado == "no_asistio" for c in citas) / total_citas, 1),
            "telemedicina": sum(c.modalidad == "telemedicina" for c in citas),
        },
        "urgencias": {
            "triages": len(triages),
            "por_nivel": dict(sorted(Counter(t.nivel for t in triages).items())),
            "espera_promedio_triage_ii_min": _prom(espera_ii),
            "triage_ii_atendidos_en_30_min_pct": round(100 * sum(x <= 30 for x in espera_ii) / len(espera_ii), 1) if espera_ii else None,
        },
        "hospitalizacion": {
            "camas": len(camas),
            "ocupacion_actual_pct": round(100 * sum(c.estado == "ocupada" for c in camas) / len(camas), 1) if camas else None,
            "egresos": len(egresos),
            "estancia_promedio_dias": _prom([(a_utc(h.fecha_egreso) - a_utc(h.fecha_ingreso)).total_seconds() / 86400 for h in egresos]),
            "mortalidad_pct": round(100 * sum(h.condicion_egreso == "02" for h in egresos) / len(egresos), 1) if egresos else None,
        },
        "consulta": {
            "atenciones_firmadas": len(atenciones),
            "primeros_diagnosticos": dx.most_common(10),
            "por_profesional": por_profesional.most_common(),
            "sugeridos_por_ia_pct": round(100 * sum(any(d.sugerido_por_ia for d in a.diagnosticos) for a in atenciones)
                                          / len(atenciones), 1) if atenciones else None,
        },
        "facturacion": {
            "facturas": len(facturas),
            "por_estado": dict(Counter(f.estado for f in facturas)),
            "valor_emitido": float(sum(f.total for f in facturas if f.estado in ("emitida", "validada"))),
            "valor_validado_muv": float(sum(f.total for f in facturas if f.estado == "validada")),
        },
    }


def _sivigila(db: Session, desde, hasta) -> list[dict]:
    ini, fin = _rango(desde, hasta)
    filas = []
    for a in db.scalars(select(Atencion).where(Atencion.estado == "firmada", Atencion.fecha_inicio >= ini,
                                               Atencion.fecha_inicio <= fin).order_by(Atencion.fecha_inicio)).all():
        for e in eventos_sivigila([d.codigo_cie10 for d in a.diagnosticos]):
            p = a.paciente
            filas.append({"fecha": a_utc(a.fecha_inicio).astimezone(TZ).strftime("%Y-%m-%d %H:%M"), "evento": e["evento"],
                          "cie10": e["codigo"], "tipo_documento": p.tipo_documento, "documento": p.numero_documento,
                          "paciente": p.nombre_completo, "edad": edad_en(p.fecha_nacimiento), "sexo": p.sexo,
                          "municipio": p.cod_municipio_residencia, "profesional": a.profesional.nombre_completo,
                          "atencion_id": str(a.id)})
    return filas


@router.get("/reportes/sivigila")
def sivigila(desde: date | None = None, hasta: date | None = None, formato: str = "json", db: Session = Depends(get_db),
             _: Usuario = Depends(requiere_rol("medico", "auditor", "admin"))):
    """Casos con diagnósticos de eventos de notificación obligatoria (para diligenciar fichas del INS)."""
    filas = _sivigila(db, desde, hasta)
    if formato == "csv":
        buf = io.StringIO()
        if filas:
            w = csv.DictWriter(buf, fieldnames=list(filas[0]), delimiter=";")
            w.writeheader()
            w.writerows(filas)
        return Response(buf.getvalue().encode("utf-8-sig"), media_type="text/csv",
                        headers={"Content-Disposition": 'attachment; filename="sivigila.csv"'})
    return filas


@router.get("/pacientes/{paciente_id}/resumen-ia")
def resumen_paciente(paciente_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
                     usuario: Usuario = Depends(requiere_rol(*LECTURA_HC))):
    p = db.get(Paciente, paciente_id)
    if not p:
        raise HTTPException(404, "Paciente no encontrado")
    atenciones = db.scalars(select(Atencion).where(Atencion.paciente_id == p.id, Atencion.estado == "firmada")
                            .order_by(Atencion.fecha_inicio)).all()
    hosp = db.scalars(select(Hospitalizacion).where(Hospitalizacion.paciente_id == p.id)).all()
    labs = db.scalars(select(OrdenServicio).where(OrdenServicio.paciente_id == p.id, OrdenServicio.estado == "validada")).all()
    registrar_evento(db, accion="RESUMEN_HC", entidad="paciente", entidad_id=p.id, usuario_id=usuario.id, ip=ip_cliente(request))
    db.commit()
    return resumen(p, list(atenciones), list(hosp), list(labs), edad_en(p.fecha_nacimiento))
