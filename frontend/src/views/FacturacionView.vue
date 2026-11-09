<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { abrirArchivo, api, fechaHora, mensajeError, pesos } from '../api/cliente'
import { useAuth } from '../stores/auth'

interface Hallazgo { nivel: string; mensaje: string }
interface F { id: string; numero: string | null; estado: string; nombre_pagador: string; cod_eapb: string | null; total: number
  subtotal: number; pagos_moderadores: number; cufe: string | null; cuv: string | null; creado_en: string
  hallazgos_auditoria: Hallazgo[] | null; items: { tipo: string; codigo: string; descripcion: string; cantidad: number; valor_total: number }[] }
interface Pend { atenciones: { id: string; fecha: string; paciente: string; documento: string; eps: string | null; consecutivo: number; motivo: string; valor: number; dx: string }[]
  hospitalizaciones: { id: string; ingreso: string; egreso: string; paciente: string; documento: string; eps: string | null; dx: string }[] }

const auth = useAuth()
const pend = ref<Pend>({ atenciones: [], hospitalizaciones: [] })
const facturas = ref<F[]>([])
const selA = ref<string[]>([])
const selH = ref<string[]>([])
const abierta = ref<string | null>(null)
const error = ref('')
const form = reactive({ tipo_pagador: 'eps', cod_eapb: '', nit_pagador: '', nombre_pagador: '', modalidad_pago: 'evento', num_contrato: '' })
const filtroEps = ref('')
const atencionesVisibles = computed(() => pend.value.atenciones.filter((a) => !filtroEps.value || a.eps === filtroEps.value))
const epsDisponibles = computed(() => [...new Set(pend.value.atenciones.map((a) => a.eps).filter(Boolean))])
const colorEstado: Record<string, string> = { borrador: 'borrador', emitida: 'borrador', validada: 'firmada', rechazada: 'borrador', anulada: 'borrador' }

async function cargar() {
  ;[facturas.value, pend.value] = await Promise.all([api.get('/facturas').then((r) => r.data),
    auth.tiene('facturacion', 'admin') ? api.get('/facturas/pendientes').then((r) => r.data) : Promise.resolve({ atenciones: [], hospitalizaciones: [] })])
}
async function accion(fn: () => Promise<unknown>) {
  error.value = ''
  try { await fn(); await cargar() } catch (e) { error.value = mensajeError(e); await cargar() }
}
const crear = () => accion(async () => {
  const { data } = await api.post('/facturas', { ...form, cod_eapb: form.cod_eapb || filtroEps.value || null, nit_pagador: form.nit_pagador || null,
    num_contrato: form.num_contrato || null, atencion_ids: selA.value, hospitalizacion_ids: selH.value })
  selA.value = []
  selH.value = []
  abierta.value = data.id
})
const op = (f: F, ruta: string) => accion(() => api.post(`/facturas/${f.id}/${ruta}`))
const anular = (f: F) => {
  const motivo = prompt('Motivo de la anulación')
  if (motivo) accion(() => api.post(`/facturas/${f.id}/anular`, { motivo }))
}
onMounted(cargar)
</script>

