import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import ip_cliente, requiere_rol, usuario_actual
from app.core.security import crear_token, decodificar_token, hash_password, validar_fortaleza, verificar_password
from app.models import Usuario
from app.schemas import CambioClave, MfaCodigo, MfaVerificar, Token, UsuarioCrear, UsuarioOut
from app.services import mfa
from app.services.ledger import a_utc, registrar_evento

router = APIRouter(prefix="/api/auth", tags=["Autenticación y usuarios"])


def _token_acceso(db: Session, usuario: Usuario, ip: str | None, accion: str = "LOGIN") -> Token:
    usuario.intentos_fallidos = 0
    usuario.bloqueado_hasta = None
    registrar_evento(db, accion=accion, entidad="usuario", entidad_id=usuario.id, usuario_id=usuario.id, ip=ip)
    db.commit()
    return Token(access_token=crear_token(str(usuario.id), usuario.rol), usuario=UsuarioOut.model_validate(usuario))


def _fallo(db: Session, usuario: Usuario | None, ip: str | None, accion: str = "LOGIN_FALLIDO") -> None:
    if usuario:
        usuario.intentos_fallidos += 1
        if usuario.intentos_fallidos >= settings.MAX_INTENTOS_LOGIN:
            usuario.bloqueado_hasta = datetime.now(timezone.utc) + timedelta(minutes=settings.MINUTOS_BLOQUEO)
            usuario.intentos_fallidos = 0
        registrar_evento(db, accion=accion, entidad="usuario", entidad_id=usuario.id, ip=ip)
        db.commit()


def _bloqueado(usuario: Usuario | None) -> bool:
    return bool(usuario and usuario.bloqueado_hasta and a_utc(usuario.bloqueado_hasta) > datetime.now(timezone.utc))


@router.post("/login", response_model=Token)
def login(request: Request, form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    usuario = db.scalars(select(Usuario).where(Usuario.email == form.username.lower().strip())).first()
    if _bloqueado(usuario):
        raise HTTPException(status.HTTP_423_LOCKED, "Usuario bloqueado temporalmente por intentos fallidos")
    if not usuario or not usuario.activo or not verificar_password(form.password, usuario.hashed_password):
        _fallo(db, usuario, ip_cliente(request))
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Correo o contraseña incorrectos")
    if usuario.mfa_activo:
        # Paso 2: se entrega un token temporal que SOLO sirve para enviar el código TOTP.
        return Token(mfa_requerido=True, token_mfa=crear_token(str(usuario.id), usuario.rol, "mfa", 5),
                     usuario=UsuarioOut.model_validate(usuario))
    return _token_acceso(db, usuario, ip_cliente(request))


@router.post("/mfa/verificar", response_model=Token)
def mfa_verificar(datos: MfaVerificar, request: Request, db: Session = Depends(get_db)):
    try:
        carga = decodificar_token(datos.token_mfa)
        if carga.get("tipo") != "mfa":
            raise ValueError
        usuario = db.get(Usuario, uuid.UUID(carga["sub"]))
    except (jwt.PyJWTError, ValueError, KeyError):
        raise HTTPException(401, "El paso de verificación venció; inicie sesión de nuevo")
    if not usuario or not usuario.activo or _bloqueado(usuario):
        raise HTTPException(401, "Usuario no disponible")
    if not usuario.totp_secreto or not mfa.verificar(usuario.totp_secreto, datos.codigo):
        _fallo(db, usuario, ip_cliente(request), "MFA_FALLIDO")
        raise HTTPException(401, "Código de verificación incorrecto")
    return _token_acceso(db, usuario, ip_cliente(request), "LOGIN_MFA")


@router.post("/renovar", response_model=Token)
def renovar(usuario: Usuario = Depends(usuario_actual)):
    """Renueva el token mientras el usuario está activo (sesión deslizante)."""
    return Token(access_token=crear_token(str(usuario.id), usuario.rol), usuario=UsuarioOut.model_validate(usuario))


@router.get("/yo", response_model=UsuarioOut)
def yo(usuario: Usuario = Depends(usuario_actual)):
    return usuario


@router.post("/mfa/configurar")
def mfa_configurar(db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_actual)):
    """Genera un secreto nuevo. Se activa solo cuando el usuario confirma un código válido."""
    if usuario.mfa_activo:
        raise HTTPException(409, "El segundo factor ya está activo")
    usuario.totp_secreto = mfa.nuevo_secreto()
    db.commit()
    enlace = mfa.uri(usuario.totp_secreto, usuario.email)
    return {"secreto": usuario.totp_secreto, "uri": enlace, "qr_svg": mfa.qr_svg(enlace)}


