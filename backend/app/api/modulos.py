"""Constructor de módulos sin programar: definición (admin) y registro de datos (roles autorizados)."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import ADMIN_GESTION, PERSONAL, es_admin, ip_cliente, requiere_rol
from app.models import Paciente, Usuario
from app.models_ext import ModuloDinamico, RegistroModulo
from app.services import modulos as srv
from app.services.ledger import json_canonico, registrar_evento, sha256

router = APIRouter(prefix="/api/modulos", tags=["Módulos dinámicos"])
from app.core.deps import PERSONAL as _P
ROLES_VALIDOS = set(_P)


class ModuloIn(BaseModel):
    clave: str = Field(pattern=r"^[a-z][a-z0-9_]{1,39}$")
    nombre: str = Field(min_length=3, max_length=120)
    descripcion: str | None = None
    categoria: str = Field("asistencial", pattern="^(asistencial|administrativo|calidad|financiero)$")
    campos: list[dict]
    roles_lectura: list[str] = Field(default_factory=list)
    roles_escritura: list[str] = Field(default_factory=list)
    por_paciente: bool = True
    sellar_al_guardar: bool = False
    activo: bool = True


class RegistroIn(BaseModel):
    paciente_id: uuid.UUID | None = None
    datos: dict


def _salida(m: ModuloDinamico) -> dict:
    return {"id": str(m.id), "clave": m.clave, "nombre": m.nombre, "descripcion": m.descripcion, "categoria": m.categoria,
            "campos": m.campos, "roles_lectura": m.roles_lectura, "roles_escritura": m.roles_escritura,
            "por_paciente": m.por_paciente, "sellar_al_guardar": m.sellar_al_guardar, "activo": m.activo, "version": m.version}


def _modulo(db: Session, clave: str) -> ModuloDinamico:
    m = db.scalars(select(ModuloDinamico).where(ModuloDinamico.clave == clave)).first()
    if not m or not m.activo:
        raise HTTPException(404, "Módulo no encontrado o inactivo")
    return m


def _puede(usuario: Usuario, roles: list[str]) -> bool:
    return usuario.rol == "admin" or usuario.rol in (roles or [])


def _validar_roles(roles: list[str]) -> None:
    if invalidos := set(roles) - ROLES_VALIDOS:
        raise HTTPException(422, f"Roles no válidos: {', '.join(sorted(invalidos))}")


@router.get("/tipos-campo")
def tipos(_: Usuario = Depends(requiere_rol(*PERSONAL))):
    return srv.TIPOS_CAMPO


@router.get("/plantillas")
def plantillas(_: Usuario = Depends(requiere_rol(*ADMIN_GESTION))):
    return srv.PLANTILLAS


@router.get("")
def listar(db: Session = Depends(get_db), usuario: Usuario = Depends(requiere_rol(*PERSONAL))):
    todos = db.scalars(select(ModuloDinamico).order_by(ModuloDinamico.categoria, ModuloDinamico.nombre)).all()
    return [{**_salida(m), "puede_escribir": _puede(usuario, m.roles_escritura)} for m in todos
            if es_admin(usuario) or (m.activo and (_puede(usuario, m.roles_lectura) or _puede(usuario, m.roles_escritura)))]


def _crear(db: Session, datos: dict, admin: Usuario, ip) -> ModuloDinamico:
    if db.scalars(select(ModuloDinamico).where(ModuloDinamico.clave == datos["clave"])).first():
        raise HTTPException(409, "Ya existe un módulo con esa clave")
    _validar_roles(datos["roles_lectura"] + datos["roles_escritura"])
    try:
        datos["campos"] = srv.validar_definicion(datos["campos"])
    except srv.ErrorModulo as exc:
        raise HTTPException(422, str(exc))
    m = ModuloDinamico(**datos, creado_por=admin.id)
    db.add(m)
    db.flush()
    registrar_evento(db, accion="MODULO_CREADO", entidad="modulo", entidad_id=m.id, datos=_salida(m), usuario_id=admin.id, ip=ip)
    db.commit()
    return m


@router.post("", status_code=201)
def crear(datos: ModuloIn, request: Request, db: Session = Depends(get_db), admin: Usuario = Depends(requiere_rol(*ADMIN_GESTION))):
    return _salida(_crear(db, datos.model_dump(), admin, ip_cliente(request)))


@router.post("/plantillas/{plantilla}/instalar", status_code=201)
def instalar(plantilla: str, request: Request, db: Session = Depends(get_db), admin: Usuario = Depends(requiere_rol(*ADMIN_GESTION))):
    if plantilla not in srv.PLANTILLAS:
        raise HTTPException(404, "Plantilla no encontrada")
    return _salida(_crear(db, {"clave": plantilla, **srv.PLANTILLAS[plantilla]}, admin, ip_cliente(request)))


@router.put("/{clave}")
def editar(clave: str, datos: ModuloIn, request: Request, db: Session = Depends(get_db),
           admin: Usuario = Depends(requiere_rol(*ADMIN_GESTION))):
    """Cada cambio crea una nueva versión; los registros anteriores conservan la versión con la que se hicieron."""
    m = db.scalars(select(ModuloDinamico).where(ModuloDinamico.clave == clave)).first()
    if not m:
        raise HTTPException(404, "Módulo no encontrado")
    _validar_roles(datos.roles_lectura + datos.roles_escritura)
    try:
        campos = srv.validar_definicion(datos.campos)
    except srv.ErrorModulo as exc:
        raise HTTPException(422, str(exc))
    for k, v in datos.model_dump(exclude={"clave", "campos"}).items():
        setattr(m, k, v)
    m.campos, m.version = campos, m.version + 1
    registrar_evento(db, accion="MODULO_EDITADO", entidad="modulo", entidad_id=m.id, datos=_salida(m), usuario_id=admin.id,
                     ip=ip_cliente(request))
    db.commit()
    return _salida(m)


@router.get("/{clave}/registros")
def registros(clave: str, paciente_id: uuid.UUID | None = None, db: Session = Depends(get_db),
              usuario: Usuario = Depends(requiere_rol(*PERSONAL))):
    m = _modulo(db, clave)
    if not (_puede(usuario, m.roles_lectura) or _puede(usuario, m.roles_escritura)):
        raise HTTPException(403, "Su rol no tiene acceso a este módulo")
    q = select(RegistroModulo).where(RegistroModulo.modulo_id == m.id).order_by(RegistroModulo.creado_en.desc()).limit(500)
    if paciente_id:
        q = q.where(RegistroModulo.paciente_id == paciente_id)
    elif not _puede(usuario, m.roles_lectura):
        q = q.where(RegistroModulo.autor_id == usuario.id)  # quien solo escribe ve únicamente sus registros
    return [{"id": str(r.id), "paciente_id": str(r.paciente_id) if r.paciente_id else None, "datos": r.datos,
             "sellado": r.sellado, "hash": r.hash_contenido, "autor": r.autor.nombre_completo, "creado_en": r.creado_en,
             "version_modulo": r.version_modulo} for r in db.scalars(q).all()]


@router.post("/{clave}/registros", status_code=201)
def registrar(clave: str, datos: RegistroIn, request: Request, db: Session = Depends(get_db),
              usuario: Usuario = Depends(requiere_rol(*PERSONAL))):
    m = _modulo(db, clave)
    if not _puede(usuario, m.roles_escritura):
        raise HTTPException(403, "Su rol no puede registrar en este módulo")
    if m.por_paciente and (not datos.paciente_id or not db.get(Paciente, datos.paciente_id)):
        raise HTTPException(422, "Este módulo requiere un paciente válido")
    try:
        limpios = srv.validar_registro(m.campos, datos.datos)
    except srv.ErrorModulo as exc:
        raise HTTPException(422, str(exc))
    contenido = {"modulo": m.clave, "version": m.version, "paciente_id": str(datos.paciente_id) if datos.paciente_id else None,
                 "datos": limpios, "autor": str(usuario.id)}
    r = RegistroModulo(modulo_id=m.id, version_modulo=m.version, paciente_id=datos.paciente_id if m.por_paciente else None,
                       datos=limpios, sellado=m.sellar_al_guardar, hash_contenido=sha256(json_canonico(contenido)),
                       autor_id=usuario.id)
    db.add(r)
    db.flush()
    registrar_evento(db, accion="MODULO_REGISTRO", entidad=f"modulo:{m.clave}", entidad_id=r.id, datos=contenido,
                     usuario_id=usuario.id, ip=ip_cliente(request))
    db.commit()
    return {"id": str(r.id), "sellado": r.sellado, "hash": r.hash_contenido}


@router.put("/{clave}/registros/{registro_id}")
def editar_registro(clave: str, registro_id: uuid.UUID, datos: RegistroIn, request: Request, db: Session = Depends(get_db),
                    usuario: Usuario = Depends(requiere_rol(*PERSONAL))):
    m = _modulo(db, clave)
    r = db.get(RegistroModulo, registro_id)
    if not r or r.modulo_id != m.id:
        raise HTTPException(404, "Registro no encontrado")
    if r.sellado:
        raise HTTPException(409, "El registro está sellado y es inalterable")
    if r.autor_id != usuario.id and usuario.rol != "admin":
        raise HTTPException(403, "Solo el autor puede editar el registro")
    try:
        limpios = srv.validar_registro(m.campos, datos.datos)
    except srv.ErrorModulo as exc:
        raise HTTPException(422, str(exc))
    r.datos, r.version_modulo = limpios, m.version
    r.hash_contenido = sha256(json_canonico({"modulo": m.clave, "datos": limpios, "registro": str(r.id)}))
    registrar_evento(db, accion="MODULO_REGISTRO_EDITADO", entidad=f"modulo:{m.clave}", entidad_id=r.id, datos=limpios,
                     usuario_id=usuario.id, ip=ip_cliente(request))
    db.commit()
    return {"id": str(r.id), "hash": r.hash_contenido}
