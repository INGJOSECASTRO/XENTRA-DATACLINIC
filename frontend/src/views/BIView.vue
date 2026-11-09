<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { api, mensajeError } from '../api/cliente'
import Grafico from '../components/Grafico.vue'
import { useAuth } from '../stores/auth'

interface Campo { clave: string; etiqueta: string }
interface Dataset { clave: string; nombre: string; dimensiones: Campo[]; medidas: Campo[] }
interface Resultado { titulo: string; columnas: { clave: string; etiqueta: string; tipo: string }[]; filas: Record<string, unknown>[]
  total_grupos: number; registros_analizados: number; grafico: string }
interface Guardado { id: string; nombre: string; descripcion: string | null; definicion: typeof consulta; propio: boolean }

const auth = useAuth()
const datasets = ref<Dataset[]>([])
const guardados = ref<Guardado[]>([])
const resultado = ref<Resultado | null>(null)
const error = ref('')
const cargando = ref(false)
const hoy = new Date().toLocaleDateString('en-CA')
const consulta = reactive({ dataset: '', dimensiones: [] as string[], medidas: ['conteo'] as string[],
  desde: new Date(Date.now() - 90 * 86400000).toLocaleDateString('en-CA'), hasta: hoy,
  filtros: {} as Record<string, string>, grafico: 'barras', limite: 500 })
const filtro = reactive({ dimension: '', valor: '' })
const actual = computed(() => datasets.value.find((d) => d.clave === consulta.dataset))
const etiquetaFila = (f: Record<string, unknown>) => consulta.dimensiones.map((d) => String(f[d] ?? '(sin dato)')).join(' · ') || 'Total'

// Reportes sugeridos según la lógica del negocio de la salud
const sugeridos = [
  { nombre: 'Morbilidad por capítulo CIE-10 y curso de vida', d: { dataset: 'atenciones', dimensiones: ['capitulo_cie10', 'curso_vida'], medidas: ['conteo', 'pacientes'] } },
  { nombre: 'Producción por profesional (mes a mes)', d: { dataset: 'atenciones', dimensiones: ['mes', 'profesional'], medidas: ['conteo', 'valor'] } },
  { nombre: 'Atenciones por EPS y régimen', d: { dataset: 'atenciones', dimensiones: ['eps', 'regimen'], medidas: ['conteo', 'valor'] } },
  { nombre: 'Oportunidad e inasistencia por profesional', d: { dataset: 'citas', dimensiones: ['profesional'], medidas: ['oportunidad', 'inasistencia', 'conteo'] } },
  { nombre: 'Facturación por pagador y estado', d: { dataset: 'facturacion', dimensiones: ['pagador', 'estado'], medidas: ['total', 'conteo'] } },
  { nombre: 'Estancia y mortalidad por servicio', d: { dataset: 'hospitalizacion', dimensiones: ['servicio'], medidas: ['estancia', 'mortalidad', 'conteo'] } },
  { nombre: 'Demanda de urgencias por hora y nivel', d: { dataset: 'urgencias', dimensiones: ['hora'], medidas: ['conteo', 'espera'] } },
  { nombre: 'Consumo de medicamentos (valor)', d: { dataset: 'farmacia', dimensiones: ['producto'], medidas: ['valor', 'unidades'] } },
]
const sugeridosDisponibles = computed(() => sugeridos.filter((s) => datasets.value.some((d) => d.clave === s.d.dataset)))

watch(() => consulta.dataset, () => {
  consulta.dimensiones = []
  consulta.medidas = ['conteo']
  consulta.filtros = {}
  resultado.value = null
})

