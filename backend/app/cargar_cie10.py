"""Carga el catálogo CIE-10 OFICIAL.

1. Descargue la tabla de referencia CIE-10 desde SISPRO:
   https://web.sispro.gov.co/WebPublico/Consultas/ConsultarDetalleReferenciaBasica.aspx?Code=CIE10
2. Ábrala en Excel y guárdela como CSV separado por ';' con las columnas:
   codigo;descripcion;sexo;edad_minima;edad_maxima   (sexo: A ambos, H hombre, M mujer)
3. Ejecute:  python -m app.cargar_cie10 ruta/archivo.csv  [--reemplazar]
   (con Docker:  docker compose exec backend python -m app.cargar_cie10 /datos/cie10.csv)
"""
import sys
from pathlib import Path

from app.core.database import SessionLocal
from app.services.cie10 import cargar_csv

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    with SessionLocal() as db:
        n = cargar_csv(db, Path(sys.argv[1]), reemplazar="--reemplazar" in sys.argv)
    print(f"Códigos cargados: {n}")
