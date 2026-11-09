<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { abrirArchivo, api, fechaHora, mensajeError } from '../api/cliente'
import CampoTexto from '../components/CampoTexto.vue'
import { useAuth } from '../stores/auth'

interface Orden { id: string; fecha: string; tipo: string; descripcion: string; dosis: string | null; via: string | null
  frecuencia: string | null; estado: string; administraciones: { id: string; fecha: string; estado: string; dosis_administrada: string | null; observacion: string | null }[] }
interface H { id: string; estado: string; paciente: { id: string; nombre_completo: string; numero_documento: string; alergias: string | null }
  cama: { codigo: string; servicio: string } | null; medico: { nombre_completo: string }; fecha_ingreso: string; motivo: string
  dx_ingreso: string; fecha_egreso: string | null; dx_egreso: string | null; epicrisis: string | null; hash_epicrisis: string | null
  evoluciones: { id: string; fecha: string; tipo: string; texto: string; signos_vitales: Record<string, number> | null; autor: { nombre_completo: string } }[]
  ordenes: Orden[]; balances: { id: string; fecha: string; tipo: string; via: string; cantidad_ml: number }[]
  balance_24h: { ingresos_ml: number; egresos_ml: number; balance_ml: number }; alertas: string[] }

const auth = useAuth()
const route = useRoute()
const h = ref<H | null>(null)
const pestana = ref('evoluciones')
const error = ref('')
const alertasOrden = ref<{ mensaje: string }[]>([])
const productos = ref<{ id: string; nombre: string; stock: number }[]>([])
const evo = reactive({ tipo: auth.tiene('medico', 'admin') ? 'medica' : 'enfermeria', texto: '',
  signos_vitales: { ta_sistolica: null, ta_diastolica: null, fc: null, fr: null, temperatura: null, spo2: null } as Record<string, number | null> })
const orden = reactive({ tipo: 'medicamento', descripcion: '', producto_id: '', dosis: '', via: 'intravenosa', frecuencia: '' })
const bal = reactive({ tipo: 'ingreso', via: 'intravenosa', cantidad_ml: 0 })
const egreso = reactive({ condicion_egreso: '01', dx_egreso: '', dx_relacionados: '', dx_causa_muerte: '', epicrisis: '' })

async function cargar() { h.value = (await api.get(`/hospitalizaciones/${route.params.id}`)).data }
async function accion(fn: () => Promise<unknown>) {
  error.value = ''
  try { await fn(); await cargar() } catch (e) { error.value = mensajeError(e) }
}
const limpio = (o: Record<string, unknown>) => Object.fromEntries(Object.entries(o).filter(([, v]) => v !== null && v !== ''))

function evolucionar() {
  return accion(async () => {
    await api.post(`/hospitalizaciones/${h.value!.id}/evoluciones`, { tipo: evo.tipo, texto: evo.texto, signos_vitales: limpio(evo.signos_vitales) })
    evo.texto = ''
  })
}
async function ordenar(confirmar = false) {
  error.value = ''
  try {
    await api.post(`/hospitalizaciones/${h.value!.id}/ordenes`, { ...orden, producto_id: orden.producto_id || null, confirmar_alertas: confirmar })
    alertasOrden.value = []
    orden.descripcion = orden.dosis = orden.frecuencia = orden.producto_id = ''
    await cargar()
  } catch (e) {
    const det = (e as { response?: { status: number; data: { detail: { alertas?: { mensaje: string }[] } } } }).response
    if (det?.status === 409 && det.data.detail.alertas) alertasOrden.value = det.data.detail.alertas
    else error.value = mensajeError(e)
  }
}
const administrar = (o: Orden, estado: string) => accion(async () => {
  const observacion = estado === 'omitido' ? prompt('Motivo de la omisión') : null
  if (estado === 'omitido' && !observacion) return
  await api.post(`/ordenes-medicas/${o.id}/administrar`, { estado, dosis_administrada: o.dosis, observacion })
})
const suspender = (o: Orden) => accion(() => api.post(`/ordenes-medicas/${o.id}/suspender`))
const balance = () => accion(() => api.post(`/hospitalizaciones/${h.value!.id}/balance`, bal))
function egresar() {
  if (!confirm('El egreso sella la epicrisis y cierra la hospitalización. ¿Continuar?')) return
  return accion(() => api.post(`/hospitalizaciones/${h.value!.id}/egreso`, {
    condicion_egreso: egreso.condicion_egreso, dx_egreso: egreso.dx_egreso, epicrisis: egreso.epicrisis,
    dx_causa_muerte: egreso.dx_causa_muerte || null,
    dx_relacionados_egreso: egreso.dx_relacionados.split(',').map((x) => x.trim()).filter(Boolean),
  }))
}
onMounted(async () => {
  await cargar()
  if (auth.tiene('medico', 'admin')) productos.value = (await api.get('/farmacia/productos')).data
})
</script>

