# Manual de usuario de XENTRA DATACLINIC

**Guía paso a paso para cada rol: médico, enfermería, admisiones, facturación, farmacia, laboratorio, auditor, administrador funcional y paciente.**

| | |
|---|---|
| Versión del software | 0.3.0 |
| Cómo usar este manual | Lea primero la **Parte A** (aplica a todos) y luego el capítulo de su rol |

---

## Contenido

**Parte A – Para todos los usuarios**
1. [Ingresar al sistema](#1-ingresar-al-sistema)
2. [Conocer la pantalla](#2-conocer-la-pantalla)
3. [Mi cuenta y seguridad](#3-mi-cuenta-y-seguridad)
4. [Reglas de oro](#4-reglas-de-oro)
5. [Cuando algo falla: soporte y contingencia](#5-cuando-algo-falla-soporte-y-contingencia)

**Parte B – Por rol**
6. [Médico(a)](#6-médicoa)
7. [Enfermería](#7-enfermería)
8. [Admisiones y agenda](#8-admisiones-y-agenda)
9. [Facturación](#9-facturación)
10. [Farmacia](#10-farmacia)
11. [Laboratorio clínico e imágenes](#11-laboratorio-clínico-e-imágenes)
12. [Auditor(a)](#12-auditora)
13. [Administrador(a) funcional](#13-administradora-funcional)
14. [Estudiantes, auxiliar de laboratorio y roles técnicos](#14-estudiantes-auxiliar-de-laboratorio-y-roles-técnicos)

**Parte C – Referencia**
15. [Inteligencia de negocio (todos los roles)](#15-inteligencia-de-negocio-todos-los-roles)
16. [Módulos adicionales (todos los roles)](#16-módulos-adicionales-todos-los-roles)
17. [Glosario](#17-glosario)

---

# Parte A – Para todos los usuarios

## 1. Ingresar al sistema

1. Abra el navegador (Chrome, Edge o Firefox) en la dirección que le dio la institución, por ejemplo `https://hce.miips.com`.
2. Escriba su **correo** y su **contraseña** y pulse **Ingresar**.
3. Si tiene activado el **segundo factor (MFA)**, abra en el celular la app autenticadora y escriba el código de 6 dígitos.
4. Verá la pantalla de **Inicio** con su nombre.

> **Primer ingreso.** La institución le entrega una **clave temporal**. El sistema lo lleva a **Mi cuenta y seguridad** y no le deja usar ninguna otra pantalla hasta que la cambie. Si su rol exige segundo factor (médicos, auditores, facturación y administradores), también debe activar el MFA allí mismo (sección 3.1).

| Mensaje | Qué significa | Qué hacer |
|---|---|---|
| "Correo o contraseña incorrectos" | Datos errados | Revise mayúsculas y el teclado |
| "Usuario bloqueado temporalmente" | 5 intentos fallidos | Espere 15 minutos |
| "Sesión cerrada por inactividad" | Pasaron 15 minutos sin uso | Vuelva a ingresar (protege sus pacientes si deja el equipo abierto) |
| "Código de verificación incorrecto" | El código del MFA venció o la hora del celular está mal | Use el código nuevo; ajuste la hora automática del celular |

> **Nunca comparta su usuario.** Todo lo que se haga con su cuenta queda a su nombre en la auditoría.

## 2. Conocer la pantalla

- **Menú (izquierda):** muestra solo los módulos de su rol. Si no ve algo, su rol no lo incluye.
- **Avisos (arriba):** mantenimientos o contingencias que publica la institución.
- **Abajo a la izquierda:** su nombre, su rol y **Cerrar sesión**.
- **Inicio:** cifras generales y el estado de la **Seguridad blockchain**. "Cadena íntegra" significa que nadie ha alterado los registros.

| Color | Significado |
|---|---|
| Rojo | Alergias, errores, alertas graves |
| Naranja / amarillo | Advertencias, borradores, pendientes |
| Verde | Firmado, válido, correcto |
| Morado | Sugerencias de inteligencia artificial |

## 3. Mi cuenta y seguridad

Menú **Mi cuenta y seguridad**.

### 3.1 Activar el segundo factor (muy recomendado)

1. Instale en su celular **Google Authenticator**, **Microsoft Authenticator** o **Authy**.
2. Pulse **Configurar**: aparece un código QR.
3. En la app, agregue una cuenta y escanee el QR.
4. Escriba el código de 6 dígitos y pulse **Activar**.
5. Desde ahora, al ingresar se le pedirá el código. Si cambia o pierde el celular, avise al administrador.

### 3.2 Cambiar la contraseña

Escriba la contraseña actual y la nueva dos veces. La nueva debe tener mínimo **10 caracteres, mayúsculas, minúsculas y números**.

## 4. Reglas de oro

1. **Lo firmado no se borra ni se edita** (Resolución 1995 de 1999). Si se equivocó, agregue una **nota aclaratoria**.
2. **Cada consulta queda registrada:** abrir la historia de un paciente queda en la auditoría, y el paciente puede ver quién la consultó. Abra solo las historias que necesita para su trabajo.
3. **La inteligencia artificial sugiere y usted decide.**
4. **Cierre sesión** al terminar, sobre todo en equipos compartidos.
5. **Los PDF contienen datos sensibles:** no los envíe por canales no autorizados.

## 5. Cuando algo falla: soporte y contingencia

### 5.1 Si aparece un error

1. Copie el **código de error** que muestra el mensaje (10 letras y números).
2. Vaya a **Soporte y continuidad → Mesa de ayuda**.
3. Antes, revise la **Base de conocimiento**: quizá ya está la solución.
4. Llene título, tipo, **prioridad**, módulo, código de error y descripción (qué hacía, qué pasó, desde cuándo).

| Prioridad | Úsela cuando | Respuesta máxima |
|---|---|---|
| Crítica | No se puede atender pacientes | 4 horas |
| Alta | Un módulo importante falla | 8 horas |
| Media | Molestia con alternativa | 24 horas |
| Baja | Mejora o duda | 72 horas |

5. Siga su caso en **Mis tickets**; puede agregar comentarios.

### 5.2 Si el sistema no está disponible (contingencia)

1. **Al iniciar cada turno**, descargue el PDF en **Soporte y continuidad → Plan de contingencia**. Contiene la agenda del día con alergias, problemas y medicamentos de cada paciente, y el censo hospitalario con las órdenes activas.
2. Si el sistema falla, atienda con ese PDF y los formatos en papel de la institución.
3. Al volver el sistema, transcriba lo atendido indicando **"registro diferido por contingencia"**.
4. Reporte el incidente con prioridad **crítica**.
5. Destruya el PDF al terminar el turno.

---

# Parte B – Por rol

## 6. Médico(a)

**Menús:** Inicio, Pacientes, Agenda, Urgencias, Hospitalización, Laboratorio e imágenes, Indicadores, Inteligencia de negocio, Módulos adicionales, Soporte y continuidad, Mi cuenta.

### 6.1 Buscar o registrar un paciente

1. **Pacientes** → escriba el documento o el nombre → **Buscar**.
2. Si no existe: **+ Nuevo paciente** → llene los datos. Los marcados con * son obligatorios; el municipio va en código DIVIPOLA (Bogotá: 11001).
3. Marque la **autorización de tratamiento de datos** solo si el paciente la dio (Ley 1581).
4. Registre las **alergias**: aparecerán en rojo en toda la historia.

### 6.2 Ficha del paciente

- **Resumen IA:** problemas activos, medicamentos recientes y resultados anormales en segundos.
- Pestañas:
  - **Historia clínica:** todos los folios.
  - **Laboratorio e imágenes:** órdenes y resultados.
  - **Consentimientos:** registrados y nuevos.

### 6.3 Atender una consulta

1. Desde **Agenda → Atender** (queda ligada a la cita) o desde la ficha → **+ Nueva atención**.
2. **Plantilla** (arriba a la derecha): medicina general, control de HTA, control prenatal, crecimiento y desarrollo o urgencias. Llena los campos vacíos; usted completa los "___".
3. **S – Subjetivo:** motivo de consulta, enfermedad actual, antecedentes y revisión por sistemas. Use **🎤 Dictar** para hablar en vez de escribir (Chrome o Edge).
4. **O – Objetivo:** signos vitales (el IMC se calcula solo) y examen físico.
5. **A – Análisis y diagnósticos:**
   - Escriba el análisis.
   - **Asistente IA CIE-10 → Sugerir diagnósticos:** revise las sugerencias, su confianza y la justificación, y pulse **Agregar** en las que correspondan.
   - O busque manualmente por código (I10) o por texto (hipertensión).
   - El primero es el **diagnóstico principal**; puede haber hasta 3 relacionados.
   - Elija el tipo: impresión diagnóstica, confirmado nuevo o confirmado repetido.
6. **P – Plan:** plan de manejo.
   - **Fórmula médica:** + Medicamento. Si hay **alergia o interacción**, aparece un aviso en rojo o naranja mientras escribe. Revíselo.
   - **Procedimientos (CUPS)** realizados.
7. **Datos para facturación / RIPS:** servicio, finalidad, causa, modalidad (telemedicina si aplica), autorización, valor y copago. Use las listas desplegables.
8. **Guardar borrador** (puede volver después) o **Firmar y cerrar folio**.

### 6.4 Después de firmar

- El folio queda **sellado**: recuadro "Integridad (sello blockchain)" con la huella SHA-256.
- **Verificar integridad:** confirma que nadie lo alteró.
- **PDF historia** y **PDF fórmula**, con código QR que cualquiera (farmacia, EPS) puede escanear para verificar su autenticidad.
- **Nota aclaratoria:** para corregir o complementar. Queda con su nombre y la hora.
- Automáticamente se genera el **RDA** (Resolución 1888) y, si el diagnóstico es de **notificación obligatoria**, aparece un aviso de SIVIGILA para diligenciar la ficha del INS.

### 6.5 Telemedicina

En la **Agenda**, las citas de telemedicina tienen el botón **Sala virtual**. Ábralo, atienda por video y registre la atención (se marca la modalidad de telemedicina). Registre también el consentimiento de telemedicina.

### 6.6 Urgencias

1. **Urgencias:** la sala de espera está ordenada por nivel de triage (I rojo a V azul) y por hora de llegada. En naranja aparecen quienes superaron el tiempo máximo.
2. **Atender:** abre la historia de urgencias con la plantilla.
3. Antes de firmar registre la **fecha, hora y condición de egreso** (necesarias para RIPS). Si el paciente falleció, registre el **diagnóstico de causa de muerte**.
4. Al firmar, el triage se finaliza solo.

### 6.7 Hospitalizar y seguir al paciente

1. **Hospitalización → Orden de hospitalización:** paciente, cama disponible, diagnóstico de ingreso (CIE-10), vía de ingreso, autorización, valor del día y motivo.
2. En la ficha de hospitalización:
   - **Evoluciones y notas:** evolución médica con signos vitales; puede dictar.
   - **Órdenes y kárdex:** medicamentos (desde el inventario), dietas, cuidados, laboratorios, imágenes, procedimientos e interconsultas.
     - Si hay **alergia o interacción grave**, el sistema bloquea la orden y muestra el motivo. Solo puede continuar con **"Ordenar de todas formas"**, y queda registrado.
     - **Suspender** una orden cuando ya no aplique.
   - **Balance de líquidos:** ingresos y egresos de 24 horas.
   - **Egreso / epicrisis:** condición de egreso, diagnóstico de egreso y relacionados, y epicrisis. Al confirmar, la epicrisis queda sellada y se genera el **PDF de epicrisis** y el RDA de hospitalización.

### 6.8 Ordenar laboratorios e imágenes

Ficha del paciente → **Laboratorio e imágenes** → tipo, CUPS, examen, prioridad e indicaciones → **Ordenar**. El resultado aparece cuando el laboratorio lo valida; los valores anormales se ven en rojo.

### 6.9 Consentimiento informado

Ficha del paciente → **Consentimientos** → plantilla (procedimiento, hospitalización, telemedicina, transfusión, retiro voluntario) → complete los "____" → datos del firmante → **firma con el dedo o el lápiz** en la pantalla → **Registrar**. Se genera un PDF con QR.

### 6.10 Reporte SIVIGILA

**Indicadores → Eventos de notificación obligatoria → Descargar CSV**, para diligenciar las fichas del INS.

---

## 7. Enfermería

**Menús:** Inicio, Pacientes, Agenda, Urgencias, Hospitalización, Laboratorio e imágenes, Inteligencia de negocio, Módulos adicionales, Soporte y continuidad, Mi cuenta.

### 7.1 Triage en urgencias

1. **Urgencias → Clasificación (triage):** busque al paciente (o regístrelo en Pacientes).
2. Escriba el **motivo** y los **signos vitales**: TA, FC, FR, temperatura, SpO₂ y Glasgow.
3. El sistema **sugiere el nivel** y explica por qué (por ejemplo, "SpO₂ 88 %").
4. Usted decide: deje el sugerido o elija otro.
5. **Clasificar.** El paciente entra a la sala de espera.

| Nivel | Atención |
|---|---|
| I | Inmediata (riesgo vital) |
| II | Máximo 30 minutos |
| III, IV, V | Según el protocolo institucional |

### 7.2 Hospitalización

Abra al paciente desde el **mapa de camas** o el censo.

- **Notas de enfermería:** signos vitales y nota (puede dictar).
- **Kárdex:** en **Órdenes y kárdex**, para cada medicamento activo pulse **Administrado** o **Omitido** (si lo omite, escriba el motivo). Queda con su nombre y la hora, y no se puede modificar.
- **Balance de líquidos:** registre cada ingreso (oral, intravenoso, sonda) y egreso (orina, drenaje, vómito, deposición, sangrado). El total de 24 horas se calcula solo.
- **Alertas:** si los últimos signos están fuera de rango (por ejemplo, saturación baja), aparecen arriba en naranja.
- **Camas en mantenimiento:** después de un egreso o traslado la cama queda en limpieza. Cuando esté lista, pulse **Lista** en el mapa de camas.

### 7.3 Toma de muestras

**Laboratorio e imágenes → Pendientes de toma → Toma realizada.**

### 7.4 Módulos asignados

En **Módulos adicionales** registre, por ejemplo, la **valoración de riesgo de caídas** o el **reporte de eventos adversos**. Los registros con 🔒 quedan sellados.

### 7.5 Consentimientos y atenciones de enfermería

Igual que el médico (secciones 6.3 y 6.9), si su institución lo autoriza.

---

## 8. Admisiones y agenda

**Menús:** Inicio, Pacientes, Agenda, Urgencias (consulta), Hospitalización (consulta), Inteligencia de negocio, Módulos adicionales, Soporte y continuidad, Mi cuenta.

### 8.1 Registrar pacientes

Igual que la sección 6.1. Verifique el documento antes de crear, para no duplicar. Registre el **correo** y el teléfono para recordatorios de citas.

### 8.2 Asignar una cita

1. **Agenda** → elija la **fecha**.
2. **Asignar cita:** busque al paciente, elija el profesional, la duración, la modalidad (presencial o telemedicina), el CUPS, la autorización y el motivo.
3. Pulse un **horario libre** (el sistema no muestra los ocupados) → **Asignar cita**.
4. En telemedicina se crea la sala virtual automáticamente.

### 8.3 Gestionar el día

| Botón | Cuándo |
|---|---|
| Confirmar | El paciente confirmó por teléfono |
| Llegó (en sala) | El paciente se presentó; avisa al profesional |
| Cancelar | Pide el motivo (se usa en los indicadores) |
| No asistió | No se presentó |

- **Reprogramar:** con la API o cancelando y asignando de nuevo.
- **Enviar recordatorios:** cada tarde envía los recordatorios de las citas del día siguiente.

### 8.4 Solicitudes de copia de la historia clínica

En esta institución **los pacientes no ingresan a la plataforma** (el portal está deshabilitado y no aparece el botón "Crear acceso al portal"). Si un paciente pide copia de su historia o saber quién la consultó, reciba la solicitud por escrito y remítala según los Protocolos de seguridad (sección 2): el médico o el archivo entrega el PDF firmado y el auditor genera el reporte de accesos.

### 8.5 PQRS

Si la institución instaló el módulo, regístrelas en **Módulos adicionales → PQRS**.

---

## 9. Facturación

**Menús:** Inicio, Facturación electrónica, RIPS (generar y validar), Inteligencia de negocio, Módulos adicionales, Soporte y continuidad, Mi cuenta.

### 9.1 Flujo completo

```
Servicios pendientes → Armar factura → Pre-auditoría → Emitir DIAN (CUFE) → Validar MUV (CUV) → Descargar RIPS
```

1. **Facturación electrónica → Servicios pendientes:** atenciones firmadas y hospitalizaciones egresadas sin facturar. Filtre por EPS.
2. Marque los servicios **del mismo pagador**.
3. **Datos del pagador:** tipo, nombre, código EAPB, NIT, modalidad de pago y contrato.
4. **Armar factura:** se crea el borrador y aparece la **pre-auditoría**.
   - **Rojo (error):** impide emitir. Por ejemplo: ítem sin valor, paciente de otra EPS, error de RIPS.
   - **Naranja (advertencia):** revise antes de radicar. Por ejemplo: falta de autorización, valor distinto a la tarifa, posible duplicidad, síntoma marcado como confirmado.
   - **Verde:** sin hallazgos.
5. **Emitir DIAN:** asigna el número consecutivo y el CUFE, y genera el RIPS.
6. **Validar MUV:** obtiene el **CUV** (validada) o el rechazo con sus causas.
7. **RIPS:** descarga el JSON.

### 9.2 Correcciones

- Un **borrador** se puede **anular** (con motivo) y los servicios vuelven a quedar pendientes.
- Una factura **emitida no se anula**: se corrige con **nota crédito** ante la DIAN, con su proveedor.
- Si el MUV la **rechaza**: corrija la causa (normalmente en la atención o en los datos del paciente) y valide de nuevo.

### 9.3 Validador de RIPS (antes de facturar)

**RIPS (generar y validar):** marque atenciones firmadas, escriba un número de factura y pulse **Generar y validar**. Muestra los errores o "Estructura válida", y puede **Descargar JSON**.

### 9.4 Reportes

**Inteligencia de negocio → Facturación por pagador y estado**, con exportación a Excel.

---

## 10. Farmacia

**Menús:** Inicio, Farmacia, Inteligencia de negocio, Módulos adicionales, Soporte y continuidad, Mi cuenta.

### 10.1 Dispensar

1. **Farmacia → Por dispensar.**
   - **Fórmulas de consulta:** de atenciones firmadas, con lo entregado y lo pendiente.
   - **Órdenes de hospitalización** activas.
2. Elija el **producto** (se sugiere solo) y la **cantidad** → **Entregar**.
3. El sistema descuenta **primero el lote que vence antes (FEFO)** y **nunca entrega lotes vencidos**.
4. No permite entregar más de lo formulado.
5. Cada entrega genera el **RDA de dispensación** (Resolución 1799 de 2026).

### 10.2 Inventario

- **Entrada de mercancía:** producto, lote, vencimiento, cantidad y registro INVIMA. No se reciben productos vencidos.
- **Nuevo producto:** nombre (DCI, concentración y forma), CUM, unidad, stock mínimo, precio, y si es de **control especial** o requiere **cadena de frío**.
- **Kárdex:** historial de movimientos de cada producto (entradas, dispensaciones, ajustes). No se puede modificar.

### 10.3 Alertas

**Farmacia → Alertas:** stock bajo, vencidos (retirar) y por vencer en 90 días.

---

## 11. Laboratorio clínico e imágenes

**Menús:** Inicio, Laboratorio e imágenes, Inteligencia de negocio, Módulos adicionales, Soporte y continuidad, Mi cuenta.

1. Elija el filtro: **Pendientes de toma**, **Pendientes de resultado**, **Pendientes de validar** o **Validados**. Las órdenes **URGENTES** aparecen primero.
2. **Toma realizada** cuando se tome la muestra.
3. **Resultado:** filas de analito, valor, unidad y referencia (escriba el rango así: `70 - 100`). Los valores fuera de rango se marcan en rojo automáticamente. Agregue el informe o la lectura (imágenes).
4. **Validar:** el bacteriólogo (rol `laboratorio`) sella el resultado. Ya no se puede modificar y aparece en la historia del paciente.

> **Auxiliar de laboratorio:** puede hacer los pasos 1 a 3 (toma y digitación), pero **no** valida (Ley 841 de 2003). Sus resultados quedan en "Pendientes de validar" hasta que el bacteriólogo los revise.

---

## 12. Auditor(a)

**Menús:** Inicio, Pacientes, Hospitalización, Facturación electrónica (consulta), Indicadores, Inteligencia de negocio, Módulos adicionales, Soporte y continuidad, Seguridad blockchain, Mi cuenta.

### 12.1 Seguridad blockchain

1. **Seguridad blockchain → Verificar cadena completa:** recorre todos los bloques. "Cadena íntegra" significa que no hubo alteraciones. Si hay un problema, indica el bloque exacto.
2. **Lista de bloques:** quién hizo qué, cuándo y desde qué IP. Filtre por acción: LOGIN, CONSULTA_HC, ATENCION_FIRMADA, FACTURA_EMITIDA, DISPENSACION, etc.
3. **Anclaje externo → Anclar ahora:** publica la huella del último bloque como sello de tiempo. "Coincide" confirma que la cadena no se reescribió después.

### 12.2 Auditoría de historias clínicas

- Lectura de todas las historias (cada consulta queda registrada).
- En cada folio, **Verificar integridad**.
- Revise los diagnósticos marcados como **sugeridos por IA**.

### 12.3 Auditoría de cuentas

**Facturación electrónica:** abra cada factura para ver ítems, hallazgos de pre-auditoría, CUFE y CUV. **Re-auditar** vuelve a ejecutar las reglas.

### 12.4 Indicadores y BI

- **Indicadores:** oportunidad de citas, inasistencia, triage II atendido en 30 minutos o menos, ocupación, estancia, mortalidad, primeros diagnósticos, producción por profesional, uso de IA y facturación validada.
- **Inteligencia de negocio:** análisis libre (Parte C).

### 12.5 Estado del sistema y RDA

- **Soporte y continuidad → Estado del sistema:** base de datos, disco, respaldos, prueba de restauración, ledger, tickets, integraciones y alertas.
- **RDA (Res. 1888):** cola de envío a la IHCE, plazos de cumplimiento y reintentos.

### 12.6 Módulos de calidad

Consulte los **eventos adversos** y demás módulos de calidad en **Módulos adicionales** y analícelos en **Inteligencia de negocio**.

---

## 13. Administrador(a) funcional

Además de todo lo anterior:

- **Usuarios:** crear, desactivar, asignar roles y quitar el MFA.
- **Módulos adicionales:** instalar plantillas o crear módulos nuevos.
- **Avisos:** publicar mantenimientos o contingencias.
- **Mesa de ayuda:** atender, resolver y documentar soluciones.
- **Camas:** crear camas por servicio.

El detalle técnico está en el **Manual del administrador técnico** (`02-MANUAL-ADMINISTRADOR-TECNICO.md`).

---

## 14. Estudiantes, auxiliar de laboratorio y roles técnicos

### 14.1 Estudiante, interno o residente

**Menús:** Inicio, Pacientes, Módulos adicionales, Soporte y continuidad, Mi cuenta.

1. Busque al paciente y pulse **+ Nueva atención**.
2. Diligencie la historia como en la sección 6.3 (puede usar plantillas, dictado y el asistente IA CIE-10).
3. Pulse **Guardar borrador**. **No existe el botón Firmar** para usted: el registro queda **pendiente de refrendo** de su docente (Decreto 2376 de 2010).
4. Puede volver a abrir y corregir su borrador mientras el docente no lo haya refrendado.

### 14.2 Médico docente: refrendar

1. En **Inicio** aparece la tarjeta **Registros de estudiantes pendientes de su refrendo**.
2. Pulse **Revisar y refrendar**. Se abre el registro con el aviso "Registro elaborado por el estudiante…".
3. Revíselo, corríjalo si es necesario y pulse **Refrendar y firmar**. Al hacerlo, usted asume la responsabilidad del registro.
4. El folio queda sellado. El PDF muestra el estudiante que lo elaboró y a usted como docente que lo refrendó.

### 14.3 Auxiliar de laboratorio

**Menús:** Inicio, Laboratorio e imágenes, Módulos adicionales, Soporte y continuidad, Mi cuenta. Toma muestras y digita resultados (sección 11, pasos 1 a 3). No valida.

### 14.4 Administrador técnico (sistemas)

**Menús:** Inicio, Hospitalización (solo camas), Seguridad blockchain, Usuarios, Módulos adicionales, Soporte y continuidad, Mi cuenta.

- Crea y desactiva usuarios (excepto administradores), repone el MFA según el protocolo P-02, administra sedes, camas y módulos, publica avisos y atiende tickets.
- **No** ve historias clínicas ni nombres de pacientes: en hospitalización solo ve si cada cama está libre, ocupada o en mantenimiento.

### 14.5 Auditor de sistemas (seguridad de la información)

**Menús:** Inicio, Indicadores (gerencia), Seguridad blockchain, Módulos adicionales, Soporte y continuidad, Mi cuenta.

- Verifica la cadena, revisa accesos e intentos fallidos y vigila las acciones de los administradores (protocolo P-07).
- Consulta el estado del sistema y la cola RDA. No ve historias clínicas.

> **Pacientes:** en esta institución los pacientes no tienen acceso a la plataforma. Sus solicitudes se atienden según la sección 8.4.

---

# Parte C – Referencia

## 15. Inteligencia de negocio (todos los roles)

Menú **Inteligencia de negocio**. Cada rol ve solo los datos que le corresponden.

1. **Reportes sugeridos**, con un clic: morbilidad por capítulo CIE-10 y curso de vida, producción por profesional, atenciones por EPS, oportunidad e inasistencia, facturación por pagador, estancia y mortalidad, demanda de urgencias por hora y consumo de medicamentos.
2. **Constructor:**
   - **¿Qué quiere analizar?** (atenciones, citas, facturación, hospitalización, farmacia, urgencias, laboratorio o un módulo adicional).
   - Fechas **desde** y **hasta**.
   - **Agrupar por** hasta 3 campos (mes, profesional, diagnóstico, EPS, sexo, curso de vida…).
   - **Medir** (número, pacientes únicos, valor, promedios, porcentajes).
   - **Filtros** opcionales (por ejemplo, Sexo = M).
   - **Generar reporte:** gráfico de barras o líneas, y tabla.
3. **Excel** o **CSV** para descargar.
4. **Guardar reporte**, y si quiere, compartirlo con otros roles (por ejemplo, "medico, auditor").

Los reportes muestran solo **datos agregados**: nunca nombres ni documentos.

## 16. Módulos adicionales (todos los roles)

1. Menú **Módulos adicionales** → elija el módulo (los que tienen 🔒 se sellan al guardar).
2. Si es por paciente, búsquelo.
3. Llene el formulario (los campos con * son obligatorios) → **Guardar registro**.
4. Abajo verá los registros. Quien solo registra ve los suyos; quien consulta ve todos.

## 17. Glosario

| Término | Significado |
|---|---|
| **Folio** | Cada atención dentro de la historia clínica |
| **Firmar / sellar** | Cerrar un registro para que no pueda modificarse |
| **Nota aclaratoria** | Corrección posterior a la firma, con autor y hora |
| **Ledger / blockchain** | Registro encadenado e inalterable de todas las acciones |
| **SHA-256 / huella** | Código único que cambia si el contenido cambia una sola letra |
| **QR de verificación** | Permite comprobar que un PDF es auténtico, sin ver datos clínicos |
| **CIE-10** | Clasificación de diagnósticos (formato colombiano de 4 caracteres, ej. I10X) |
| **CUPS** | Códigos de procedimientos y servicios |
| **CUM** | Código único de medicamentos (INVIMA) |
| **RIPS** | Registros de prestación de servicios que soportan la factura (Res. 2275 de 2023) |
| **CUFE** | Código de la factura electrónica (DIAN) |
| **MUV / CUV** | Validador del Ministerio y código de validación de los RIPS |
| **RDA** | Resumen Digital de Atención (Res. 1888 de 2025) que se envía a la IHCE |
| **IHCE** | Interoperabilidad de la Historia Clínica Electrónica (plataforma del Ministerio) |
| **FHIR** | Estándar internacional de intercambio de información en salud |
| **Triage** | Clasificación de urgencias en 5 niveles (Res. 5596 de 2015) |
| **Kárdex** | Registro de administración de medicamentos por enfermería |
| **FEFO** | Primero en vencer, primero en salir (farmacia) |
| **Pre-auditoría** | Revisión automática de la cuenta antes de facturar, para evitar glosas |
| **MFA** | Segundo factor: código del celular además de la contraseña |
| **ANS** | Acuerdo de nivel de servicio (tiempo máximo de respuesta de soporte) |
| **SIVIGILA** | Sistema de vigilancia en salud pública (eventos de notificación obligatoria) |
| **Contingencia** | Operación en papel cuando el sistema no está disponible |
