<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, mensajeError } from '../api/cliente'
import type { Atencion, CIE10, Diagnostico, Paciente, Prescripcion, Procedimiento, Sugerencia } from '../api/tipos'
import SelectorCIE10 from '../components/SelectorCIE10.vue'
import { useAuth } from '../stores/auth'
import CampoTexto from '../components/CampoTexto.vue'
import CatalogoSelect from '../components/CatalogoSelect.vue'

const route = useRoute()
const router = useRouter()
const pacienteId = route.params.id as string
const atencionId = ref<string | null>((route.params.atencionId as string) || null)
const paciente = ref<Paciente | null>(null)
const error = ref('')
const guardando = ref(false)
const sugerencias = ref<Sugerencia[]>([])
const proveedorIA = ref('')
const pensando = ref(false)

const form = reactive({
  tipo: 'consulta',
  motivo_consulta: '',
  enfermedad_actual: '',
  antecedentes: { personales: '', familiares: '', quirurgicos: '', farmacologicos: '', alergicos: '', gineco_obstetricos: '', habitos: '' } as Record<string, string>,
  revision_sistemas: '',
  signos_vitales: { ta_sistolica: null, ta_diastolica: null, fc: null, fr: null, temperatura: null, spo2: null, peso: null, talla: null } as Record<string, number | null>,
  examen_fisico: '',
  analisis: '',
  plan: '',
  cod_consulta_cups: '890201',
  finalidad_tecnologia: '15',
  modalidad_grupo_servicio: '01',
  grupo_servicios: '01',
  fecha_egreso: '' as string | null,
  condicion_egreso: null as string | null,
  dx_causa_muerte: null as string | null,
  causa_motivo_atencion: '38',
  cod_servicio: 328,
  num_autorizacion: '',
  valor_servicio: 0,
  valor_pago_moderador: 0,
  diagnosticos: [] as Diagnostico[],
  procedimientos: [] as Procedimiento[],
  prescripciones: [] as Prescripcion[],
})

const imc = computed(() => {
  const { peso, talla } = form.signos_vitales
  if (!peso || !talla) return null
  return (peso / (talla / 100) ** 2).toFixed(1)
})

const auth = useAuth()
const esEstudiante = auth.tiene('estudiante')
const autor = ref<{ id: string; nombre_completo?: string; nombres: string; apellidos: string; rol: string } | null>(null)
const refrendo = computed(() => !!autor.value && autor.value.id !== auth.usuario?.id)
const plantillas = ref<Record<string, Record<string, string>>>({})
const plantilla = ref('')
const alertasFormula = ref<{ severidad: string; mensaje: string }[]>([])
const citaId = (route.query.cita as string) || null
const triageId = (route.query.triage as string) || null

function aplicarPlantilla() {
  const pl = plantillas.value[plantilla.value]
  if (!pl) return
  const f = form as unknown as Record<string, unknown>
  for (const [campo, texto] of Object.entries(pl)) if (campo !== 'nombre' && !f[campo]) f[campo] = texto
}

let espera: ReturnType<typeof setTimeout> | undefined
watch(() => form.prescripciones.map((r) => r.medicamento).join('|'), (meds) => {
  clearTimeout(espera)
  espera = setTimeout(async () => {
    const lista = meds.split('|').filter((m) => m.trim().length > 2)
    alertasFormula.value = lista.length
      ? (await api.post('/clinica/revisar-prescripcion', { paciente_id: pacienteId, medicamentos: lista })).data : []
  }, 600)
})

