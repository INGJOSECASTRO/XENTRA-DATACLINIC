# 4. Seguridad y "blockchain"

## 4.1 Lo que usted pidió y lo que realmente conviene

Cuando se dice "historia clínica con blockchain" normalmente se busca una cosa: **que nadie pueda alterar la
historia sin que se note**. Eso es lo que se implementó.

Lo que **NO** se debe hacer (y muchos proveedores lo venden como "blockchain"):

- ❌ **Guardar datos de pacientes en una blockchain pública** (Ethereum, Bitcoin, etc.): son públicas y
  permanentes. Violaría la Ley 1581 de 2012 (datos sensibles) y el secreto profesional.
- ❌ **Cifrar los datos y subirlos a una cadena pública**: el cifrado de hoy puede romperse en 15 años
  (y la HC se guarda mínimo 15 años).

## 4.2 Cómo funciona el ledger de XENTRA

Cada acción importante crea un **bloque**:

```
Bloque 41                              Bloque 42
┌──────────────────────────────┐       ┌──────────────────────────────┐
│ fecha, usuario, IP, acción   │       │ fecha, usuario, IP, acción   │
│ hash_datos = SHA256(datos)   │       │ hash_datos = SHA256(datos)   │
│ hash_anterior = <hash del 40>│  ┌───▶│ hash_anterior = <hash del 41>│
│ hash = SHA256(todo lo de     │──┘    │ hash = SHA256(...)           │
│        arriba)               │       │ firma = HMAC(llave, hash)    │
│ firma = HMAC(llave, hash)    │       └──────────────────────────────┘
└──────────────────────────────┘
```

- **SHA-256** es una "huella digital": si cambia una sola letra, la huella cambia por completo.
- **Encadenamiento**: cada bloque guarda la huella del anterior. Alterar el bloque 10 rompe los bloques 11, 12, 13…
- **Firma HMAC**: un atacante con acceso a la base de datos podría intentar recalcular toda la cadena. No puede,
  porque cada bloque está firmado con `LEDGER_HMAC_KEY`, que **no está en la base de datos**.
- **Solo huellas**: el ledger guarda el hash de los datos, no los datos clínicos.

### Qué se registra

`LOGIN`, `LOGIN_FALLIDO`, `PACIENTE_CREADO`, `PACIENTE_ACTUALIZADO`, `CONSULTA_PACIENTE`, `CONSULTA_HC`,
`CONSULTA_ATENCION`, `ATENCION_CREADA`, `ATENCION_EDITADA`, `ATENCION_FIRMADA`, `NOTA_ACLARATORIA`,
`BORRADOR_ELIMINADO`, `RIPS_GENERADO`, `USUARIO_CREADO`, `USUARIO_ACTIVADO/DESACTIVADO`.

### Firma de un folio

Al firmar, se calcula el SHA-256 de todo el contenido clínico (texto, signos, diagnósticos, procedimientos,
fórmula). Ese hash queda en el folio **y** en el bloque `ATENCION_FIRMADA`. El botón **Verificar integridad**
recalcula el hash y lo compara con ambos.

### Tres barreras contra la manipulación

| Barrera | Qué detiene |
|---|---|
| API (FastAPI) | Un usuario normal no puede editar un folio firmado (error 409). |
| PostgreSQL (triggers) | Alguien que entra directo a la BD no puede hacer `UPDATE`/`DELETE` sobre folios firmados ni sobre el ledger. |
| Ledger + HMAC | Si un superusuario desactiva los triggers y altera datos, la verificación lo **detecta** y dice en qué bloque. |

## 4.3 Anclaje público (implementado)

Para tener una prueba **externa** de que el ledger no se reescribió (útil en litigios):

1. Una vez al día, tome el hash del último bloque (la "raíz" del día).
2. Publique **solo ese hash** (64 caracteres, no revela nada del paciente) en:
   - **OpenTimestamps** (gratuito, ancla en Bitcoin), o
   - una blockchain pública de bajo costo (Polygon, etc.), o
   - un servicio de **estampado cronológico** de una entidad de certificación acreditada por ONAC (validez legal en Colombia).
3. Guarde el comprobante. Así, ni siquiera el dueño del servidor puede reescribir la historia sin que se note.

En XENTRA: `ANCLAJE_MODO=opentimestamps` en `.env` y programe `python -m app.anclar` una vez al día (o use el botón
**Anclar ahora** en Auditoría). El sistema guarda cada comprobante y verifica que el hash anclado siga coincidiendo
con el bloque del ledger.

## 4.4 Otras capas implementadas

| Capa | Detalle |
|---|---|
| **MFA (TOTP)** | Segundo factor con app autenticadora; el token intermedio no sirve para usar la API |
| **Sesión** | JWT de 30 min renovado mientras hay actividad; cierre automático tras 15 min de inactividad |
| **Usuario de BD sin privilegios** | La API corre como `xentra_app`: no es dueño de las tablas, no puede desactivar triggers, y no tiene permiso de `UPDATE/DELETE` sobre el ledger ni sobre los registros de solo inserción. Las migraciones usan el dueño |
| **Registros sellados** | Folios firmados, notas aclaratorias, evoluciones, kárdex, consentimientos, balance de líquidos, movimientos de inventario, epicrisis y resultados validados (triggers) |
| **Verificación pública** | Cada PDF lleva un QR hacia `/verificar/...`, que confirma autenticidad sin revelar datos |
| **Portal del paciente** | El titular ve quién consultó su historia (transparencia) |

Si en el futuro varias IPS quieren compartir un ledger, se puede evaluar una blockchain **permisionada**
(Hyperledger Fabric), pero para una sola institución añade complejidad sin beneficio real.

## 4.5 Lista de verificación de seguridad para producción

- [ ] HTTPS obligatorio, HSTS (incluido con `docker-compose.prod.yml`).
- [ ] Todas las claves del `.env` cambiadas y guardadas en un gestor de secretos.
- [ ] `LEDGER_HMAC_KEY` respaldada fuera del servidor.
- [x] BD sin puerto público; API con usuario sin privilegios (incluido).
- [ ] Cifrado de disco en el servidor y copias de seguridad cifradas fuera del servidor.
- [ ] MFA obligatorio para administradores, médicos y facturación (actívelo en "Mi cuenta").
- [ ] Anclaje diario del ledger programado.
- [ ] Prueba de penetración (pentest) antes de salir a producción y una vez al año.
- [ ] Monitoreo de registros y alertas (intentos fallidos masivos, accesos fuera de horario).
- [ ] Actualización periódica de dependencias (`pip list --outdated`, `npm outdated`).
- [ ] Plan de respuesta a incidentes y de continuidad del negocio.
- [ ] Referencia: OWASP ASVS, ISO/IEC 27001 y 27799 (seguridad de información en salud).
