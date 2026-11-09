<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { abrirArchivo, api, fechaHora } from '../api/cliente'

/* eslint-disable @typescript-eslint/no-explicit-any */
const resumen = ref<any>(null)
const atenciones = ref<any[]>([])
const citas = ref<any[]>([])
const resultados = ref<any[]>([])
const accesos = ref<any[]>([])
const pestana = ref('resumen')

onMounted(async () => {
  ;[resumen.value, atenciones.value, citas.value, resultados.value, accesos.value] = await Promise.all(
    ['resumen', 'atenciones', 'citas', 'resultados', 'accesos'].map((r) => api.get(`/portal/${r}`).then((x) => x.data)))
})
const exportar = () => abrirArchivo('/portal/exportar', undefined, 'mi_historia_clinica_fhir.json')
</script>

<template>
  <template v-if="resumen">
    <div class="fila entre">
      <div><h1 style="margin: 0">Hola, {{ resumen.paciente.nombre }}</h1><p class="suave">{{ resumen.paciente.documento }} · EPS {{ resumen.paciente.eps || '—' }}</p></div>
      <button class="btn sec" @click="exportar">Descargar toda mi historia (FHIR)</button>
    </div>
    <div class="fila" style="margin-bottom: 1rem; gap: .4rem">
      <button v-for="p in ['resumen', 'atenciones', 'citas', 'resultados', 'accesos']" :key="p" :class="['btn peq', pestana === p ? '' : 'sec']" @click="pestana = p">
        {{ { resumen: 'Mi resumen', atenciones: 'Mis consultas', citas: 'Mis citas', resultados: 'Mis resultados', accesos: '¿Quién vio mi historia?' }[p] }}
      </button>
    </div>

    <div v-if="pestana === 'resumen'" class="rejilla-2">
      <div class="tarjeta">
        <h2>Alergias</h2><p>{{ resumen.estructurado.alergias }}</p>
        <h2>Diagnósticos del último año</h2>
        <ul><li v-for="p in resumen.estructurado.problemas_activos" :key="p.codigo">{{ p.descripcion }} ({{ p.codigo }})</li></ul>
        <p v-if="!resumen.estructurado.problemas_activos.length" class="suave">Sin diagnósticos registrados.</p>
      </div>
      <div class="tarjeta">
        <h2>Medicamentos recientes</h2>
        <ul><li v-for="m in resumen.estructurado.medicamentos_recientes" :key="m">{{ m }}</li></ul>
        <h2>Próximas citas</h2>
        <p v-for="c in citas.filter((x) => ['programada', 'confirmada'].includes(x.estado))" :key="c.id">{{ fechaHora(c.inicio) }} · {{ c.profesional }}</p>
      </div>
    </div>

    <div v-if="pestana === 'atenciones'" class="tarjeta">
      <table><tbody>
        <tr v-for="a in atenciones" :key="a.id">
          <td>{{ fechaHora(a.fecha) }}<br /><small class="suave">{{ a.profesional }}</small></td>
          <td><strong>{{ a.motivo }}</strong><br /><small>{{ a.diagnosticos.join(' · ') }}</small><div v-if="a.plan" class="suave">{{ a.plan }}</div></td>
          <td style="width: 200px">
            <button class="btn sec peq" @click="abrirArchivo(`/portal/atenciones/${a.id}/pdf`)">Historia PDF</button>
            <button v-if="a.tiene_formula" class="btn sec peq" @click="abrirArchivo(`/portal/atenciones/${a.id}/pdf`, { documento: 'formula' })">Fórmula</button>
          </td>
        </tr>
      </tbody></table>
    </div>

    <div v-if="pestana === 'citas'" class="tarjeta">
      <table><tbody>
        <tr v-for="c in citas" :key="c.id">
          <td>{{ fechaHora(c.inicio) }}</td><td>{{ c.profesional }}</td><td>{{ c.estado }}</td>
          <td><a v-if="c.sala_virtual" class="btn peq" :href="c.sala_virtual" target="_blank" rel="noopener">Entrar a la teleconsulta</a></td>
        </tr>
      </tbody></table>
    </div>

    <div v-if="pestana === 'resultados'" class="tarjeta">
      <div v-for="r in resultados" :key="r.id" style="border-bottom: 1px solid var(--borde); padding: .6rem 0">
        <strong>{{ r.examen }}</strong> · <small class="suave">{{ fechaHora(r.fecha) }}</small>
        <div v-for="v in r.resultados || []" :key="v.analito" :style="{ color: v.anormal ? 'var(--peligro)' : '' }">{{ v.analito }}: <strong>{{ v.valor }}</strong> {{ v.unidad }} <small class="suave">(ref. {{ v.referencia }})</small></div>
        <div v-if="r.informe" class="suave">{{ r.informe }}</div>
      </div>
      <p v-if="!resultados.length" class="suave">Aún no tiene resultados.</p>
    </div>

    <div v-if="pestana === 'accesos'" class="tarjeta">
      <p class="suave">Por transparencia (Ley 1581 de 2012) puede ver quién consultó su historia clínica. Si encuentra un acceso que no reconoce, comuníquese con la institución.</p>
      <table><tbody><tr v-for="(a, i) in accesos" :key="i"><td>{{ fechaHora(a.fecha) }}</td><td>{{ a.persona }}</td><td>{{ a.rol }}</td><td class="suave">{{ a.accion }}</td></tr></tbody></table>
    </div>
  </template>
</template>