onMounted(async () => {
  plantillas.value = (await api.get('/clinica/plantillas')).data
  if (route.query.tipo === 'urgencias') {
    Object.assign(form, { tipo: 'urgencias', grupo_servicios: '05', cod_consulta_cups: '890701', cod_servicio: 501 })
    plantilla.value = 'urgencias'
  }
  paciente.value = (await api.get(`/pacientes/${pacienteId}`)).data
  if (paciente.value?.alergias) form.antecedentes.alergicos = paciente.value.alergias
  if (atencionId.value) {
    const a: Atencion = (await api.get(`/atenciones/${atencionId.value}`)).data
    if (a.estado === 'firmada') return router.replace(`/atenciones/${a.id}`)
    autor.value = a.profesional
    Object.assign(form, {
      ...a,
      antecedentes: { ...form.antecedentes, ...((a as unknown as { antecedentes: object }).antecedentes || {}) },
      signos_vitales: { ...form.signos_vitales, ...(a.signos_vitales || {}) },
      num_autorizacion: (a as unknown as { num_autorizacion: string }).num_autorizacion || '',
    })
    const egreso = (a as unknown as { fecha_egreso: string | null }).fecha_egreso
    if (egreso) {
      const d = new Date(egreso)
      form.fecha_egreso = new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16)
    }
  }
})

function agregarDx(codigo: string, descripcion: string, ia = false) {
  if (form.diagnosticos.some((d) => d.codigo_cie10 === codigo)) return
  if (form.diagnosticos.length >= 4) {
    error.value = 'Máximo 4 diagnósticos (1 principal + 3 relacionados, como exige RIPS)'
    return
  }
  form.diagnosticos.push({ codigo_cie10: codigo, descripcion, tipo_diagnostico: '01', sugerido_por_ia: ia })
}

async function sugerirIA() {
  const texto = [form.motivo_consulta, form.enfermedad_actual, form.examen_fisico, form.analisis].filter(Boolean).join('. ')
  if (texto.length < 5) {
    error.value = 'Escriba el motivo de consulta o la enfermedad actual para obtener sugerencias'
    return
  }
  pensando.value = true
  try {
    const { data } = await api.post('/cie10/sugerir', { texto, paciente_id: pacienteId })
    sugerencias.value = data.sugerencias
    proveedorIA.value = data.proveedor
  } catch (e) {
    error.value = mensajeError(e)
  } finally {
    pensando.value = false
  }
}

function payload() {
  const limpiar = (o: Record<string, unknown>) => Object.fromEntries(Object.entries(o).filter(([, v]) => v !== '' && v !== null))
  return {
    ...form,
    paciente_id: pacienteId,
    cita_id: atencionId.value ? undefined : citaId,
    fecha_egreso: form.fecha_egreso ? new Date(form.fecha_egreso).toISOString() : null,
    num_autorizacion: form.num_autorizacion || null,
    antecedentes: limpiar(form.antecedentes),
    signos_vitales: limpiar(form.signos_vitales),
  }
}

async function guardar(firmar = false) {
  error.value = ''
  const texto = refrendo.value ? 'Al REFRENDAR, usted firma y asume la responsabilidad del registro del estudiante. El folio quedará sellado. ¿Continuar?'
    : 'Al firmar, el folio queda SELLADO y no podrá modificarse (solo notas aclaratorias). ¿Firmar ahora?'
  if (firmar && !confirm(texto)) return
  guardando.value = true
  try {
    const { data } = atencionId.value
      ? await api.put(`/atenciones/${atencionId.value}`, payload())
      : await api.post('/atenciones', payload())
    atencionId.value = data.id
    if (firmar) {
      await api.post(`/atenciones/${data.id}/firmar`)
      if (triageId) await api.post(`/urgencias/triage/${triageId}/finalizar`, null, { params: { atencion_id: data.id } }).catch(() => null)
      router.push(`/atenciones/${data.id}`)
    } else {
      router.replace(`/pacientes/${pacienteId}/atencion/${data.id}`)
      alert(esEstudiante ? 'Borrador guardado. Quedó pendiente de refrendo por su docente.' : 'Borrador guardado')
    }
  } catch (e) {
    error.value = mensajeError(e)
  } finally {
    guardando.value = false
  }
}
</script>

