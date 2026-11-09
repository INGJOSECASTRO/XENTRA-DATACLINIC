"""Utilidades de texto en español."""
import re
import unicodedata


def normalizar(texto: str) -> str:
    """Minúsculas, sin tildes ni signos: 'Hipertensión Arterial' -> 'hipertension arterial'."""
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9ñ ]+", " ", texto).strip()


_PATRONES_PII = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "[EMAIL]"),
    (re.compile(r"\b\d{6,}\b"), "[NUMERO]"),  # documentos, teléfonos, historias
    (re.compile(r"\b(cc|ti|ce|rc|c\.c\.?)\s*[:#]?\s*\S+", re.IGNORECASE), "[DOCUMENTO]"),
]


def anonimizar(texto: str, nombres: list[str] | None = None) -> str:
    """Quita datos que identifican al paciente antes de enviar texto a un servicio externo."""
    resultado = texto or ""
    for patron, reemplazo in _PATRONES_PII:
        resultado = patron.sub(reemplazo, resultado)
    for nombre in nombres or []:
        if nombre and len(nombre) > 2:
            resultado = re.sub(rf"\b{re.escape(nombre)}\b", "[PACIENTE]", resultado, flags=re.IGNORECASE)
    return resultado
