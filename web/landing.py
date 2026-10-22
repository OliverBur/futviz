"""La landing (`dist/index.html`): un buscador para entrar por un jugador, un equipo o una gráfica,
preguntas para empezar, la lectura destacada de Machine Learning y cómo leer el sitio.

Todo lo que la página muestra sale de lo que el build ya tiene registrado: las vistas del análisis
exploratorio (`ChartPage` con su pestaña y familia), las tablas de jugadores y equipos que usan las
gráficas (`react_views`), el artículo de xG (`ArticlePage`) y la malla de probabilidad que aprendió el
modelo (la tabla `xg` del artículo). Nada se escribe a mano: si se agrega una temporada, una liga o una
vista, la landing y el índice se rehacen solos en el siguiente build.

**El índice del buscador** (`dist/assets/search-index.js`) es un `.js` que define `window.futvizIndice`
y no un `.json`, por la misma razón que las tablas de las vistas: tiene que funcionar abierto con doble
clic (`file://`), donde `fetch` no sirve. El buscador (`web/static/buscador.js`) lo pide la primera vez
que alguien toca el campo, nunca al cargar la página. Solo entran los jugadores y equipos que tienen
punto en alguna gráfica (los mismos filtros de minutos que usan las vistas): buscar a alguien que no
aparece llevaría a una gráfica vacía.
"""

import gzip
import json
import math
from html import escape
from pathlib import Path

import react_views
from ml_reader import _minutos
from site_utils import (
    BRAND_ROOT_CSS, COLOR_BG_CLARO, FONT_LINKS, SECTION_META, THEME_COLOR_META, THEME_INIT_SCRIPT,
    THEME_TOGGLE_SCRIPT, ArticlePage, favicon_links, site_bar,
)

SITIO_URL = "https://futviz-lake.vercel.app/"
TITULO = "FutViz — Pregúntale a los datos del fútbol"
DESCRIPCION = ("Gráficas interactivas de jugadores y equipos de las 5 grandes ligas de Europa y un modelo "
               "de xG propio. Busca a un jugador o empieza por una pregunta.")
PRESUPUESTO_INDICE_KB = 150   # gzip

# Las preguntas de la portada y la vista que las responde. Si una vista cambia de nombre o desaparece, el
# build falla aquí en vez de dejar un enlace roto.
PREGUNTAS = [
    ("Jugadores", "¿Quién marca más de lo que debería?", "goles-vs-xg"),
    ("Jugadores", "¿Desde dónde se tira en las 5 ligas?", "mapa-tiros"),
    ("Jugadores", "¿Quién genera más ocasiones para sus compañeros?", "pases-clave-vs-xa"),
    ("Equipos", "¿Quién defiende mejor y cómo?", "defensa"),
    ("Equipos", "¿Qué equipo aprovecha mejor sus ocasiones?", "eficiencia-definicion"),
    ("Equipos", "¿Qué tan distinto es el nivel entre ligas?", "nivel-por-liga-equipos"),
]

# A qué gráficas manda el buscador a un jugador según su posición, en orden de relevancia. Solo entran las
# dispersiones: son las que aceptan `fijar` en la URL (el mapa de tiros y las cajas no filtran por jugador
# ni equipo; ver docs/BUSCADOR-MEJORAS.md). Lo que no esté aquí se completa con el orden de las pestañas.
PRIORIDAD_JUGADOR = {
    "Delantero": ["goles-vs-xg", "perfil-ofensivo", "asistencias-vs-xa"],
    "Medio": ["perfil-ofensivo", "pases-clave-vs-xa", "construir-vs-producir"],
    "Defensa": ["perfil-defensivo", "recuperacion-vs-faltas", "perfil-dos-fases"],
}
PRIORIDAD_EQUIPO = ["eficiencia-definicion", "creacion", "defensa"]
VISTAS_POR_RESULTADO = 3   # la principal + "Ver a {nombre} en…" con dos más
SUGERIDOS_JUGADORES = 4    # con el campo vacío: los máximos goleadores de la temporada más reciente
SUGERIDAS_VISTAS = 3       # ...y las primeras gráficas de "Preguntas para empezar"

# La combinación del mapa de calor de la portada: la más común (jugada abierta, pie derecho, tras un pase).
CLAVE_MAPA = "jugada|pie_der|Pass"
NIVELES_MAPA = 16   # tonos de la rampa; el desenfoque se encarga de que no se vean escalones


# --- el índice del buscador ------------------------------------------------------------------

def _filas_con_dato(payload, columnas):
    """Por fila: si tiene dato en todas las `columnas`. Las derivadas (que el navegador recalcula, ver
    `react_views.registrar_tabla`) cuentan como presentes si están sus operandos."""
    c, derivadas = payload["c"], payload.get("derivadas") or {}
    n = payload["n"]
    ok = [True] * n
    for col in columnas:
        if col in derivadas:
            tipo, *operandos = derivadas[col]          # ["suma", a, b] o ["por90", a]
            if tipo == "por90":
                operandos = operandos + ["min"]
        else:
            operandos = [col]
        for op in operandos:
            valores = c.get(op)
            for r in range(n):
                if ok[r] and (valores is None or valores[r] is None):
                    ok[r] = False
    return ok


def _vistas_por_entidad(paginas_eda):
    """[(slug, pestaña, familia, entidad, tabla, requiere)] de las dispersiones que aceptan `fijar`."""
    salida = []
    for p in paginas_eda:
        v = react_views.vista_registrada(p.slug)
        if not v or v["tipo"] != "scatter" or v["config"].get("explorador"):
            continue
        cfg = v["config"]
        salida.append((p.slug, cfg["tabla"], cfg["requiere"]))
    return salida


