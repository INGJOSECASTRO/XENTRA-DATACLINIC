<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { abrirArchivo, api, pesos } from '../api/cliente'
import { useAuth } from '../stores/auth'

const auth = useAuth()
const hoy = new Date()
const desde = ref(new Date(hoy.getTime() - 30 * 86400000).toLocaleDateString('en-CA'))
const hasta = ref(hoy.toLocaleDateString('en-CA'))
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const ind = ref<any>(null)
const sivigila = ref<{ fecha: string; evento: string; cie10: string; documento: string; paciente: string; municipio: string }[]>([])

async function cargar() {
  const params = { desde: desde.value, hasta: hasta.value }
  if (auth.tiene('admin', 'auditor', 'auditor_sistemas')) ind.value = (await api.get('/reportes/indicadores', { params })).data
  if (auth.tiene('admin', 'auditor', 'medico')) sivigila.value = (await api.get('/reportes/sivigila', { params })).data
}
const fmt = (v: number | null | undefined, suf = '') => (v === null || v === undefined ? '—' : `${v}${suf}`)
onMounted(cargar)
</script>

<template>
  <div class="fila entre">
    <h1>Indicadores y reportes</h1>
    <div class="fila"><input v-model="desde" type="date" /><input v-model="hasta" type="date" /><button class="btn" @click="cargar">Actualizar</button></div>
  </div>
  <template v-if="ind">
    <div class="rejilla">
      <div class="tarjeta"><div class="suave">Oportunidad cita medicina general</div><div class="kpi">{{ fmt(ind.agenda.oportunidad_medicina_general_dias, ' d') }}</div><small class="suave">Res. 256/2016</small></div>
      <div class="tarjeta"><div class="suave">Inasistencia a citas</div><div class="kpi">{{ fmt(ind.agenda.inasistencia_pct, '%') }}</div></div>
      <div class="tarjeta"><div class="suave">Triage II atendido ≤ 30 min</div><div class="kpi">{{ fmt(ind.urgencias.triage_ii_atendidos_en_30_min_pct, '%') }}</div></div>
      <div class="tarjeta"><div class="suave">Ocupación de camas</div><div class="kpi">{{ fmt(ind.hospitalizacion.ocupacion_actual_pct, '%') }}</div></div>
      <div class="tarjeta"><div class="suave">Estancia promedio</div><div class="kpi">{{ fmt(ind.hospitalizacion.estancia_promedio_dias, ' d') }}</div></div>
      <div class="tarjeta"><div class="suave">Atenciones firmadas</div><div class="kpi">{{ ind.consulta.atenciones_firmadas }}</div></div>
      <div class="tarjeta"><div class="suave">Dx con apoyo de IA</div><div class="kpi">{{ fmt(ind.consulta.sugeridos_por_ia_pct, '%') }}</div></div>
      <div class="tarjeta"><div class="suave">Validado en MUV</div><div class="kpi" style="font-size: 1.3rem">{{ pesos(ind.facturacion.valor_validado_muv) }}</div></div>
    </div>
    <div class="rejilla-2">
      <div class="tarjeta"><h2>Primeros diagnósticos</h2><table><tbody><tr v-for="[dx, n] in ind.consulta.primeros_diagnosticos" :key="dx"><td>{{ dx }}</td><td>{{ n }}</td></tr></tbody></table></div>
      <div class="tarjeta"><h2>Atenciones por profesional</h2><table><tbody><tr v-for="[p, n] in ind.consulta.por_profesional" :key="p"><td>{{ p }}</td><td>{{ n }}</td></tr></tbody></table>
        <h3 style="margin-top: 1rem">Urgencias por nivel de triage</h3><p>{{ Object.entries(ind.urgencias.por_nivel).map(([k, v]) => `Nivel ${k}: ${v}`).join(' · ') || '—' }}</p></div>
    </div>
  </template>
  <div v-if="auth.tiene('admin', 'auditor', 'medico')" class="tarjeta">
    <div class="fila entre">
      <h2>Eventos de notificación obligatoria (SIVIGILA)</h2>
      <button class="btn sec" @click="abrirArchivo('/reportes/sivigila', { desde, hasta, formato: 'csv' }, 'sivigila.csv')">Descargar CSV</button>
    </div>
    <table>
      <thead><tr><th>Fecha</th><th>Evento</th><th>CIE-10</th><th>Paciente</th><th>Municipio</th></tr></thead>
      <tbody>
        <tr v-for="s in sivigila" :key="s.fecha + s.documento + s.cie10"><td>{{ s.fecha }}</td><td><strong>{{ s.evento }}</strong></td><td>{{ s.cie10 }}</td><td>{{ s.paciente }} · {{ s.documento }}</td><td>{{ s.municipio }}</td></tr>
        <tr v-if="!sivigila.length"><td class="suave">Sin casos en el periodo.</td></tr>
      </tbody>
    </table>
  </div>
</template>
