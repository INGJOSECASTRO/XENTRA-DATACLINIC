<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api, mensajeError } from '../api/cliente'
import type { Paciente, Usuario } from '../api/tipos'
import { useAuth } from '../stores/auth'

interface Cita {
  id: string; inicio: string; duracion_min: number; estado: string; modalidad: string; motivo: string | null
  sala_virtual: string | null; cod_cups: string; atencion_id: string | null
  paciente: { id: string; nombre_completo: string; numero_documento: string; telefono: string | null }
  profesional: { id: string; nombre_completo: string }
}

const auth = useAuth()
const router = useRouter()
const hoy = new Date().toLocaleDateString('en-CA')
const fecha = ref(hoy)
const profesionalId = ref('')
const citas = ref<Cita[]>([])
const profesionales = ref<Usuario[]>([])
const libres = ref<string[]>([])
const error = ref('')
const busqueda = ref('')
const pacientes = ref<Paciente[]>([])
const form = reactive({ paciente_id: '', profesional_id: '', inicio: '', duracion_min: 20, cod_cups: '890201',
  modalidad: 'presencial', motivo: '', num_autorizacion: '' })

const siguiente: Record<string, string[]> = {
  programada: ['confirmada', 'en_sala', 'cancelada', 'no_asistio'], confirmada: ['en_sala', 'cancelada', 'no_asistio'],
  en_sala: ['no_asistio'],
}
const textoEstado: Record<string, string> = { confirmada: 'Confirmar', en_sala: 'Llegó (en sala)', cancelada: 'Cancelar', no_asistio: 'No asistió' }
const hora = (f: string) => new Date(f).toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit' })
const puedeAtender = computed(() => auth.tiene('medico', 'enfermeria', 'admin'))

async function cargar() {
  citas.value = (await api.get('/citas', { params: { desde: fecha.value, profesional_id: profesionalId.value || undefined } })).data
}
async function cargarLibres() {
  libres.value = []
  if (!form.profesional_id) return
  libres.value = (await api.get('/citas/disponibilidad', { params: { profesional_id: form.profesional_id, fecha: fecha.value,
    duracion: form.duracion_min } })).data.libres
}
async function buscarPacientes() {
  pacientes.value = busqueda.value.length > 2 ? (await api.get('/pacientes', { params: { q: busqueda.value, limite: 10 } })).data : []
  form.paciente_id = pacientes.value[0]?.id || ''
}
async function asignar() {
  error.value = ''
  try {
    await api.post('/citas', { ...form, num_autorizacion: form.num_autorizacion || null, motivo: form.motivo || null })
    form.inicio = ''
    await Promise.all([cargar(), cargarLibres()])
  } catch (e) {
    error.value = mensajeError(e)
  }
}
async function estado(c: Cita, nuevo: string) {
  const motivo = nuevo === 'cancelada' ? prompt('Motivo de la cancelación') : null
  if (nuevo === 'cancelada' && !motivo) return
  try {
    await api.patch(`/citas/${c.id}/estado`, { estado: nuevo, motivo_cancelacion: motivo })
    await cargar()
  } catch (e) {
    error.value = mensajeError(e)
  }
}
async function recordatorios() {
  const { data } = await api.post('/citas/recordatorios')
  alert(`Recordatorios enviados para mañana: ${data.total}`)
}

watch(fecha, () => { cargar(); cargarLibres() })
watch(profesionalId, cargar)
watch(() => [form.profesional_id, form.duracion_min], cargarLibres)
onMounted(async () => {
  profesionales.value = (await api.get('/auth/usuarios')).data.filter((u: Usuario) => ['medico', 'enfermeria'].includes(u.rol))
  if (auth.tiene('medico', 'enfermeria')) profesionalId.value = form.profesional_id = auth.usuario!.id
  await cargar()
})
</script>

