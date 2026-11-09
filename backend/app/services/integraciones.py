"""Integraciones externas: DIAN (factura electrónica) y MUV del Ministerio (validación FEV-RIPS).

Cada integración tiene dos modos (variables *_MODO en .env):
- "simulado": respuestas de prueba para desarrollar y capacitar SIN enviar nada.
- "real":     llamadas HTTP reales.

DIAN: la factura electrónica se emite a través de un PROVEEDOR TECNOLÓGICO autorizado por la DIAN
(o software propio habilitado). Cada proveedor tiene su propia API: adapte `DianReal.emitir` al
contrato de su proveedor (entrada: datos de la factura; salida: CUFE + XML firmado en base64).

MUV: el Ministerio publica la "API FEV-RIPS" (se despliega como contenedor en la infraestructura del
prestador). Los nombres de los endpoints usados abajo siguen la documentación técnica publicada;
VERIFÍQUELOS contra el manual técnico vigente antes de producción.
"""
import base64
import hashlib
import json
import logging
from datetime import datetime, timezone

import httpx

from app.core.config import settings

log = logging.getLogger(__name__)


class ErrorIntegracion(Exception):
    pass


# ----------------------------------------------------------------------------- DIAN
def _xml_simulado(factura, cufe: str) -> str:
    xml = (f'<?xml version="1.0" encoding="UTF-8"?><Invoice><ID>{factura.numero}</ID><UUID>{cufe}</UUID>'
           f"<IssueDate>{factura.fecha_emision:%Y-%m-%d}</IssueDate><Total>{factura.total}</Total>"
           f"<Note>DOCUMENTO SIMULADO - SIN VALIDEZ FISCAL</Note></Invoice>")
    return base64.b64encode(xml.encode()).decode()


class DianSimulado:
    def emitir(self, factura) -> dict:
        semilla = f"{factura.numero}{factura.fecha_emision:%Y-%m-%d%H:%M:%S}{factura.total}{settings.PRESTADOR_NIT}{factura.nit_pagador}"
        cufe = hashlib.sha384(semilla.encode()).hexdigest()
        return {"cufe": cufe, "xml_base64": _xml_simulado(factura, cufe), "estado": "ACEPTADA (SIMULADO)"}


class DianReal:
    def emitir(self, factura) -> dict:
        if not settings.DIAN_PROVEEDOR_URL:
            raise ErrorIntegracion("Configure DIAN_PROVEEDOR_URL y DIAN_PROVEEDOR_TOKEN")
        cuerpo = {
            "numero": factura.numero, "prefijo": factura.prefijo, "consecutivo": factura.consecutivo,
            "fecha": factura.fecha_emision.isoformat(), "emisor_nit": settings.PRESTADOR_NIT,
            "adquiriente": {"nit": factura.nit_pagador, "nombre": factura.nombre_pagador},
            "sector_salud": {"modalidad_pago": factura.modalidad_pago, "num_contrato": factura.num_contrato},
            "items": [{"codigo": i.codigo, "descripcion": i.descripcion, "cantidad": i.cantidad,
                       "valor_unitario": float(i.valor_unitario)} for i in factura.items],
            "total": float(factura.total), "pagos_moderadores": float(factura.pagos_moderadores),
        }
        try:
            r = httpx.post(settings.DIAN_PROVEEDOR_URL, json=cuerpo, timeout=60,
                           headers={"Authorization": f"Bearer {settings.DIAN_PROVEEDOR_TOKEN}"})
            r.raise_for_status()
        except httpx.HTTPError as exc:
            raise ErrorIntegracion(f"Error con el proveedor de facturación: {exc}") from exc
        datos = r.json()
        if not datos.get("cufe"):
            raise ErrorIntegracion(f"El proveedor no devolvió CUFE: {datos}")
        return datos


# ----------------------------------------------------------------------------- MUV (FEV-RIPS)
class MuvSimulado:
    def validar(self, rips: dict, xml_base64: str | None) -> dict:
        usuarios = rips.get("usuarios", [])
        if not usuarios:
            return {"ResultState": False, "ResultadosValidacion": [{"Clase": "RECHAZADO", "Descripcion": "Sin usuarios"}]}
        cuv = hashlib.sha384(json.dumps(rips, sort_keys=True).encode()).hexdigest()
        return {"ResultState": True, "CodigoUnicoValidacion": cuv, "NumFactura": rips.get("numFactura"),
                "FechaRadicacion": datetime.now(timezone.utc).isoformat(), "ResultadosValidacion": [],
                "Simulado": True}


class MuvReal:
    def _token(self, cliente: httpx.Client) -> str:
        r = cliente.post("/api/Auth/LoginSISPRO", json={
            "persona": {"identificacion": {"tipo": settings.MUV_TIPO_USUARIO, "numero": settings.MUV_USUARIO}},
            "clave": settings.MUV_CLAVE, "nit": settings.PRESTADOR_NIT,
        })
        r.raise_for_status()
        token = r.json().get("token")
        if not token:
            raise ErrorIntegracion("El MUV no devolvió token de acceso")
        return token

    def validar(self, rips: dict, xml_base64: str | None) -> dict:
        if not settings.MUV_USUARIO:
            raise ErrorIntegracion("Configure MUV_URL, MUV_USUARIO y MUV_CLAVE")
        try:
            with httpx.Client(base_url=settings.MUV_URL, timeout=120) as cliente:
                token = self._token(cliente)
                r = cliente.post("/api/PaquetesFevRips/CargarFevRips", json={"rips": rips, "xmlFevFile": xml_base64},
                                 headers={"Authorization": f"Bearer {token}"})
                return r.json()
        except httpx.HTTPError as exc:
            raise ErrorIntegracion(f"Error de comunicación con el MUV: {exc}") from exc


def dian():
    return DianReal() if settings.DIAN_MODO == "real" else DianSimulado()


def muv():
    return MuvReal() if settings.MUV_MODO == "real" else MuvSimulado()


# ----------------------------------------------------------------------------- Notificaciones
def notificar(destino: str | None, mensaje: str) -> dict:
    """Punto de integración para WhatsApp Business / SMS / correo. Hoy registra el mensaje en el log.
    Conecte aquí su proveedor (Twilio, Meta WhatsApp Cloud API, Amazon SES, etc.)."""
    if not destino:
        return {"enviado": False, "motivo": "Sin teléfono/correo"}
    log.info("NOTIFICACIÓN a %s: %s", destino[-4:].rjust(len(destino), "*"), mensaje)
    return {"enviado": True, "canal": "log", "destino": destino}
