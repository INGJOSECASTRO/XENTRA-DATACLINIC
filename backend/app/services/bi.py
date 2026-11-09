"""Constructor de reportes (inteligencia de negocio) basado en la lógica del negocio de la salud.

El usuario elige un conjunto de datos (atenciones, citas, facturación, hospitalización, farmacia, triage,
laboratorio o cualquier módulo dinámico), hasta 3 dimensiones (agrupar por), las medidas y los filtros.
Seguridad:
- No hay SQL libre: solo dimensiones y medidas declaradas aquí (no hay inyección posible).
- Solo datos agregados: ninguna dimensión expone nombres ni documentos (minimización - Ley 1581).
- Cada conjunto de datos declara qué roles pueden consultarlo.
Para volúmenes muy grandes, conecte una herramienta BI (Metabase, Superset, Power BI) a una réplica de lectura.
"""
import csv
import io
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timezone
from typing import Callable
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Atencion
from app.models_ext import (Cita, Factura, Hospitalizacion, ModuloDinamico, MovimientoInventario, OrdenServicio,
                            RegistroModulo, Triage)
from app.services.ledger import a_utc

TZ = ZoneInfo(settings.ZONA_HORARIA)
MAX_FILAS = 200_000


def _local(dt) -> datetime | None:
    return a_utc(dt).astimezone(TZ) if dt else None


def _mes(dt) -> str | None:
    d = _local(dt)
    return d.strftime("%Y-%m") if d else None


def _dia(dt) -> str | None:
    d = _local(dt)
    return d.strftime("%Y-%m-%d") if d else None


def _anio(dt) -> str | None:
    d = _local(dt)
    return str(d.year) if d else None


def grupo_edad(nacimiento: date, en: date) -> str:
    e = en.year - nacimiento.year - ((en.month, en.day) < (nacimiento.month, nacimiento.day))
    for limite, nombre in ((5, "0-5 primera infancia"), (11, "6-11 infancia"), (17, "12-17 adolescencia"),
                           (28, "18-28 juventud"), (59, "29-59 adultez")):
        if e <= limite:
            return nombre
    return "60+ vejez"  # cursos de vida - Resolución 3280 de 2018


CAPITULOS_CIE10 = [("A", "B", "I Infecciosas"), ("C", "D4", "II Neoplasias"), ("D5", "D8", "III Sangre"), ("E", "E", "IV Endocrinas"),
                   ("F", "F", "V Mentales"), ("G", "G", "VI Nervioso"), ("H0", "H5", "VII Ojo"), ("H6", "H9", "VIII Oído"),
                   ("I", "I", "IX Circulatorio"), ("J", "J", "X Respiratorio"), ("K", "K", "XI Digestivo"), ("L", "L", "XII Piel"),
                   ("M", "M", "XIII Osteomuscular"), ("N", "N", "XIV Genitourinario"), ("O", "O", "XV Embarazo"),
                   ("P", "P", "XVI Perinatal"), ("Q", "Q", "XVII Malformaciones"), ("R", "R", "XVIII Síntomas"),
                   ("S", "T", "XIX Traumatismos"), ("V", "Y", "XX Causas externas"), ("Z", "Z", "XXI Factores de salud"),
                   ("U", "U", "XXII Códigos especiales")]


def capitulo(codigo: str | None) -> str | None:
    if not codigo:
        return None
    for ini, fin, nombre in CAPITULOS_CIE10:
        if ini <= codigo[: len(ini)] and codigo[: len(fin)] <= fin:
            return nombre
    return "Otro"


@dataclass
class Dataset:
    clave: str
    nombre: str
    roles: tuple
    campo_fecha: str  # columna usada para el filtro de periodo
    consulta: Callable[[Session, datetime, datetime], list]  # devuelve objetos de la BD
    dimensiones: dict[str, tuple[str, Callable]]  # clave -> (etiqueta, función(obj) -> valor)
    medidas: dict[str, tuple[str, str, Callable | None]] = field(default_factory=dict)  # clave -> (etiqueta, agregación, valor)


def _rango(modelo, columna):
    def consulta(db: Session, ini, fin):
        col = getattr(modelo, columna)
        return db.scalars(select(modelo).where(col >= ini, col <= fin).limit(MAX_FILAS)).yield_per(2000)
    return consulta


def _dx(a):
    return a.diagnosticos[0].codigo_cie10 if a.diagnosticos else None


