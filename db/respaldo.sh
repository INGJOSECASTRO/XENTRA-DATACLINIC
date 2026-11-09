#!/bin/sh
# Respaldo diario a las 02:00 (hora de Colombia) + uno al arrancar. Conserva RESPALDO_DIAS días.
# Cada domingo restaura el último respaldo en una base temporal para PROBAR que sirve (un respaldo
# que nunca se ha restaurado no es un respaldo). El resultado queda en /backups/ultima_verificacion.txt
# y se ve en "Estado del sistema".
# IMPORTANTE: copie también ./backups FUERA del servidor (nube cifrada, disco externo).
# Restaurar:  pg_restore -h db -U xentra -d xentra_hce --clean --if-exists /backups/ARCHIVO.dump
set -e
respaldar() {
  archivo="/backups/xentra_$(date +%Y%m%d_%H%M%S).dump"
  pg_dump -Fc -f "$archivo" && echo "Respaldo creado: $archivo ($(du -h "$archivo" | cut -f1))"
  find /backups -name 'xentra_*.dump' -mtime +"${RESPALDO_DIAS:-14}" -delete
  echo "$archivo"
}
verificar() {
  archivo="$1"
  dropdb --if-exists xentra_verificacion
  createdb xentra_verificacion
  if pg_restore -d xentra_verificacion --no-owner "$archivo" >/tmp/restauracion.log 2>&1; then
    pacientes=$(psql -d xentra_verificacion -tAc "select count(*) from pacientes")
    bloques=$(psql -d xentra_verificacion -tAc "select count(*) from ledger_bloques")
    echo "OK $(date '+%Y-%m-%d %H:%M') - $(basename "$archivo") restaurado: $pacientes pacientes, $bloques bloques de auditoría" > /backups/ultima_verificacion.txt
  else
    echo "FALLÓ $(date '+%Y-%m-%d %H:%M') - $(basename "$archivo"): $(tail -3 /tmp/restauracion.log | tr '\n' ' ')" > /backups/ultima_verificacion.txt
  fi
  dropdb --if-exists xentra_verificacion
  cat /backups/ultima_verificacion.txt
}
ultimo=$(respaldar | tail -1)
[ -f /backups/ultima_verificacion.txt ] || verificar "$ultimo"
while true; do
  ahora=$(date +%s)
  objetivo=$(date -d "$(date +%Y-%m-%d) 02:00" +%s 2>/dev/null || date -D '%Y-%m-%d %H:%M' -d "$(date +%Y-%m-%d) 02:00" +%s)
  [ "$objetivo" -le "$ahora" ] && objetivo=$((objetivo + 86400))
  sleep $((objetivo - ahora))
  ultimo=$(respaldar | tail -1)
  [ "$(date +%u)" = "7" ] && verificar "$ultimo"
done
