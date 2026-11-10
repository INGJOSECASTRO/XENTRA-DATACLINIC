<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../stores/auth'
import { mensajeError } from '../api/cliente'

const auth = useAuth()
const router = useRouter()
const email = ref('')
const password = ref('')
const codigo = ref('')
const pasoMfa = ref(false)
const error = ref('')
const aviso = ref(sessionStorage.getItem('motivo_salida') || '')
sessionStorage.removeItem('motivo_salida')
const cargando = ref(false)

async function entrar() {
  error.value = ''
  cargando.value = true
  try {
    if (pasoMfa.value) await auth.verificarMfa(codigo.value)
    else if (await auth.login(email.value, password.value)) {
      pasoMfa.value = true
      return
    }
    router.push(auth.esPaciente ? '/portal' : '/')
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
      <h1><img src="/logo.svg" alt="XENTRA DATACLINIC" class="logo" /></h1>
      <p class="suave">Historia Clínica Electrónica · Gestión Hospitalaria</p>
      <div v-if="aviso" class="alerta aviso">{{ aviso }}</div>
      <div v-if="error" class="alerta error">{{ error }}</div>
      <template v-if="!pasoMfa">
        <label>Correo <input v-model="email" type="email" autocomplete="username" required /></label>
        <label>Contraseña <input v-model="password" type="password" autocomplete="current-password" required /></label>
      </template>
      <label v-else>Código de su app autenticadora (6 dígitos)
        <input v-model="codigo" inputmode="numeric" autocomplete="one-time-code" maxlength="6" required autofocus />
      </label>
      <button class="btn" :disabled="cargando">{{ cargando ? 'Verificando…' : pasoMfa ? 'Verificar' : 'Ingresar' }}</button>
      <p class="suave nota">
        Acceso restringido a personal autorizado. Toda actividad queda registrada en el
        libro de auditoría (Ley 1581 de 2012 y Resolución 1995 de 1999).
      </p>
    </form>
  </div>
</template>

<style scoped>
.fondo { min-height: 100vh; display: grid; place-items: center; padding: 1rem; background: linear-gradient(135deg, #115e59, #0f766e 60%, #14b8a6); }
.caja { width: 100%; max-width: 400px; display: flex; flex-direction: column; gap: .9rem; }
.caja h1 { margin: 0; color: var(--primario); }
.caja .logo { display: block; width: 260px; max-width: 100%; height: auto; margin: 0 auto .2rem; }
.nota { font-size: .75rem; margin: 0; }
</style>
