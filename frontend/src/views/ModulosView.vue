<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { api, fechaHora, mensajeError } from '../api/cliente'
import type { Paciente } from '../api/tipos'
import { useAuth } from '../stores/auth'

interface CampoDef { clave: string; etiqueta: string; tipo: string; requerido: boolean; opciones: string[] | null; min?: number | null; max?: number | null; ayuda?: string | null }
interface Modulo { id: string; clave: string; nombre: string; descripcion: string | null; categoria: string; campos: CampoDef[]
  roles_lectura: string[]; roles_escritura: string[]; por_paciente: boolean; sellar_al_guardar: boolean; activo: boolean
  version: number; puede_escribir: boolean }
interface Registro { id: string; paciente_id: string | null; datos: Record<string, unknown>; sellado: boolean; autor: string; creado_en: string }

const auth = useAuth()
const modulos = ref<Modulo[]>([])
const plantillas = ref<Record<string, { nombre: string; descripcion: string }>>({})
const tipos = ref<Record<string, string>>({})
const actual = ref<Modulo | null>(null)
const registros = ref<Registro[]>([])
const datos = reactive<Record<string, unknown>>({})
const error = ref('')
const ok = ref('')
const busqueda = ref('')
const pacientes = ref<Paciente[]>([])
const pacienteId = ref('')
const constructor = ref(false)
const ROLES = ['medico', 'enfermeria', 'admisiones', 'facturacion', 'farmacia', 'laboratorio', 'auditor']
const nuevo = reactive({ clave: '', nombre: '', descripcion: '', categoria: 'asistencial', por_paciente: true, sellar_al_guardar: false,
  roles_lectura: [] as string[], roles_escritura: [] as string[],
  campos: [{ clave: '', etiqueta: '', tipo: 'texto', requerido: false, opcionesTexto: '', min: null as number | null, max: null as number | null }] })
const esAdmin = computed(() => auth.tiene('admin'))
const nombrePaciente = (id: string | null) => pacientes.value.find((p) => p.id === id)?.nombre_completo || (id ? id.slice(0, 8) : '—')

async function cargar() {
  modulos.value = (await api.get('/modulos')).data
  tipos.value = (await api.get('/modulos/tipos-campo')).data
  if (esAdmin.value) plantillas.value = (await api.get('/modulos/plantillas')).data
}
async function abrir(m: Modulo) {
  actual.value = m
  Object.keys(datos).forEach((k) => delete datos[k])
  for (const c of m.campos) datos[c.clave] = c.tipo === 'multiple' ? [] : c.tipo === 'si_no' ? false : ''
  registros.value = (await api.get(`/modulos/${m.clave}/registros`, { params: { paciente_id: pacienteId.value || undefined } })).data
}
async function buscar() {
  pacientes.value = busqueda.value.length > 2 ? (await api.get('/pacientes', { params: { q: busqueda.value, limite: 8 } })).data : []
  pacienteId.value = pacientes.value[0]?.id || ''
  if (actual.value) await abrir(actual.value)
}
async function accion(fn: () => Promise<unknown>, mensaje: string) {
  error.value = ok.value = ''
  try {
    const r = await fn()
    ok.value = typeof r === 'string' ? r : mensaje
  } catch (e) { error.value = mensajeError(e) }
}
const registrar = () => accion(async () => {
  const limpio = Object.fromEntries(Object.entries(datos).filter(([, v]) => v !== '' && !(Array.isArray(v) && !v.length)))
  const r = (await api.post(`/modulos/${actual.value!.clave}/registros`, { paciente_id: pacienteId.value || null, datos: limpio })).data
  await abrir(actual.value!)
  return r.sellado ? 'Registro guardado y sellado (inalterable)' : 'Registro guardado'
}, 'Registro guardado')
const instalar = (k: string) => accion(async () => { await api.post(`/modulos/plantillas/${k}/instalar`); await cargar() }, 'Módulo instalado')
const crear = () => accion(async () => {
  await api.post('/modulos', { ...nuevo, campos: nuevo.campos.map((c) => ({ ...c, opciones: c.opcionesTexto.split(',').map((x) => x.trim()).filter(Boolean) })) })
  constructor.value = false
  await cargar()
}, 'Módulo creado')
function claveDesde(texto: string) {
  return texto.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '').slice(0, 40)
}
onMounted(cargar)
</script>