def _destinos(payload, vistas, temporadas):
    """Por cada nombre de la tabla: [(vista, temporada)] de las gráficas donde tiene punto, con la ÚLTIMA
    temporada en que lo tiene (sin `t` la vista abriría en la más reciente, donde puede no haber jugado)."""
    nombres, f = payload["nombres"], payload["f"]
    por_nombre = {}
    for slug, req in vistas:
        ok = _filas_con_dato(payload, req)
        for r in range(payload["n"]):
            if not ok[r]:
                continue
            j, t = f["j"][r], temporadas.index(payload["temporadas"][f["t"][r]])
            mejor = por_nombre.setdefault(j, {})
            if t > mejor.get(slug, -1):
                mejor[slug] = t
    return {nombres[j]: d for j, d in por_nombre.items()}


def _ultima_fila(payload):
    """Por código de nombre: la fila de su temporada más reciente (de ahí sale "Equipo · Liga")."""
    f, ultima = payload["f"], {}
    for r in range(payload["n"]):
        j = f["j"][r]
        if j not in ultima or f["t"][r] >= f["t"][ultima[j]]:
            ultima[j] = r
    return ultima


def construir_indice(paginas_eda, articulos):
    """El índice compacto que lee `buscador.js` (las URLs las arma el navegador a partir de esto)."""
    jug, equ = react_views.tabla_registrada("jugadores"), react_views.tabla_registrada("equipos")
    temporadas = sorted(set(jug["temporadas"]) | set(equ["temporadas"]))
    ligas = list(jug["ligas"])
    slugs = [p.slug for p in paginas_eda]
    v_idx = {s: i for i, s in enumerate(slugs)}
    scatter = _vistas_por_entidad(paginas_eda)
    orden_j = [s for s, tabla, _ in scatter if tabla == "jugadores"]
    orden_e = [s for s, tabla, _ in scatter if tabla == "equipos"]

    def ordenar(destinos, prioridad):
        preferidas = [s for s in prioridad if s in destinos]
        resto = [s for s in (orden_j + orden_e) if s in destinos and s not in preferidas]
        return [[v_idx[s], destinos[s]] for s in (preferidas + resto)[:VISTAS_POR_RESULTADO]]

    # jugadores
    dj = _destinos(jug, [(s, req) for s, tabla, req in scatter if tabla == "jugadores"], temporadas)
    ultima = _ultima_fila(jug)
    minutos = {}
    for r in range(jug["n"]):
        j = jug["f"]["j"][r]
        minutos[j] = minutos.get(j, 0) + (jug["c"]["min"][r] or 0)
    jugadores = []
    for j, nombre in enumerate(jug["nombres"]):
        if nombre not in dj:
            continue
        r = ultima[j]
        posicion = jug["posiciones"][jug["f"]["p"][r]] if jug["f"].get("p") and jug["f"]["p"][r] >= 0 else ""
        jugadores.append([nombre, jug["equipos"][jug["f"]["e"][r]], jug["f"]["l"][r],
                          round(minutos[j] / 100), ordenar(dj[nombre], PRIORIDAD_JUGADOR.get(posicion, []))])

    # equipos
    de = _destinos(equ, [(s, req) for s, tabla, req in scatter if tabla == "equipos"], temporadas)
    ultima = _ultima_fila(equ)
    equipos = [[nombre, equ["f"]["l"][ultima[j]], ordenar(de[nombre], PRIORIDAD_EQUIPO)]
               for j, nombre in enumerate(equ["nombres"]) if nombre in de]

    vistas = [[p.slug, p.tab or p.title, p.group, p.section] for p in paginas_eda]
    lecturas = [[a.title, f"{SECTION_META[a.section]['slug']}.html#{a.slug}", a.section] for a in articulos]

    # Sugerencias para el campo vacío, sacadas de los datos: los que más goles llevan en la temporada más
    # reciente de la tabla (con sus goles) y las primeras gráficas de las preguntas de la portada.
    ultima_t = jug["temporadas"][-1]
    t_ult = jug["temporadas"].index(ultima_t)
    en_indice = {x[0] for x in jugadores}
    goles = jug["c"]["goals"]
    filas = [r for r in range(jug["n"]) if jug["f"]["t"][r] == t_ult and goles[r] is not None
             and jug["nombres"][jug["f"]["j"][r]] in en_indice]
    filas.sort(key=lambda r: (-goles[r], -(jug["c"]["xG"][r] or 0)))
    sugeridos = []
    for r in filas:
        nombre = jug["nombres"][jug["f"]["j"][r]]
        if nombre not in (n for n, _ in sugeridos):
            sugeridos.append([nombre, int(goles[r])])
        if len(sugeridos) == SUGERIDOS_JUGADORES:
            break
    sugeridas = [v_idx[slug] for _, _, slug in PREGUNTAS if slug in v_idx][:SUGERIDAS_VISTAS]
    return {"t": temporadas, "l": ligas, "v": vistas, "j": jugadores, "e": equipos, "a": lecturas,
            "s": {"titulo": f"Más goles en {ultima_t}", "j": sugeridos, "v": sugeridas}}


