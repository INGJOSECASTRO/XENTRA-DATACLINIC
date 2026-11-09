"""Verificación PÚBLICA de autenticidad de documentos (lo que lee el código QR).

No requiere sesión y NO devuelve datos clínicos ni personales: solo si el documento es auténtico.
"""
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models import Atencion
from app.models_ext import Consentimiento, Hospitalizacion, OrdenServicio
from app.services import historia
from app.services.pdf import fecha

router = APIRouter(prefix="/api/publico", tags=["Verificación pública"])


@router.get("/verificar/{tipo}/{doc_id}")
def verificar(tipo: str, doc_id: uuid.UUID, h: str = "", db: Session = Depends(get_db)):
    respuesta = {"institucion": settings.PRESTADOR_RAZON_SOCIAL, "tipo": tipo, "valido": False}
    if tipo == "atencion":
        a = db.get(Atencion, doc_id)
        if a and a.estado == "firmada":
            actual = historia.calcular_hash(a)
            respuesta.update(valido=actual == a.hash_contenido == h, fecha_firma=fecha(a.firmada_en),
                             profesional_registro=a.profesional.registro_profesional)
    elif tipo == "epicrisis":
        x = db.get(Hospitalizacion, doc_id)
        if x and x.hash_epicrisis:
            respuesta.update(valido=x.hash_epicrisis == h, fecha_firma=fecha(x.fecha_egreso))
    elif tipo == "consentimiento":
        x = db.get(Consentimiento, doc_id)
        if x:
            respuesta.update(valido=x.hash_contenido == h, fecha_firma=fecha(x.fecha))
    elif tipo == "resultado":
        x = db.get(OrdenServicio, doc_id)
        if x and x.hash_resultado:
            respuesta.update(valido=x.hash_resultado == h, fecha_firma=fecha(x.fecha_resultado))
    respuesta["mensaje"] = ("Documento auténtico: coincide con el registro sellado de la institución." if respuesta["valido"]
                            else "No se pudo verificar: el documento no existe, fue alterado o el código no corresponde.")
    return respuesta
