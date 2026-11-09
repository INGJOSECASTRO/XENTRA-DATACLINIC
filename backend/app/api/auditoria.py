from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import requiere_rol, usuario_actual
from app.models import Atencion, BloqueLedger, Paciente, Usuario
from app.schemas import BloqueOut
from app.services.ledger import verificar_cadena

router = APIRouter(prefix="/api/auditoria", tags=["Auditoría y ledger (blockchain)"])


@router.get("/ledger", response_model=list[BloqueOut])
def bloques(entidad_id: str | None = None, accion: str | None = None, limite: int = Query(100, le=1000),
            db: Session = Depends(get_db), _: Usuario = Depends(requiere_rol("auditor", "admin"))):
    q = select(BloqueLedger).order_by(BloqueLedger.id.desc()).limit(limite)
    if entidad_id:
        q = q.where(BloqueLedger.entidad_id == entidad_id)
    if accion:
        q = q.where(BloqueLedger.accion == accion)
    return db.scalars(q).all()


@router.get("/verificar-cadena")
def verificar(db: Session = Depends(get_db), _: Usuario = Depends(requiere_rol("auditor", "admin"))):
    return verificar_cadena(db)


@router.get("/estadisticas")
def estadisticas(db: Session = Depends(get_db), _: Usuario = Depends(usuario_actual)):
    contar = lambda m, *w: db.scalar(select(func.count()).select_from(m).where(*w)) or 0  # noqa: E731
    return {
        "pacientes": contar(Paciente),
        "atenciones": contar(Atencion),
        "atenciones_firmadas": contar(Atencion, Atencion.estado == "firmada"),
        "atenciones_borrador": contar(Atencion, Atencion.estado == "borrador"),
        "bloques_ledger": contar(BloqueLedger),
    }
