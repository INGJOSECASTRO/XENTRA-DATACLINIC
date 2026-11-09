# 7. Hoja de ruta: de MVP a "el mejor del mercado"

El MVP actual cubre el corazón del sistema (HC, firma inalterable, auditoría, IA CIE-10, RIPS). Estas son las
fases recomendadas, en orden de prioridad. Cada fase debería terminar con pruebas automáticas y una versión
desplegable.

## Fase 0 – Antes de atender pacientes reales (obligatorio)

- [ ] Cargar catálogos oficiales: **CIE-10 completo, CUPS, CUM, DIVIPOLA, EAPB y tablas de referencia RIPS** (SISPRO), con
      actualización periódica. Mostrarlos como listas desplegables en lugar de códigos escritos a mano.
- [ ] **Migraciones con Alembic** (hoy las tablas se crean al arrancar; en producción cada cambio de estructura debe
      ser una migración versionada).
- [ ] **Separar usuarios de base de datos**: un usuario *dueño* para migraciones y un usuario *de aplicación* sin
      permisos para `ALTER TABLE` ni para desactivar triggers.
- [ ] HTTPS con dominio propio, copias de seguridad automáticas cifradas y prueba de restauración.
- [ ] Política de tratamiento de datos, aviso de privacidad y formato de autorización (Ley 1581).
- [ ] Validación de RIPS en el ambiente de pruebas del MUV.
- [ ] Pentest externo.

## Fase 1 – Operación básica de una IPS (1–3 meses)

- [ ] **MFA** (segundo factor: app autenticadora) y cierre de sesión por inactividad; *refresh tokens*.
- [ ] **Agenda de citas** (por profesional, sede y especialidad; recordatorios por WhatsApp/SMS/correo).
- [ ] **Admisiones**: verificación de derechos (BDUA/ADRES), autorizaciones, copagos y cuotas moderadoras.
- [ ] **Facturación electrónica DIAN** (integración con proveedor tecnológico) + envío automático al **MUV** y
      almacenamiento del CUV.
- [ ] RIPS de urgencias, hospitalización, recién nacidos, medicamentos y otros servicios.
- [ ] **Impresión/PDF** de la HC, fórmula médica, incapacidades, órdenes y remisiones, con código QR que apunte
      a la verificación de integridad.
- [ ] Alerta de alergia al formular; plantillas de nota por especialidad.
- [ ] **Consentimientos informados** con firma del paciente en tableta.
- [ ] Anclaje diario del ledger (OpenTimestamps o estampado cronológico acreditado).

## Fase 2 – Hospital y diferenciación (3–6 meses)

- [ ] **Interoperabilidad (Ley 2015 de 2020 / Resolución 866 de 2021)**: API **HL7 FHIR R4** (Patient, Encounter,
      Condition, MedicationRequest, Procedure, Observation) siguiendo las guías de implementación que publique el
      Ministerio para la IHCE.
- [ ] **Urgencias** con triage (Resolución 5596 de 2015), **hospitalización** (censo de camas, evolución, órdenes
      médicas, kárdex y notas de enfermería, balance de líquidos), **epicrisis**.
- [ ] **Farmacia e inventarios** (dispensación, lotes, vencimientos, cadena de frío).
- [ ] **Laboratorio e imágenes** (órdenes, resultados, integración HL7 v2 / DICOM-PACS).
- [ ] **Firma digital** con certificado de entidad acreditada ONAC.
- [ ] IA: resumen de HC, pre-auditoría de cuentas para reducir glosas, interacciones medicamentosas.
- [ ] Reportes: SIVIGILA, indicadores de calidad (Resolución 256 de 2016), tableros gerenciales.

## Fase 3 – Escala y excelencia (6–12 meses)

- [ ] Multi-sede y multi-empresa (*multi-tenant*).
- [ ] **Portal del paciente** y app móvil (resultados, citas, fórmulas, descarga de su HC).
- [ ] **Telesalud** (videoconsulta integrada).
- [ ] Dictado por voz a nota clínica; IA predictiva validada clínicamente.
- [ ] Alta disponibilidad (réplicas de PostgreSQL, Kubernetes), observabilidad (OpenTelemetry, Grafana).
- [ ] Certificación ISO/IEC 27001.
- [ ] **CIE-11** con mapeo desde CIE-10 según la transición que defina el Ministerio.

## Herramientas de calidad recomendadas para el equipo

| Necesidad | Herramienta |
|---|---|
| Integración continua (pruebas en cada cambio) | GitHub Actions |
| Estilo y errores en Python | Ruff + mypy |
| Estilo en Vue/TS | ESLint + Prettier |
| Pruebas de interfaz | Playwright |
| Errores en producción | Sentry (autoalojado si hay datos sensibles) |
| Escaneo de vulnerabilidades | Dependabot, Trivy (imágenes Docker) |
