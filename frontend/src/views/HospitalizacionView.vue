<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, fechaHora, mensajeError } from '../api/cliente'
import type { Paciente } from '../api/tipos'
import { useAuth } from '../stores/auth'

interface Cama { id: string; codigo: string; servicio: string; estado: string; paciente: string | null; hospitalizacion_id: string | null }
interface Hosp { id: string; paciente: { nombre_completo: string; numero_documento: string }; cama: Cama | null; fecha_ingreso: string; dx_ingreso: string; motivo: string }

const auth = useAuth()
const router = useRouter()
const camas = ref<Cama[]>([])
const censo = ref<Hosp[]>([])
const error = ref('')
const busqueda = ref('')
const pacientes = ref<Paciente[]>([])
const form = reactive({ paciente_id: '', cama_id: '', motivo: '', dx_ingreso: '', via_ingreso: '03', causa_motivo_atencion: '38',
  num_autorizacion: '', valor_estancia_dia: 0 })
const nuevaCama = reactive({ codigo: '', servicio: 'adultos' })
const servicios = computed(() => [...new Set(camas.value.map((c) => c.servicio))])
const ocupacion = computed(() => camas.value.length ? Math.round((100 * camas.value.filter((c) => c.estado === 'ocupada').length) / camas.value.length) : 0)

async function cargar() {
  ;[camas.value, censo.value] = await Promise.all([api.get('/camas').then((r) => r.data), api.get('/hospitalizaciones').then((r) => r.data)])
}
async function buscar() {
  pacientes.value = busqueda.value.length > 2 ? (await api.get('/pacientes', { params: { q: busqueda.value, limite: 8 } })).data : []
  form.paciente_id = pacientes.value[0]?.id || ''
}
async function ingresar() {
  error.value = ''
  try {
    const { data } = await api.post('/hospitalizaciones', { ...form, num_autorizacion: form.num_autorizacion || null })
    router.push(`/hospitalizacion/${data.id}`)
  } catch (e) { error.value = mensajeError(e) }
}
async function liberar(c: Cama) {
  await api.patch(`/camas/${c.id}`, null, { params: { estado: 'disponible' } })
  await cargar()
}
async function crearCama() {
  try {
    await api.post('/camas', nuevaCama)
    nuevaCama.codigo = ''
    await cargar()
  } catch (e) { error.value = mensajeError(e) }
}
onMounted(cargar)
</script>

<template>
  <div class="fila entre"><h1>Hospitalización</h1><span class="suave">Ocupación actual: <strong>{{ ocupacion }}%</strong></span></div>
  <div v-if="error" class="alerta error">{{ error }}</div>

  <div class="tarjeta">
    <h2>Mapa de camas</h2>
    <div v-for="s in servicios" :key="s" style="margin-bottom: .8rem">
      <h3 style="text-transform: capitalize">{{ s }}</h3>
      <div class="camas">
        <div v-for="c in camas.filter((x) => x.servicio === s)" :key="c.id" :class="['cama', c.estado]"
          @click="c.hospitalizacion_id ? router.push(`/hospitalizacion/${c.hospitalizacion_id}`) : (form.cama_id = c.estado === 'disponible' ? c.id : form.cama_id)">
          <strong>{{ c.codigo }}</strong>
          <small>{{ c.paciente || c.estado }}</small>
          <button v-if="c.estado === 'mantenimiento' && auth.tiene('enfermeria', 'admin')" class="btn sec peq" @click.stop="liberar(c)">Lista</button>
        </div>
      </div>
    </div>
    <form v-if="auth.tiene('admin')" class="fila" @submit.prevent="crearCama">
      <input v-model="nuevaCama.codigo" placeholder="Código nueva cama" style="max-width: 180px" required />
      <select v-model="nuevaCama.servicio" style="max-width: 180px">
        <option v-for="s in ['adultos', 'pediatria', 'obstetricia', 'uci', 'intermedios', 'observacion', 'neonatos']" :key="s">{{ s }}</option>
      </select>
      <button class="btn sec">Agregar cama</button>
    </form>
  </div>

  <div class="rejilla-2">
    <div class="tarjeta">
      <h2>Censo ({{ censo.length }} pacientes)</h2>
      <table>
        <thead><tr><th>Cama</th><th>Paciente</th><th>Ingreso</th><th>Dx</th></tr></thead>
        <tbody>
          <tr v-for="h in censo" :key="h.id" class="clic" @click="router.push(`/hospitalizacion/${h.id}`)">
            <td>{{ h.cama?.codigo }}</td><td><strong>{{ h.paciente.nombre_completo }}</strong></td><td>{{ fechaHora(h.fecha_ingreso) }}</td><td>{{ h.dx_ingreso }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <form v-if="auth.tiene('medico', 'admin')" class="tarjeta" @submit.prevent="ingresar">
      <h2>Orden de hospitalización</h2>
      <label>Paciente <input v-model="busqueda" placeholder="Documento o nombre…" @input="buscar" /></label>
      <select v-if="pacientes.length" v-model="form.paciente_id" style="margin-top: .3rem">
        <option v-for="p in pacientes" :key="p.id" :value="p.id">{{ p.nombre_completo }} · {{ p.numero_documento }}</option>
      </select>
      <div class="rejilla" style="margin-top: .6rem">
        <label>Cama
          <select v-model="form.cama_id" required>
            <option v-for="c in camas.filter((x) => x.estado === 'disponible')" :key="c.id" :value="c.id">{{ c.codigo }} ({{ c.servicio }})</option>
          </select>
        </label>
        <label>Dx de ingreso (CIE-10) <input v-model="form.dx_ingreso" placeholder="J189" required /></label>
        <label>Vía de ingreso <select v-model="form.via_ingreso"><option value="01">01 Demanda espontánea</option><option value="02">02 Consulta externa</option><option value="03">03 Urgencias</option><option value="13">13 Referido</option></select></label>
        <label>N.° autorización <input v-model="form.num_autorizacion" /></label>
        <label>Valor día estancia <input v-model.number="form.valor_estancia_dia" type="number" min="0" /></label>
      </div>
      <label style="margin-top: .6rem">Motivo <textarea v-model="form.motivo" required /></label>
      <button class="btn" style="margin-top: 1rem" :disabled="!form.paciente_id">Hospitalizar</button>
    </form>
  </div>
</template>

<style scoped>
.camas { display: grid; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); gap: .5rem; }
.cama { border-radius: 8px; padding: .6rem; display: flex; flex-direction: column; gap: .2rem; cursor: pointer; border: 1px solid var(--borde); font-size: .85rem; }
.cama.disponible { background: var(--exito-claro); }
.cama.ocupada { background: #e0f2fe; }
.cama.mantenimiento { background: var(--aviso-claro); }
</style>
