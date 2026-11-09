"""Carga una tabla de referencia oficial.

Uso:  python -m app.cargar_catalogo <tipo> archivo.csv [--reemplazar]
Tipos: cups, cum, divipola, eapb, tipo_usuario, modalidad, grupo_servicio, servicio, finalidad,
       causa_atencion, via_ingreso, condicion_egreso, concepto_recaudo, tipo_medicamento
CSV separado por ';' con columnas: codigo;descripcion[;datos]   (datos = JSON opcional, ej {"valor": 45000})
"""
import sys
from pathlib import Path

from app.core.database import SessionLocal
from app.services.catalogos import TIPOS, cargar_csv

if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in TIPOS:
        print(__doc__)
        sys.exit(1)
    with SessionLocal() as db:
        print("Registros cargados:", cargar_csv(db, sys.argv[1], Path(sys.argv[2]), "--reemplazar" in sys.argv))
