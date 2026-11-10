<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, fechaHora } from '../api/cliente'
import { useAuth } from '../stores/auth'

const auth = useAuth()
const stats = ref<Record<string, number>>({})
const pendientesRefrendo = ref<{ id: string; paciente_id: string; consecutivo: number; fecha_inicio: string; motivo_consulta: string;
  profesional: { nombres: string; apellidos: string } }[]>([])
const cadena = ref<{ valida: boolean; total_bloques: number; folios_sellados: number; ultimo_anclaje: string | null; detalle?: string } | null>(null)

onMounted(async () => {
  ;[stats.value, cadena.value] = await Promise.all([api.get('/auditoria/estadisticas').then((r) => r.data),
    api.get('/auditoria/estado-cadena').then((r) => r.data)])
  if (auth.tiene('medico', 'admin')) pendientesRefrendo.value = (await api.get('/atenciones/refrendo/pendientes')).data
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

  <div v-if="cadena" :class="['tarjeta', 'blockchain', cadena.valida ? 'ok' : 'mal']">
    <div class="fila entre">
      <div>
        <h2 style="margin: 0">🔐 Seguridad blockchain: {{ cadena.valida ? 'cadena íntegra' : 'ALERTA DE INTEGRIDAD' }}</h2>
        <p class="suave" style="margin: .4rem 0">
          Cada acción (accesos, firmas, RIPS, facturas, dispensaciones) queda en un bloque encadenado con SHA-256 y firmado con HMAC.
          Si alguien altera un registro, la cadena se rompe y el sistema lo detecta.
        </p>
        <p style="margin: 0"><strong>{{ cadena.total_bloques }}</strong> bloques verificados ·
          <strong>{{ cadena.folios_sellados }}</strong> folios clínicos sellados ·
          último anclaje externo: {{ fechaHora(cadena.ultimo_anclaje) }}</p>
        <p v-if="!cadena.valida" class="alerta error" style="margin-top: .5rem">{{ cadena.detalle }}</p>
      </div>
      <RouterLink v-if="auth.tiene('auditor', 'admin', 'auditor_sistemas', 'admin_tecnico')" class="btn" to="/auditoria">Ver cadena y verificar</RouterLink>
    </div>
  </div>

  <div v-if="pendientesRefrendo.length" class="tarjeta" style="border-left: 5px solid var(--aviso)">
    <h2>Registros de estudiantes pendientes de su refrendo ({{ pendientesRefrendo.length }})</h2>
    <table><tbody>
      <tr v-for="p in pendientesRefrendo" :key="p.id">
        <td>{{ fechaHora(p.fecha_inicio) }}</td><td>{{ p.motivo_consulta }}</td>
        <td>Estudiante: {{ p.profesional.nombres }} {{ p.profesional.apellidos }}</td>
        <td><RouterLink class="btn peq" :to="`/pacientes/${p.paciente_id}/atencion/${p.id}`">Revisar y refrendar</RouterLink></td>
      </tr>
    </tbody></table>
  </div>

  <div class="tarjeta">
    <h2>Accesos rápidos</h2>
    <div class="fila">
      <RouterLink v-if="auth.tiene('admin', 'medico', 'enfermeria', 'estudiante', 'admisiones', 'auditor')" class="btn" to="/pacientes">Buscar / registrar paciente</RouterLink>
      <RouterLink v-if="auth.tiene('admin_tecnico')" class="btn" to="/usuarios">Gestionar usuarios</RouterLink>
      <RouterLink v-if="auth.tiene('facturacion', 'admin')" class="btn sec" to="/rips">Generar y validar RIPS</RouterLink>
      <RouterLink v-if="auth.tiene('facturacion', 'admin', 'auditor')" class="btn sec" to="/facturacion">Facturación electrónica (DIAN + RIPS + MUV)</RouterLink>
      <RouterLink v-if="auth.tiene('auditor', 'admin', 'auditor_sistemas', 'admin_tecnico')" class="btn sec" to="/auditoria">Seguridad blockchain</RouterLink>
    </div>
    <p v-if="auth.tiene('medico', 'enfermeria')" class="suave" style="margin-top: .8rem">
      Al firmar una atención verá en el folio el recuadro <strong>"Integridad (sello blockchain)"</strong> con su huella SHA-256 y el botón
      <strong>Verificar integridad</strong>. Los RIPS los genera el área de facturación a partir de sus atenciones firmadas.
    </p>
  </div>
</template>

<style scoped>
.blockchain.ok { border-left: 5px solid var(--exito); }
.blockchain.mal { border-left: 5px solid var(--peligro); }
</style>