def escribir_indice(indice, dist_dir: Path):
    """`dist/assets/search-index.js`. Devuelve (ruta, KB sin comprimir, KB gzip)."""
    cuerpo = json.dumps(indice, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    datos = f"window.futvizIndice={cuerpo};".encode("utf-8")
    ruta = dist_dir / "assets" / "search-index.js"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_bytes(datos)
    kb_gz = len(gzip.compress(datos, 9)) / 1024
    if kb_gz > PRESUPUESTO_INDICE_KB:
        raise SystemExit(f"El índice del buscador pesa {kb_gz:.0f} KB gzip, más que el presupuesto de "
                         f"{PRESUPUESTO_INDICE_KB} KB: ver docs/BUSCADOR-MEJORAS.md (cómo partirlo).")
    return ruta, len(datos) / 1024, kb_gz


# --- el mapa de calor (lo que aprendió el modelo) ------------------------------------------------

def _geometria(sup):
    nx, ny, largo, ancho = sup["nx"], sup["ny"], sup["largo"], sup["ancho"]
    ch = (sup["xmax"] - sup["xmin"]) / (nx - 1) * largo     # alto de celda (metros, hacia el campo)
    cw = (sup["ymax"] - sup["ymin"]) / (ny - 1) * ancho     # ancho de celda (metros, a lo ancho)
    prof = (1 - sup["xmin"]) * largo + ch / 2               # metros de cancha que se dibujan
    x0 = sup["ymin"] * ancho - cw / 2
    y0 = (1 - sup["xmax"]) * largo - ch / 2                 # la columna más cercana a la portería
    return nx, ny, ancho, ch, cw, prof, x0, y0


def _niveles(sup, clave):
    """Por celda (fila k desde la portería, columna r a lo ancho): nivel 1..NIVELES_MAPA o 0 sin dato."""
    nx, ny = sup["nx"], sup["ny"]
    rej, vmax = sup["rejillas"][clave], sup["vmax"]
    niveles = [[0] * ny for _ in range(nx)]
    for i, v in enumerate(rej):
        if v is None:
            continue
        r, c = i // nx, i % nx
        k = nx - 1 - c                                       # k = 0 es la columna pegada a la portería
        # Raíz cuadrada: casi toda la cancha está por debajo de 0.1 de xG y unas pocas celdas cerca de la
        # portería pasan de 0.5; en escala lineal todo lo de afuera del área caería en el primer nivel.
        # La raíz conserva el orden (más intenso = más probable) y separa los valores bajos.
        niveles[k][r] = max(1, min(NIVELES_MAPA, math.ceil(math.sqrt(min(1, v / vmax)) * NIVELES_MAPA)))
    return niveles


def _rampa(sup):
    """NIVELES_MAPA colores interpolados sobre la rampa azul del artículo (`SEQUENTIAL_BLUE`), de poco a muy
    probable. En el tema oscuro se usa al revés, como en el artículo: lo más probable es lo más brillante."""
    paradas = [tuple(int(h[i:i + 2], 16) for i in (1, 3, 5)) for h in sup["rampa"]]
    salida = []
    for n in range(NIVELES_MAPA):
        x = n / (NIVELES_MAPA - 1) * (len(paradas) - 1)
        i = min(len(paradas) - 2, int(x))
        f = x - i
        salida.append(tuple(round(a + (b - a) * f) for a, b in zip(paradas[i], paradas[i + 1])))
    return salida


def rampa_css(sup):
    """Las variables `--mapa-1..N` de los dos temas (salen de la rampa del artículo, no se escriben a mano)."""
    claro = [f"#{r:02X}{g:02X}{b:02X}" for r, g, b in _rampa(sup)]
    oscuro = claro[::-1]
    var = lambda colores: "".join(f"--mapa-{i + 1}:{c};" for i, c in enumerate(colores))  # noqa: E731
    return f':root{{{var(claro)}}}html[data-theme="dark"]{{{var(oscuro)}}}'


def mapa_svg(sup, clave=CLAVE_MAPA):
    """El mapa como SVG que sigue al tema: un <path> por tono de la rampa (las celdas contiguas del mismo
    tono unidas en tramos) con el color en una variable CSS, así cambia con el botón sin repintar nada. Un
    desenfoque leve borra los escalones de la rejilla de 40x32 y una rejilla fina de 2 m deja leer la escala.
    Lleva los valores de la malla para el tooltip (`_MAPA_JS`): el xG que da el modelo a un tiro desde el
    punto bajo el mouse y su distancia a la portería."""
    nx, ny, ancho, ch, cw, prof, x0, y0 = _geometria(sup)
    niveles = _niveles(sup, clave)
    trazos = {n: [] for n in range(1, NIVELES_MAPA + 1)}
    for k in range(nx):
        r = 0
        while r < ny:
            n = niveles[k][r]
            fin = r
            while fin + 1 < ny and niveles[k][fin + 1] == n:
                fin += 1
            if n:
                trazos[n].append(f"M{r} {k}h{fin - r + 1}v1h-{fin - r + 1}z")
            r = fin + 1
    capas = "".join(f'<path d="{"".join(t)}" style="fill:var(--mapa-{n})"/>' for n, t in trazos.items() if t)
    medio, penal = ancho / 2, 11
    tope = math.asin(math.sqrt(9.15 ** 2 - (16.5 - penal) ** 2) / 9.15)
    arco = " ".join(f"{medio + 9.15 * math.sin(a):.2f},{penal + 9.15 * math.cos(a):.2f}"
                    for a in (-tope + 2 * tope * i / 40 for i in range(41)))
    lineas = (f'<rect x="{medio - 20.16:.2f}" y="0" width="40.32" height="16.5"/>'
              f'<rect x="{medio - 9.16:.2f}" y="0" width="18.32" height="5.5"/>'
              f'<polyline points="{arco}"/><rect x="0" y="0" width="{ancho:g}" height="{prof:.2f}"/>')
    vb_h = prof + 3.2 + 1
    datos = {"nx": nx, "ny": ny, "xmin": sup["xmin"], "ymin": sup["ymin"], "ymax": sup["ymax"],
             "largo": sup["largo"], "ancho": ancho, "ch": round(ch, 5), "prof": round(prof, 3),
             "v": [None if v is None else round(v, 2) for v in sup["rejillas"][clave]]}
    return (
        f'<div class="mapa-caja">'
        f'<svg class="mapa" viewBox="-1 -3.2 {ancho + 2:g} {vb_h:.2f}" width="560" height="{560 * vb_h / (ancho + 2):.0f}" '
        f'role="img" aria-label="Mapa de la cancha cerca de la portería rival: cuanto más intenso el color, '
        f'más probable es que un tiro desde ahí termine en gol, según el modelo.">'
        f'<defs><clipPath id="mapa-recorte"><rect x="0" y="0" width="{ancho:g}" height="{prof:.2f}"/></clipPath>'
        f'<filter id="mapa-suave" x="-5%" y="-5%" width="110%" height="110%"><feGaussianBlur stdDeviation="0.9"/></filter>'
        f'<pattern id="mapa-rejilla" width="2" height="2" patternUnits="userSpaceOnUse"><path d="M2 0H0V2"/></pattern></defs>'
        f'<rect class="mapa-fondo" x="0" y="0" width="{ancho:g}" height="{prof:.2f}"/>'
        f'<g clip-path="url(#mapa-recorte)"><g filter="url(#mapa-suave)">'
        f'<g transform="translate({x0:.3f} {y0:.3f}) scale({cw:.4f} {ch:.4f})">{capas}</g></g></g>'
        f'<rect class="mapa-rejilla" x="0" y="0" width="{ancho:g}" height="{prof:.2f}" fill="url(#mapa-rejilla)"/>'
        f'<g class="mapa-lineas mapa-lineas-fondo">{lineas}</g><g class="mapa-lineas">{lineas}</g>'
        f'<rect class="mapa-porteria" x="{medio - 3.66:.2f}" y="-1.2" width="7.32" height="1.2"/>'
        f'<circle class="mapa-punto" cx="{medio:g}" cy="{penal}" r="0.45"/>'
        f'<circle class="mapa-marca" r="1.15" cx="0" cy="0" visibility="hidden"/></svg>'
        f'<div class="mapa-tip" aria-hidden="true" hidden><small>xG de un tiro desde aquí</small><b></b><span></span></div>'
        f'</div><script type="application/json" id="mapa-datos">{json.dumps(datos, separators=(",", ":"))}</script>')


# El tooltip del mapa: lee la malla que trae la página y no pide nada. Puntero (mouse o toque), sin teclado:
# el mapa es una ilustración del artículo, la misma información se explora completa allá.
_MAPA_JS = """<script>
(function () {
  var svg = document.querySelector(".mapa"), caja = svg && svg.parentNode, fuente = document.getElementById("mapa-datos");
  if (!svg || !fuente) return;
  var d = JSON.parse(fuente.textContent), tip = caja.querySelector(".mapa-tip"), marca = svg.querySelector(".mapa-marca");
  function ocultar() { tip.hidden = true; marca.setAttribute("visibility", "hidden"); }
  function mover(ev) {
    var m = svg.getScreenCTM();
    if (!m) return;
    var pt = svg.createSVGPoint();
    pt.x = ev.clientX; pt.y = ev.clientY;
    var p = pt.matrixTransform(m.inverse());
    var r = Math.round((p.x / d.ancho - d.ymin) / (d.ymax - d.ymin) * (d.ny - 1));
    var c = Math.round(((1 - d.xmin) * d.largo - p.y) / d.ch);
    var v = r >= 0 && r < d.ny && c >= 0 && c < d.nx ? d.v[r * d.nx + c] : null;
    if (v == null || p.x < 0 || p.x > d.ancho || p.y < 0 || p.y > d.prof) return ocultar();
    marca.setAttribute("cx", p.x); marca.setAttribute("cy", p.y); marca.setAttribute("visibility", "visible");
    tip.querySelector("b").textContent = v.toFixed(2);
    tip.querySelector("span").textContent = "a " + Math.round(Math.hypot(p.y, p.x - d.ancho / 2)) + " m de la portería";
    tip.hidden = false;
    var cj = caja.getBoundingClientRect(), x = ev.clientX - cj.left, y = ev.clientY - cj.top;
    var derecha = x > cj.width - tip.offsetWidth - 28;
    tip.style.left = (derecha ? x - tip.offsetWidth - 18 : x + 18) + "px";
    tip.style.top = Math.max(0, y - tip.offsetHeight / 2) + "px";
  }
  svg.addEventListener("pointermove", mover);
  svg.addEventListener("pointerdown", mover);
  svg.addEventListener("pointerleave", ocultar);
})();
</script>"""


def og_image(sup, dist_dir: Path):
    """La imagen para compartir (1200x630): logo, título y el mismo mapa de calor, en el tema claro."""
    from PIL import Image, ImageDraw, ImageFont

    fondo = tuple(int(COLOR_BG_CLARO[i:i + 2], 16) for i in (1, 3, 5))
    texto = (26, 46, 51)
    im = Image.new("RGB", (1200, 630), fondo)
    d = ImageDraw.Draw(im)
    logo = Image.open(dist_dir / "assets" / "logo.png")
    logo = logo.resize((300, round(300 * logo.height / logo.width)), Image.LANCZOS)
    im.paste(logo, (72, 72), logo)
    # Inter, la misma fuente del sitio, en TTF (PIL no lee woff2): la imagen sale igual en cualquier sistema.
    ttf = Path(__file__).parent / "static" / "fonts" / "ttf"
    grande, chica = ImageFont.truetype(str(ttf / "inter-800.ttf"), 62), ImageFont.truetype(str(ttf / "inter-400.ttf"), 27)
    for i, linea in enumerate(("Pregúntale a los", "datos del fútbol")):
        d.text((72, 210 + i * 80), linea, font=grande, fill=texto)
    d.text((72, 400), "Jugadores y equipos de las 5 grandes ligas,", font=chica, fill=(87, 112, 122))
    d.text((72, 438), "con gráficas interactivas y un modelo de xG.", font=chica, fill=(87, 112, 122))
    # el mapa: mismas celdas, tonos y desenfoque que el SVG (tema claro)
    from PIL import ImageFilter
    nx, ny, ancho, ch, cw, prof, x0, y0 = _geometria(sup)
    niveles, rampa = _niveles(sup, CLAVE_MAPA), _rampa(sup)
    escala = 460 / ancho
    ox, oy = 680, 90
    # Se desenfoca sobre el color del fondo (no sobre transparente, que deja un halo oscuro en el borde) y
    # se pega solo dentro de la cancha.
    capa = Image.new("RGB", im.size, fondo)
    dc = ImageDraw.Draw(capa)
    for k in range(nx):
        for r in range(ny):
            n = niveles[k][r]
            if n:
                x, y = ox + (x0 + r * cw) * escala, oy + (y0 + k * ch) * escala
                dc.rectangle([x, y, x + cw * escala, y + ch * escala], fill=rampa[n - 1])
    capa = capa.filter(ImageFilter.GaussianBlur(0.9 * escala))
    recorte = Image.new("L", im.size, 0)
    ImageDraw.Draw(recorte).rectangle([ox, oy, ox + ancho * escala, oy + prof * escala], fill=255)
    im.paste(capa, (0, 0), recorte)
    medio = ancho / 2
    for (x, y, w, h) in ((medio - 20.16, 0, 40.32, 16.5), (medio - 9.16, 0, 18.32, 5.5), (0, 0, ancho, prof)):
        d.rectangle([ox + x * escala, oy + y * escala, ox + (x + w) * escala, oy + (y + h) * escala],
                    outline=(255, 255, 255), width=2)
    ruta = dist_dir / "assets" / "og-image.png"
    im.save(ruta, optimize=True)
    return ruta


# --- la página -----------------------------------------------------------------------------------

LANDING_TEMPLATE = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
__THEME_COLOR__
<title>__TITULO__</title>
<meta name="description" content="__DESCRIPCION__">
<link rel="canonical" href="__URL__">
<meta property="og:type" content="website">
<meta property="og:locale" content="es_MX">
<meta property="og:url" content="__URL__">
<meta property="og:title" content="__TITULO__">
<meta property="og:description" content="__DESCRIPCION__">
<meta property="og:image" content="__URL__assets/og-image.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="FutViz: pregúntale a los datos del fútbol. Mapa de la probabilidad de gol según dónde se tira.">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="__TITULO__">
<meta name="twitter:description" content="__DESCRIPCION__">
<meta name="twitter:image" content="__URL__assets/og-image.png">
__FAVICON__
__THEME_INIT__
__FONT_LINKS__
<script src="assets/buscador.js" defer></script>
<style>
__BRAND_ROOT__
  /* Sin tarjetas: la estructura la dan líneas de 1px con --color-border. */
  .contenedor { max-width: 1200px; margin: 0 auto; padding-left: 32px; padding-right: 32px; }
  .sr-only { position: absolute; width: 1px; height: 1px; margin: -1px; padding: 0; overflow: hidden;
    clip: rect(0 0 0 0); white-space: nowrap; border: 0; }
  .skip { position: absolute; left: 12px; top: -60px; z-index: 60; padding: 10px 14px; border-radius: 8px;
    background: var(--color-primary); color: var(--color-bg); font-weight: 600; font-size: 14px; text-decoration: none; }
  .skip:focus-visible { top: 12px; outline: 2px solid var(--color-interactive); outline-offset: 2px; }
  a, button, input { -webkit-tap-highlight-color: transparent; }
  :focus-visible { outline: 2px solid var(--color-interactive); outline-offset: 2px; }

  /* Header */
  .site-header { border-bottom: 1px solid var(--color-border); }

  /* Hero */
  /* Hero centrado: el buscador es la idea de la página y el header ya es simétrico (logo a un lado, menú y
     tema al otro). Cargado a la izquierda dejaba media pantalla vacía en monitores anchos. */
  .hero { text-align: center; padding-top: clamp(64px, 11vw, 136px); padding-bottom: clamp(56px, 9vw, 112px); }
  h1 { font-size: clamp(36px, 7vw, 64px); line-height: 1.05; letter-spacing: -0.03em; font-weight: 800;
    color: var(--color-primary); margin: 0; text-align: left; }   /* el ancho es el del texto: así el bloque ícono + título queda centrado */
  /* Ícono grande + título como un solo bloque centrado, del alto de los dos renglones del título. */
  .titular { display: flex; align-items: center; justify-content: center; gap: clamp(20px, 2.5vw, 32px); margin: 0 auto 36px; }
  .titular img { height: 2.1em; width: auto; font-size: clamp(36px, 7vw, 64px); flex: none; }
  .leer { display: inline-flex; align-items: center; min-height: 44px; margin-top: 16px; font-size: 15px;
    font-weight: 600; color: var(--color-interactive); text-decoration: none; }

  /* Buscador: el campo es un combobox con la lista desplegada debajo (en pantallas chicas, a pantalla completa). */
  .buscador { position: relative; max-width: 760px; margin: 0 auto; text-align: left; }
  .campo { display: flex; align-items: center; gap: 12px; min-height: 60px; padding: 0 16px 0 18px;
    background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 12px;
    transition: border-color .12s ease, box-shadow .12s ease; }
  .campo:focus-within { border-color: var(--color-interactive); box-shadow: 0 0 0 3px var(--color-interactive-soft); }
  .campo svg { width: 20px; height: 20px; flex: none; color: var(--color-muted); }
  .campo input { flex: 1; min-width: 0; height: 58px; border: 0; background: transparent; outline: none;
    font: 500 17px/1.2 "Inter", system-ui, sans-serif; color: var(--color-text-body); }
  .campo input::placeholder { color: var(--color-muted); opacity: 1; }
  .campo input::-webkit-search-cancel-button { display: none; }
  .cerrar { display: none; min-height: 44px; padding: 0 4px; border: 0; background: none; cursor: pointer;
    font: 600 15px "Inter", system-ui, sans-serif; color: var(--color-interactive); }
  .panel { position: absolute; left: 0; right: 0; top: calc(100% + 8px); z-index: 30; max-height: min(70vh, 560px);
    overflow-y: auto; overscroll-behavior: contain; background: var(--color-surface);
    border: 1px solid var(--color-border); border-radius: 12px; padding: 8px 0;
    box-shadow: 0 16px 40px color-mix(in srgb, var(--color-primary) 18%, transparent);
    opacity: 0; transform: translateY(-4px); transition: opacity .12s ease, transform .12s ease; }
  .panel.visible { opacity: 1; transform: none; }
  .panel[hidden] { display: none; }
  .panel ul { list-style: none; margin: 0; padding: 0; }
  .grupo { display: block; padding: 10px 18px 4px; font-size: 11px; font-weight: 700; letter-spacing: .07em;
    text-transform: uppercase; color: var(--color-muted); }
  .opcion { display: flex; align-items: center; gap: 12px; min-height: 52px; padding: 8px 18px; cursor: pointer; }
  .opcion[aria-selected="true"] { background: var(--color-interactive-soft); box-shadow: inset 2px 0 0 var(--color-interactive); }
  .opcion .txt { flex: 1; min-width: 0; }
  .opcion .nom { display: block; font-size: 15px; font-weight: 600; color: var(--color-primary); }
  .opcion .det { display: block; font-size: 13px; color: var(--color-muted); }
  /* sobre el resaltado, el gris no llega a 4.5:1 en oscuro: el detalle pasa al color del texto */
  .opcion[aria-selected="true"] .det { color: var(--color-text-body); }
  .opcion .acc { flex: none; font-size: 13px; font-weight: 600; color: var(--color-interactive); }
  .opcion.sec { min-height: 44px; padding-left: 34px; }
  .opcion.sec .nom { font-weight: 500; font-size: 14px; color: var(--color-text-body); }
  .opcion mark { background: transparent; color: inherit; text-decoration: underline;
    text-decoration-color: var(--color-interactive); text-decoration-thickness: 2px; text-underline-offset: 3px; }
  .aviso { padding: 14px 18px; font-size: 14.5px; line-height: 1.5; color: var(--color-text-body); }
  .aviso a { color: var(--color-interactive); font-weight: 600; }

  /* Secciones */
  .seccion { padding: clamp(48px, 7vw, 88px) 0; border-top: 1px solid var(--color-border); }
  h2 { position: relative; padding-left: 16px; margin: 0 0 32px; font-size: clamp(22px, 3vw, 28px);
    line-height: 1.2; letter-spacing: -0.01em; color: var(--color-primary); }
  h2::before { content: ""; position: absolute; left: 0; top: .18em; bottom: .18em; width: 4px; border-radius: 2px;
    background: var(--color-brand-accent); }
  .etiqueta { display: block; font-size: 11px; font-weight: 700; letter-spacing: .07em; text-transform: uppercase;
    color: var(--color-muted); margin-bottom: 10px; }
  .preguntas { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); column-gap: 48px; }
  .preguntas li { border-top: 1px solid var(--color-border); padding: 24px 0 20px; }
  .preguntas h3 { margin: 0 0 8px; font-size: 24px; line-height: 1.25; font-weight: 600; letter-spacing: -0.01em;
    color: var(--color-primary); max-width: 20ch; text-wrap: balance; }
  .ir { display: inline-flex; align-items: center; min-height: 44px; font-size: 15px; font-weight: 600;
    color: var(--color-interactive); text-decoration: none; }
  .ir:hover, .leer:hover { text-decoration: underline; text-underline-offset: 4px; }
  .todas { display: inline-flex; align-items: center; min-height: 44px; margin-top: 16px; font-weight: 600;
    color: var(--color-text-body); text-underline-offset: 4px; }

  .destacada { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 56px; align-items: center; }
  .destacada h3 { margin: 0 0 14px; font-size: clamp(28px, 4vw, 44px); line-height: 1.1; letter-spacing: -0.02em;
    font-weight: 700; color: var(--color-primary); text-wrap: balance; }
  .destacada p { margin: 0 0 14px; font-size: 16px; line-height: 1.6; color: var(--color-text-body); max-width: 52ch; }
  .destacada .meta { font-size: 14px; color: var(--color-muted); font-variant-numeric: tabular-nums; }
  .boton { display: inline-flex; align-items: center; min-height: 48px; padding: 0 22px; margin: 8px 0 28px; border-radius: 10px;
    background: var(--color-primary); color: var(--color-bg); font-weight: 600; font-size: 15px; text-decoration: none; }
  .boton:hover { background: color-mix(in srgb, var(--color-primary) 88%, var(--color-bg)); }
  .proximo { margin: 0; padding-top: 18px; border-top: 1px solid var(--color-border); font-size: 14.5px; color: var(--color-muted); }
  figure { margin: 0; }
  __RAMPA_CSS__
  .mapa-caja { position: relative; }
  .mapa { display: block; width: 100%; height: auto; touch-action: pan-y; }
  .mapa-fondo { fill: var(--color-primary); fill-opacity: .05; }
  .mapa-rejilla { pointer-events: none; }
  #mapa-rejilla path { fill: none; stroke: var(--color-bg); stroke-opacity: .32; stroke-width: .06; }
  .mapa-marca { fill: none; stroke: var(--color-brand-accent); stroke-width: 2.4; vector-effect: non-scaling-stroke; pointer-events: none; }
  .mapa-tip { position: absolute; z-index: 2; min-width: 150px; padding: 10px 14px; border-radius: 10px; pointer-events: none;
    background: var(--color-surface); border: 1px solid var(--color-border);
    box-shadow: 0 10px 28px color-mix(in srgb, var(--color-primary) 20%, transparent); font-variant-numeric: tabular-nums; }
  .mapa-tip[hidden] { display: none; }
  .mapa-tip small { display: block; font-size: 11px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; color: var(--color-muted); }
  .mapa-tip b { display: block; font-size: 26px; line-height: 1.15; font-weight: 700; color: var(--color-primary); }
  .mapa-tip span { display: block; font-size: 13px; color: var(--color-muted); }
  /* `vector-effect` no se hereda: va en cada línea, o el trazo escalaría con el viewBox (en metros). */
  .mapa-lineas { fill: none; stroke: var(--color-muted); stroke-width: 1.2; }
  .mapa-lineas > * { vector-effect: non-scaling-stroke; }
  .mapa-lineas-fondo { stroke: var(--color-bg); stroke-width: 3.4; }
  .mapa-porteria { fill: none; stroke: var(--color-muted); stroke-width: 2; vector-effect: non-scaling-stroke; }
  .mapa-punto { fill: var(--color-bg); }
  .leyenda { display: flex; align-items: center; gap: 10px; margin-top: 14px; font-size: 13px; color: var(--color-muted); }
  .leyenda i { flex: 0 0 140px; height: 8px; border-radius: 4px; background: __RAMPA_LEYENDA__; }
  figcaption { margin-top: 10px; font-size: 13.5px; line-height: 1.5; color: var(--color-text-body); }
  figcaption small { display: block; color: var(--color-muted); font-size: 12.5px; margin-top: 2px; }

  .site-footer { border-top: 1px solid var(--color-border); padding: 28px 0 40px; font-size: 13.5px; color: var(--color-muted); }
  .site-footer .contenedor { display: flex; flex-wrap: wrap; gap: 12px 32px; justify-content: space-between; align-items: center; }
  .site-footer p { margin: 0; max-width: 70ch; line-height: 1.55; }
  .site-footer nav { display: flex; gap: 4px 18px; align-items: center; flex-wrap: wrap; }
  .site-footer a { display: inline-flex; align-items: center; min-height: 44px; color: var(--color-text-body); font-weight: 600; }

  @media (max-width: 860px) {
    .preguntas, .destacada { grid-template-columns: minmax(0, 1fr); }
    .destacada { gap: 32px; }
  }
  @media (max-width: 640px) {
    .contenedor { padding-left: 16px; padding-right: 16px; }   /* solo lateral: el hero también es .contenedor */
    /* En el teléfono el título usa tres renglones: el ícono va arriba, más chico. */
    .titular { flex-direction: column; gap: 16px; margin-bottom: 28px; }
    .titular img { height: 56px; }
    h1 { text-align: center; }
    .preguntas h3 { font-size: 21px; }
    /* El buscador abierto ocupa la pantalla: el teclado del teléfono deja poco espacio para la lista. */
    .buscador.abierto { position: fixed; inset: 0; z-index: 50; max-width: none; padding: 12px 16px;
      background: var(--color-bg); overflow-y: auto; overscroll-behavior: contain; }
    .buscador.abierto .cerrar { display: inline-flex; align-items: center; }
    .buscador.abierto .panel { position: static; margin-top: 10px; max-height: none; box-shadow: none; }
    .campo input { font-size: 16px; }
  }
  @media (prefers-reduced-motion: reduce) {
    .panel, .campo { transition: none; }
  }
