<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api/cliente'
import type { Bloque } from '../api/tipos'

const bloques = ref<Bloque[]>([])
const accion = ref('')
const cadena = ref<{ valida: boolean; total_bloques: number; detalle?: string; bloque_con_error?: number; ultimo_hash?: string } | null>(null)
const verificando = ref(false)
const anclajes = ref<{ id: number; bloque: number; fecha: string; proveedor: string; estado: string; coincide: boolean; hash: string }[]>([])
async function cargarAnclajes() {
  anclajes.value = (await api.get('/auditoria/anclajes')).data
}
async function anclar() {
  const { data } = await api.post('/auditoria/anclar')
  alert(`Bloque ${data.bloque} anclado (${data.proveedor}): ${data.estado}`)
  await cargarAnclajes()
}

async function cargar() {
  bloques.value = (await api.get('/auditoria/ledger', { params: { accion: accion.value || undefined, limite: 200 } })).data
}
async function verificar() {
  verificando.value = true
  cadena.value = (await api.get('/auditoria/verificar-cadena')).data
  verificando.value = false
}
const fecha = (f: string) => new Date(f).toLocaleString('es-CO')
onMounted(() => { cargar(); cargarAnclajes() })
</script>

<template>
  <h1>Seguridad blockchain · Libro mayor inmutable</h1>
  <div class="tarjeta">
    <div class="fila entre">
      <p class="suave" style="max-width: 640px; margin: 0">
        Cada acción (accesos, creación, firma, RIPS) genera un bloque encadenado con SHA-256 y firmado con HMAC.
        Si alguien altera o borra un registro, la verificación identifica el bloque exacto.
      </p>
      <button class="btn" :disabled="verificando" @click="verificar">{{ verificando ? 'Verificando…' : 'Verificar cadena completa' }}</button>
    </div>
    <div v-if="cadena" :class="['alerta', cadena.valida ? 'ok' : 'error']" style="margin-top: .75rem">
      <template v-if="cadena.valida">Cadena íntegra · {{ cadena.total_bloques }} bloques · último hash <span class="mono">{{ cadena.ultimo_hash }}</span></template>
      <template v-else>ALTERACIÓN DETECTADA en el bloque #{{ cadena.bloque_con_error }}: {{ cadena.detalle }}</template>
    </div>
  </div>
  <div class="tarjeta">
    <div class="fila entre">
      <div>
        <h2 style="margin: 0">Anclaje externo</h2>
        <p class="suave" style="margin: .3rem 0">Publica solo el hash del último bloque (sello de tiempo). Ver docs/04-seguridad-blockchain.md.</p>
      </div>
      <button class="btn sec" @click="anclar">Anclar ahora</button>
    </div>
    <table v-if="anclajes.length">
      <tbody>
        <tr v-for="a in [...anclajes].reverse().slice(0, 10)" :key="a.id">
          <td>{{ fecha(a.fecha) }}</td><td>Bloque #{{ a.bloque }}</td><td>{{ a.proveedor }} · {{ a.estado }}</td>
          <td><span :class="['etiqueta', a.coincide ? 'firmada' : 'borrador']">{{ a.coincide ? 'coincide' : 'NO coincide' }}</span></td>
          <td class="mono">{{ a.hash.slice(0, 16) }}…</td>
        </tr>
      </tbody>
    </table>
  </div>
  <div class="tarjeta">
    <div class="fila" style="margin-bottom: .75rem">
      <select v-model="accion" style="max-width: 280px" @change="cargar">
        <option value="">Todas las acciones</option>
        <option v-for="x in ['LOGIN', 'LOGIN_FALLIDO', 'PACIENTE_CREADO', 'CONSULTA_PACIENTE', 'CONSULTA_HC', 'CONSULTA_ATENCION', 'ATENCION_CREADA', 'ATENCION_FIRMADA', 'NOTA_ACLARATORIA', 'RIPS_GENERADO', 'USUARIO_CREADO', 'MFA_FALLIDO', 'FACTURA_EMITIDA', 'DISPENSACION', 'TRIAGE', 'HOSPITALIZACION_INGRESO', 'HOSPITALIZACION_EGRESO', 'CONSENTIMIENTO', 'RESULTADO_VALIDADO', 'FHIR_EXPORTACION', 'EVENTO_SIVIGILA', 'PORTAL_EXPORTACION']" :key="x">{{ x }}</option>
      </select>
    </div>
    <table>
      <thead><tr><th>#</th><th>Fecha</th><th>Acción</th><th>Entidad</th><th>Usuario</th><th>IP</th><th>Hash</th></tr></thead>
      <tbody>
        <tr v-for="b in bloques" :key="b.id">
          <td>{{ b.id }}</td>
          <td>{{ fecha(b.marca_tiempo) }}</td>
          <td><strong>{{ b.accion }}</strong></td>
          <td>{{ b.entidad }}<br /><span class="mono suave">{{ b.entidad_id }}</span></td>
          <td class="mono">{{ b.usuario_id?.slice(0, 8) || '—' }}</td>
          <td>{{ b.ip_origen || '—' }}</td>
          <td class="mono" :title="`Anterior: ${b.hash_anterior}`">{{ b.hash.slice(0, 16) }}…</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
