import math, sys
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen

OUT = sys.argv[1]
F_BOLD = '/usr/share/fonts/opentype/inter/InterDisplay-ExtraBold.otf'
F_SEMI = '/usr/share/fonts/opentype/inter/Inter-SemiBold.otf'

def texto(cadena, fuente, tam, x, y, espacio=0.0):
    """Convierte texto en trazos (no depende de fuentes instaladas). Devuelve (lista de (letra, path d), ancho)."""
    f = TTFont(fuente); gs = f.getGlyphSet(); cmap = f.getBestCmap(); upm = f['head'].unitsPerEm
    esc = tam / upm; cx = x; salida = []
    for i, ch in enumerate(cadena):
        nombre = cmap[ord(ch)]
        pen = SVGPathPen(gs)
        gs[nombre].draw(TransformPen(pen, (esc, 0, 0, -esc, cx, y)))
        salida.append((ch, pen.getCommands()))
        cx += gs[nombre].width * esc + (espacio * tam if i < len(cadena) - 1 else 0)
    return salida, cx - x

def hexagono(cx, cy, r, rr):
    """Hexágono con vértice arriba y esquinas redondeadas (radio rr)."""
    pts = [(cx + r * math.cos(math.radians(-90 + 60 * k)), cy + r * math.sin(math.radians(-90 + 60 * k))) for k in range(6)]
    d = ''
    for k in range(6):
        p0, p1, p2 = pts[k - 1], pts[k], pts[(k + 1) % 6]
        def hacia(a, b, t):
            L = math.dist(a, b); return (b[0] + (a[0] - b[0]) * t / L, b[1] + (a[1] - b[1]) * t / L)
        a = hacia(p0, p1, rr); b = hacia(p2, p1, rr)
        d += (f'M{a[0]:.2f},{a[1]:.2f}' if k == 0 else f'L{a[0]:.2f},{a[1]:.2f}') + f'Q{p1[0]:.2f},{p1[1]:.2f} {b[0]:.2f},{b[1]:.2f}'
    return d + 'Z'

def simbolo(id_, oscuro=False, simple=False, borde=False):
    """Símbolo de 128x128: bloque (hexágono) + X de nodos de datos + cruz médica en el núcleo."""
    g = f'g{id_}'
    nodos = [(39, 39), (89, 89), (39, 89)]
    if simple:  # favicon: menos detalle para que se lea a 16-32 px
        return f'''<defs><linearGradient id="{g}" gradientUnits="userSpaceOnUse" x1="14" y1="8" x2="114" y2="120">
    <stop offset="0" stop-color="#2dd4bf"/><stop offset=".55" stop-color="#0f766e"/><stop offset="1" stop-color="#134e4a"/></linearGradient></defs>
<path d="{hexagono(64, 64, 62, 14)}" fill="url(#{g})"/>
<g stroke="#ffffff" stroke-width="14" stroke-linecap="round"><line x1="38" y1="38" x2="90" y2="90"/><line x1="90" y1="38" x2="38" y2="90"/></g>
<circle cx="90" cy="38" r="11" fill="#99f6e4"/>
<circle cx="64" cy="64" r="17" fill="url(#{g})" stroke="#ffffff" stroke-width="5"/>
<rect x="55" y="60.5" width="18" height="7" rx="2" fill="#ffffff"/><rect x="60.5" y="55" width="7" height="18" rx="2" fill="#ffffff"/>'''
    marco = f'<path d="{hexagono(64, 64, 60, 14)}" fill="none" stroke="#99f6e4" stroke-opacity=".7" stroke-width="3"/>' if borde else ''
    return f'''<defs>
  <linearGradient id="{g}" gradientUnits="userSpaceOnUse" x1="14" y1="8" x2="114" y2="120">
    <stop offset="0" stop-color="#2dd4bf"/><stop offset=".55" stop-color="#0f766e"/><stop offset="1" stop-color="#134e4a"/>
  </linearGradient>
</defs>
<path d="{hexagono(64, 64, 60, 14)}" fill="url(#{g})"/>
<path d="{hexagono(64, 64, 50, 10)}" fill="none" stroke="#ffffff" stroke-opacity=".16" stroke-width="1.6"/>
<g stroke="#ffffff" stroke-width="9" stroke-linecap="round">
  <line x1="39" y1="39" x2="89" y2="89"/><line x1="89" y1="39" x2="39" y2="89"/>
</g>
{''.join(f'<circle cx="{x}" cy="{y}" r="8" fill="#ffffff"/>' for x, y in nodos)}
<circle cx="89" cy="39" r="9.5" fill="url(#{g})" stroke="#99f6e4" stroke-width="4"/>
<circle cx="89" cy="39" r="3" fill="#ffffff"/>
<circle cx="64" cy="64" r="16" fill="url(#{g})" stroke="#ffffff" stroke-width="3"/>
<rect x="56" y="61.25" width="16" height="5.5" rx="2" fill="#ffffff"/>
<rect x="61.25" y="56" width="5.5" height="16" rx="2" fill="#ffffff"/>{marco}'''

