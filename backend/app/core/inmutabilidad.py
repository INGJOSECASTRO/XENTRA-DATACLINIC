"""Reglas de inmutabilidad DENTRO de PostgreSQL (triggers).

Aunque alguien se salte la API y entre directo a la base de datos, PostgreSQL
rechazará: (1) modificar/borrar bloques del ledger y (2) modificar/borrar folios
de historia clínica ya firmados o sus diagnósticos, procedimientos y fórmulas.
"""
from sqlalchemy.engine import Engine

SQL = r"""
CREATE OR REPLACE FUNCTION hce_ledger_inmutable() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'El ledger es inmutable: operación % no permitida', TG_OP;
END; $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_ledger_inmutable ON ledger_bloques;
CREATE TRIGGER trg_ledger_inmutable BEFORE UPDATE OR DELETE ON ledger_bloques
  FOR EACH ROW EXECUTE FUNCTION hce_ledger_inmutable();

CREATE OR REPLACE FUNCTION hce_atencion_inmutable() RETURNS trigger AS $$
BEGIN
  IF OLD.estado = 'firmada' THEN
    RAISE EXCEPTION 'La atención % está firmada y es inalterable (Res. 1995 de 1999)', OLD.id;
  END IF;
  IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
  RETURN NEW;
END; $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_atencion_inmutable ON atenciones;
CREATE TRIGGER trg_atencion_inmutable BEFORE UPDATE OR DELETE ON atenciones
  FOR EACH ROW WHEN (OLD.estado = 'firmada') EXECUTE FUNCTION hce_atencion_inmutable();

CREATE OR REPLACE FUNCTION hce_hijo_inmutable() RETURNS trigger AS $$
DECLARE est text;
BEGIN
  IF TG_OP = 'INSERT' THEN
    SELECT estado INTO est FROM atenciones WHERE id = NEW.atencion_id;
  ELSE
    SELECT estado INTO est FROM atenciones WHERE id = OLD.atencion_id;
  END IF;
  IF est = 'firmada' THEN
    RAISE EXCEPTION 'No se puede modificar % de una atención firmada', TG_TABLE_NAME;
  END IF;
  IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
  RETURN NEW;
END; $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_dx_inmutable ON diagnosticos;
CREATE TRIGGER trg_dx_inmutable BEFORE INSERT OR UPDATE OR DELETE ON diagnosticos
  FOR EACH ROW EXECUTE FUNCTION hce_hijo_inmutable();
DROP TRIGGER IF EXISTS trg_proc_inmutable ON procedimientos;
CREATE TRIGGER trg_proc_inmutable BEFORE INSERT OR UPDATE OR DELETE ON procedimientos
  FOR EACH ROW EXECUTE FUNCTION hce_hijo_inmutable();
DROP TRIGGER IF EXISTS trg_rx_inmutable ON prescripciones;
CREATE TRIGGER trg_rx_inmutable BEFORE INSERT OR UPDATE OR DELETE ON prescripciones
  FOR EACH ROW EXECUTE FUNCTION hce_hijo_inmutable();

CREATE OR REPLACE FUNCTION hce_nota_inmutable() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'Las notas aclaratorias son inmutables';
END; $$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS trg_nota_inmutable ON notas_aclaratorias;
CREATE TRIGGER trg_nota_inmutable BEFORE UPDATE OR DELETE ON notas_aclaratorias
  FOR EACH ROW EXECUTE FUNCTION hce_nota_inmutable();
"""


def instalar_triggers(engine: Engine) -> None:
    if engine.dialect.name != "postgresql":
        return
    raw = engine.raw_connection()  # sin parámetros: evita interpretar '%' como marcador
    try:
        with raw.cursor() as cur:
            cur.execute(SQL)
        raw.commit()
    finally:
        raw.close()
