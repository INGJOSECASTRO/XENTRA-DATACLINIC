"""Lista de verificación ANTES de atender pacientes reales con XENTRA.

Uso (en el servidor):
    docker compose exec backend python -m app.verificar_produccion
    docker compose exec backend python -m app.verificar_produccion --desactivar-demo

Revisa configuración, usuarios, cadena del ledger, respaldos, catálogos e integraciones, y explica en
español qué falta. Termina con código 1 si hay algún punto CRÍTICO (útil para automatizar).
--desactivar-demo  desactiva los usuarios de demostración (clave pública Demo12345*) y lo registra en el ledger.
"""
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import func, select

CRITICO, AVISO, OK = "CRÍTICO", "AVISO", "OK"
SIMBOLO = {CRITICO: "❌", AVISO: "⚠️ ", OK: "✅"}


def revisar(desactivar_demo: bool = False, carpeta_respaldos: Path = Path("/backups")) -> list[tuple[str, str]]:
    import app.models_ext  # noqa: F401
    from app.core.config import settings
    from app.core.database import SessionLocal
    from app.models import CIE10, Usuario
    from app.seed import USUARIOS_DEMO
    from app.services.ledger import registrar_evento, verificar_cadena

    r: list[tuple[str, str]] = []

    # 1. Configuración
    for p in settings.problemas_produccion():
        r.append((CRITICO, p))
    if not settings.es_produccion:
        r.append((CRITICO, "ENTORNO no es 'produccion': ponga ENTORNO=produccion en el .env"))
    if not settings.MFA_OBLIGATORIO_ROLES.strip():
        r.append((CRITICO, "MFA_OBLIGATORIO_ROLES está vacío: el segundo factor no es obligatorio para nadie"))
    if not settings.CAMBIO_CLAVE_PRIMER_INGRESO:
        r.append((CRITICO, "CAMBIO_CLAVE_PRIMER_INGRESO=false: las claves temporales no se obligan a cambiar"))
    if settings.PORTAL_PACIENTE_ACTIVO:
        r.append((AVISO, "PORTAL_PACIENTE_ACTIVO=true: la institución decidió que los pacientes no ingresen"))
    if "localhost" in settings.URL_PUBLICA:
        r.append((AVISO, f"URL_PUBLICA={settings.URL_PUBLICA}: los QR de los documentos no funcionarán fuera del servidor"))
    if settings.PRESTADOR_NIT == "900000000" or "DEMO" in settings.PRESTADOR_RAZON_SOCIAL.upper():
        r.append((CRITICO, "Datos del prestador de ejemplo (PRESTADOR_NIT / RAZON_SOCIAL / COD_HABILITACION): "
                           "los RIPS y facturas saldrían con datos falsos"))
    if not r or all(n != CRITICO for n, _ in r):
        r.append((OK, "Configuración de seguridad"))

    with SessionLocal() as db:
        # 2. Usuarios
        demo = [e for e, *_ in USUARIOS_DEMO]
        activos_demo = db.scalars(select(Usuario).where(Usuario.email.in_(demo), Usuario.activo.is_(True))).all()
        if activos_demo and desactivar_demo:
            for u in activos_demo:
                u.activo = False
                registrar_evento(db, accion="USUARIO_DESACTIVADO", entidad="usuario", entidad_id=u.id,
                                 datos={"motivo": "usuario de demostración, paso a producción"})
            db.commit()
            r.append((OK, f"Se desactivaron {len(activos_demo)} usuarios de demostración"))
        elif activos_demo:
            r.append((CRITICO, f"{len(activos_demo)} usuarios de demostración activos con clave pública "
                               "(ejecute con --desactivar-demo)"))
        else:
            r.append((OK, "Sin usuarios de demostración activos"))

        admins = db.scalars(select(Usuario).where(Usuario.rol == "admin", Usuario.activo.is_(True))).all()
        if len(admins) > 2:
            r.append((AVISO, f"Hay {len(admins)} administradores activos (el protocolo recomienda máximo 2)"))
        inicial = next((u for u in admins if u.email == settings.ADMIN_EMAIL.lower()), None)
        if inicial and len(admins) > 1:
            r.append((AVISO, f"La cuenta inicial {inicial.email} sigue activa: desactívela una vez creadas las "
                             "cuentas personales de los administradores (protocolo P-06)"))
        if inicial and inicial.debe_cambiar_clave:
            r.append((AVISO, f"{inicial.email} aún tiene la clave inicial: ingrese y cámbiela"))
        personal = db.scalar(select(func.count()).select_from(Usuario).where(
            Usuario.activo.is_(True), Usuario.rol != "admin", ~Usuario.email.in_(demo))) or 0
        if personal == 0:
            r.append((AVISO, "Aún no hay usuarios reales del personal: cárguelos con python -m app.crear_usuarios"))
        else:
            r.append((OK, f"{personal} usuarios reales del personal activos"))

        # 3. Ledger
        cadena = verificar_cadena(db)
        if cadena["valida"]:
            r.append((OK, f"Cadena del ledger íntegra ({cadena['total_bloques']} bloques)"))
        else:
            r.append((CRITICO, f"Cadena del ledger con error en el bloque {cadena['bloque_con_error']}: "
                               f"{cadena['detalle']}"))

        # 4. Catálogo CIE-10
        n_cie = db.scalar(select(func.count()).select_from(CIE10)) or 0
        if n_cie < 5000:
            r.append((CRITICO, f"El CIE-10 tiene solo {n_cie} códigos (muestra). Cargue la tabla oficial de SISPRO "
                               "con python -m app.cargar_cie10"))
        else:
            r.append((OK, f"Catálogo CIE-10 con {n_cie} códigos"))

    # 5. Respaldos
    respaldos = sorted(carpeta_respaldos.glob("xentra_*.dump"), key=lambda p: p.stat().st_mtime) \
        if carpeta_respaldos.exists() else []
    if not respaldos:
        r.append((CRITICO, "No se encontró ningún respaldo en /backups (revise el contenedor 'respaldo')"))
    else:
        edad = timedelta(seconds=time.time() - respaldos[-1].stat().st_mtime)
        if edad > timedelta(hours=26):
            r.append((CRITICO, f"El último respaldo tiene {edad.days} días: el respaldo diario no está funcionando"))
        else:
            r.append((OK, f"Último respaldo: {respaldos[-1].name}"))
        r.append((AVISO, "Confirme que la carpeta 'backups' se copia FUERA del servidor (nube o disco externo)"))

    # 6. Integraciones (pueden seguir simuladas mientras se habilitan, pero hay que saberlo)
    for nombre, modo in (("MUV (validación RIPS)", settings.MUV_MODO), ("DIAN (factura electrónica)", settings.DIAN_MODO),
                         ("RDA / IHCE", settings.RDA_MODO)):
        if modo != "real":
            r.append((AVISO, f"{nombre} en modo '{modo}': no se envía nada real hasta configurarlo"))
    if settings.ANCLAJE_MODO != "opentimestamps":
        r.append((AVISO, "ANCLAJE_MODO=local: active 'opentimestamps' para la prueba externa del ledger"))
    return r


def main() -> int:
    resultado = revisar(desactivar_demo="--desactivar-demo" in sys.argv)
    print(f"\nXENTRA · Verificación de producción · {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC\n")
    for nivel in (CRITICO, AVISO, OK):
        for n, texto in resultado:
            if n == nivel:
                print(f"  {SIMBOLO[n]} {texto}")
    criticos = sum(n == CRITICO for n, _ in resultado)
    print(f"\n  {'LISTO para producción' if not criticos else f'{criticos} punto(s) CRÍTICO(S) por resolver'}. "
          "Guía: docs/15-paso-a-produccion.md\n")
    return 1 if criticos else 0


if __name__ == "__main__":
    sys.exit(main())
