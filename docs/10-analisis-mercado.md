# 10. Análisis del mercado colombiano: deficiencias frecuentes y cómo las resuelve XENTRA

> Fecha de la revisión: noviembre de 2026. Fuentes públicas en la web (listadas al final).

## 10.1 Advertencia metodológica (importante)

Se buscaron comentarios, quejas y vulnerabilidades públicas de **Dinámica Gerencial (SYAC), Zeus Salud
(Zeus Tecnología / Siesa), Panacea (CNT Sistemas de Información), SISMA Salud y HeOn (Heon Health On Line)**.

- **No se encontraron quejas públicas verificables ni vulnerabilidades reportadas para ninguno de esos productos
  específicos.** Lo que existe en la web es, sobre todo, material comercial del propio fabricante, trabajos
  académicos y directorios.
- Por eso este documento **no atribuye fallas a ningún producto**. Describe los **problemas del sector** que sí
  están documentados (ataques informáticos a hospitales, falta de interoperabilidad, hallazgos de auditoría en
  historias clínicas, exigencias normativas nuevas) y cómo XENTRA los resuelve.
- Para comparar productos concretos, lo correcto es pedir a cada proveedor referencias de clientes, visitar IPS
  que lo usen y solicitar evidencia de cumplimiento (RDA, RIPS JSON, pruebas de seguridad, plan de continuidad).

## 10.2 Lo que dicen las fuentes sobre los productos revisados

| Producto | Lo que se encontró públicamente |
|---|---|
| **Dinámica Gerencial** (SYAC) | Sistema modular en línea que integra áreas administrativa, financiera y asistencial; su folleto 2025 indica que está en proceso de migración tecnológica. Sin quejas públicas encontradas. |
| **Zeus Salud** | Producto de Zeus Tecnología, adquirida por Siesa; cubre admisiones, facturación, enfermería, farmacia, historia clínica y RIPS. Sin quejas públicas encontradas. |
| **Panacea** (CNT) | Plataforma 100 % web para clínicas y hospitales de segundo y tercer nivel; usada también en entornos académicos. Sin reportes de fallas encontrados. |
| **SISMA Salud** | Solo se encontró el sitio del fabricante (historia clínica, farmacia ligada a enfermería). Sin evaluaciones independientes. |
| **HeOn** | Información mayormente antigua (2013-2016); existe una tesis de auditoría de su módulo de urgencias. Sin información reciente verificable. |

## 10.3 Problemas documentados del sector y respuesta de XENTRA

| # | Problema documentado en el sector | Evidencia | Cómo lo resuelve XENTRA |
|---|---|---|---|
| 1 | **Ransomware y caída total de sistemas hospitalarios** (p. ej. Hospital Universitario de Caldas, 2024: servidores comprometidos, operación manual y recuperación desde respaldos; Audifarma 2023; Keralty) | Telesemana, Infosecurity Magazine, Intexus | Respaldos diarios automáticos con **prueba de restauración semanal**; usuario de BD sin privilegios; ledger con firma HMAC y anclaje externo que detecta alteraciones; MFA; **PDF de contingencia** para operar en papel; plan de continuidad documentado (docs/11) |
| 2 | **6 de cada 10 ciberataques en Colombia apuntan a hospitales y clínicas** | Colombia One / Biofile | Defensa en profundidad (docs/04), cabeceras de seguridad, HTTPS automático, bloqueo por intentos, cierre por inactividad, auditoría de cada acceso visible para el paciente |
| 3 | **Nueva obligación: Resumen Digital de Atención (RDA)**, Resolución 1888 de 2025 (HL7 FHIR, Bundle tipo *document* con un único Composition; RDA de paciente, consulta externa, urgencias y hospitalización). La Resolución 1799 de 2026 la modificó (incluye dispensación farmacéutica) | Consultor Salud, compilación Supersalud, guía IHCE (vulcano.ihcecol.gov.co), Manual de Operaciones IHCE | **RDA generado automáticamente** al firmar una atención o dar egreso, **validado** con las reglas del Manual de Operaciones y enviado con **cola de reintentos** (la atención nunca se bloquea si la IHCE no responde). Pendiente: ajustar perfiles y operaciones a la guía oficial vigente y agregar el RDA de dispensación |
| 4 | **Falta de interoperabilidad**: historias dispersas entre instituciones, información incompleta en urgencias y referencias | SciELO (caso Colombia), Radio Nacional, Medesk | API FHIR R4 con `$everything`, RDA, portal del paciente con descarga completa de su historia |
| 5 | **Hallazgos de auditoría en historias clínicas**: registros incompletos (Supersalud, Clínica Juan N. Corpas 2026), notas copiadas y pegadas entre consultas, ediciones posteriores no marcadas | Consultor Salud, Radio Nacional, Saludtools | Firma que **sella** el folio (triggers de BD), correcciones solo por nota aclaratoria con autor y hora, plantillas que guían el registro completo, campos obligatorios, trazabilidad de cada edición en el ledger |
| 6 | **Pacientes duplicados** por problemas de identificación | Saludtools | Documento único por tipo y número (restricción en BD), búsqueda previa al registro |
| 7 | **Nuevos silos**: notificación de incidentes, calidad y PQRS por fuera de la historia clínica | Salud by Díaz | **Módulos dinámicos** (eventos adversos, riesgo de caídas, PQRS, gestantes…) dentro del mismo sistema, ligados al paciente y al BI |
| 8 | **Rechazos y glosas** por RIPS o RDA mal construidos | Medesk, Saludtools (fuentes comerciales) | Pre-auditoría automática de cuentas, validación RIPS antes de emitir, validación estructural del RDA |
| 9 | **Soporte lento y difícil resolución** (queja típica del mercado; no documentada públicamente para un producto específico) | — | **Código de error** en cada respuesta para que soporte encuentre la causa en el log; **mesa de ayuda con ANS** por prioridad (4/8/24/72 h); **base de conocimiento** alimentada por cada ticket resuelto; estado del sistema con alertas; avisos de mantenimiento a todos los usuarios |
| 10 | **Reportes rígidos y dependencia del proveedor** para cada informe o módulo nuevo (queja típica del mercado) | — | **Constructor de reportes** (BI) sin programar, con reportes sugeridos según la lógica del negocio de la salud, exportación a Excel y reportes compartidos por rol; **constructor de módulos** sin programar |

