"""Helpers para armar el sitio estático a partir de los mismos gráficos que
viven en los notebooks de `code/`. No son parte del EDA — solo empaquetan
el HTML de un gráfico (Plotly vía `viz_theme.sidebar_chart_html`/`plot_html`,
o una figura de matplotlib exportada a PNG) dentro de una página con la
identidad visual del proyecto, más un índice que las enlaza."""

import json
import re
import sys
from dataclasses import dataclass
from html import escape as escapar_html
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
CODE_DIR = REPO_ROOT / "code"

# Los CSV crudos viven en una carpeta por temporada (`data/2025-26/`, ...) y
# `data/processed/` tiene las 5 temporadas ya consolidadas y etiquetadas.
# Los gráficos leen del consolidado (traen selector de temporada); `SEASON`
# queda como la temporada que se muestra al abrir un gráfico y la que usan
# los pocos gráficos que siguen siendo de un solo período.
SEASON = "2025-26"
SEASON_DIR = DATA_DIR / SEASON
PROCESSED_DIR = DATA_DIR / "processed"


def temporadas_en_curso():
    """`{temporada: jornadas}` de las temporadas que no han terminado: las que el equipo que más partidos
    lleva no pasa de 30. Lo usan las vistas del análisis exploratorio para avisar que la muestra es chica."""
    import pandas as pd
    df = pd.read_csv(PROCESSED_DIR / "teams_all_seasons.csv", usecols=["temporada", "ov_Playing Time_MP"])
    mp = df.groupby("temporada")["ov_Playing Time_MP"].max()
    return {t: int(n) for t, n in mp.items() if n < 30}

# Las temporadas que hay descargadas, leídas de las carpetas de `data/` en vez
# de listadas a mano: es lo que dice el pie de la landing, y agregar una
# temporada no tiene por qué obligar a acordarse de tocar un literal acá.
SEASONS = sorted(d.name for d in DATA_DIR.iterdir()
                 if d.is_dir() and re.fullmatch(r"\d{4}-\d{2}", d.name))

# Crédito de fuentes del pie de la landing. FBref publica las tablas de equipo;
# Understat es de donde salen los jugadores (xG/xA, que FBref dejó de publicar
# en la versión gratuita) y el detalle de tiros.
# Filtro de nivel de club — el mismo control en las dos secciones que lo usan.
#
# Vive acá y no en `charts/teams.py` porque `charts/players.py` lo necesita
# igual y una sección no debería importar de la otra. El umbral en sí no está
# acá: lo define `consolidate_data.ELO_TOP`, que es quien calcula la columna
# `nivel` para las dos tablas — así un club no puede salir top en una gráfica y
# underground en la de al lado.
#
# --- Por qué existe ---
# Casi todos los scatter del sitio tienen el mismo problema de fondo que salió
# en el clustering: el eje que más separa a los equipos europeos no es cómo
# juegan sino qué tan buenos son. Con los 96 equipos (o los ~1.600 jugadores)
# en pantalla, la nube la ordena el nivel y las diferencias dentro del pelotón
# quedan aplastadas contra el margen. Sacar a los grandes deja ver esa mitad de
# la distribución; dejar solo a los grandes deja compararlos entre ellos.
#
# --- Por qué ELO y no una métrica que ya teníamos ---
# El ELO de clubelo se calcula **solo con resultados** y es independiente de
# FBref y de Understat. Segmentar con puntos por partido o con diferencia de
# goles sería circular: se estaría filtrando por una variable que después
# aparece en los ejes.
#
# --- Por qué un desplegable y no dos casillas ---
# El pedido original era "dos botones como los de sub-21", pero los dos grupos
# son complementarios, así que dos casillas independientes tendrían un estado
# —las dos marcadas— que deja el gráfico vacío. El desplegable los hace
# excluyentes por construcción.
NIVEL_FILTER = {
    "col": "nivel",
    "label": "Nivel del club",
    "all_label": "Todos los clubes",
    "clave": "nivel",
    # La nota va dentro de una (i) al lado del rótulo y no como párrafo debajo
    # del desplegable: explicar el umbral toma tres renglones, y son tres
    # renglones fijos de barra lateral para algo que se consulta una vez.
    "info": True,
}


def nivel_filter(df, hint):
    """El filtro de nivel, o None si los datos no traen la columna.

    `elo.csv` es opcional en la consolidación —igual que las tablas `vs`— así
    que el sitio se tiene que poder construir sin él: sin la columna, el
    desplegable no se dibuja en vez de aparecer y no hacer nada al usarlo.
    `options` sale de los valores que de verdad están, por el mismo motivo que
    en el filtro de posición: un desplegable no debe ofrecer una opción que
    deje el gráfico vacío."""
    from consolidate_data import NIVELES

    if "nivel" not in df.columns:
        return None
    opciones = [n for n in NIVELES if (df["nivel"] == n).any()]
    if not opciones:
        return None
    return {**NIVEL_FILTER, "options": opciones, "hint": hint}


sys.path.insert(0, str(CODE_DIR))

from viz_theme import INK, LEAGUE_COLORS, LEAGUE_COLORS_DARK  # noqa: E402

# Las fuentes se sirven desde el propio sitio (`web/static/fonts`, licencia OFL; `build.py` las copia a
# `dist/assets/fonts`). Antes venían de Google Fonts: eso eran dos orígenes más (conexión, TLS) antes de
# poder pintar el texto. Inter es variable (un archivo cubre los pesos 400 a 800) y va partida como en Google:
# `latin` alcanza para el español y es la única que se precarga; `latin-ext` solo se pide si aparece un
# carácter fuera de ese rango (un nombre de jugador con ł, ő, ğ...). Sansita se usa SOLO donde aparece la
# palabra "FutViz" como texto (el resto del sitio es Inter). Abierto con doble clic (`file://`) el navegador
# bloquea fuentes locales y el texto cae en la fuente del sistema: se ve distinto, pero no se rompe nada.
_RANGO_LATIN = ("U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, U+0308, "
                "U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD")
_RANGO_LATIN_EXT = ("U+0100-02BA, U+02BD-02C5, U+02C7-02CC, U+02CE-02D7, U+02DD-02FF, U+0304, U+0308, U+0329, "
                    "U+1D00-1DBF, U+1E00-1E9F, U+1EF2-1EFF, U+2020, U+20A0-20AB, U+20AD-20C4, U+2113, "
                    "U+2C60-2C7F, U+A720-A7FF")
FUENTES = [   # (familia, peso, archivo, rango)
    ("Inter", "400 800", "inter-400-800-latin.woff2", _RANGO_LATIN),
    ("Inter", "400 800", "inter-400-800-latin-ext.woff2", _RANGO_LATIN_EXT),
    ("Sansita", "700", "sansita-700-latin.woff2", _RANGO_LATIN),
    ("Sansita", "700", "sansita-700-latin-ext.woff2", _RANGO_LATIN_EXT),
    ("Sansita", "800", "sansita-800-latin.woff2", _RANGO_LATIN),
    ("Sansita", "800", "sansita-800-latin-ext.woff2", _RANGO_LATIN_EXT),
]


def font_links(prefijo=""):
    """Las fuentes de una página. `prefijo` es la ruta de la página a la raíz del sitio ("" o "../")."""
    caras = "".join(
        f"@font-face{{font-family:'{fam}';font-style:normal;font-weight:{peso};font-display:swap;"
        f"src:url({prefijo}assets/fonts/{archivo}) format('woff2');unicode-range:{rango};}}"
        for fam, peso, archivo, rango in FUENTES)
    return (f'<link rel="preload" href="{prefijo}assets/fonts/{FUENTES[0][2]}" as="font" type="font/woff2" crossorigin>\n'
            f"<style>{caras}</style>")


FONT_LINKS = font_links()   # para las páginas que cuelgan de la raíz

# El logo tiene dos versiones: `assets/logo.png` (slate, para el tema claro) y `assets/logo-dark.png`
# (el slate pasa a `--color-primary` oscuro; ver `build.py:_trim_oscuro`). Van las dos <img> y el CSS de
# `BRAND_ROOT_CSS` muestra una según `html[data-theme]`, el mismo patrón que los thumbnails de la landing.
# `prefijo` es la ruta de la raíz del sitio a la página ("" o "../").
def logo_img(prefijo="", clase="site-logo", alt="FutViz — volver al inicio"):
    return (f'<img class="{clase} logo-theme-light" src="{prefijo}assets/logo.png" alt="{alt}">'
            f'<img class="{clase} logo-theme-dark" src="{prefijo}assets/logo-dark.png" alt="" aria-hidden="true">')


# El favicon claro y, para pestañas oscuras, el de `favicon-dark.png`. Este sigue el tema del SISTEMA
# (`prefers-color-scheme`), no el botón de la página: la pestaña del navegador no la controla la página.
def favicon_links(prefijo=""):
    return (f'<link rel="icon" type="image/png" href="{prefijo}favicon.png">\n'
            f'<link rel="icon" type="image/png" href="{prefijo}favicon-dark.png" media="(prefers-color-scheme: dark)">')


