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

/** Abre un PDF/archivo protegido (la petición lleva el token) en una pestaña nueva o lo descarga. */
export async function abrirArchivo(url: string, params?: Record<string, string>, descargarComo?: string) {
  const { data } = await api.get(url, { params, responseType: 'blob' })
  const enlace = URL.createObjectURL(data)
  if (descargarComo) {
    const a = document.createElement('a')
    a.href = enlace
    a.download = descargarComo
    a.click()
  } else {
    window.open(enlace, '_blank')
  }
  setTimeout(() => URL.revokeObjectURL(enlace), 60_000)
}

export const fechaHora = (f?: string | null) =>
  f ? new Date(f).toLocaleString('es-CO', { dateStyle: 'medium', timeStyle: 'short' }) : '—'
export const soloFecha = (f?: string | null) => (f ? new Date(f).toLocaleDateString('es-CO') : '—')
export const pesos = (v?: number | string | null) =>
  Number(v || 0).toLocaleString('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 })