DATASETS: dict[str, Dataset] = {
    "atenciones": Dataset(
        "atenciones", "Atenciones (historia clínica)", ("admin", "auditor", "medico"), "fecha_inicio",
        lambda db, ini, fin: db.scalars(select(Atencion).where(Atencion.fecha_inicio >= ini, Atencion.fecha_inicio <= fin,
                                                               Atencion.estado == "firmada").limit(MAX_FILAS)).yield_per(2000),
        {"mes": ("Mes", lambda a: _mes(a.fecha_inicio)), "dia": ("Día", lambda a: _dia(a.fecha_inicio)),
         "anio": ("Año", lambda a: _anio(a.fecha_inicio)), "tipo": ("Tipo de atención", lambda a: a.tipo),
         "profesional": ("Profesional", lambda a: a.profesional.nombre_completo),
         "especialidad": ("Especialidad", lambda a: a.profesional.especialidad or a.profesional.rol),
         "dx_principal": ("Diagnóstico principal", lambda a: f"{_dx(a)} {a.diagnosticos[0].descripcion[:50]}" if a.diagnosticos else None),
         "capitulo_cie10": ("Capítulo CIE-10", lambda a: capitulo(_dx(a))),
         "eps": ("EPS", lambda a: a.paciente.cod_eapb), "regimen": ("Tipo de usuario", lambda a: a.paciente.tipo_usuario),
         "sexo": ("Sexo", lambda a: a.paciente.sexo),
         "curso_vida": ("Curso de vida", lambda a: grupo_edad(a.paciente.fecha_nacimiento, _local(a.fecha_inicio).date())),
         "municipio": ("Municipio", lambda a: a.paciente.cod_municipio_residencia),
         "finalidad": ("Finalidad", lambda a: a.finalidad_tecnologia), "cups": ("CUPS consulta", lambda a: a.cod_consulta_cups),
         "con_ia": ("Dx con apoyo de IA", lambda a: "Sí" if any(d.sugerido_por_ia for d in a.diagnosticos) else "No")},
        {"conteo": ("Número de atenciones", "count", None), "pacientes": ("Pacientes únicos", "distinct", lambda a: a.paciente_id),
         "valor": ("Valor de servicios", "sum", lambda a: float(a.valor_servicio or 0)),
         "copagos": ("Pagos moderadores", "sum", lambda a: float(a.valor_pago_moderador or 0))},
    ),
    "citas": Dataset(
        "citas", "Agenda / citas", ("admin", "auditor", "admisiones"), "inicio", _rango(Cita, "inicio"),
        {"mes": ("Mes", lambda c: _mes(c.inicio)), "dia": ("Día", lambda c: _dia(c.inicio)),
         "profesional": ("Profesional", lambda c: c.profesional.nombre_completo), "estado": ("Estado", lambda c: c.estado),
         "modalidad": ("Modalidad", lambda c: c.modalidad), "cups": ("CUPS", lambda c: c.cod_cups),
         "hora": ("Hora del día", lambda c: _local(c.inicio).strftime("%H:00"))},
        {"conteo": ("Número de citas", "count", None),
         "oportunidad": ("Oportunidad promedio (días)", "avg",
                         lambda c: (_local(c.inicio).date() - (c.fecha_deseada or _local(c.fecha_solicitud).date())).days),
         "inasistencia": ("% inasistencia", "pct", lambda c: c.estado == "no_asistio")},
    ),
    "facturacion": Dataset(
        "facturacion", "Facturación", ("admin", "auditor", "facturacion"), "creado_en", _rango(Factura, "creado_en"),
        {"mes": ("Mes", lambda f: _mes(f.creado_en)), "estado": ("Estado", lambda f: f.estado),
         "pagador": ("Pagador", lambda f: f.nombre_pagador), "eps": ("Código EAPB", lambda f: f.cod_eapb),
         "tipo_pagador": ("Tipo de pagador", lambda f: f.tipo_pagador), "modalidad": ("Modalidad de pago", lambda f: f.modalidad_pago)},
        {"conteo": ("Número de facturas", "count", None), "total": ("Valor total", "sum", lambda f: float(f.total or 0)),
         "con_hallazgos": ("% con errores de pre-auditoría", "pct",
                           lambda f: any(h.get("nivel") == "error" for h in (f.hallazgos_auditoria or [])))},
    ),
    "hospitalizacion": Dataset(
        "hospitalizacion", "Hospitalización", ("admin", "auditor", "medico"), "fecha_ingreso",
        _rango(Hospitalizacion, "fecha_ingreso"),
        {"mes": ("Mes de ingreso", lambda h: _mes(h.fecha_ingreso)), "servicio": ("Servicio", lambda h: h.cama.servicio if h.cama else None),
         "dx_ingreso": ("Dx de ingreso", lambda h: h.dx_ingreso), "capitulo_cie10": ("Capítulo CIE-10", lambda h: capitulo(h.dx_ingreso)),
         "estado": ("Estado", lambda h: h.estado), "condicion_egreso": ("Condición de egreso", lambda h: h.condicion_egreso),
         "via_ingreso": ("Vía de ingreso", lambda h: h.via_ingreso)},
        {"conteo": ("Número de hospitalizaciones", "count", None),
         "estancia": ("Estancia promedio (días)", "avg",
                      lambda h: (a_utc(h.fecha_egreso) - a_utc(h.fecha_ingreso)).total_seconds() / 86400 if h.fecha_egreso else None),
         "mortalidad": ("% mortalidad", "pct", lambda h: h.condicion_egreso == "02")},
    ),
    "farmacia": Dataset(
        "farmacia", "Dispensación de medicamentos", ("admin", "auditor", "farmacia"), "fecha",
        lambda db, ini, fin: db.scalars(select(MovimientoInventario).where(
            MovimientoInventario.fecha >= ini, MovimientoInventario.fecha <= fin,
            MovimientoInventario.tipo == "dispensacion").limit(MAX_FILAS)).yield_per(2000),
        {"mes": ("Mes", lambda m: _mes(m.fecha)), "producto": ("Producto", lambda m: m.producto.nombre),
         "origen": ("Origen", lambda m: "Consulta" if m.prescripcion_id else "Hospitalización")},
        {"conteo": ("Entregas", "count", None), "unidades": ("Unidades", "sum", lambda m: abs(m.cantidad)),
         "valor": ("Valor", "sum", lambda m: float(m.producto.precio_unitario or 0) * abs(m.cantidad))},
    ),
    "urgencias": Dataset(
        "urgencias", "Urgencias (triage)", ("admin", "auditor", "medico", "enfermeria"), "llegada", _rango(Triage, "llegada"),
        {"mes": ("Mes", lambda t: _mes(t.llegada)), "dia": ("Día", lambda t: _dia(t.llegada)), "nivel": ("Nivel de triage", lambda t: t.nivel),
         "hora": ("Hora de llegada", lambda t: _local(t.llegada).strftime("%H:00")), "estado": ("Estado", lambda t: t.estado)},
        {"conteo": ("Pacientes", "count", None),
         "espera": ("Espera promedio (min)", "avg",
                    lambda t: (a_utc(t.inicio_atencion) - a_utc(t.llegada)).total_seconds() / 60 if t.inicio_atencion else None),
         "concordancia": ("% concordancia con sugerencia", "pct", lambda t: t.nivel == t.nivel_sugerido)},
    ),
    "laboratorio": Dataset(
        "laboratorio", "Laboratorio e imágenes", ("admin", "auditor", "laboratorio", "medico"), "fecha", _rango(OrdenServicio, "fecha"),
        {"mes": ("Mes", lambda o: _mes(o.fecha)), "tipo": ("Tipo", lambda o: o.tipo), "examen": ("Examen", lambda o: f"{o.cod_cups} {o.descripcion[:40]}"),
         "estado": ("Estado", lambda o: o.estado), "prioridad": ("Prioridad", lambda o: o.prioridad)},
        {"conteo": ("Órdenes", "count", None),
         "oportunidad": ("Horas hasta el resultado", "avg",
                         lambda o: (a_utc(o.fecha_resultado) - a_utc(o.fecha)).total_seconds() / 3600 if o.fecha_resultado else None),
         "anormales": ("% con valores anormales", "pct", lambda o: any(r.get("anormal") for r in (o.resultados or [])))},
    ),
}


