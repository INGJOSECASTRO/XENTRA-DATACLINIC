<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuth } from './stores/auth'
import type { Rol } from './api/tipos'

const auth = useAuth()
const route = useRoute()
const router = useRouter()

const menu: { a: string; texto: string; roles?: Rol[] }[] = [
  { a: '/', texto: 'Inicio' },
  { a: '/pacientes', texto: 'Pacientes' },
  { a: '/rips', texto: 'RIPS / Facturación', roles: ['facturacion', 'admin'] },
  { a: '/auditoria', texto: 'Auditoría (ledger)', roles: ['auditor', 'admin'] },
  { a: '/usuarios', texto: 'Usuarios', roles: ['admin'] },
]
const visibles = computed(() => menu.filter((m) => !m.roles || auth.tiene(...m.roles)))

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
    <main><RouterView /></main>
  </div>
</template>

<style scoped>
.marco { display: grid; grid-template-columns: 230px 1fr; min-height: 100vh; }
aside { background: var(--primario-osc); color: #fff; display: flex; flex-direction: column; padding: 1rem; position: sticky; top: 0; height: 100vh; }
.marca { display: flex; gap: .6rem; align-items: center; margin-bottom: 1.5rem; }
.marca small { display: block; font-size: .65rem; letter-spacing: .15em; opacity: .8; }
nav { display: flex; flex-direction: column; gap: .2rem; flex: 1; }
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
