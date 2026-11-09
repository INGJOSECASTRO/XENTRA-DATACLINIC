<script setup lang="ts">
// Buscador CIE-10 con autocompletado por código o descripción.
import { ref, watch } from 'vue'
import { api } from '../api/cliente'
import type { CIE10 } from '../api/tipos'

const emit = defineEmits<{ elegir: [c: CIE10] }>()
const q = ref('')
const resultados = ref<CIE10[]>([])
let temporizador: ReturnType<typeof setTimeout> | undefined

watch(q, (valor) => {
  clearTimeout(temporizador)
  if (valor.trim().length < 2) {
    resultados.value = []
    return
  }
  temporizador = setTimeout(async () => {
    resultados.value = (await api.get('/cie10', { params: { q: valor, limite: 10 } })).data
  }, 250)
})

function elegir(c: CIE10) {
  emit('elegir', c)
  q.value = ''
  resultados.value = []
}
</script>

<template>
  <div class="selector">
    <input v-model="q" placeholder="Buscar CIE-10 por código (I10) o texto (hipertensión)…" />
    <ul v-if="resultados.length">
      <li v-for="c in resultados" :key="c.codigo" @click="elegir(c)"><strong>{{ c.codigo }}</strong> {{ c.descripcion }}</li>
    </ul>
  </div>
</template>

<style scoped>
.selector { position: relative; }
ul { position: absolute; z-index: 10; left: 0; right: 0; margin: .2rem 0 0; padding: 0; list-style: none; background: #fff; border: 1px solid var(--borde); border-radius: 8px; max-height: 260px; overflow: auto; box-shadow: 0 8px 24px rgba(0,0,0,.08); }
li { padding: .5rem .7rem; font-size: .85rem; cursor: pointer; }
li:hover { background: var(--primario-claro); }
</style>
