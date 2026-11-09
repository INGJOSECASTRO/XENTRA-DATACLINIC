export type Rol = 'admin' | 'medico' | 'enfermeria' | 'facturacion' | 'auditor' | 'admisiones' | 'farmacia' | 'laboratorio' | 'paciente'

export interface Usuario {
  id: string
  tipo_documento: string
  numero_documento: string
  nombres: string
  apellidos: string
  email: string
  rol: Rol
  registro_profesional: string | null
  especialidad: string | null
  activo: boolean
  mfa_activo?: boolean
  paciente_id?: string | null
}

export interface Paciente {
  id: string
  tipo_documento: string
  numero_documento: string
  primer_nombre: string
  segundo_nombre: string | null
  primer_apellido: string
  segundo_apellido: string | null
  nombre_completo: string
  fecha_nacimiento: string
  edad: number
  sexo: 'H' | 'M' | 'I'
  telefono: string | null
  email: string | null
  direccion: string | null
  cod_municipio_residencia: string
  zona_territorial: string
  tipo_usuario: string
  cod_eapb: string | null
  grupo_sanguineo: string | null
  alergias: string | null
  ocupacion: string | null
  acompanante_nombre: string | null
  acompanante_telefono: string | null
  autoriza_tratamiento_datos: boolean
}

export interface Diagnostico {
  orden?: number
  codigo_cie10: string
  descripcion: string
  tipo_diagnostico: '01' | '02' | '03'
  sugerido_por_ia: boolean
}

export interface Procedimiento {
  cod_cups: string
  descripcion: string
  valor: number
}

export interface Prescripcion {
  id?: string
  medicamento: string
  dosis: string
  via: string
  frecuencia: string
  duracion_dias: number
  cantidad: number
  indicaciones?: string | null
}

export interface SignosVitales {
  ta_sistolica?: number | null
  ta_diastolica?: number | null
  fc?: number | null
  fr?: number | null
  temperatura?: number | null
  spo2?: number | null
  peso?: number | null
  talla?: number | null
}

export interface Nota {
  id: string
  texto: string
  hash_contenido: string
  creado_en: string
  autor: Usuario
}

export interface Atencion {
  id: string
  paciente_id: string
  consecutivo: number
  fecha_inicio: string
  tipo: string
  motivo_consulta: string
  estado: 'borrador' | 'firmada'
  profesional: Usuario
  diagnosticos: Diagnostico[]
  enfermedad_actual?: string | null
  revision_sistemas?: string | null
  signos_vitales?: SignosVitales | null
  examen_fisico?: string | null
  analisis?: string | null
  plan?: string | null
  cod_consulta_cups?: string
  valor_servicio?: number
  firmada_en?: string | null
  hash_contenido?: string | null
  bloque_ledger_id?: number | null
  procedimientos?: Procedimiento[]
  prescripciones?: Prescripcion[]
  notas_aclaratorias?: Nota[]
  alertas?: string[]
}

export interface Sugerencia {
  codigo: string
  descripcion: string
  confianza: number
  justificacion: string
  fuente: string
}

export interface CIE10 {
  codigo: string
  descripcion: string
}

export interface Bloque {
  id: number
  marca_tiempo: string
  usuario_id: string | null
  accion: string
  entidad: string
  entidad_id: string | null
  hash_datos: string
  hash_anterior: string
  hash: string
  ip_origen: string | null
}

export interface ItemCatalogo {
  codigo: string
  descripcion: string
  datos: Record<string, unknown> | null
}
