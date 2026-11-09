<script setup lang="ts">
// Área de texto clínica con dictado por voz.
import VozDictado from './VozDictado.vue'

defineProps<{ etiqueta: string; placeholder?: string }>()
const modelo = defineModel<string | null | undefined>()
const agregar = (t: string) => (modelo.value = modelo.value ? `${modelo.value} ${t}` : t)
</script>

<template>
  <label class="campo">
    <span class="fila entre"><span>{{ etiqueta }}</span><VozDictado @texto="agregar" /></span>
    <textarea v-model="modelo" :placeholder="placeholder" />
  </label>
</template>

<style scoped>
.campo { margin-top: .75rem; }
</style>
