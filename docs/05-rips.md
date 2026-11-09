# 5. RIPS, factura electrónica y MUV (Resolución 2275 de 2023)

## 5.1 ¿Qué son?

Los **RIPS** reportan cada servicio prestado. Con la Resolución 2275 de 2023 son **JSON** y **soporte obligatorio
de la factura electrónica de venta (FEV)** en salud. El JSON se envía con la factura al **Mecanismo Único de
Validación (MUV)** del Ministerio de Salud, que devuelve un **Código Único de Validación (CUV)**.

## 5.2 Flujo en XENTRA (módulo Facturación)

```
Atenciones firmadas / hospitalizaciones egresadas
        │  seleccionar (mismo pagador)
        ▼
   Factura BORRADOR ──► Pre-auditoría automática (errores bloquean, advertencias informan)
        │  Emitir DIAN (proveedor tecnológico)
        ▼
   Factura EMITIDA: número consecutivo + CUFE + XML + RIPS JSON
        │  Validar MUV
        ▼
   VALIDADA (CUV)  o  RECHAZADA (se corrige y se reenvía)
```

- Un servicio no puede estar en dos facturas vigentes; al anular un borrador vuelve a quedar pendiente.
- Una factura **emitida no se anula**: se corrige con **nota crédito** ante la DIAN (`tipoNota` = NC en RIPS).
- Medicamentos: se facturan los efectivamente **dispensados** por farmacia (con lote), no solo los formulados.
- Hospitalización: estancia (días × valor día) + medicamentos dispensados por órdenes médicas.

## 5.3 Servicios RIPS generados

| Servicio | Origen en el sistema |
|---|---|
| `consultas` | Cada atención firmada |
| `procedimientos` | Procedimientos CUPS de la atención |
| `urgencias` | Atención tipo urgencias con fecha y condición de egreso |
| `hospitalizacion` | Hospitalización egresada (vía de ingreso, Dx de ingreso y egreso, condición, causa de muerte) |
| `medicamentos` | Dispensaciones de farmacia (CUM, cantidad, valor unitario) |
| `recienNacidos`, `otrosServicios` | ⏳ pendientes |

Código: `backend/app/services/rips.py` y `backend/app/services/facturacion.py`.

## 5.4 Pre-auditoría (reduce glosas)

Revisa antes de emitir: errores de estructura RIPS, ítems sin valor, CUPS inexistentes, valor distinto a la tarifa
del catálogo, paciente de otra EPS, falta de autorización, diagnóstico de síntoma marcado como confirmado,
incoherencia de capítulo Z con finalidad, posibles duplicidades del mismo día.

## 5.5 Integraciones (variables en `.env`)

| Variable | Valores |
|---|---|
| `DIAN_MODO` | `simulado` (pruebas, CUFE ficticio) · `real` (llama a `DIAN_PROVEEDOR_URL` con `DIAN_PROVEEDOR_TOKEN`) |
| `MUV_MODO` | `simulado` (CUV ficticio) · `real` (API FEV-RIPS en `MUV_URL` con `MUV_USUARIO`/`MUV_CLAVE`) |
| `FACTURA_PREFIJO` | Prefijo autorizado en su resolución de facturación DIAN |

**Antes de producción**: cada proveedor DIAN tiene su propia API; adapte `DianReal.emitir` en
`backend/app/services/integraciones.py`. Verifique los endpoints del MUV contra el manual técnico vigente de la API
FEV-RIPS del Ministerio y pruebe en su ambiente de pruebas.

## 5.6 Tablas de referencia

Los códigos (finalidad, causa, modalidad, grupo de servicio, servicio REPS, vía de ingreso, condición de egreso,
concepto de recaudo, tipo de usuario) se eligen de listas alimentadas por el catálogo. Los valores incluidos son una
**muestra**: cargue las tablas vigentes de SISPRO:

```bash
docker compose exec backend python -m app.cargar_catalogo finalidad /tmp/finalidad.csv --reemplazar
```
