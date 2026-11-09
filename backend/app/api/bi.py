"""Inteligencia de negocio: constructor de reportes, reportes guardados y exportación a Excel/CSV."""
import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import PERSONAL, ip_cliente, requiere_rol
from app.models import Usuario
from app.models_ext import ReporteGuardado
from app.services import bi
from app.services.ledger import registrar_evento

router = APIRouter(prefix="/api/bi", tags=["Inteligencia de negocio"])


class Consulta(BaseModel):
    dataset: str
    dimensiones: list[str] = Field(default_factory=list, max_length=3)
    medidas: list[str] = Field(default_factory=list, max_length=6)
    desde: date | None = None
    hasta: date | None = None
    filtros: dict[str, str] = Field(default_factory=dict)
    grafico: str = Field("barras", pattern="^(barras|lineas|tabla|torta)$")
    limite: int = Field(500, ge=1, le=5000)


class ReporteIn(BaseModel):
    nombre: str = Field(min_length=3, max_length=150)
    descripcion: str | None = None
    definicion: Consulta
    roles: list[str] = Field(default_factory=list)


def _ejecutar(db: Session, usuario: Usuario, c: Consulta) -> dict:
    datasets = bi.disponibles(db, usuario.rol)
    if c.dataset not in datasets:
        raise HTTPException(403, "No tiene acceso a este conjunto de datos o no existe")
    hasta = c.hasta or date.today()
    desde = c.desde or hasta - timedelta(days=90)
    if (hasta - desde).days > 3660:
        raise HTTPException(422, "El periodo máximo es de 10 años")
    try:
        r = bi.ejecutar(db, datasets[c.dataset], c.dimensiones, c.medidas, desde, hasta, c.filtros, c.limite)
    except bi.ErrorConsulta as exc:
        raise HTTPException(422, str(exc))
    r["grafico"] = c.grafico
    return r


@router.get("/datasets")
def datasets(db: Session = Depends(get_db), usuario: Usuario = Depends(requiere_rol(*PERSONAL))):
    return [{"clave": d.clave, "nombre": d.nombre,
             "dimensiones": [{"clave": k, "etiqueta": v[0]} for k, v in d.dimensiones.items()],
             "medidas": [{"clave": k, "etiqueta": v[0]} for k, v in d.medidas.items()]}
            for d in bi.disponibles(db, usuario.rol).values()]


@router.post("/consultar")
def consultar(c: Consulta, db: Session = Depends(get_db), usuario: Usuario = Depends(requiere_rol(*PERSONAL))):
    return _ejecutar(db, usuario, c)


@router.post("/exportar")
def exportar(c: Consulta, request: Request, formato: str = "xlsx", db: Session = Depends(get_db),
             usuario: Usuario = Depends(requiere_rol(*PERSONAL))):
    r = _ejecutar(db, usuario, c)
    registrar_evento(db, accion="REPORTE_EXPORTADO", entidad="reporte", datos=c.model_dump(mode="json"),
                     usuario_id=usuario.id, ip=ip_cliente(request))
    db.commit()
    if formato == "csv":
        return Response(bi.a_csv(r), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="reporte.csv"'})
    return Response(bi.a_excel(r), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": 'attachment; filename="reporte.xlsx"'})


def _visibles(db: Session, usuario: Usuario) -> list[ReporteGuardado]:
    todos = db.scalars(select(ReporteGuardado).order_by(ReporteGuardado.nombre)).all()
    return [r for r in todos if usuario.rol == "admin" or r.creado_por == usuario.id or usuario.rol in (r.roles or [])]


@router.get("/reportes")
def reportes(db: Session = Depends(get_db), usuario: Usuario = Depends(requiere_rol(*PERSONAL))):
    return [{"id": str(r.id), "nombre": r.nombre, "descripcion": r.descripcion, "definicion": r.definicion, "roles": r.roles,
             "propio": r.creado_por == usuario.id} for r in _visibles(db, usuario)]


@router.post("/reportes", status_code=201)
def guardar(datos: ReporteIn, db: Session = Depends(get_db), usuario: Usuario = Depends(requiere_rol(*PERSONAL))):
    _ejecutar(db, usuario, datos.definicion)  # valida que la definición funcione antes de guardarla
    r = ReporteGuardado(nombre=datos.nombre, descripcion=datos.descripcion, definicion=datos.definicion.model_dump(mode="json"),
                        roles=datos.roles, creado_por=usuario.id)
    db.add(r)
    db.commit()
    return {"id": str(r.id)}


@router.get("/reportes/{reporte_id}/ejecutar")
def ejecutar_guardado(reporte_id: uuid.UUID, desde: date | None = None, hasta: date | None = None,
                      db: Session = Depends(get_db), usuario: Usuario = Depends(requiere_rol(*PERSONAL))):
    r = next((x for x in _visibles(db, usuario) if x.id == reporte_id), None)
    if not r:
        raise HTTPException(404, "Reporte no encontrado")
    c = Consulta(**{**r.definicion, "desde": desde or r.definicion.get("desde"), "hasta": hasta or r.definicion.get("hasta")})
    return {"nombre": r.nombre, **_ejecutar(db, usuario, c)}


@router.delete("/reportes/{reporte_id}", status_code=204)
def borrar(reporte_id: uuid.UUID, db: Session = Depends(get_db), usuario: Usuario = Depends(requiere_rol(*PERSONAL))):
    r = db.get(ReporteGuardado, reporte_id)
    if not r or (r.creado_por != usuario.id and usuario.rol != "admin"):
        raise HTTPException(404, "Reporte no encontrado")
    db.delete(r)
    db.commit()
