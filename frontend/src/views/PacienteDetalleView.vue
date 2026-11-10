<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { abrirArchivo, api, fechaHora, mensajeError } from '../api/cliente'
import type { Atencion, Paciente } from '../api/tipos'
import FirmaCanvas from '../components/FirmaCanvas.vue'
import { useAuth } from '../stores/auth'

/* eslint-disable @typescript-eslint/no-explicit-any */
const auth = useAuth()
const route = useRoute()
const router = useRouter()
const id = route.params.id as string
const p = ref<Paciente | null>(null)
const historia = ref<Atencion[]>([])
const resumen = ref<any>(null)
const consentimientos = ref<any[]>([])
const ordenes = ref<any[]>([])
const plantillasC = ref<Record<string, { titulo: string; texto: string }>>({})
const pestana = ref('historia')
const error = ref('')
const ok = ref('')
const firma = ref<string | null>(null)
const cons = reactive({ plantilla: '', titulo: '', texto: '', decision: 'acepta', firmante_nombre: '', firmante_documento: '', parentesco: 'paciente' })
const orden = reactive({ tipo: 'laboratorio', cod_cups: '', descripcion: '', prioridad: 'rutina', indicaciones: '' })
const clinico = auth.tiene('medico', 'enfermeria', 'auditor', 'admin', 'estudiante')

async function cargar() {
  p.value = (await api.get(`/pacientes/${id}`)).data
  if (clinico) {
    ;[historia.value, consentimientos.value, ordenes.value] = await Promise.all([
      api.get(`/pacientes/${id}/historia`).then((r) => r.data), api.get(`/pacientes/${id}/consentimientos`).then((r) => r.data),
      api.get('/ordenes-servicio', { params: { paciente_id: id } }).then((r) => r.data)])
  }
}
async function verResumen() { resumen.value = (await api.get(`/pacientes/${id}/resumen-ia`)).data }
const portalActivo = ref(false)
function abrir(a: Atencion) {
  const propio = a.profesional.id === auth.usuario?.id
  const refrendable = auth.tiene('medico', 'admin') && a.profesional.rol === 'estudiante'
  if (a.estado === 'borrador' && (propio || refrendable)) router.push(`/pacientes/${id}/atencion/${a.id}`)
  else router.push(`/atenciones/${a.id}`)
}
function elegirPlantilla() {
  const pl = plantillasC.value[cons.plantilla]
  if (pl) Object.assign(cons, { titulo: pl.titulo, texto: pl.texto })
  if (p.value && !cons.firmante_nombre) Object.assign(cons, { firmante_nombre: p.value.nombre_completo, firmante_documento: p.value.numero_documento })
}
async function accion(fn: () => Promise<unknown>, mensaje: string) {
  error.value = ok.value = ''
  try { await fn(); ok.value = mensaje; await cargar() } catch (e) { error.value = mensajeError(e) }
}
const firmarConsentimiento = () => accion(async () => {
  if (!firma.value) throw { response: { data: { detail: 'Falta la firma' } } }
  await api.post('/consentimientos', { ...cons, paciente_id: id, firma_imagen: firma.value })
}, 'Consentimiento registrado')
const ordenar = () => accion(() => api.post('/ordenes-servicio', { ...orden, paciente_id: id, indicaciones: orden.indicaciones || null }), 'Orden enviada')
const accesoPortal = () => accion(async () => {
  const { data } = await api.post(`/pacientes/${id}/acceso-portal`)
  alert(`Usuario: ${data.usuario}\nClave temporal: ${data.clave_temporal}\n\n${data.mensaje}`)
}, 'Acceso al portal creado')

onMounted(async () => {
  portalActivo.value = (await api.get('/salud')).data.portal_paciente
  await cargar()
  if (auth.tiene('medico', 'enfermeria', 'admin')) plantillasC.value = (await api.get('/consentimientos/plantillas')).data
})
</script>