def svg(ancho, alto, cuerpo, fondo=None):
    f = f'<rect width="100%" height="100%" fill="{fondo}"/>' if fondo else ''
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {ancho} {alto}" width="{ancho}" height="{alto}" role="img" aria-label="XENTRA DATACLINIC">{f}{cuerpo}</svg>\n'

def palabra(x, y, oscuro, tam=64, id_='w', centrado=False):
    letras, ancho = texto('XENTRA', F_BOLD, tam, x, y, espacio=0.02)
    color = '#ffffff' if oscuro else '#0b2b29'
    d = ''.join(f'<path d="{p}" fill="{color}"/>' for _, p in letras)
    sub, ancho2 = texto('DATACLINIC', F_SEMI, tam * 0.285, x + 2, y + tam * 0.47, espacio=0.42)
    if centrado:
        sub, ancho2 = texto('DATACLINIC', F_SEMI, tam * 0.285, x + (ancho - ancho2) / 2, y + tam * 0.47, espacio=0.42)
    c2 = '#5eead4' if oscuro else '#0f766e'
    d += ''.join(f'<path d="{p}" fill="{c2}"/>' for _, p in sub)
    return d, max(ancho, ancho2)

archivos = {}
archivos['xentra-simbolo.svg'] = svg(128, 128, simbolo('s'))
archivos['favicon.svg'] = svg(128, 128, simbolo('f', simple=True))
for oscuro, nombre in ((False, 'xentra-logo-horizontal.svg'), (True, 'xentra-logo-horizontal-oscuro.svg')):
    w, ancho = palabra(150, 82, oscuro)
    cuerpo = f'<g transform="translate(6,6)">{simbolo("h" + str(oscuro))}</g>' + w
    archivos[nombre] = svg(int(150 + ancho + 12), 140, cuerpo, '#0b1f1e' if oscuro else None)
# Vertical
w, ancho = palabra(0, 0, False, tam=56, centrado=True)
anchoV = int(max(ancho, 140) + 40)
cuerpoV = f'<g transform="translate({(anchoV - 128) / 2},12)">{simbolo("v")}</g><g transform="translate({(anchoV - ancho) / 2},200)">{w}</g>'
archivos['xentra-logo-vertical.svg'] = svg(anchoV, 250, cuerpoV)
# Para el menú lateral de la app (fondo verde oscuro): símbolo + texto blanco
w, ancho = palabra(150, 82, True)
archivos['xentra-logo-menu.svg'] = svg(int(150 + ancho + 12), 140, f'<g transform="translate(6,6)">{simbolo("m", borde=True)}</g>' + w)
for n, c in archivos.items():
    open(f'{OUT}/{n}', 'w').write(c)
print('\n'.join(archivos))