# Se corre lo antes posible en <head> (antes de pintar) para que la página
# no "flashee" en claro y después salte a oscuro. Lee la preferencia
# guardada; si no hay ninguna, usa la del sistema operativo/navegador.
THEME_INIT_SCRIPT = """<script>
(function() {
  try {
    var stored = localStorage.getItem('futviz-theme');
    var theme = stored || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    document.documentElement.setAttribute('data-theme', theme);
  } catch (e) {}
})();
</script>"""

# Botón sol/luna — el ícono que se muestra es el modo AL QUE SE CAMBIA al
# hacer click (luna visible en modo claro = "click para oscuro"), convención
# estándar. Mismo id en las tres plantillas, un solo botón por página.
THEME_TOGGLE_HTML = """<button type="button" class="theme-toggle" id="theme-toggle" aria-label="Cambiar entre modo claro y oscuro">
  <svg class="icon-sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>
  </svg>
  <svg class="icon-moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z"/>
  </svg>
</button>"""


# El buscador (jugadores, equipos, gráficas y artículos). Es UN solo marcado y UN solo script
# (`web/static/buscador.js`) para todo el sitio. En la portada es el campo grande del hero; en las demás
# páginas vive dentro de un <dialog> que abre la lupa de la barra (ver `site_bar`). Los ids llevan el prefijo
# `buscador-` porque otras páginas ya tienen un `#anuncio` (el lector de Machine Learning) y no deben chocar.
#
#  `accion`   a dónde lleva el formulario sin JS: la página de gráficas, con la ruta de la página a la raíz.
#  `prefijo`  esa ruta ("" o "../"): el script la antepone al pedir el índice y a los enlaces a artículos.
#  `ejemplo`  el jugador que se sugiere teclear; solo la portada lo trae (lo toma de los datos).
BUSCADOR_HTML = """<form class="buscador" id="buscador" action="__ACCION__" data-prefijo="__PREFIJO__" role="search">
      <label class="sr-only" for="buscador-q">Busca un jugador, un equipo o una gráfica</label>
      <div class="campo">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
        <input id="buscador-q" name="q" type="search" placeholder="__PLACEHOLDER__"__EJEMPLO_ATTR__
          autocomplete="off" autocapitalize="off" spellcheck="false" enterkeyhint="search"
          role="combobox" aria-expanded="false" aria-controls="buscador-lista" aria-autocomplete="list">
        <button type="button" class="cerrar" id="buscador-cerrar">Cerrar</button>
      </div>
      <div class="panel" id="buscador-panel" hidden>
        <ul id="buscador-lista" role="listbox" aria-label="Resultados de la búsqueda"></ul>
        <div class="aviso" id="buscador-aviso" hidden></div>
      </div>
      <p class="sr-only" id="buscador-anuncio" aria-live="polite"></p>
    </form>"""


def buscador_html(accion, prefijo="", ejemplo=None):
    """El formulario del buscador. `ejemplo` ya viene escapado para HTML."""
    if ejemplo:
        placeholder = f"Prueba con {ejemplo}, un equipo o una gráfica…"
        atributo = f' data-ejemplo="{ejemplo}"'
    else:
        placeholder, atributo = "Jugador, equipo o gráfica…", ""
    return (BUSCADOR_HTML.replace("__ACCION__", accion).replace("__PREFIJO__", prefijo)
            .replace("__PLACEHOLDER__", placeholder).replace("__EJEMPLO_ATTR__", atributo))


LUPA_SVG = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
            'stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>')


# Barra de arriba de todas las páginas: logo a la izquierda (vuelve al inicio), secciones, lupa y tema a la derecha.
# `actual` es el nombre de la sección de la página ("Análisis exploratorio", "Machine Learning") o None en la
# portada; esa sección lleva `aria-current`. El CSS está en `BRAND_ROOT_CSS` (`.sitebar`).
#
# Los enlaces de la barra usan el nombre corto de `SECTION_META[...]["barra"]` ("Gráficas", "Modelos"): los
# títulos de las páginas siguen siendo "Análisis exploratorio" y "Machine Learning", y el nombre completo va en
# `aria-label` y `title` del enlace (el `aria-label` contiene el texto visible, como pide WCAG 2.5.3).
#
# La lupa abre el buscador desde cualquier página (`buscador.js`). Con `portada=True` no hay <dialog> ni
# <script>: la portada ya tiene el campo grande y su propio <script>, y la lupa solo lo enfoca.
def site_bar(prefijo="", actual=None, portada=False):
    def enlace(nombre):
        meta = SECTION_META[nombre]
        marca = ' aria-current="page"' if nombre == actual else ""
        return (f'<a href="{prefijo}{meta["slug"]}.html"{marca} aria-label="{meta["barra"]["titulo"]}" '
                f'title="{meta["barra"]["titulo"]}">{meta["barra"]["texto"]}</a>')
    inicio = ' aria-current="page"' if actual is None else ""
    if portada:
        lupa_attrs, dialogo = 'aria-controls="buscador-q"', ""
    else:
        lupa_attrs = 'aria-haspopup="dialog" aria-expanded="false" aria-controls="buscador-dialogo"'
        dialogo = (f'\n  <dialog class="buscar" id="buscador-dialogo" aria-label="Buscar en FutViz">\n'
                   f'    {buscador_html(prefijo + SECTION_META["Análisis exploratorio"]["slug"] + ".html", prefijo)}\n'
                   f'  </dialog>\n'
                   f'  <script src="{prefijo}assets/buscador.js" defer></script>')
    return (f'<div class="sitebar">\n'
            f'  <a class="marca" href="{prefijo}index.html"{inicio}>{logo_img(prefijo)}</a>\n'
            f'  <nav class="sitebar-nav" aria-label="Secciones">'
            f'{enlace("Análisis exploratorio")}{enlace("Machine Learning")}</nav>\n'
            f'  <div class="sitebar-acciones">\n'
            f'    <button type="button" class="buscar-abrir" id="buscador-abrir" aria-label="Buscar" title="Buscar (tecla /)" '
            f'aria-keyshortcuts="/" {lupa_attrs}>{LUPA_SVG}</button>\n'
            f'    {THEME_TOGGLE_HTML}\n'
            f'  </div>{dialogo}\n'
            f'</div>')

# Fondo y borde del tema claro: UNA definición. `BRAND_ROOT_CSS` los pone en `--color-bg` / `--color-border` y
# de aquí salen también el fallback del <meta theme-color> y el placeholder de los previews (`build.py`).
# El fondo pasó del lavanda #EFEDF7 (matiz 252°) a un blanco azulado: la marca es slate (192°) + verde.
COLOR_BG_CLARO = "#F2F6F8"
COLOR_BORDE_CLARO = "#DAE3E8"

# El <meta name="theme-color"> de todas las páginas (barra del navegador en móvil). El valor es solo el de
# arranque, el del tema claro: `THEME_SYNC_JS` lo reescribe con el `--color-bg` del tema en uso.
THEME_COLOR_META = f'<meta name="theme-color" content="{COLOR_BG_CLARO}">'

# Lo que TODAS las páginas hacen con el tema además del botón, en un solo lugar: se inserta (con
# `.replace("__THEME_SYNC__", ...)`) dentro del IIFE de `THEME_TOGGLE_SCRIPT` y de `PLOTLY_THEME_SCRIPT`,
# que son los dos scripts de tema que existen (cada página lleva uno).
#  1. theme-color: la barra del navegador sigue al fondo de la página, al cargar y en cada
#     `futviz-theme-change`. Se lee la variable CSS (`--color-bg`) y no el fondo del <body>, que tiene
#     una transición y justo al cambiar de tema todavía devuelve el color viejo.
#  2. Sistema operativo: mientras NO haya preferencia guardada (`futviz-theme`), un cambio del tema del
#     SO con la página abierta cambia el de la página, igual que el botón (mismo evento). En cuanto la
#     persona usa el botón queda una preferencia guardada y el SO deja de mandar. Si el navegador no
#     deja leer localStorage cuenta como "sin preferencia".
THEME_SYNC_JS = """  var metaTema = document.querySelector('meta[name="theme-color"]');
  function sincronizarThemeColor() {
    if (metaTema) metaTema.content = getComputedStyle(document.documentElement).getPropertyValue('--color-bg').trim();
  }
  document.addEventListener('futviz-theme-change', sincronizarThemeColor);
  sincronizarThemeColor();

  var oscuroSO = window.matchMedia('(prefers-color-scheme: dark)');
  function alCambiarElSistema(e) {
    try { if (localStorage.getItem('futviz-theme')) return; } catch (err) {}
    var tema = e.matches ? 'dark' : 'light';
    if (document.documentElement.getAttribute('data-theme') === tema) return;
    document.documentElement.setAttribute('data-theme', tema);
    document.dispatchEvent(new CustomEvent('futviz-theme-change', {detail: {theme: tema}}));
  }
  if (oscuroSO.addEventListener) oscuroSO.addEventListener('change', alCambiarElSistema);
  else if (oscuroSO.addListener) oscuroSO.addListener(alCambiarElSistema);
"""

THEME_TOGGLE_SCRIPT = """<script>
(function() {
__THEME_SYNC__
  var btn = document.getElementById('theme-toggle');
  if (!btn) return;
  btn.addEventListener('click', function() {
    var current = document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
    var next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    try { localStorage.setItem('futviz-theme', next); } catch (e) {}
    document.dispatchEvent(new CustomEvent('futviz-theme-change', {detail: {theme: next}}));
  });
})();
</script>""".replace("__THEME_SYNC__", THEME_SYNC_JS)

