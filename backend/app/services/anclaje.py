"""Anclaje externo del ledger: publica SOLO el hash del último bloque como sello de tiempo.

- local:           registra el ancla en la BD (útil si se combina con un sellado acreditado externo).
- opentimestamps:  envía el hash a los calendarios públicos de OpenTimestamps (anclaje en Bitcoin, gratuito).
                   El comprobante (.ots) se guarda en base64 y puede verificarse con el cliente 'ots'.
Ningún dato de pacientes sale del servidor: solo 32 bytes de hash.
"""
import base64

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import BloqueLedger
from app.models_ext import AnclajeLedger


def anclar(db: Session) -> AnclajeLedger:
    ultimo = db.scalars(select(BloqueLedger).order_by(BloqueLedger.id.desc()).limit(1)).first()
    if not ultimo:
        raise ValueError("El ledger está vacío")
    ancla = AnclajeLedger(bloque_id=ultimo.id, hash_raiz=ultimo.hash, proveedor=settings.ANCLAJE_MODO, estado="local")
    if settings.ANCLAJE_MODO == "opentimestamps":
        comprobantes, errores = [], []
        for calendario in [c.strip() for c in settings.OTS_CALENDARIOS.split(",") if c.strip()]:
            try:
                r = httpx.post(f"{calendario}/digest", content=bytes.fromhex(ultimo.hash), timeout=20,
                               headers={"Accept": "application/vnd.opentimestamps.v1",
                                        "User-Agent": "xentra-dataclinic-ledger"})
                r.raise_for_status()
                comprobantes.append(f"{calendario}|{base64.b64encode(r.content).decode()}")
            except httpx.HTTPError as exc:
                errores.append(f"{calendario}: {exc}")
        ancla.estado = "enviado" if comprobantes else "fallido"
        ancla.comprobante = "\n".join(comprobantes) or None
        ancla.detalle = "; ".join(errores) or "Pendiente de confirmación en Bitcoin (algunas horas)"
    db.add(ancla)
    db.commit()
    return ancla


def verificar_anclas(db: Session) -> list[dict]:
    salida = []
    for a in db.scalars(select(AnclajeLedger).order_by(AnclajeLedger.id)).all():
        bloque = db.get(BloqueLedger, a.bloque_id)
        salida.append({"id": a.id, "bloque": a.bloque_id, "fecha": a.creado_en, "proveedor": a.proveedor, "estado": a.estado,
                       "coincide": bool(bloque and bloque.hash == a.hash_raiz), "hash": a.hash_raiz})
    return salida