<template>
  <div v-if="paciente">
    <div class="fila entre">
      <div>
        <h1 style="margin: 0">{{ atencionId ? 'Editar atención (borrador)' : 'Nueva atención' }}</h1>
        <p class="suave">{{ paciente.nombre_completo }} · {{ paciente.tipo_documento }} {{ paciente.numero_documento }} · {{ paciente.edad }} años</p>
      </div>
      <RouterLink class="btn sec" :to="`/pacientes/${pacienteId}`">Volver</RouterLink>
    </div>
    <div v-if="paciente.alergias" class="alerta error"><strong>ALERGIAS:</strong> {{ paciente.alergias }}</div>
    <div v-if="esEstudiante" class="alerta aviso">Usted registra como <strong>estudiante</strong>: guarde el borrador; su docente lo revisará y lo refrendará con su firma (Decreto 2376 de 2010).</div>
    <div v-if="refrendo" class="alerta aviso">Registro elaborado por el estudiante <strong>{{ autor?.nombres }} {{ autor?.apellidos }}</strong>. Revíselo, corríjalo si es necesario y refréndelo.</div>

    <div class="tarjeta">
      <div class="fila entre">
        <h2 style="margin: 0">S · Subjetivo</h2>
        <label class="fila" style="flex-direction: row; align-items: center">Plantilla
          <select v-model="plantilla" style="max-width: 280px" @change="aplicarPlantilla">
            <option value="">—</option><option v-for="(pl, k) in plantillas" :key="k" :value="k">{{ pl.nombre }}</option>
          </select>
        </label>
      </div>
      <div class="rejilla" style="margin-bottom: .75rem">
        <label>Tipo de atención
          <select v-model="form.tipo"><option value="consulta">Consulta externa</option><option value="control">Control</option><option value="urgencias">Urgencias</option><option value="hospitalizacion">Hospitalización</option></select>
        </label>
      </div>
      <CampoTexto v-model="form.motivo_consulta" etiqueta="Motivo de consulta *" placeholder="En palabras del paciente" />
      <CampoTexto v-model="form.enfermedad_actual" etiqueta="Enfermedad actual" />
      <h3 style="margin-top: 1rem">Antecedentes</h3>
      <div class="rejilla">
        <label>Personales / patológicos <textarea v-model="form.antecedentes.personales" /></label>
        <label>Familiares <textarea v-model="form.antecedentes.familiares" /></label>
        <label>Quirúrgicos <textarea v-model="form.antecedentes.quirurgicos" /></label>
        <label>Farmacológicos <textarea v-model="form.antecedentes.farmacologicos" /></label>
        <label>Alérgicos <textarea v-model="form.antecedentes.alergicos" /></label>
        <label v-if="paciente.sexo === 'M'">Gineco-obstétricos <textarea v-model="form.antecedentes.gineco_obstetricos" placeholder="G_P_C_A_V_ FUM:" /></label>
        <label>Hábitos (tabaco, alcohol, actividad física) <textarea v-model="form.antecedentes.habitos" /></label>
      </div>
      <CampoTexto v-model="form.revision_sistemas" etiqueta="Revisión por sistemas" />
    </div>

    <div class="tarjeta">
      <h2>O · Objetivo</h2>
      <div class="rejilla">
        <label>TA sistólica (mmHg) <input v-model.number="form.signos_vitales.ta_sistolica" type="number" /></label>
        <label>TA diastólica (mmHg) <input v-model.number="form.signos_vitales.ta_diastolica" type="number" /></label>
        <label>Frec. cardiaca (lpm) <input v-model.number="form.signos_vitales.fc" type="number" /></label>
        <label>Frec. respiratoria (rpm) <input v-model.number="form.signos_vitales.fr" type="number" /></label>
        <label>Temperatura (°C) <input v-model.number="form.signos_vitales.temperatura" type="number" step="0.1" /></label>
        <label>SpO₂ (%) <input v-model.number="form.signos_vitales.spo2" type="number" /></label>
        <label>Peso (kg) <input v-model.number="form.signos_vitales.peso" type="number" step="0.1" /></label>
        <label>Talla (cm) <input v-model.number="form.signos_vitales.talla" type="number" /></label>
      </div>
      <p v-if="imc" class="suave">IMC calculado: <strong>{{ imc }}</strong></p>
      <CampoTexto v-model="form.examen_fisico" etiqueta="Examen físico" />
    </div>

    <div class="tarjeta">
      <h2>A · Análisis y diagnósticos (CIE-10)</h2>
      <CampoTexto v-model="form.analisis" etiqueta="Análisis" />
      <div class="rejilla-2" style="margin-top: 1rem">
        <div>
          <h3>Diagnósticos</h3>
          <SelectorCIE10 @elegir="(c: CIE10) => agregarDx(c.codigo, c.descripcion)" />
          <table style="margin-top: .5rem">
            <tbody>
              <tr v-for="(d, i) in form.diagnosticos" :key="d.codigo_cie10">
                <td>
                  <div><strong>{{ d.codigo_cie10 }}</strong> {{ d.descripcion }} <span v-if="d.sugerido_por_ia" class="etiqueta ia">IA</span></div>
                  <small class="suave">{{ i === 0 ? 'Principal' : `Relacionado ${i}` }}</small>
                </td>
                <td style="width: 170px">
                  <select v-model="d.tipo_diagnostico">
                    <option value="01">Impresión diagnóstica</option>
                    <option value="02">Confirmado nuevo</option>
                    <option value="03">Confirmado repetido</option>
                  </select>
                </td>
                <td style="width: 40px"><button type="button" class="btn sec peq" @click="form.diagnosticos.splice(i, 1)">✕</button></td>
              </tr>
            </tbody>
          </table>
          <p v-if="!form.diagnosticos.length" class="suave">Agregue al menos el diagnóstico principal.</p>
        </div>
        <div class="panel-ia">
          <div class="fila entre">
            <h3 style="margin: 0">Asistente IA CIE-10</h3>
            <button type="button" class="btn peq" :disabled="pensando" @click="sugerirIA">{{ pensando ? 'Analizando…' : 'Sugerir diagnósticos' }}</button>
          </div>
          <p class="suave">Analiza motivo, enfermedad actual, examen y análisis. Usted decide qué códigos aplicar.</p>
          <div v-for="s in sugerencias" :key="s.codigo" class="sug">
            <div class="fila entre">
              <div><strong>{{ s.codigo }}</strong> {{ s.descripcion }}</div>
              <button type="button" class="btn sec peq" @click="agregarDx(s.codigo, s.descripcion, true)">Agregar</button>
            </div>
            <div class="barra"><span :style="{ width: `${s.confianza * 100}%` }" /></div>
            <small class="suave">Confianza {{ Math.round(s.confianza * 100) }}% · {{ s.justificacion }}</small>
          </div>
          <small v-if="proveedorIA" class="suave">Motor: {{ proveedorIA === 'claude' ? 'Claude (texto anonimizado)' : 'local (sin internet)' }}</small>
        </div>
      </div>
    </div>

    <div class="tarjeta">
      <h2>P · Plan</h2>
      <CampoTexto v-model="form.plan" etiqueta="Plan de manejo, educación y recomendaciones" />

      <h3 style="margin-top: 1rem">Fórmula médica</h3>
      <table>
        <thead><tr><th>Medicamento (DCI, concentración, forma)</th><th>Dosis</th><th>Vía</th><th>Frecuencia</th><th>Días</th><th>Cant.</th><th></th></tr></thead>
        <tbody>
          <tr v-for="(r, i) in form.prescripciones" :key="i">
            <td><input v-model="r.medicamento" /></td>
            <td><input v-model="r.dosis" /></td>
            <td><select v-model="r.via"><option>oral</option><option>intravenosa</option><option>intramuscular</option><option>subcutánea</option><option>tópica</option><option>inhalada</option><option>oftálmica</option></select></td>
            <td><input v-model="r.frecuencia" /></td>
            <td style="width: 70px"><input v-model.number="r.duracion_dias" type="number" min="1" /></td>
            <td style="width: 70px"><input v-model.number="r.cantidad" type="number" min="1" /></td>
            <td><button type="button" class="btn sec peq" @click="form.prescripciones.splice(i, 1)">✕</button></td>
          </tr>
        </tbody>
      </table>
      <button type="button" class="btn sec peq" style="margin-top: .5rem"
        @click="form.prescripciones.push({ medicamento: '', dosis: '', via: 'oral', frecuencia: '', duracion_dias: 1, cantidad: 1 })">+ Medicamento</button>

      <div v-for="a in alertasFormula" :key="a.mensaje" :class="['alerta', a.severidad === 'moderada' ? 'aviso' : 'error']" style="margin-top: .5rem">{{ a.mensaje }}</div>

      <h3 style="margin-top: 1rem">Procedimientos (CUPS)</h3>
      <table>
        <thead><tr><th>Código CUPS</th><th>Descripción</th><th>Valor</th><th></th></tr></thead>
        <tbody>
          <tr v-for="(p, i) in form.procedimientos" :key="i">
            <td style="width: 120px"><input v-model="p.cod_cups" maxlength="6" /></td>
            <td><input v-model="p.descripcion" /></td>
            <td style="width: 140px"><input v-model.number="p.valor" type="number" min="0" /></td>
            <td><button type="button" class="btn sec peq" @click="form.procedimientos.splice(i, 1)">✕</button></td>
          </tr>
        </tbody>
      </table>
      <button type="button" class="btn sec peq" style="margin-top: .5rem" @click="form.procedimientos.push({ cod_cups: '', descripcion: '', valor: 0 })">+ Procedimiento</button>
    </div>

    <div class="tarjeta">
      <h2>Datos para facturación / RIPS</h2>
      <div class="rejilla">
        <label>CUPS de la consulta <input v-model="form.cod_consulta_cups" maxlength="6" /></label>
        <label>Servicio (REPS) <CatalogoSelect v-model="form.cod_servicio" tipo="servicio" /></label>
        <label>Finalidad <CatalogoSelect v-model="form.finalidad_tecnologia" tipo="finalidad" /></label>
        <label>Causa motivo de atención <CatalogoSelect v-model="form.causa_motivo_atencion" tipo="causa_atencion" /></label>
        <label>Modalidad <CatalogoSelect v-model="form.modalidad_grupo_servicio" tipo="modalidad" /></label>
        <label>Grupo de servicios <CatalogoSelect v-model="form.grupo_servicios" tipo="grupo_servicio" /></label>
        <label>N.° autorización <input v-model="form.num_autorizacion" /></label>
        <label>Valor del servicio <input v-model.number="form.valor_servicio" type="number" min="0" /></label>
        <label>Cuota moderadora / copago <input v-model.number="form.valor_pago_moderador" type="number" min="0" /></label>
      </div>
      <div v-if="form.tipo === 'urgencias'" class="rejilla" style="margin-top: .75rem">
        <label>Fecha y hora de egreso de urgencias <input v-model="form.fecha_egreso" type="datetime-local" /></label>
        <label>Condición de egreso <CatalogoSelect v-model="form.condicion_egreso" tipo="condicion_egreso" vacio="" /></label>
        <label v-if="form.condicion_egreso === '02'">Dx causa de muerte <input v-model="form.dx_causa_muerte" /></label>
      </div>
      <p class="suave">Valide los códigos contra las tablas de referencia vigentes de SISPRO.</p>
    </div>

    <div v-if="error" class="alerta error">{{ error }}</div>
    <div class="fila" style="justify-content: flex-end; margin-bottom: 2rem">
      <button class="btn sec" :disabled="guardando" @click="guardar(false)">Guardar borrador</button>
      <button v-if="!esEstudiante" class="btn" :disabled="guardando || !form.diagnosticos.length" @click="guardar(true)">
        {{ refrendo ? 'Refrendar y firmar' : 'Firmar y cerrar folio' }}</button>
    </div>
  </div>
</template>

<style scoped>
.panel-ia { background: #faf5ff; border: 1px solid #e9d5ff; border-radius: 8px; padding: .9rem; }
.sug { background: #fff; border: 1px solid var(--borde); border-radius: 8px; padding: .6rem; margin-bottom: .5rem; }
.barra { height: 5px; background: #ede9fe; border-radius: 99px; margin: .35rem 0; overflow: hidden; }
.barra span { display: block; height: 100%; background: #7c3aed; }
</style>
