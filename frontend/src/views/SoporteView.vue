<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { abrirArchivo, api, fechaHora, mensajeError } from '../api/cliente'
import { useAuth } from '../stores/auth'

/* eslint-disable @typescript-eslint/no-explicit-any */
interface Ticket { id: number; titulo: string; descripcion: string; categoria: string; prioridad: string; modulo: string | null
  codigo_error: string | null; estado: string; autor: string; creado_en: string; vence_en: string; solucion: string | null
  comentarios: { autor: string; fecha: string; texto: string }[]; vencido: boolean }

const auth = useAuth()
const gestion = auth.tiene('admin', 'auditor')
const pestana = ref(gestion ? 'estado' : 'tickets')
const estado = ref<any>(null)
const tickets = ref<Ticket[]>([])
const conocimiento = ref<{ id: number; titulo: string; modulo: string | null; solucion: string }[]>([])
const rda = ref<any[]>([])
const rdaResumen = ref<any>(null)
const busquedaKb = ref('')
const error = ref('')
const ok = ref('')
const abierto = ref<number | null>(null)
const comentario = ref('')
const nuevo = reactive({ titulo: '', descripcion: '', categoria: 'incidente', prioridad: 'media', modulo: '', codigo_error: '' })
const aviso = reactive({ nivel: 'aviso', mensaje: '', hasta: '' })
const fechaContingencia = ref(new Date().toLocaleDateString('en-CA'))
const colorPrioridad: Record<string, string> = { critica: 'borrador', alta: 'borrador', media: 'ia', baja: 'firmada' }

async function cargar() {
  const tareas: Promise<unknown>[] = [
    api.get('/sistema/tickets').then((r) => (tickets.value = r.data)),
    api.get('/sistema/base-conocimiento', { params: { q: busquedaKb.value || undefined } }).then((r) => (conocimiento.value = r.data)),
  ]
  if (gestion) {
    tareas.push(api.get('/sistema/estado').then((r) => (estado.value = r.data)))
    tareas.push(api.get('/rda').then((r) => (rda.value = r.data)), api.get('/rda/resumen').then((r) => (rdaResumen.value = r.data)))
  }
  await Promise.all(tareas)
}
async function accion(fn: () => Promise<unknown>, mensaje: string) {
  error.value = ok.value = ''
  try { await fn(); ok.value = mensaje; await cargar() } catch (e) { error.value = mensajeError(e) }
}
const crearTicket = () => accion(async () => {
  await api.post('/sistema/tickets', { ...nuevo, modulo: nuevo.modulo || null, codigo_error: nuevo.codigo_error || null })
  Object.assign(nuevo, { titulo: '', descripcion: '', modulo: '', codigo_error: '' })
}, 'Ticket creado. Soporte le responderá dentro del tiempo acordado.')
const actualizar = (t: Ticket, cambios: Record<string, unknown>) => accion(() => api.patch(`/sistema/tickets/${t.id}`, cambios), 'Ticket actualizado')
function resolver(t: Ticket) {
  const solucion = prompt('Describa la solución (quedará en la base de conocimiento)')
  if (solucion) actualizar(t, { estado: 'resuelto', solucion })
}
function comentar(t: Ticket) {
  if (comentario.value.trim()) actualizar(t, { comentario: comentario.value }).then(() => (comentario.value = ''))
}
const publicarAviso = () => accion(() => api.post('/sistema/avisos', { ...aviso, hasta: aviso.hasta ? new Date(aviso.hasta).toISOString() : null }), 'Aviso publicado')
const procesarRda = () => accion(() => api.post('/rda/procesar'), 'Cola de RDA procesada')
const reintentar = (id: string) => accion(() => api.post(`/rda/${id}/reintentar`), 'RDA reenviado')
const contingencia = () => abrirArchivo('/sistema/contingencia', { fecha: fechaContingencia.value }, `contingencia_${fechaContingencia.value}.pdf`)
const verRda = (id: string) => abrirArchivo(`/rda/${id}`, undefined, `rda_${id}.json`)
onMounted(cargar)
</script>

