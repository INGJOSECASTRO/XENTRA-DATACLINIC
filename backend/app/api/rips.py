import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import FACTURACION, ip_cliente, requiere_rol
from app.models import Atencion, Usuario
from app.schemas import RipsIn, RipsOut
from app.services.ledger import registrar_evento
from app.services.rips import generar_rips

router = APIRouter(prefix="/api/rips", tags=["RIPS (Resolución 2275 de 2023)"])


def _generar(datos: RipsIn, db: Session):
    atenciones = db.scalars(select(Atencion).where(Atencion.id.in_(datos.atencion_ids))).all()
    if len(atenciones) != len(set(datos.atencion_ids)):
        raise HTTPException(404, "Una o más atenciones no existen")
    return generar_rips(atenciones, datos.num_factura, datos.tipo_nota, datos.num_nota)


@router.post("/generar", response_model=RipsOut)
def generar(datos: RipsIn, request: Request, db: Session = Depends(get_db),
            usuario: Usuario = Depends(requiere_rol(*FACTURACION))):
    rips, errores = _generar(datos, db)
    registrar_evento(db, accion="RIPS_GENERADO", entidad="factura", entidad_id=None,
                     datos=rips, usuario_id=usuario.id, ip=ip_cliente(request))
    db.commit()
    return RipsOut(valido=not errores, errores=errores, rips=rips)


@router.post("/descargar")
def descargar(datos: RipsIn, db: Session = Depends(get_db), _: Usuario = Depends(requiere_rol(*FACTURACION))):
    rips, errores = _generar(datos, db)
    if errores:
        raise HTTPException(422, {"errores": errores})
    contenido = json.dumps(rips, ensure_ascii=False, indent=2)
    return Response(contenido, media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="RIPS_{datos.num_factura}.json"'})