</style>
</head>
<body>
<a class="skip" href="#main">Saltar al contenido</a>
<header class="site-header">
  __SITE_BAR__
</header>
<main id="main">
  <section class="hero contenedor" aria-labelledby="titulo">
    <div class="titular">
      <img class="logo-theme-light" src="assets/logo-icono.png" alt="" width="353" height="240">
      <img class="logo-theme-dark" src="assets/logo-icono-dark.png" alt="" width="353" height="240">
      <h1 id="titulo">Pregúntale a los<br> datos del fútbol</h1>
    </div>
    <form class="buscador" id="buscador" action="__EDA_URL__" role="search">
      <label class="sr-only" for="q">Busca un jugador, un equipo o una gráfica</label>
      <div class="campo">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
        <input id="q" name="q" type="search" placeholder="Busca un jugador, un equipo o una gráfica…"
          autocomplete="off" autocapitalize="off" spellcheck="false" enterkeyhint="search"
          role="combobox" aria-expanded="false" aria-controls="sugerencias" aria-autocomplete="list">
        <button type="button" class="cerrar" id="cerrar">Cerrar</button>
      </div>
      <div class="panel" id="panel" hidden>
        <ul id="sugerencias" role="listbox" aria-label="Resultados de la búsqueda"></ul>
        <div class="aviso" id="aviso" hidden></div>
      </div>
      <p class="sr-only" id="anuncio" aria-live="polite"></p>
    </form>
    <a class="leer" href="__ARTICULO_URL__">¿Prefieres leer? Empieza por __ARTICULO_TITULO__ →</a>
  </section>

  <section class="seccion" aria-labelledby="preguntas">
    <div class="contenedor">
      <h2 id="preguntas">Preguntas para empezar</h2>
      <ul class="preguntas">__PREGUNTAS__</ul>
      <a class="todas" href="__EDA_URL__">Ver las __N_VISTAS__ gráficas</a>
    </div>
  </section>

  <section class="seccion" aria-labelledby="destacada">
    <div class="contenedor">
      <h2 id="destacada">Lectura destacada</h2>
      <div class="destacada">
        <div>
          <span class="etiqueta">__ARTICULO_SECCION__</span>
          <h3>__ARTICULO_TITULO__</h3>
          <p>__ARTICULO_DESCRIPCION__</p>
          <p class="meta">__ARTICULO_META__</p>
          <a class="boton" href="__ARTICULO_URL__">Leer el artículo →</a>
          __PROXIMO__
        </div>
        <figure>
          __MAPA__
          <div class="leyenda" aria-hidden="true"><span>Poco probable</span><i></i><span>Muy probable</span></div>
          <figcaption>Lo que aprendió el modelo es la probabilidad de gol según el contexto del tiro.<small>Las zonas sin color no tienen tiros suficientes.</small></figcaption>
        </figure>
      </div>
    </div>
  </section>
