<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api/cliente'
import type { Atencion, Paciente } from '../api/tipos'
import { useAuth } from '../stores/auth'

const auth = useAuth()
const route = useRoute()
const router = useRouter()
const p = ref<Paciente | null>(null)
const historia = ref<Atencion[]>([])
const id = route.params.id as string

onMounted(async () => {
  p.value = (await api.get(`/pacientes/${id}`)).data
  if (auth.tiene('medico', 'enfermeria', 'auditor', 'admin')) historia.value = (await api.get(`/pacientes/${id}/historia`)).data
})

const fecha = (f: string) => new Date(f).toLocaleString('es-CO', { dateStyle: 'medium', timeStyle: 'short' })
function abrir(a: Atencion) {
  if (a.estado === 'borrador' && a.profesional.id === auth.usuario?.id) router.push(`/pacientes/${id}/atencion/${a.id}`)
  else router.push(`/atenciones/${a.id}`)
}
</script>

<template>
  <template v-if="p">
    <div class="fila entre">
      <div>
        <h1 style="margin: 0">{{ p.nombre_completo }}</h1>
        <p class="suave">{{ p.tipo_documento }} {{ p.numero_documento }} · {{ p.edad }} años · {{ { H: 'Hombre', M: 'Mujer', I: 'Indeterminado' }[p.sexo] }}</p>
      </div>
      <RouterLink v-if="auth.tiene('medico', 'enfermeria', 'admin')" class="btn" :to="`/pacientes/${p.id}/atencion`">+ Nueva atención</RouterLink>
    </div>

    <div v-if="p.alergias" class="alerta error"><strong>ALERGIAS:</strong> {{ p.alergias }}</div>
    <div v-if="!p.autoriza_tratamiento_datos" class="alerta aviso">El paciente no ha autorizado el tratamiento de datos personales (Ley 1581 de 2012).</div>

    <div class="tarjeta">
      <h2>Datos del paciente</h2>
      <div class="rejilla">
        <div><div class="suave">Fecha de nacimiento</div>{{ p.fecha_nacimiento }}</div>
        <div><div class="suave">Teléfono</div>{{ p.telefono || '—' }}</div>
        <div><div class="suave">Correo</div>{{ p.email || '—' }}</div>
        <div><div class="suave">Dirección</div>{{ p.direccion || '—' }}</div>
        <div><div class="suave">Municipio</div>{{ p.cod_municipio_residencia }} ({{ p.zona_territorial === '01' ? 'rural' : 'urbana' }})</div>
        <div><div class="suave">EPS / régimen</div>{{ p.cod_eapb || '—' }} / {{ p.tipo_usuario }}</div>
        <div><div class="suave">Grupo sanguíneo</div>{{ p.grupo_sanguineo || '—' }}</div>
        <div><div class="suave">Acompañante</div>{{ p.acompanante_nombre || '—' }} {{ p.acompanante_telefono || '' }}</div>
      </div>
    </div>

    <div class="tarjeta" v-if="auth.tiene('medico', 'enfermeria', 'auditor', 'admin')">
      <h2>Historia clínica ({{ historia.length }} folios)</h2>
      <table>
        <thead><tr><th>Folio</th><th>Fecha</th><th>Tipo</th><th>Motivo</th><th>Diagnóstico principal</th><th>Profesional</th><th>Estado</th></tr></thead>
        <tbody>
          <tr v-for="a in historia" :key="a.id" class="clic" @click="abrir(a)">
            <td>#{{ a.consecutivo }}</td>
            <td>{{ fecha(a.fecha_inicio) }}</td>
            <td style="text-transform: capitalize">{{ a.tipo }}</td>
            <td>{{ a.motivo_consulta }}</td>
            <td>{{ a.diagnosticos[0] ? `${a.diagnosticos[0].codigo_cie10} ${a.diagnosticos[0].descripcion}` : '—' }}</td>
            <td>{{ a.profesional.nombres }} {{ a.profesional.apellidos }}</td>
            <td><span :class="['etiqueta', a.estado]">{{ a.estado }}</span></td>
          </tr>
          <tr v-if="!historia.length"><td colspan="7" class="suave">Sin atenciones registradas.</td></tr>
        </tbody>
      </table>
    </div>
  </template>
</template>
