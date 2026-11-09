"""Libro mayor inmutable (ledger) con encadenamiento de hashes SHA-256 + firma HMAC.

¿Por qué no una blockchain pública?
- La historia clínica es dato sensible (Ley 1581 de 2012): NUNCA debe ir a una red pública.
- Aquí solo se guardan HUELLAS (hashes) de los datos, nunca los datos clínicos.
- La cadena de hashes da la misma propiedad clave de una blockchain: cualquier
  alteración posterior es detectable. La firma HMAC (con llave fuera de la BD)
  impide que alguien con acceso a la BD "recalcule" la cadena completa.
- Opcionalmente, el hash del último bloque (raíz diaria) se puede "anclar" en una
  red pública (p. ej. OpenTimestamps/Bitcoin, Polygon) como sello de tiempo externo.
"""
import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import BloqueLedger

HASH_GENESIS = "0" * 64


def json_canonico(datos: Any) -> str:
    """Serializa de forma determinista (mismo dato => mismo texto => mismo hash)."""
    return json.dumps(datos, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def sha256(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def a_utc(fecha: datetime) -> datetime:
    """Normaliza a UTC (algunas BD devuelven fechas sin zona horaria)."""
    return fecha.replace(tzinfo=timezone.utc) if fecha.tzinfo is None else fecha.astimezone(timezone.utc)


def _hash_bloque(b: BloqueLedger) -> str:
    partes = [
        str(b.id),
        a_utc(b.marca_tiempo).isoformat(),
        b.usuario_id or "",
        b.accion,
        b.entidad,
        b.entidad_id or "",
        b.hash_datos,
        b.hash_anterior,
    ]
    return sha256("|".join(partes))


def _firmar(hash_bloque: str) -> str:
    return hmac.new(settings.LEDGER_HMAC_KEY.encode(), hash_bloque.encode(), hashlib.sha256).hexdigest()


def registrar_evento(
    db: Session,
    *,
    accion: str,
    entidad: str,
    entidad_id: Any = None,
    datos: Any = None,
    usuario_id: Any = None,
    ip: str | None = None,
) -> BloqueLedger:
    """Agrega un bloque al final de la cadena. Se confirma junto con la transacción del llamador."""
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        # Evita que dos peticiones simultáneas agreguen bloques con el mismo "anterior".
        db.execute(text("SELECT pg_advisory_xact_lock(424242)"))

    ultimo = db.scalars(select(BloqueLedger).order_by(BloqueLedger.id.desc()).limit(1)).first()
    bloque = BloqueLedger(
        id=(ultimo.id + 1) if ultimo else 1,
        marca_tiempo=datetime.now(timezone.utc).replace(microsecond=0),
        usuario_id=str(usuario_id) if usuario_id else None,
        accion=accion,
        entidad=entidad,
        entidad_id=str(entidad_id) if entidad_id else None,
        hash_datos=sha256(json_canonico(datos if datos is not None else {})),
        hash_anterior=ultimo.hash if ultimo else HASH_GENESIS,
        ip_origen=ip,
    )
    bloque.hash = _hash_bloque(bloque)
    bloque.firma = _firmar(bloque.hash)
    db.add(bloque)
    db.flush()
    return bloque


def verificar_cadena(db: Session) -> dict:
    """Recorre toda la cadena y reporta el primer bloque alterado, si existe."""
    anterior = HASH_GENESIS
    esperado_id = 1
    total = 0
    for b in db.scalars(select(BloqueLedger).order_by(BloqueLedger.id)).yield_per(1000):
        total += 1
        problema = None
        if b.id != esperado_id:
            problema = f"Falta el bloque {esperado_id} (posible eliminación)"
        elif b.hash_anterior != anterior:
            problema = "El enlace con el bloque anterior está roto"
        elif _hash_bloque(b) != b.hash:
            problema = "El contenido del bloque fue modificado"
        elif not hmac.compare_digest(_firmar(b.hash), b.firma):
            problema = "Firma HMAC inválida (bloque recalculado sin la llave)"
        if problema:
            return {"valida": False, "total_bloques": total, "bloque_con_error": b.id, "detalle": problema}
        anterior = b.hash
        esperado_id += 1
    return {"valida": True, "total_bloques": total, "ultimo_hash": anterior if total else None}