</main>
<footer class="site-footer">
  <div class="contenedor">
    <p>__FUENTES__</p>
    <nav aria-label="Autor">
      <span>Autor: <strong>Oliver Burguete</strong></span>
      <a href="https://github.com/OliverBur" rel="noopener">GitHub</a>
      <a href="https://www.linkedin.com/in/oliburguete" rel="noopener">LinkedIn</a>
    </nav>
  </div>
</footer>
__THEME_SCRIPT__
</body>
</html>
"""


def escribir_landing(pages, dist_dir: Path):
    """Escribe `dist/index.html`, el índice del buscador y la og:image. Devuelve un resumen para el log."""
    hub = "Análisis exploratorio"
    entidades = SECTION_META[hub]["entidades"]
    paginas_eda = [p for e in entidades for p in pages if p.section == e]
    articulos = [p for p in pages if isinstance(p, ArticlePage)]
    slugs = {p.slug: p for p in paginas_eda}
    eda_url = f"{SECTION_META[hub]['slug']}.html"
    ml = SECTION_META["Machine Learning"]
    ml_url = f"{ml['slug']}.html"

    preguntas = []
    for etiqueta, pregunta, slug in PREGUNTAS:
        if slug not in slugs:
            raise SystemExit(f"La pregunta «{pregunta}» apunta a la vista «{slug}», que ya no existe.")
        preguntas.append(
            f'<li><span class="etiqueta">{etiqueta}</span><h3>{pregunta}</h3>'
            f'<a class="ir" href="{eda_url}#{slug}">{escape(slugs[slug].tab or slugs[slug].title)} →</a></li>')

    art = articulos[0]
    meta = f"{_minutos(art.body_html)} min de lectura"
    proximo = (f'<p class="proximo">Próximamente: {escape(ml["proximos"][0]["title"])}.</p>'
               if ml.get("proximos") else "")
    sup = react_views.tabla_registrada("xg")["superficie"]

    html = (LANDING_TEMPLATE
            .replace("__PREGUNTAS__", "".join(preguntas))
            .replace("__N_VISTAS__", str(len(paginas_eda)))
            .replace("__MAPA__", mapa_svg(sup))
            .replace("__RAMPA_CSS__", rampa_css(sup))
            .replace("__RAMPA_LEYENDA__", "linear-gradient(to right, "
                     + ", ".join(f"var(--mapa-{i})" for i in range(1, NIVELES_MAPA + 1, 3)) + f", var(--mapa-{NIVELES_MAPA}))")
            .replace("__ARTICULO_URL__", f"{ml_url}#{art.slug}")
            .replace("__ARTICULO_TITULO__", escape(art.title))
            .replace("__ARTICULO_SECCION__", escape(art.section))
            .replace("__ARTICULO_DESCRIPCION__", escape(art.subtitle))
            .replace("__ARTICULO_META__", escape(meta))
            .replace("__PROXIMO__", proximo)
            .replace("__FUENTES__", "Datos: FBref y Understat")
            .replace("__EDA_URL__", eda_url)
            .replace("__ML_URL__", ml_url)
            .replace("__TITULO__", escape(TITULO))
            .replace("__DESCRIPCION__", escape(DESCRIPCION))
            .replace("__URL__", SITIO_URL)
            .replace("__SITE_BAR__", site_bar())
            .replace("__THEME_COLOR__", THEME_COLOR_META)
            .replace("__FAVICON__", favicon_links())
            .replace("__THEME_INIT__", THEME_INIT_SCRIPT)
            .replace("__FONT_LINKS__", FONT_LINKS)
            .replace("__BRAND_ROOT__", BRAND_ROOT_CSS)
            .replace("__THEME_SCRIPT__", THEME_TOGGLE_SCRIPT + "\n" + _MAPA_JS))
    salida = dist_dir / "index.html"
    salida.write_text(html, encoding="utf-8")

    indice = construir_indice(paginas_eda, articulos)
    ruta_idx, kb, kb_gz = escribir_indice(indice, dist_dir)
    og = og_image(sup, dist_dir)
    return {"index": salida, "indice": ruta_idx, "og": og, "kb": kb, "kb_gz": kb_gz,
            "jugadores": len(indice["j"]), "equipos": len(indice["e"]), "vistas": len(indice["v"]),
            "lecturas": len(indice["a"]),
            "jugadores_tabla": len(react_views.tabla_registrada("jugadores")["nombres"])}
