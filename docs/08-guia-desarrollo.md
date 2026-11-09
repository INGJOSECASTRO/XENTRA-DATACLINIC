# 8. Guía para desarrolladores

## 8.1 Cómo está organizado el backend

```
backend/app/
├── main.py              Crea la app y registra las rutas; en desarrollo crea tablas y triggers
├── models.py            Tablas núcleo: usuarios, pacientes, atenciones, diagnósticos, ledger, CIE-10
├── models_ext.py        Tablas hospitalarias: sedes, catálogos, citas, facturas, triage, camas, farmacia…
├── schemas.py / schemas_ext.py   Validación de entrada/salida (Pydantic)
├── seed.py              Admin, catálogos de muestra y datos demo
├── cargar_cie10.py / cargar_catalogo.py / anclar.py   Scripts de línea de comandos
├── core/                config, database, security (Argon2/JWT), deps (roles), inmutabilidad (triggers)
├── api/                 Rutas: auth, pacientes, atenciones, cie10, agenda, hospital, farmacia, laboratorio,
│                        facturacion, rips, fhir, portal, reportes, auditoria, administracion, publico
└── services/            Lógica sin HTTP: ledger, historia, rips, facturacion, integraciones (DIAN/MUV),
                         cie10, ia, resumen, seguridad_clinica, hospital, pdf, fhir, mfa, anclaje, catalogos
backend/alembic/         Migraciones (versions/0001_esquema_inicial.py incluye triggers y permisos)
```

**Regla de oro**: las rutas (`api/`) reciben la petición, verifican permisos y llaman a `services/`.

## 8.2 Migraciones de base de datos (Alembic)

- En desarrollo y pruebas (`AUTO_CREAR_TABLAS=true`) las tablas se crean solas al arrancar.
- En Docker/producción el servicio `migrate` ejecuta `alembic upgrade head` con el usuario dueño.
- Después de cambiar un modelo:
  ```bash
  cd backend
  alembic revision --autogenerate -m "agrega campo X"   # revise el archivo generado
  alembic upgrade head
  alembic check                                          # CI falla si modelos y migraciones no coinciden
  ```
- Si agrega una tabla que debe ser inalterable, añada su trigger en `core/inmutabilidad.py` **y** en la migración.

## 8.3 Receta: agregar un módulo nuevo

1. Modelo en `models_ext.py`; esquemas en `schemas_ext.py`.
2. Rutas en `api/mi_modulo.py`, protegidas con `Depends(requiere_rol(...))`; registre acciones con `registrar_evento(...)`.
3. Registrar el router en `main.py`.
4. Migración Alembic (8.2) y prueba en `tests/`.
5. Frontend: vista en `src/views/`, ruta con `meta.roles` en `src/router/index.ts` y enlace en el menú de `App.vue`.

## 8.4 Pruebas

```bash
cd backend
pytest                                                    # SQLite temporal
TEST_DATABASE_URL=postgresql+psycopg://usuario:clave@localhost:5432/xentra_test pytest   # PostgreSQL + triggers
```

43 pruebas cubren: MFA (incluye vector RFC 6238), sesión, roles, catálogos, alertas de alergia/interacción,
SIVIGILA, PDF y verificación pública, agenda (cruces, telemedicina, transiciones), facturación (pre-auditoría,
DIAN y MUV simulados, no duplicar), RIPS de urgencias/hospitalización/medicamentos, triage, hospitalización completa,
farmacia FEFO, laboratorio, consentimientos, FHIR, portal del paciente (incluye que no vea datos ajenos),
indicadores, anclaje, IA local y Claude simulado, y manipulación directa de la BD.

## 8.5 Convenciones

- Código y mensajes en español; nombres sin tildes en el código.
- Fechas en UTC en la BD; se convierten a hora de Colombia al mostrar o en RIPS.
- Nunca registre datos clínicos en los logs; nunca suba `.env`, respaldos ni datos reales.
- Cada cambio: rama → pull request → CI en verde → revisión → merge.

## 8.6 Endpoints principales

| Área | Rutas |
|---|---|
| Autenticación | `POST /api/auth/login`, `/mfa/verificar`, `/mfa/configurar`, `/mfa/activar`, `/renovar`, `/cambiar-clave`, `/usuarios` |
| Pacientes e HC | `/api/pacientes`, `/api/pacientes/{id}/historia`, `/api/atenciones` (+ `/firmar`, `/notas`, `/verificar`, `/pdf`) |
| IA y catálogos | `/api/cie10`, `/api/cie10/sugerir`, `/api/catalogos/{tipo}`, `/api/clinica/plantillas`, `/api/clinica/revisar-prescripcion`, `/api/pacientes/{id}/resumen-ia` |
| Agenda | `/api/citas`, `/api/citas/disponibilidad`, `/{id}/estado`, `/{id}/reprogramar`, `/api/citas/recordatorios` |
| Urgencias | `/api/urgencias/triage`, `/api/urgencias/triage/sugerir`, `/api/urgencias/cola`, `/api/urgencias/triage/{id}/{atender|finalizar}` |
| Hospitalización | `/api/camas`, `/api/hospitalizaciones` (+ `/evoluciones`, `/ordenes`, `/balance`, `/trasladar`, `/egreso`, `/epicrisis.pdf`), `/api/ordenes-medicas/{id}/{administrar|suspender}` |
| Farmacia | `/api/farmacia/productos`, `/entradas`, `/ajustes`, `/alertas`, `/pendientes`, `/dispensar`, `/kardex/{id}` |
| Laboratorio / consentimientos | `/api/ordenes-servicio` (+ `/toma`, `/resultado`, `/validar`), `/api/consentimientos` |
| Facturación | `/api/facturas`, `/pendientes`, `/{id}/auditar`, `/{id}/emitir`, `/{id}/enviar-muv`, `/{id}/anular`, `/{id}/rips` |
| FHIR R4 | `/fhir/metadata`, `/fhir/Patient?identifier=CC|123`, `/fhir/Patient/{id}/$everything`, `/fhir/{Recurso}?patient={id}` |
| Portal | `/api/portal/resumen`, `/atenciones`, `/citas`, `/resultados`, `/accesos`, `/exportar` |
| Reportes / auditoría | `/api/reportes/indicadores`, `/api/reportes/sivigila`, `/api/auditoria/ledger`, `/verificar-cadena`, `/anclar`, `/anclajes` |
| Público | `/api/publico/verificar/{tipo}/{id}?h=hash` |

Documentación interactiva completa: `/docs` (Swagger) con el backend en marcha.