<template>
  <h1>Módulos adicionales</h1>
  <p class="suave">Escalas, seguimientos, programas de calidad, PQRS… creados por la institución sin programar. Cada registro queda en la auditoría y alimenta automáticamente la inteligencia de negocio.</p>
  <div v-if="error" class="alerta error">{{ error }}</div>
  <div v-if="ok" class="alerta ok">{{ ok }}</div>

  <div v-if="esAdmin" class="tarjeta">
    <div class="fila entre"><h2 style="margin: 0">Instalar plantillas listas</h2><button class="btn sec peq" @click="constructor = !constructor">{{ constructor ? 'Cerrar constructor' : '+ Crear módulo desde cero' }}</button></div>
    <div class="fila" style="gap: .4rem; margin-top: .6rem">
      <button v-for="(p, k) in plantillas" :key="k" class="btn sec peq" :disabled="modulos.some((m) => m.clave === k)" :title="p.descripcion" @click="instalar(k)">
        {{ modulos.some((m) => m.clave === k) ? '✓ ' : '+ ' }}{{ p.nombre }}
      </button>
    </div>

    <form v-if="constructor" style="margin-top: 1rem" @submit.prevent="crear">
      <div class="rejilla">
        <label>Nombre del módulo <input v-model="nuevo.nombre" required @input="nuevo.clave = claveDesde(nuevo.nombre)" /></label>
        <label>Clave interna <input v-model="nuevo.clave" required pattern="[a-z][a-z0-9_]{1,39}" /></label>
        <label>Categoría <select v-model="nuevo.categoria"><option>asistencial</option><option>administrativo</option><option>calidad</option><option>financiero</option></select></label>
      </div>
      <label style="margin-top: .5rem">Descripción <input v-model="nuevo.descripcion" /></label>
      <div class="fila" style="margin-top: .5rem">
        <label class="check"><input v-model="nuevo.por_paciente" type="checkbox" /> Se registra por paciente</label>
        <label class="check"><input v-model="nuevo.sellar_al_guardar" type="checkbox" /> Sellar registros (dato clínico inalterable)</label>
      </div>
      <div class="rejilla-2" style="margin-top: .5rem">
        <div><strong>Pueden consultar</strong><div class="fila"><label v-for="r in ROLES" :key="r" class="check"><input v-model="nuevo.roles_lectura" type="checkbox" :value="r" /> {{ r }}</label></div></div>
        <div><strong>Pueden registrar</strong><div class="fila"><label v-for="r in ROLES" :key="r" class="check"><input v-model="nuevo.roles_escritura" type="checkbox" :value="r" /> {{ r }}</label></div></div>
      </div>
      <h3 style="margin-top: 1rem">Campos</h3>
      <table>
        <thead><tr><th>Etiqueta</th><th>Clave</th><th>Tipo</th><th>Opciones (coma)</th><th>Mín</th><th>Máx</th><th>Oblig.</th><th></th></tr></thead>
        <tbody>
          <tr v-for="(c, i) in nuevo.campos" :key="i">
            <td><input v-model="c.etiqueta" required @input="c.clave = claveDesde(c.etiqueta)" /></td>
            <td><input v-model="c.clave" required /></td>
            <td><select v-model="c.tipo"><option v-for="(t, k) in tipos" :key="k" :value="k">{{ t }}</option></select></td>
            <td><input v-model="c.opcionesTexto" :disabled="!['seleccion', 'multiple'].includes(c.tipo)" /></td>
            <td style="width: 70px"><input v-model.number="c.min" type="number" :disabled="!['numero', 'entero'].includes(c.tipo)" /></td>
            <td style="width: 70px"><input v-model.number="c.max" type="number" :disabled="!['numero', 'entero'].includes(c.tipo)" /></td>
            <td style="width: 50px"><input v-model="c.requerido" type="checkbox" /></td>
            <td><button type="button" class="btn sec peq" @click="nuevo.campos.splice(i, 1)">✕</button></td>
          </tr>
        </tbody>
      </table>
      <button type="button" class="btn sec peq" @click="nuevo.campos.push({ clave: '', etiqueta: '', tipo: 'texto', requerido: false, opcionesTexto: '', min: null, max: null })">+ Campo</button>
      <button class="btn" style="margin-left: .5rem">Crear módulo</button>
    </form>
  </div>

  <div class="rejilla-2">
    <div class="tarjeta">
      <h2>Módulos disponibles</h2>
      <p v-if="!modulos.length" class="suave">No hay módulos para su rol.{{ esAdmin ? ' Instale una plantilla arriba.' : '' }}</p>
      <button v-for="m in modulos" :key="m.id" :class="['btn peq', actual?.id === m.id ? '' : 'sec']" style="margin: .2rem" @click="abrir(m)">
        {{ m.nombre }} <small v-if="m.sellar_al_guardar">🔒</small>
      </button>
    </div>
    <div v-if="actual?.por_paciente" class="tarjeta">
      <h2>Paciente</h2>
      <input v-model="busqueda" placeholder="Documento o nombre…" @input="buscar" />
      <select v-if="pacientes.length" v-model="pacienteId" style="margin-top: .3rem" @change="abrir(actual!)">
        <option v-for="p in pacientes" :key="p.id" :value="p.id">{{ p.nombre_completo }} · {{ p.numero_documento }}</option>
      </select>
    </div>
  </div>

  <template v-if="actual">
    <form v-if="actual.puede_escribir" class="tarjeta" @submit.prevent="registrar">
      <h2>{{ actual.nombre }} <small class="suave">v{{ actual.version }}</small></h2>
      <p class="suave">{{ actual.descripcion }}</p>
      <div class="rejilla">
        <div v-for="c in actual.campos" :key="c.clave" class="campo-mod" :style="c.tipo === 'texto_largo' || c.tipo === 'multiple' ? 'grid-column: 1 / -1' : ''">
          <span class="etq-mod">{{ c.etiqueta }}{{ c.requerido ? ' *' : '' }}</span>
          <textarea v-if="c.tipo === 'texto_largo'" v-model="datos[c.clave] as string" :aria-label="c.etiqueta" />
          <select v-else-if="c.tipo === 'seleccion'" v-model="datos[c.clave]" :aria-label="c.etiqueta"><option value="">—</option><option v-for="o in c.opciones" :key="o">{{ o }}</option></select>
          <span v-else-if="c.tipo === 'multiple'" class="fila"><label v-for="o in c.opciones" :key="o" class="check"><input v-model="datos[c.clave]" type="checkbox" :value="o" /> {{ o }}</label></span>
          <label v-else-if="c.tipo === 'si_no'" class="check"><input v-model="datos[c.clave]" type="checkbox" /> Sí</label>
          <input v-else v-model="datos[c.clave]" :type="{ numero: 'number', entero: 'number', fecha: 'date', fecha_hora: 'datetime-local' }[c.tipo] || 'text'"
            :step="c.tipo === 'numero' ? 'any' : undefined" :min="c.min ?? undefined" :max="c.max ?? undefined" :placeholder="c.tipo === 'cie10' ? 'Ej. I10X' : ''" :aria-label="c.etiqueta" />
        </div>
      </div>
      <button class="btn" style="margin-top: 1rem" :disabled="actual.por_paciente && !pacienteId">Guardar registro</button>
    </form>
    <div class="tarjeta">
      <h2>Registros ({{ registros.length }})</h2>
      <table>
        <thead><tr><th>Fecha</th><th v-if="actual.por_paciente">Paciente</th><th v-for="c in actual.campos.slice(0, 4)" :key="c.clave">{{ c.etiqueta }}</th><th>Autor</th><th></th></tr></thead>
        <tbody>
          <tr v-for="r in registros" :key="r.id">
            <td>{{ fechaHora(r.creado_en) }}</td>
            <td v-if="actual.por_paciente">{{ nombrePaciente(r.paciente_id) }}</td>
            <td v-for="c in actual.campos.slice(0, 4)" :key="c.clave">{{ Array.isArray(r.datos[c.clave]) ? (r.datos[c.clave] as string[]).join(', ') : r.datos[c.clave] === true ? 'Sí' : r.datos[c.clave] === false ? 'No' : r.datos[c.clave] ?? '—' }}</td>
            <td>{{ r.autor }}</td>
            <td>{{ r.sellado ? '🔒' : '' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </template>
</template>

<style scoped>
.campo-mod { display: flex; flex-direction: column; gap: .3rem; }
.etq-mod { font-size: .8rem; font-weight: 600; color: var(--texto-suave); }
</style>
