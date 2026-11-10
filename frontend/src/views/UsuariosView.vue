<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { api, mensajeError } from '../api/cliente'
import type { Usuario } from '../api/tipos'
import { useAuth } from '../stores/auth'

const auth = useAuth()
const usuarios = ref<Usuario[]>([])
const error = ref('')
const ok = ref('')
const filtro = ref('')

// Roles según los protocolos de seguridad (docs/manuales/04-PROTOCOLOS-SEGURIDAD.md)
const ROLES: Record<string, { nombre: string; quien: string; registro: boolean; historia: boolean }> = {
  medico: { nombre: 'Médico(a)', quien: 'Médicos generales y especialistas', registro: true, historia: true },
  enfermeria: { nombre: 'Enfermería', quien: 'Enfermeros profesionales y auxiliares de enfermería', registro: true, historia: true },
  estudiante: { nombre: 'Estudiante / interno / residente', quien: 'Registra en borrador; firma el docente (refrendo)', registro: false, historia: true },
  admisiones: { nombre: 'Admisiones y agenda', quien: 'Recepción, citas, registro de pacientes', registro: false, historia: false },
  facturacion: { nombre: 'Facturación', quien: 'Facturadores y cuentas médicas', registro: false, historia: false },
  farmacia: { nombre: 'Farmacia', quien: 'Químico farmacéutico o regente', registro: true, historia: false },
  laboratorio: { nombre: 'Laboratorio (valida)', quien: 'Bacteriólogos y radiólogos', registro: true, historia: false },
  auxiliar_laboratorio: { nombre: 'Auxiliar de laboratorio', quien: 'Toma muestras y digita resultados, no valida', registro: false, historia: false },
  auditor: { nombre: 'Auditor(a) médico', quien: 'Profesional de la salud: auditoría de HC, cuentas y calidad', registro: true, historia: true },
  auditor_sistemas: { nombre: 'Auditor(a) de sistemas', quien: 'Seguridad de la información; sin historia clínica', registro: false, historia: false },
  admin_tecnico: { nombre: 'Administrador técnico', quien: 'Sistemas: usuarios, sedes, módulos, soporte; sin historia clínica', registro: false, historia: false },
  admin: { nombre: 'Administrador (dirección)', quien: 'Dirección médico-administrativa; acceso total. Máximo 2', registro: false, historia: true },
}
const rolesDisponibles = computed(() => Object.entries(ROLES).filter(([k]) => k !== 'admin' || auth.tiene('admin')))
const vacio = () => ({ tipo_documento: 'CC', numero_documento: '', nombres: '', apellidos: '', email: '', password: '', rol: 'medico',
  registro_profesional: '', especialidad: '' })
const form = reactive(vacio())
const rolActual = computed(() => ROLES[form.rol])
const visibles = computed(() => usuarios.value.filter((u) => !filtro.value || u.rol === filtro.value))

async function cargar() {
  usuarios.value = (await api.get('/auth/usuarios')).data
}
function generarClave() {
  const a = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789'
  const r = crypto.getRandomValues(new Uint32Array(12))
  form.password = Array.from(r, (x) => a[x % a.length]).join('') + '7a*'
}
async function crear() {
  error.value = ok.value = ''
  try {
    const clave = form.password
    await api.post('/auth/usuarios', { ...form, registro_profesional: form.registro_profesional || null, especialidad: form.especialidad || null })
    ok.value = `Usuario ${form.email} creado. Clave temporal: ${clave} — entréguela por un canal seguro; el sistema le pedirá cambiarla en el primer ingreso.`
    Object.assign(form, vacio())
    await cargar()
  } catch (e) {
    error.value = mensajeError(e)
  }
}
async function quitarMfa(u: Usuario) {
  if (!confirm(`¿Desactivar el segundo factor de ${u.nombres}? Verifique antes su identidad (protocolo P-02).`)) return
  await api.post(`/auth/mfa/desactivar/${u.id}`)
  await cargar()
}
async function cambiar(u: Usuario) {
  if (u.activo && !confirm(`¿Desactivar a ${u.nombres} ${u.apellidos}? Su historial se conserva.`)) return
  try {
    await api.patch(`/auth/usuarios/${u.id}/estado`, null, { params: { activo: !u.activo } })
    await cargar()
  } catch (e) {
    error.value = mensajeError(e)
  }
}
onMounted(cargar)
</script>

