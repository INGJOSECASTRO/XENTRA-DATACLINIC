<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { api, fechaHora, mensajeError, pesos } from '../api/cliente'

interface P { id: string; nombre: string; cum: string | null; stock: number; stock_minimo: number; precio_unitario: number
  lotes: { id: string; numero: string; vencimiento: string; cantidad: number }[] }
interface Pend { formulas: { prescripcion_id: string; paciente: string; documento: string; medicamento: string; dosis: string; cantidad: number; entregado: number; fecha: string }[]
  ordenes: { orden_id: string; paciente: string; cama: string | null; descripcion: string; dosis: string | null; frecuencia: string | null; producto_id: string | null; entregado: number }[] }

const pestana = ref('pendientes')
const productos = ref<P[]>([])
const pend = ref<Pend>({ formulas: [], ordenes: [] })
const alertas = ref<Record<string, { producto: string; lote?: string; vencimiento?: string; cantidad?: number; stock?: number; minimo?: number }[]>>({})
const error = ref('')
const ok = ref('')
const seleccion = reactive<Record<string, { producto_id: string; cantidad: number }>>({})
const nuevo = reactive({ nombre: '', cum: '', concentracion: '', forma_farmaceutica: '', unidad: 'tableta', stock_minimo: 10, precio_unitario: 0, controlado: false, cadena_frio: false })
const entrada = reactive({ producto_id: '', lote: '', vencimiento: '', cantidad: 0, registro_invima: '' })

async function cargar() {
  ;[productos.value, pend.value, alertas.value] = await Promise.all([
    api.get('/farmacia/productos').then((r) => r.data), api.get('/farmacia/pendientes').then((r) => r.data),
    api.get('/farmacia/alertas').then((r) => r.data)])
  // Selección inicial: producto sugerido por nombre y cantidad pendiente
  const sugerir = (texto: string) => productos.value.find((p) => texto.toLowerCase().startsWith(p.nombre.toLowerCase().split(' ')[0]))?.id || ''
  for (const f of pend.value.formulas)
    seleccion[f.prescripcion_id] = { producto_id: sugerir(f.medicamento), cantidad: f.cantidad - f.entregado }
  for (const o of pend.value.ordenes) seleccion[o.orden_id] = { producto_id: o.producto_id || sugerir(o.descripcion), cantidad: 1 }
}
async function accion(fn: () => Promise<unknown>, mensaje: string) {
  error.value = ok.value = ''
  try { await fn(); ok.value = mensaje; await cargar() } catch (e) { error.value = mensajeError(e) }
}
const dispensarFormula = (f: Pend['formulas'][0]) => accion(() => api.post('/farmacia/dispensar', { ...seleccion[f.prescripcion_id], prescripcion_id: f.prescripcion_id }), 'Fórmula entregada')
const dispensarOrden = (o: Pend['ordenes'][0]) => accion(() => api.post('/farmacia/dispensar', { ...seleccion[o.orden_id], orden_id: o.orden_id }), 'Entregado a hospitalización')
const crear = () => accion(() => api.post('/farmacia/productos', { ...nuevo, cum: nuevo.cum || null }), 'Producto creado')
const recibir = () => accion(() => api.post('/farmacia/entradas', { ...entrada, registro_invima: entrada.registro_invima || null }), 'Entrada registrada')
onMounted(cargar)
</script>

