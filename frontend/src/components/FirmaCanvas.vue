<script setup lang="ts">
// Captura de firma manuscrita (dedo, lápiz o mouse) para consentimientos informados.
import { onMounted, ref } from 'vue'

const emit = defineEmits<{ firma: [png: string | null] }>()
const lienzo = ref<HTMLCanvasElement>()
let dibujando = false
let trazos = 0

function pos(e: PointerEvent) {
  const r = lienzo.value!.getBoundingClientRect()
  return [((e.clientX - r.left) * lienzo.value!.width) / r.width, ((e.clientY - r.top) * lienzo.value!.height) / r.height]
}
function inicio(e: PointerEvent) {
  dibujando = true
  const ctx = lienzo.value!.getContext('2d')!
  ctx.beginPath()
  ctx.moveTo(...(pos(e) as [number, number]))
  lienzo.value!.setPointerCapture(e.pointerId)
}
function mover(e: PointerEvent) {
  if (!dibujando) return
  const ctx = lienzo.value!.getContext('2d')!
  ctx.lineTo(...(pos(e) as [number, number]))
  ctx.stroke()
}
function fin() {
  if (!dibujando) return
  dibujando = false
  trazos++
  emit('firma', lienzo.value!.toDataURL('image/png'))
}
function limpiar() {
  const ctx = lienzo.value!.getContext('2d')!
  ctx.fillStyle = '#fff'
  ctx.fillRect(0, 0, lienzo.value!.width, lienzo.value!.height)
  trazos = 0
  emit('firma', null)
}
onMounted(() => {
  const ctx = lienzo.value!.getContext('2d')!
  ctx.lineWidth = 2.5
  ctx.lineCap = 'round'
  ctx.strokeStyle = '#111'
  limpiar()
})
defineExpose({ limpiar, vacia: () => trazos === 0 })
</script>

<template>
  <div>
    <canvas ref="lienzo" width="600" height="180" class="firma" @pointerdown="inicio" @pointermove="mover" @pointerup="fin" @pointerleave="fin" />
    <div class="fila entre"><small class="suave">Firme dentro del recuadro</small><button type="button" class="btn sec peq" @click="limpiar">Borrar</button></div>
  </div>
</template>

<style scoped>
.firma { width: 100%; max-width: 600px; height: auto; aspect-ratio: 600 / 180; border: 1px dashed var(--borde); border-radius: 8px; touch-action: none; background: #fff; }
</style>
