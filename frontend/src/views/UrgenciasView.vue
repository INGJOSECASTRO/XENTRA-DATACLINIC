<script setup lang="ts">
import { onMounted, onUnmounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, fechaHora, mensajeError } from '../api/cliente'
import type { Paciente } from '../api/tipos'
import { useAuth } from '../stores/auth'

interface T { id: string; paciente: { id: string; nombre_completo: string; numero_documento: string }; nivel: number
  nivel_sugerido: number; motivo: string; estado: string; llegada: string; minutos_espera: number; tiempo_maximo: number
  vencido: boolean; razones: string[] }

const auth = useAuth()
const router = useRouter()
const cola = ref<T[]>([])
const busqueda = ref('')
const pacientes = ref<Paciente[]>([])
const sugerencia = ref<{ nivel: number; descripcion: string; razones: string[] } | null>(null)
const error = ref('')
const form = reactive({ paciente_id: '', motivo: '', nivel: null as number | null, observaciones: '',
  signos_vitales: { ta_sistolica: null, ta_diastolica: null, fc: null, fr: null, temperatura: null, spo2: null, glasgow: null } as Record<string, number | null> })
const colores: Record<number, string> = { 1: '#b42318', 2: '#f97316', 3: '#eab308', 4: '#16a34a', 5: '#2563eb' }
let refresco: ReturnType<typeof setInterval>

const signos = () => Object.fromEntries(Object.entries(form.signos_vitales).filter(([, v]) => v !== null && v !== undefined && (v as unknown) !== ''))
async function cargar() { cola.value = (await api.get('/urgencias/cola')).data }
async function buscar() {
  pacientes.value = busqueda.value.length > 2 ? (await api.get('/pacientes', { params: { q: busqueda.value, limite: 8 } })).data : []
  form.paciente_id = pacientes.value[0]?.id || ''
}
async function sugerir() {
  if (!form.paciente_id || form.motivo.length < 3) return
  sugerencia.value = (await api.post('/urgencias/triage/sugerir', { ...form, signos_vitales: signos() })).data
}
async function clasificar() {
  error.value = ''
  try {
    await api.post('/urgencias/triage', { ...form, nivel: form.nivel || null, signos_vitales: signos() })
    Object.assign(form, { paciente_id: '', motivo: '', nivel: null, observaciones: '' })
    sugerencia.value = null
    busqueda.value = ''
    pacientes.value = []
    await cargar()
  } catch (e) { error.value = mensajeError(e) }
}
async function atender(t: T) {
  await api.post(`/urgencias/triage/${t.id}/atender`)
  router.push({ path: `/pacientes/${t.paciente.id}/atencion`, query: { tipo: 'urgencias', triage: t.id } })
}
async function finalizar(t: T) {
  await api.post(`/urgencias/triage/${t.id}/finalizar`)
  await cargar()
}
onMounted(() => { cargar(); refresco = setInterval(cargar, 60_000) })
onUnmounted(() => clearInterval(refresco))
</script>

<template>
  <h1>Urgencias</h1>
  <div v-if="error" class="alerta error">{{ error }}</div>
  <div class="rejilla-2">
    <div class="tarjeta">
      <h2>Sala de espera ({{ cola.filter((c) => c.estado === 'en_espera').length }})</h2>
      <table>
        <tbody>
          <tr v-for="t in cola" :key="t.id" :class="{ vencido: t.vencido }">
            <td style="width: 54px"><span class="nivel" :style="{ background: colores[t.nivel] }">{{ ['I', 'II', 'III', 'IV', 'V'][t.nivel - 1] }}</span></td>
            <td>
              <strong>{{ t.paciente.nombre_completo }}</strong> <small class="suave">{{ t.paciente.numero_documento }}</small><br />
              <small>{{ t.motivo }}</small><br />
              <small class="suave">Llegó {{ fechaHora(t.llegada) }} · espera {{ t.minutos_espera }} min (máx. {{ t.tiempo_maximo }})</small>
              <div v-if="t.vencido" class="etiqueta borrador">Tiempo máximo superado</div>
            </td>
            <td style="width: 120px">
              <template v-if="auth.tiene('medico', 'enfermeria', 'admin')">
                <button v-if="t.estado === 'en_espera'" class="btn peq" @click="atender(t)">Atender</button>
                <button v-else class="btn sec peq" @click="finalizar(t)">Finalizar</button>
              </template>
            </td>
          </tr>
          <tr v-if="!cola.length"><td class="suave">No hay pacientes en espera.</td></tr>
        </tbody>
      </table>
    </div>

    <form v-if="auth.tiene('medico', 'enfermeria', 'admin')" class="tarjeta" @submit.prevent="clasificar">
      <h2>Clasificación (triage – Res. 5596 de 2015)</h2>
      <label>Paciente <input v-model="busqueda" placeholder="Documento o nombre…" @input="buscar" /></label>
      <select v-if="pacientes.length" v-model="form.paciente_id" style="margin-top: .3rem">
        <option v-for="p in pacientes" :key="p.id" :value="p.id">{{ p.nombre_completo }} · {{ p.numero_documento }}</option>
      </select>
      <p v-if="busqueda.length > 2 && !pacientes.length" class="suave">¿No existe? Regístrelo en <RouterLink to="/pacientes">Pacientes</RouterLink>.</p>
      <label style="margin-top: .6rem">Motivo de consulta <textarea v-model="form.motivo" @blur="sugerir" /></label>
      <div class="rejilla" style="margin-top: .6rem">
        <label>TAS <input v-model.number="form.signos_vitales.ta_sistolica" type="number" @blur="sugerir" /></label>
        <label>TAD <input v-model.number="form.signos_vitales.ta_diastolica" type="number" @blur="sugerir" /></label>
        <label>FC <input v-model.number="form.signos_vitales.fc" type="number" @blur="sugerir" /></label>
        <label>FR <input v-model.number="form.signos_vitales.fr" type="number" @blur="sugerir" /></label>
        <label>T° <input v-model.number="form.signos_vitales.temperatura" type="number" step="0.1" @blur="sugerir" /></label>
        <label>SpO₂ <input v-model.number="form.signos_vitales.spo2" type="number" @blur="sugerir" /></label>
        <label>Glasgow <input v-model.number="form.signos_vitales.glasgow" type="number" min="3" max="15" @blur="sugerir" /></label>
      </div>
      <div v-if="sugerencia" class="alerta aviso" style="margin-top: .75rem">
        <strong>Sugerido: {{ sugerencia.descripcion }}</strong>
        <ul><li v-for="r in sugerencia.razones" :key="r">{{ r }}</li></ul>
      </div>
      <label>Nivel asignado (decisión del profesional)
        <select v-model="form.nivel">
          <option :value="null">Usar el sugerido</option>
          <option v-for="n in 5" :key="n" :value="n">Triage {{ ['I', 'II', 'III', 'IV', 'V'][n - 1] }}</option>
        </select>
      </label>
      <label style="margin-top: .6rem">Observaciones <input v-model="form.observaciones" /></label>
      <button class="btn" style="margin-top: 1rem" :disabled="!form.paciente_id || form.motivo.length < 3">Clasificar</button>
    </form>
  </div>
</template>

<style scoped>
.nivel { display: inline-grid; place-items: center; width: 40px; height: 40px; border-radius: 8px; color: #fff; font-weight: 800; }
tr.vencido td { background: #fff7ed; }
</style>
