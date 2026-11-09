# 7. Hoja de ruta: estado actual y lo que falta

Leyenda: ✅ implementado y probado · 🔶 parcial / punto de integración listo · ⏳ pendiente · 📋 no es código
(trámite, contrato, certificación o decisión de la institución).

## Fase 0 – Antes de atender pacientes reales

| Tarea | Estado |
|---|---|
| Migraciones versionadas (Alembic) con triggers incluidos y verificación en CI (`alembic check`) | ✅ |
| Usuario de BD de aplicación sin privilegios (no altera tablas, no desactiva triggers, no borra auditoría) | ✅ |
| HTTPS automático (Caddy + Let's Encrypt) y cabeceras HSTS | ✅ `docker-compose.prod.yml` |
| Respaldos diarios automáticos con rotación | ✅ servicio `respaldo` · 📋 copiarlos fuera del servidor y probar restauración mensual |
| Catálogos de referencia (CUPS, CUM, DIVIPOLA, EAPB, tablas RIPS) con cargador y listas desplegables | ✅ muestra · 📋 **cargar las tablas oficiales vigentes de SISPRO** (`python -m app.cargar_catalogo`) |
| Catálogo CIE-10 oficial completo | 📋 cargar (`python -m app.cargar_cie10`) |
| Política de tratamiento de datos, aviso de privacidad, registro de bases de datos ante la SIC si aplica | 📋 asesor jurídico |
| Pruebas en el ambiente del MUV y con el proveedor DIAN | 📋 credenciales de la IPS |
| Prueba de penetración externa | 📋 contratar |

## Fase 1 – Operación básica de una IPS

| Tarea | Estado |
|---|---|
| MFA (TOTP), sesión deslizante y cierre por inactividad | ✅ |
| Agenda: disponibilidad, cruces, estados, reprogramación, recordatorios | ✅ · 🔶 conectar proveedor WhatsApp/SMS en `integraciones.notificar` |
| Admisiones: autorizaciones y copagos/cuotas moderadoras | ✅ campos en cita/atención · ⏳ verificación de derechos en línea (BDUA/ADRES no ofrece API pública abierta: requiere convenio) |
| Factura electrónica | 🔶 flujo completo + adaptador; 📋 contratar proveedor tecnológico DIAN y ajustar `DianReal` a su API |
| Envío automático al MUV y almacenamiento del CUV | 🔶 adaptador `MuvReal` según la API FEV-RIPS publicada · 📋 verificar endpoints con el manual técnico vigente |
| RIPS de consultas, procedimientos, urgencias, hospitalización y medicamentos | ✅ · ⏳ `recienNacidos` y `otrosServicios` |
| PDF de HC, fórmula, epicrisis y consentimientos con QR y verificación pública | ✅ · ⏳ incapacidades, órdenes y remisiones en PDF |
| Alertas de alergia (con reactividad cruzada) e interacciones al formular | ✅ tabla de apoyo · 📋 licenciar base farmacológica completa |
| Plantillas por tipo de consulta | ✅ 5 plantillas · ⏳ editor de plantillas por especialidad |
| Consentimientos informados con firma manuscrita | ✅ |
| Anclaje del ledger (OpenTimestamps) | ✅ `ANCLAJE_MODO=opentimestamps` + `python -m app.anclar` diario |

## Fase 2 – Hospital y diferenciación

| Tarea | Estado |
|---|---|
| API HL7 FHIR R4 de lectura + `$everything` | ✅ · ⏳ ajustar a los perfiles oficiales de la IHCE cuando el Ministerio los publique; escritura (recibir datos de otras IPS) |
| Urgencias con triage (Res. 5596/2015) y sala de espera priorizada | ✅ |
| Hospitalización: camas, evoluciones, órdenes, kárdex, balance de líquidos, traslados, epicrisis | ✅ |
| Farmacia: lotes, vencimientos, FEFO, dispensación, alertas | ✅ · ⏳ medicamentos de control especial (libro oficial FNE), devoluciones |
| Laboratorio e imágenes: órdenes, resultados, validación | ✅ · ⏳ integración con equipos (HL7 v2/ASTM) y PACS/DICOM |
| Firma digital con certificado ONAC | 📋 adquirir certificado; hoy: firma electrónica + hash + ledger |
| IA: resumen clínico, pre-auditoría de cuentas, interacciones | ✅ |
| Reportes: SIVIGILA (detección y CSV), indicadores de calidad | ✅ · ⏳ envío directo al aplicativo del INS, reportes de la Res. 256 completos |

## Fase 3 – Escala y excelencia

| Tarea | Estado |
|---|---|
| Multi-sede | ✅ sedes en usuarios, citas, camas y atenciones · ⏳ multi-empresa (*multi-tenant*) |
| Portal del paciente (historia, citas, resultados, accesos, descarga FHIR) | ✅ web · ⏳ app móvil nativa |
| Telesalud | ✅ salas Jitsi por cita · 📋 servidor Jitsi propio para mayor privacidad |
| Dictado por voz | ✅ Web Speech API del navegador · ⏳ transcripción local (Whisper) para no depender del navegador |
| IA predictiva (riesgo cardiovascular, reingreso) | ⏳ requiere validación clínica antes de usarse |
| Alta disponibilidad (réplicas, Kubernetes) y observabilidad (OpenTelemetry/Grafana) | ⏳ |
| ISO/IEC 27001 | 📋 certificación |
| CIE-11 con mapeo desde CIE-10 | ⏳ según la transición que defina el Ministerio |

## Lo que nunca se resuelve solo con código

1. **Datos oficiales**: tablas SISPRO, CIE-10, CUPS anual, CUM, tarifas de contratos.
2. **Credenciales y contratos**: proveedor DIAN, usuario del MUV, certificado de firma digital, WhatsApp Business.
3. **Validación**: pruebas con facturas reales en ambientes de prueba, revisión clínica de plantillas y alertas.
4. **Cumplimiento**: políticas de datos, comité de historias clínicas, capacitación del personal, pentest, plan de continuidad.
