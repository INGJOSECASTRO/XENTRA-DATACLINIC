<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api, mensajeError } from '../api/cliente'
import type { Atencion } from '../api/tipos'
import { useAuth } from '../stores/auth'

const auth = useAuth()
const route = useRoute()
const a = ref<Atencion | null>(null)
const verificacion = ref<{ integra: boolean | null; detalle: string; hash_actual?: string; bloque?: number } | null>(null)
const nota = ref('')
const error = ref('')

async function cargar() {
  a.value = (await api.get(`/atenciones/${route.params.id}`)).data
}
async function verificar() {
  verificacion.value = (await api.get(`/atenciones/${route.params.id}/verificar`)).data
}
async function agregarNota() {
  error.value = ''
  try {
    await api.post(`/atenciones/${route.params.id}/notas`, { texto: nota.value })
    nota.value = ''
    await cargar()
  } catch (e) {
    error.value = mensajeError(e)
  }
}
const fecha = (f?: string | null) => (f ? new Date(f).toLocaleString('es-CO', { dateStyle: 'medium', timeStyle: 'short' }) : '—')
const etiquetasSV: Record<string, string> = { ta_sistolica: 'TAS', ta_diastolica: 'TAD', fc: 'FC', fr: 'FR', temperatura: 'T°', spo2: 'SpO₂', peso: 'Peso', talla: 'Talla' }
const tipoDx: Record<string, string> = { '01': 'Impresión diagnóstica', '02': 'Confirmado nuevo', '03': 'Confirmado repetido' }
onMounted(cargar)
</script>

<template>
  <div v-if="a">
    <div class="fila entre">
      <div>
        <h1 style="margin: 0">Folio #{{ a.consecutivo }} · <span style="text-transform: capitalize">{{ a.tipo }}</span></h1>
        <p class="suave">{{ fecha(a.fecha_inicio) }} · {{ a.profesional.nombres }} {{ a.profesional.apellidos }}
          ({{ a.profesional.especialidad || a.profesional.rol }}, reg. {{ a.profesional.registro_profesional || '—' }})</p>
      </div>
      <div class="fila">
        <span :class="['etiqueta', a.estado]">{{ a.estado }}</span>
        <RouterLink class="btn sec" :to="`/pacientes/${a.paciente_id}`">Volver al paciente</RouterLink>
        <button class="btn sec" onclick="window.print()">Imprimir</button>
      </div>
    </div>

    <div v-for="al in a.alertas" :key="al" class="alerta aviso">{{ al }}</div>

    <div class="tarjeta" v-if="a.estado === 'firmada'">
      <div class="fila entre">
        <div>
          <h2 style="margin: 0">Integridad (sello blockchain)</h2>
          <p class="suave" style="margin: .3rem 0">Firmado {{ fecha(a.firmada_en) }} · Bloque #{{ a.bloque_ledger_id }}</p>
          <div class="mono">SHA-256: {{ a.hash_contenido }}</div>
        </div>
        <button class="btn" @click="verificar">Verificar integridad</button>
      </div>
      <div v-if="verificacion" :class="['alerta', verificacion.integra ? 'ok' : 'error']" style="margin-top: .75rem">{{ verificacion.detalle }}</div>
    </div>

    <div class="tarjeta">
      <h3>Motivo de consulta</h3><p>{{ a.motivo_consulta }}</p>
      <template v-if="a.enfermedad_actual"><h3>Enfermedad actual</h3><p>{{ a.enfermedad_actual }}</p></template>
      <template v-if="a.revision_sistemas"><h3>Revisión por sistemas</h3><p>{{ a.revision_sistemas }}</p></template>
      <template v-if="a.signos_vitales && Object.keys(a.signos_vitales).length">
        <h3>Signos vitales</h3>
        <div class="fila"><span v-for="(v, k) in a.signos_vitales" :key="k" class="etiqueta borrador">{{ etiquetasSV[k] || k }}: {{ v }}</span></div>
      </template>
      <template v-if="a.examen_fisico"><h3 style="margin-top: 1rem">Examen físico</h3><p>{{ a.examen_fisico }}</p></template>
      <template v-if="a.analisis"><h3>Análisis</h3><p>{{ a.analisis }}</p></template>
      <h3>Diagnósticos</h3>
      <ul>
        <li v-for="(d, i) in a.diagnosticos" :key="d.codigo_cie10">
          <strong>{{ d.codigo_cie10 }}</strong> {{ d.descripcion }} — {{ i === 0 ? 'Principal' : 'Relacionado' }}, {{ tipoDx[d.tipo_diagnostico] }}
          <span v-if="d.sugerido_por_ia" class="etiqueta ia">sugerido por IA</span>
        </li>
      </ul>
      <template v-if="a.plan"><h3>Plan</h3><p>{{ a.plan }}</p></template>
      <template v-if="a.prescripciones?.length">
        <h3>Fórmula médica</h3>
        <ol><li v-for="(r, i) in a.prescripciones" :key="i">{{ r.medicamento }} — {{ r.dosis }} vía {{ r.via }} {{ r.frecuencia }} por {{ r.duracion_dias }} días (cant. {{ r.cantidad }})</li></ol>
      </template>
      <template v-if="a.procedimientos?.length">
        <h3>Procedimientos</h3>
        <ul><li v-for="p in a.procedimientos" :key="p.cod_cups">{{ p.cod_cups }} {{ p.descripcion }}</li></ul>
      </template>
    </div>

    <div class="tarjeta" v-if="a.estado === 'firmada'">
      <h2>Notas aclaratorias</h2>
      <p class="suave">El folio firmado es inalterable. Las correcciones se registran como notas con fecha, hora y autor.</p>
      <div v-for="n in a.notas_aclaratorias" :key="n.id" class="tarjeta" style="background: #f8fafc">
        <div class="suave">{{ fecha(n.creado_en) }} · {{ n.autor.nombres }} {{ n.autor.apellidos }}</div>
        <p style="margin: .4rem 0">{{ n.texto }}</p>
        <div class="mono suave">{{ n.hash_contenido }}</div>
      </div>
      <template v-if="auth.tiene('medico', 'enfermeria', 'admin')">
        <div v-if="error" class="alerta error">{{ error }}</div>
        <textarea v-model="nota" placeholder="Escriba la aclaración…" />
        <button class="btn" style="margin-top: .5rem" :disabled="nota.length < 5" @click="agregarNota">Agregar nota aclaratoria</button>
      </template>
    </div>
  </div>
</template>