# Solo para páginas de chart con un gráfico Plotly (kind != radar/bar — ver
# write_chart_page). El fondo del gráfico ya es transparente (paper/plot
# bgcolor, ver apply_plotly_theme() en viz_theme.py) así que sigue el tema
# de la página solo; lo que hace falta recolorear a mano vía JS es el
# TEXTO/LÍNEAS, que Plotly guarda como color fijo en el layout — no hay
# variables CSS ahí adentro. Los colores replican los tokens INK del tema
# claro y los --color-x oscuros del sitio (ver BRAND_ROOT_CSS).
PLOTLY_THEME_SCRIPT = """<script>
(function() {
  var LIGHT = __INK_CLARO__;
  var DARK = {primary:'#D7E4E7', secondary:'#C7D3D6', muted:'#8CA0A5', grid:'#2C393C', axis:'#3A4A4E', surface:'#1B2426'};

  // Los colores de liga son [claro, oscuro] — mismo hue, distinta luminosidad
  // y croma (ver LEAGUE_COLORS_DARK en viz_theme.py para por qué no alcanza
  // con usar los mismos en los dos modos).
  var LIGAS = __LEAGUE_COLORS__;

  function conAlpha(hex, alpha) {
    var n = parseInt(hex.slice(1), 16);
    return 'rgba(' + [(n >> 16) & 255, (n >> 8) & 255, n & 255].join(',') + ',' + alpha + ')';
  }
  function alphaDe(css) {
    var m = /rgba?\\([^)]*,\\s*([0-9.]+)\\s*\\)/.exec(css || '');
    return m ? m[1] : null;
  }

  // Los colores de liga de un gráfico, listos para UNA sola llamada a Plotly.
  //
  // Se agrupan por el juego de propiedades que toca cambiar —un box no tiene lo
  // mismo que un scatterpolar, y una propiedad ausente no se toca porque un
  // restyle se la inventaría— y dentro de cada grupo los valores van como
  // arreglo, uno por traza. En la práctica las 5 trazas de liga de un gráfico
  // son del mismo tipo, así que sale un solo grupo. Repintarlas de a una era
  // un redibujo por traza: en un scatter de 1.900 puntos, ~1.100ms de cambio
  // de tema contra los ~60 que tarda así.
  function ligasUpdate(gd, theme) {
    var i = theme === 'dark' ? 1 : 0;
    var grupos = [], porFirma = {};
    (gd.data || []).forEach(function(t, idx) {
      var par = LIGAS[t.name];
      if (!par) return;
      var color = par[i], props = {};
      if (t.marker && t.marker.color) props['marker.color'] = color;
      if (t.line && t.line.color) props['line.color'] = color;
      var a = alphaDe(t.fillcolor);
      if (a !== null) props.fillcolor = conAlpha(color, a);
      var claves = Object.keys(props);
      if (!claves.length) return;
      var firma = claves.join('|');
      var g = porFirma[firma];
      if (!g) { g = porFirma[firma] = {idx: [], vals: {}}; grupos.push(g); }
      g.idx.push(idx);
      claves.forEach(function(p) { (g.vals[p] = g.vals[p] || []).push(props[p]); });
    });

    // Los títulos de cada subplot del radar son anotaciones pintadas con el
    // color de su liga; se las reconoce justamente por eso. Van al patch del
    // layout para que entren en la misma llamada.
    var anns = (gd.layout && gd.layout.annotations) || [], lay = {};
    anns.forEach(function(an, k) {
      var col = ((an.font && an.font.color) || '').toLowerCase();
      if (!col) return;
      Object.keys(LIGAS).forEach(function(liga) {
        if (LIGAS[liga].indexOf(col) !== -1) {
          lay['annotations[' + k + '].font.color'] = LIGAS[liga][i];
        }
      });
    });
    return {grupos: grupos, layout: lay};
  }

  // Los ejes se descubren leyendo el layout real de cada gráfico en vez de
  // listar 'xaxis'/'yaxis' a mano: un gráfico con subplots tiene xaxis2,
  // yaxis2..., y un radar no tiene ejes cartesianos sino `polar`. Con la
  // lista fija, esos se quedaban con la tinta clara sobre fondo oscuro.
  function patchFor(gd, theme) {
    var c = theme === 'dark' ? DARK : LIGHT;
    var patch = {
      'font.color': c.primary, 'title.font.color': c.primary,
      'legend.font.color': c.secondary,
      'hoverlabel.bgcolor': c.surface, 'hoverlabel.font.color': c.primary
    };
    Object.keys(gd._fullLayout || {}).forEach(function(k) {
      if (/^[xy]axis\\d*$/.test(k)) {
        patch[k + '.tickfont.color'] = c.muted;
        patch[k + '.title.font.color'] = c.secondary;
        patch[k + '.gridcolor'] = c.grid;
        patch[k + '.zerolinecolor'] = c.axis;
        patch[k + '.linecolor'] = c.axis;
      } else if (/^polar\\d*$/.test(k)) {
        patch[k + '.angularaxis.tickfont.color'] = c.secondary;
        patch[k + '.angularaxis.gridcolor'] = c.grid;
        patch[k + '.angularaxis.linecolor'] = c.axis;
        patch[k + '.radialaxis.tickfont.color'] = c.muted;
        patch[k + '.radialaxis.gridcolor'] = c.grid;
        patch[k + '.radialaxis.linecolor'] = c.axis;
      }
    });
    return patch;
  }

  // La barra de color de un mapa de calor no es un eje del layout, así que
  // patchFor() no la ve: sus rótulos viven dentro de la traza y hay que
  // recolorearlos con restyle o se quedan en tinta oscura sobre fondo oscuro.
  function patchColorbars(gd, theme) {
    var c = theme === 'dark' ? DARK : LIGHT;
    var conBarra = [];
    (gd.data || []).forEach(function(t, i) { if (t.colorbar) conBarra.push(i); });
    if (conBarra.length) {
      Plotly.restyle(gd, {'colorbar.tickfont.color': c.muted,
                          'colorbar.title.font.color': c.secondary}, conBarra);
    }
  }

  function syncPlotly() {
    if (!window.Plotly) return;
    var theme = document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
    document.querySelectorAll('.js-plotly-plot').forEach(function(gd) {
      // Un gráfico en una pestaña oculta (display:none) no se toca: Plotly mide
      // cero ahí y el relayout le descoloca título y subtítulo. Se recolorea al
      // mostrarlo (section_views llama otra vez a esta función). `tema` recuerda
      // con qué tinta quedó, así no se repinta lo que ya está bien.
      if (!gd.getClientRects().length || gd.dataset.tema === theme) return;
      gd.dataset.tema = theme;
      var ligas = ligasUpdate(gd, theme);
      var lay = patchFor(gd, theme);
      Object.keys(ligas.layout).forEach(function(k) { lay[k] = ligas.layout[k]; });
      // Un solo redibujo: `update` aplica trazas y layout de una pasada, en vez
      // de un relayout más un restyle por traza.
      if (ligas.grupos.length) {
        Plotly.update(gd, ligas.grupos[0].vals, lay, ligas.grupos[0].idx);
        for (var i = 1; i < ligas.grupos.length; i++) {
          Plotly.restyle(gd, ligas.grupos[i].vals, ligas.grupos[i].idx);
        }
      } else {
        Plotly.relayout(gd, lay);
      }
      patchColorbars(gd, theme);
    });
  }
  syncPlotly();
  // Las páginas con vistas montan gráficos DESPUÉS de cargar (ver section_views.py):
  // al montarlos llaman a esto para que nazcan con la tinta del tema actual.
  window.futvizSyncPlotly = syncPlotly;
  // El botón ya llama a syncPlotly; esto cubre el cambio que viene del sistema operativo (es idempotente).
  document.addEventListener('futviz-theme-change', syncPlotly);

__THEME_SYNC__
  var btn = document.getElementById('theme-toggle');
  if (btn) {
    btn.addEventListener('click', function() {
      var current = document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
      var next = current === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      try { localStorage.setItem('futviz-theme', next); } catch (e) {}
      syncPlotly();
      document.dispatchEvent(new CustomEvent('futviz-theme-change', {detail: {theme: next}}));
    });
  }
})();
</script>"""

# El mapa de colores de liga se inyecta desde Python en vez de repetirlo a mano
# en el JS: `viz_theme` es la única definición de la paleta, y una copia acá se
# desincronizaría en cuanto alguien tocara un color.
PLOTLY_THEME_SCRIPT = PLOTLY_THEME_SCRIPT.replace(
    "__LEAGUE_COLORS__",
    json.dumps({liga: [LEAGUE_COLORS[liga].lower(), LEAGUE_COLORS_DARK[liga].lower()]
                 for liga in LEAGUE_COLORS}, ensure_ascii=False),
).replace("__THEME_SYNC__", THEME_SYNC_JS).replace(
    "__INK_CLARO__", json.dumps({k: INK[k] for k in ("primary", "secondary", "muted", "grid", "axis", "surface")}))


