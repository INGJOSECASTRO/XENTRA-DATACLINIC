"""Segundo factor de autenticación TOTP (RFC 6238), compatible con Google Authenticator,
Microsoft Authenticator, Authy, etc. Implementado sin dependencias externas."""
import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

import segno

PERIODO = 30
DIGITOS = 6


def nuevo_secreto() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _codigo(secreto: str, contador: int) -> str:
    clave = base64.b32decode(secreto + "=" * (-len(secreto) % 8), casefold=True)
    digest = hmac.new(clave, struct.pack(">Q", contador), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    numero = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % (10**DIGITOS)
    return str(numero).zfill(DIGITOS)


def codigo_actual(secreto: str, instante: float | None = None) -> str:
    return _codigo(secreto, int((instante or time.time()) // PERIODO))


def verificar(secreto: str, codigo: str, ventana: int = 1) -> bool:
    """Acepta el código actual y ±1 periodo (tolera relojes desfasados ~30 s)."""
    codigo = (codigo or "").strip().replace(" ", "")
    if not codigo.isdigit() or len(codigo) != DIGITOS:
        return False
    actual = int(time.time() // PERIODO)
    return any(hmac.compare_digest(_codigo(secreto, actual + d), codigo) for d in range(-ventana, ventana + 1))


def uri(secreto: str, cuenta: str, emisor: str = "XENTRA DATACLINIC") -> str:
    return f"otpauth://totp/{quote(emisor)}:{quote(cuenta)}?secret={secreto}&issuer={quote(emisor)}&digits={DIGITOS}&period={PERIODO}"


def qr_svg(texto: str) -> str:
    return segno.make(texto, error="m").svg_inline(scale=5)