def dataset_modulo(m: ModuloDinamico) -> Dataset:
    dims = {"mes": ("Mes", lambda r: _mes(r.creado_en)), "autor": ("Registrado por", lambda r: r.autor.nombre_completo)}
    medidas = {"conteo": ("Registros", "count", None)}
    if m.por_paciente:
        medidas["pacientes"] = ("Pacientes únicos", "distinct", lambda r: r.paciente_id)
    for c in m.campos:
        k, etq = c["clave"], c["etiqueta"]
        if c["tipo"] in ("seleccion", "si_no", "cie10", "texto", "fecha"):
            dims[k] = (etq, lambda r, k=k: (("Sí" if r.datos.get(k) else "No") if isinstance(r.datos.get(k), bool) else r.datos.get(k)))
        elif c["tipo"] == "multiple":
            dims[k] = (etq, lambda r, k=k: ", ".join(sorted(r.datos.get(k) or [])) or None)
        if c["tipo"] in ("numero", "entero"):
            medidas[f"suma_{k}"] = (f"Suma de {etq}", "sum", lambda r, k=k: r.datos.get(k))
            medidas[f"prom_{k}"] = (f"Promedio de {etq}", "avg", lambda r, k=k: r.datos.get(k))
    roles = tuple(set(m.roles_lectura or []) | {"admin", "auditor"})

    def consulta(db, ini, fin, mid=m.id):
        return db.scalars(select(RegistroModulo).where(RegistroModulo.modulo_id == mid, RegistroModulo.creado_en >= ini,
                                                       RegistroModulo.creado_en <= fin).limit(MAX_FILAS)).yield_per(2000)
    return Dataset(f"modulo:{m.clave}", f"Módulo: {m.nombre}", roles, "creado_en", consulta, dims, medidas)


