"""Dependencias reutilizables: usuario autenticado y control de acceso por roles (RBAC)."""
import uuid

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import decodificar_token
from app.models import Usuario

oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# Rutas permitidas mientras el usuario tiene una acción de seguridad pendiente
# (cambiar la clave temporal o activar el segundo factor obligatorio para su rol).
RUTAS_SIEMPRE_PERMITIDAS = ("/api/auth/yo", "/api/auth/cambiar-clave", "/api/auth/mfa/configurar",
                            "/api/auth/mfa/activar", "/api/auth/renovar", "/api/sistema/avisos")


def roles_mfa_obligatorio() -> set[str]:
    return {r.strip() for r in settings.MFA_OBLIGATORIO_ROLES.split(",") if r.strip()}


def accion_pendiente(usuario: Usuario) -> str | None:
    if settings.CAMBIO_CLAVE_PRIMER_INGRESO and usuario.debe_cambiar_clave:
        return "Debe cambiar su contraseña temporal antes de continuar"
    if usuario.rol in roles_mfa_obligatorio() and not usuario.mfa_activo:
        return "Su rol exige el segundo factor de autenticación (MFA): actívelo en Mi cuenta y seguridad"
    return None


def usuario_actual(request: Request, token: str = Depends(oauth2), db: Session = Depends(get_db)) -> Usuario:
    error = HTTPException(status.HTTP_401_UNAUTHORIZED, "Sesión inválida o vencida", {"WWW-Authenticate": "Bearer"})
    try:
        datos = decodificar_token(token)
        if datos.get("tipo", "acceso") != "acceso":
            raise error
        usuario = db.get(Usuario, uuid.UUID(datos["sub"]))
    except (jwt.PyJWTError, KeyError, ValueError):
        raise error
    if not usuario or not usuario.activo:
        raise error
    if usuario.rol == "paciente" and not settings.PORTAL_PACIENTE_ACTIVO:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "El portal del paciente no está habilitado en esta institución")
    if (motivo := accion_pendiente(usuario)) and request.url.path not in RUTAS_SIEMPRE_PERMITIDAS:
        raise HTTPException(status.HTTP_403_FORBIDDEN, motivo, {"X-Accion-Requerida": "seguridad"})
    return usuario


def requiere_rol(*roles: str):
    """Uso: Depends(requiere_rol("medico", "admin"))"""

    def verificar(usuario: Usuario = Depends(usuario_actual)) -> Usuario:
        if usuario.rol not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Su rol no tiene permiso para esta acción")
        return usuario

    return verificar


def ip_cliente(request: Request) -> str | None:
    reenviada = request.headers.get("x-forwarded-for")
    if reenviada:
        return reenviada.split(",")[0].strip()
    return request.client.host if request.client else None


# ---------------------------------------------------------------------------------------------
# Matriz de permisos (ver docs/manuales/04-PROTOCOLOS-SEGURIDAD.md)
#  admin               Dirección médico-administrativa (profesional de salud): todo, incluida la HC.
#  admin_tecnico       Sistemas: usuarios, sedes, camas, módulos, avisos, soporte, seguridad. SIN historia clínica.
#  medico / enfermeria Equipo de salud.
#  estudiante          Internos y residentes (Decreto 2376 de 2010): registran en borrador; firma el docente (refrendo).
#  auditor             Auditor MÉDICO (profesional de salud): lectura de HC, cuentas, calidad, ledger.
#  auditor_sistemas    Auditoría de seguridad: ledger, estado del sistema, indicadores agregados. SIN historia clínica.
#  laboratorio         Bacteriólogo / radiólogo: resultados y VALIDACIÓN (Ley 841 de 2003).
#  auxiliar_laboratorio Toma de muestras y digitación de resultados, sin validar.
#  farmacia, facturacion, admisiones, paciente (portal, desactivable).
# ---------------------------------------------------------------------------------------------
ADMIN_GESTION = ("admin", "admin_tecnico")
CLINICOS = ("medico", "enfermeria", "admin")
CLINICOS_FORMACION = CLINICOS + ("estudiante",)
MEDICOS = ("medico", "admin")
LECTURA_HC = ("medico", "enfermeria", "auditor", "admin", "estudiante")
REGISTRO_PACIENTES = ("medico", "enfermeria", "admisiones", "admin")
FACTURACION = ("facturacion", "admin")
AGENDA = ("admisiones", "medico", "enfermeria", "admin")
FARMACIA = ("farmacia", "admin")
LABORATORIO = ("laboratorio", "admin")
LABORATORIO_OPERATIVO = LABORATORIO + ("auxiliar_laboratorio",)
AUDITORIA_SEGURIDAD = ("auditor", "auditor_sistemas", "admin", "admin_tecnico")
PERSONAL = ("admin", "admin_tecnico", "medico", "enfermeria", "estudiante", "facturacion", "auditor", "auditor_sistemas",
            "admisiones", "farmacia", "laboratorio", "auxiliar_laboratorio")
# Roles que exigen registro profesional (ReTHUS u homólogo) al crear el usuario (Ley 1164 de 2007)
ROLES_CON_REGISTRO = ("medico", "enfermeria", "laboratorio", "farmacia", "auditor")
# Roles con acceso a datos clínicos individuales (los demás solo ven datos administrativos o agregados)
ROLES_CLINICOS = ("admin", "medico", "enfermeria", "estudiante", "auditor")


def es_admin(usuario: Usuario) -> bool:
    return usuario.rol in ADMIN_GESTION