<template>
  <h1>Farmacia e inventario</h1>
  <div v-if="error" class="alerta error">{{ error }}</div>
  <div v-if="ok" class="alerta ok">{{ ok }}</div>
  <div class="fila" style="margin-bottom: 1rem; gap: .4rem">
    <button v-for="p in ['pendientes', 'inventario', 'alertas']" :key="p" :class="['btn peq', pestana === p ? '' : 'sec']" @click="pestana = p">
      {{ { pendientes: 'Por dispensar', inventario: 'Inventario', alertas: `Alertas (${(alertas.stock_bajo?.length || 0) + (alertas.vencidos?.length || 0) + (alertas.por_vencer?.length || 0)})` }[p] }}
    </button>
  </div>

  <template v-if="pestana === 'pendientes'">
    <div class="tarjeta">
      <h2>Fórmulas de consulta</h2>
      <table>
        <tbody>
          <tr v-for="f in pend.formulas" :key="f.prescripcion_id">
            <td><strong>{{ f.medicamento }}</strong> · {{ f.dosis }}<br /><small class="suave">{{ f.paciente }} · {{ f.documento }} · {{ fechaHora(f.fecha) }}</small></td>
            <td>Entregado {{ f.entregado }}/{{ f.cantidad }}</td>
            <td style="width: 360px" class="fila">
              <select v-model="seleccion[f.prescripcion_id].producto_id" style="max-width: 200px">
                <option value="">Producto…</option><option v-for="p in productos" :key="p.id" :value="p.id">{{ p.nombre }} ({{ p.stock }})</option>
              </select>
              <input v-model.number="seleccion[f.prescripcion_id].cantidad" type="number" min="1" style="max-width: 80px" />
              <button class="btn peq" :disabled="!seleccion[f.prescripcion_id]?.producto_id" @click="dispensarFormula(f)">Entregar</button>
            </td>
          </tr>
          <tr v-if="!pend.formulas.length"><td class="suave">Sin fórmulas pendientes.</td></tr>
        </tbody>
      </table>
    </div>
    <div class="tarjeta">
      <h2>Órdenes de hospitalización activas</h2>
      <table>
        <tbody>
          <tr v-for="o in pend.ordenes" :key="o.orden_id">
            <td><strong>{{ o.descripcion }}</strong> {{ o.dosis }} {{ o.frecuencia }}<br /><small class="suave">{{ o.paciente }} · cama {{ o.cama }} · entregado {{ o.entregado }}</small></td>
            <td style="width: 360px" class="fila">
              <select v-model="seleccion[o.orden_id].producto_id" style="max-width: 200px">
                <option value="">Producto…</option><option v-for="p in productos" :key="p.id" :value="p.id">{{ p.nombre }} ({{ p.stock }})</option>
              </select>
              <input v-model.number="seleccion[o.orden_id].cantidad" type="number" min="1" style="max-width: 80px" />
              <button class="btn peq" :disabled="!seleccion[o.orden_id]?.producto_id" @click="dispensarOrden(o)">Entregar</button>
            </td>
          </tr>
          <tr v-if="!pend.ordenes.length"><td class="suave">Sin órdenes activas.</td></tr>
        </tbody>
      </table>
    </div>
  </template>

  <template v-if="pestana === 'inventario'">
    <div class="tarjeta">
      <table>
        <thead><tr><th>Producto</th><th>CUM</th><th>Stock</th><th>Precio</th><th>Lotes (vencimiento)</th></tr></thead>
        <tbody>
          <tr v-for="p in productos" :key="p.id">
            <td><strong>{{ p.nombre }}</strong></td><td>{{ p.cum || '—' }}</td>
            <td :style="{ color: p.stock <= p.stock_minimo ? 'var(--peligro)' : '' }">{{ p.stock }} <small class="suave">(mín {{ p.stock_minimo }})</small></td>
            <td>{{ pesos(p.precio_unitario) }}</td>
            <td><small v-for="l in p.lotes" :key="l.id" style="display: block">{{ l.numero }}: {{ l.cantidad }} · {{ l.vencimiento }}</small></td>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="rejilla-2">
      <form class="tarjeta" @submit.prevent="recibir">
        <h2>Entrada de mercancía</h2>
        <label>Producto <select v-model="entrada.producto_id" required><option v-for="p in productos" :key="p.id" :value="p.id">{{ p.nombre }}</option></select></label>
        <div class="rejilla" style="margin-top: .5rem">
          <label>Lote <input v-model="entrada.lote" required /></label>
          <label>Vencimiento <input v-model="entrada.vencimiento" type="date" required /></label>
          <label>Cantidad <input v-model.number="entrada.cantidad" type="number" min="1" required /></label>
          <label>Registro INVIMA <input v-model="entrada.registro_invima" /></label>
        </div>
        <button class="btn" style="margin-top: .8rem">Registrar entrada</button>
      </form>
      <form class="tarjeta" @submit.prevent="crear">
        <h2>Nuevo producto</h2>
        <div class="rejilla">
          <label>Nombre (DCI + concentración + forma) <input v-model="nuevo.nombre" required /></label>
          <label>CUM <input v-model="nuevo.cum" /></label>
          <label>Concentración <input v-model="nuevo.concentracion" /></label>
          <label>Forma farmacéutica <input v-model="nuevo.forma_farmaceutica" /></label>
          <label>Unidad <input v-model="nuevo.unidad" /></label>
          <label>Stock mínimo <input v-model.number="nuevo.stock_minimo" type="number" min="0" /></label>
          <label>Precio unitario <input v-model.number="nuevo.precio_unitario" type="number" min="0" /></label>
        </div>
        <label class="check"><input v-model="nuevo.controlado" type="checkbox" /> Medicamento de control especial</label>
        <label class="check"><input v-model="nuevo.cadena_frio" type="checkbox" /> Requiere cadena de frío</label>
        <button class="btn" style="margin-top: .8rem">Crear</button>
      </form>
    </div>
  </template>

  <div v-if="pestana === 'alertas'" class="rejilla">
    <div v-for="(lista, tipo) in alertas" :key="tipo" class="tarjeta">
      <h2>{{ { stock_bajo: 'Stock bajo', vencidos: 'Vencidos (retirar)', por_vencer: 'Vencen en 90 días' }[tipo] }}</h2>
      <p v-for="a in lista" :key="a.producto + (a.lote || '')" style="margin: .3rem 0">
        <strong>{{ a.producto }}</strong> <small class="suave">{{ a.lote ? `lote ${a.lote} · ${a.vencimiento} · ${a.cantidad} und` : `stock ${a.stock} / mín ${a.minimo}` }}</small>
      </p>
      <p v-if="!lista.length" class="suave">Sin alertas.</p>
    </div>
  </div>
</template>
