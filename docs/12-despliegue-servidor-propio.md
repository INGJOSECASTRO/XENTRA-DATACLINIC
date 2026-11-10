# Despliegue de XENTRA DATACLINIC en su propio equipo como servidor

Esta guía convierte el computador donde hoy prueba XENTRA (Windows + Docker Desktop) en el **servidor** de la institución. Va por niveles: haga el 1 y avance solo si lo necesita.

| Nivel | Quién entra | Qué necesita | Costo |
|---|---|---|---|
| **1. Red local** | Los equipos conectados al mismo router (una sede) | Nada adicional | $0 |
| **2. Remoto privado** | Personal autorizado desde su casa u otra sede, **sin publicar** el sistema en internet | Tailscale en cada equipo | $0 (hasta 3 usuarios y 100 equipos en el plan gratuito; verifique condiciones vigentes) |
| **3. Internet con dominio y HTTPS** | Cualquier equipo autorizado, con dirección tipo `https://hce.suips.com` | Un dominio + cuenta gratuita de Cloudflare | Solo el dominio (≈ USD 10–15 al año) |

> **Antes de empezar: ¿sirve un portátil como servidor?**
> Sirve para **piloto, capacitación o un consultorio pequeño**. Para una IPS u hospital con pacientes reales, el servidor debe ser un equipo **dedicado** (o un servidor en la nube) porque guarda historias clínicas: debe estar encendido 24/7, con UPS, disco cifrado, respaldos fuera del equipo y sin que nadie lo use para otras cosas (correo, navegación, WhatsApp). Ver la sección 6.

---

## 0. Preparar el equipo (una sola vez)

### 0.1 Requisitos mínimos

| Recurso | Mínimo | Recomendado |
|---|---|---|
| RAM | 8 GB | 16 GB |
| Disco | SSD con 50 GB libres | SSD de 256 GB o más |
| Sistema | Windows 10/11 64 bits con Docker Desktop | Windows 11 Pro (permite BitLocker) |
| Energía | — | UPS (regulador con batería) de 30 minutos |
| Red | Wi-Fi | **Cable de red** al router |

### 0.2 Que Docker arranque solo

1. Abra **Docker Desktop → Settings (⚙) → General**.
2. Active **Start Docker Desktop when you sign in to your computer**.
3. Pulse **Apply & restart**.

Los contenedores de XENTRA ya tienen `restart: unless-stopped`: cuando Docker arranca, la aplicación arranca sola.

### 0.3 Que el equipo no se duerma

**Configuración → Sistema → Inicio/apagado y batería** (o "Energía"):

- **Suspender** (con corriente): **Nunca**.
- **Apagar pantalla**: puede dejarlo en 10 minutos; la pantalla apagada no afecta.
- En un portátil: **Configuración → Sistema → Energía → Acción al cerrar la tapa → No hacer nada** (con corriente).

### 0.4 Que Windows Update no lo reinicie en horario de atención

**Configuración → Windows Update → Opciones avanzadas → Horas activas**: póngalas de 6:00 a 23:00. Los reinicios se harán de madrugada y Docker volverá a subir todo solo.

### 0.5 Inicio de sesión automático (opcional, recomendado en un equipo dedicado)

Docker Desktop arranca cuando alguien inicia sesión en Windows. Si se va la luz y el equipo se reinicia, nadie inicia sesión y XENTRA no sube. En un equipo **dedicado y en un cuarto con llave**, configure el inicio de sesión automático (herramienta *Autologon* de Microsoft Sysinternals). En un equipo de uso compartido **no** lo haga.

### 0.6 Configurar el archivo `.env` para producción

Abra el archivo `.env` de la carpeta del proyecto con el Bloc de notas y revise:

