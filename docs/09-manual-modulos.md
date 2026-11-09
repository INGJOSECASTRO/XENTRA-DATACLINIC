# 9. Manual de uso por módulo

Cada persona ve en el menú solo los módulos de su rol. Todo lo que se consulta o registra queda en el ledger de
auditoría.

## Matriz de permisos (resumen)

| Módulo | Admin | Médico | Enfermería | Admisiones | Facturación | Farmacia | Laboratorio | Auditor | Paciente |
|---|---|---|---|---|---|---|---|---|---|
| Pacientes (registro) | ✅ | ✅ | ✅ | ✅ | — | — | — | ver | — |
| Historia clínica | ✅ | ✅ escribe/firma | ✅ escribe/firma | — | — | — | — | ver | su propia (portal) |
| Agenda | ✅ | ✅ | ✅ | ✅ | ver | — | — | — | sus citas |
| Urgencias / triage | ✅ | ✅ | ✅ | ver cola | — | — | — | — | — |
| Hospitalización | ✅ | ✅ órdenes, evolución, egreso | ✅ notas, kárdex, balance | ver | — | — | — | ver | — |
| Laboratorio | ✅ | ordena y ve | toma muestras | — | — | — | ✅ resultados/validación | — | sus resultados |
| Farmacia | ✅ | ve inventario | ve inventario | — | — | ✅ | — | kárdex | — |
| Facturación | ✅ | — | — | — | ✅ | — | — | ver | — |
| Indicadores / SIVIGILA | ✅ | SIVIGILA | — | — | — | — | — | ✅ | — |
| Auditoría (ledger) | ✅ | — | — | — | — | — | — | ✅ | quién vio su HC |

## Mi cuenta y seguridad (todos)
1. Menú **Mi cuenta y seguridad** → **Configurar** segundo factor.
2. Escanee el QR con Google/Microsoft Authenticator y escriba el código de 6 dígitos.
3. Desde entonces, al iniciar sesión se pide el código. Si pierde el celular, el administrador lo desactiva en **Usuarios**.
4. La sesión se cierra sola tras **15 minutos sin actividad**.

## Agenda (admisiones, médicos, enfermería)
1. Elija la fecha y (opcional) el profesional.
2. En **Asignar cita** busque el paciente, elija profesional, modalidad (presencial o **telemedicina**) y haga clic en un horario libre.
3. Estados: *programada → confirmada → en sala → atendida*, o *cancelada* (con motivo) / *no asistió*.
4. El médico pulsa **Atender** y se abre la historia clínica ligada a la cita. En telemedicina, **Sala virtual** abre la videollamada (el paciente la ve en su portal).
5. **Enviar recordatorios** notifica las citas de mañana (conecte su proveedor de WhatsApp/SMS en `integraciones.py`).

## Historia clínica (médicos, enfermería)
1. Desde el paciente o la cita: **Nueva atención**.
2. Elija una **plantilla** (medicina general, HTA, prenatal, crecimiento y desarrollo, urgencias): rellena los campos vacíos.
3. Use **🎤 Dictar** en cualquier campo de texto (Chrome/Edge).
4. **Sugerir diagnósticos** (IA) y agregue los que correspondan, o búsquelos manualmente.
5. Al formular, el sistema avisa en tiempo real **alergias** e **interacciones**.
6. **Firmar y cerrar folio**: queda sellado. Para corregir, use **nota aclaratoria**.
7. **PDF historia / PDF fórmula**: documentos con QR que cualquiera puede verificar en `/verificar/...`.

## Urgencias (enfermería, médicos)
1. Busque al paciente, escriba el motivo y los signos vitales: el sistema **sugiere** el nivel de triage con sus razones.
2. Confirme o cambie el nivel (decisión del profesional) y **Clasificar**.
3. La sala de espera se ordena por nivel y llegada; en naranja quienes superaron el tiempo máximo.
4. **Atender** abre la historia clínica de urgencias; al firmarla, el triage se finaliza. Registre la fecha y condición de egreso (necesarias para RIPS de urgencias).

## Hospitalización
- **Médico**: crea la orden de hospitalización (paciente, cama, Dx), registra evoluciones, órdenes (medicamentos, dietas, laboratorios…), suspende órdenes y da el **egreso** con epicrisis.
- **Enfermería**: notas de enfermería con signos, **kárdex** (administrado / omitido con motivo), **balance de líquidos** (24 h automático).
- Las camas que se liberan quedan en *mantenimiento* (limpieza); enfermería las marca **Lista**.

## Laboratorio e imágenes
1. El médico ordena desde la ficha del paciente → pestaña **Laboratorio e imágenes**.
2. Laboratorio: **Toma realizada** → **Resultado** (analito, valor, unidad, referencia "70 - 100") → **Validar**.
3. Los valores fuera de rango se marcan en rojo; tras validar, el resultado queda sellado y aparece en el portal del paciente.

## Farmacia
- **Por dispensar**: fórmulas de consultas firmadas y órdenes hospitalarias activas. Elija producto y cantidad → **Entregar** (descuenta primero los lotes que vencen antes; nunca lotes vencidos).
- **Inventario**: entradas por lote con vencimiento y registro INVIMA; creación de productos.
- **Alertas**: stock bajo, vencidos y por vencer (90 días).

## Consentimientos informados
Ficha del paciente → **Consentimientos** → plantilla → complete el texto → firma en pantalla → **Registrar**. Se genera PDF con QR.

## Facturación
1. Marque los servicios pendientes (consultas firmadas, hospitalizaciones egresadas) del mismo pagador.
2. Complete el pagador y **Armar factura**: aparece la **pre-auditoría** (errores bloquean, advertencias informan).
3. **Emitir DIAN** → asigna número y CUFE, genera el RIPS.
4. **Validar MUV** → obtiene el CUV (o el rechazo con sus causas).
5. **RIPS** descarga el JSON. Un borrador se puede anular; una factura emitida se corrige con nota crédito.

## Portal del paciente
1. Admisiones, en la ficha del paciente (con correo y autorización de datos): **Crear acceso al portal** → entregue la clave temporal.
2. El paciente entra con su correo, ve resumen, consultas (PDF), citas (entra a la teleconsulta), resultados, **quién vio su historia** y puede **descargar toda su historia** en formato FHIR.

## Indicadores y SIVIGILA
Elija el periodo. Los eventos de notificación obligatoria se detectan al firmar (por CIE-10) y se exportan en CSV para diligenciar las fichas del INS.

## Auditoría
**Verificar cadena completa** comprueba que nadie alteró el ledger. **Anclar ahora** publica el hash del último bloque (o programe `python -m app.anclar` a diario).
