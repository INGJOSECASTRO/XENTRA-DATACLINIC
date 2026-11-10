"""Creación masiva de los usuarios REALES de la institución desde un archivo CSV.

Uso:
    python -m app.crear_usuarios archivo.csv --salida credenciales.csv
    (Docker)  docker compose cp usuarios.csv backend:/tmp/usuarios.csv
              docker compose exec backend python -m app.crear_usuarios /tmp/usuarios.csv --salida /tmp/credenciales.csv
              docker compose cp backend:/tmp/credenciales.csv ./credenciales.csv

CSV separado por ';' con columnas (plantilla en docs/plantillas/usuarios_institucion.csv):
    tipo_documento;numero_documento;nombres;apellidos;email;rol;registro_profesional;especialidad

Reglas (docs/manuales/04-PROTOCOLOS-SEGURIDAD.md):
- Una cuenta por persona; el correo no puede repetirse.
- Roles con registro profesional obligatorio: medico, enfermeria, laboratorio, farmacia, auditor.
- Cada usuario recibe una CLAVE TEMPORAL aleatoria que debe cambiar en su primer ingreso.
- El archivo de credenciales contiene claves: entréguelas en persona o por canal seguro y BÓRRELO después.
"""
import csv
import secrets
import string
import sys
from pathlib import Path

from sqlalchemy import select

ROLES = ("admin", "admin_tecnico", "medico", "enfermeria", "estudiante", "facturacion", "auditor", "auditor_sistemas",
         "admisiones", "farmacia", "laboratorio", "auxiliar_laboratorio")


def clave_temporal() -> str:
    alfabeto = string.ascii_letters + string.digits
    while True:
        c = "".join(secrets.choice(alfabeto) for _ in range(12)) + "*"
        if any(x.isupper() for x in c) and any(x.islower() for x in c) and any(x.isdigit() for x in c):
            return c


def crear_desde_csv(ruta: Path) -> tuple[list[dict], list[str]]:
    import app.models_ext  # noqa: F401
    from app.core.database import SessionLocal
    from app.core.deps import ROLES_CON_REGISTRO
    from app.core.security import hash_password
    from app.models import Usuario
    from app.services.ledger import registrar_evento

    creados, errores = [], []
    with SessionLocal() as db, open(ruta, encoding="utf-8-sig") as f:
        for n, fila in enumerate(csv.DictReader(f, delimiter=";"), start=2):
            fila = {k.strip(): (v or "").strip() for k, v in fila.items() if k}
            email, rol = fila.get("email", "").lower(), fila.get("rol", "")
            if not email or "@" not in email:
                errores.append(f"Fila {n}: correo inválido")
                continue
            if rol not in ROLES:
                errores.append(f"Fila {n} ({email}): rol '{rol}' no válido. Use: {', '.join(ROLES)}")
                continue
            if rol in ROLES_CON_REGISTRO and not fila.get("registro_profesional"):
                errores.append(f"Fila {n} ({email}): el rol {rol} exige registro profesional (ReTHUS)")
                continue
            if db.scalars(select(Usuario).where(Usuario.email == email)).first():
                errores.append(f"Fila {n} ({email}): ya existe; no se modificó")
                continue
            clave = clave_temporal()
            u = Usuario(tipo_documento=fila.get("tipo_documento") or "CC", numero_documento=fila.get("numero_documento", ""),
                        nombres=fila.get("nombres", ""), apellidos=fila.get("apellidos", ""), email=email, rol=rol,
                        registro_profesional=fila.get("registro_profesional") or None,
                        especialidad=fila.get("especialidad") or None, hashed_password=hash_password(clave),
                        debe_cambiar_clave=True)
            db.add(u)
            db.flush()
            registrar_evento(db, accion="USUARIO_CREADO", entidad="usuario", entidad_id=u.id,
                             datos={"email": email, "rol": rol, "origen": "carga_masiva"})
            creados.append({"nombres": u.nombres, "apellidos": u.apellidos, "email": email, "rol": rol, "clave_temporal": clave})
        db.commit()
    return creados, errores


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    salida = Path(sys.argv[sys.argv.index("--salida") + 1]) if "--salida" in sys.argv else Path("credenciales_temporales.csv")
    creados, errores = crear_desde_csv(Path(sys.argv[1]))
    if creados:
        with open(salida, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(creados[0]), delimiter=";")
            w.writeheader()
            w.writerows(creados)
    print(f"Usuarios creados: {len(creados)}  ·  Credenciales en: {salida if creados else '-'}")
    for e in errores:
        print("  ⚠", e)
    print("Recuerde: entregue las claves por canal seguro, pida activar MFA y BORRE el archivo de credenciales.")
