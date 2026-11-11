# Paso a producción de XENTRA DATACLINIC

Esta guía lleva a XENTRA de "funciona en pruebas" a "atiende pacientes reales" de forma segura. El sistema tiene tres protecciones que impiden salir a producción a medias:

| Protección | Qué hace |
|---|---|
| **Interruptor de seguridad** | Con `ENTORNO=produccion`, el servidor **no arranca** si detecta claves de ejemplo, datos demo o tablas automáticas |
| **Preparador del `.env`** (`scripts/preparar_produccion.py`) | Genera todas las claves al azar y deja la configuración de producción lista |
| **Verificador** (`python -m app.verificar_produccion`) | Revisa configuración, usuarios, ledger, catálogos y respaldos, y dice en español qué falta |

Además, en producción:
- se oculta la documentación técnica de la API (`/docs`);
- el administrador inicial debe cambiar su clave en el primer ingreso;
- los registros (logs) tienen tamaño máximo, para que no llenen el disco.

---

## Parte 1. Lo que NO es código (y es obligatorio)

El software está listo, pero **operar una historia clínica con pacientes reales exige trámites que solo la institución puede hacer**. Revíselos con jurídica antes de la fecha de arranque:

| # | Requisito | Para qué | Con quién |
|---|---|---|---|
| 1 | **Código de habilitación (REPS)** y NIT reales en el `.env` | RIPS y facturas con datos válidos | Secretaría de Salud / REPS |
| 2 | **Política de tratamiento de datos** y aviso de privacidad (Ley 1581 de 2012, Decreto 1377 de 2013) | Los datos de salud son sensibles | Jurídica |
| 3 | **Registro de bases de datos ante la SIC (RNBD)**, si aplica según los activos de la entidad (Decreto 090 de 2018) | Obligación legal de responsables de datos | SIC |
| 4 | **Habilitación como facturador electrónico** y contrato con un **proveedor tecnológico** autorizado | Facturación electrónica real (`DIAN_MODO=real`) | DIAN + proveedor |
| 5 | **Usuario del MUV** (SISPRO) | Validar FEV-RIPS y obtener el CUV (`MUV_MODO=real`) | Ministerio de Salud |
| 6 | **Registro ante la IHCE** | Enviar el RDA (Res. 1888 de 2025; `RDA_MODO=real`) | Ministerio de Salud |
| 7 | **Catálogos oficiales completos** (CIE-10, CUPS, CUM…) | XENTRA trae solo una muestra | SISPRO (descarga pública) |
| 8 | **Prueba de penetración** (pentest) por un tercero | Encontrar vulnerabilidades antes que un atacante | Empresa de seguridad |
| 9 | **Piloto controlado** (1 servicio, 2 a 4 semanas) | Corregir con usuarios reales antes de extender | Dirección + jefes de área |
| 10 | **Capacitación** por rol y firma de acuerdos de confidencialidad | Protocolos de seguridad P-01 y P-08 | Talento humano |

Mientras se completan los trámites 4 a 6, XENTRA puede operar con esas integraciones en modo `simulado`: la historia clínica, la agenda, la hospitalización y el resto funcionan, y la facturación y el RDA se pueden completar después.

---

## Parte 2. Elegir dónde corre

| Opción | Cuándo | Archivo |
|---|---|---|
| **A. Su equipo + VPN (HCE privada)** | Piloto o consultorio pequeño; nadie la ve desde internet | `docker-compose.vpn.yml`, guía 13 |
| **B. VPS (por ejemplo Hostinger) + HTTPS** | Producción 24/7, varias sedes | `docker-compose.prod.yml` |
| **B + VPN** | VPS siempre encendido y además privado (lo más recomendado para la HCE) | `docker-compose.prod.yml` o `docker-compose.vpn.yml` en el VPS |

Para un VPS: mínimo 4 GB de RAM (mejor 8 GB), 2 núcleos y 80 GB de disco SSD, con Ubuntu 24.04 LTS. Si el centro de datos está fuera de Colombia, documente la transferencia internacional de datos (Ley 1581).

---

## Parte 3. Paso a paso técnico

### Paso 1. Traer la última versión

```bash
git pull
```

### Paso 2. Generar el `.env` de producción (con claves aleatorias)

**Windows (PowerShell):**

```powershell
docker run --rm -v "${PWD}:/xentra" -w /xentra python:3.13-slim python scripts/preparar_produccion.py --modo vpn --dominio sudominio.com --nit 901234567 --razon-social "IPS EJEMPLO SAS" --cod-habilitacion 110010000001
```

**Linux / VPS:**

```bash
docker run --rm -v "$PWD:/xentra" -w /xentra python:3.13-slim python scripts/preparar_produccion.py --modo https --dominio sudominio.com --nit 901234567 --razon-social "IPS EJEMPLO SAS" --cod-habilitacion 110010000001
```

- `--modo vpn` → HCE privada (`vpn.sudominio.com`). `--modo https` → en internet (`hce.sudominio.com`).
- El script muestra **una sola vez** la clave temporal del administrador: **anótela**.
- **Guarde la línea `LEDGER_HMAC_KEY`** del `.env` en un sobre sellado y en un gestor de contraseñas.
- Si había un `.env`, queda una copia (`.env.anterior-FECHA`).

### Paso 3. Empezar con una base de datos limpia

El `.env` nuevo trae claves de base de datos **nuevas**. Si este equipo tenía la base de **pruebas**, bórrela:

```bash
docker compose down -v
```

> ⚠️ `-v` **borra todos los datos**. Hágalo solo con datos de prueba. **Nunca** si ya hay pacientes reales.

### Paso 4. DNS en Hostinger (o en su proveedor de dominio)

