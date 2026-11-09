# 11. Plan de continuidad del negocio y soporte

Plantilla técnica para que la IPS la adopte en su plan institucional (ajuste nombres, teléfonos y tiempos).

## 11.1 Objetivos de recuperación (sugeridos)

| Indicador | Meta sugerida | Cómo se logra en XENTRA |
|---|---|---|
| **RPO** (datos que se pueden perder) | ≤ 24 h (≤ 1 h con réplica) | Respaldo diario automático; para RPO menor configure replicación de PostgreSQL o respaldos WAL continuos |
| **RTO** (tiempo para volver a operar) | ≤ 4 h | Docker Compose recrea todo en minutos + restauración de `pg_restore` probada cada semana |
| Atención durante la caída | Inmediata | PDF de contingencia descargado al inicio de cada turno |

## 11.2 Lo que el sistema hace solo

- **Respaldo diario** (02:00) con rotación, y **prueba de restauración cada domingo** en una base temporal; el
  resultado se ve en *Soporte y continuidad → Estado del sistema*.
- **Reinicio automático** de contenedores caídos (`restart: unless-stopped`) y chequeo de salud del backend.
- **La página siempre abre**: si la API cae, Nginx muestra un mensaje claro en lugar de una pantalla en blanco.
- **Integraciones con cola**: el RDA (IHCE) se reintenta con espera exponencial; una caída externa no detiene la atención.
- **Alertas** en el estado del sistema: BD lenta, disco < 10 %, respaldo > 26 h, RDA con error, tickets con ANS vencido.

## 11.3 Escenarios y procedimientos

| Escenario | Qué hacer |
|---|---|
| **Cae la red interna o internet** | Atender con el PDF de contingencia y formatos en papel. Al volver: transcribir como "registro diferido por contingencia". |
| **Falla el servidor** | 1) `docker compose ps` y `docker compose logs backend --tail 100`. 2) `docker compose up -d`. 3) Si el disco o la máquina se perdió: servidor nuevo + clonar repositorio + `.env` (guardado en el gestor de secretos) + restaurar el último respaldo copiado fuera del servidor. |
| **Ransomware / sospecha de intrusión** | Aislar el servidor de la red. NO pagar. Activar contingencia en papel. Reportar a ColCERT y a la Superintendencia de Industria y Comercio si hay datos personales comprometidos. Restaurar en un servidor limpio desde un respaldo externo anterior al incidente. Verificar la cadena del ledger y los anclajes. Cambiar todas las claves (incluida `LEDGER_HMAC_KEY` en un ledger nuevo, conservando la anterior para verificar lo histórico). |
| **Corrupción de datos** | Verificar la cadena (Auditoría → Verificar). El bloque señalado indica desde cuándo. Restaurar el respaldo previo y comparar. |
| **Falla de la IHCE, DIAN o MUV** | Nada se pierde: el RDA queda en cola; las facturas quedan en "emitida/rechazada" para reenviar. Revisar Soporte → RDA. |

### Restauración paso a paso (probarla cada mes en un equipo de pruebas)

```bash
docker compose exec respaldo ls -lh /backups
docker compose stop backend
docker compose exec respaldo pg_restore -h db -U xentra -d xentra_hce --clean --if-exists /backups/xentra_AAAAMMDD_HHMMSS.dump
docker compose start backend
```
Luego: Auditoría → **Verificar cadena completa**.

## 11.4 Soporte y resolución de problemas

1. El usuario ve un mensaje con **código de error** (10 caracteres).
2. Lo reporta en **Soporte y continuidad → Mesa de ayuda**, con la prioridad:
   crítica 4 h (no se puede atender), alta 8 h, media 24 h, baja 72 h.
3. Soporte busca el código en el log: `docker compose logs backend | grep CODIGO` y ve el error exacto.
4. Al resolver, **registra la solución**: queda en la **base de conocimiento** para que el siguiente usuario la encuentre solo.
5. Para mantenimientos programados, publique un **aviso** (aparece a todos los usuarios).

## 11.5 Responsabilidades (complete)

| Rol | Persona | Contacto |
|---|---|---|
| Líder de continuidad | | |
| Soporte técnico nivel 1 (mesa de ayuda) | | |
| Soporte nivel 2 (servidor / base de datos) | | |
| Oficial de seguridad de la información | | |
| Responsable de protección de datos (Ley 1581) | | |

## 11.6 Calendario de pruebas

| Frecuencia | Prueba |
|---|---|
| Diaria | Revisar "Estado del sistema"; copiar `backups/` fuera del servidor |
| Semanal | Automática: restauración de prueba (ver resultado en Estado del sistema) |
| Mensual | Restauración completa en un equipo de pruebas siguiendo 11.3 |
| Semestral | Simulacro de contingencia en papel con el personal asistencial |
| Anual | Prueba de penetración externa y revisión de este plan |