<template>
  <h1>Facturación electrónica y RIPS</h1>
  <div class="alerta aviso">Flujo: armar cuenta → pre-auditoría automática → emitir ante la DIAN (CUFE) → validar RIPS en el MUV (CUV). En modo "simulado" no se envía nada a entidades externas.</div>
  <div v-if="error" class="alerta error">{{ error }}</div>

  <div v-if="auth.tiene('facturacion', 'admin')" class="tarjeta">
    <div class="fila entre">
      <h2>1. Servicios pendientes por facturar</h2>
      <select v-model="filtroEps" style="max-width: 200px"><option value="">Todas las EPS</option><option v-for="e in epsDisponibles" :key="e!" :value="e">{{ e }}</option></select>
    </div>
    <table>
      <tbody>
        <tr v-for="a in atencionesVisibles" :key="a.id">
          <td style="width: 30px"><input v-model="selA" type="checkbox" :value="a.id" /></td>
          <td>{{ fechaHora(a.fecha) }}</td><td><strong>{{ a.paciente }}</strong> <small class="suave">{{ a.documento }} · {{ a.eps }}</small></td>
          <td>Consulta #{{ a.consecutivo }} · {{ a.dx }}</td><td>{{ pesos(a.valor) }}</td>
        </tr>
        <tr v-for="h in pend.hospitalizaciones" :key="h.id">
          <td><input v-model="selH" type="checkbox" :value="h.id" /></td>
          <td>{{ fechaHora(h.egreso) }}</td><td><strong>{{ h.paciente }}</strong> <small class="suave">{{ h.documento }} · {{ h.eps }}</small></td>
          <td>Hospitalización · {{ h.dx }}</td><td>—</td>
        </tr>
        <tr v-if="!atencionesVisibles.length && !pend.hospitalizaciones.length"><td class="suave">No hay servicios pendientes.</td></tr>
      </tbody>
    </table>
    <h2 style="margin-top: 1rem">2. Datos del pagador</h2>
    <div class="rejilla">
      <label>Tipo <select v-model="form.tipo_pagador"><option value="eps">EPS</option><option value="particular">Particular</option><option value="soat">SOAT</option><option value="arl">ARL</option><option value="otro">Otro</option></select></label>
      <label>Nombre del pagador <input v-model="form.nombre_pagador" required /></label>
      <label>Código EAPB <input v-model="form.cod_eapb" :placeholder="filtroEps" /></label>
      <label>NIT <input v-model="form.nit_pagador" /></label>
      <label>Modalidad <select v-model="form.modalidad_pago"><option value="evento">Evento</option><option value="capitacion">Capitación</option><option value="pgp">PGP</option><option value="otro">Otro</option></select></label>
      <label>N.° contrato <input v-model="form.num_contrato" /></label>
    </div>
    <button class="btn" style="margin-top: 1rem" :disabled="!form.nombre_pagador || (!selA.length && !selH.length)" @click="crear">Armar factura ({{ selA.length + selH.length }} servicios)</button>
  </div>

  <div class="tarjeta">
    <h2>Facturas</h2>
    <table>
      <thead><tr><th>Número</th><th>Pagador</th><th>Total</th><th>Estado</th><th></th></tr></thead>
      <tbody>
        <template v-for="f in facturas" :key="f.id">
          <tr class="clic" @click="abierta = abierta === f.id ? null : f.id">
            <td><strong>{{ f.numero || 'Borrador' }}</strong><br /><small class="suave">{{ fechaHora(f.creado_en) }}</small></td>
            <td>{{ f.nombre_pagador }} <small class="suave">{{ f.cod_eapb }}</small></td>
            <td>{{ pesos(f.total) }}</td>
            <td><span :class="['etiqueta', colorEstado[f.estado]]">{{ f.estado }}</span></td>
            <td @click.stop>
              <template v-if="auth.tiene('facturacion', 'admin')">
                <button v-if="f.estado === 'borrador'" class="btn sec peq" @click="op(f, 'auditar')">Re-auditar</button>
                <button v-if="f.estado === 'borrador'" class="btn peq" @click="op(f, 'emitir')">Emitir DIAN</button>
                <button v-if="['emitida', 'rechazada'].includes(f.estado)" class="btn peq" @click="op(f, 'enviar-muv')">Validar MUV</button>
                <button v-if="f.numero" class="btn sec peq" @click="abrirArchivo(`/facturas/${f.id}/rips`, undefined, `RIPS_${f.numero}.json`)">RIPS</button>
                <button v-if="f.estado === 'borrador'" class="btn sec peq" @click="anular(f)">Anular</button>
              </template>
            </td>
          </tr>
          <tr v-if="abierta === f.id">
            <td colspan="5">
              <div v-for="h in f.hallazgos_auditoria || []" :key="h.mensaje" :class="['alerta', h.nivel === 'error' ? 'error' : h.nivel === 'ok' ? 'ok' : 'aviso']">{{ h.mensaje }}</div>
              <table>
                <tbody><tr v-for="(i, n) in f.items" :key="n"><td>{{ i.tipo }}</td><td>{{ i.codigo }}</td><td>{{ i.descripcion }}</td><td>{{ i.cantidad }}</td><td>{{ pesos(i.valor_total) }}</td></tr></tbody>
              </table>
              <p class="suave">Subtotal {{ pesos(f.subtotal) }} · Pagos moderadores {{ pesos(f.pagos_moderadores) }} · <strong>Total {{ pesos(f.total) }}</strong></p>
              <p v-if="f.cufe" class="mono suave">CUFE: {{ f.cufe }}</p>
              <p v-if="f.cuv" class="mono suave">CUV: {{ f.cuv }}</p>
            </td>
          </tr>
        </template>
      </tbody>
    </table>
  </div>
</template>
