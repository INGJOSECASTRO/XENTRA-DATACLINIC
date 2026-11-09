"""Contraseñas (Argon2id, recomendado por OWASP) y tokens JWT."""
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import settings

_ph = PasswordHasher()
ALGORITMO = "HS256"


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verificar_password(password: str, hashed: str) -> bool:
    try:
        return _ph.verify(hashed, password)
    except (VerificationError, InvalidHashError):
        return False


def validar_fortaleza(password: str) -> str | None:
    """Devuelve un mensaje de error o None si la contraseña es aceptable."""
    if len(password) < 10:
        return "La contraseña debe tener mínimo 10 caracteres"
    if not any(c.isupper() for c in password) or not any(c.islower() for c in password):
        return "La contraseña debe tener mayúsculas y minúsculas"
    if not any(c.isdigit() for c in password):
        return "La contraseña debe tener al menos un número"
    return None


def crear_token(sub: str, rol: str) -> str:
    ahora = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "rol": rol,
        "iat": ahora,
        "exp": ahora + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITMO)


def decodificar_token(token: str) -> dict:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITMO])
