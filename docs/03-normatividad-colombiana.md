# 3. Normatividad colombiana: qué cumple el sistema y qué falta

> ⚖️ Esta tabla es una guía técnica, **no asesoría jurídica**. Las normas cambian: verifique siempre la
> versión vigente en el portal del Ministerio de Salud (minsalud.gov.co) y la Secretaría del Senado.
> Recomendación: valide el producto con un abogado especializado en salud antes de comercializarlo.

## 3.1 Historia clínica

| Norma | Qué exige (resumen) | Cómo lo cumple XENTRA | Estado |
|---|---|---|---|
| **Resolución 1995 de 1999** (manejo de la HC) | Integralidad, secuencialidad, racionalidad, disponibilidad, oportunidad. La HC es **inalterable**: no se borra ni se tachan datos; correcciones con nota fechada y firmada. Identificación del profesional. | Folios con consecutivo por paciente; firma que sella el folio; triggers en PostgreSQL; notas aclaratorias con autor, fecha y hash; nombre y registro del profesional en cada folio. | ✅ Base implementada |
| **Ley 23 de 1981** (ética médica) | La HC es reservada; solo la conocen terceros con autorización del paciente o en casos legales. | Control de acceso por rol; registro de **quién** consultó cada historia. | ✅ / 🔶 falta módulo de autorizaciones de acceso de terceros |
| **Resolución 839 de 2017** | Tiempos de conservación de la HC (mínimo 15 años desde la última atención) y procedimiento de disposición final. | Nada se borra (inmutabilidad). | 🔶 Falta política de archivo y respaldo de largo plazo |
| **Ley 2015 de 2020** (HC Electrónica Interoperable) | Toda IPS debe intercambiar la HC electrónica de forma interoperable. | Modelo de datos alineado con elementos de datos clínicos. | 🔶 **Prioridad fase 2**: API FHIR / IHCE |
| **Resolución 866 de 2021** | Conjunto de elementos de datos clínicos relevantes para la interoperabilidad. | Datos de identificación, demográficos, diagnósticos, medicamentos, procedimientos. | 🔶 Revisar uno a uno contra la norma y su anexo técnico |
| **Ley 527 de 1999 y Decreto 2364 de 2012** | Validez de mensajes de datos y firma electrónica. | Firma electrónica con usuario + contraseña + hash + registro en ledger. | 🔶 Para mayor fuerza probatoria: firma **digital** con certificado de entidad acreditada (ONAC) |

## 3.2 Datos personales

| Norma | Exige | XENTRA | Estado |
|---|---|---|---|
| **Ley 1581 de 2012** y **Decreto 1377 de 2013** (incorporado en el Decreto 1074 de 2015) | Los datos de salud son **sensibles**: autorización previa, expresa e informada; finalidad; seguridad; derechos del titular. | Casilla de autorización con fecha; anonimización antes de enviar texto a la IA externa; IA local por defecto; trazabilidad de accesos. | ✅ / 🔶 falta: política de tratamiento publicada, gestión de consultas/reclamos del titular, Registro Nacional de Bases de Datos (SIC) cuando aplique |

## 3.3 Facturación y reportes

| Norma | Exige | XENTRA | Estado |
|---|---|---|---|
| **Resolución 2275 de 2023** (RIPS) | RIPS en JSON como **soporte de la factura electrónica de venta**; validación en el **MUV** del Ministerio, que entrega el CUV. | Generación y validación estructural del JSON para consultas y procedimientos. | ✅ Consultas y procedimientos · 🔶 Faltan urgencias, hospitalización, recién nacidos, medicamentos, otros servicios; integración con API del MUV |
| **Resoluciones de la DIAN sobre factura electrónica** (Anexo técnico, sector salud) | Factura electrónica con campos del sector salud. | — | 🔶 Integrar con un proveedor tecnológico autorizado por la DIAN |
| **Resolución 3100 de 2019** (habilitación) | Estándar de historia clínica y registros; códigos de servicios habilitados. | Código de servicio (REPS) por atención. | 🔶 Validar contra el REPS de la IPS |

## 3.4 Codificación clínica

| Elemento | Situación |
|---|---|
| **CIE-10** | Formato colombiano de 4 caracteres (`I10X`, `E119`). El sistema valida formato, existencia en catálogo y pertinencia por sexo/edad. |
| **CIE-11** | El Ministerio ha venido adelantando la transición a la CIE-11. **Verifique la resolución y el plazo vigentes.** El diseño permite agregar una tabla CIE-11 y un mapeo CIE-10 ↔ CIE-11 sin rehacer el sistema. |
| **CUPS** | Clasificación Única de Procedimientos en Salud, se actualiza anualmente por resolución. Cargar la tabla oficial (fase 1). |
| **CUM / IUM** | Códigos de medicamentos del INVIMA. Campo `cum` ya existe en la fórmula; falta cargar el catálogo. |
| **Tablas de referencia RIPS** | Finalidad, causa externa, modalidad, grupo de servicio, tipo de usuario, etc. Se publican en **SISPRO** y cambian. Los valores por defecto del sistema deben validarse. |

## 3.5 Otras normas a considerar según los módulos que agregue

- **Prescripción de tecnologías no financiadas con UPC**: MIPRES (campo `idMIPRES` en RIPS ya contemplado).
- **Notificación obligatoria** de eventos de interés en salud pública: SIVIGILA (INS).
- **Resolución 3280 de 2018**: Rutas Integrales de Atención (promoción y mantenimiento de la salud, materno-perinatal).
- **Resolución 4505 de 2012** y sus modificaciones: reporte de actividades de protección específica y detección temprana (verificar vigencia, ha sido modificada y reemplazada en parte).
- **Consentimiento informado**: Ley 23 de 1981 y jurisprudencia; módulo de consentimientos con firma del paciente (fase 2).
- **Telesalud**: Ley 1419 de 2010 y Resolución 2654 de 2019.

Leyenda: ✅ implementado · 🔶 parcial o pendiente.
