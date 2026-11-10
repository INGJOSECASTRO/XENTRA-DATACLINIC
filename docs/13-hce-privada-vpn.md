# HCE privada: acceso a XENTRA solo por VPN (WireGuard)

Con esta configuración la historia clínica **no se publica en internet**. Nadie puede ver ni siquiera la pantalla de ingreso, a menos que tenga en su equipo un **perfil de VPN** que usted le entregó. Es la opción más segura para datos de salud, porque **los datos nunca salen de su servidor ni pasan por empresas externas**.

| Pieza | Qué hace | Licencia | Costo |
|---|---|---|---|
| **WireGuard** | Túnel cifrado entre cada equipo autorizado y su servidor | Código abierto | $0 |
| **wg-easy** | Panel web para crear y revocar perfiles con código QR | Código abierto | $0 |
| **DuckDNS** (opcional) | Nombre fijo (`suips.duckdns.org`) aunque su IP pública cambie | Gratuito | $0 |

```
 Médico en casa / otra sede                         Su servidor (Docker)
 ┌──────────────────────┐   túnel WireGuard    ┌───────────────────────────────┐
 │ App WireGuard activa │══════(cifrado)═════▶ │ vpn (UDP 51820) ──▶ XENTRA    │
 │ http://172.30.77.10  │                      │                 172.30.77.10  │
 └──────────────────────┘                      └───────────────────────────────┘
 Sin perfil de VPN ──────────────✖  no ve nada (no hay ningún puerto web abierto a internet)
```

---

## Paso 1. ¿Tiene IP pública?

WireGuard necesita que los equipos de afuera puedan llegar a su router.

1. Entre al router (normalmente `http://192.168.1.1` o `192.168.0.1`; el usuario y la clave suelen estar en una etiqueta debajo del router). Busque **IP WAN** o **IP de Internet**.
2. En el navegador abra `https://ifconfig.me`.
3. Compare:
   - **Son iguales** → tiene IP pública. Siga con el paso 2.
   - **Son distintas**, o la IP WAN empieza por `100.64` a `100.127`, `10.` o `192.168.` → su proveedor usa **CG-NAT**. Llame al proveedor y pida una **IP pública** (algunos la dan gratis y otros cobran un valor mensual), o use la alternativa de la sección 9.

## Paso 2. Nombre fijo con DuckDNS (si su IP cambia)

La mayoría de los planes de hogar y pyme cambian la IP pública de vez en cuando. DuckDNS le da un nombre que siempre apunta a su IP actual.

1. Entre a `https://www.duckdns.org` e inicie sesión (con Google o GitHub).
2. En **sub domain** escriba un nombre (ej. `suips-hce`) y pulse **add domain**. Le queda `suips-hce.duckdns.org`.
3. Copie el **token** que aparece arriba. Es secreto: no lo comparta.

Si su IP pública es fija (contratada), puede saltarse este paso y usar la IP directamente.

## Paso 3. Abrir el puerto de la VPN en el router

En el router, sección **Reenvío de puertos** / **Port forwarding** / **NAT** / **Servidor virtual**:

| Campo | Valor |
|---|---|
| Protocolo | **UDP** |
| Puerto externo | **51820** |
| IP interna | La IP fija de su servidor (ej. `192.168.1.50`; ver guía 12, sección 1.2) |
| Puerto interno | **51820** |

> Es el **único** puerto que se abre. **No** reenvíe el 8080, el 80 ni el 443: XENTRA no debe ser visible desde internet.

Y en el firewall de Windows, en PowerShell **como administrador**:

```powershell
New-NetFirewallRule -DisplayName "XENTRA VPN WireGuard" -Direction Inbound -Protocol UDP -LocalPort 51820 -Action Allow
```

## Paso 4. Clave del panel de la VPN

El panel de wg-easy se protege con una clave, que se guarda cifrada (hash). Genérela en PowerShell, cambiando `SuClaveDelPanel` por una clave larga suya:

```powershell
docker run --rm ghcr.io/wg-easy/wg-easy:14 wgpw 'SuClaveDelPanel2026*'
```

Responde algo como:

```
PASSWORD_HASH='$2a$12$Xyz...'
```

Copie lo que está **entre las comillas simples**, con los signos `$` incluidos.

## Paso 5. Configurar el `.env`

Abra el `.env` con el Bloc de notas y agregue al final:

```bash
# --- HCE privada por VPN (docker-compose.vpn.yml) ---
VPN_HOST=suips-hce.duckdns.org
VPN_PANEL_HASH='$2a$12$Xyz...el hash completo...'
DUCKDNS_SUBDOMINIO=suips-hce
DUCKDNS_TOKEN=el-token-de-duckdns

URL_PUBLICA=http://172.30.77.10
CORS_ORIGINS=http://172.30.77.10,http://localhost:8080
```

- `VPN_PANEL_HASH` va **entre comillas simples** (`'...'`). Sin ellas, Docker confunde los `$` y la clave del panel no funcionará.
- Si no usa DuckDNS, ponga su IP pública en `VPN_HOST` y borre las dos líneas `DUCKDNS_`.

## Paso 6. Arrancar XENTRA en modo privado

En PowerShell, en la carpeta del proyecto:

```powershell
git pull
docker compose down
docker compose -f docker-compose.yml -f docker-compose.vpn.yml --profile duckdns up -d --build
```

(Sin DuckDNS, quite `--profile duckdns`.)

- `docker compose down` **no borra datos**: solo apaga los contenedores para recrear la red interna con las direcciones nuevas. **Nunca** le agregue `-v`, porque eso sí borra la base de datos.
- Verifique:

```powershell
docker compose -f docker-compose.yml -f docker-compose.vpn.yml ps
```

