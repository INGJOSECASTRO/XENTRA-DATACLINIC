# 2. Guía de instalación para principiantes (paso a paso, sin saltarse nada)

Esta guía asume que **nunca ha instalado nada de programación**. Siga los pasos en orden.
Las líneas que están dentro de un recuadro gris son **comandos**: se copian y se pegan en la **terminal**.

> **¿Qué es la terminal?** Es una ventana donde se escriben órdenes al computador.
> - **Windows**: menú Inicio → escriba `PowerShell` → ábralo.
> - **Mac**: presione `Cmd + Espacio` → escriba `Terminal` → Enter.
> - **Linux**: `Ctrl + Alt + T`.

---

## Opción A (recomendada): con Docker – lo más fácil

Docker es un programa que crea "cajas" (contenedores) con todo lo necesario ya instalado: la base de datos,
el backend y el frontend. Usted no tiene que instalar Python, Node ni PostgreSQL por separado.

### Paso 1. Instalar Git

Git sirve para descargar el código y guardar versiones.

- **Windows/Mac**: descargue desde https://git-scm.com/downloads e instale con las opciones por defecto (Siguiente, Siguiente…).
- **Linux (Ubuntu)**: `sudo apt install git`

Verifique en la terminal:
```bash
git --version
```
Debe aparecer algo como `git version 2.x`. Si dice "no se reconoce el comando", cierre y vuelva a abrir la terminal.

### Paso 2. Instalar Docker Desktop

- Descargue desde https://www.docker.com/products/docker-desktop/ e instálelo.
- **Windows**: si le pide activar **WSL 2**, acepte y reinicie el computador.
- Abra Docker Desktop y espere a que diga **"Engine running"** (motor en ejecución).

Verifique:
```bash
docker --version
docker compose version
```

### Paso 3. Descargar el proyecto

```bash
cd Documentos
git clone https://github.com/ingjosecastro/xentra-dataclinic.git
cd xentra-dataclinic
```

> `cd` significa "entrar a la carpeta". Ahora está dentro de la carpeta del proyecto.

### Paso 4. Crear el archivo de configuración `.env`

El archivo `.env` guarda las claves secretas. **Nunca** se sube a GitHub.

- **Windows (PowerShell)**: `copy .env.example .env`
- **Mac/Linux**: `cp .env.example .env`

