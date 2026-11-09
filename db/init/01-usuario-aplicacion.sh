#!/bin/sh
# Se ejecuta UNA sola vez, cuando PostgreSQL crea la base por primera vez.
# Crea "xentra_app": el usuario con el que corre la API. NO es dueño de las tablas, por lo que
# no puede alterarlas, desactivar triggers ni borrar la auditoría. Las migraciones usan el dueño.
set -e
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<SQL
CREATE ROLE xentra_app LOGIN PASSWORD '${APP_DB_PASSWORD}';
GRANT CONNECT ON DATABASE "${POSTGRES_DB}" TO xentra_app;
GRANT USAGE ON SCHEMA public TO xentra_app;
ALTER DEFAULT PRIVILEGES FOR ROLE "${POSTGRES_USER}" IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO xentra_app;
ALTER DEFAULT PRIVILEGES FOR ROLE "${POSTGRES_USER}" IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO xentra_app;
SQL
