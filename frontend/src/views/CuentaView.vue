<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, mensajeError } from '../api/cliente'
import { useAuth } from '../stores/auth'

const auth = useAuth()
const router = useRouter()
const qr = ref('')
const secreto = ref('')
const codigo = ref('')
const msg = ref('')
const error = ref('')
const clave = ref({ actual: '', nueva: '', repetir: '' })

async function configurar() {
  error.value = ''
  try {
    const { data } = await api.post('/auth/mfa/configurar')
    qr.value = data.qr_svg
    secreto.value = data.secreto
  } catch (e) {
    error.value = mensajeError(e)
  }
}
async function activar() {
  error.value = ''
  try {
    await api.post('/auth/mfa/activar', { codigo: codigo.value })
    await auth.refrescarUsuario()
    qr.value = ''
    msg.value = 'Segundo factor activado. Desde ahora se pedirá el código al iniciar sesión.'
    if (!auth.usuario?.debe_cambiar_clave) setTimeout(() => router.push('/'), 1200)
  } catch (e) {
    error.value = mensajeError(e)
  }
}
async function cambiarClave() {
  error.value = ''
  if (clave.value.nueva !== clave.value.repetir) return (error.value = 'Las contraseñas nuevas no coinciden')
  try {
    await api.post('/auth/cambiar-clave', { actual: clave.value.actual, nueva: clave.value.nueva })
    clave.value = { actual: '', nueva: '', repetir: '' }
    msg.value = 'Contraseña actualizada'
    await auth.refrescarUsuario()
    if (!(auth.usuario?.mfa_obligatorio && !auth.usuario?.mfa_activo)) setTimeout(() => router.push('/'), 1200)
  } catch (e) {
    error.value = mensajeError(e)
  }
}
</script>

<template>
  <h1>Mi cuenta y seguridad</h1>
  <div v-if="auth.usuario?.debe_cambiar_clave" class="alerta aviso">
    🔑 Su contraseña es <strong>temporal</strong>. Por seguridad debe cambiarla antes de usar el sistema.
  </div>
  <div v-if="auth.usuario?.mfa_obligatorio && !auth.usuario?.mfa_activo" class="alerta aviso">
    📱 Su rol exige el <strong>segundo factor de autenticación (MFA)</strong>. Actívelo para continuar.
  </div>
  <div v-if="msg" class="alerta ok">{{ msg }}</div>
  <div v-if="error" class="alerta error">{{ error }}</div>
  <div class="rejilla-2">
    <div class="tarjeta">
      <h2>Segundo factor de autenticación (MFA)</h2>
      <p v-if="auth.usuario?.mfa_activo" class="alerta ok">Activo ✓</p>
      <template v-else>
        <p class="suave">Protege su cuenta aunque alguien conozca su contraseña. Use Google Authenticator, Microsoft Authenticator o Authy.</p>
        <button v-if="!qr" class="btn" @click="configurar">Configurar</button>
        <template v-else>
          <ol class="suave">
            <li>Abra la app autenticadora y escanee el código.</li>
            <li>Escriba el código de 6 dígitos que aparece.</li>
          </ol>
          <!-- SVG generado por el propio backend (segno) -->
          <div class="qr" v-html="qr" />
          <p class="mono suave">Clave manual: {{ secreto }}</p>
          <div class="fila"><input v-model="codigo" maxlength="6" placeholder="123456" style="max-width: 140px" /><button class="btn" @click="activar">Activar</button></div>
        </template>
      </template>
    </div>
    <form class="tarjeta" @submit.prevent="cambiarClave">
      <h2>Cambiar contraseña</h2>
      <label>Contraseña actual <input v-model="clave.actual" type="password" required /></label>
      <label style="margin-top: .6rem">Nueva (mín. 10, mayúsculas, minúsculas y números) <input v-model="clave.nueva" type="password" required /></label>
      <label style="margin-top: .6rem">Repetir nueva <input v-model="clave.repetir" type="password" required /></label>
      <button class="btn" style="margin-top: 1rem">Guardar</button>
    </form>
  </div>
</template>

<style scoped>
.qr :deep(svg) { width: 200px; height: 200px; }
</style>