<template>
  <div class="fila entre">
    <h1>Agenda</h1>
    <div class="fila">
      <input v-model="fecha" type="date" style="max-width: 170px" />
      <select v-model="profesionalId" style="max-width: 240px">
        <option value="">Todos los profesionales</option>
        <option v-for="p in profesionales" :key="p.id" :value="p.id">{{ p.nombres }} {{ p.apellidos }}</option>
      </select>
      <button v-if="auth.tiene('admisiones', 'admin')" class="btn sec" @click="recordatorios">Enviar recordatorios</button>
    </div>
  </div>
  <div v-if="error" class="alerta error">{{ error }}</div>

  <div class="rejilla-2">
    <div class="tarjeta">
      <h2>Citas del día</h2>
      <table>
        <tbody>
          <tr v-for="c in citas" :key="c.id">
            <td style="width: 70px"><strong>{{ hora(c.inicio) }}</strong><br /><small class="suave">{{ c.duracion_min }} min</small></td>
            <td>
              <strong>{{ c.paciente.nombre_completo }}</strong> <small class="suave">{{ c.paciente.numero_documento }}</small><br />
              <small>{{ c.profesional.nombre_completo }} · {{ c.motivo || c.cod_cups }}</small>
              <span v-if="c.modalidad === 'telemedicina'" class="etiqueta ia">Telemedicina</span>
            </td>
            <td style="width: 210px">
              <span :class="['etiqueta', ['atendida', 'confirmada'].includes(c.estado) ? 'firmada' : 'borrador']">{{ c.estado.replace('_', ' ') }}</span>
              <div class="fila" style="margin-top: .3rem; gap: .3rem">
                <button v-for="s in siguiente[c.estado] || []" :key="s" class="btn sec peq" @click="estado(c, s)">{{ textoEstado[s] }}</button>
                <a v-if="c.sala_virtual && c.estado !== 'cancelada'" class="btn sec peq" :href="c.sala_virtual" target="_blank" rel="noopener">Sala virtual</a>
                <button v-if="puedeAtender && ['en_sala', 'confirmada', 'programada'].includes(c.estado) && !c.atencion_id" class="btn peq"
                  @click="router.push({ path: `/pacientes/${c.paciente.id}/atencion`, query: { cita: c.id } })">Atender</button>
                <RouterLink v-if="c.atencion_id" class="btn sec peq" :to="`/atenciones/${c.atencion_id}`">Ver atención</RouterLink>
              </div>
            </td>
          </tr>
          <tr v-if="!citas.length"><td class="suave">No hay citas.</td></tr>
        </tbody>
      </table>
    </div>

    <form v-if="auth.tiene('admisiones', 'admin', 'medico', 'enfermeria')" class="tarjeta" @submit.prevent="asignar">
      <h2>Asignar cita</h2>
      <label>Paciente
        <input v-model="busqueda" placeholder="Documento o nombre…" @input="buscarPacientes" />
      </label>
      <select v-if="pacientes.length" v-model="form.paciente_id" style="margin-top: .3rem">
        <option v-for="p in pacientes" :key="p.id" :value="p.id">{{ p.nombre_completo }} · {{ p.numero_documento }}</option>
      </select>
      <div class="rejilla" style="margin-top: .6rem">
        <label>Profesional
          <select v-model="form.profesional_id" required>
            <option v-for="p in profesionales" :key="p.id" :value="p.id">{{ p.nombres }} {{ p.apellidos }}</option>
          </select>
        </label>
        <label>Duración (min) <input v-model.number="form.duracion_min" type="number" min="5" step="5" /></label>
        <label>Modalidad
          <select v-model="form.modalidad"><option value="presencial">Presencial</option><option value="telemedicina">Telemedicina</option></select>
        </label>
        <label>CUPS <input v-model="form.cod_cups" maxlength="6" /></label>
        <label>N.° autorización <input v-model="form.num_autorizacion" /></label>
      </div>
      <label style="margin-top: .6rem">Motivo <input v-model="form.motivo" /></label>
      <h3 style="margin-top: 1rem">Horarios libres ({{ fecha }})</h3>
      <div class="fila" style="gap: .35rem">
        <button v-for="l in libres" :key="l" type="button" :class="['btn peq', form.inicio === l ? '' : 'sec']" @click="form.inicio = l">{{ hora(l) }}</button>
        <span v-if="!libres.length" class="suave">Seleccione profesional y fecha.</span>
      </div>
      <button class="btn" style="margin-top: 1rem" :disabled="!form.paciente_id || !form.inicio">Asignar cita</button>
    </form>
  </div>
</template>