@dataclass
class ChartPage:
    slug: str
    section: str
    title: str
    subtitle: str
    body_html: str
    kind: str = "scatter"  # scatter | radar | bar | box — qué ícono mostrar en la grilla de sección

    # Para las secciones con vistas (`section_views.py`): el texto corto de la
    # pestaña y la familia en que se agrupa. Si `tab` va vacío se usa `title`.
    tab: str = ""
    group: str = ""

    # Dónde vive el archivo respecto de dist/ — lo usa la card de la sección
    # para armar el href (ver `write_section_pages`).
    href_prefix: str = "charts/"


@dataclass
class ArticlePage:
    """Análisis largo: prosa + gráficos intercalados, en vez de un solo
    gráfico para explorar. Es otro tipo de contenido, no un ChartPage con
    más texto — un chart page responde "¿cómo se ve X?" y se lee en
    cualquier orden; un artículo sostiene un argumento y el orden importa.

    `body_html` lo arma el módulo del análisis (ver `web/charts/ml_xg.py`)
    con los helpers de `ml_comun.py`; acá solo se envuelve en la plantilla."""

    slug: str
    section: str
    title: str
    subtitle: str      # bajada corta, la que se ve en la card de la sección
    deck: str          # entradilla larga, arriba del artículo
    body_html: str
    fuente: str        # origen de los datos, para el pie del artículo
    kind: str = "article"
    href_prefix: str = "analisis/"
    # Con gráficas de React: la página carga el bundle (`../react/futviz-react.js`) y le dice dónde
    # está `react/` (los análisis cuelgan de `analisis/`, no de la raíz).
    react: bool = False


# Ícono por tipo de gráfico, para que las cards de `equipos.html`/`jugadores.html`
# se puedan distinguir de un vistazo sin abrirlas (antes eran solo texto).
CHART_ICONS = {
    "venn": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="5"/>'
        '<circle cx="8" cy="15" r="5"/><circle cx="16" cy="15" r="5"/></svg>'
    ),
    "scatter": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round"><circle cx="6" cy="16" r="2"/>'
        '<circle cx="12" cy="9" r="2"/><circle cx="18" cy="14" r="2"/><circle cx="15" cy="6" r="2"/></svg>'
    ),
    "radar": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v18M3 12h18M5.6 5.6l12.8 12.8M18.4 5.6 5.6 18.4"/>'
        '<circle cx="12" cy="12" r="8"/></svg>'
    ),
    "bar": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="10" width="4" height="11"/>'
        '<rect x="10" y="5" width="4" height="16"/><rect x="17" y="13" width="4" height="8"/></svg>'
    ),
    "box": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v4M12 17v4"/>'
        '<rect x="6" y="7" width="12" height="10" rx="1"/><path d="M6 12h12"/></svg>'
    ),
    # Serie temporal: los gráficos que miran la evolución a lo largo de las
    # temporadas, no una foto de una sola.
    "line": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round"><path d="M3 20V4M3 20h18"/>'
        '<path d="m6 15 4-5 4 3 5-7"/></svg>'
    ),
    # Explorador: los deslizadores del panel de control, porque lo que
    # distingue a esa página no es la forma del gráfico (es un scatter más)
    # sino que las variables las elige quien mira.
    "explorer": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round"><path d="M4 7h16M4 12h16M4 17h16"/>'
        '<circle cx="9" cy="7" r="2" fill="var(--color-bg)"/>'
        '<circle cx="16" cy="12" r="2" fill="var(--color-bg)"/>'
        '<circle cx="7" cy="17" r="2" fill="var(--color-bg)"/></svg>'
    ),
    # Mapa de calor: la grilla de celdas de distinta intensidad, que es lo
    # único que lo distingue de un gráfico de barras a este tamaño.
    "heatmap": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="1"/>'
        '<path d="M9 3v18M15 3v18M3 9h18M3 15h18"/>'
        '<rect x="9" y="9" width="6" height="6" fill="currentColor" stroke="none"/></svg>'
    ),
    # Artículo: hoja con líneas de texto — distinto de los íconos de
    # gráfico para que en la grilla se note que ahí hay una lectura, no
    # un gráfico suelto.
    "article": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round"><path d="M5 3h9l5 5v13a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z"/>'
        '<path d="M14 3v5h5M8 13h8M8 17h5"/></svg>'
    ),
}


# Slug de archivo para la página de cada sección (dist/{slug}.html), su título y su bajada. La landing
# (`landing.py`) toma de aquí los enlaces del menú y la lectura destacada.
SECTION_META = {
    # Equipos y Jugadores ya no tienen página propia: viven juntos en "Análisis exploratorio"
    # (`section_views.py`). Siguen aquí porque `slug` nombra la carpeta de sus
    # fragmentos y `hub` dice en qué página aparecen.
    "Equipos": {"slug": "equipos", "hub": "Análisis exploratorio"},
    "Jugadores": {"slug": "jugadores", "hub": "Análisis exploratorio"},
    "Análisis exploratorio": {
        "slug": "analisis-exploratorio",
        "description": "Rendimiento, estilo y nivel de jugadores y equipos de las 5 grandes ligas, "
                       "con filtros y un explorador para cruzar cualquier par de variables.",
        # El encabezado de esta página es compacto (`page_header_html`): la bajada visible es esta, de un
        # renglón, y `description` se queda como <meta name="description">. Sin `lead`, la bajada es `description`.
        "lead": "Elige una pregunta, toca un punto y mira quién es.",
        # Cómo se llama la página (el título grande y la pestaña del navegador). La clave de este diccionario sigue siendo
        # "Análisis exploratorio": es un identificador que usan los enlaces, el buscador y los tests, no un texto.
        "titulo": "Explora los datos",
        # Cómo se llama en la barra de arriba (el título de la página sigue siendo el de la clave) y el nombre
        # completo, que va en el `aria-label` y el `title` del enlace.
        "barra": {"texto": "Gráficas", "titulo": "Explora los datos: gráficas de jugadores y equipos"},
        "views": True,
        "entidades": ["Jugadores", "Equipos"],  # orden de la fila de arriba; la primera abre la página
    },
    "Machine Learning": {
        "slug": "machine-learning",
        "description": "Aplicación de modelos de Machine Learning para buscar patrones "
                        "que no estén a simple vista.",
        "barra": {"texto": "Modelos", "titulo": "Machine Learning: modelos y artículos"},
        "reader": True,   # una sola página con lector (`ml_reader.py`), no una grilla de cards
        # Artículos en preparación: salen en el carrusel como "Próximamente" y no cuentan en la
        # landing. Cuando uno se publique, se borra de aquí y entra solo como `ArticlePage`.
        "proximos": [
            {"slug": "valores-jugadores", "title": "Valores de jugadores",
             "subtitle": "En preparación."},
        ],
    },
}

PAGE_TEMPLATE = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{theme_color}
<title>{title} · FutViz</title>
{favicon}
{theme_init_script}
{font_links}
<style>
{brand_root}
  header {{ border-bottom: 1px solid var(--color-border); }}
  main {{ padding: 28px 24px 60px; }}
  /* Tanto los gráficos Plotly (transparentes, texto recoloreado en JS —
     ver PLOTLY_THEME_SCRIPT) como los PNG de matplotlib (dos versiones
     pre-renderizadas, claro/oscuro — ver viz_theme.dark_ink()) siguen el
     tema de la página, así que la tarjeta puede seguir var(--color-bg). */
  /* La tarjeta se estira a lo ancho a propósito; lo que se centra dentro es el
     bloque del gráfico, que sí tiene ancho fijo (ver `viz_theme._centrado`).
     Se probó `width: fit-content` para que la tarjeta se ajustara al gráfico
     y NO sirve: el ancho máximo de un flex con `width:100%` adentro lo calcula
     de menos, y termina encogiendo el gráfico —un boxplot de 800px quedaba en
     520— que es peor que el marco ancho. */
  .chart-scroll {{ max-width: 100%; overflow-x: auto; background: var(--color-bg);
    border: 1px solid var(--color-border); border-radius: 14px; padding: 20px; }}
  img.static-chart {{ max-width: 100%; min-width: 600px; height: auto; border-radius: 6px; display: block; }}
  /* Mismo criterio que el sol/luna y los thumbnails de la landing: dos
     <img>, se muestra una u otra según el tema. */
  img.static-chart-dark {{ display: none; }}
  html[data-theme="dark"] img.static-chart-light {{ display: none; }}
  html[data-theme="dark"] img.static-chart-dark {{ display: block; }}
  @media (max-width: 640px) {{
    main {{ padding: 20px 16px 40px; }}
    .chart-scroll {{ padding: 12px; }}
  }}
</style>
</head>
<body>
<header>
  {site_bar}