def disponibles(db: Session, rol: str) -> dict[str, Dataset]:
    todos = dict(DATASETS)
    for m in db.scalars(select(ModuloDinamico).where(ModuloDinamico.activo.is_(True))).all():
        d = dataset_modulo(m)
        todos[d.clave] = d
    return {k: d for k, d in todos.items() if rol in d.roles}


class ErrorConsulta(ValueError):
    pass


def ejecutar(db: Session, ds: Dataset, dimensiones: list[str], medidas: list[str], desde: date, hasta: date,
             filtros: dict | None = None, limite: int = 500) -> dict:
    if len(dimensiones) > 3:
        raise ErrorConsulta("Máximo 3 dimensiones")
    medidas = medidas or ["conteo"]
    for d in dimensiones + list((filtros or {}).keys()):
        if d not in ds.dimensiones:
            raise ErrorConsulta(f"Dimensión no disponible: {d}")
    for m in medidas:
        if m not in ds.medidas:
            raise ErrorConsulta(f"Medida no disponible: {m}")
    ini = datetime.combine(desde, time.min, TZ).astimezone(timezone.utc)
    fin = datetime.combine(hasta, time.max, TZ).astimezone(timezone.utc)
    grupos: dict[tuple, dict] = defaultdict(lambda: {m: [] for m in medidas})
    filas_leidas = 0
    for obj in ds.consulta(db, ini, fin):
        if filtros and any(str(ds.dimensiones[k][1](obj)) != str(v) for k, v in filtros.items() if v not in (None, "")):
            continue
        filas_leidas += 1
        clave = tuple(ds.dimensiones[d][1](obj) for d in dimensiones)
        for m in medidas:
            _, agg, fn = ds.medidas[m]
            grupos[clave][m].append(1 if fn is None else fn(obj))
    filas = []
    for clave, valores in grupos.items():
        fila = {d: clave[i] for i, d in enumerate(dimensiones)}
        for m in medidas:
            agg, vals = ds.medidas[m][1], [v for v in valores[m] if v is not None]
            if agg == "count":
                fila[m] = len(valores[m])
            elif agg == "sum":
                fila[m] = round(sum(vals), 2)
            elif agg == "avg":
                fila[m] = round(sum(vals) / len(vals), 2) if vals else None
            elif agg == "distinct":
                fila[m] = len(set(vals))
            elif agg == "pct":
                fila[m] = round(100 * sum(1 for v in valores[m] if v) / len(valores[m]), 1) if valores[m] else None
        filas.append(fila)
    orden = medidas[0]
    filas.sort(key=lambda f: (f.get(orden) is None, -(f.get(orden) or 0)) if not dimensiones or dimensiones[0] not in ("mes", "dia", "anio", "hora")
               else (str(f.get(dimensiones[0])),))
    columnas = [{"clave": d, "etiqueta": ds.dimensiones[d][0], "tipo": "dimension"} for d in dimensiones] + \
               [{"clave": m, "etiqueta": ds.medidas[m][0], "tipo": "medida"} for m in medidas]
    return {"dataset": ds.clave, "titulo": ds.nombre, "columnas": columnas, "filas": filas[:limite],
            "total_grupos": len(filas), "registros_analizados": filas_leidas,
            "periodo": {"desde": desde.isoformat(), "hasta": hasta.isoformat()}}


def a_csv(resultado: dict) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow([c["etiqueta"] for c in resultado["columnas"]])
    for f in resultado["filas"]:
        w.writerow([f.get(c["clave"]) for c in resultado["columnas"]])
    return buf.getvalue().encode("utf-8-sig")


def a_excel(resultado: dict) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    wb = Workbook()
    ws = wb.active
    ws.title = "Reporte"
    ws.append([resultado["titulo"]])
    ws["A1"].font = Font(bold=True, size=13)
    ws.append([f"Periodo: {resultado['periodo']['desde']} a {resultado['periodo']['hasta']} · "
               f"{resultado['registros_analizados']} registros analizados"])
    ws.append([])
    ws.append([c["etiqueta"] for c in resultado["columnas"]])
    for celda in ws[4]:
        celda.font = Font(bold=True, color="FFFFFF")
        celda.fill = PatternFill("solid", fgColor="0F766E")
    for f in resultado["filas"]:
        ws.append([f.get(c["clave"]) for c in resultado["columnas"]])
    for i, c in enumerate(resultado["columnas"], 1):
        ws.column_dimensions[chr(64 + i)].width = 34 if c["tipo"] == "dimension" else 20
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
