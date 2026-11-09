<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, mensajeError } from '../api/cliente'
import type { Atencion } from '../api/tipos'

const atenciones = ref<Atencion[]>([])
const seleccion = ref<string[]>([])
const numFactura = ref('')
const resultado = ref<{ valido: boolean; errores: string[]; rips: object } | null>(null)
const error = ref('')

onMounted(async () => {
  atenciones.value = (await api.get('/atenciones', { params: { estado: 'firmada' } })).data
})

const cuerpo = () => ({ num_factura: numFactura.value, atencion_ids: seleccion.value })

async function generar() {
  error.value = ''
  try {
    resultado.value = (await api.post('/rips/generar', cuerpo())).data
  } catch (e) {
    error.value = mensajeError(e)
  }
}

async function descargar() {
  try {
    const { data } = await api.post('/rips/descargar', cuerpo(), { responseType: 'blob' })
    const url = URL.createObjectURL(data)
    const enlace = document.createElement('a')
    enlace.href = url
    enlace.download = `RIPS_${numFactura.value}.json`
    enlace.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    error.value = 'No se pudo descargar: corrija los errores de validación'
  }
}
const fecha = (f: string) => new Date(f).toLocaleString('es-CO', { dateStyle: 'short', timeStyle: 'short' })
</script>

<template>
  <h1>RIPS · Resolución 2275 de 2023</h1>
  <div class="alerta aviso">
    Aquí puede <strong>generar y validar</strong> el JSON de RIPS de cualquier grupo de atenciones firmadas, antes de facturar.
    Para el flujo completo (factura DIAN + RIPS + validación en el MUV con CUV) use
    <RouterLink to="/facturacion">Facturación electrónica</RouterLink>: allí cada factura emitida genera su RIPS automáticamente
    (consultas, procedimientos, urgencias, hospitalización y medicamentos).
  </div>
  <div class="tarjeta">
    <h2>1. Seleccione las atenciones firmadas a facturar</h2>
    <table>
      <thead><tr><th></th><th>Fecha</th><th>Folio</th><th>Motivo</th><th>Dx principal</th></tr></thead>
      <tbody>
        <tr v-for="a in atenciones" :key="a.id">
          <td><input v-model="seleccion" type="checkbox" :value="a.id" /></td>
          <td>{{ fecha(a.fecha_inicio) }}</td>
          <td>#{{ a.consecutivo }}</td>
          <td>{{ a.motivo_consulta }}</td>
          <td>{{ a.diagnosticos[0]?.codigo_cie10 }}</td>
        </tr>
        <tr v-if="!atenciones.length"><td colspan="5" class="suave">No hay atenciones firmadas.</td></tr>
      </tbody>
    </table>
  </div>
  <div class="tarjeta">
    <h2>2. Número de la factura electrónica</h2>
    <div class="fila">
      <input v-model="numFactura" placeholder="Ej: FEV1001" style="max-width: 260px" />
      <button class="btn" :disabled="!numFactura || !seleccion.length" @click="generar">Generar y validar</button>
      <button class="btn sec" :disabled="!resultado?.valido" @click="descargar">Descargar JSON</button>
    </div>
  </div>
  <div v-if="error" class="alerta error">{{ error }}</div>
  <template v-if="resultado">
    <div :class="['alerta', resultado.valido ? 'ok' : 'error']">
      <template v-if="resultado.valido">Estructura válida. Lista para enviar al MUV.</template>
      <template v-else><strong>Errores:</strong><ul><li v-for="e in resultado.errores" :key="e">{{ e }}</li></ul></template>
    </div>
    <div class="tarjeta"><pre class="mono">{{ JSON.stringify(resultado.rips, null, 2) }}</pre></div>
  </template>
</template>