<template>
  <h1>Usuarios y roles</h1>
  <div class="alerta aviso">
    Una cuenta por persona, nunca compartida. Solicitud firmada por el jefe del área, registro profesional verificado en ReTHUS y
    desactivación el mismo día del retiro (protocolo P-01 de gestión de usuarios).
  </div>

  <form class="tarjeta" @submit.prevent="crear">
    <h2>Nuevo usuario</h2>
    <div v-if="error" class="alerta error">{{ error }}</div>
    <div v-if="ok" class="alerta ok">{{ ok }}</div>
    <div class="rejilla">
      <label>Rol
        <select v-model="form.rol">
          <option v-for="[k, r] in rolesDisponibles" :key="k" :value="k">{{ r.nombre }}</option>
        </select>
      </label>
      <label>Tipo doc. <select v-model="form.tipo_documento"><option>CC</option><option>CE</option><option>PA</option><option>PT</option></select></label>
      <label>Documento <input v-model="form.numero_documento" required /></label>
      <label>Nombres <input v-model="form.nombres" required /></label>
      <label>Apellidos <input v-model="form.apellidos" required /></label>
      <label>Correo institucional <input v-model="form.email" type="email" required /></label>
      <label>Registro profesional {{ rolActual?.registro ? '* (ReTHUS)' : '(opcional)' }}
        <input v-model="form.registro_profesional" :required="rolActual?.registro" />
      </label>
      <label>Especialidad / cargo <input v-model="form.especialidad" /></label>
      <label>Clave temporal
        <span class="fila" style="flex-wrap: nowrap"><input v-model="form.password" required minlength="10" /><button type="button" class="btn sec peq" @click="generarClave">Generar</button></span>
      </label>
    </div>
    <p v-if="rolActual" class="suave" style="margin: .6rem 0 0">
      <strong>{{ rolActual.nombre }}:</strong> {{ rolActual.quien }}.
      {{ rolActual.historia ? 'Accede a historias clínicas (cada consulta queda registrada).' : 'NO accede a historias clínicas.' }}
    </p>
    <button class="btn" style="margin-top: 1rem">Crear usuario</button>
  </form>

  <div class="tarjeta">
    <div class="fila entre">
      <h2 style="margin: 0">Usuarios ({{ visibles.length }})</h2>
      <select v-model="filtro" style="max-width: 260px"><option value="">Todos los roles</option><option v-for="(r, k) in ROLES" :key="k" :value="k">{{ r.nombre }}</option></select>
    </div>
    <table>
      <thead><tr><th>Nombre</th><th>Correo</th><th>Rol</th><th>Registro</th><th>MFA</th><th>Clave</th><th>Estado</th><th></th></tr></thead>
      <tbody>
        <tr v-for="u in visibles" :key="u.id">
          <td>{{ u.nombres }} {{ u.apellidos }}<br /><small class="suave">{{ u.especialidad }}</small></td>
          <td>{{ u.email }}</td><td>{{ ROLES[u.rol]?.nombre || u.rol }}</td><td>{{ u.registro_profesional || '—' }}</td>
          <td>
            <button v-if="u.mfa_activo" class="btn sec peq" title="Quitar segundo factor" @click="quitarMfa(u)">Activo ✕</button>
            <span v-else :class="u.mfa_obligatorio ? 'etiqueta borrador' : 'suave'">{{ u.mfa_obligatorio ? 'Pendiente (obligatorio)' : '—' }}</span>
          </td>
          <td><span v-if="u.debe_cambiar_clave" class="etiqueta borrador">Temporal</span><span v-else class="suave">Propia</span></td>
          <td><span :class="['etiqueta', u.activo ? 'firmada' : 'borrador']">{{ u.activo ? 'activo' : 'inactivo' }}</span></td>
          <td><button v-if="u.rol !== 'admin' || auth.tiene('admin')" class="btn sec peq" @click="cambiar(u)">{{ u.activo ? 'Desactivar' : 'Activar' }}</button></td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
