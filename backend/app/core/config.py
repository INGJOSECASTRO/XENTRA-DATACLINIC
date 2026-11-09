"""Configuración central. Todos los valores se leen de variables de entorno (.env)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NOMBRE: str = "XENTRA DATACLINIC"
    DATABASE_URL: str = "postgresql+psycopg://xentra:xentra@localhost:5432/xentra_hce"

    SECRET_KEY: str = "dev-inseguro-cambiar-esta-clave-antes-de-produccion"
    LEDGER_HMAC_KEY: str = "dev-ledger-inseguro-cambiar-antes-de-produccion"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    MAX_INTENTOS_LOGIN: int = 5
    MINUTOS_BLOQUEO: int = 15

    ADMIN_EMAIL: str = "admin@xentra.co"
    ADMIN_PASSWORD: str = "Admin123*"

    PRESTADOR_NIT: str = "900000000"
    PRESTADOR_COD_HABILITACION: str = "110010000001"
    PRESTADOR_RAZON_SOCIAL: str = "IPS DEMO XENTRA SAS"

    IA_PROVEEDOR: str = "local"  # local | claude
    ANTHROPIC_API_KEY: str = ""
    IA_MODELO: str = "claude-opus-5-5"

    URL_PUBLICA: str = "http://localhost:8080"  # se usa en los QR de verificación de documentos
    JITSI_URL: str = "https://meet.jit.si"  # recomendado: servidor Jitsi propio para telesalud
    # Integraciones externas: "simulado" (pruebas) o "real"
    MUV_MODO: str = "simulado"
    MUV_URL: str = "https://localhost:9443"  # API FEV-RIPS del Ministerio (contenedor local que publica MinSalud)
    MUV_USUARIO: str = ""
    MUV_CLAVE: str = ""
    MUV_TIPO_USUARIO: str = "RE"
    DIAN_MODO: str = "simulado"
    DIAN_PROVEEDOR_URL: str = ""
    DIAN_PROVEEDOR_TOKEN: str = ""
    # RDA - Resolución 1888 de 2025 (Interoperabilidad de Historia Clínica Electrónica, IHCE)
    RDA_MODO: str = "simulado"  # simulado | real | desactivado
    IHCE_URL: str = ""  # API Gateway de la IHCE asignado por el Ministerio
    IHCE_TOKEN: str = ""
    RDA_PERFIL_BASE: str = "https://fhir.minsalud.gov.co/rda/StructureDefinition"  # verificar con la guía oficial
    RDA_MAX_INTENTOS: int = 8
    ANCLAJE_MODO: str = "local"  # local | opentimestamps
    OTS_CALENDARIOS: str = "https://a.pool.opentimestamps.org,https://b.pool.opentimestamps.org"
    FACTURA_PREFIJO: str = "FEV"
    ZONA_HORARIA: str = "America/Bogota"
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:8080"
    CARGAR_DATOS_DEMO: bool = True
    # true: crea tablas al arrancar (desarrollo/pruebas). En producción: false y se usa Alembic (servicio "migrate").
    AUTO_CREAR_TABLAS: bool = True

    @property
    def cors_lista(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
