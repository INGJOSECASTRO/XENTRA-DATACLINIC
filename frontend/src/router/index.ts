import { createRouter, createWebHistory } from 'vue-router'
import { useAuth } from '../stores/auth'
import type { Rol } from '../api/tipos'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: () => import('../views/LoginView.vue'), meta: { publica: true } },
    { path: '/', name: 'inicio', component: () => import('../views/InicioView.vue') },
    { path: '/pacientes', name: 'pacientes', component: () => import('../views/PacientesView.vue') },
    { path: '/pacientes/:id', name: 'paciente', component: () => import('../views/PacienteDetalleView.vue') },
    {
      path: '/pacientes/:id/atencion/:atencionId?',
      name: 'atencion-form',
      component: () => import('../views/AtencionFormView.vue'),
      meta: { roles: ['medico', 'enfermeria', 'admin'] },
    },
    { path: '/atenciones/:id', name: 'atencion', component: () => import('../views/AtencionDetalleView.vue') },
    { path: '/rips', name: 'rips', component: () => import('../views/RipsView.vue'), meta: { roles: ['facturacion', 'admin'] } },
    { path: '/auditoria', name: 'auditoria', component: () => import('../views/AuditoriaView.vue'), meta: { roles: ['auditor', 'admin'] } },
    { path: '/usuarios', name: 'usuarios', component: () => import('../views/UsuariosView.vue'), meta: { roles: ['admin'] } },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach((to) => {
  const auth = useAuth()
  if (!to.meta.publica && !auth.autenticado) return { name: 'login' }
  const roles = to.meta.roles as Rol[] | undefined
  if (roles && !auth.tiene(...roles)) return { name: 'inicio' }
})

export default router
