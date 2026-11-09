# 8. Guía para desarrolladores

## 8.1 Cómo está organizado el backend

```
backend/app/
├── main.py              Crea la app, registra rutas, al arrancar: tablas + triggers + datos iniciales
├── models.py            Tablas (SQLAlchemy)
├── schemas.py           Qué datos entran y salen de la API (Pydantic). Aquí van las validaciones.
├── seed.py              Admin, catálogo CIE-10 de muestra y datos demo
├── cargar_cie10.py      Script para cargar el catálogo oficial
├── core/
│   ├── config.py        Lee el .env
│   ├── database.py      Conexión a PostgreSQL
│   ├── security.py      Argon2id y JWT
│   ├── deps.py          usuario_actual, requiere_rol(...) y grupos de roles
│   └── inmutabilidad.py Triggers SQL de PostgreSQL
├── api/                 Un archivo por módulo (rutas HTTP)
└── services/            Lógica de negocio sin HTTP (fácil de probar)
    ├── ledger.py        Cadena de bloques de auditoría
    ├── historia.py      Hash/firma del folio
    ├── rips.py          Generación del JSON RIPS
    ├── cie10.py         Catálogo, búsqueda y motor local de sugerencias
    ├── ia.py            Proveedor Claude + alertas clínicas
    └── texto.py         Normalización y anonimización
```

**Regla de oro**: las rutas (`api/`) solo reciben la petición, verifican permisos y llaman a `services/`.
La lógica vive en `services/` para poder probarla.

## 8.2 Receta: agregar un módulo nuevo (ej. "Citas")

1. **Modelo** en `models.py`: clase `Cita(Base)` con sus columnas.
2. **Esquemas** en `schemas.py`: `CitaCrear` (entrada) y `CitaOut` (salida).
3. **Rutas** en `api/citas.py` con `router = APIRouter(prefix="/api/citas", tags=["Citas"])`. Proteja cada
   ruta con `Depends(requiere_rol(...))` y registre en el ledger las acciones importantes con `registrar_evento(...)`.
4. **Registrar** el router en `main.py` (tupla de módulos).
5. **Prueba** en `tests/test_citas.py`.
6. **Frontend**: tipo en `src/api/tipos.ts`, vista en `src/views/CitasView.vue`, ruta en `src/router/index.ts`
   (con `meta.roles`) y enlace en el menú de `App.vue`.
7. Con Alembic (fase 0): `alembic revision --autogenerate -m "citas"` y `alembic upgrade head`.

## 8.3 Pruebas

```bash
cd backend
pytest                    # SQLite temporal, rápido
TEST_DATABASE_URL=postgresql+psycopg://usuario:clave@localhost:5432/xentra_test pytest   # PostgreSQL real
```

Qué cubren (20 pruebas):
- Formato CIE-10 colombiano, normalización y anonimización.
- Alertas de signos vitales.
- Motor de IA local (gripa → J00X, presión alta → I10X, ardor al orinar → N390, dolor lumbar → M545) y filtro por sexo.
- Proveedor Claude simulado: descarta códigos inventados y no pertinentes; si falla usa el motor local.
- Control de acceso por roles, bloqueo por intentos fallidos, contraseñas débiles.
- Flujo completo: paciente → atención → firma → inmutabilidad → nota aclaratoria → RIPS → ledger.
- Manipulación directa en la BD: en PostgreSQL los triggers la impiden; en SQLite la verificación la detecta.

## 8.4 Convenciones

- Código y mensajes en **español** (el dominio es colombiano); nombres sin tildes en el código.
- Nunca registre datos clínicos en los *logs* del servidor.
- Nunca suba `.env`, respaldos ni datos reales al repositorio.
- Cada cambio: rama nueva → *pull request* → revisión → pruebas en verde → *merge*.

## 8.5 Endpoints principales

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| POST | `/api/auth/login` | público | Inicio de sesión (form `username`, `password`) |
| GET/POST | `/api/auth/usuarios` | admin | Listar / crear usuarios |
| GET/POST | `/api/pacientes` | clínicos, admisiones | Buscar / crear pacientes |
| GET | `/api/pacientes/{id}/historia` | clínicos, auditor | Folios del paciente |
| POST | `/api/atenciones` | médico, enfermería | Crear borrador |
| PUT | `/api/atenciones/{id}` | autor | Editar borrador |
| POST | `/api/atenciones/{id}/firmar` | autor | Firmar y sellar |
| POST | `/api/atenciones/{id}/notas` | clínicos | Nota aclaratoria |
| GET | `/api/atenciones/{id}/verificar` | clínicos, auditor | Verificar integridad |
| GET | `/api/cie10?q=` | autenticado | Buscar CIE-10 |
| POST | `/api/cie10/sugerir` | clínicos | Sugerencias IA |
| POST | `/api/rips/generar` · `/descargar` | facturación | RIPS JSON |
| GET | `/api/auditoria/ledger` · `/verificar-cadena` | auditor, admin | Ledger |

La documentación interactiva completa está en `/docs` (Swagger) cuando el backend está corriendo.
