import { createRouter, createWebHistory } from 'vue-router'
import { useAuth } from '../stores/auth'
import type { Rol } from '../api/tipos'

const CLINICOS: Rol[] = ['medico', 'enfermeria', 'admin']
const v = (n: string) => () => import(`../views/${n}.vue`)

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: v('LoginView'), meta: { publica: true } },
    { path: '/verificar/:tipo/:id', component: v('VerificarView'), meta: { publica: true } },
    { path: '/', component: v('InicioView') },
    { path: '/portal', component: v('PortalView'), meta: { roles: ['paciente'] } },
    { path: '/cuenta', component: v('CuentaView') },
    { path: '/pacientes', component: v('PacientesView') },
    { path: '/pacientes/:id', component: v('PacienteDetalleView') },
    { path: '/pacientes/:id/atencion/:atencionId?', component: v('AtencionFormView'), meta: { roles: CLINICOS } },
    { path: '/atenciones/:id', component: v('AtencionDetalleView') },
    { path: '/agenda', component: v('AgendaView'), meta: { roles: ['admisiones', 'medico', 'enfermeria', 'admin'] } },
    { path: '/urgencias', component: v('UrgenciasView'), meta: { roles: [...CLINICOS, 'admisiones'] } },
    { path: '/hospitalizacion', component: v('HospitalizacionView'), meta: { roles: [...CLINICOS, 'admisiones', 'auditor'] } },
    { path: '/hospitalizacion/:id', component: v('HospitalizacionDetalleView'), meta: { roles: [...CLINICOS, 'auditor'] } },
    { path: '/laboratorio', component: v('LaboratorioView'), meta: { roles: ['laboratorio', 'medico', 'enfermeria', 'admin'] } },
    { path: '/farmacia', component: v('FarmaciaView'), meta: { roles: ['farmacia', 'admin'] } },
    { path: '/facturacion', component: v('FacturacionView'), meta: { roles: ['facturacion', 'admin', 'auditor'] } },
    { path: '/reportes', component: v('ReportesView'), meta: { roles: ['admin', 'auditor', 'medico'] } },
    { path: '/auditoria', component: v('AuditoriaView'), meta: { roles: ['auditor', 'admin'] } },
    { path: '/bi', component: v('BIView') },
    { path: '/modulos', component: v('ModulosView') },
    { path: '/soporte', component: v('SoporteView') },
    { path: '/usuarios', component: v('UsuariosView'), meta: { roles: ['admin'] } },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach((to) => {
  const auth = useAuth()
  if (to.meta.publica) return
  if (!auth.autenticado) return '/login'
  if (auth.esPaciente && !['/portal', '/cuenta'].includes(to.path)) return '/portal'
  const roles = to.meta.roles as Rol[] | undefined
  if (roles && !auth.tiene(...roles)) return '/'
})

export default router
