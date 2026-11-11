"""Prepara el archivo .env de PRODUCCIÓN de XENTRA con claves aleatorias seguras.

No necesita nada instalado aparte de Docker. Desde la carpeta del proyecto:

  Windows (PowerShell):
    docker run --rm -v "${PWD}:/xentra" -w /xentra python:3.13-slim python scripts/preparar_produccion.py --modo vpn --dominio sudominio.com

  Linux / VPS:
    docker run --rm -v "$PWD:/xentra" -w /xentra python:3.13-slim python scripts/preparar_produccion.py --modo https --dominio sudominio.com

Opciones:
  --modo vpn     HCE privada por VPN WireGuard (docker-compose.vpn.yml). Usa vpn.<dominio>
  --modo https   En internet con HTTPS (docker-compose.prod.yml, Caddy). Usa hce.<dominio>
  --dominio      Su dominio (ej. miips.com). Opcional en modo vpn si usa DuckDNS o IP.
  --nit --razon-social --cod-habilitacion --admin-email   Datos reales del prestador (REPS)

Si ya existe un .env, se guarda una copia (.env.anterior-FECHA) antes de reemplazarlo.
"""
import argparse
import secrets
import string
import sys
from datetime import datetime
from pathlib import Path


def clave(n: int = 48) -> str:
    return secrets.token_urlsafe(n)


def clave_humana() -> str:
    """Clave temporal legible para el administrador (mayúsculas, minúsculas, números y símbolo)."""
    alfabeto = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789"
    while True:
        c = "".join(secrets.choice(alfabeto) for _ in range(14)) + "*"
        if any(x.isupper() for x in c) and any(x.islower() for x in c) and any(x.isdigit() for x in c):
            return c


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--modo", choices=["vpn", "https"], required=True)
    p.add_argument("--dominio", default="")
    p.add_argument("--nit", default="")
    p.add_argument("--razon-social", default="")
    p.add_argument("--cod-habilitacion", default="")
    p.add_argument("--admin-email", default="")
    a = p.parse_args()

    base = Path(".env.example")
    if not base.exists():
        print("Ejecute este script desde la carpeta del proyecto (donde está .env.example).")
        return 1
    if a.modo == "https" and not a.dominio:
        print("En modo https debe indicar --dominio (ej. --dominio miips.com).")
        return 1

    pg, app_db = clave(24), clave(24)
    valores = {
        "ENTORNO": "produccion",
        "POSTGRES_PASSWORD": pg,
        "DATABASE_URL_MIGRACIONES": f"postgresql+psycopg://xentra:{pg}@db:5432/xentra_hce",
        "APP_DB_PASSWORD": app_db,
        "DATABASE_URL": f"postgresql+psycopg://xentra_app:{app_db}@db:5432/xentra_hce",
        "SECRET_KEY": clave(),
        "LEDGER_HMAC_KEY": clave(),
        "ADMIN_PASSWORD": clave_humana(),
        "PORTAL_PACIENTE_ACTIVO": "false",
        "CAMBIO_CLAVE_PRIMER_INGRESO": "true",
        "MFA_OBLIGATORIO_ROLES": "admin,admin_tecnico,auditor,auditor_sistemas,medico,facturacion",
        "CARGAR_DATOS_DEMO": "false",
    }
    if a.modo == "https":
        host = f"hce.{a.dominio}"
        valores.update({"DOMINIO": host, "URL_PUBLICA": f"https://{host}", "CORS_ORIGINS": f"https://{host}"})
    else:
        valores.update({"URL_PUBLICA": "http://172.30.77.10", "CORS_ORIGINS": "http://172.30.77.10,http://localhost:8080"})
        if a.dominio:
            valores["VPN_HOST"] = f"vpn.{a.dominio}"
    for opcion, var in (("nit", "PRESTADOR_NIT"), ("razon_social", "PRESTADOR_RAZON_SOCIAL"),
                        ("cod_habilitacion", "PRESTADOR_COD_HABILITACION"), ("admin_email", "ADMIN_EMAIL")):
        if getattr(a, opcion):
            valores[var] = getattr(a, opcion)

    lineas, usadas = [], set()
    for linea in base.read_text(encoding="utf-8").splitlines():
        nombre = linea.split("=", 1)[0].strip()
        if "=" in linea and not linea.lstrip().startswith("#") and nombre in valores:
            lineas.append(f"{nombre}={valores[nombre]}")
            usadas.add(nombre)
        else:
            lineas.append(linea)
    faltantes = [k for k in valores if k not in usadas]
    if faltantes:
        lineas += ["", "# --- Agregado por scripts/preparar_produccion.py ---"] + [f"{k}={valores[k]}" for k in faltantes]

    destino = Path(".env")
    if destino.exists():
        copia = Path(f".env.anterior-{datetime.now():%Y%m%d-%H%M%S}")
        copia.write_text(destino.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"Copia del .env anterior: {copia}")
    destino.write_text("\n".join(lineas) + "\n", encoding="utf-8")

    print(f"""
==================================================================
  .env de PRODUCCIÓN creado  (modo: {a.modo})
==================================================================
  Administrador inicial : {valores.get('ADMIN_EMAIL', 'admin@xentra.co (ver .env)')}
  Clave TEMPORAL        : {valores['ADMIN_PASSWORD']}
                          (el sistema le pedirá cambiarla al ingresar)

  ⚠  GUARDE AHORA, en sobre sellado y en un gestor de contraseñas,
     la línea LEDGER_HMAC_KEY del archivo .env. Si se pierde, no se
     podrán verificar los bloques antiguos del ledger.

  ⚠  Las claves de la base de datos son NUEVAS. Si este equipo ya
     tenía una base de datos de pruebas, debe empezar limpio:
        docker compose down -v      (BORRA los datos de prueba)
     Nunca lo haga si ya hay datos reales de pacientes.

  Revise también en el .env: PRESTADOR_NIT, PRESTADOR_RAZON_SOCIAL,
  PRESTADOR_COD_HABILITACION (datos reales del REPS).

  Siguiente paso: docs/15-paso-a-produccion.md
==================================================================
""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
