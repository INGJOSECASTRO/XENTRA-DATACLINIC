<script setup lang="ts">
// Lista desplegable alimentada por las tablas de referencia (SISPRO) del backend.
import { onMounted, ref } from 'vue'
import { api } from '../api/cliente'
import type { ItemCatalogo } from '../api/tipos'

const props = defineProps<{ tipo: string; vacio?: string }>()
const modelo = defineModel<string | number | null>()
const items = ref<ItemCatalogo[]>([])
const cache: Record<string, ItemCatalogo[]> = (window as unknown as { __cat?: Record<string, ItemCatalogo[]> }).__cat ||= {}

onMounted(async () => {
  if (!cache[props.tipo]) cache[props.tipo] = (await api.get(`/catalogos/${props.tipo}`, { params: { limite: 500 } })).data
  items.value = cache[props.tipo]
})
</script>

<template>
  <select v-model="modelo">
    <option v-if="vacio !== undefined" :value="null">{{ vacio || '—' }}</option>
    <option v-for="i in items" :key="i.codigo" :value="tipo === 'servicio' ? Number(i.codigo) : i.codigo">{{ i.codigo }} · {{ i.descripcion }}</option>
  </select>
</template>
