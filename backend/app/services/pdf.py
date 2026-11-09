"""Documentos PDF (historia clínica, fórmula, epicrisis, consentimiento) con QR de verificación.

El QR apunta a  {URL_PUBLICA}/verificar/{tipo}/{id}?h={hash}  : cualquiera (p. ej. una farmacia o una EPS)
puede comprobar que el documento es auténtico y no fue alterado, SIN ver datos clínicos.
"""
import io
from datetime import datetime
from zoneinfo import ZoneInfo

import segno
from fpdf import FPDF

from app.core.config import settings

TZ = ZoneInfo(settings.ZONA_HORARIA)


def _t(texto) -> str:
    """Las fuentes estándar de PDF usan Latin-1: se reemplazan caracteres no soportados."""
    texto = "" if texto is None else str(texto)
    reemplazos = {"₂": "2", "–": "-", "—": "-", "“": '"', "”": '"', "’": "'", "…": "...", "≥": ">=", "≤": "<=", "°": " grados "}
    for a, b in reemplazos.items():
        texto = texto.replace(a, b)
    return texto.encode("latin-1", "replace").decode("latin-1")


def fecha(dt: datetime | None) -> str:
    if not dt:
        return "-"
    from app.services.ledger import a_utc

    return a_utc(dt).astimezone(TZ).strftime("%Y-%m-%d %H:%M")


def url_verificacion(tipo: str, id_, hash_: str | None) -> str:
    return f"{settings.URL_PUBLICA.rstrip('/')}/verificar/{tipo}/{id_}?h={hash_ or ''}"