Ahora ábralo con un editor (recomendado: **Visual Studio Code**, https://code.visualstudio.com):
```bash
code .env
```

Cambie **todos** los valores que dicen `CAMBIAR`:

1. `POSTGRES_PASSWORD`: una clave larga para la base de datos (usuario dueño, solo para migraciones).
2. `DATABASE_URL_MIGRACIONES`: ponga **la misma clave** en lugar de `CAMBIAR_clave_bd_muy_segura`.
3. `APP_DB_PASSWORD`: otra clave distinta, para el usuario sin privilegios con el que corre la API, y póngala
   también dentro de `DATABASE_URL` en lugar de `CAMBIAR_clave_usuario_aplicacion`.
4. `SECRET_KEY` y `LEDGER_HMAC_KEY`: textos aleatorios largos. Para generarlos, si tiene Python:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(64))"
   ```
   Si no tiene Python, use un generador de contraseñas de 64 caracteres (sin espacios ni comillas).
5. `ADMIN_PASSWORD`: la clave del administrador (mínimo 10 caracteres, mayúsculas, minúsculas y números).
6. `URL_PUBLICA`: la dirección con la que se abrirá el sistema (se imprime en los QR de los documentos).
7. `PRESTADOR_NIT`, `PRESTADOR_COD_HABILITACION` (12 dígitos del REPS) y `PRESTADOR_RAZON_SOCIAL`: los datos de su IPS.

> ⚠️ **Guarde una copia segura de `LEDGER_HMAC_KEY`** (por ejemplo en un gestor de contraseñas).
> Si la pierde, no podrá verificar la cadena de auditoría antigua.

Guarde el archivo (`Ctrl + S`).

### Paso 5. Levantar el sistema

```bash
docker compose up -d --build
```

- La primera vez tarda varios minutos (descarga imágenes y compila).
- `-d` significa que queda corriendo en segundo plano.

Verifique que los 3 contenedores estén arriba:
```bash
docker compose ps
```
Deben aparecer `db`, `backend`, `frontend` y `respaldo` en estado `running` / `healthy`.
El servicio `migrate` aparece como `exited (0)`: es normal, crea/actualiza las tablas y termina.

### Paso 6. Entrar al sistema

Abra el navegador en: **http://localhost:8080**

- Usuario: `admin@xentra.co` (o el que puso en `ADMIN_EMAIL`)
- Clave: la que puso en `ADMIN_PASSWORD`

Si dejó `CARGAR_DATOS_DEMO=true`, también puede entrar como `medico@xentra.co`, `enfermeria@xentra.co`,
`admisiones@xentra.co`, `facturacion@xentra.co`, `farmacia@xentra.co`, `laboratorio@xentra.co` o
`auditor@xentra.co`, todos con la clave `Demo12345*`.

La documentación técnica interactiva de la API (para programadores) está en **http://localhost:8080/docs**.

### Paso 7. Prueba guiada (10 minutos)

1. Entre como **medico@xentra.co**.
2. Menú **Pacientes** → abra "José Rodríguez Mejía".
3. Botón **+ Nueva atención**.
4. En *Motivo de consulta* escriba: `Dolor de cabeza y presión alta desde hace 3 días`.
5. Llene signos vitales: TA 168/102, peso 82, talla 170. Verá el IMC calculado.
6. En el recuadro morado **Asistente IA CIE-10** haga clic en **Sugerir diagnósticos**. Agregue `I10X`.
7. Haga clic en **Firmar y cerrar folio** y confirme.
8. En el folio firmado haga clic en **Verificar integridad** → debe decir que coincide.
9. Intente agregar una **nota aclaratoria**.
10. Antes de firmar, ponga un valor en "Valor del servicio". Cierre sesión, entre como **facturacion@xentra.co** →
    **Facturación electrónica** (o **RIPS (generar y validar)** para validar antes de facturar) → marque la atención, escriba el pagador → **Armar factura** → **Emitir DIAN** →
    **Validar MUV** → **RIPS** (descarga el JSON). En modo simulado no se envía nada a entidades externas.
11. Entre como **auditor@xentra.co** → **Seguridad blockchain** → **Verificar cadena completa**. Verá todos los
    accesos que hizo, incluida la consulta de la historia.

Para recorrer agenda, urgencias, hospitalización, laboratorio, farmacia, facturación y portal del paciente,
siga el [manual por módulo](09-manual-modulos.md).

### Comandos útiles del día a día

| Quiero… | Comando |
|---|---|
| Ver si está corriendo | `docker compose ps` |
| Ver los mensajes/errores del backend | `docker compose logs -f backend` |
| Apagar todo (los datos se conservan) | `docker compose down` |
| Encender de nuevo | `docker compose up -d` |
| Actualizar después de cambiar el código | `git pull` y luego `docker compose up -d --build` |
| Ver los respaldos automáticos (diarios, 2 a. m.) | carpeta `backups/` del proyecto |
| Respaldo manual inmediato | `docker compose exec respaldo pg_dump -Fc -f /backups/manual.dump` |
| Restaurar un respaldo | `docker compose exec respaldo pg_restore -h db -U xentra -d xentra_hce --clean --if-exists /backups/ARCHIVO.dump` |
| Anclar el ledger (ponerlo en cron diario) | `docker compose exec backend python -m app.anclar` |
| ⚠️ Borrar TODO, incluidos los datos | `docker compose down -v` (¡solo en pruebas!) |

### Cargar las demás tablas oficiales (CUPS, CUM, DIVIPOLA, EAPB, tablas RIPS)

Igual que la CIE-10: CSV con `codigo;descripcion[;datos]` (datos = JSON opcional, por ejemplo `{"valor": 45000}`
para la tarifa de un CUPS) y:
```bash
docker compose cp cups.csv backend:/tmp/cups.csv
docker compose exec backend python -m app.cargar_catalogo cups /tmp/cups.csv --reemplazar
```
Tipos: `cups, cum, divipola, eapb, tipo_usuario, modalidad, grupo_servicio, servicio, finalidad, causa_atencion,
via_ingreso, condicion_egreso, concepto_recaudo, tipo_medicamento`.

### Cargar el catálogo CIE-10 oficial completo

El sistema trae una **muestra de ~220 códigos frecuentes**. Para producción cargue el catálogo oficial:

1. Descargue la tabla de referencia **CIE10** de SISPRO (web.sispro.gov.co → Tablas de referencia).
2. Ábrala en Excel y deje estas columnas en este orden: `codigo;descripcion;sexo;edad_minima;edad_maxima`
   (sexo: `A` ambos, `H` hombre, `M` mujer; edades en años).
3. Guárdela como **CSV (delimitado por punto y coma)** con codificación UTF-8, en la carpeta del proyecto, con el nombre `cie10.csv`.
4. Ejecute:
   ```bash
   docker compose cp cie10.csv backend:/tmp/cie10.csv
   docker compose exec backend python -m app.cargar_cie10 /tmp/cie10.csv
   ```

---

## Opción B: sin Docker (para desarrollar y modificar el código)

Use esta opción cuando quiera programar y ver los cambios al instante.

### B.1 Instalar los programas

1. **Python 3.12 o superior**: https://www.python.org/downloads/ — en Windows marque la casilla **"Add Python to PATH"**.
2. **Node.js 22 LTS**: https://nodejs.org
3. **PostgreSQL 16**: https://www.postgresql.org/download/ — anote la clave del usuario `postgres` que le pida el instalador.
4. **Visual Studio Code** con las extensiones *Python* y *Vue - Official*.

Verifique:
```bash
python --version
node --version
psql --version
```

### B.2 Crear la base de datos

```bash
psql -U postgres
```
Dentro de `psql` escriba (cambie la clave):
```sql
CREATE USER xentra WITH PASSWORD 'mi_clave_segura';
CREATE DATABASE xentra_hce OWNER xentra;
\q
```

### B.3 Backend

```bash
cd backend
python -m venv .venv
```
Active el entorno virtual (una "caja" de Python solo para este proyecto):
- **Windows**: `.venv\Scripts\activate`
- **Mac/Linux**: `source .venv/bin/activate`

Verá `(.venv)` al inicio de la línea. Luego:
```bash
pip install -r requirements-dev.txt
```
Cree el archivo `backend/.env` con al menos:
```
DATABASE_URL=postgresql+psycopg://xentra:mi_clave_segura@localhost:5432/xentra_hce
SECRET_KEY=pon_aqui_un_texto_aleatorio_largo_de_al_menos_32_caracteres
LEDGER_HMAC_KEY=pon_aqui_otro_texto_aleatorio_largo_de_al_menos_32
ADMIN_PASSWORD=Admin12345*
```
Arranque el servidor:
```bash
uvicorn app.main:app --reload
```
Abra http://localhost:8000/docs para ver la API.

### B.4 Frontend (en OTRA terminal)

```bash
cd frontend
npm install
npm run dev
```
Abra http://localhost:5173. Las llamadas a `/api` se reenvían automáticamente al backend del puerto 8000.

### B.5 Correr las pruebas automáticas

```bash
cd backend
pytest
```
Debe ver `43 passed`. Para probar contra PostgreSQL real (incluye los triggers):
```bash
# Mac/Linux
TEST_DATABASE_URL=postgresql+psycopg://xentra:mi_clave@localhost:5432/xentra_test pytest
```
(cree antes la base `xentra_test`). **Nunca** apunte las pruebas a la base de producción: las pruebas la borran.

---

## Problemas frecuentes

| Síntoma | Solución |
|---|---|
| `docker: command not found` | Docker Desktop no está abierto o no se instaló. Ábralo y espere "Engine running". |
| `port is already allocated` (8080 u 8000 ocupado) | Otro programa usa ese puerto. Cambie `"8080:80"` por `"8081:80"` en `docker-compose.yml`. |
| El backend se reinicia en bucle | `docker compose logs backend`. Casi siempre es la clave de `DATABASE_URL` distinta a `POSTGRES_PASSWORD`. |
| Cambié la clave en `.env` y la BD no conecta | La clave de PostgreSQL se fija la primera vez. En pruebas: `docker compose down -v` y vuelva a levantar. |
| "Correo o contraseña incorrectos" con el admin | El admin se crea solo la primera vez. Si cambió `ADMIN_PASSWORD` después, use la clave original. |
| "Usuario bloqueado temporalmente" | 5 intentos fallidos: espere 15 minutos. |
| `python` no se reconoce (Windows) | Reinstale Python marcando "Add Python to PATH", o use `py` en lugar de `python`. |

---

## Llevarlo a producción (servidor en la nube) con HTTPS

1. Servidor Linux (Ubuntu 24.04) con mínimo 4 GB de RAM, **alojado preferiblemente en Colombia o en un país con
   nivel adecuado de protección de datos** (la transferencia internacional de datos personales tiene reglas en la Ley 1581).
2. Instale Docker (`curl -fsSL https://get.docker.com | sh`) y Git; clone el proyecto y cree el `.env` como en los pasos 3 y 4.
3. Compre un dominio (ej. `hce.miips.com`) y cree un registro DNS tipo **A** que apunte a la IP del servidor.
4. En `.env`: `DOMINIO=hce.miips.com`, `URL_PUBLICA=https://hce.miips.com`, `CORS_ORIGINS=https://hce.miips.com`,
   `CARGAR_DATOS_DEMO=false` y todas las claves cambiadas.
5. Abra los puertos 80 y 443 en el firewall del servidor y ejecute:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
   ```
   Caddy obtiene y renueva solo el certificado HTTPS. El frontend y la API quedan accesibles únicamente por HTTPS.
6. Copie la carpeta `backups/` fuera del servidor todos los días (cifrada) y pruebe restaurar una vez al mes.
7. La HC debe conservarse mínimo **15 años** desde la última atención (Resolución 839 de 2017): planifique el almacenamiento.
8. Cambie a modo real las integraciones (`DIAN_MODO`, `MUV_MODO`, `ANCLAJE_MODO=opentimestamps`) cuando tenga las credenciales.
