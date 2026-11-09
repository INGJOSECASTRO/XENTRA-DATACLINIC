import { defineStore } from 'pinia'
import { api } from '../api/cliente'
import type { Rol, Usuario } from '../api/tipos'

// sessionStorage: la sesión se cierra al cerrar el navegador (equipos compartidos en IPS).
export const useAuth = defineStore('auth', {
  state: () => ({
    token: sessionStorage.getItem('token') as string | null,
    usuario: JSON.parse(sessionStorage.getItem('usuario') || 'null') as Usuario | null,
  }),
  getters: {
    autenticado: (s) => !!s.token,
  },
  actions: {
    async login(email: string, password: string) {
      const form = new URLSearchParams({ username: email, password })
      const { data } = await api.post('/auth/login', form)
      this.token = data.access_token
      this.usuario = data.usuario
      sessionStorage.setItem('token', data.access_token)
      sessionStorage.setItem('usuario', JSON.stringify(data.usuario))
    },
    logout() {
      this.token = null
      this.usuario = null
      sessionStorage.clear()
    },
    tiene(...roles: Rol[]) {
      return !!this.usuario && roles.includes(this.usuario.rol)
    },
  },
})