class Documento(FPDF):
    def __init__(self, titulo: str, verificacion: str | None = None):
        super().__init__(format="Letter")
        self.titulo = titulo
        self.verificacion = verificacion
        self.set_auto_page_break(True, margin=22)
        self.set_margins(15, 15, 15)
        self.add_page()

    def header(self):
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(15, 118, 110)
        self.cell(0, 6, _t(settings.PRESTADOR_RAZON_SOCIAL), new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 8)
        self.set_text_color(90, 90, 90)
        self.cell(0, 4, _t(f"NIT {settings.PRESTADOR_NIT} - Código de habilitación {settings.PRESTADOR_COD_HABILITACION}"),
                  new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(0, 0, 0)
        self.cell(0, 8, _t(self.titulo), new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(15, 118, 110)
        self.line(15, self.get_y(), 201, self.get_y())
        self.ln(3)

    def footer(self):
        self.set_y(-18)
        self.set_font("Helvetica", "", 7)
        self.set_text_color(100, 100, 100)
        self.multi_cell(150, 3.5, _t("Documento generado por XENTRA DATACLINIC. Información confidencial protegida por la "
                                     "Ley 1581 de 2012 y la Resolución 1995 de 1999. Verifique su autenticidad con el código QR."))
        self.set_xy(170, -18)
        self.cell(30, 4, f"Página {self.page_no()}/{{nb}}", align="R")

    def seccion(self, titulo: str, texto=None):
        if texto in (None, "", [], {}):
            return
        self.set_font("Helvetica", "B", 9)
        self.set_fill_color(230, 245, 243)
        self.cell(0, 6, _t(titulo), fill=True, new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 9)
        self.multi_cell(0, 4.5, _t(texto))
        self.ln(1.5)

    def pares(self, filas: list[tuple[str, str]], columnas: int = 2):
        ancho = (self.w - 30) / columnas
        self.set_font("Helvetica", "", 8.5)
        for i, (k, v) in enumerate(filas):
            self.set_font("Helvetica", "B", 8.5)
            self.cell(ancho * 0.38, 5, _t(k + ":"))
            self.set_font("Helvetica", "", 8.5)
            self.cell(ancho * 0.62, 5, _t(v)[:60], new_x="LMARGIN" if i % columnas == columnas - 1 else "RIGHT",
                      new_y="NEXT" if i % columnas == columnas - 1 else "TOP")
        if len(filas) % columnas:
            self.ln(5)
        self.ln(2)

    def tabla(self, encabezados: list[str], filas: list[list], anchos: list[float]):
        self.set_font("Helvetica", "B", 8)
        for e, a in zip(encabezados, anchos):
            self.cell(a, 6, _t(e), border=1, fill=True)
        self.ln()
        self.set_font("Helvetica", "", 8)
        for fila in filas:
            for v, a in zip(fila, anchos):
                self.cell(a, 5.5, _t(v)[: int(a / 1.6)], border=1)
            self.ln()
        self.ln(2)

    def firma(self, nombre: str, detalle: str, hash_: str | None, fecha_firma: datetime | None):
        self.ln(4)
        y = self.get_y()
        if y > self.h - 60:
            self.add_page()
            y = self.get_y()
        self.set_font("Helvetica", "B", 9)
        self.cell(110, 5, _t(nombre), new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 8)
        self.cell(110, 4, _t(detalle), new_x="LMARGIN", new_y="NEXT")
        if hash_:
            self.cell(110, 4, _t(f"Firmado electrónicamente: {fecha(fecha_firma)}"), new_x="LMARGIN", new_y="NEXT")
            self.set_font("Courier", "", 6.5)
            self.multi_cell(110, 3, f"SHA-256: {hash_}")
        if self.verificacion:
            buf = io.BytesIO()
            segno.make(self.verificacion, error="m").save(buf, kind="png", scale=4, border=1)
            buf.seek(0)
            self.image(buf, x=165, y=y, w=32)
            self.set_xy(150, y + 33)
            self.set_font("Helvetica", "", 6.5)
            self.multi_cell(50, 3, _t("Escanee para verificar autenticidad"), align="C")

    def bytes(self) -> bytes:
        self.alias_nb_pages()
        return bytes(self.output())


def _encabezado_paciente(doc: Documento, p, edad: int):
    doc.pares([
        ("Paciente", p.nombre_completo), ("Documento", f"{p.tipo_documento} {p.numero_documento}"),
        ("Edad", f"{edad} años"), ("Sexo", {"H": "Hombre", "M": "Mujer", "I": "Indeterminado"}.get(p.sexo, p.sexo)),
        ("EPS", p.cod_eapb or "-"), ("Régimen", p.tipo_usuario), ("Teléfono", p.telefono or "-"),
        ("Alergias", p.alergias or "No conocidas"),
    ])


def pdf_atencion(a, edad: int) -> bytes:
    p, prof = a.paciente, a.profesional
    doc = Documento(f"HISTORIA CLÍNICA - Folio {a.consecutivo} ({a.tipo})", url_verificacion("atencion", a.id, a.hash_contenido))
    _encabezado_paciente(doc, p, edad)
    doc.pares([("Fecha de atención", fecha(a.fecha_inicio)), ("Estado", a.estado.upper())])
    doc.seccion("Motivo de consulta", a.motivo_consulta)
    doc.seccion("Enfermedad actual", a.enfermedad_actual)
    if a.antecedentes:
        doc.seccion("Antecedentes", "\n".join(f"{k.replace('_', ' ').capitalize()}: {v}" for k, v in a.antecedentes.items() if v))
    doc.seccion("Revisión por sistemas", a.revision_sistemas)
    if a.signos_vitales:
        nombres = {"ta_sistolica": "TAS", "ta_diastolica": "TAD", "fc": "FC", "fr": "FR", "temperatura": "Temp",
                   "spo2": "SpO2", "peso": "Peso", "talla": "Talla"}
        doc.seccion("Signos vitales", "   ".join(f"{nombres.get(k, k)}: {v}" for k, v in a.signos_vitales.items()))
    doc.seccion("Examen físico", a.examen_fisico)
    doc.seccion("Análisis", a.analisis)
    tipos = {"01": "Impresión diagnóstica", "02": "Confirmado nuevo", "03": "Confirmado repetido"}
    doc.seccion("Diagnósticos", "\n".join(
        f"{'Principal' if d.orden == 0 else 'Relacionado'}: {d.codigo_cie10} {d.descripcion} ({tipos.get(d.tipo_diagnostico, '')})"
        for d in a.diagnosticos))
    doc.seccion("Plan", a.plan)
    if a.prescripciones:
        doc.seccion("Fórmula médica", "\n".join(
            f"{i}. {r.medicamento} - {r.dosis} vía {r.via} {r.frecuencia} x {r.duracion_dias} días. Cant: {r.cantidad}"
            for i, r in enumerate(a.prescripciones, 1)))
    if a.procedimientos:
        doc.seccion("Procedimientos", "\n".join(f"{x.cod_cups} {x.descripcion}" for x in a.procedimientos))
    for n in a.notas_aclaratorias:
        doc.seccion(f"Nota aclaratoria {fecha(n.creado_en)} - {n.autor.nombre_completo}", n.texto)
    doc.firma(prof.nombre_completo, f"{prof.especialidad or prof.rol} - Reg. {prof.registro_profesional or '-'}",
              a.hash_contenido, a.firmada_en)
    return doc.bytes()


def pdf_formula(a, edad: int) -> bytes:
    p, prof = a.paciente, a.profesional
    doc = Documento("FÓRMULA MÉDICA", url_verificacion("atencion", a.id, a.hash_contenido))
    _encabezado_paciente(doc, p, edad)
    doc.pares([("Fecha", fecha(a.fecha_inicio)), ("Diagnóstico", a.diagnosticos[0].codigo_cie10 if a.diagnosticos else "-")])
    doc.tabla(["#", "Medicamento", "Dosis", "Vía", "Frecuencia", "Días", "Cant."],
              [[i, r.medicamento, r.dosis, r.via, r.frecuencia, r.duracion_dias, r.cantidad]
               for i, r in enumerate(a.prescripciones, 1)], [7, 60, 28, 20, 36, 12, 13])
    for r in a.prescripciones:
        if r.indicaciones:
            doc.seccion(f"Indicaciones - {r.medicamento}", r.indicaciones)
    doc.firma(prof.nombre_completo, f"{prof.especialidad or prof.rol} - Reg. {prof.registro_profesional or '-'}",
              a.hash_contenido, a.firmada_en)
    return doc.bytes()


def pdf_epicrisis(h, edad: int) -> bytes:
    doc = Documento("EPICRISIS", url_verificacion("epicrisis", h.id, h.hash_epicrisis))
    _encabezado_paciente(doc, h.paciente, edad)
    doc.pares([("Ingreso", fecha(h.fecha_ingreso)), ("Egreso", fecha(h.fecha_egreso)),
               ("Cama", h.cama.codigo if h.cama else "-"), ("Condición de egreso", h.condicion_egreso or "-"),
               ("Dx ingreso", h.dx_ingreso), ("Dx egreso", h.dx_egreso or "-")])
    doc.seccion("Motivo de ingreso", h.motivo)
    doc.seccion("Resumen de la hospitalización y plan de egreso", h.epicrisis)
    doc.firma(h.medico.nombre_completo, f"Reg. {h.medico.registro_profesional or '-'}", h.hash_epicrisis, h.fecha_egreso)
    return doc.bytes()


def pdf_consentimiento(c, paciente, edad: int) -> bytes:
    import base64

    doc = Documento(_t(c.titulo).upper(), url_verificacion("consentimiento", c.id, c.hash_contenido))
    _encabezado_paciente(doc, paciente, edad)
    doc.seccion("Contenido", c.texto)
    doc.seccion("Decisión", {"acepta": "ACEPTO el procedimiento descrito", "rechaza": "RECHAZO el procedimiento descrito",
                             "revoca": "REVOCO el consentimiento otorgado"}[c.decision])
    doc.pares([("Firmante", c.firmante_nombre), ("Documento", c.firmante_documento), ("Calidad", c.parentesco),
               ("Fecha", fecha(c.fecha))])
    if c.firma_imagen.startswith("data:image/png;base64,"):
        img = io.BytesIO(base64.b64decode(c.firma_imagen.split(",", 1)[1]))
        doc.image(img, w=60)
    doc.firma(c.profesional.nombre_completo, f"Profesional - Reg. {c.profesional.registro_profesional or '-'}",
              c.hash_contenido, c.fecha)
    return doc.bytes()
