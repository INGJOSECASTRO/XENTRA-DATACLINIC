// Cliente HTTP: agrega el token a cada petición y cierra sesión si el token vence.
import axios from 'axios'

export const api = axios.create({ baseURL: '/api' })

api.interceptors.request.use((config) => {
  const token = sessionStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (r) => r,
  (error) => {
    if (error.response?.status === 401 && !error.config.url?.includes('/auth/login')) {
      sessionStorage.clear()
      window.location.href = '/login'
    }
    return Promise.reject(error)
  },
)

/** Convierte cualquier error de la API en un mensaje legible en español. */
export function mensajeError(e: unknown): string {
  const err = e as { response?: { data?: { detail?: unknown } } }
  const detalle = err.response?.data?.detail
  if (typeof detalle === 'string') return detalle
  if (Array.isArray(detalle)) return detalle.map((d) => `${d.loc?.slice(-1)[0]}: ${d.msg}`).join(' · ')
  if (detalle && typeof detalle === 'object' && 'errores' in detalle) return (detalle as { errores: string[] }).errores.join(' · ')
  return 'Ocurrió un error inesperado'
}
