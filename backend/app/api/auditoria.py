from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import PERSONAL, requiere_rol
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
def estadisticas(db: Session = Depends(get_db), _: Usuario = Depends(requiere_rol(*PERSONAL))):
    contar = lambda m, *w: db.scalar(select(func.count()).select_from(m).where(*w)) or 0  # noqa: E731
    return {
        "pacientes": contar(Paciente),
        "atenciones": contar(Atencion),
        "atenciones_firmadas": contar(Atencion, Atencion.estado == "firmada"),
        "atenciones_borrador": contar(Atencion, Atencion.estado == "borrador"),
        "bloques_ledger": contar(BloqueLedger),
    }


@router.post("/anclar")
def anclar_ledger(db: Session = Depends(get_db), _: Usuario = Depends(requiere_rol("auditor", "admin"))):
    from app.services.anclaje import anclar

    try:
        a = anclar(db)
    except ValueError as exc:
        from fastapi import HTTPException

        raise HTTPException(409, str(exc))
    return {"id": a.id, "bloque": a.bloque_id, "hash": a.hash_raiz, "proveedor": a.proveedor, "estado": a.estado,
            "detalle": a.detalle}


@router.get("/anclajes")
def anclajes(db: Session = Depends(get_db), _: Usuario = Depends(requiere_rol("auditor", "admin"))):
    from app.services.anclaje import verificar_anclas

    return verificar_anclas(db)


@router.get("/estado-cadena")
def estado_cadena(db: Session = Depends(get_db), _: Usuario = Depends(requiere_rol(*PERSONAL))):
    """Resumen de la seguridad blockchain visible para todo el personal (sin detalles de los bloques)."""
    from app.models_ext import AnclajeLedger

    r = verificar_cadena(db)
    ancla = db.scalars(select(AnclajeLedger).order_by(AnclajeLedger.id.desc()).limit(1)).first()
    firmadas = db.scalar(select(func.count()).select_from(Atencion).where(Atencion.estado == "firmada")) or 0
    return {"valida": r["valida"], "total_bloques": r["total_bloques"], "folios_sellados": firmadas,
            "ultimo_anclaje": ancla.creado_en if ancla else None,
            "detalle": r.get("detalle")}