@router.post("/mfa/activar", response_model=UsuarioOut)
def mfa_activar(datos: MfaCodigo, request: Request, db: Session = Depends(get_db),
                usuario: Usuario = Depends(usuario_actual)):
    if not usuario.totp_secreto or not mfa.verificar(usuario.totp_secreto, datos.codigo):
        raise HTTPException(422, "Código incorrecto. Revise la hora de su celular e intente de nuevo")
    usuario.mfa_activo = True
    registrar_evento(db, accion="MFA_ACTIVADO", entidad="usuario", entidad_id=usuario.id, usuario_id=usuario.id,
                     ip=ip_cliente(request))
    db.commit()
    return usuario


@router.post("/mfa/desactivar/{usuario_id}", response_model=UsuarioOut)
def mfa_desactivar(usuario_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
                   admin: Usuario = Depends(requiere_rol("admin"))):
    """Para usuarios que perdieron el celular (el administrador verifica su identidad)."""
    usuario = db.get(Usuario, usuario_id)
    if not usuario:
        raise HTTPException(404, "Usuario no encontrado")
    usuario.mfa_activo = False
    usuario.totp_secreto = None
    registrar_evento(db, accion="MFA_DESACTIVADO", entidad="usuario", entidad_id=usuario.id, usuario_id=admin.id,
                     ip=ip_cliente(request))
    db.commit()
    return usuario


@router.post("/cambiar-clave", status_code=204)
def cambiar_clave(datos: CambioClave, request: Request, db: Session = Depends(get_db),
                  usuario: Usuario = Depends(usuario_actual)):
    if not verificar_password(datos.actual, usuario.hashed_password):
        raise HTTPException(422, "La contraseña actual no es correcta")
    if error := validar_fortaleza(datos.nueva):
        raise HTTPException(422, error)
    usuario.hashed_password = hash_password(datos.nueva)
    registrar_evento(db, accion="CLAVE_CAMBIADA", entidad="usuario", entidad_id=usuario.id, usuario_id=usuario.id,
                     ip=ip_cliente(request))
    db.commit()


@router.get("/usuarios", response_model=list[UsuarioOut])
def listar_usuarios(rol: str | None = None, db: Session = Depends(get_db),
                    _: Usuario = Depends(requiere_rol("admin", "admisiones", "medico", "enfermeria", "facturacion"))):
    q = select(Usuario).where(Usuario.rol != "paciente").order_by(Usuario.apellidos)
    if rol:
        q = q.where(Usuario.rol == rol)
    return db.scalars(q).all()


@router.post("/usuarios", response_model=UsuarioOut, status_code=201)
def crear_usuario(
    datos: UsuarioCrear, request: Request, db: Session = Depends(get_db), admin: Usuario = Depends(requiere_rol("admin"))
):
    if error := validar_fortaleza(datos.password):
        raise HTTPException(422, error)
    if db.scalars(select(Usuario).where(Usuario.email == datos.email.lower())).first():
        raise HTTPException(409, "Ya existe un usuario con ese correo")
    if datos.rol == "medico" and not datos.registro_profesional:
        raise HTTPException(422, "El médico debe tener registro profesional (ReTHUS)")
    usuario = Usuario(**datos.model_dump(exclude={"password", "email"}), email=datos.email.lower(),
                      hashed_password=hash_password(datos.password))
    db.add(usuario)
    db.flush()
    registrar_evento(db, accion="USUARIO_CREADO", entidad="usuario", entidad_id=usuario.id,
                     datos={"email": usuario.email, "rol": usuario.rol}, usuario_id=admin.id, ip=ip_cliente(request))
    db.commit()
    return usuario


@router.patch("/usuarios/{usuario_id}/estado", response_model=UsuarioOut)
def cambiar_estado(usuario_id: uuid.UUID, activo: bool, request: Request, db: Session = Depends(get_db),
                   admin: Usuario = Depends(requiere_rol("admin"))):
    usuario = db.get(Usuario, usuario_id)
    if not usuario:
        raise HTTPException(404, "Usuario no encontrado")
    if usuario.id == admin.id:
        raise HTTPException(400, "No puede desactivarse a sí mismo")
    usuario.activo = activo
    registrar_evento(db, accion="USUARIO_ACTIVADO" if activo else "USUARIO_DESACTIVADO", entidad="usuario",
                     entidad_id=usuario.id, usuario_id=admin.id, ip=ip_cliente(request))
    db.commit()
    return usuario
