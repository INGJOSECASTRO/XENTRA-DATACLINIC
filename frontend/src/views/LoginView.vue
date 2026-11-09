<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../stores/auth'
import { mensajeError } from '../api/cliente'

const auth = useAuth()
const router = useRouter()
const email = ref('')
const password = ref('')
const error = ref('')
const cargando = ref(false)

async function entrar() {
  error.value = ''
  cargando.value = true
  try {
    await auth.login(email.value, password.value)
    router.push('/')
  } catch (e) {
    error.value = mensajeError(e)
  } finally {
    cargando.value = false
  }
}
</script>

<template>
  <div class="fondo">
    <form class="tarjeta caja" @submit.prevent="entrar">
      <h1>XENTRA DATACLINIC</h1>
      <p class="suave">Historia Clínica Electrónica · Gestión Hospitalaria</p>
      <div v-if="error" class="alerta error">{{ error }}</div>
      <label>Correo <input v-model="email" type="email" autocomplete="username" required /></label>
      <label>Contraseña <input v-model="password" type="password" autocomplete="current-password" required /></label>
      <button class="btn" :disabled="cargando">{{ cargando ? 'Ingresando…' : 'Ingresar' }}</button>
      <p class="suave aviso">
        Acceso restringido a personal autorizado. Toda actividad queda registrada en el libro de auditoría
        (Ley 1581 de 2012 y Resolución 1995 de 1999).
      </p>
    </form>
  </div>
</template>

<style scoped>
.fondo { min-height: 100vh; display: grid; place-items: center; padding: 1rem; background: linear-gradient(135deg, #115e59, #0f766e 60%, #14b8a6); }
.caja { width: 100%; max-width: 400px; display: flex; flex-direction: column; gap: .9rem; }
.caja h1 { margin: 0; color: var(--primario); }
.aviso { font-size: .75rem; margin: 0; }
</style>
