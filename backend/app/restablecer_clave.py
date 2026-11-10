"""Restablece la clave de un usuario desde el servidor (por ejemplo, si se olvidó la del administrador).

Uso:
    docker compose exec backend python -m app.restablecer_clave admin@xentra.co

- Genera una CLAVE TEMPORAL aleatoria y la muestra una sola vez en pantalla.
- Quita el bloqueo por intentos fallidos y reactiva la cuenta.
- Obliga a cambiar la clave en el siguiente ingreso.
- Opcional: --quitar-mfa desactiva el segundo factor (celular perdido; verifique antes la identidad, protocolo P-02).
- Queda registrado en el ledger (CLAVE_RESTABLECIDA_SERVIDOR).

Solo puede ejecutarlo quien tiene acceso al servidor; por eso no requiere iniciar sesión.
"""
import argparse
import sys

from sqlalchemy import func, select


def restablecer(email: str, quitar_mfa: bool = False) -> str:
    import app.models_ext  # noqa: F401
    from app.core.database import SessionLocal
    from app.core.security import hash_password
    from app.crear_usuarios import clave_temporal
    from app.models import Usuario
    from app.services.ledger import registrar_evento

    with SessionLocal() as db:
        u = db.scalars(select(Usuario).where(func.lower(Usuario.email) == email.strip().lower())).first()
        if not u:
            raise SystemExit(f"No existe un usuario con el correo {email}")
        clave = clave_temporal()
        u.hashed_password = hash_password(clave)
        u.intentos_fallidos = 0
        u.bloqueado_hasta = None
        u.activo = True
        u.debe_cambiar_clave = True
        if quitar_mfa:
            u.mfa_activo = False
            u.totp_secreto = None
        db.flush()
        registrar_evento(db, accion="CLAVE_RESTABLECIDA_SERVIDOR", entidad="usuario", entidad_id=u.id,
                         datos={"mfa_quitado": quitar_mfa})
        db.commit()
        return clave


def main() -> None:
    p = argparse.ArgumentParser(description="Restablece la clave de un usuario")
    p.add_argument("email")
    p.add_argument("--quitar-mfa", action="store_true", help="Desactiva también el segundo factor")
    a = p.parse_args()
    clave = restablecer(a.email, a.quitar_mfa)
    print(f"\nClave temporal de {a.email}:  {clave}\n")
    print("Ingrese con ella; el sistema le pedirá cambiarla de inmediato.", file=sys.stderr)


if __name__ == "__main__":
    main()
