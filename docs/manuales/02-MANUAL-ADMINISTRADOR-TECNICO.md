# Manual del administrador técnico de XENTRA DATACLINIC

**Instalación, configuración, operación diaria, seguridad, respaldos, integraciones y solución de problemas.**

| | |
|---|---|
| Versión del software | 0.3.0 |
| Público | Ingeniero(a) de sistemas o técnico(a) responsable del servidor, y el usuario con rol **admin** dentro del sistema |
| Requisitos previos | Manejo básico de la terminal (PowerShell o Bash) y de Docker |

---

## Contenido

1. [Responsabilidades del administrador](#1-responsabilidades-del-administrador)
2. [Requisitos de infraestructura](#2-requisitos-de-infraestructura)
3. [Instalación](#3-instalación)
4. [Configuración (.env): referencia completa](#4-configuración-env-referencia-completa)
5. [Primer arranque: lista de verificación](#5-primer-arranque-lista-de-verificación)
6. [Administración funcional dentro del sistema](#6-administración-funcional-dentro-del-sistema)
7. [Catálogos oficiales](#7-catálogos-oficiales)
8. [Integraciones externas](#8-integraciones-externas)
9. [Seguridad](#9-seguridad)
10. [Respaldos y restauración](#10-respaldos-y-restauración)
11. [Monitoreo y operación diaria](#11-monitoreo-y-operación-diaria)
12. [Tareas programadas](#12-tareas-programadas)
13. [Actualizaciones](#13-actualizaciones)
14. [Soporte a usuarios](#14-soporte-a-usuarios)
15. [Solución de problemas](#15-solución-de-problemas)
16. [Referencia de comandos](#16-referencia-de-comandos)

---

## 1. Responsabilidades del administrador

| Área | Tareas |
|---|---|
| Infraestructura | Servidor, red, dominio, HTTPS, actualizaciones del sistema operativo |
| Plataforma | Instalar, actualizar y reiniciar los contenedores; aplicar migraciones |
| Seguridad | Guardar las claves, gestionar usuarios y roles, MFA, revisar el estado del sistema y el ledger |
| Datos | Respaldos fuera del servidor, pruebas de restauración, carga de catálogos oficiales |
| Integraciones | Configurar DIAN, MUV, IHCE (RDA), IA y anclaje |
| Soporte | Atender la mesa de ayuda, publicar avisos, mantener la base de conocimiento |
| Continuidad | Ejecutar el plan de continuidad (`docs/11-plan-continuidad.md`) |

---

## 2. Requisitos de infraestructura

| Recurso | Mínimo (IPS pequeña, < 30 usuarios) | Recomendado (hospital, > 100 usuarios) |
|---|---|---|
| CPU | 2 vCPU | 8 vCPU |
| RAM | 4 GB | 16 GB |
| Disco | 50 GB SSD | 500 GB SSD + almacenamiento externo para respaldos |
| Sistema operativo | Ubuntu Server 24.04 LTS | Ubuntu Server 24.04 LTS |
| Software | Docker Engine y Docker Compose v2.24 o superior, Git | Igual, más monitoreo externo |
| Red | Puertos 80 y 443 abiertos (producción) | Igual, más VPN para la administración |
| Ubicación | Preferiblemente en Colombia o en un país con protección de datos adecuada (Ley 1581) | Igual, con contrato que garantice la custodia |

Equipos de los usuarios: un navegador moderno (Chrome, Edge o Firefox). El **dictado por voz** solo funciona en Chrome o Edge.

---

## 3. Instalación

### 3.1 Servidor de pruebas o computador local

```bash
git clone https://github.com/ingjosecastro/xentra-dataclinic.git
cd xentra-dataclinic
git checkout claude/electronic-health-records-system-1zx3xq
cp .env.example .env         # Windows: copy .env.example .env
# Edite .env (sección 4)
docker compose up -d --build
docker compose ps
```

Resultado esperado: `db` healthy, `migrate` **Exited (0)**, `backend` running (healthy), `frontend` running, `respaldo` running. Abra `http://localhost:8080`.

### 3.1.1 Su propio equipo Windows como servidor

Para usar el mismo computador con Docker Desktop como servidor (red local, acceso remoto privado con Tailscale o internet con dominio y HTTPS mediante Cloudflare Tunnel, sin abrir puertos), siga la guía `docs/12-despliegue-servidor-propio.md` y el archivo `docker-compose.tunel.yml`.

### 3.2 Producción con HTTPS

1. Cree un registro DNS tipo **A** de su dominio (ej. `hce.miips.com`) apuntando a la IP del servidor.
2. Instale Docker: `curl -fsSL https://get.docker.com | sh`.
3. Firewall: `ufw allow 22 && ufw allow 80 && ufw allow 443 && ufw enable`.
4. Clone el repositorio y cree el `.env` (sección 4) con:
   `DOMINIO=hce.miips.com`, `URL_PUBLICA=https://hce.miips.com`, `CORS_ORIGINS=https://hce.miips.com` y `CARGAR_DATOS_DEMO=false`.
5. Levante el sistema:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
   ```
6. Caddy obtiene y renueva solo el certificado. El frontend y la API ya no quedan expuestos por puertos directos.

### 3.3 Qué hace cada contenedor

| Servicio | Función | Se reinicia solo |
|---|---|---|
| `db` | PostgreSQL 16; la primera vez crea el usuario sin privilegios `xentra_app` | Sí |
| `migrate` | Aplica las migraciones con el usuario dueño y termina | No (es normal que termine) |
| `backend` | API FastAPI; corre con `xentra_app` | Sí, con chequeo de salud |
| `frontend` | Nginx con la aplicación Vue; reenvía `/api` y `/fhir` | Sí |
| `respaldo` | Respaldo diario a las 02:00 y prueba de restauración los domingos | Sí |
| `caddy` (producción) | HTTPS automático | Sí |

---

## 4. Configuración (.env): referencia completa

> El archivo `.env` contiene secretos: **nunca** lo suba a GitHub ni lo envíe por correo. Guarde una copia en un gestor de secretos.

Genere valores aleatorios con: `python -c "import secrets; print(secrets.token_urlsafe(64))"`.

### 4.1 Base de datos

| Variable | Descripción |
|---|---|
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | Usuario **dueño** de la base (solo para migraciones) |
| `DATABASE_URL_MIGRACIONES` | URL de conexión del dueño; la clave debe coincidir con `POSTGRES_PASSWORD` |
| `APP_DB_PASSWORD` | Clave del usuario sin privilegios `xentra_app` |
| `DATABASE_URL` | URL con la que corre la API: `postgresql+psycopg://xentra_app:APP_DB_PASSWORD@db:5432/xentra_hce` |
| `AUTO_CREAR_TABLAS` | `true` solo en desarrollo. En Docker se fuerza a `false` |

> Las claves de la BD se fijan **la primera vez** que se crea el volumen. Si las cambia después, debe cambiarlas también dentro de PostgreSQL (`ALTER ROLE`), o empezar de cero con `docker compose down -v` (borra los datos).

### 4.2 Seguridad

| Variable | Valor por defecto | Descripción |
|---|---|---|
| `SECRET_KEY` | (cambiar) | Firma de los tokens de sesión. Si cambia, se cierran todas las sesiones |
| `LEDGER_HMAC_KEY` | (cambiar) | Firma de los bloques del ledger. **Si se pierde, no se pueden verificar los bloques antiguos.** Respáldela fuera del servidor |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 30 | Duración del token (se renueva mientras hay actividad) |
| `MAX_INTENTOS_LOGIN` | 5 | Intentos fallidos antes del bloqueo |
| `MINUTOS_BLOQUEO` | 15 | Duración del bloqueo |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | admin@xentra.co | Administrador inicial; se crea solo en el primer arranque |
| `PORTAL_PACIENTE_ACTIVO` | false | `false`: los pacientes no ingresan a la plataforma (se oculta el botón y se rechaza cualquier cuenta de paciente) |
| `CAMBIO_CLAVE_PRIMER_INGRESO` | true | Obliga a cambiar la clave temporal antes de usar el sistema |
| `MFA_OBLIGATORIO_ROLES` | (vacío) | Roles que deben activar el MFA para trabajar. Producción: `admin,admin_tecnico,auditor,auditor_sistemas,medico,facturacion` |

### 4.3 Datos de la institución

| Variable | Descripción |
|---|---|
| `PRESTADOR_NIT` | NIT de la IPS (RIPS, facturas, RDA) |
| `PRESTADOR_COD_HABILITACION` | Código de habilitación REPS de 12 dígitos |
| `PRESTADOR_RAZON_SOCIAL` | Aparece en los PDF |
| `URL_PUBLICA` | Dirección pública; se imprime en los QR de verificación |
| `ZONA_HORARIA` | `America/Bogota` |
| `CORS_ORIGINS` | Direcciones desde las que se usa la aplicación |
| `CARGAR_DATOS_DEMO` | `true` crea usuarios y pacientes de prueba. **En producción: `false`** |

### 4.4 Inteligencia artificial

| Variable | Valores | Descripción |
|---|---|---|
| `IA_PROVEEDOR` | `local` / `claude` | Local funciona sin internet. Claude requiere API key y autorización de tratamiento de datos |
| `ANTHROPIC_API_KEY` | — | Clave de la API de Anthropic |
| `IA_MODELO` | `claude-opus-5-5` | Modelo de Claude |

### 4.5 Integraciones (ver sección 8)

| Variable | Descripción |
|---|---|
| `DIAN_MODO`, `DIAN_PROVEEDOR_URL`, `DIAN_PROVEEDOR_TOKEN` | Facturación electrónica a través del proveedor tecnológico |
| `FACTURA_PREFIJO` | Prefijo autorizado en la resolución de facturación DIAN |
| `MUV_MODO`, `MUV_URL`, `MUV_TIPO_USUARIO`, `MUV_USUARIO`, `MUV_CLAVE` | Validación FEV-RIPS en el MUV |
| `RDA_MODO` | `simulado` / `real` / `desactivado` |
| `IHCE_URL`, `IHCE_TOKEN` | URL y credencial que asigna el Ministerio al registrar la IPS. **No use una URL genérica** |
| `RDA_PERFIL_BASE` | `https://fhir.minsalud.gov.co/rda/StructureDefinition` (oficial; no cambiar salvo una nueva versión de la guía) |
| `RDA_OPERACION_DISPENSACION` | Ruta de "Enviar Dispensación" que confirme la IHCE |
| `RDA_MAX_INTENTOS` | 8 reintentos con espera exponencial |
| `ANCLAJE_MODO`, `OTS_CALENDARIOS` | `local` u `opentimestamps` |
| `JITSI_URL` | Servidor de video para telemedicina (recomendado uno propio) |

### 4.6 Infraestructura

| Variable | Descripción |
|---|---|
| `DOMINIO` | Dominio para HTTPS (`docker-compose.prod.yml`) |
| `RESPALDO_DIAS` | Días que se conservan los respaldos locales (14) |

---

## 5. Primer arranque: lista de verificación

- [ ] Todas las claves `CAMBIAR` reemplazadas; `.env` guardado en el gestor de secretos.
- [ ] `CARGAR_DATOS_DEMO=false` en producción.
- [ ] Ingreso con `admin@xentra.co` y cambio inmediato de la contraseña (*Mi cuenta y seguridad*).
- [ ] MFA activado para el administrador.
- [ ] Sedes creadas y verificados los datos del prestador.
- [ ] Usuarios reales creados con su rol y registro profesional (ReTHUS).
- [ ] Camas creadas por servicio.
- [ ] Catálogos oficiales cargados (CIE-10, CUPS con tarifas, CUM, DIVIPOLA, EAPB, tablas RIPS).
- [ ] Productos e inventario inicial de farmacia.
- [ ] Respaldos visibles en *Soporte y continuidad → Estado del sistema* y copia externa configurada.
- [ ] Anclaje diario programado.
- [ ] Prueba completa: atención → firma → PDF → factura → RIPS → RDA.

---

## 6. Administración funcional dentro del sistema

### 6.1 Usuarios y roles

Menú **Usuarios** (roles `admin` y `admin_tecnico`). Los procedimientos completos de alta, cambio, baja y revisión están en los **Protocolos de seguridad** (`04-PROTOCOLOS-SEGURIDAD.md`, P-01 y P-02), que incluyen la matriz completa de permisos.

| Rol | Puede | ¿Ve HC? |
|---|---|---|
| `admin` | Todo, incluida la configuración. Único que crea otros `admin`. Máximo 2 | Sí |
| `admin_tecnico` | Usuarios (menos `admin`), sedes, camas, módulos, avisos, tickets, ledger, estado del sistema | **No** (en camas solo ve "Ocupada") |
| `medico` | Historia clínica, firma, órdenes, hospitalización, urgencias, agenda, refrendo de estudiantes, BI clínico | Sí |
| `enfermeria` | Triage, notas, kárdex, balance, signos, toma de muestras, módulos asignados | Sí |
| `estudiante` | Registra atenciones en **borrador**; no firma. El médico las refrenda | Sí |
| `admisiones` | Pacientes, agenda, recordatorios, PQRS | No |
| `facturacion` | Facturas, RIPS, pre-auditoría, BI financiero | No |
| `farmacia` | Inventario, entradas, dispensación | No |
| `laboratorio` | Toma, resultados y **validación** | No |
| `auxiliar_laboratorio` | Toma de muestras y digitación de resultados; **no valida** | No |
| `auditor` | Lectura de HC, ledger, indicadores, BI, RDA, estado del sistema | Sí (lectura) |
| `auditor_sistemas` | Ledger, accesos, RDA, estado del sistema, indicadores de gerencia | **No** |
| `paciente` | Deshabilitado mientras `PORTAL_PACIENTE_ACTIVO=false` | — |

**Crear un usuario:** rol (debajo aparece qué hace y si ve historias), documento, nombres, correo, registro profesional (obligatorio para `medico`, `enfermeria`, `laboratorio`, `farmacia` y `auditor`) y clave temporal (botón **Generar**). La clave se muestra una sola vez: entréguela en persona. En el primer ingreso el sistema obliga a cambiarla. Las columnas **MFA** ("Pendiente (obligatorio)") y **Clave** ("Temporal" o "Propia") muestran quién no ha cumplido.

**Carga masiva:** para crear a todo el personal de una vez, use la plantilla `docs/plantillas/usuarios_institucion.csv` y el comando:

```bash
docker compose cp usuarios.csv backend:/tmp/usuarios.csv
docker compose exec backend python -m app.crear_usuarios /tmp/usuarios.csv --salida /tmp/credenciales.csv
docker compose cp backend:/tmp/credenciales.csv ./credenciales.csv
docker compose exec backend rm /tmp/usuarios.csv /tmp/credenciales.csv
```

`credenciales.csv` trae una clave temporal distinta para cada persona: entréguelas en sobre cerrado y borre el archivo (detalle en el protocolo, sección 16).

**Desactivar** (no borrar) a quien deja la institución: botón **Desactivar**. Su historial queda intacto.

**Quitar el MFA** a alguien que perdió el celular: botón **Activo ✕** en la columna MFA, después de verificar su identidad. La acción queda en el ledger.

**Desbloquear:** el bloqueo por intentos dura 15 minutos y se libera solo.

**Olvidó la clave (incluso la del administrador) o necesita desbloquear ya:** desde el servidor ejecute

```bash
docker compose exec backend python -m app.restablecer_clave admin@xentra.co
```

Muestra una **clave temporal** nueva, quita el bloqueo, reactiva la cuenta y obliga a cambiar la clave al ingresar. Agregue `--quitar-mfa` si además perdió el celular del segundo factor (verifique antes su identidad, protocolo P-02). Queda en el ledger como `CLAVE_RESTABLECIDA_SERVIDOR`.

> El administrador inicial se crea **solo la primera vez** que arranca la base de datos, con la `ADMIN_PASSWORD` que tenía el `.env` en ese momento. Cambiar después esa variable no cambia la clave: use este comando.

### 6.2 Sedes y camas

- Las sedes se crean por API (`POST /api/sedes`, con el código de habilitación de 12 dígitos) o desde Swagger (`/docs`).
- Las camas se crean en **Hospitalización → Mapa de camas → Agregar cama**. Servicios: adultos, pediatría, obstetricia, UCI, intermedios, observación y neonatos.

### 6.3 Módulos adicionales

Menú **Módulos adicionales**:

- **Plantillas listas**: riesgo de caídas, eventos adversos, PQRS y seguimiento de gestantes.
- **Crear desde cero**: campos (texto, número, fecha, lista, sí/no, CIE-10), roles que consultan, roles que registran, si es por paciente y si se sella.
- Cada edición de la definición crea una **nueva versión**; los registros anteriores conservan la suya.

### 6.4 Avisos a los usuarios

**Soporte y continuidad → Avisos**: mensaje, nivel (información, mantenimiento o crítico) y fecha de vencimiento. Todos los usuarios lo ven arriba de la pantalla.

---

## 7. Catálogos oficiales

El sistema trae **muestras**. En producción cargue las tablas oficiales vigentes de SISPRO.

### 7.1 CIE-10

1. Descargue la tabla de referencia CIE-10 de SISPRO.
2. Prepare un CSV separado por `;` con las columnas `codigo;descripcion;sexo;edad_minima;edad_maxima` (sexo: A ambos, H hombre, M mujer), en UTF-8.
3. Cárguelo:
   ```bash
   docker compose cp cie10.csv backend:/tmp/cie10.csv
   docker compose exec backend python -m app.cargar_cie10 /tmp/cie10.csv --reemplazar
   ```

### 7.2 Demás tablas

CSV con columnas `codigo;descripcion;datos` (datos = JSON opcional; para CUPS, `{"valor": 45000}` define la tarifa que usa la pre-auditoría).

```bash
docker compose cp cups.csv backend:/tmp/cups.csv
docker compose exec backend python -m app.cargar_catalogo cups /tmp/cups.csv --reemplazar
```

Tipos disponibles: `cups`, `cum`, `divipola`, `eapb`, `tipo_usuario`, `modalidad`, `grupo_servicio`, `servicio`, `finalidad`, `causa_atencion`, `via_ingreso`, `condicion_egreso`, `concepto_recaudo`, `tipo_medicamento`.

Actualice CUPS cada año (resolución anual) y la CIE-10 cuando el Ministerio publique cambios.

---

## 8. Integraciones externas

Todas tienen modo **simulado** (para capacitar y probar sin enviar nada) y modo **real**.

### 8.1 Facturación electrónica DIAN

1. Contrate un proveedor tecnológico autorizado por la DIAN.
2. Adapte `DianReal.emitir` en `backend/app/services/integraciones.py` a la API de ese proveedor (entrada: datos de la factura; salida: CUFE y XML en base64).
3. Configure `DIAN_MODO=real`, `DIAN_PROVEEDOR_URL`, `DIAN_PROVEEDOR_TOKEN` y `FACTURA_PREFIJO`.
4. Pruebe primero en el ambiente de habilitación del proveedor.

### 8.2 MUV (validación FEV-RIPS)

1. Despliegue la API FEV-RIPS que publica el Ministerio, según su manual.
2. Configure `MUV_MODO=real`, `MUV_URL`, `MUV_USUARIO`, `MUV_CLAVE` y `MUV_TIPO_USUARIO`.
3. En *Facturación*, después de emitir, pulse **Validar MUV**: queda el CUV o el detalle del rechazo.

### 8.3 RDA – IHCE (Resolución 1888 de 2025 y 1799 de 2026)

1. Registre la IPS en la IHCE del Ministerio y obtenga la URL del API Gateway y la credencial.
2. Configure `RDA_MODO=real`, `IHCE_URL`, `IHCE_TOKEN` y `RDA_OPERACION_DISPENSACION` (si presta servicio farmacéutico).
3. Revise la cola en **Soporte y continuidad → RDA**:
   - `pendiente`: en espera de envío.
   - `enviado`: aceptado por la IHCE.
   - `simulado`: modo de prueba, no se envió.
   - `error`: falló la validación o se agotaron los intentos. Use **Reintentar**.
4. Programe `python -m app.procesar_rda` cada 5 a 10 minutos (sección 12).

**Plazos:** el RDA clínico es obligatorio desde el **15/04/2026**; el de dispensación, desde el **01/03/2027**.

### 8.4 Inteligencia artificial con Claude

1. Obtenga una API key en `console.anthropic.com`.
2. Configure `IA_PROVEEDOR=claude` y `ANTHROPIC_API_KEY`.
3. Antes de usarlo con pacientes reales: inclúyalo en la política de tratamiento de datos, revise la retención de datos del proveedor y evalúe la transferencia internacional. El texto se envía anonimizado.

### 8.5 Anclaje del ledger

`ANCLAJE_MODO=opentimestamps` y la tarea diaria `python -m app.anclar` (sección 12). Solo sale el hash del último bloque (32 bytes).

### 8.6 Telemedicina

`JITSI_URL`. Para mayor privacidad, instale un servidor Jitsi propio.

### 8.7 Notificaciones (WhatsApp / SMS / correo)

Hoy los recordatorios quedan en el log. Conecte su proveedor en la función `notificar` de `integraciones.py`.

---

## 9. Seguridad

### 9.1 Lo que ya trae el sistema

Argon2id, MFA, bloqueo por intentos, cierre por inactividad, roles en cada endpoint, triggers de inmutabilidad, usuario de BD sin privilegios, ledger con HMAC, anclaje externo, cabeceras de seguridad, HTTPS (producción) y errores sin detalles técnicos.

### 9.2 Lo que debe hacer el administrador

- [ ] Aplicar los **Protocolos de seguridad** (`04-PROTOCOLOS-SEGURIDAD.md`) y su lista de verificación.
- [ ] Exigir MFA con `MFA_OBLIGATORIO_ROLES=admin,admin_tecnico,auditor,auditor_sistemas,medico,facturacion`.
- [ ] Desactivar la cuenta inicial `admin@xentra.co` una vez creadas las cuentas personales, y apagar los usuarios demo (`CARGAR_DATOS_DEMO=false`).
- [ ] Revisar cada semana *Seguridad blockchain → Verificar cadena completa*.
- [ ] Revisar en el ledger los `LOGIN_FALLIDO` y `MFA_FALLIDO` repetidos.
- [ ] Mantener el servidor actualizado (`apt update && apt upgrade`) y Docker al día.
- [ ] Acceso SSH solo con llave y, si es posible, por VPN.
- [ ] Cifrado de disco en el servidor y respaldos cifrados.
- [ ] Prueba de penetración antes de producción y una vez al año.
- [ ] Desactivar de inmediato a quien deja la institución.

### 9.3 Interpretar la verificación de la cadena

| Resultado | Significado | Acción |
|---|---|---|
| Cadena íntegra | Nadie alteró ni borró registros de auditoría | Ninguna |
| "El contenido del bloque fue modificado" | Alguien cambió un bloque directamente en la BD | Incidente de seguridad: aislar, investigar y restaurar (`docs/11`) |
| "Falta el bloque N" | Se borraron bloques | Igual |
| "Firma HMAC inválida" | Se recalculó la cadena sin la llave | Igual |
| Anclaje "NO coincide" | La cadena fue reescrita después del anclaje | Igual |

---

## 10. Respaldos y restauración

### 10.1 Automático

- Respaldo **diario a las 02:00** en `./backups/xentra_AAAAMMDD_HHMMSS.dump`, con rotación de `RESPALDO_DIAS`.
- **Cada domingo** restaura el último respaldo en una base temporal y escribe el resultado en `backups/ultima_verificacion.txt`, que se ve en *Estado del sistema*.

### 10.2 Lo que debe hacer usted

- Copiar `./backups` **fuera del servidor cada día** (nube cifrada o disco externo). Un respaldo dentro del mismo servidor no protege contra ransomware.
- Guardar el `.env` en un lugar seguro y separado de los respaldos.

### 10.3 Respaldo manual

```bash
docker compose exec respaldo pg_dump -Fc -f /backups/manual_$(date +%Y%m%d).dump
```

### 10.4 Restaurar

```bash
docker compose stop backend
docker compose exec respaldo pg_restore -h db -U xentra -d xentra_hce --clean --if-exists /backups/ARCHIVO.dump
docker compose start backend
```

Después: *Seguridad blockchain → Verificar cadena completa*.

### 10.5 Recuperación ante desastre (servidor perdido)

1. Servidor nuevo con Docker.
2. Clonar el repositorio en la misma versión.
3. Restaurar el `.env` desde el gestor de secretos.
4. `docker compose up -d --build` (crea una base vacía con el esquema).
5. Copiar el último respaldo externo a `./backups` y restaurarlo (10.4).
6. Verificar la cadena y los anclajes.

---

## 11. Monitoreo y operación diaria

### 11.1 Panel de estado

**Soporte y continuidad → Estado del sistema** (admin y auditor):

| Indicador | Alerta cuando |
|---|---|
| Latencia de la BD | Supera 500 ms |
| Disco libre | Queda menos del 10 % |
| Último respaldo | Tiene más de 26 horas |
| Prueba de restauración | Dice "FALLÓ" |
| RDA | Hay envíos en estado `error` |
| Tickets | Hay ANS vencidos |
| Integraciones | Muestra el modo de cada una (simulado o real) |

### 11.2 Rutina diaria (5 minutos)

1. Revisar *Estado del sistema* (debe decir "operativo").
2. Confirmar la copia externa de los respaldos.
3. Revisar los tickets críticos.
4. Revisar la cola de RDA con error.

### 11.3 Monitoreo externo

Configure UptimeRobot o Uptime Kuma contra `https://SU-DOMINIO/api/salud`, que responde `{"estado":"ok"}`.

---

## 12. Tareas programadas

En el servidor, con `crontab -e`:

```cron
# Anclaje diario del ledger (02:30)
30 2 * * * cd /ruta/xentra-dataclinic && docker compose exec -T backend python -m app.anclar >> /var/log/xentra-anclaje.log 2>&1
# Cola de RDA cada 10 minutos
*/10 * * * * cd /ruta/xentra-dataclinic && docker compose exec -T backend python -m app.procesar_rda >> /var/log/xentra-rda.log 2>&1
# Copia externa de respaldos (ejemplo con rclone)
0 4 * * * rclone copy /ruta/xentra-dataclinic/backups remoto-cifrado:xentra-backups
```

Los **recordatorios de citas** los envía admisiones cada tarde desde **Agenda → Enviar recordatorios** (citas del día siguiente). Para automatizarlos, una herramienta externa debe llamar a `POST /api/citas/recordatorios` con un token de un usuario de admisiones.

---

## 13. Actualizaciones

1. Avise a los usuarios (**Avisos**, nivel "mantenimiento").
2. Haga un respaldo manual (10.3).
3. Actualice:
   ```bash
   git pull
   docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
   ```
4. El servicio `migrate` aplica solo las migraciones nuevas. Si falla, `backend` no arranca y los datos no se tocan: revise `docker compose logs migrate`.
5. Verifique la cadena y haga una prueba funcional.

---

## 14. Soporte a usuarios

### 14.1 Código de error

Cada falla inesperada muestra al usuario un código de 10 caracteres. Para encontrar la causa:

```bash
docker compose logs backend | grep CODIGO
```

### 14.2 Mesa de ayuda

- Tiempos máximos de respuesta (ANS): crítica 4 h, alta 8 h, media 24 h, baja 72 h.
- El administrador ve todos los tickets, los pasa a "en proceso" y los resuelve **escribiendo la solución**, que queda en la **base de conocimiento**.
- No se puede resolver un ticket sin escribir la solución.

### 14.3 Preguntas frecuentes de los usuarios

| Pregunta | Respuesta |
|---|---|
| "Me sacó del sistema" | Cierre por 15 minutos de inactividad (por seguridad) |
| "Usuario bloqueado" | 5 intentos fallidos: esperar 15 minutos |
| "Perdí el celular del MFA" | El admin quita el MFA tras verificar la identidad |
| "No puedo editar una atención" | Está firmada: se corrige con una nota aclaratoria |
| "El dictado no funciona" | Usar Chrome o Edge y permitir el micrófono |
| "El PDF no abre" | Permitir ventanas emergentes para el sitio |
| "No veo un menú" | El menú depende del rol del usuario |

---

## 15. Solución de problemas

| Síntoma | Causa probable | Solución |
|---|---|---|
| "No se puede acceder a este sitio" | El contenedor `frontend` no está arriba o Docker está apagado | `docker compose ps`; abrir Docker Desktop; `docker compose up -d` |
| `failed to connect to the docker API` | Docker Desktop apagado | Abrirlo y esperar a "Engine running" |
| `no configuration file provided` | Terminal fuera de la carpeta del proyecto | `cd` a la carpeta que contiene `docker-compose.yml` |
| `migrate` en Exited (1) | Claves del `.env` que no coinciden, o un error de migración | `docker compose logs migrate`; revisar `DATABASE_URL_MIGRACIONES` |
| `backend` en Restarting | `DATABASE_URL` incorrecta o `xentra_app` sin clave | `docker compose logs backend`; verificar `APP_DB_PASSWORD` |
| Mensaje "El servidor de XENTRA no responde" | La API está caída o reiniciándose | `docker compose logs backend --tail 100`; `docker compose restart backend` |
| `port is already allocated` | Puerto 8080 ocupado | Cambiar `"8080:80"` en `docker-compose.yml` |
| El HTTPS no se emite | DNS sin propagar o puertos 80/443 cerrados | Verificar el registro A y el firewall; `docker compose logs caddy` |
| "Sin datos" en respaldos | Carpeta no montada (fuera de Docker) | Es normal fuera de Docker; en Docker revisar `./backups` |
| Los RDA quedan en "pendiente" | Modo real sin `IHCE_URL`, o la IHCE no responde | Revisar la configuración; la cola reintenta sola |
| La factura no se emite | La pre-auditoría encontró errores | Leer los hallazgos de la factura y corregir la atención o los datos |
| Sale "permission denied" en la BD | Comportamiento esperado: `xentra_app` no puede alterar la auditoría | Ninguna; es una medida de seguridad |

---

## 16. Referencia de comandos

| Acción | Comando |
|---|---|
| Ver estado | `docker compose ps` |
| Logs en vivo | `docker compose logs -f backend` |
| Reiniciar la API | `docker compose restart backend` |
| Apagar | `docker compose down` |
| Encender | `docker compose up -d` |
| Actualizar | `git pull && docker compose up -d --build` |
| Borrar todo (solo pruebas) | `docker compose down -v` |
| Entrar a la BD | `docker compose exec db psql -U xentra xentra_hce` |
| Cargar CIE-10 | `docker compose exec backend python -m app.cargar_cie10 /tmp/archivo.csv` |
| Cargar catálogo | `docker compose exec backend python -m app.cargar_catalogo TIPO /tmp/archivo.csv` |
| Anclar el ledger | `docker compose exec backend python -m app.anclar` |
| Procesar RDA | `docker compose exec backend python -m app.procesar_rda` |
| Documentación de la API | `http://SU-DOMINIO/docs` |
