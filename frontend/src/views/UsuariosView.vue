<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { api, mensajeError } from '../api/cliente'
import type { Usuario } from '../api/tipos'

const usuarios = ref<Usuario[]>([])
const error = ref('')
const vacio = () => ({ tipo_documento: 'CC', numero_documento: '', nombres: '', apellidos: '', email: '', password: '', rol: 'medico', registro_profesional: '', especialidad: '' })
const form = reactive(vacio())

async function cargar() {
  usuarios.value = (await api.get('/auth/usuarios')).data
}
async function crear() {
  error.value = ''
  try {
    await api.post('/auth/usuarios', { ...form, registro_profesional: form.registro_profesional || null, especialidad: form.especialidad || null })
    Object.assign(form, vacio())
    await cargar()
  } catch (e) {
    error.value = mensajeError(e)
  }
}
async function cambiar(u: Usuario) {
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
  <form class="tarjeta" @submit.prevent="crear">
    <h2>Nuevo usuario</h2>
    <div v-if="error" class="alerta error">{{ error }}</div>
    <div class="rejilla">
      <label>Documento <input v-model="form.numero_documento" required /></label>
      <label>Nombres <input v-model="form.nombres" required /></label>
      <label>Apellidos <input v-model="form.apellidos" required /></label>
      <label>Correo <input v-model="form.email" type="email" required /></label>
      <label>Contraseña (mín. 10, mayúscula, número) <input v-model="form.password" type="password" required /></label>
      <label>Rol
        <select v-model="form.rol">
          <option value="medico">Médico</option><option value="enfermeria">Enfermería</option><option value="admisiones">Admisiones</option>
          <option value="facturacion">Facturación</option><option value="auditor">Auditor</option><option value="admin">Administrador</option>
        </select>
      </label>
      <label>Registro profesional (ReTHUS) <input v-model="form.registro_profesional" /></label>
      <label>Especialidad <input v-model="form.especialidad" /></label>
    </div>
    <button class="btn" style="margin-top: 1rem">Crear usuario</button>
  </form>
  <div class="tarjeta">
    <table>
      <thead><tr><th>Nombre</th><th>Correo</th><th>Rol</th><th>Registro</th><th>Estado</th><th></th></tr></thead>
      <tbody>
        <tr v-for="u in usuarios" :key="u.id">
          <td>{{ u.nombres }} {{ u.apellidos }}</td><td>{{ u.email }}</td><td>{{ u.rol }}</td><td>{{ u.registro_profesional || '—' }}</td>
          <td><span :class="['etiqueta', u.activo ? 'firmada' : 'borrador']">{{ u.activo ? 'activo' : 'inactivo' }}</span></td>
          <td><button class="btn sec peq" @click="cambiar(u)">{{ u.activo ? 'Desactivar' : 'Activar' }}</button></td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
