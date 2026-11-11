"""Datos iniciales: administrador, catálogo CIE-10 y (opcional) datos de demostración."""
import logging
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.models import CIE10, Paciente, Usuario
from app.services import catalogos, cie10

log = logging.getLogger(__name__)

USUARIOS_DEMO = [
    ("medico@xentra.co", "Laura", "Gómez Ruiz", "medico", "52123456", "RM-123456", "Medicina general"),
    ("enfermeria@xentra.co", "Carlos", "Pérez Díaz", "enfermeria", "80123456", "TP-98765", "Enfermería"),
    ("facturacion@xentra.co", "Ana", "Martínez", "facturacion", "1010123456", None, None),
    ("auditor@xentra.co", "Jorge", "Ramírez", "auditor", "79123456", "RM-555555", "Auditoría médica"),
    ("admisiones@xentra.co", "Paula", "Rincón", "admisiones", "1020111222", None, None),
    ("farmacia@xentra.co", "Andrés", "Mora", "farmacia", "1020333444", "QF-1234", "Química farmacéutica"),
    ("laboratorio@xentra.co", "Diana", "Suárez", "laboratorio", "1020555666", "BAC-5678", "Bacteriología"),
    ("sistemas@xentra.co", "Mateo", "Quintero", "admin_tecnico", "1020777888", None, "Ingeniería de sistemas"),
    ("seguridad@xentra.co", "Lucía", "Barrera", "auditor_sistemas", "1020999000", None, "Seguridad de la información"),
    ("residente@xentra.co", "Santiago", "Ortiz", "estudiante", "1031222333", "EST-2026-001", "Internado - Medicina"),
    ("auxiliar.laboratorio@xentra.co", "Camila", "Rojas", "auxiliar_laboratorio", "1031444555", None, "Auxiliar de laboratorio"),
]
CLAVE_DEMO = "Demo12345*"


def inicializar(db: Session) -> None:
    if not db.scalars(select(Usuario).where(Usuario.email == settings.ADMIN_EMAIL.lower())).first():
        db.add(Usuario(tipo_documento="CC", numero_documento="0", nombres="Administrador", apellidos="Sistema",
                       email=settings.ADMIN_EMAIL.lower(), hashed_password=hash_password(settings.ADMIN_PASSWORD),
                       rol="admin", debe_cambiar_clave=True))
        db.commit()
        log.info("Usuario administrador creado: %s", settings.ADMIN_EMAIL)

    if (db.scalar(select(func.count()).select_from(CIE10)) or 0) == 0:
        n = cie10.cargar_csv(db)
        log.info("Catálogo CIE-10 de muestra cargado (%s códigos)", n)

    if n := catalogos.cargar_muestra(db):
        log.info("Catálogos de referencia de muestra cargados (%s registros)", n)

    if settings.CARGAR_DATOS_DEMO:
        for email, nombres, apellidos, rol, doc, registro, esp in USUARIOS_DEMO:
            if not db.scalars(select(Usuario).where(Usuario.email == email)).first():
                db.add(Usuario(tipo_documento="CC", numero_documento=doc, nombres=nombres, apellidos=apellidos,
                               email=email, hashed_password=hash_password(CLAVE_DEMO), rol=rol,
                               registro_profesional=registro, especialidad=esp))
        _demo_hospital(db)
        if not db.scalars(select(Paciente).limit(1)).first():
            db.add_all([
                Paciente(tipo_documento="CC", numero_documento="1020304050", primer_nombre="María",
                         segundo_nombre="Fernanda", primer_apellido="López", segundo_apellido="Castro",
                         fecha_nacimiento=date(1985, 3, 14), sexo="M", telefono="3001234567",
                         cod_municipio_residencia="11001", tipo_usuario="01", cod_eapb="EPS001",
                         grupo_sanguineo="O+", alergias="Penicilina", autoriza_tratamiento_datos=True),
                Paciente(tipo_documento="CC", numero_documento="79888777", primer_nombre="José",
                         primer_apellido="Rodríguez", segundo_apellido="Mejía", fecha_nacimiento=date(1958, 11, 2),
                         sexo="H", telefono="3109876543", cod_municipio_residencia="05001", tipo_usuario="04",
                         cod_eapb="EPS002", grupo_sanguineo="A+", autoriza_tratamiento_datos=True),
                Paciente(tipo_documento="TI", numero_documento="1122334455", primer_nombre="Sofía",
                         primer_apellido="Herrera", fecha_nacimiento=date(2014, 6, 20), sexo="M",
                         cod_municipio_residencia="76001", tipo_usuario="02", cod_eapb="EPS001",
                         acompanante_nombre="Diana Herrera", acompanante_telefono="3205556677",
                         autoriza_tratamiento_datos=True),
            ])
        db.commit()


def _demo_hospital(db: Session) -> None:
    from datetime import timedelta

    from app.models_ext import Cama, Lote, Producto, Sede

    if not db.scalars(select(Sede).limit(1)).first():
        db.add(Sede(nombre="Sede Principal", cod_habilitacion=settings.PRESTADOR_COD_HABILITACION, cod_municipio="11001",
                    direccion="Calle 100 # 10-20"))
    if not db.scalars(select(Cama).limit(1)).first():
        for servicio, prefijo, n in (("adultos", "H", 6), ("pediatria", "P", 3), ("observacion", "OBS", 4), ("uci", "UCI", 2)):
            for i in range(1, n + 1):
                db.add(Cama(codigo=f"{prefijo}-{i:02d}", servicio=servicio))
    if not db.scalars(select(Producto).limit(1)).first():
        vence = date.today() + timedelta(days=540)
        demo = [
            ("Acetaminofén 500 mg tableta", "19940582-1", "500 mg", "Tableta", 120, 1, 800),
            ("Losartán 50 mg tableta", "20005316-2", "50 mg", "Tableta", 60, 0, 300),
            ("Amoxicilina 500 mg cápsula", "19935744-3", "500 mg", "Cápsula", 50, 1, 400),
            ("Ibuprofeno 400 mg tableta", "19915263-4", "400 mg", "Tableta", 40, 0, 250),
            ("Cloruro de sodio 0,9% 500 mL", "19960283-5", "0,9%", "Solución inyectable", 30, 1, 5000),
        ]
        for nombre, cum, conc, forma, minimo, _, precio in demo:
            p = Producto(nombre=nombre, cum=cum, concentracion=conc, forma_farmaceutica=forma, stock_minimo=minimo // 4,
                         precio_unitario=precio, unidad=forma.lower())
            db.add(p)
            db.flush()
            db.add(Lote(producto_id=p.id, numero=f"L{cum[-3:]}A", vencimiento=vence, cantidad=minimo * 2))
    db.commit()
