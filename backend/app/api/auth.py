import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import ip_cliente, requiere_rol, usuario_actual
from app.core.security import crear_token, hash_password, validar_fortaleza, verificar_password
from app.models import Usuario
from app.schemas import Token, UsuarioCrear, UsuarioOut
from app.services.ledger import a_utc, registrar_evento

router = APIRouter(prefix="/api/auth", tags=["Autenticación y usuarios"])


@router.post("/login", response_model=Token)
def login(request: Request, form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    usuario = db.scalars(select(Usuario).where(Usuario.email == form.username.lower().strip())).first()
    ahora = datetime.now(timezone.utc)
    if usuario and usuario.bloqueado_hasta and a_utc(usuario.bloqueado_hasta) > ahora:
        raise HTTPException(status.HTTP_423_LOCKED, "Usuario bloqueado temporalmente por intentos fallidos")
    if not usuario or not usuario.activo or not verificar_password(form.password, usuario.hashed_password):
        if usuario:
            usuario.intentos_fallidos += 1
            if usuario.intentos_fallidos >= settings.MAX_INTENTOS_LOGIN:
                usuario.bloqueado_hasta = ahora + timedelta(minutes=settings.MINUTOS_BLOQUEO)
                usuario.intentos_fallidos = 0
            registrar_evento(db, accion="LOGIN_FALLIDO", entidad="usuario", entidad_id=usuario.id, ip=ip_cliente(request))
            db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Correo o contraseña incorrectos")
    usuario.intentos_fallidos = 0
    usuario.bloqueado_hasta = None
    registrar_evento(db, accion="LOGIN", entidad="usuario", entidad_id=usuario.id, usuario_id=usuario.id, ip=ip_cliente(request))
    db.commit()
    return Token(access_token=crear_token(str(usuario.id), usuario.rol), usuario=UsuarioOut.model_validate(usuario))


@router.get("/yo", response_model=UsuarioOut)
def yo(usuario: Usuario = Depends(usuario_actual)):
    return usuario


@router.get("/usuarios", response_model=list[UsuarioOut])
def listar_usuarios(db: Session = Depends(get_db), _: Usuario = Depends(requiere_rol("admin"))):
    return db.scalars(select(Usuario).order_by(Usuario.apellidos)).all()


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
