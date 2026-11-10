<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, mensajeError } from '../api/cliente'
import { ESTADOS_CIVILES } from '../api/tipos'
import type { Paciente } from '../api/tipos'
import { useAuth } from '../stores/auth'

const auth = useAuth()
const router = useRouter()
const q = ref('')
const pacientes = ref<Paciente[]>([])
const mostrarForm = ref(false)
const error = ref('')

const vacio = () => ({
  tipo_documento: 'CC', numero_documento: '', primer_nombre: '', segundo_nombre: '', primer_apellido: '',
  segundo_apellido: '', fecha_nacimiento: '', sexo: 'M', telefono: '', email: '', direccion: '',
  cod_municipio_residencia: '11001', zona_territorial: '02', tipo_usuario: '01', cod_eapb: '',
  grupo_sanguineo: '', alergias: '', ocupacion: '', estado_civil: '', acompanante_nombre: '', acompanante_telefono: '',
  autoriza_tratamiento_datos: false,
})
const form = reactive(vacio())

async function buscar() {
  pacientes.value = (await api.get('/pacientes', { params: { q: q.value || undefined } })).data
}

async function guardar() {
  error.value = ''
  if (!form.autoriza_tratamiento_datos && !confirm('El paciente NO ha autorizado el tratamiento de datos (Ley 1581). ¿Continuar?')) return
  const datos = Object.fromEntries(Object.entries(form).map(([k, v]) => [k, v === '' ? null : v]))
  try {
    const { data } = await api.post('/pacientes', datos)
    router.push(`/pacientes/${data.id}`)
  } catch (e) {
    error.value = mensajeError(e)
  }
}

onMounted(buscar)
</script>

<template>
  <div class="fila entre">
    <h1>Pacientes</h1>
    <button v-if="auth.tiene('medico', 'enfermeria', 'admisiones', 'admin')" class="btn" @click="mostrarForm = !mostrarForm">
      {{ mostrarForm ? 'Cancelar' : '+ Nuevo paciente' }}
    </button>
  </div>

  <form v-if="mostrarForm" class="tarjeta" @submit.prevent="guardar">
    <h2>Registro de paciente</h2>
    <div v-if="error" class="alerta error">{{ error }}</div>
    <div class="rejilla">
      <label>Tipo de documento
        <select v-model="form.tipo_documento">
          <option value="CC">CC - Cédula de ciudadanía</option><option value="TI">TI - Tarjeta de identidad</option>
          <option value="RC">RC - Registro civil</option><option value="CE">CE - Cédula de extranjería</option>
          <option value="PA">PA - Pasaporte</option><option value="PT">PT - Permiso por protección temporal</option>
          <option value="MS">MS - Menor sin identificación</option><option value="AS">AS - Adulto sin identificación</option>
        </select>
      </label>
      <label>Número de documento * <input v-model="form.numero_documento" required /></label>
      <label>Primer nombre * <input v-model="form.primer_nombre" required /></label>
      <label>Segundo nombre <input v-model="form.segundo_nombre" /></label>
      <label>Primer apellido * <input v-model="form.primer_apellido" required /></label>
      <label>Segundo apellido <input v-model="form.segundo_apellido" /></label>
      <label>Fecha de nacimiento * <input v-model="form.fecha_nacimiento" type="date" required /></label>
      <label>Sexo biológico *
        <select v-model="form.sexo"><option value="M">Mujer</option><option value="H">Hombre</option><option value="I">Indeterminado/Intersexual</option></select>
      </label>
      <label>Teléfono <input v-model="form.telefono" /></label>
      <label>Correo <input v-model="form.email" type="email" /></label>
      <label>Dirección <input v-model="form.direccion" /></label>
      <label>Municipio (DIVIPOLA) <input v-model="form.cod_municipio_residencia" maxlength="5" placeholder="11001 = Bogotá" /></label>
      <label>Zona <select v-model="form.zona_territorial"><option value="02">Urbana</option><option value="01">Rural</option></select></label>
      <label>Tipo de usuario (régimen)
        <select v-model="form.tipo_usuario">
          <option value="01">01 Contributivo cotizante</option><option value="02">02 Contributivo beneficiario</option>
          <option value="03">03 Contributivo adicional</option><option value="04">04 Subsidiado</option>
          <option value="05">05 No afiliado</option><option value="06">06 Especial / excepción</option>
        </select>
      </label>
      <label>Código EPS / EAPB <input v-model="form.cod_eapb" /></label>
      <label>Grupo sanguíneo <input v-model="form.grupo_sanguineo" placeholder="O+" maxlength="3" /></label>
      <label>Alergias <input v-model="form.alergias" placeholder="Ninguna conocida" /></label>
      <label>Estado civil
        <select v-model="form.estado_civil">
          <option value="">— Sin dato —</option>
          <option v-for="(texto, valor) in ESTADOS_CIVILES" :key="valor" :value="valor">{{ texto }}</option>
        </select>
      </label>
      <label>Ocupación <input v-model="form.ocupacion" /></label>
      <label>Acompañante / responsable <input v-model="form.acompanante_nombre" /></label>
      <label>Teléfono acompañante <input v-model="form.acompanante_telefono" /></label>
    </div>
    <label class="check" style="margin: 1rem 0">
      <input v-model="form.autoriza_tratamiento_datos" type="checkbox" />
      El paciente autoriza de forma previa, expresa e informada el tratamiento de sus datos sensibles de salud (Ley 1581 de 2012).
    </label>
    <button class="btn">Guardar paciente</button>
  </form>

  <div class="tarjeta">
    <form class="fila" @submit.prevent="buscar">
      <input v-model="q" placeholder="Buscar por documento o nombre…" style="flex: 1" />
      <button class="btn sec">Buscar</button>
    </form>
    <table style="margin-top: 1rem">
      <thead><tr><th>Documento</th><th>Nombre</th><th>Edad</th><th>Sexo</th><th>EPS</th></tr></thead>
      <tbody>
        <tr v-for="p in pacientes" :key="p.id" class="clic" @click="router.push(`/pacientes/${p.id}`)">
          <td>{{ p.tipo_documento }} {{ p.numero_documento }}</td>
          <td><strong>{{ p.nombre_completo }}</strong></td>
          <td>{{ p.edad }} años</td>
          <td>{{ { H: 'Hombre', M: 'Mujer', I: 'Indet.' }[p.sexo] }}</td>
          <td>{{ p.cod_eapb || '—' }}</td>
        </tr>
        <tr v-if="!pacientes.length"><td colspan="5" class="suave">No hay resultados.</td></tr>
      </tbody>
    </table>
  </div>
</template>
