<script setup lang="ts">
// Página pública que abre el código QR de los documentos. No muestra datos clínicos.
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api/cliente'

const route = useRoute()
const r = ref<{ valido: boolean; mensaje: string; institucion: string; fecha_firma?: string; tipo: string } | null>(null)
onMounted(async () => {
  r.value = (await api.get(`/publico/verificar/${route.params.tipo}/${route.params.id}`, { params: { h: route.query.h } })).data
})
</script>

<template>
  <div class="fondo">
    <div class="tarjeta caja" v-if="r">
      <div :class="['icono', r.valido ? 'ok' : 'mal']">{{ r.valido ? '✓' : '✕' }}</div>
      <h1>{{ r.valido ? 'Documento auténtico' : 'No verificado' }}</h1>
      <p>{{ r.mensaje }}</p>
      <p class="suave">Institución: {{ r.institucion }}<br />Tipo: {{ r.tipo }}<br v-if="r.fecha_firma" />{{ r.fecha_firma ? `Firmado: ${r.fecha_firma}` : '' }}</p>
      <p class="suave nota">Esta verificación no revela información clínica ni personal.</p>
    </div>
  </div>
</template>

<style scoped>
.fondo { min-height: 100vh; display: grid; place-items: center; padding: 1rem; background: var(--fondo); }
.caja { max-width: 440px; text-align: center; }
.icono { width: 72px; height: 72px; border-radius: 50%; display: grid; place-items: center; font-size: 2.2rem; margin: 0 auto 1rem; color: #fff; }
.icono.ok { background: var(--exito); }
.icono.mal { background: var(--peligro); }
.nota { font-size: .75rem; }
</style>