</header>
<main><div class="chart-scroll">{body}</div></main>
{theme_toggle_script}
</body>
</html>
"""

# El CSS del buscador (ver `BUSCADOR_HTML`), compartido por la portada y el <dialog> de las demás páginas:
# entra en `BRAND_ROOT_CSS`, así que lo lleva toda página con barra. Los selectores van bajo `.buscador` para no
# chocar con nada de las gráficas ni de los artículos.
#
# - Portada: el formulario es el campo del hero y la lista se despliega debajo. En pantallas chicas, al enfocar
#   el campo, `buscador.js` le pone `.abierto` y ocupa la pantalla (el teclado deja poco espacio).
# - Demás páginas: `dialog.buscar` (modal nativo: foco atrapado, Escape y fondo inerte los pone el navegador),
#   con la lista siempre debajo del campo. Desde 640px abajo ocupa toda la pantalla y muestra "Cerrar".
#   Mientras está abierto la página de atrás no se desliza (`overflow: hidden`) y, en escritorio,
#   `scrollbar-gutter` evita que salte cuando desaparece su barra de scroll (en móvil el <dialog> la tapa).
BUSCADOR_CSS = """
  .buscador { position: relative; max-width: 760px; margin: 0 auto; text-align: left; }
  .buscador .campo { display: flex; align-items: center; gap: 12px; min-height: 60px; padding: 0 16px 0 18px;
    background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 12px;
    transition: border-color .12s ease, box-shadow .12s ease; }
  .buscador .campo:focus-within { border-color: var(--color-interactive); box-shadow: 0 0 0 3px var(--color-interactive-soft); }
  .buscador .campo svg { width: 20px; height: 20px; flex: none; color: var(--color-muted); }
  .buscador .campo input { flex: 1; min-width: 0; height: 58px; border: 0; background: transparent; outline: none;
    font: 500 17px/1.2 "Inter", system-ui, sans-serif; color: var(--color-text-body); }
  .buscador .campo input::placeholder { color: var(--color-muted); opacity: 1; }
  .buscador .campo input::-webkit-search-cancel-button { display: none; }
  .buscador .cerrar { display: none; min-height: 44px; padding: 0 4px; border: 0; background: none; cursor: pointer;
    font: 600 15px "Inter", system-ui, sans-serif; color: var(--color-interactive); }
  .buscador .cerrar:focus-visible { outline: 2px solid var(--color-interactive); outline-offset: 2px; border-radius: 6px; }
  .buscador .panel { position: absolute; left: 0; right: 0; top: calc(100% + 8px); z-index: 30; max-height: min(70vh, 560px);
    overflow-y: auto; overscroll-behavior: contain; background: var(--color-surface);
    border: 1px solid var(--color-border); border-radius: 12px; padding: 8px 0;
    box-shadow: 0 16px 40px color-mix(in srgb, var(--color-primary) 18%, transparent);
    opacity: 0; transform: translateY(-4px); transition: opacity .12s ease, transform .12s ease; }
  .buscador .panel.visible { opacity: 1; transform: none; }
  .buscador .panel[hidden] { display: none; }
  .buscador .panel ul { list-style: none; margin: 0; padding: 0; }
  .buscador .grupo { display: block; padding: 10px 18px 4px; font-size: 11px; font-weight: 700; letter-spacing: .07em;
    text-transform: uppercase; color: var(--color-muted); }
  .buscador .opcion { display: flex; align-items: center; gap: 12px; min-height: 52px; padding: 8px 18px; cursor: pointer; }
  .buscador .opcion[aria-selected="true"] { background: var(--color-interactive-soft); box-shadow: inset 2px 0 0 var(--color-interactive); }
  .buscador .opcion .txt { flex: 1; min-width: 0; }
  .buscador .opcion .nom { display: block; font-size: 15px; font-weight: 600; color: var(--color-primary); }
  .buscador .opcion .det { display: block; font-size: 13px; color: var(--color-muted); }
  /* sobre el resaltado, el gris no llega a 4.5:1 en oscuro: el detalle pasa al color del texto */
  .buscador .opcion[aria-selected="true"] .det { color: var(--color-text-body); }
  .buscador .opcion .acc { flex: none; font-size: 13px; font-weight: 600; color: var(--color-interactive); }
  .buscador .opcion.sec { min-height: 44px; padding-left: 34px; }
  .buscador .opcion.sec .nom { font-weight: 500; font-size: 14px; color: var(--color-text-body); }
  .buscador .opcion mark { background: transparent; color: inherit; text-decoration: underline;
    text-decoration-color: var(--color-interactive); text-decoration-thickness: 2px; text-underline-offset: 3px; }
  .buscador .aviso { padding: 14px 18px; font-size: 14.5px; line-height: 1.5; color: var(--color-text-body); }
  .buscador .aviso a { color: var(--color-interactive); font-weight: 600; }

  /* El buscador dentro de un <dialog> (todas las páginas menos la portada). Sin padding en el <dialog>: así un
     clic sobre él, y no sobre su contenido, es siempre un clic en el fondo oscuro, que lo cierra. */
  dialog.buscar { width: min(680px, calc(100% - 32px)); max-width: none; max-height: calc(100% - 16vh); margin: 8vh auto auto;
    padding: 0; overflow: hidden; border: 1px solid var(--color-border); border-radius: 16px;
    background: var(--color-bg); color: var(--color-text-body); box-shadow: 0 24px 64px rgba(10, 18, 20, .35); }
  dialog.buscar::backdrop { background: rgba(10, 18, 20, .55); }
  dialog.buscar .buscador { max-width: none; padding: 12px; }
  dialog.buscar .campo { min-height: 54px; }
  dialog.buscar .campo input { height: 52px; }
  dialog.buscar .panel { position: static; margin-top: 8px; padding: 4px 0 0; max-height: min(60vh, 460px);
    border: 0; border-radius: 0; background: transparent; box-shadow: none; transform: none; }
  html:has(dialog.buscar[open]) { overflow: hidden; }
  @media (min-width: 641px) { html:has(dialog.buscar[open]) { scrollbar-gutter: stable; } }

  @media (max-width: 640px) {
    .buscador .campo input { font-size: 16px; }   /* 16 px: iOS no hace zoom al enfocar */
    /* Portada: el buscador abierto ocupa la pantalla: el teclado del teléfono deja poco espacio para la lista. */
    .buscador.abierto { position: fixed; inset: 0; z-index: 50; max-width: none; padding: 12px 16px;
      background: var(--color-bg); overflow-y: auto; overscroll-behavior: contain; }
    .buscador.abierto .cerrar { display: inline-flex; align-items: center; }
    .buscador.abierto .panel { position: static; margin-top: 10px; max-height: none; box-shadow: none; }
    /* Demás páginas: el <dialog> es la pantalla; la lista ocupa lo que queda y se desliza ella sola. */
    dialog.buscar { width: 100%; height: 100%; height: 100dvh; max-height: none; margin: 0; border: 0; border-radius: 0; }
    dialog.buscar .buscador { height: 100%; display: flex; flex-direction: column; padding: 12px 16px; }
    dialog.buscar .cerrar { display: inline-flex; align-items: center; }
    dialog.buscar .panel { flex: 1 1 auto; min-height: 0; max-height: none; margin-top: 10px; }
  }
  @media (prefers-reduced-motion: reduce) {
    .buscador .panel, .buscador .campo { transition: none; }
  }
