"""Dependencias reutilizables: usuario autenticado y control de acceso por roles (RBAC)."""
import uuid

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decodificar_token
from app.models import Usuario

oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def usuario_actual(token: str = Depends(oauth2), db: Session = Depends(get_db)) -> Usuario:
    error = HTTPException(status.HTTP_401_UNAUTHORIZED, "Sesión inválida o vencida", {"WWW-Authenticate": "Bearer"})
    try:
        datos = decodificar_token(token)
        usuario = db.get(Usuario, uuid.UUID(datos["sub"]))
    except (jwt.PyJWTError, KeyError, ValueError):
        raise error
    if not usuario or not usuario.activo:
        raise error
    return usuario


def requiere_rol(*roles: str):
    """Uso: Depends(requiere_rol("medico", "admin"))"""

    def verificar(usuario: Usuario = Depends(usuario_actual)) -> Usuario:
        if usuario.rol not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Su rol no tiene permiso para esta acción")
        return usuario

    return verificar


def ip_cliente(request: Request) -> str | None:
    reenviada = request.headers.get("x-forwarded-for")
    if reenviada:
        return reenviada.split(",")[0].strip()
    return request.client.host if request.client else None


# Grupos de roles (matriz de permisos)
CLINICOS = ("medico", "enfermeria", "admin")
LECTURA_HC = ("medico", "enfermeria", "auditor", "admin")
REGISTRO_PACIENTES = ("medico", "enfermeria", "admisiones", "admin")
FACTURACION = ("facturacion", "admin")
