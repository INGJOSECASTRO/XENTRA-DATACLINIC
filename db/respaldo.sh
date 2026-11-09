#!/bin/sh
# Respaldo diario a las 02:00 (hora de Colombia) + uno al arrancar. Conserva RESPALDO_DIAS días.
# IMPORTANTE: copie también ./backups FUERA del servidor (nube cifrada, disco externo) y pruebe restaurar.
# Restaurar:  pg_restore -h db -U xentra -d xentra_hce --clean --if-exists /backups/ARCHIVO.dump
set -e
respaldar() {
  archivo="/backups/xentra_$(date +%Y%m%d_%H%M%S).dump"
  pg_dump -Fc -f "$archivo" && echo "Respaldo creado: $archivo ($(du -h "$archivo" | cut -f1))"
  find /backups -name 'xentra_*.dump' -mtime +"${RESPALDO_DIAS:-14}" -delete
}
respaldar
while true; do
  ahora=$(date +%s)
  objetivo=$(date -d "$(date +%Y-%m-%d) 02:00" +%s 2>/dev/null || date -D '%Y-%m-%d %H:%M' -d "$(date +%Y-%m-%d) 02:00" +%s)
  [ "$objetivo" -le "$ahora" ] && objetivo=$((objetivo + 86400))
  sleep $((objetivo - ahora))
  respaldar
done