function alternar(lista: string[], clave: string, maximo: number) {
  const i = lista.indexOf(clave)
  if (i >= 0) lista.splice(i, 1)
  else if (lista.length < maximo) lista.push(clave)
}
async function ejecutar() {
  error.value = ''
  cargando.value = true
  try {
    resultado.value = (await api.post('/bi/consultar', consulta)).data
  } catch (e) { error.value = mensajeError(e) } finally { cargando.value = false }
}
function aplicar(d: Partial<typeof consulta>) {
  consulta.dataset = d.dataset!
  setTimeout(() => { Object.assign(consulta, { filtros: {}, ...d }); ejecutar() })
}
function agregarFiltro() {
  if (filtro.dimension && filtro.valor) consulta.filtros[filtro.dimension] = filtro.valor
  filtro.valor = ''
}
async function exportar(formato: string) {
  try {
    const { data } = await api.post('/bi/exportar', consulta, { params: { formato }, responseType: 'blob' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(data)
    a.download = `reporte.${formato}`
    a.click()
  } catch (e) { error.value = mensajeError(e) }
}
async function guardar() {
  const nombre = prompt('Nombre del reporte')
  if (!nombre) return
  const compartir = prompt('Compartir con roles (separados por coma, opcional): medico, auditor, facturacion…') || ''
  try {
    await api.post('/bi/reportes', { nombre, definicion: consulta, roles: compartir.split(',').map((x) => x.trim()).filter(Boolean) })
    guardados.value = (await api.get('/bi/reportes')).data
  } catch (e) { error.value = mensajeError(e) }
}
async function borrar(g: Guardado) {
  if (!confirm(`¿Eliminar "${g.nombre}"?`)) return
  await api.delete(`/bi/reportes/${g.id}`)
  guardados.value = (await api.get('/bi/reportes')).data
}
onMounted(async () => {
  ;[datasets.value, guardados.value] = await Promise.all([api.get('/bi/datasets').then((r) => r.data), api.get('/bi/reportes').then((r) => r.data)])
})
</script>

<template>
  <h1>Inteligencia de negocio</h1>
  <p class="suave">Arme reportes sin programar: elija qué analizar, cómo agruparlo y qué medir. Solo muestra datos agregados (sin nombres ni documentos), según los permisos de su rol ({{ auth.usuario?.rol }}).</p>
  <div v-if="error" class="alerta error">{{ error }}</div>

  <div class="rejilla-2">
    <div class="tarjeta">
      <h2>Reportes sugeridos</h2>
      <div class="fila" style="gap: .4rem">
        <button v-for="s in sugeridosDisponibles" :key="s.nombre" class="btn sec peq" @click="aplicar(s.d)">{{ s.nombre }}</button>
      </div>
    </div>
    <div class="tarjeta">
      <h2>Mis reportes guardados</h2>
      <p v-if="!guardados.length" class="suave">Aún no hay reportes guardados.</p>
      <div v-for="g in guardados" :key="g.id" class="fila entre" style="margin: .3rem 0">
        <button class="btn sec peq" @click="aplicar(g.definicion)">{{ g.nombre }}</button>
        <button v-if="g.propio" class="btn sec peq" @click="borrar(g)">✕</button>
      </div>
    </div>
  </div>

  <div class="tarjeta">
    <h2>Constructor de reportes</h2>
    <div class="rejilla">
      <label>¿Qué quiere analizar?
        <select v-model="consulta.dataset"><option value="" disabled>Elija…</option><option v-for="d in datasets" :key="d.clave" :value="d.clave">{{ d.nombre }}</option></select>
      </label>
      <label>Desde <input v-model="consulta.desde" type="date" /></label>
      <label>Hasta <input v-model="consulta.hasta" type="date" /></label>
      <label>Visualización
        <select v-model="consulta.grafico"><option value="barras">Barras</option><option value="lineas">Líneas (tendencia)</option><option value="tabla">Solo tabla</option></select>
      </label>
    </div>
    <template v-if="actual">
      <h3 style="margin-top: 1rem">Agrupar por (máximo 3)</h3>
      <div class="fila chips">
        <button v-for="d in actual.dimensiones" :key="d.clave" :class="['btn peq', consulta.dimensiones.includes(d.clave) ? '' : 'sec']"
          @click="alternar(consulta.dimensiones, d.clave, 3)">{{ d.etiqueta }}</button>
      </div>
      <h3 style="margin-top: 1rem">Medir</h3>
      <div class="fila chips">
        <button v-for="m in actual.medidas" :key="m.clave" :class="['btn peq', consulta.medidas.includes(m.clave) ? '' : 'sec']"
          @click="alternar(consulta.medidas, m.clave, 6)">{{ m.etiqueta }}</button>
      </div>
      <h3 style="margin-top: 1rem">Filtros</h3>
      <div class="fila">
        <select v-model="filtro.dimension" style="max-width: 220px"><option value="">Campo…</option><option v-for="d in actual.dimensiones" :key="d.clave" :value="d.clave">{{ d.etiqueta }}</option></select>
        <input v-model="filtro.valor" placeholder="Valor exacto (ej. M, EPS001, Alto)" style="max-width: 260px" />
        <button class="btn sec peq" @click="agregarFiltro">Agregar</button>
        <span v-for="(v, k) in consulta.filtros" :key="k" class="etiqueta ia">{{ actual.dimensiones.find((d) => d.clave === k)?.etiqueta }} = {{ v }}
          <a href="#" @click.prevent="delete consulta.filtros[k]">✕</a></span>
      </div>
      <div class="fila" style="margin-top: 1rem">
        <button class="btn" :disabled="cargando || !consulta.medidas.length" @click="ejecutar">{{ cargando ? 'Calculando…' : 'Generar reporte' }}</button>
        <template v-if="resultado">
          <button class="btn sec" @click="exportar('xlsx')">Excel</button>
          <button class="btn sec" @click="exportar('csv')">CSV</button>
          <button class="btn sec" @click="guardar">Guardar reporte</button>
        </template>
      </div>
    </template>
  </div>

  <div v-if="resultado" class="tarjeta">
    <div class="fila entre">
      <h2 style="margin: 0">{{ resultado.titulo }}</h2>
      <span class="suave">{{ resultado.registros_analizados }} registros · {{ resultado.total_grupos }} grupos</span>
    </div>
    <Grafico v-if="resultado.grafico !== 'tabla' && resultado.filas.length" :filas="resultado.filas" :etiqueta="etiquetaFila"
      :medida="consulta.medidas[0]" :tipo="resultado.grafico" style="margin: 1rem 0" />
    <table>
      <thead><tr><th v-for="c in resultado.columnas" :key="c.clave">{{ c.etiqueta }}</th></tr></thead>
      <tbody>
        <tr v-for="(f, i) in resultado.filas" :key="i">
          <td v-for="c in resultado.columnas" :key="c.clave" :style="{ textAlign: c.tipo === 'medida' ? 'right' : 'left' }">
            {{ c.tipo === 'medida' && typeof f[c.clave] === 'number' ? (f[c.clave] as number).toLocaleString('es-CO') : f[c.clave] ?? '—' }}
          </td>
        </tr>
        <tr v-if="!resultado.filas.length"><td class="suave">Sin datos en el periodo.</td></tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.chips { gap: .35rem; }
</style>