hPanel → **Dominios** → su dominio → **DNS / Nameservers** → **Administrar registros DNS**:

| Modo | Tipo | Nombre | Apunta a |
|---|---|---|---|
| VPN con IP dinámica | CNAME | `vpn` | `su-subdominio.duckdns.org` |
| VPN con IP fija o VPS | A | `vpn` | IP pública del servidor |
| HTTPS en VPS | A | `hce` | IP pública del VPS |

### Paso 5. Arrancar

```bash
# Modo VPN (HCE privada):
docker compose -f docker-compose.yml -f docker-compose.vpn.yml up -d --build

# Modo HTTPS (VPS con dominio; puertos 80 y 443 abiertos):
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Si el `.env` tuviera algo inseguro, el contenedor `backend` no arrancará y lo dirá en el log:

```bash
docker compose logs backend --tail 20
```

### Paso 6. Cargar los catálogos oficiales

1. Descargue la tabla **CIE-10** de SISPRO (`web.sispro.gov.co` → Tablas de referencia).
2. Guárdela como CSV separado por `;` con las columnas `codigo;descripcion;sexo;edad_minima;edad_maxima`.
3. Cárguela:

```bash
docker compose cp cie10.csv backend:/tmp/cie10.csv
docker compose exec backend python -m app.cargar_cie10 /tmp/cie10.csv --reemplazar
```

Haga lo mismo con las demás tablas de referencia con `python -m app.cargar_catalogo` (ver Manual del administrador técnico, sección 7).

### Paso 7. Primer ingreso y usuarios reales

1. Ingrese con el administrador inicial y la **clave temporal** del paso 2. El sistema le pide cambiarla y activar el MFA.
2. Cree las **cuentas personales** de los 1 o 2 administradores reales.
3. Cargue al personal con la plantilla `docs/plantillas/usuarios_institucion.csv`:

```bash
docker compose cp usuarios.csv backend:/tmp/usuarios.csv
docker compose exec backend python -m app.crear_usuarios /tmp/usuarios.csv --salida /tmp/credenciales.csv
docker compose cp backend:/tmp/credenciales.csv ./credenciales.csv
docker compose exec backend rm /tmp/usuarios.csv /tmp/credenciales.csv
```

4. Entregue las claves temporales en sobre cerrado y **borre `credenciales.csv`**.
5. Desactive la cuenta inicial (`admin@...`) en **Usuarios**.

### Paso 8. Verificar

```bash
docker compose exec backend python -m app.verificar_produccion
```

Ejemplo de lo que muestra:

```
  ❌ El CIE-10 tiene solo 217 códigos (muestra). Cargue la tabla oficial de SISPRO ...
  ❌ 11 usuarios de demostración activos con clave pública (ejecute con --desactivar-demo)
  ⚠️  MUV (validación RIPS) en modo 'simulado': no se envía nada real hasta configurarlo
  ✅ Cadena del ledger íntegra (63 bloques)
  ✅ Último respaldo: xentra_20261111_020000.dump
```

- **❌ CRÍTICO:** debe resolverse antes de atender pacientes.
- **⚠️ AVISO:** se puede arrancar, pero hay que tenerlo presente (por ejemplo, integraciones aún simuladas).
- Si quedaron usuarios demo de una instalación anterior: `python -m app.verificar_produccion --desactivar-demo`.

**No atienda pacientes reales hasta que diga `LISTO para producción`.**

### Paso 9. Respaldos fuera del servidor

Sincronice la carpeta `backups` con una nube institucional (Google Drive u OneDrive con verificación en dos pasos) o cópiela cada semana a un disco externo cifrado. Ver guía 12, sección 4.

---

## Parte 4. El día del arranque

| Momento | Acción |
|---|---|
| Día anterior | `verificar_produccion` en verde. Respaldo manual. Avisar a todo el personal |
| Hora 0 | Arranca el **servicio piloto**. Soporte presente en el servicio (no solo por teléfono) |
| Primeras 2 horas | Revisar `docker compose logs backend` y la mesa de ayuda cada 30 minutos |
| Fin del día 1 | Reunión de 15 minutos: qué falló y qué se corrige. Verificar la cadena del ledger |
| Semana 1 | Ajustes diarios; formatos en papel listos por si hay contingencia (`docs/11-plan-continuidad.md`) |
| Semana 2–4 | Si el piloto es estable, extender servicio por servicio |

## Parte 5. Si algo sale mal (volver atrás)

| Situación | Qué hacer |
|---|---|
| El backend no arranca tras una actualización | `docker compose logs backend --tail 50`; si es urgente, volver a la versión anterior: `git checkout <commit-anterior>` y `docker compose up -d --build` |
| Se dañaron datos | Restaurar el último respaldo (Manual del administrador técnico, sección 10.4) |
| El servidor se perdió | Plan de recuperación ante desastre (Manual del administrador técnico, sección 10.5) |
| Sospecha de ataque | Protocolo P-09 de respuesta a incidentes |

## Parte 6. Mantenimiento

| Frecuencia | Tarea |
|---|---|
| Diaria | Panel **Estado del sistema**; revisar que exista el respaldo del día |
| Semanal | **Verificar cadena completa**; revisar intentos fallidos de ingreso |
| Mensual | `verificar_produccion`; revisión de usuarios (P-01); actualizar el servidor |
| Trimestral | Prueba de restauración de un respaldo; recertificación de accesos |
| Anual | Prueba de penetración; revisión de protocolos y de este documento |

Para actualizar XENTRA: verifique que exista un respaldo reciente, ejecute `git pull` y repita el comando del paso 5 (con `--build`). El contenedor `migrate` aplica solo las migraciones nuevas, sin perder datos.
