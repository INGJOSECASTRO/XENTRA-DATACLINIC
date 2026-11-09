<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api/cliente'
import { useAuth } from '../stores/auth'

const auth = useAuth()
const stats = ref<Record<string, number>>({})
const cadena = ref<{ valida: boolean; total_bloques: number; detalle?: string } | null>(null)

onMounted(async () => {
  stats.value = (await api.get('/auditoria/estadisticas')).data
  if (auth.tiene('auditor', 'admin')) cadena.value = (await api.get('/auditoria/verificar-cadena')).data
})
</script>

<template>
  <h1>Bienvenido(a), {{ auth.usuario?.nombres }}</h1>
  <div class="rejilla">
    <div class="tarjeta"><div class="suave">Pacientes</div><div class="kpi">{{ stats.pacientes ?? '—' }}</div></div>
    <div class="tarjeta"><div class="suave">Atenciones firmadas</div><div class="kpi">{{ stats.atenciones_firmadas ?? '—' }}</div></div>
    <div class="tarjeta"><div class="suave">Borradores pendientes</div><div class="kpi">{{ stats.atenciones_borrador ?? '—' }}</div></div>
    <div class="tarjeta"><div class="suave">Bloques en el ledger</div><div class="kpi">{{ stats.bloques_ledger ?? '—' }}</div></div>
  </div>
  <div v-if="cadena" :class="['alerta', cadena.valida ? 'ok' : 'error']">
    {{ cadena.valida ? `Cadena de auditoría íntegra (${cadena.total_bloques} bloques verificados).` : `ALERTA DE INTEGRIDAD: ${cadena.detalle}` }}
  </div>
  <div class="tarjeta">
    <h2>Accesos rápidos</h2>
    <div class="fila">
      <RouterLink class="btn" to="/pacientes">Buscar / registrar paciente</RouterLink>
      <RouterLink v-if="auth.tiene('facturacion', 'admin')" class="btn sec" to="/rips">Generar RIPS</RouterLink>
      <RouterLink v-if="auth.tiene('auditor', 'admin')" class="btn sec" to="/auditoria">Auditoría</RouterLink>
    </div>
  </div>
</template>