"""

# CSS compartido por las tres capas del sitio (landing, secciones, páginas
# de chart): mismo :root de variables de marca + fade-in de página, para
# que todo el sitio se sienta consistente de punta a punta.
#
# Reglas de uso de color (documentadas acá porque no son obvias del nombre):
# - --color-brand-accent (verde del logo): SOLO en elementos grandes —
#   íconos, bordes de acento, títulos de sección, el dato destacado. Nunca
#   como color de texto chico ni de botón — a ese tamaño no pasa contraste
#   AA sobre el fondo claro del sitio.
# - --color-interactive (verde oscurecido): hover, foco, bordes de card al
#   interactuar — cualquier estado interactivo, más legible que el brand.
# - --color-*-soft son SIEMPRE fondos de baja opacidad (chips, washes de
#   hover), nunca texto — ahí el contraste no aplica.
BRAND_ROOT_CSS = ("""
  :root {
    --color-bg: __BG_CLARO__;
    --color-surface: #FFFFFF;
    --color-primary: #2C4C54;
    --color-brand-accent: #399906;
    --color-brand-accent-soft: rgba(57, 153, 6, 0.12);
    --color-interactive: #2E7A06;
    --color-interactive-soft: rgba(46, 122, 6, 0.10);
    --color-text-body: #1A2E33;
    --color-muted: #57707A;
    --color-border: __BORDE_CLARO__;
  }
  /* Modo oscuro: mismos nombres de variable, valores nuevos — todo lo que
     ya usa var(--color-x) se adapta solo, sin tocar cada regla. Verificado
     que las 5 pasan AA sobre --color-bg/--color-surface oscuros (6.6:1 a
     13.8:1). html[data-theme="dark"] pisa a :root por especificidad
     (selector de atributo sobre elemento > pseudo-clase :root). */
  html[data-theme="dark"] {
    --color-bg: #12181A;
    --color-surface: #1B2426;
    --color-primary: #D7E4E7;
    --color-brand-accent: #5CC22A;
    --color-brand-accent-soft: rgba(92, 194, 42, 0.16);
    --color-interactive: #6FDB3B;
    --color-interactive-soft: rgba(111, 219, 59, 0.14);
    --color-text-body: #C7D3D6;
    --color-muted: #8CA0A5;
    --color-border: #2C393C;
  }
  * { box-sizing: border-box; }
  html { -webkit-text-size-adjust: 100%; background: var(--color-bg); color-scheme: light; }
  html[data-theme="dark"] { color-scheme: dark; }
  body { margin: 0; font-family: "Inter", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
    background: var(--color-bg); color: var(--color-text-body);
    animation: futviz-fade-in .2s ease-out;
    transition: background-color .15s ease, color .15s ease; }
  .wordmark { font-family: "Sansita", "Inter", system-ui, sans-serif; }
  @keyframes futviz-fade-in { from { opacity: 0; } to { opacity: 1; } }
  @media (prefers-reduced-motion: reduce) { body { animation: none; } }

  .sr-only { position: absolute; width: 1px; height: 1px; margin: -1px; padding: 0; overflow: hidden;
    clip: rect(0 0 0 0); white-space: nowrap; border: 0; }

  /* Los dos botones cuadrados de la barra: la lupa del buscador (`.buscar-abrir`) y el tema (`.theme-toggle`). */
  .theme-toggle, .buscar-abrir { flex: none; display: inline-flex; align-items: center; justify-content: center;
    width: 34px; height: 34px; border-radius: 8px; border: 1px solid var(--color-border);
    background: var(--color-surface); color: var(--color-primary); cursor: pointer; padding: 0;
    transition: border-color .15s ease, background-color .15s ease, color .15s ease; }
  .theme-toggle:hover, .buscar-abrir:hover, .buscar-abrir[aria-expanded="true"] { border-color: var(--color-interactive); }
  .theme-toggle:focus-visible, .buscar-abrir:focus-visible { outline: 2px solid var(--color-interactive); outline-offset: 2px; }
  .theme-toggle svg, .buscar-abrir svg { width: 18px; height: 18px; }
  @media (prefers-reduced-motion: reduce) { .theme-toggle, .buscar-abrir { transition: none; } }
  .theme-toggle .icon-sun { display: none; }
  html[data-theme="dark"] .theme-toggle .icon-sun { display: block; }
  html[data-theme="dark"] .theme-toggle .icon-moon { display: none; }

  /* Logo: dos <img> (ver `logo_img`), se muestra la del tema. El selector lleva `img.` para ganarle a
     `.site-logo { display: block }` y `.logo-large`, que las plantillas definen después. */
  img.logo-theme-dark { display: none; }
  html[data-theme="dark"] img.logo-theme-light { display: none; }
  html[data-theme="dark"] img.logo-theme-dark { display: block; }

  /* Barra de arriba (ver `site_bar`): la misma en todas las páginas, para que el logo quede siempre en el
     mismo punto. Va a todo el ancho, sin tope, con 24px a los lados: el mismo margen que el `.shell` del
     análisis exploratorio y el `.reader` de Machine Learning, así el logo cae sobre el panel lateral (en
     pantallas de más de 1880px esos dos se centran y la barra no). */
  .sitebar { display: flex; align-items: center; flex-wrap: wrap; gap: 0 24px; min-height: 72px; padding: 0 24px; }
  .sitebar .marca { display: inline-flex; align-items: center; min-height: 44px; margin-right: auto; line-height: 0; }
  .sitebar .marca img { height: 30px; width: auto; }
  .sitebar-nav { display: flex; flex-wrap: wrap; gap: 0 20px; }
  .sitebar-nav a { display: inline-flex; align-items: center; min-height: 44px; font-size: 14.5px; font-weight: 500;
    color: var(--color-text-body); text-decoration: none; }
  .sitebar-nav a:hover { color: var(--color-interactive); }
  .sitebar-nav a[aria-current="page"] { color: var(--color-primary); font-weight: 600; text-decoration: underline;
    text-decoration-color: var(--color-brand-accent); text-decoration-thickness: 2px; text-underline-offset: 8px; }
  .sitebar-acciones { display: flex; align-items: center; gap: 8px; }
  .sitebar .theme-toggle, .sitebar .buscar-abrir { width: 44px; height: 44px; border-radius: 10px; }
  @media (max-width: 640px) {
    .sitebar { min-height: 0; padding: 10px 16px 0; }   /* dos renglones: logo, lupa y tema; abajo las secciones */
    .sitebar .marca img { height: 26px; }
    .sitebar-nav { order: 3; width: 100%; padding-bottom: 4px; }
  }
""" + BUSCADOR_CSS).replace("__BG_CLARO__", COLOR_BG_CLARO).replace("__BORDE_CLARO__", COLOR_BORDE_CLARO)

SECTION_PAGE_TEMPLATE = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{theme_color}
<title>{name} · FutViz</title>
{favicon}
{theme_init_script}
{font_links}
<style>
{brand_root}
  /* Misma textura de puntos que la landing (opacidad ya subida ~10%),
     pero acá solo en el header — no en toda la página. */
  header {{ padding: 0 0 24px; border-bottom: 1px solid var(--color-border);
    background-image:
      radial-gradient(rgba(44, 76, 84, 0.077) 1.4px, transparent 1.6px),
      radial-gradient(rgba(57, 153, 6, 0.066) 1.4px, transparent 1.6px);
    background-size: 22px 22px, 22px 22px;
    background-position: 0 0, 11px 11px; }}
  .intro {{ max-width: 1880px; margin: 0 auto; padding: 4px 24px 0; }}
  h1 {{ position: relative; font-size: 24px; font-weight: 700; letter-spacing: -0.01em;
    color: var(--color-primary); margin: 0 0 8px; padding-left: 14px; }}
  h1::before {{ content: ""; position: absolute; left: 0; top: 3px; bottom: 3px;
    width: 4px; border-radius: 2px; background: var(--color-brand-accent); }}
  /* 760px y no 640: la bajada de cada sección es UNA frase, y a 640 la más
     larga (Machine Learning) partía en dos renglones dejando dos palabras
     sueltas abajo. En pantallas angostas sigue partiendo, que es lo correcto. */
  .lead {{ color: var(--color-muted); font-size: 14px; line-height: 1.55; max-width: 760px; }}

  main {{ padding: 28px 20px 64px; max-width: 1180px; margin: 0 auto; }}
  .grid {{ display: grid; grid-template-columns: 1fr; gap: 16px; }}

  a.card {{ display: flex; gap: 14px; align-items: flex-start; padding: 18px 20px; border-radius: 12px;
    text-decoration: none; color: inherit; background: var(--color-surface);
    border: 1px solid var(--color-border); box-shadow: 0 1px 2px rgba(44, 76, 84, 0.05);
    transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease, background-color .18s ease; }}
  a.card:hover, a.card:focus-visible {{
    transform: translateY(-2px);
    box-shadow: 0 12px 28px rgba(44, 76, 84, 0.14);
    border-color: var(--color-interactive);
    background: var(--color-interactive-soft);
  }}
  a.card:focus-visible {{ outline: 2px solid var(--color-interactive); outline-offset: 2px; }}
  .card-icon {{ flex: none; display: flex; align-items: center; justify-content: center;
    width: 36px; height: 36px; border-radius: 10px; background: var(--color-brand-accent-soft);
    color: var(--color-primary); }}
  .card-icon svg {{ width: 18px; height: 18px; }}
  a.card .card-title {{ font-size: 15.5px; font-weight: 600; color: var(--color-primary);
    line-height: 1.35; margin-bottom: 6px; }}
  a.card .card-sub {{ font-size: 13px; font-weight: 400; color: var(--color-muted); line-height: 1.5; }}

  /* Variante "herramienta" (Crea tu gráfico). Ocupa la fila entera y va con
     el fondo de acento porque no es una gráfica más de la grilla: las otras
     son una lectura ya hecha y esta es un banco de trabajo. Va al final, así
     que la fila completa además cierra la grilla en vez de dejar una card
     suelta en la última fila. */
  a.card--tool {{ grid-column: 1 / -1; position: relative; align-items: center;
    gap: 18px; padding: 24px 26px 24px 30px; overflow: hidden;
    background: var(--color-brand-accent-soft); border-color: rgba(57, 153, 6, 0.35); }}
  /* Misma barra de acento que el <h1> de la sección. */
  a.card--tool::before {{ content: ""; position: absolute; left: 0; top: 0; bottom: 0;
    width: 4px; background: var(--color-brand-accent); }}
  a.card--tool .card-icon {{ width: 46px; height: 46px; border-radius: 12px;
    background: var(--color-surface); }}
  a.card--tool .card-icon svg {{ width: 22px; height: 22px; }}
  a.card--tool .card-title {{ font-size: 18px; }}
  a.card--tool .card-sub {{ font-size: 13.5px; max-width: 66ch; }}
  .card-cta {{ display: none; }}

  @media (min-width: 640px) {{
    header {{ padding: 20px 32px 28px; }}
    h1 {{ font-size: 28px; }}
    .lead {{ font-size: 15px; }}
    main {{ padding: 36px 32px 72px; }}
    .grid {{ grid-template-columns: repeat(2, 1fr); gap: 18px; }}
    .card-cta {{ display: flex; align-items: center; gap: 7px; flex: none; margin-left: auto;
      font-size: 13.5px; font-weight: 600; color: var(--color-interactive); }}
    .card-cta svg {{ width: 16px; height: 16px; }}
    a.card--tool:hover .card-cta svg {{ transform: translateX(3px); }}
    .card-cta svg {{ transition: transform .18s ease; }}
  }}
  @media (min-width: 960px) {{
    .grid {{ grid-template-columns: repeat(3, 1fr); gap: 20px; }}
  }}
</style>
</head>
<body>
<header>
  {site_bar}
  <div class="intro">
    <h1>{name}</h1>
    <div class="lead">{description}</div>
  </div>
</header>
<main><div class="grid">{cards}</div></main>
{theme_toggle_script}
</body>
</html>
"""