```bash
# Claves largas y aleatorias (genere cada una con el comando de abajo)
SECRET_KEY=...
LEDGER_HMAC_KEY=...
POSTGRES_PASSWORD=...
APP_DB_PASSWORD=...

# Protocolos de seguridad (docs/manuales/04-PROTOCOLOS-SEGURIDAD.md)
PORTAL_PACIENTE_ACTIVO=false
CAMBIO_CLAVE_PRIMER_INGRESO=true
MFA_OBLIGATORIO_ROLES=admin,admin_tecnico,auditor,auditor_sistemas,medico,facturacion
CARGAR_DATOS_DEMO=false
```

Para generar una clave aleatoria, en PowerShell:

```powershell
docker compose exec backend python -c "import secrets; print(secrets.token_urlsafe(48))"
```

> ⚠️ **`POSTGRES_PASSWORD` y `APP_DB_PASSWORD` solo se pueden cambiar así antes de crear la base de datos.** Si ya tiene datos de prueba y quiere empezar limpio para producción: `docker compose down -v` (**borra todos los datos**) y luego `docker compose up -d --build`. Si ya tiene datos reales, no lo haga: pida ayuda para cambiarlas dentro de PostgreSQL.
>
> ⚠️ **`LEDGER_HMAC_KEY`**: guárdela en un sobre sellado y en un gestor de contraseñas. Si se pierde, no se pueden verificar los bloques antiguos.

Los usuarios de demostración que ya se hayan creado **no se borran** al poner `CARGAR_DATOS_DEMO=false`: desactívelos en **Usuarios** o empiece con una base limpia.

---

## Nivel 1. Red local (una sede)

XENTRA ya escucha en el puerto **8080** de su equipo. Solo falta que los demás equipos lo encuentren.

### 1.1 Averiguar la IP del servidor

En PowerShell:

```powershell
ipconfig
```

Busque **Dirección IPv4** del adaptador que usa (Ethernet o Wi-Fi), por ejemplo `192.168.1.50`.

### 1.2 Fijar esa IP

Si la IP cambia, los demás equipos dejarán de encontrar el servidor. Dos opciones:

- **Recomendada:** en el router, opción *Reserva DHCP* / *IP estática por MAC*: asigne siempre la misma IP al servidor. La MAC aparece en `ipconfig /all` como *Dirección física*.
- **Alternativa:** IP fija en Windows: *Configuración → Red → Propiedades del adaptador → Asignación de IP → Manual*.

### 1.3 Abrir el puerto en el firewall de Windows

PowerShell **como administrador** (clic derecho → *Ejecutar como administrador*):

```powershell
New-NetFirewallRule -DisplayName "XENTRA 8080 (red local)" -Direction Inbound -Protocol TCP -LocalPort 8080 -Action Allow -Profile Private
```

Y marque la red como **privada**: *Configuración → Red e Internet → (su red) → Tipo de perfil de red → Privada*.

### 1.4 Probar desde otro equipo

En otro computador conectado al mismo router, abra el navegador en:

```
http://192.168.1.50:8080
```

(con la IP de su servidor). Debe ver la pantalla de ingreso de XENTRA.

### 1.5 Ajustar el `.env`

```bash
URL_PUBLICA=http://192.168.1.50:8080
CORS_ORIGINS=http://192.168.1.50:8080,http://localhost:8080
```

Aplique con `docker compose up -d`. `URL_PUBLICA` es la dirección que se imprime en los códigos QR de los documentos.

> En la red local el tráfico va **sin cifrar** (http). Úselo solo en una red cableada o un Wi-Fi propio con clave WPA2/WPA3, nunca en un Wi-Fi de invitados. Para cifrado, use el nivel 2 o 3.

---

## Nivel 2. Acceso remoto privado con Tailscale (sin publicar en internet)

Tailscale crea una **red privada cifrada** entre los equipos autorizados. El sistema **no queda expuesto** en internet: solo los equipos que usted agregue pueden verlo. Es la opción más segura para que médicos o directivos entren desde casa.

