<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, fechaHora, mensajeError } from '../api/cliente'
import { useAuth } from '../stores/auth'

interface R { analito: string; valor: string; unidad: string | null; referencia: string | null; anormal?: boolean | null }
interface O { id: string; paciente: { nombre_completo: string; numero_documento: string }; tipo: string; cod_cups: string
  descripcion: string; prioridad: string; indicaciones: string | null; estado: string; fecha: string; resultados: R[] | null; informe: string | null }

const auth = useAuth()
const estado = ref('ordenada')
const ordenes = ref<O[]>([])
const abierta = ref<string | null>(null)
const filas = ref<R[]>([])
const informe = ref('')
const error = ref('')

async function cargar() { ordenes.value = (await api.get('/ordenes-servicio', { params: { estado: estado.value || undefined } })).data }
function abrir(o: O) {
  abierta.value = o.id
  filas.value = o.resultados?.length ? o.resultados.map((r) => ({ ...r })) : [{ analito: o.descripcion, valor: '', unidad: '', referencia: '' }]
  informe.value = o.informe || ''
}
async function accion(fn: () => Promise<unknown>) {
  error.value = ''
  try { await fn(); await cargar() } catch (e) { error.value = mensajeError(e) }
}
const tomar = (o: O) => accion(() => api.post(`/ordenes-servicio/${o.id}/toma`))
const guardar = (o: O) => accion(async () => {
  await api.post(`/ordenes-servicio/${o.id}/resultado`, { resultados: filas.value.filter((f) => f.analito && f.valor), informe: informe.value || null })
  abierta.value = null
})
const validar = (o: O) => confirm('Al validar, el resultado queda sellado. ¿Continuar?') && accion(() => api.post(`/ordenes-servicio/${o.id}/validar`))
onMounted(cargar)
</script>

<template>
  <div class="fila entre">
    <h1>Laboratorio clínico e imágenes</h1>
    <select v-model="estado" style="max-width: 220px" @change="cargar">
      <option value="ordenada">Pendientes de toma</option><option value="tomada">Pendientes de resultado</option>
      <option value="resultado">Pendientes de validar</option><option value="validada">Validados</option><option value="">Todas</option>
    </select>
  </div>
  <div v-if="error" class="alerta error">{{ error }}</div>
  <div class="tarjeta">
    <table>
      <tbody>
        <template v-for="o in ordenes" :key="o.id">
          <tr>
            <td><span v-if="o.prioridad === 'urgente'" class="etiqueta borrador">URGENTE</span> <strong>{{ o.cod_cups }}</strong> {{ o.descripcion }}<br />
              <small class="suave">{{ o.tipo }} · {{ fechaHora(o.fecha) }} · {{ o.indicaciones }}</small></td>
            <td>{{ o.paciente.nombre_completo }}<br /><small class="suave">{{ o.paciente.numero_documento }}</small></td>
            <td><span :class="['etiqueta', o.estado === 'validada' ? 'firmada' : 'borrador']">{{ o.estado }}</span></td>
            <td style="width: 200px">
              <button v-if="o.estado === 'ordenada'" class="btn peq" @click="tomar(o)">Toma realizada</button>
              <button v-if="['tomada', 'resultado'].includes(o.estado) && auth.tiene('laboratorio', 'medico', 'admin')" class="btn sec peq" @click="abrir(o)">Resultado</button>
              <button v-if="o.estado === 'resultado' && auth.tiene('laboratorio', 'medico', 'admin')" class="btn peq" @click="validar(o)">Validar</button>
            </td>
          </tr>
          <tr v-if="o.resultados && abierta !== o.id">
            <td colspan="4"><small v-for="r in o.resultados" :key="r.analito" :class="{ anormal: r.anormal }" style="margin-right: 1rem">{{ r.analito }}: <strong>{{ r.valor }}</strong> {{ r.unidad }} ({{ r.referencia }})</small>
              <div v-if="o.informe" class="suave">{{ o.informe }}</div></td>
          </tr>
          <tr v-if="abierta === o.id">
            <td colspan="4">
              <table>
                <thead><tr><th>Analito / estudio</th><th>Valor</th><th>Unidad</th><th>Referencia (mín - máx)</th></tr></thead>
                <tbody>
                  <tr v-for="(f, i) in filas" :key="i">
                    <td><input v-model="f.analito" /></td><td><input v-model="f.valor" /></td><td><input v-model="f.unidad" /></td><td><input v-model="f.referencia" placeholder="70 - 100" /></td>
                  </tr>
                </tbody>
              </table>
              <button class="btn sec peq" @click="filas.push({ analito: '', valor: '', unidad: '', referencia: '' })">+ Fila</button>
              <label style="margin-top: .5rem">Informe / lectura <textarea v-model="informe" /></label>
              <button class="btn" style="margin-top: .5rem" @click="guardar(o)">Guardar resultado</button>
            </td>
          </tr>
        </template>
        <tr v-if="!ordenes.length"><td class="suave">Sin órdenes en este estado.</td></tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.anormal { color: var(--peligro); }
</style>
