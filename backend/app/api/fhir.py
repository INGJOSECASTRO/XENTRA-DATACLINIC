"""API HL7 FHIR R4 (solo lectura) para intercambio con otras IPS, EPS y la plataforma IHCE."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import LECTURA_HC, ip_cliente, requiere_rol
from app.models import Atencion, Paciente, Usuario
from app.models_ext import Hospitalizacion, OrdenServicio
from app.services import fhir
from app.services.ledger import registrar_evento

router = APIRouter(prefix="/fhir", tags=["FHIR R4 (interoperabilidad)"])
TIPO = "application/fhir+json"


def _r(contenido: dict, status: int = 200) -> JSONResponse:
    return JSONResponse(contenido, status_code=status, media_type=TIPO)


def _no_encontrado(tipo: str, id_) -> JSONResponse:
    return _r({"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "not-found",
                                                              "diagnostics": f"{tipo}/{id_} no existe"}]}, 404)


def datos_paciente(db: Session, paciente_id):
    atenciones = db.scalars(select(Atencion).where(Atencion.paciente_id == paciente_id, Atencion.estado == "firmada")
                            .order_by(Atencion.fecha_inicio)).all()
    hosp = db.scalars(select(Hospitalizacion).where(Hospitalizacion.paciente_id == paciente_id)).all()
    labs = db.scalars(select(OrdenServicio).where(OrdenServicio.paciente_id == paciente_id,
                                                  OrdenServicio.estado == "validada")).all()
    return atenciones, hosp, labs


@router.get("/metadata")
def metadata():
    return _r(fhir.capability())


@router.get("/Patient")
def buscar_pacientes(identifier: str, db: Session = Depends(get_db), _: Usuario = Depends(requiere_rol(*LECTURA_HC))):
    """identifier=CC|1020304050  (tipo|número)."""
    tipo, _, numero = identifier.rpartition("|")
    q = select(Paciente).where(Paciente.numero_documento == numero)
    if tipo:
        q = q.where(Paciente.tipo_documento == tipo.rsplit("/", 1)[-1])
    return _r(fhir.bundle([fhir.patient(p) for p in db.scalars(q).all()]))


@router.get("/Patient/{paciente_id}")
def leer_paciente(paciente_id: uuid.UUID, db: Session = Depends(get_db), _: Usuario = Depends(requiere_rol(*LECTURA_HC))):
    p = db.get(Paciente, paciente_id)
    return _r(fhir.patient(p)) if p else _no_encontrado("Patient", paciente_id)


@router.get("/Patient/{paciente_id}/$everything")
def todo(paciente_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
         usuario: Usuario = Depends(requiere_rol(*LECTURA_HC))):
    p = db.get(Paciente, paciente_id)
    if not p:
        return _no_encontrado("Patient", paciente_id)
    registrar_evento(db, accion="FHIR_EXPORTACION", entidad="paciente", entidad_id=p.id, usuario_id=usuario.id,
                     ip=ip_cliente(request))
    db.commit()
    return _r(fhir.everything(p, *datos_paciente(db, p.id)))


@router.get("/Practitioner/{usuario_id}")
def profesional(usuario_id: uuid.UUID, db: Session = Depends(get_db), _: Usuario = Depends(requiere_rol(*LECTURA_HC))):
    u = db.get(Usuario, usuario_id)
    if not u or u.rol == "paciente":
        return _no_encontrado("Practitioner", usuario_id)
    return _r(fhir.practitioner(u))


@router.get("/{tipo}")
def buscar_por_paciente(tipo: str, patient: uuid.UUID, db: Session = Depends(get_db),
                        _: Usuario = Depends(requiere_rol(*LECTURA_HC))):
    """Encounter | Condition | MedicationRequest | Procedure | Observation ?patient={id}"""
    atenciones, hosp, labs = datos_paciente(db, patient)
    recursos: list[dict] = []
    if tipo == "Encounter":
        recursos = [fhir.encounter_atencion(a) for a in atenciones] + [fhir.encounter_hospitalizacion(h) for h in hosp]
    elif tipo == "Condition":
        recursos = [fhir.condition(d, a) for a in atenciones for d in a.diagnosticos]
    elif tipo == "MedicationRequest":
        recursos = [fhir.medication_request(r, a) for a in atenciones for r in a.prescripciones]
    elif tipo == "Procedure":
        recursos = [fhir.procedure(p, a) for a in atenciones for p in a.procedimientos]
    elif tipo == "Observation":
        recursos = [o for a in atenciones for o in fhir.observaciones_signos(a)] + \
                   [o for lab in labs for o in fhir.observaciones_laboratorio(lab)]
    else:
        raise HTTPException(404, f"Recurso {tipo} no soportado")
    return _r(fhir.bundle(recursos))