<template>
  <h1>Soporte y continuidad del negocio</h1>
  <div v-if="error" class="alerta error">{{ error }}</div>
  <div v-if="ok" class="alerta ok">{{ ok }}</div>
  <div class="fila" style="margin-bottom: 1rem; gap: .4rem">
    <button v-for="p in (gestion ? ['estado', 'tickets', 'conocimiento', 'contingencia', 'rda', 'avisos'] : ['tickets', 'conocimiento', 'contingencia'])" :key="p"
      :class="['btn peq', pestana === p ? '' : 'sec']" @click="pestana = p">
      {{ { estado: 'Estado del sistema', tickets: 'Mesa de ayuda', conocimiento: 'Base de conocimiento', contingencia: 'Plan de contingencia', rda: 'RDA (Res. 1888)', avisos: 'Avisos' }[p] }}
    </button>
  </div>

  <template v-if="pestana === 'estado' && estado">
    <div :class="['alerta', estado.estado_general === 'operativo' ? 'ok' : 'aviso']">
      Estado general: <strong>{{ estado.estado_general }}</strong> · versión {{ estado.version }} · activo hace {{ estado.activo_desde_horas }} h
      <ul v-if="estado.alertas.length"><li v-for="a in estado.alertas" :key="a">{{ a }}</li></ul>
    </div>
    <div class="rejilla">
      <div class="tarjeta"><div class="suave">Base de datos</div><div class="kpi">{{ estado.base_datos.latencia_ms }} ms</div></div>
      <div class="tarjeta"><div class="suave">Disco libre</div><div class="kpi">{{ estado.disco.libre_pct }}%</div><small class="suave">{{ estado.disco.libre_gb }} de {{ estado.disco.total_gb }} GB</small></div>
      <div class="tarjeta"><div class="suave">Último respaldo</div>
        <div class="kpi" style="font-size: 1.3rem">{{ estado.respaldos.disponible ? `hace ${estado.respaldos.horas_desde_ultimo} h` : 'Sin datos' }}</div>
        <small class="suave">{{ estado.respaldos.ultima_prueba_restauracion || estado.respaldos.detalle || '' }}</small></div>
      <div class="tarjeta"><div class="suave">Ledger</div><div class="kpi">{{ estado.ledger.bloques }}</div><small class="suave">Último anclaje: {{ fechaHora(estado.ledger.ultimo_anclaje) }}</small></div>
      <div class="tarjeta"><div class="suave">Tickets abiertos</div><div class="kpi">{{ estado.soporte.tickets_abiertos }}</div><small class="suave">{{ estado.soporte.criticos }} críticos</small></div>
    </div>
    <div class="tarjeta"><h2>Integraciones</h2>
      <p><span v-for="(v, k) in estado.integraciones" :key="k" class="etiqueta ia" style="margin-right: .4rem">{{ k }}: {{ v }}</span></p>
    </div>
  </template>

  <template v-if="pestana === 'tickets'">
    <form class="tarjeta" @submit.prevent="crearTicket">
      <h2>Reportar un problema o solicitud</h2>
      <p class="suave">Si la pantalla mostró un código de error, cópielo aquí: soporte encontrará la causa de inmediato. Antes, revise la base de conocimiento.</p>
      <div class="rejilla">
        <label>Título <input v-model="nuevo.titulo" required minlength="5" /></label>
        <label>Tipo <select v-model="nuevo.categoria"><option value="incidente">Incidente (algo falla)</option><option value="solicitud">Solicitud</option><option value="mejora">Mejora</option><option value="seguridad">Seguridad</option></select></label>
        <label>Prioridad <select v-model="nuevo.prioridad"><option value="critica">Crítica (4 h) – no se puede atender</option><option value="alta">Alta (8 h)</option><option value="media">Media (24 h)</option><option value="baja">Baja (72 h)</option></select></label>
        <label>Módulo <input v-model="nuevo.modulo" placeholder="Historia clínica, facturación…" /></label>
        <label>Código de error <input v-model="nuevo.codigo_error" placeholder="Ej. 3F9A1C2B7D" /></label>
      </div>
      <label style="margin-top: .5rem">Descripción (qué hacía, qué pasó, desde cuándo) <textarea v-model="nuevo.descripcion" required minlength="10" /></label>
      <button class="btn" style="margin-top: .6rem">Enviar a soporte</button>
    </form>
    <div class="tarjeta">
      <h2>{{ gestion && auth.tiene('admin') ? 'Todos los tickets' : 'Mis tickets' }}</h2>
      <table>
        <tbody>
          <template v-for="t in tickets" :key="t.id">
            <tr class="clic" @click="abierto = abierto === t.id ? null : t.id">
              <td>#{{ t.id }}</td>
              <td><strong>{{ t.titulo }}</strong><br /><small class="suave">{{ t.modulo }} · {{ t.autor }} · {{ fechaHora(t.creado_en) }}</small></td>
              <td><span :class="['etiqueta', colorPrioridad[t.prioridad]]">{{ t.prioridad }}</span></td>
              <td><span :class="['etiqueta', ['resuelto', 'cerrado'].includes(t.estado) ? 'firmada' : 'borrador']">{{ t.estado }}</span>
                <div v-if="t.vencido" class="etiqueta borrador">ANS vencido</div></td>
              <td><small class="suave">Vence {{ fechaHora(t.vence_en) }}</small></td>
            </tr>
            <tr v-if="abierto === t.id">
              <td colspan="5">
                <p style="white-space: pre-wrap">{{ t.descripcion }}</p>
                <p v-if="t.codigo_error" class="mono">Código de error: {{ t.codigo_error }}</p>
                <p v-if="t.solucion" class="alerta ok">Solución: {{ t.solucion }}</p>
                <div v-for="(c, i) in t.comentarios" :key="i" class="suave">{{ fechaHora(c.fecha) }} · {{ c.autor }}: {{ c.texto }}</div>
                <div class="fila" style="margin-top: .5rem">
                  <input v-model="comentario" placeholder="Agregar comentario…" style="max-width: 400px" />
                  <button class="btn sec peq" @click="comentar(t)">Comentar</button>
                  <template v-if="auth.tiene('admin') && !['resuelto', 'cerrado'].includes(t.estado)">
                    <button class="btn sec peq" @click="actualizar(t, { estado: 'en_proceso' })">En proceso</button>
                    <button class="btn peq" @click="resolver(t)">Resolver</button>
                  </template>
                </div>
              </td>
            </tr>
          </template>
          <tr v-if="!tickets.length"><td class="suave">No hay tickets.</td></tr>
        </tbody>
      </table>
    </div>
  </template>

  <div v-if="pestana === 'conocimiento'" class="tarjeta">
    <form class="fila" @submit.prevent="cargar"><input v-model="busquedaKb" placeholder="Buscar solución…" style="flex: 1" /><button class="btn sec">Buscar</button></form>
    <div v-for="k in conocimiento" :key="k.id" style="border-top: 1px solid var(--borde); padding: .6rem 0">
      <strong>{{ k.titulo }}</strong> <small class="suave">{{ k.modulo }}</small>
      <p style="margin: .3rem 0">{{ k.solucion }}</p>
    </div>
    <p v-if="!conocimiento.length" class="suave">Sin resultados. Las soluciones de los tickets resueltos aparecen aquí automáticamente.</p>
  </div>

  <div v-if="pestana === 'contingencia'" class="tarjeta">
    <h2>Plan de contingencia</h2>
    <p>Si se cae la red, el servidor o la energía, la atención no se detiene:</p>
    <ol>
      <li><strong>Al iniciar cada turno</strong>, descargue el PDF de contingencia (agenda del día con alergias, problemas y medicamentos de cada paciente, y censo hospitalario con órdenes activas).</li>
      <li>Si el sistema falla, atienda con ese PDF y los formatos en papel de la institución.</li>
      <li>Al restablecerse, transcriba las atenciones indicando "registro diferido por contingencia".</li>
      <li>Reporte el incidente en la mesa de ayuda con prioridad <strong>crítica</strong>.</li>
    </ol>
    <div class="fila"><input v-model="fechaContingencia" type="date" style="max-width: 180px" /><button class="btn" @click="contingencia">Descargar PDF de contingencia</button></div>
    <p class="suave">El PDF contiene datos sensibles: custódielo y destrúyalo al terminar el turno.</p>
  </div>

  <template v-if="pestana === 'rda'">
    <div class="tarjeta">
      <div class="fila entre">
        <div>
          <h2 style="margin: 0">Resumen Digital de Atención (Resolución 1888 de 2025)</h2>
          <p class="suave" style="margin: .3rem 0">Se genera automáticamente al firmar una atención o dar egreso, y se envía a la IHCE con reintentos si la red falla.
            Modo actual: <strong>{{ rdaResumen?.modo }}</strong></p>
        </div>
        <button class="btn" @click="procesarRda">Procesar cola ahora</button>
      </div>
      <p><span v-for="(n, e) in rdaResumen?.por_estado" :key="e" class="etiqueta ia" style="margin-right: .4rem">{{ e }}: {{ n }}</span></p>
      <div v-if="rdaResumen?.plazos" class="rejilla">
        <div v-for="(p, k) in rdaResumen.plazos" :key="k">
          <strong>{{ k === 'rda_clinico' ? 'RDA clínico' : 'RDA de dispensación' }}</strong> · {{ p.norma }}<br />
          <span :class="['etiqueta', new Date(p.obligatorio_desde) <= new Date() ? 'borrador' : 'ia']">
            {{ new Date(p.obligatorio_desde) <= new Date() ? 'Obligatorio desde' : 'Obligatorio a partir de' }} {{ p.obligatorio_desde }}</span>
        </div>
      </div>
      <div v-if="rdaResumen && !rdaResumen.ihce_configurada" class="alerta aviso" style="margin-top: .6rem">
        La IHCE no está configurada (IHCE_URL). Los RDA se generan y validan, pero no se transmiten al Ministerio hasta que la IPS se registre y configure la URL y la credencial asignadas.
      </div>
    </div>
    <div class="tarjeta">
      <table>
        <thead><tr><th>Generado</th><th>Tipo</th><th>Estado</th><th>Intentos</th><th>Detalle</th><th></th></tr></thead>
        <tbody>
          <tr v-for="r in rda" :key="r.id">
            <td>{{ fechaHora(r.generado_en) }}</td><td>{{ r.tipo }}</td>
            <td><span :class="['etiqueta', ['enviado', 'simulado'].includes(r.estado) ? 'firmada' : 'borrador']">{{ r.estado }}</span></td>
            <td>{{ r.intentos }}</td>
            <td><small>{{ r.errores_validacion?.join('; ') || r.respuesta?.error || r.respuesta?.resultado || '' }}</small></td>
            <td><button class="btn sec peq" @click="verRda(r.id)">JSON</button>
              <button v-if="['pendiente', 'error'].includes(r.estado) && !r.errores_validacion" class="btn sec peq" @click="reintentar(r.id)">Reintentar</button></td>
          </tr>
        </tbody>
      </table>
    </div>
  </template>

  <form v-if="pestana === 'avisos' && auth.tiene('admin')" class="tarjeta" @submit.prevent="publicarAviso">
    <h2>Publicar aviso para todos los usuarios</h2>
    <div class="rejilla">
      <label>Nivel <select v-model="aviso.nivel"><option value="info">Información</option><option value="aviso">Aviso (mantenimiento)</option><option value="critico">Crítico (contingencia)</option></select></label>
      <label>Visible hasta <input v-model="aviso.hasta" type="datetime-local" /></label>
    </div>
    <label style="margin-top: .5rem">Mensaje <input v-model="aviso.mensaje" required minlength="5" placeholder="Mantenimiento programado el sábado de 10 p. m. a 12 a. m." /></label>
    <button class="btn" style="margin-top: .6rem">Publicar</button>
  </form>
</template>