1. Cree una cuenta en `tailscale.com` (con el correo institucional).
2. Instale Tailscale en el **servidor** e inicie sesión. Anote el nombre o la IP que le asigna (tipo `100.x.y.z`).
3. Instale Tailscale en cada equipo o celular autorizado e inicie sesión con una cuenta invitada a su red.
4. Desde esos equipos, abra `http://100.x.y.z:8080`. El tráfico viaja cifrado por el túnel de Tailscale.
5. Agregue esa dirección a `CORS_ORIGINS` en el `.env`.

Para dar de baja a alguien, elimínelo de la consola de Tailscale el mismo día (protocolo P-01).

---

## Nivel 3. Internet con dominio propio y HTTPS (Cloudflare Tunnel)

Con un túnel de Cloudflare su equipo **sale** hacia Cloudflare y Cloudflare entrega las visitas por ese túnel. Ventajas:

- **No se abren puertos** en el router y no se necesita IP fija del proveedor de internet.
- **HTTPS automático** (candado verde) con certificado gratuito.
- Protección contra ataques de denegación de servicio.
- Funciona aunque su proveedor use CG-NAT (común en Colombia con fibra y 4G).

### 3.1 Comprar el dominio

Compre un dominio, por ejemplo `suips.com` o `suips.com.co`, en cualquier registrador o directamente en Cloudflare (*Domain Registration*). Para `.co` / `.com.co` también sirve un registrador colombiano.

### 3.2 Pasar el dominio a Cloudflare

1. Cree una cuenta gratuita en `dash.cloudflare.com`.
2. **Add a domain** → escriba su dominio → plan **Free**.
3. Cloudflare le muestra dos *nameservers* (ej. `ana.ns.cloudflare.com`). Póngalos en el panel de su registrador, en la opción *Nameservers / DNS*.
4. Espere el correo "your domain is now active" (de minutos a 24 horas).

### 3.3 Crear el túnel

1. En Cloudflare: **Zero Trust → Networks → Tunnels → Create a tunnel**.
2. Tipo **Cloudflared** → nombre: `xentra`.
3. En "Install and run a connector", elija **Docker**. Aparece un comando con `--token eyJh...`. **Copie solo el token** (el texto largo que empieza por `eyJ`). **No lo comparta**: quien lo tenga puede suplantar su túnel.
4. Siguiente → **Public Hostname**:
   - **Subdomain**: `hce`
   - **Domain**: su dominio
   - **Service**: Type `HTTP`, URL `frontend:80`
5. **Save tunnel**.

### 3.4 Configurar el `.env`

Agregue al final del `.env` (este archivo **nunca** se sube a GitHub):

```bash
CLOUDFLARE_TUNNEL_TOKEN=eyJh...el token completo...
URL_PUBLICA=https://hce.suips.com
CORS_ORIGINS=https://hce.suips.com,http://localhost:8080
```

### 3.5 Arrancar con el túnel

En PowerShell, en la carpeta del proyecto:

```powershell
docker compose -f docker-compose.yml -f docker-compose.tunel.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.tunel.yml ps
```

Debe aparecer el contenedor `tunel` en *running*, y en Cloudflare el túnel en estado **HEALTHY**.

Abra **https://hce.suips.com** desde el celular con datos móviles (fuera de su red) para confirmar que funciona.

> A partir de ahora use **siempre** los dos `-f` en los comandos (`up`, `ps`, `logs`, `down`). Si ejecuta solo `docker compose up -d`, el túnel no se levanta.

### 3.6 Capa extra recomendada: Cloudflare Access

Como XENTRA quedará en internet, agregue una puerta antes del login de XENTRA:

1. **Zero Trust → Access → Applications → Add an application → Self-hosted**.
2. Dominio: `hce.suips.com`.
3. Política: **Allow** → *Emails ending in* `@suips.com` (o la lista de correos autorizados).
4. Método: *One-time PIN* (llega un código al correo).

Así, quien no tenga un correo autorizado ni siquiera ve la pantalla de ingreso. Es gratuito hasta 50 usuarios (verifique condiciones vigentes).

### 3.7 Si se cae internet

