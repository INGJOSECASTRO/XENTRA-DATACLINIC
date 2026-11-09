<script setup lang="ts">
// Dictado por voz (Web Speech API del navegador, español de Colombia). Funciona en Chrome y Edge.
// El audio lo procesa el navegador/servicio del fabricante: informe al paciente según su política de datos.
import { ref } from 'vue'

const emit = defineEmits<{ texto: [t: string] }>()
const escuchando = ref(false)
type Reconocedor = { lang: string; continuous: boolean; interimResults: boolean; start(): void; stop(): void;
  onresult: (e: { resultIndex: number; results: { isFinal: boolean; 0: { transcript: string } }[] }) => void; onend: () => void }
const Clase = (window as unknown as { SpeechRecognition?: new () => Reconocedor; webkitSpeechRecognition?: new () => Reconocedor })
const Ctor = Clase.SpeechRecognition || Clase.webkitSpeechRecognition
let rec: Reconocedor | null = null

function alternar() {
  if (!Ctor) return alert('Su navegador no soporta dictado por voz. Use Chrome o Edge.')
  if (escuchando.value) return rec?.stop()
  rec = new Ctor()
  rec.lang = 'es-CO'
  rec.continuous = true
  rec.interimResults = false
  rec.onresult = (e) => {
    for (let i = e.resultIndex; i < e.results.length; i++) if (e.results[i].isFinal) emit('texto', e.results[i][0].transcript.trim())
  }
  rec.onend = () => (escuchando.value = false)
  rec.start()
  escuchando.value = true
}
</script>

<template>
  <button type="button" class="btn sec peq voz" :class="{ activo: escuchando }" :title="escuchando ? 'Detener dictado' : 'Dictar por voz'" @click="alternar">
    {{ escuchando ? '■ Detener' : '🎤 Dictar' }}
  </button>
</template>

<style scoped>
.voz.activo { background: var(--peligro-claro); color: var(--peligro); border-color: var(--peligro); }
</style>