<template>
  <div v-if="h">
    <div class="fila entre">
      <div>
        <h1 style="margin: 0">{{ h.paciente.nombre_completo }} · Cama {{ h.cama?.codigo }}</h1>
        <p class="suave">{{ h.paciente.numero_documento }} · Ingreso {{ fechaHora(h.fecha_ingreso) }} · Dx {{ h.dx_ingreso }} · {{ h.medico.nombre_completo }}</p>
      </div>
      <div class="fila">
        <span :class="['etiqueta', h.estado === 'activa' ? 'borrador' : 'firmada']">{{ h.estado }}</span>
        <button v-if="h.hash_epicrisis" class="btn sec" @click="abrirArchivo(`/hospitalizaciones/${h.id}/epicrisis.pdf`)">Epicrisis PDF</button>
        <RouterLink class="btn sec" :to="`/pacientes/${h.paciente.id}`">Paciente</RouterLink>
      </div>
    </div>
    <div v-if="h.paciente.alergias" class="alerta error"><strong>ALERGIAS:</strong> {{ h.paciente.alergias }}</div>
    <div v-for="a in h.alertas" :key="a" class="alerta aviso">{{ a }}</div>
    <div v-if="error" class="alerta error">{{ error }}</div>

    <div class="fila pestanas">
      <button v-for="p in ['evoluciones', 'ordenes', 'balance', 'egreso']" :key="p" :class="['btn peq', pestana === p ? '' : 'sec']" @click="pestana = p">
        {{ { evoluciones: 'Evoluciones y notas', ordenes: 'Órdenes y kárdex', balance: 'Balance de líquidos', egreso: 'Egreso / epicrisis' }[p] }}
      </button>
    </div>

    <div v-if="pestana === 'evoluciones'" class="tarjeta">
      <form v-if="h.estado === 'activa'" @submit.prevent="evolucionar">
        <div class="fila">
          <select v-model="evo.tipo" style="max-width: 220px">
            <option v-if="auth.tiene('medico', 'admin')" value="medica">Evolución médica</option><option value="enfermeria">Nota de enfermería</option>
          </select>
        </div>
        <div class="rejilla" style="margin-top: .5rem">
          <label v-for="(etq, k) in { ta_sistolica: 'TAS', ta_diastolica: 'TAD', fc: 'FC', fr: 'FR', temperatura: 'T°', spo2: 'SpO₂' }" :key="k">{{ etq }}
            <input v-model.number="evo.signos_vitales[k]" type="number" step="0.1" />
          </label>
        </div>
        <CampoTexto v-model="evo.texto" etiqueta="Nota (subjetivo, objetivo, análisis, plan)" />
        <button class="btn" style="margin-top: .5rem" :disabled="evo.texto.length < 3">Registrar</button>
      </form>
      <div v-for="e in [...h.evoluciones].reverse()" :key="e.id" class="nota">
        <div class="suave"><strong>{{ e.tipo === 'medica' ? 'Evolución médica' : 'Nota de enfermería' }}</strong> · {{ fechaHora(e.fecha) }} · {{ e.autor.nombre_completo }}</div>
        <div v-if="e.signos_vitales" class="suave">{{ Object.entries(e.signos_vitales).map(([k, v]) => `${k}: ${v}`).join(' · ') }}</div>
        <p style="white-space: pre-wrap; margin: .3rem 0">{{ e.texto }}</p>
      </div>
    </div>

    <div v-if="pestana === 'ordenes'" class="tarjeta">
      <form v-if="h.estado === 'activa' && auth.tiene('medico', 'admin')" @submit.prevent="ordenar(false)">
        <div class="rejilla">
          <label>Tipo
            <select v-model="orden.tipo"><option v-for="t in ['medicamento', 'dieta', 'cuidado', 'laboratorio', 'imagen', 'procedimiento', 'interconsulta']" :key="t">{{ t }}</option></select>
          </label>
          <label v-if="orden.tipo === 'medicamento'">Producto (inventario)
            <select v-model="orden.producto_id"><option value="">— texto libre —</option><option v-for="p in productos" :key="p.id" :value="p.id">{{ p.nombre }} (stock {{ p.stock }})</option></select>
          </label>
          <label>Descripción <input v-model="orden.descripcion" required /></label>
          <template v-if="orden.tipo === 'medicamento'">
            <label>Dosis <input v-model="orden.dosis" /></label>
            <label>Vía <input v-model="orden.via" /></label>
            <label>Frecuencia <input v-model="orden.frecuencia" /></label>
          </template>
        </div>
        <div v-if="alertasOrden.length" class="alerta error" style="margin-top: .5rem">
          <div v-for="a in alertasOrden" :key="a.mensaje">{{ a.mensaje }}</div>
          <button type="button" class="btn peligro peq" style="margin-top: .4rem" @click="ordenar(true)">Ordenar de todas formas (queda registrado)</button>
        </div>
        <button class="btn" style="margin-top: .6rem">Agregar orden</button>
      </form>
      <table style="margin-top: 1rem">
        <thead><tr><th>Orden</th><th>Estado</th><th>Kárdex</th><th></th></tr></thead>
        <tbody>
          <tr v-for="o in h.ordenes" :key="o.id">
            <td><strong>{{ o.tipo }}</strong>: {{ o.descripcion }} <span v-if="o.dosis">· {{ o.dosis }} {{ o.via }} {{ o.frecuencia }}</span><br /><small class="suave">{{ fechaHora(o.fecha) }}</small></td>
            <td><span :class="['etiqueta', o.estado === 'activa' ? 'borrador' : 'firmada']">{{ o.estado }}</span></td>
            <td><small v-for="ad in o.administraciones" :key="ad.id" style="display: block">{{ fechaHora(ad.fecha) }} · {{ ad.estado }} {{ ad.observacion || '' }}</small></td>
            <td>
              <template v-if="o.estado === 'activa' && h.estado === 'activa'">
                <template v-if="o.tipo === 'medicamento' && auth.tiene('enfermeria', 'medico', 'admin')">
                  <button class="btn peq" @click="administrar(o, 'administrado')">Administrado</button>
                  <button class="btn sec peq" @click="administrar(o, 'omitido')">Omitido</button>
                </template>
                <button v-if="auth.tiene('medico', 'admin')" class="btn sec peq" @click="suspender(o)">Suspender</button>
              </template>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="pestana === 'balance'" class="tarjeta">
      <div class="rejilla">
        <div><div class="suave">Ingresos 24 h</div><div class="kpi">{{ h.balance_24h.ingresos_ml }} mL</div></div>
        <div><div class="suave">Egresos 24 h</div><div class="kpi">{{ h.balance_24h.egresos_ml }} mL</div></div>
        <div><div class="suave">Balance 24 h</div><div class="kpi">{{ h.balance_24h.balance_ml }} mL</div></div>
      </div>
      <form v-if="h.estado === 'activa'" class="fila" style="margin-top: 1rem" @submit.prevent="balance">
        <select v-model="bal.tipo" style="max-width: 130px"><option value="ingreso">Ingreso</option><option value="egreso">Egreso</option></select>
        <select v-model="bal.via" style="max-width: 180px">
          <option v-for="v in bal.tipo === 'ingreso' ? ['oral', 'intravenosa', 'sonda'] : ['orina', 'drenaje', 'vómito', 'deposición', 'sangrado']" :key="v">{{ v }}</option>
        </select>
        <input v-model.number="bal.cantidad_ml" type="number" min="1" placeholder="mL" style="max-width: 120px" />
        <button class="btn">Registrar</button>
      </form>
      <table style="margin-top: 1rem">
        <tbody><tr v-for="b in [...h.balances].reverse()" :key="b.id"><td>{{ fechaHora(b.fecha) }}</td><td>{{ b.tipo }}</td><td>{{ b.via }}</td><td>{{ b.cantidad_ml }} mL</td></tr></tbody>
      </table>
    </div>

    <div v-if="pestana === 'egreso'" class="tarjeta">
      <template v-if="h.estado === 'egresada'">
        <p><strong>Egreso:</strong> {{ fechaHora(h.fecha_egreso) }} · Dx {{ h.dx_egreso }}</p>
        <p style="white-space: pre-wrap">{{ h.epicrisis }}</p>
        <p class="mono suave">SHA-256: {{ h.hash_epicrisis }}</p>
      </template>
      <form v-else-if="auth.tiene('medico', 'admin')" @submit.prevent="egresar">
        <div class="rejilla">
          <label>Condición de egreso
            <select v-model="egreso.condicion_egreso">
              <option value="01">01 Domicilio</option><option value="02">02 Fallecido</option><option value="03">03 Otro servicio</option>
              <option value="04">04 Referido a otra institución</option><option value="05">05 Contrarreferido</option>
            </select>
          </label>
          <label>Dx de egreso <input v-model="egreso.dx_egreso" required /></label>
          <label>Dx relacionados (coma) <input v-model="egreso.dx_relacionados" placeholder="I10X, E119" /></label>
          <label v-if="egreso.condicion_egreso === '02'">Dx causa de muerte <input v-model="egreso.dx_causa_muerte" required /></label>
        </div>
        <CampoTexto v-model="egreso.epicrisis" etiqueta="Epicrisis (resumen de la estancia, tratamiento, condición de salida, recomendaciones)" />
        <button class="btn" style="margin-top: .6rem" :disabled="egreso.epicrisis.length < 20">Dar egreso y firmar epicrisis</button>
      </form>
    </div>
  </div>
</template>

<style scoped>
.pestanas { margin-bottom: 1rem; gap: .4rem; }
.nota { border-top: 1px solid var(--borde); padding-top: .6rem; margin-top: .6rem; }
</style>