El puerto 8080 sigue abierto en la red local: los equipos de la sede trabajan con `http://IP-DEL-SERVIDOR:8080` (nivel 1) hasta que vuelva internet. Si se cae el servidor, active el plan de contingencia en papel (`docs/11-plan-continuidad.md`).

---

## 4. Respaldos fuera del equipo (obligatorio)

El contenedor `respaldo` guarda una copia diaria en la carpeta `backups` del proyecto. Pero si el equipo se daña o se lo roban, se pierden **los datos y los respaldos**. Haga una copia **fuera**:

- **Opción sencilla:** instale **Google Drive para escritorio** u **OneDrive** y sincronice la carpeta `backups` con una carpeta de la nube institucional (no personal).
- **Opción adicional:** cada semana, copie `backups` a un disco externo que se guarde en otro lugar.

Los respaldos contienen historias clínicas: la cuenta en la nube debe tener verificación en dos pasos, y el disco externo debe estar cifrado (BitLocker To Go).

**Prueba de restauración:** el sistema prueba automáticamente cada domingo que el último respaldo se puede restaurar. Revise el resultado en **Soporte y continuidad → Estado del sistema**.

---

## 5. Operación diaria

| Tarea | Comando o lugar |
|---|---|
| Ver si todo está arriba | `docker compose -f docker-compose.yml -f docker-compose.tunel.yml ps` |
| Ver errores del backend | `docker compose -f docker-compose.yml -f docker-compose.tunel.yml logs backend --tail 50` |
| Actualizar a una nueva versión | `git pull` y luego `docker compose -f docker-compose.yml -f docker-compose.tunel.yml up -d --build` |
| Desbloquear o restablecer una clave | `docker compose exec backend python -m app.restablecer_clave correo@...` |
| Estado general | Menú **Soporte y continuidad → Estado del sistema** |
| Integridad de la cadena | Menú **Seguridad blockchain → Verificar cadena completa** |

(Si usa solo el nivel 1 o 2, omita `-f docker-compose.yml -f docker-compose.tunel.yml`.)

Antes de actualizar, verifique que exista un respaldo reciente en `backups`.

---

## 6. Seguridad del equipo servidor

Además de los protocolos de `docs/manuales/04-PROTOCOLOS-SEGURIDAD.md`:

- [ ] **Equipo dedicado**: nadie lo usa para correo, navegación, redes sociales ni descargas.
- [ ] **Cuenta de Windows con contraseña fuerte** y bloqueo automático de pantalla.
- [ ] **BitLocker** activado (Windows Pro: *Configuración → Privacidad y seguridad → Cifrado del dispositivo / BitLocker*). Guarde la clave de recuperación fuera del equipo. Si roban el equipo, los datos no se pueden leer.
- [ ] **Windows Defender** activo y Windows actualizado.
- [ ] **UPS** para que un corte de luz no dañe la base de datos.
- [ ] **Ubicación física** en un lugar con llave, no en la recepción.
- [ ] El puerto 5432 (base de datos) **nunca** se publica: ya viene cerrado en `docker-compose.yml`.
- [ ] `.env` y `backups` **nunca** se suben a GitHub (ya están en `.gitignore`).
- [ ] Respaldos fuera del equipo funcionando (sección 4).

### ¿Cuándo pasar a un servidor de verdad?

| Señal | Siguiente paso |
|---|---|
| Más de 10–15 usuarios simultáneos, o varias sedes | Servidor dedicado (torre con Linux) en la IPS, o servidor en la nube |
| Atención 24 horas (urgencias, hospitalización) | Servidor con UPS, disco espejo (RAID 1) y un segundo equipo de reserva |
| Exigencias de la EPS, auditoría o habilitación | Servidor en la nube con proveedor certificado (ISO 27001) y contrato de transmisión de datos (Ley 1581) |

Para un servidor Linux en la nube con dominio, la ruta ya está lista: `docker-compose.prod.yml` (Caddy con HTTPS automático). Ver el Manual del administrador técnico, sección 3.2.