<template>
  <template v-if="p">
    <div class="fila entre">
      <div>
        <h1 style="margin: 0">{{ p.nombre_completo }}</h1>
        <p class="suave">{{ p.tipo_documento }} {{ p.numero_documento }} · {{ p.edad }} años · {{ { H: 'Hombre', M: 'Mujer', I: 'Indeterminado' }[p.sexo] }}</p>
      </div>
      <div class="fila">
        <button v-if="clinico" class="btn sec" @click="verResumen">Resumen IA</button>
        <button v-if="portalActivo && auth.tiene('admisiones', 'admin')" class="btn sec" @click="accesoPortal">Crear acceso al portal</button>
        <RouterLink v-if="auth.tiene('medico', 'enfermeria', 'admin', 'estudiante')" class="btn" :to="`/pacientes/${p.id}/atencion`">+ Nueva atención</RouterLink>
      </div>
    </div>
    <div v-if="p.alergias" class="alerta error"><strong>ALERGIAS:</strong> {{ p.alergias }}</div>
    <div v-if="!p.autoriza_tratamiento_datos" class="alerta aviso">El paciente no ha autorizado el tratamiento de datos personales (Ley 1581 de 2012).</div>
    <div v-if="error" class="alerta error">{{ error }}</div>
    <div v-if="ok" class="alerta ok">{{ ok }}</div>

    <div v-if="resumen" class="tarjeta panel-ia">
      <div class="fila entre"><h2 style="margin: 0">Resumen clínico ({{ resumen.proveedor === 'claude' ? 'IA Claude' : 'automático' }})</h2><button class="btn sec peq" @click="resumen = null">Cerrar</button></div>
      <p v-if="resumen.narrativo" style="white-space: pre-wrap">{{ resumen.narrativo }}</p>
      <div class="rejilla">
        <div><strong>Problemas activos</strong><ul><li v-for="x in resumen.estructurado.problemas_activos" :key="x.codigo">{{ x.codigo }} {{ x.descripcion }} ({{ x.consultas }})</li></ul></div>
        <div><strong>Medicamentos recientes</strong><ul><li v-for="m in resumen.estructurado.medicamentos_recientes" :key="m">{{ m }}</li></ul></div>
        <div><strong>Resultados anormales</strong><ul><li v-for="r in resumen.estructurado.resultados_anormales" :key="r">{{ r }}</li></ul></div>
      </div>
      <small class="suave">{{ resumen.aviso }}</small>
    </div>

    <div class="tarjeta">
      <h2>Datos del paciente</h2>
      <div class="rejilla">
        <div><div class="suave">Fecha de nacimiento</div>{{ p.fecha_nacimiento }}</div>
        <div><div class="suave">Teléfono</div>{{ p.telefono || '—' }}</div>
        <div><div class="suave">Correo</div>{{ p.email || '—' }}</div>
        <div><div class="suave">Municipio</div>{{ p.cod_municipio_residencia }} ({{ p.zona_territorial === '01' ? 'rural' : 'urbana' }})</div>
        <div><div class="suave">EPS / régimen</div>{{ p.cod_eapb || '—' }} / {{ p.tipo_usuario }}</div>
        <div><div class="suave">Grupo sanguíneo</div>{{ p.grupo_sanguineo || '—' }}</div>
        <div><div class="suave">Acompañante</div>{{ p.acompanante_nombre || '—' }} {{ p.acompanante_telefono || '' }}</div>
      </div>
    </div>

    <template v-if="clinico">
      <div class="fila" style="margin-bottom: 1rem; gap: .4rem">
        <button v-for="x in ['historia', 'ordenes', 'consentimientos']" :key="x" :class="['btn peq', pestana === x ? '' : 'sec']" @click="pestana = x">
          {{ { historia: `Historia clínica (${historia.length})`, ordenes: `Laboratorio e imágenes (${ordenes.length})`, consentimientos: `Consentimientos (${consentimientos.length})` }[x] }}
        </button>
      </div>

      <div v-if="pestana === 'historia'" class="tarjeta">
        <table>
          <thead><tr><th>Folio</th><th>Fecha</th><th>Tipo</th><th>Motivo</th><th>Dx principal</th><th>Profesional</th><th>Estado</th></tr></thead>
          <tbody>
            <tr v-for="a in historia" :key="a.id" class="clic" @click="abrir(a)">
              <td>#{{ a.consecutivo }}</td><td>{{ fechaHora(a.fecha_inicio) }}</td><td style="text-transform: capitalize">{{ a.tipo }}</td><td>{{ a.motivo_consulta }}</td>
              <td>{{ a.diagnosticos[0] ? `${a.diagnosticos[0].codigo_cie10} ${a.diagnosticos[0].descripcion}` : '—' }}</td>
              <td>{{ a.profesional.nombres }} {{ a.profesional.apellidos }}</td><td><span :class="['etiqueta', a.estado]">{{ a.estado }}</span></td>
            </tr>
            <tr v-if="!historia.length"><td colspan="7" class="suave">Sin atenciones registradas.</td></tr>
          </tbody>
        </table>
      </div>

      <div v-if="pestana === 'ordenes'" class="tarjeta">
        <form v-if="auth.tiene('medico', 'admin')" @submit.prevent="ordenar">
          <div class="rejilla">
            <label>Tipo <select v-model="orden.tipo"><option value="laboratorio">Laboratorio</option><option value="imagen">Imagen diagnóstica</option></select></label>
            <label>CUPS <input v-model="orden.cod_cups" maxlength="6" required /></label>
            <label>Examen <input v-model="orden.descripcion" required /></label>
            <label>Prioridad <select v-model="orden.prioridad"><option value="rutina">Rutina</option><option value="urgente">Urgente</option></select></label>
          </div>
          <label style="margin-top: .5rem">Indicaciones <input v-model="orden.indicaciones" /></label>
          <button class="btn" style="margin-top: .6rem">Ordenar</button>
        </form>
        <table style="margin-top: 1rem">
          <tbody>
            <tr v-for="o in ordenes" :key="o.id">
              <td>{{ fechaHora(o.fecha) }}</td><td><strong>{{ o.cod_cups }}</strong> {{ o.descripcion }}</td><td>{{ o.estado }}</td>
              <td><small v-for="r in o.resultados || []" :key="r.analito" :style="{ color: r.anormal ? 'var(--peligro)' : '', display: 'block' }">{{ r.analito }}: {{ r.valor }} {{ r.unidad }}</small><small class="suave">{{ o.informe }}</small></td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="pestana === 'consentimientos'" class="tarjeta">
        <form v-if="auth.tiene('medico', 'enfermeria', 'admin')" @submit.prevent="firmarConsentimiento">
          <div class="rejilla">
            <label>Plantilla <select v-model="cons.plantilla" @change="elegirPlantilla"><option value="">—</option><option v-for="(pl, k) in plantillasC" :key="k" :value="k">{{ pl.titulo }}</option></select></label>
            <label>Decisión <select v-model="cons.decision"><option value="acepta">Acepta</option><option value="rechaza">Rechaza</option><option value="revoca">Revoca</option></select></label>
            <label>Firmante <input v-model="cons.firmante_nombre" required /></label>
            <label>Documento <input v-model="cons.firmante_documento" required /></label>
            <label>Calidad <select v-model="cons.parentesco"><option value="paciente">Paciente</option><option value="representante legal">Representante legal</option><option value="familiar">Familiar</option></select></label>
          </div>
          <label style="margin-top: .5rem">Título <input v-model="cons.titulo" required /></label>
          <label style="margin-top: .5rem">Texto (complete los espacios ____) <textarea v-model="cons.texto" rows="6" required /></label>
          <h3 style="margin-top: .8rem">Firma</h3>
          <FirmaCanvas @firma="(f) => (firma = f)" />
          <button class="btn" style="margin-top: .6rem" :disabled="!firma">Registrar consentimiento</button>
        </form>
        <table style="margin-top: 1rem">
          <tbody>
            <tr v-for="c in consentimientos" :key="c.id">
              <td>{{ fechaHora(c.fecha) }}</td><td><strong>{{ c.titulo }}</strong></td><td>{{ c.decision }}</td><td>{{ c.firmante_nombre }}</td>
              <td><button class="btn sec peq" @click="abrirArchivo(`/consentimientos/${c.id}/pdf`)">PDF</button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </template>
</template>

<style scoped>
.panel-ia { background: #faf5ff; border-color: #e9d5ff; }
</style>
