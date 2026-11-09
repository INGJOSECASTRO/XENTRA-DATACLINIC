# 6. Inteligencia artificial y CIE-10

## 6.1 Principio rector: la IA ayuda, el médico decide

- La IA **solo sugiere**. El diagnóstico lo elige y firma el profesional.
- Cada diagnóstico queda marcado como `sugerido_por_ia` para auditoría y para medir la calidad de la IA.
- **Anti-alucinación**: ningún código llega al usuario si no existe en el catálogo CIE-10 cargado y si no es
  pertinente para el sexo y la edad del paciente.

## 6.2 Dos motores

### Motor local (por defecto, `IA_PROVEEDOR=local`)

- Funciona **sin internet** y sin costo. Ningún dato sale del servidor.
- Entiende lenguaje coloquial colombiano mediante un diccionario de sinónimos
  (`gripa` → rinofaringitis, `presión alta` → hipertensión, `ardor al orinar` → infección urinaria, `agrieras` →
  reflujo…). Puede ampliarlo en `backend/app/services/cie10.py` (diccionario `SINONIMOS`).
- Calcula similitud (TF-IDF) entre el texto clínico y las descripciones oficiales.
- Filtra por sexo y edad.

### Claude de Anthropic (opcional, `IA_PROVEEDOR=claude`)

Mayor precisión: entiende el contexto clínico completo y propone el código más específico con una justificación.

Cómo activarlo:
1. Cree una cuenta en https://console.anthropic.com y genere una **API key**.
2. En `.env`:
   ```
   IA_PROVEEDOR=claude
   ANTHROPIC_API_KEY=sk-ant-...
   IA_MODELO=claude-opus-5-5
   ```
3. `docker compose up -d` para aplicar.

Protecciones incluidas (`backend/app/services/ia.py`):
- **Anonimización** antes de enviar: se eliminan nombres del paciente, números de documento/teléfono y correos.
- Respuesta en **JSON estructurado** (esquema estricto), validada contra el catálogo.
- Si la API falla o no responde, se usa el motor local automáticamente.
- Si el modelo principal declina una solicitud, la API reintenta con un modelo alterno (`fallbacks`).

> ⚖️ **Antes de activar Claude con datos reales**: aunque el texto va anonimizado, informe en su política de
> tratamiento de datos que usa un proveedor de IA en la nube, revise los términos de retención de datos del
> proveedor y evalúe la transferencia internacional de datos (Ley 1581). Muchas IPS empiezan con el motor local.

## 6.3 Catálogo CIE-10

- Trae una muestra de ~220 códigos frecuentes en atención primaria en `backend/app/data/cie10_muestra.csv`.
- Para producción **cargue el catálogo oficial completo** (instrucciones en la
  [guía de instalación](02-guia-instalacion-principiantes.md#cargar-el-catálogo-cie-10-oficial-completo)).
- Formato colombiano: 4 caracteres sin punto; los códigos de 3 caracteres llevan `X` (`I10` → `I10X`).
  El sistema convierte automáticamente `I10`, `i10`, `E11.9`.

## 6.4 Otras funciones de IA incluidas y recomendadas

| Función | Estado |
|---|---|
| Sugerencia de CIE-10 | ✅ |
| Alertas de signos vitales (crisis hipertensiva, SpO₂ baja, fiebre, IMC) | ✅ (reglas clínicas) |
| Alertas de alergia vs. medicamento formulado | 🔶 Fase 1 |
| Interacciones medicamentosas | 🔶 Fase 2 (requiere base de datos farmacológica licenciada) |
| Resumen automático de la HC para interconsultas/epicrisis | 🔶 Fase 2 (Claude) |
| Dictado por voz → nota SOAP | 🔶 Fase 3 |
| Auditoría de calidad de la nota y pertinencia RIPS antes de facturar (reduce glosas) | 🔶 Fase 2 |
| Predicción de reingreso / riesgo cardiovascular | 🔶 Fase 3 (requiere validación clínica) |

## 6.5 Cómo medir si la IA funciona

Cada diagnóstico guardado indica si vino de la IA. Con eso puede calcular:
- % de sugerencias aceptadas por los médicos.
- % de veces que el código final estaba entre las 3 primeras sugerencias.
- Glosas por diagnóstico antes y después de activar la IA.
