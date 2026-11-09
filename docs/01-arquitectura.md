# 1. Arquitectura y decisiones técnicas

## 1.1 Mi recomendación sobre su elección (FastAPI + Vue + PostgreSQL)

Usted propuso **FastAPI + Vue.js + PostgreSQL**. Es una **excelente elección** y la mantuve. Esto es lo que
haría un equipo profesional, y lo que agregué o ajusté:

| Usted propuso | Decisión final | Comentario de "gurú" |
|---|---|---|
| FastAPI | ✅ FastAPI + SQLAlchemy 2 + Pydantic v2 | FastAPI es de lo mejor para APIs en Python. SQLAlchemy es el estándar para hablar con la BD. |
| Vue.js | ✅ Vue 3 + **TypeScript** + Vite + Pinia | TypeScript detecta errores antes de que lleguen al usuario. Pinia guarda el estado (sesión). |
| PostgREST | ❌ **No se usa** → PostgreSQL directo desde FastAPI | PostgREST expone la BD como API sin capa intermedia: las reglas clínicas (quién firma, qué no se puede editar, auditoría de accesos) quedarían dispersas en SQL. Con FastAPI todo queda en un solo lugar, probado. |
| — | **PostgreSQL 16 con triggers** | La propia BD impide modificar historias firmadas, aunque alguien entre directo con pgAdmin. |
| — | **Docker Compose + Nginx** | Instalación en un comando; igual en su PC y en el servidor. |
| "Blockchain" | **Ledger encadenado SHA-256 + HMAC** (y anclaje público opcional) | Ver [04-seguridad-blockchain.md](04-seguridad-blockchain.md): da la garantía útil de blockchain sin poner datos de salud en una red pública. |
| IA | **Motor local + Claude (opcional)** | Funciona sin internet; con API de Anthropic mejora la precisión. El texto se anonimiza antes de salir. |

### ¿Hay algo "mejor"?

Alternativas que se usan en el mercado y por qué **no** las elegí como base:

- **Java/Spring Boot o .NET**: muy usadas en hospitales grandes, pero más lentas de desarrollar y más difíciles para
  alguien que empieza. FastAPI tiene rendimiento suficiente para miles de usuarios concurrentes.
- **Node.js (NestJS)**: buena opción, pero el ecosistema de IA y ciencia de datos es más fuerte en Python.
- **Bases NoSQL (MongoDB)**: la HC necesita integridad referencial y transacciones; PostgreSQL es superior aquí.
- **Plataformas FHIR nativas (HAPI FHIR, Medplum)**: muy útiles para interoperabilidad. La recomendación es
  **agregar una capa FHIR** encima de este sistema (fase 2 de la [hoja de ruta](07-hoja-de-ruta.md)), no reemplazarlo.

## 1.2 Diagrama de componentes

```
            Navegador (médico, enfermería, facturación, auditor)
                                 │ HTTPS
                     ┌───────────▼────────────┐
                     │  Nginx (contenedor     │  sirve la app Vue y
                     │  "frontend", puerto    │  reenvía /api al backend
                     │  8080)                 │
                     └───────────┬────────────┘
                                 │ /api
                     ┌───────────▼────────────┐       ┌──────────────────────┐
                     │  FastAPI ("backend")   │──────▶│ API de Claude        │
                     │  - autenticación JWT   │ (opc.)│ (texto anonimizado)  │
                     │  - reglas clínicas     │       └──────────────────────┘
                     │  - ledger / RIPS / IA  │
                     └───────────┬────────────┘
                                 │ SQL
                     ┌───────────▼────────────┐
                     │  PostgreSQL ("db")     │  triggers de inmutabilidad
                     │  NO expuesto a internet│
                     └────────────────────────┘
```

## 1.3 Modelo de datos (tablas principales)

| Tabla | Qué guarda |
|---|---|
| `usuarios` | Personal con rol, registro profesional (ReTHUS), contraseña cifrada con Argon2id |
| `pacientes` | Datos de identificación y demográficos requeridos por RIPS + autorización Ley 1581 |
| `atenciones` | Cada folio de la HC (SOAP, signos vitales, datos RIPS, estado, hash de firma) |
| `diagnosticos` | Hasta 4 por atención (1 principal + 3 relacionados), CIE-10 formato colombiano |
| `procedimientos` | Procedimientos CUPS de la atención |
| `prescripciones` | Fórmula médica (medicamento, dosis, vía, frecuencia, duración, cantidad) |
| `notas_aclaratorias` | Correcciones posteriores a la firma (inmutables) |
| `ledger_bloques` | Cadena de auditoría (hash, hash anterior, firma HMAC, usuario, IP, acción) |
| `cie10` | Catálogo de diagnósticos con reglas de sexo y edad |
| `catalogos` | Tablas de referencia (CUPS, CUM, DIVIPOLA, EAPB, tablas RIPS) |
| `sedes` | Sedes de la institución (código de habilitación por sede) |
| `citas` | Agenda (presencial y telemedicina) |
| `triages` | Clasificación de urgencias |
| `camas`, `hospitalizaciones`, `evoluciones`, `ordenes_medicas`, `administraciones_medicamento`, `balance_liquidos` | Hospitalización completa |
| `productos`, `lotes`, `movimientos_inventario` | Farmacia e inventario |
| `ordenes_servicio` | Laboratorio e imágenes (orden y resultado) |
| `consentimientos` | Consentimientos informados con firma |
| `facturas`, `factura_items` | Facturación electrónica y RIPS |
| `anclajes_ledger` | Sellos de tiempo externos del ledger |

## 1.4 Flujo de una consulta

1. El médico inicia sesión → bloque `LOGIN` en el ledger.
2. Busca al paciente y abre su historia → bloques `CONSULTA_PACIENTE` y `CONSULTA_HC` (trazabilidad de accesos).
3. Crea la atención (borrador) → la puede editar cuantas veces quiera.
4. Pide sugerencias CIE-10 a la IA y elige los diagnósticos.
5. **Firma** → se calcula el SHA-256 del contenido clínico, se registra en el ledger (`ATENCION_FIRMADA`) y la fila
   queda bloqueada por PostgreSQL.
6. Facturación selecciona las atenciones firmadas y genera el **RIPS JSON** → bloque `RIPS_GENERADO`.
7. El auditor puede verificar en cualquier momento que nada fue alterado.

## 1.5 Seguridad por capas (defensa en profundidad)

1. **Red**: solo el puerto del frontend se publica; la BD queda en la red interna de Docker.
2. **Autenticación**: contraseñas Argon2id, política de complejidad, bloqueo por intentos fallidos, JWT de 30 min.
3. **Autorización**: cada endpoint declara qué roles pueden usarlo (`requiere_rol(...)`).
4. **Aplicación**: validación estricta de todos los datos de entrada con Pydantic.
5. **Base de datos**: triggers que impiden alterar la HC firmada y el ledger.
6. **Auditoría**: ledger encadenado + firma HMAC con llave fuera de la BD.
7. **Navegador**: cabeceras de seguridad, sesión en `sessionStorage` (se borra al cerrar el navegador), sin caché de datos clínicos.