Deben aparecer `vpn`, `frontend`, `backend`, `db`, `respaldo` (y `duckdns`) en *running*.

## Paso 7. Crear un perfil por persona

1. **En el propio servidor**, abra `http://localhost:51821` (el panel no se puede abrir desde otro equipo, por seguridad).
2. Ingrese con la clave del paso 4.
3. Pulse **+ New** y escriba el nombre de la **persona y el equipo**, ej. `dra-gomez-celular` o `dr-ruiz-portatil`. **Un perfil por equipo**, nunca compartido.
4. Aparece el perfil con dos opciones:
   - **Código QR** (icono de cuadrícula): para celulares.
   - **Descargar** (flecha): archivo `.conf` para computadores.

Registre cada perfil entregado en el formato F-01 del protocolo de gestión de usuarios.

## Paso 8. Conectar a un usuario

1. Instale la app oficial **WireGuard** (gratuita): Play Store, App Store, o `wireguard.com/install` para Windows y Mac.
2. **Celular:** **+** → **Escanear código QR** → escanee el QR del panel → nombre `XENTRA` → active el interruptor.
   **Computador:** **Importar túnel desde archivo** → elija el `.conf` → **Activar**.
3. Con la VPN activa, abra en el navegador:

```
http://172.30.77.10
```

4. Ingrese con su usuario y clave de XENTRA (y el código MFA si su rol lo exige).

Entregue el QR o el archivo `.conf` **en persona o por un canal seguro**: quien tenga ese perfil puede entrar a la red privada. Después, aún necesita usuario, clave y MFA de XENTRA.

> El tráfico dentro de la VPN viaja cifrado por WireGuard, aunque la dirección empiece por `http://`.
>
> **Túnel dividido:** por la VPN solo viaja el tráfico hacia XENTRA. El resto de la navegación del usuario sale normal por su internet, y la VPN no le da acceso a ningún otro equipo de la red de la IPS.

## Paso 9. Si tiene CG-NAT (sin IP pública)

WireGuard directo no funciona. Alternativas que también son privadas:

| Opción | Cómo | Notas |
|---|---|---|
| **Pedir IP pública al proveedor** | Llamada al proveedor de internet | La más simple; luego siga esta guía |
| **NetBird** | Instale NetBird en el servidor y en cada equipo; entran a `http://IP-NETBIRD-DEL-SERVIDOR:8080` | Código abierto. Su plan en la nube es gratuito para equipos pequeños, o se puede alojar uno mismo |
| **Tailscale** | Igual que NetBird (guía 12, nivel 2) | No es de código abierto, pero el plan gratuito es suficiente para un piloto |
| **Headscale** en una VM gratis de Oracle Cloud | Servidor de control propio + apps de Tailscale | Totalmente bajo su control, pero requiere más conocimientos |

En las tres últimas, el tráfico va cifrado de punta a punta. Solo pasan por terceros las "presentaciones" entre equipos, nunca el contenido de la historia clínica.

---

## Operación

| Tarea | Cómo |
|---|---|
| **Dar de baja** a alguien (retiro, celular perdido) | Panel `http://localhost:51821` → **eliminar** su perfil **el mismo día**. Además, desactive su usuario en XENTRA (protocolo P-01) |
| Ver quién está conectado | El panel muestra cada perfil, su última conexión y el tráfico |
| Suspender temporalmente | Interruptor del perfil en el panel |
| Ver estado | `docker compose -f docker-compose.yml -f docker-compose.vpn.yml ps` |
| Actualizar XENTRA | `git pull` y `docker compose -f docker-compose.yml -f docker-compose.vpn.yml --profile duckdns up -d --build` |
| Respaldo de los perfiles | Los perfiles viven en el volumen `datos_vpn`. Si se pierde, se crean de nuevo y se reparten otra vez |

**Solo VPN, también en la sede.** Por defecto el puerto 8080 queda abierto en la red local como contingencia. Si quiere que **todos**, incluso dentro de la sede, entren solo por VPN, abra `docker-compose.vpn.yml` y cambie, en `frontend`, las líneas de `ports` por `ports: !reset []`. Luego ejecute de nuevo el `up`.

**Auditoría.** Con la VPN, el ledger de XENTRA registra como IP la de la puerta de la VPN (`172.30.77.2`). La trazabilidad se mantiene porque cada acceso queda con el **usuario** de XENTRA, y el panel de la VPN registra qué perfil (persona y equipo) estaba conectado.

## Comprobar que es privada

1. Con la VPN **apagada** y el celular en **datos móviles**, abra `http://172.30.77.10` → **no debe cargar**.
2. Abra `http://SU-IP-PUBLICA:8080` → **no debe cargar**, porque no reenvió ese puerto.
3. Active la VPN → `http://172.30.77.10` **carga**.

Si se cumplen los tres puntos, su HCE es privada.

## Solución de problemas

| Síntoma | Causa probable | Solución |
|---|---|---|
| La app WireGuard conecta pero no carga la página | Puerto UDP 51820 no reenviado, o firewall de Windows | Revise los pasos 3 y el firewall; confirme que `VPN_HOST` es correcto |
| El contenedor `vpn` se reinicia una y otra vez | El kernel de WSL no tiene WireGuard | PowerShell como administrador: `wsl --update`, reinicie el PC |
| `Pool overlaps with other one on this address space` | Otra red usa `172.30.77.0/24` | Cambie esa subred en `docker-compose.vpn.yml` (y las IPs `.2`, `.10`) por otra, ej. `172.31.88.0/24` |
| No puedo entrar al panel | Contraseña o hash mal copiado | Regenere el hash (paso 4) y póngalo **entre comillas simples** en el `.env` |
| Funcionaba y dejó de funcionar | Cambió la IP pública | Use DuckDNS (paso 2) |