CARD_TEMPLATE = """<a class="card" href="{href}">
  <div class="card-icon">{icon}</div>
  <div>
    <div class="card-title">{title}</div>
    <div class="card-sub">{subtitle}</div>
  </div>
</a>
"""

# La card de las páginas `kind="explorer"`. Es otra plantilla y no la misma con
# una clase extra porque lleva la llamada a la acción, que las otras no tienen.
# Ver `a.card--tool` en el CSS de la página de sección para por qué se distingue.
TOOL_CARD_TEMPLATE = """<a class="card card--tool" href="{href}">
  <div class="card-icon">{icon}</div>
  <div>
    <div class="card-title">{title}</div>
    <div class="card-sub">{subtitle}</div>
  </div>
  <span class="card-cta">Armar el gráfico
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"
      stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
  </span>
</a>
"""


# Encabezado compartido por las dos páginas con panel lateral (el lector de Machine Learning,
# `ml_reader.py`, y las vistas del análisis exploratorio, `section_views.py`): la barra del sitio, título
# de la sección y bajada, más el enlace "saltar al contenido" que solo aparece con el foco del teclado.
# Los dos módulos arman su página con `.replace("__X__", ...)`, no con `.format`: las llaves van simples.
PAGE_HEADER_CSS = """
  html { -webkit-tap-highlight-color: transparent; }
  .page-header { border-bottom: 1px solid var(--color-border);
    background-image:
      radial-gradient(rgba(44, 76, 84, 0.077) 1.4px, transparent 1.6px),
      radial-gradient(rgba(57, 153, 6, 0.066) 1.4px, transparent 1.6px);
    background-size: 22px 22px, 22px 22px; background-position: 0 0, 11px 11px; }
  .page-intro { max-width: 1880px; margin: 0 auto; padding: 4px 24px 26px; }
  h1.page-title { position: relative; font-size: 28px; font-weight: 700; letter-spacing: -0.01em;
    color: var(--color-primary); margin: 0 0 8px; padding-left: 14px; }
  h1.page-title::before { content: ""; position: absolute; left: 0; top: 3px; bottom: 3px;
    width: 4px; border-radius: 2px; background: var(--color-brand-accent); }
  .lead { color: var(--color-muted); font-size: 15px; line-height: 1.55; max-width: 760px; }
  @media (max-width: 640px) {
    .page-intro { padding: 8px 16px 20px; }
    h1.page-title { font-size: 24px; }
    .lead { font-size: 14px; }
  }
  /* Variante compacta (la página de gráficas, ver `page_header_html`): el eje X de la gráfica tiene que caber en
     pantalla, y el título y la bajada de dos renglones se comían ~190 px. Título más chico, bajada de un renglón. */
  /* El título de la página de gráficas: Inter grueso y apretado, sin la barra verde de los demás títulos. */
  .page-header--compacto .page-intro { padding: 0 24px 16px; }
  .page-header--compacto h1.page-title { font-weight: 800; font-size: 32px; line-height: 1.1; letter-spacing: -0.025em;
    margin: 0 0 4px; padding-left: 0; text-wrap: balance; }
  .page-header--compacto h1.page-title::before { display: none; }
  .page-header--compacto .lead { font-size: 14px; line-height: 1.5; max-width: none; }
  @media (max-width: 640px) {
    .page-header--compacto .page-intro { padding: 4px 16px 12px; }
    .page-header--compacto h1.page-title { font-size: 26px; }
    .page-header--compacto .lead { font-size: 13.5px; }
  }

  .skip { position: absolute; left: 12px; top: -48px; z-index: 40; padding: 9px 14px; border-radius: 8px;
    background: var(--color-primary); color: var(--color-bg); font-size: 13px; font-weight: 600; text-decoration: none;
    transition: transform .15s ease; }
  .skip:focus-visible { transform: translateY(60px); outline: 2px solid var(--color-interactive); outline-offset: 2px; }
  @media (prefers-reduced-motion: reduce) { .skip { transition: none; } }
"""

#
# Si la sección tiene `lead` en `SECTION_META` (hoy solo el análisis exploratorio), el encabezado es compacto y
# la bajada visible es ese texto corto; `description` queda solo en el <meta name="description"> de la página.
# Las demás (Machine Learning) siguen con el encabezado de siempre y `description` como bajada.
def page_header_html(nombre):
    meta = SECTION_META[nombre]
    lead = meta.get("lead")
    clase = "page-header page-header--compacto" if lead else "page-header"
    bajada = escapar_html(lead) if lead else "__DESCRIPTION__"
    titulo = escapar_html(meta["titulo"]) if meta.get("titulo") else "__NAME__"
    return f"""<header class="{clase}">
  {site_bar(actual=nombre)}
  <div class="page-intro">
    <h1 class="page-title">{titulo}</h1>
    <div class="lead">{bajada}</div>
  </div>
</header>"""

# CSS de la lectura de un análisis (prosa, figuras, tablas, callouts). Lo comparten la página
# suelta de cada artículo (`ARTICLE_PAGE_TEMPLATE`) y el lector de la sección de Machine
# Learning (`ml_reader.py`): así los dos se ven igual sin mantener el CSS por duplicado.
# Llaves simples a propósito: se inyecta como valor de `.format`, no dentro de la plantilla.
ARTICLE_CSS = """
  /* Dos anchos: la prosa se lee en una columna angosta (~68 caracteres) y
     los gráficos pueden respirar más. Ambos centrados sobre el mismo eje. */
  .wrap { max-width: 720px; margin: 0 auto; }
  .wrap-wide { max-width: 940px; margin: 0 auto; }

  .hero { padding: 48px 0 28px; }
  .kicker { display: inline-block; font-size: 12px; font-weight: 600; letter-spacing: .06em;
    text-transform: uppercase; color: var(--color-primary); background: var(--color-brand-accent-soft);
    padding: 5px 11px; border-radius: 999px; margin-bottom: 18px; }
  .hero h1 { font-size: 32px; line-height: 1.15; font-weight: 800; letter-spacing: -0.02em;
    color: var(--color-primary); margin: 0 0 16px; }
  .deck { font-size: 17px; line-height: 1.6; color: var(--color-muted); margin: 0; }
  article { font-size: 16.5px; line-height: 1.72; }
  article h2 { font-size: 25px; line-height: 1.25; font-weight: 700; letter-spacing: -0.015em;
    color: var(--color-primary); margin: 60px 0 6px; scroll-margin-top: 70px; }
  article h2 .step { display: block; font-size: 12px; font-weight: 600; letter-spacing: .06em;
    text-transform: uppercase; color: var(--color-brand-accent); margin-bottom: 8px; }
  article h3 { font-size: 18px; font-weight: 700; color: var(--color-primary); margin: 38px 0 4px; }
  article p { margin: 16px 0; }
  article ul { margin: 16px 0; padding-left: 22px; }
  article li { margin: 9px 0; }
  article strong { color: var(--color-primary); font-weight: 650; }
  article a { color: var(--color-interactive); }
  article code { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: .88em;
    background: var(--color-brand-accent-soft); padding: 2px 6px; border-radius: 5px;
    color: var(--color-primary); }

  /* Bloque de gráfico: mismo tratamiento de tarjeta que las páginas de
     chart (.chart-scroll) para que se sienta el mismo sitio. */
  figure { margin: 34px auto; }
  .chart-scroll { max-width: 100%; overflow-x: auto; background: var(--color-bg);
    border: 1px solid var(--color-border); border-radius: 14px; padding: 18px; }
  figcaption { font-size: 13px; line-height: 1.5; color: var(--color-muted); margin-top: 12px;
    padding-left: 12px; border-left: 2px solid var(--color-border); }

  .callout { margin: 34px 0; padding: 20px 22px; border-radius: 12px;
    background: var(--color-surface); border: 1px solid var(--color-border);
    border-left: 4px solid var(--color-brand-accent); }
  .callout.warn { border-left-color: #E0891C; }
  .callout .callout-title { font-size: 12px; font-weight: 700; letter-spacing: .06em;
    text-transform: uppercase; color: var(--color-primary); margin-bottom: 8px; }
  .callout p { margin: 8px 0 0; font-size: 15.5px; }
  .callout p:first-of-type { margin-top: 0; }

  /* Dato grande: para el número que sostiene el argumento. */
  .stat { margin: 34px 0; padding: 26px 24px; border-radius: 14px; text-align: center;
    background: var(--color-surface); border: 1px solid var(--color-border); }
  .stat .stat-value { font-size: 46px; font-weight: 800; letter-spacing: -0.02em; line-height: 1;
    color: var(--color-brand-accent); }
  .stat .stat-label { font-size: 14px; color: var(--color-muted); margin-top: 12px; line-height: 1.5; }

  .table-scroll { overflow-x: auto; margin: 30px 0; }
  table { border-collapse: collapse; width: 100%; font-size: 14px; min-width: 520px; }
  th, td { text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--color-border);
    vertical-align: top; }
  thead th { font-size: 11.5px; font-weight: 700; letter-spacing: .05em; text-transform: uppercase;
    color: var(--color-primary); border-bottom-width: 2px; }
  td.num { text-align: right; font-variant-numeric: tabular-nums; }
  tbody tr:hover { background: var(--color-interactive-soft); }

  .article-end { margin: 56px 0 0; padding-top: 26px; border-top: 1px solid var(--color-border);
    display: flex; flex-wrap: wrap; gap: 12px; align-items: center; justify-content: space-between; }
  .article-end a { font-size: 14px; font-weight: 600; text-decoration: none;
    color: var(--color-interactive); }
  .article-end .note { font-size: 12.5px; color: var(--color-muted); }
  @media (max-width: 640px) {
    .hero { padding: 32px 0 22px; }
    .hero h1 { font-size: 26px; }
    .deck { font-size: 15.5px; }
    article { font-size: 16px; }
    article h2 { font-size: 21px; margin-top: 46px; }
    .chart-scroll { padding: 12px; }
    .stat .stat-value { font-size: 36px; }
  }
"""