## 10.4 Diferenciadores de XENTRA frente al mercado

1. **Inmutabilidad verificable**: hash + ledger + anclaje externo + verificación pública por QR.
2. **El paciente ve quién consultó su historia** (transparencia Ley 1581).
3. **IA con anonimización y anti-alucinación** (solo códigos del catálogo, pertinencia sexo/edad).
4. **RDA y FHIR nativos**, no como complemento.
5. **Continuidad**: PDF de contingencia, respaldos probados, colas con reintento para integraciones externas.
6. **Autonomía de la IPS**: reportes y módulos nuevos sin depender del proveedor.
7. **Código abierto a la institución**: sin cajas negras, con 49 pruebas automáticas y CI.

## 10.5 Fuentes

- Dinámica Gerencial: [syac.net.co](https://syac.net.co/dinamica-gerencial/), [Folleto 2025](https://syac.net.co/wp-content/uploads/2025/06/BROCHURE-DINAMICA-GERENCIAL-2025.pdf), [ACHC folleto](https://achc.org.co/wp-content/uploads/2022/07/BROCHURE-SYAC-DG-2021.pdf)
- Zeus Salud: [La República](https://www.larepublica.co/especiales/la-salud-despues-del-covid/zeus-salud-agiliza-la-administracion-de-las-entidades-de-salud-y-la-atencion-de-pacientes-3175274), [La República 2](https://www.larepublica.co/especiales/la-salud-despues-del-covid/zeus-salud-una-herramienta-tecnologica-que-apuesta-por-la-integralidad-de-servicios-3174657), [ConnectAmericas](https://connectamericas.com/company/zeus-tecnologia)
- Panacea: [Guía TIC](https://guiatic.com/co/251-software-para-la-administracion-y-gestion-de-instituciones-prestadoras-de-salud-ips-clinicas-y-hospitales/1165-panacea-aplicacion-web-para-la-gestion-de-clinicas-y-hospitales), [CNT](https://www.cnt.com.co/panacea-ads/), [Universidad Cooperativa de Colombia](https://repository.ucc.edu.co/items/b0141a90-94db-46d2-95f4-4e4a3ea2bef9)
- SISMA: [sismasalud.com](http://sismasalud.com/)
- HeOn: [Healthcare IT News](https://www.healthcareitnews.com/news/colombia-law-unique-ehr-come-effect-2013), [Redalyc](https://www.redalyc.org/pdf/206/20645903007.pdf)
- Ciberataques: [Telesemana – Hospital de Caldas](https://www.telesemana.com/blog/2024/03/20/transformacion-digital-y-ciberseguridad-un-ataque-de-ransomware-encendio-las-alarmas-en-un-hospital-de-colombia/), [Infosecurity Magazine](https://www.infosecurity-magazine.com/news/ransomware-target-colombias-health/), [Intexus](https://intexus.la/blog/ciberataques-sector-salud/), [Colombia One](https://colombiaone.com/2026/09/13/colombia-cyberattacks-target-hospitals/), [AREANI](https://areani.io/ciberseguridad-en-hospitales-colombianos-la-deuda-pendiente-que-pone-en-riesgo-millones-de-datos/)
- Resolución 1888 de 2025 / RDA: [Consultor Salud](https://consultorsalud.com/colombia-resumen-digital-de-atencion-en-salud/), [Compilación Supersalud](https://normograma.supersalud.gov.co/compilacion/docs/resolucion_minsaludps_1888_2025.htm), [Alcaldía de Bogotá](https://www.alcaldiabogota.gov.co/sisjur/normas/Norma1.jsp?i=190733&dt=S), [Guía FHIR RDA – IHCE](https://vulcano.ihcecol.gov.co/), [Manual de Operaciones IHCE](https://www.minsalud.gov.co/ihce/Manuales/Manual_de_operaciones_interoperabilidad_IHCE.pdf), [RDA dispensación – Res. 1799 de 2026](https://consultorsalud.com/rda-de-dispensacion-de-medicamentos-en-colombia/)
- Interoperabilidad y auditoría: [SciELO – HCE interoperable Colombia](http://www.scielo.org.pe/scielo.php?script=sci_arttext&pid=S2227-47312022000100026), [Radio Nacional](https://www.radionacional.co/actualidad/salud/medicos-en-colombia-pueden-acceder-historias-clinicas-en-toda-la-red-de-salud), [Saludtools – auditoría HC](https://www.saludtools.com/articulo/auditoria-historia-clinica-colombia), [Supersalud – Juan N. Corpas](https://consultorsalud.com/supersalud-medida-cautelar-clinica-juan-corpas/), [Salud by Díaz](https://saludbydiaz.com/2026/11/06/las-quejas-en-la-atencion-de-la-salud/)

**Pendiente de verificar en fuente oficial** (no fue posible abrir las páginas del Ministerio desde el entorno de
desarrollo): plazos exactos de la Resolución 1888 de 2025 y de la 1799 de 2026, URL canónicas de los perfiles RDA y
nombres de las operaciones de envío. Se configuran en `.env` (`RDA_PERFIL_BASE`, `IHCE_URL`) y en
`backend/app/services/rda.py` (`OPERACIONES`).
