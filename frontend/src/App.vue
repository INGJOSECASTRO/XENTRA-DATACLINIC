<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { api } from './api/cliente'
import { useRoute, useRouter } from 'vue-router'
import { useAuth } from './stores/auth'
import type { Rol } from './api/tipos'

const auth = useAuth()
const route = useRoute()
const router = useRouter()

const PERSONAL: Rol[] = ['admin', 'medico', 'enfermeria', 'facturacion', 'auditor', 'admisiones', 'farmacia', 'laboratorio']
const menu: { a: string; texto: string; roles: Rol[] }[] = [
  { a: '/portal', texto: 'Mi salud', roles: ['paciente'] },
  { a: '/', texto: 'Inicio', roles: PERSONAL },
  { a: '/pacientes', texto: 'Pacientes', roles: ['admin', 'medico', 'enfermeria', 'admisiones', 'auditor'] },
  { a: '/agenda', texto: 'Agenda', roles: ['admisiones', 'medico', 'enfermeria', 'admin'] },
  { a: '/urgencias', texto: 'Urgencias', roles: ['medico', 'enfermeria', 'admin', 'admisiones'] },
  { a: '/hospitalizacion', texto: 'Hospitalización', roles: ['medico', 'enfermeria', 'admin', 'admisiones', 'auditor'] },
  { a: '/laboratorio', texto: 'Laboratorio e imágenes', roles: ['laboratorio', 'medico', 'enfermeria', 'admin'] },
  { a: '/farmacia', texto: 'Farmacia', roles: ['farmacia', 'admin'] },
  { a: '/facturacion', texto: 'Facturación y RIPS', roles: ['facturacion', 'admin', 'auditor'] },
  { a: '/reportes', texto: 'Indicadores', roles: ['admin', 'auditor', 'medico'] },
  { a: '/bi', texto: 'Inteligencia de negocio', roles: PERSONAL },
  { a: '/modulos', texto: 'Módulos adicionales', roles: PERSONAL },
  { a: '/soporte', texto: 'Soporte y continuidad', roles: PERSONAL },
  { a: '/auditoria', texto: 'Auditoría (ledger)', roles: ['auditor', 'admin'] },
  { a: '/usuarios', texto: 'Usuarios', roles: ['admin'] },
  { a: '/cuenta', texto: 'Mi cuenta y seguridad', roles: [...PERSONAL, 'paciente'] },
]
const visibles = computed(() => menu.filter((m) => auth.tiene(...m.roles)))

const avisos = ref<{ id: number; nivel: string; mensaje: string }[]>([])
let temporizadorAvisos: ReturnType<typeof setInterval> | undefined
async function cargarAvisos() {
  if (!auth.autenticado) return
  try { avisos.value = (await api.get('/sistema/avisos')).data } catch { /* sin conexión: se reintenta */ }
}
onMounted(() => { cargarAvisos(); temporizadorAvisos = setInterval(cargarAvisos, 300_000) })
watch(() => auth.token, (t) => (t ? cargarAvisos() : (avisos.value = [])))
onUnmounted(() => clearInterval(temporizadorAvisos))

function salir() {
  auth.logout()
  router.push('/login')
}
</script>

<template>
  <RouterView v-if="route.meta.publica" />
  <div v-else class="marco">
    <aside>
      <div class="marca">
        <svg viewBox="0 0 32 32" width="28" height="28"><rect width="32" height="32" rx="7" fill="#fff" /><path d="M13 7h6v6h6v6h-6v6h-6v-6H7v-6h6z" fill="#0f766e" /></svg>
        <div><strong>XENTRA</strong><small>DATACLINIC</small></div>
      </div>
      <nav>
        <RouterLink v-for="m in visibles" :key="m.a" :to="m.a" :class="{ activo: m.a === '/' ? route.path === '/' : route.path.startsWith(m.a) }">
          {{ m.texto }}
        </RouterLink>
      </nav>
      <div class="usuario" v-if="auth.usuario">
        <div>{{ auth.usuario.nombres }} {{ auth.usuario.apellidos }}</div>
        <small>{{ auth.usuario.rol }}</small>
        <button class="btn sec peq" @click="salir">Cerrar sesión</button>
      </div>
    </aside>
    <main>
      <div v-for="a in avisos" :key="a.id" :class="['alerta', a.nivel === 'critico' ? 'error' : a.nivel === 'aviso' ? 'aviso' : 'ok']">📢 {{ a.mensaje }}</div>
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.marco { display: grid; grid-template-columns: 230px 1fr; min-height: 100vh; }
aside { background: var(--primario-osc); color: #fff; display: flex; flex-direction: column; padding: 1rem; position: sticky; top: 0; height: 100vh; }
.marca { display: flex; gap: .6rem; align-items: center; margin-bottom: 1.5rem; }
.marca small { display: block; font-size: .65rem; letter-spacing: .15em; opacity: .8; }
nav { display: flex; flex-direction: column; gap: .2rem; flex: 1; overflow-y: auto; }
nav a { color: #e6fffa; padding: .55rem .75rem; border-radius: 8px; font-size: .9rem; }
nav a:hover { background: rgba(255,255,255,.08); }
nav a.activo { background: rgba(255,255,255,.16); font-weight: 600; }
.usuario { border-top: 1px solid rgba(255,255,255,.2); padding-top: .75rem; font-size: .85rem; display: flex; flex-direction: column; gap: .3rem; }
.usuario small { opacity: .75; text-transform: capitalize; }
main { padding: 1.5rem 2rem; max-width: 1200px; width: 100%; }
@media (max-width: 800px) {
  .marco { grid-template-columns: 1fr; }
  aside { position: static; height: auto; }
  nav { flex-direction: row; flex-wrap: wrap; }
  main { padding: 1rem; }
}
</style>