ARTICLE_PAGE_TEMPLATE = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{theme_color}
<title>{title} · FutViz</title>
{favicon}
<meta name="description" content="{subtitle}">
{theme_init_script}
{font_links}
{react_scripts}
<style>
{brand_root}
  header {{ border-bottom: 1px solid var(--color-border); position: sticky; top: 0; z-index: 20;
    background: color-mix(in srgb, var(--color-bg) 88%, transparent);
    backdrop-filter: blur(8px); }}

  /* Barra de progreso de lectura: en un artículo largo da idea de cuánto
     falta, que es justo lo que una grilla de gráficos no necesita. */
  #progress {{ position: fixed; top: 0; left: 0; height: 3px; width: 0%;
    background: var(--color-brand-accent); z-index: 30; transition: width .1s linear; }}

  main {{ padding: 0 20px 80px; }}

{article_css}
  @media (max-width: 640px) {{
    main {{ padding: 0 16px 56px; }}
    /* En el teléfono la barra ocupa dos renglones: fija se comería un tercio de la pantalla al leer. */
    header {{ position: static; }}
  }}
</style>
</head>
<body>
<div id="progress"></div>
<header>
  {site_bar}
</header>
<main>
  <div class="wrap hero">
    <span class="kicker">{section_name}</span>
    <h1>{title}</h1>
    <p class="deck">{deck}</p>
  </div>
  <article>{body}</article>
  <div class="wrap article-end">
    <a href="../{section_slug}.html#{slug}">&larr; Volver a {section_name}</a>
    <span class="note">Datos: {fuente}</span>
  </div>
</main>
{theme_toggle_script}
<script>
(function() {{
  var bar = document.getElementById('progress');
  function update() {{
    var h = document.documentElement;
    var max = h.scrollHeight - h.clientHeight;
    bar.style.width = (max > 0 ? (h.scrollTop / max) * 100 : 0) + '%';
  }}
  window.addEventListener('scroll', update, {{passive: true}});
  window.addEventListener('resize', update);
  update();
}})();

// PLOTLY_THEME_SCRIPT recolorea ejes, leyenda y hover, pero no las
// anotaciones: sus colores quedan horneados en el HTML al generarlo en
// Python. En el biplot cada flecha de carga ES una anotación, así que sin
// esto el gráfico queda con las etiquetas en tinta clara sobre fondo
// oscuro. Se recorre `gd.layout.annotations` y se repinta cada una.
(function() {{
  function syncAnnotations() {{
    if (!window.Plotly) return;
    var dark = document.documentElement.getAttribute('data-theme') === 'dark';
    var ink = dark ? '#C7D3D6' : '{ink_claro}';
    document.querySelectorAll('.js-plotly-plot').forEach(function(gd) {{
      var anns = (gd.layout && gd.layout.annotations) || [];
      if (!anns.length) return;
      var patch = {{}};
      for (var i = 0; i < anns.length; i++) {{
        patch['annotations[' + i + '].font.color'] = ink;
        if (anns[i].showarrow) patch['annotations[' + i + '].arrowcolor'] = ink;
      }}
      Plotly.relayout(gd, patch);
    }});
  }}
  if (document.readyState === 'loading') {{
    document.addEventListener('DOMContentLoaded', syncAnnotations);
  }} else {{
    syncAnnotations();
  }}
  document.addEventListener('futviz-theme-change', syncAnnotations);
}})();
</script>
</body>
</html>
"""



def write_article_page(page: "ArticlePage", dist_dir: Path) -> Path:
    """Escribe un análisis largo en `dist/analisis/{slug}.html`."""
    out_dir = dist_dir / page.href_prefix.strip("/")
    out_dir.mkdir(parents=True, exist_ok=True)

    section_meta = SECTION_META.get(page.section, {})

    html = ARTICLE_PAGE_TEMPLATE.format(
        slug=page.slug, title=page.title, subtitle=page.subtitle, deck=page.deck, body=page.body_html,
        fuente=page.fuente, section_name=page.section,
        section_slug=section_meta.get("slug", "index"),
        brand_root=BRAND_ROOT_CSS, font_links=font_links("../"), article_css=ARTICLE_CSS,
        theme_init_script=THEME_INIT_SCRIPT, theme_color=THEME_COLOR_META,
        site_bar=site_bar("../", page.section), favicon=favicon_links("../"), ink_claro=INK["secondary"],
        react_scripts=(
            '<script>window.futvizBase="../";</script>\n'
            '<script src="../react/futviz-react.js" defer></script>') if page.react else "",
        # Igual que en las páginas de chart: el toggle también recolorea los
        # gráficos Plotly ya renderizados (ver PLOTLY_THEME_SCRIPT).
        theme_toggle_script=PLOTLY_THEME_SCRIPT,
    )
    out_path = out_dir / f"{page.slug}.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path


def write_chart_page(page: ChartPage, charts_dir: Path) -> Path:
    section_slug = SECTION_META.get(page.section, {}).get("slug", "index")
    # PLOTLY_THEME_SCRIPT sirve para todas las páginas de chart: hace todo
    # lo que THEME_TOGGLE_SCRIPT (toggle + localStorage) y de paso
    # recolorea los gráficos Plotly si hay alguno — en páginas solo con
    # PNG de matplotlib el querySelectorAll no encuentra nada y no hace
    # nada extra, es inofensivo.
    html = PAGE_TEMPLATE.format(
        title=page.title, body=page.body_html,
        section_slug=section_slug, section_name=page.section,
        font_links=font_links("../"), brand_root=BRAND_ROOT_CSS,
        theme_init_script=THEME_INIT_SCRIPT, theme_color=THEME_COLOR_META,
        site_bar=site_bar("../", SECTION_META.get(page.section, {}).get("hub", page.section)),
        favicon=favicon_links("../"), theme_toggle_script=PLOTLY_THEME_SCRIPT,
    )
    out_path = charts_dir / f"{page.slug}.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path


def write_section_pages(pages: list[ChartPage], dist_dir: Path) -> list[Path]:
    """Una página por sección (Equipos, Jugadores) con la grilla de charts
    que antes vivía toda junta en el índice."""
    sections: dict[str, list[ChartPage]] = {}
    for page in pages:
        sections.setdefault(page.section, []).append(page)

    out_paths = []
    for name, section_pages in sections.items():
        meta = SECTION_META[name]
        if meta.get("views") or meta.get("hub") or meta.get("reader"):
            continue  # esas secciones son una sola página (section_views.py, ml_reader.py)
        cards = "".join(
            (TOOL_CARD_TEMPLATE if p.kind == "explorer" else CARD_TEMPLATE).format(
                href=f"{p.href_prefix}{p.slug}.html", title=p.title,
                subtitle=p.subtitle, icon=CHART_ICONS[p.kind])
            for p in section_pages
        )
        html = SECTION_PAGE_TEMPLATE.format(
            name=name, description=meta["description"], cards=cards,
            brand_root=BRAND_ROOT_CSS, font_links=FONT_LINKS,
            theme_init_script=THEME_INIT_SCRIPT, theme_color=THEME_COLOR_META,
            site_bar=site_bar(actual=name), favicon=favicon_links(),
            theme_toggle_script=THEME_TOGGLE_SCRIPT,
        )
        out_path = dist_dir / f"{meta['slug']}.html"
        out_path.write_text(html, encoding="utf-8")
        out_paths.append(out_path)
    return out_paths


def matplotlib_chart_body(fig, slug: str, assets_dir: Path, alt_text: str, variant: str = "light") -> str:
    """Guarda `fig` (matplotlib) como PNG en `assets_dir` y devuelve el
    fragmento <img> que la referencia (ruta relativa a la página del
    gráfico, que vive un nivel arriba de assets_dir). `variant` controla la
    clase CSS que decide si se muestra en claro u oscuro (ver
    `.static-chart-light`/`.static-chart-dark` en PAGE_TEMPLATE) — la
    imagen en sí ya viene renderizada con la tinta correcta (ver
    `viz_theme.dark_ink()`), esto solo elige cuál mostrar."""
    assets_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(assets_dir / f"{slug}.png", bbox_inches="tight")
    cls = "static-chart-light" if variant == "light" else "static-chart-dark"
    return f'<img class="static-chart {cls}" src="assets/{slug}.png" alt="{alt_text}">'
