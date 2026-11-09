import { defineStore } from 'pinia'
import { api } from '../api/cliente'
import type { Rol, Usuario } from '../api/tipos'

const INACTIVIDAD_MIN = 15 // cierre automático de sesión por inactividad
const RENOVAR_MIN = 10 // renovación del token mientras hay actividad

let temporizador: ReturnType<typeof setInterval> | undefined
let ultimaActividad = Date.now()
let ultimaRenovacion = Date.now()

// sessionStorage: la sesión se cierra al cerrar el navegador (equipos compartidos en IPS).
export const useAuth = defineStore('auth', {
  state: () => ({
    token: sessionStorage.getItem('token') as string | null,
    usuario: JSON.parse(sessionStorage.getItem('usuario') || 'null') as Usuario | null,
    tokenMfa: null as string | null,
  }),
  getters: {
    autenticado: (s) => !!s.token,
    esPaciente: (s) => s.usuario?.rol === 'paciente',
  },
  actions: {
    guardar(data: { access_token: string; usuario: Usuario }) {
      this.token = data.access_token
      this.usuario = data.usuario
      this.tokenMfa = null
      sessionStorage.setItem('token', data.access_token)
      sessionStorage.setItem('usuario', JSON.stringify(data.usuario))
      this.vigilar()
    },
    /** Devuelve true si se requiere el segundo factor. */
    async login(email: string, password: string): Promise<boolean> {
      const form = new URLSearchParams({ username: email, password })
      const { data } = await api.post('/auth/login', form)
      if (data.mfa_requerido) {
        this.tokenMfa = data.token_mfa
        return true
      }
      this.guardar(data)
      return false
    },
    async verificarMfa(codigo: string) {
      const { data } = await api.post('/auth/mfa/verificar', { token_mfa: this.tokenMfa, codigo })
      this.guardar(data)
    },
    async refrescarUsuario() {
      const { data } = await api.get('/auth/yo')
      this.usuario = data
      sessionStorage.setItem('usuario', JSON.stringify(data))
    },
    logout(motivo?: string) {
      this.token = null
      this.usuario = null
      sessionStorage.clear()
      clearInterval(temporizador)
      if (motivo) sessionStorage.setItem('motivo_salida', motivo)
    },
    tiene(...roles: Rol[]) {
      return !!this.usuario && roles.includes(this.usuario.rol)
    },
    vigilar() {
      if (temporizador || !this.token) return
      const marcar = () => (ultimaActividad = Date.now())
      ;['click', 'keydown', 'mousemove', 'touchstart'].forEach((e) => window.addEventListener(e, marcar, { passive: true }))
      temporizador = setInterval(async () => {
        if (!this.token) return
        const ahora = Date.now()
        if (ahora - ultimaActividad > INACTIVIDAD_MIN * 60_000) {
          this.logout('Sesión cerrada por inactividad')
          window.location.href = '/login'
        } else if (ahora - ultimaRenovacion > RENOVAR_MIN * 60_000) {
          ultimaRenovacion = ahora
          try {
            const { data } = await api.post('/auth/renovar')
            this.guardar(data)
          } catch {
            /* el interceptor 401 redirige */
          }
        }
      }, 30_000)
    },
  },
})
