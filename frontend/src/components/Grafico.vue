<script setup lang="ts">
// Gráfico SVG sin librerías externas: barras horizontales o líneas.
import { computed } from 'vue'

const props = defineProps<{ filas: Record<string, unknown>[]; etiqueta: (f: Record<string, unknown>) => string; medida: string; tipo: string }>()
const datos = computed(() => props.filas.slice(0, 30).map((f) => ({ texto: props.etiqueta(f), valor: Number(f[props.medida] ?? 0) })))
const maximo = computed(() => Math.max(1, ...datos.value.map((d) => d.valor)))
const ancho = 640
const alto = 220
const puntos = computed(() => datos.value.map((d, i) =>
  `${40 + (i * (ancho - 60)) / Math.max(1, datos.value.length - 1)},${alto - 30 - ((alto - 50) * d.valor) / maximo.value}`).join(' '))
const fmt = (v: number) => v.toLocaleString('es-CO', { maximumFractionDigits: 1 })
</script>

<template>
  <div v-if="tipo === 'barras'" class="barras">
    <div v-for="d in datos" :key="d.texto" class="fila-barra">
      <span class="etq" :title="d.texto">{{ d.texto || '(sin dato)' }}</span>
      <span class="pista"><span class="barra" :style="{ width: `${(100 * d.valor) / maximo}%` }" /></span>
      <span class="val">{{ fmt(d.valor) }}</span>
    </div>
  </div>
  <svg v-else-if="tipo === 'lineas'" :viewBox="`0 0 ${ancho} ${alto}`" class="lineas" role="img" aria-label="Gráfico de líneas">
    <line x1="40" :y1="alto - 30" :x2="ancho - 20" :y2="alto - 30" stroke="var(--borde)" />
    <polyline :points="puntos" fill="none" stroke="var(--primario)" stroke-width="2.5" />
    <g v-for="(d, i) in datos" :key="d.texto">
      <circle :cx="40 + (i * (ancho - 60)) / Math.max(1, datos.length - 1)" :cy="alto - 30 - ((alto - 50) * d.valor) / maximo" r="3.5" fill="var(--primario)">
        <title>{{ d.texto }}: {{ fmt(d.valor) }}</title>
      </circle>
      <text v-if="datos.length <= 12" :x="40 + (i * (ancho - 60)) / Math.max(1, datos.length - 1)" :y="alto - 12" font-size="10" text-anchor="middle" fill="currentColor">{{ d.texto.slice(0, 10) }}</text>
    </g>
    <text x="4" y="24" font-size="10" fill="currentColor">{{ fmt(maximo) }}</text>
  </svg>
</template>

<style scoped>
.fila-barra { display: grid; grid-template-columns: minmax(120px, 34%) 1fr 70px; gap: .5rem; align-items: center; font-size: .82rem; margin: .2rem 0; }
.etq { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pista { background: var(--fondo); border-radius: 4px; height: 14px; }
.barra { display: block; height: 100%; background: var(--primario); border-radius: 4px; min-width: 2px; }
.val { text-align: right; font-variant-numeric: tabular-nums; }
.lineas { width: 100%; height: auto; color: var(--texto-suave); }
</style>
