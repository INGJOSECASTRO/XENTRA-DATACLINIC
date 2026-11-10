"""Lección 3: una mini-cadena tipo blockchain, igual en esencia al ledger de XENTRA
(backend/app/services/ledger.py), para entenderla y "hackearla".

Ejecutar en su PC (con XENTRA corriendo en Docker):
    docker compose cp docs/curso/leccion3_cadena.py backend:/tmp/leccion3.py
    docker compose exec backend python /tmp/leccion3.py
"""
import copy
import hashlib
import hmac
import json

# ---------------------------------------------------------------------------
# 1. LAS HERRAMIENTAS
# ---------------------------------------------------------------------------

def huella(texto: str) -> str:
    """SHA-256: convierte cualquier texto en una 'huella digital' de 64 caracteres."""
    return hashlib.sha256(texto.encode()).hexdigest()


def json_canonico(datos) -> str:
    """Escribe los datos SIEMPRE igual (mismo orden, sin espacios), para que la huella sea estable."""
    return json.dumps(datos, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


LLAVE_SECRETA = b"esta-llave-vive-FUERA-de-la-base-de-datos"   # en XENTRA: LEDGER_HMAC_KEY del .env


def firmar(texto: str) -> str:
    """HMAC: una huella que SOLO puede calcular quien tiene la llave secreta."""
    return hmac.new(LLAVE_SECRETA, texto.encode(), hashlib.sha256).hexdigest()


GENESIS = "0" * 64   # el "bloque cero": el primer bloque se encadena a esto


# ---------------------------------------------------------------------------
# 2. CREAR BLOQUES
# ---------------------------------------------------------------------------

def huella_del_bloque(b: dict) -> str:
    """La huella del bloque incluye la huella del ANTERIOR: eso es lo que forma la cadena."""
    return huella(f'{b["numero"]}|{b["accion"]}|{b["huella_datos"]}|{b["huella_anterior"]}')


def agregar_bloque(cadena: list, accion: str, datos: dict) -> None:
    anterior = cadena[-1]["huella"] if cadena else GENESIS
    b = {
        "numero": len(cadena) + 1,
        "accion": accion,
        "datos": datos,                                  # (en XENTRA los datos viven en su tabla; aquí, juntos)
        "huella_datos": huella(json_canonico(datos)),    # huella del contenido
        "huella_anterior": anterior,                     # ← el eslabón con el bloque anterior
    }
    b["huella"] = huella_del_bloque(b)
    b["firma"] = firmar(b["huella"])                     # sello con la llave secreta
    cadena.append(b)


# ---------------------------------------------------------------------------
# 3. VERIFICAR (lo que hace "Verificar cadena completa" en XENTRA)
# ---------------------------------------------------------------------------

def verificar(cadena: list) -> str:
    anterior = GENESIS
    for esperado, b in enumerate(cadena, start=1):
        if b["numero"] != esperado:
            return f"❌ Falta el bloque {esperado} (alguien lo borró)"
        if huella(json_canonico(b["datos"])) != b["huella_datos"]:
            return f"❌ Bloque {b['numero']}: los DATOS fueron modificados"
        if b["huella_anterior"] != anterior:
            return f"❌ Bloque {b['numero']}: el eslabón con el bloque anterior está roto"
        if huella_del_bloque(b) != b["huella"]:
            return f"❌ Bloque {b['numero']}: el bloque fue modificado"
        if not hmac.compare_digest(firmar(b["huella"]), b["firma"]):
            return f"❌ Bloque {b['numero']}: firma inválida (recalculado sin la llave secreta)"
        anterior = b["huella"]
    return f"✅ Cadena íntegra: {len(cadena)} bloques verificados"


def mostrar(cadena: list) -> None:
    for b in cadena:
        print(f'  Bloque {b["numero"]} | {b["accion"]:<17} | anterior: {b["huella_anterior"][:10]}… '
              f'| huella: {b["huella"][:10]}…')


# ---------------------------------------------------------------------------
# 4. LA DEMOSTRACIÓN
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("\n=== PASO 1: una huella cambia por completo con una sola letra ===")
    print("  'Gastritis' →", huella("Gastritis")[:32], "…")
    print("  'gastritis' →", huella("gastritis")[:32], "…")

    print("\n=== PASO 2: construimos una cadena de 3 bloques ===")
    original = []
    agregar_bloque(original, "LOGIN", {"usuario": "medico@xentra.co"})
    agregar_bloque(original, "ATENCION_FIRMADA", {"paciente": "CC 1020304050", "dx": "K297", "plan": "Omeprazol 20 mg"})
    agregar_bloque(original, "DESCARGA_PDF", {"atencion": 2, "usuario": "auditor@xentra.co"})
    mostrar(original)
    print(" ", verificar(original))

    print("\n=== ATAQUE 1: cambiar el diagnóstico de la atención firmada ===")
    c = copy.deepcopy(original)
    c[1]["datos"]["dx"] = "Z000"            # el atacante cambia K297 por Z000
    print(" ", verificar(c))

    print("\n=== ATAQUE 2: cambiar el dato Y recalcular la huella de ese bloque ===")
    c = copy.deepcopy(original)
    c[1]["datos"]["dx"] = "Z000"
    c[1]["huella_datos"] = huella(json_canonico(c[1]["datos"]))
    c[1]["huella"] = huella_del_bloque(c[1])
    print(" ", verificar(c))

    print("\n=== ATAQUE 3: recalcular TODAS las huellas de la cadena (sin la llave) ===")
    c = copy.deepcopy(original)
    c[1]["datos"]["dx"] = "Z000"
    anterior = GENESIS
    for b in c:
        b["huella_datos"] = huella(json_canonico(b["datos"]))
        b["huella_anterior"] = anterior
        b["huella"] = huella_del_bloque(b)
        anterior = b["huella"]
    print(" ", verificar(c))

    print("\n=== ATAQUE 4: borrar el bloque 2 para desaparecer la evidencia ===")
    c = copy.deepcopy(original)
    del c[1]
    print(" ", verificar(c))

    print("\n=== Y la cadena original sigue intacta ===")
    print(" ", verificar(original), "\n")
