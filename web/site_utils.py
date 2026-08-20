"""Helpers para armar el sitio estático a partir de los mismos gráficos que
viven en los notebooks de `code/`. No son parte del EDA — solo empaquetan
el HTML de un gráfico (Plotly vía `viz_theme.sidebar_chart_html`/`plot_html`,
o una figura de matplotlib exportada a PNG) dentro de una página con la
identidad visual del proyecto, más un índice que las enlaza."""

import re
import sys
from dataclasses import dataclass
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

# Las temporadas que hay descargadas, leídas de las carpetas de `data/` en vez
# de listadas a mano: es lo que dice el pie de la landing, y agregar una
# temporada no tiene por qué obligar a acordarse de tocar un literal acá.
SEASONS = sorted(d.name for d in DATA_DIR.iterdir()
                 if d.is_dir() and re.fullmatch(r"\d{4}-\d{2}", d.name))

# Crédito de fuentes del pie de la landing. FBref publica las tablas de equipo;
# Understat es de donde salen los jugadores (xG/xA, que FBref dejó de publicar
# en la versión gratuita) y el detalle de tiros.
FUENTES_SITIO = (f"Datos: FBref (equipos) y Understat (jugadores y tiros) · "
                 f"Las 5 grandes ligas de Europa, temporadas "
                 f"{SEASONS[0]} a {SEASONS[-1]}")

sys.path.insert(0, str(CODE_DIR))

# Un solo <link> de Google Fonts, con todos los pesos que usa cualquier
# plantilla del sitio (landing, secciones, páginas de chart) — se inyecta
# igual en las tres para que la tipografía no cambie de una capa a otra.
# Sansita se usa SOLO donde aparece la palabra "FutViz" como texto (no hay
# logo de imagen a mano) — el resto del sitio sigue en Inter.
FONT_LINKS = """<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Sansita:wght@700;800&display=swap" rel="stylesheet">"""

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

THEME_TOGGLE_SCRIPT = """<script>
(function() {
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
</script>"""

# Solo para páginas de chart con un gráfico Plotly (kind != radar/bar — ver
# write_chart_page). El fondo del gráfico ya es transparente (paper/plot
# bgcolor, ver apply_plotly_theme() en viz_theme.py) así que sigue el tema
# de la página solo; lo que hace falta recolorear a mano vía JS es el
# TEXTO/LÍNEAS, que Plotly guarda como color fijo en el layout — no hay
# variables CSS ahí adentro. Los colores replican los tokens INK del tema
# claro y los --color-x oscuros del sitio (ver BRAND_ROOT_CSS).
PLOTLY_THEME_SCRIPT = """<script>
(function() {
  var LIGHT = {primary:'#0b0b0b', secondary:'#52514e', muted:'#898781', grid:'#e1e0d9', axis:'#c3c2b7', surface:'#fcfcfb'};
  var DARK = {primary:'#D7E4E7', secondary:'#C7D3D6', muted:'#8CA0A5', grid:'#2C393C', axis:'#3A4A4E', surface:'#1B2426'};

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
      Plotly.relayout(gd, patchFor(gd, theme));
      patchColorbars(gd, theme);
    });
  }
  syncPlotly();

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


@dataclass
class ChartPage:
    slug: str
    section: str
    title: str
    subtitle: str
    body_html: str
    kind: str = "scatter"  # scatter | radar | bar | box — qué ícono mostrar en la grilla de sección

    # Dónde vive el archivo respecto de dist/ — lo usa la card de la sección
    # para armar el href (ver `write_section_pages`).
    href_prefix: str = "charts/"


@dataclass
class ArticlePage:
    """Análisis largo: prosa + gráficos intercalados, en vez de un solo
    gráfico para explorar. Es otro tipo de contenido, no un ChartPage con
    más texto — un chart page responde "¿cómo se ve X?" y se lee en
    cualquier orden; un artículo sostiene un argumento y el orden importa.

    `body_html` lo arma el módulo del análisis (ver `web/charts/ml.py`)
    con los helpers de ahí; acá solo se envuelve en la plantilla."""

    slug: str
    section: str
    title: str
    subtitle: str      # bajada corta, la que se ve en la card de la sección
    deck: str          # entradilla larga, arriba del artículo
    body_html: str
    meta: list         # pares (etiqueta, valor) para la barra de metadatos
    fuente: str        # origen de los datos, para el pie del artículo
    kind: str = "article"
    href_prefix: str = "analisis/"


# Ícono por tipo de gráfico, para que las cards de `equipos.html`/`jugadores.html`
# se puedan distinguir de un vistazo sin abrirlas (antes eran solo texto).
CHART_ICONS = {
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


# Slug de archivo para la página de cada sección (dist/{slug}.html) y
# metadatos de la card correspondiente en la landing. `preview` es el
# thumbnail que se genera en `build.py` (`build_previews()`) — real si
# existe `img/preview-{slug}.png`, si no un placeholder generado.
SECTION_META = {
    "Equipos": {
        "slug": "equipos",
        "description": "Rendimiento, estilo de juego y disciplina a nivel de equipo.",
        "preview": "preview-equipos.png",
    },
    "Jugadores": {
        "slug": "jugadores",
        "description": "Producción individual, eficiencia y perfiles ofensivos.",
        "preview": "preview-jugadores.png",
    },
    # `noun` es lo que se cuenta en la card de la landing: las otras dos
    # secciones ofrecen gráficos sueltos para explorar, esta ofrece
    # análisis para leer de principio a fin.
    "Machine Learning": {
        "slug": "machine-learning",
        "description": "Aplicación de modelos de Machine Learning para buscar patrones "
                        "que no estén a simple vista.",
        "preview": "preview-machine-learning.png",
        "noun": "análisis",
    },
}

PAGE_TEMPLATE = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · FutViz</title>
<link rel="icon" type="image/png" href="../favicon.png">
{theme_init_script}
{font_links}
<style>
{brand_root}
  header {{ display: flex; align-items: center; justify-content: space-between; gap: 12px;
    padding: 14px 32px; border-bottom: 1px solid var(--color-border); }}
  .crumb {{ color: var(--color-muted); text-decoration: none; font-size: 13px; font-weight: 500; }}
  .crumb:hover {{ color: var(--color-interactive); }}
  .header-right {{ display: flex; align-items: center; gap: 14px; }}
  .site-logo-link {{ flex: none; line-height: 0; }}
  .site-logo {{ height: 30px; width: auto; display: block; }}
  main {{ padding: 28px 32px 60px; }}
  /* Tanto los gráficos Plotly (transparentes, texto recoloreado en JS —
     ver PLOTLY_THEME_SCRIPT) como los PNG de matplotlib (dos versiones
     pre-renderizadas, claro/oscuro — ver viz_theme.dark_ink()) siguen el
     tema de la página, así que la tarjeta puede seguir var(--color-bg). */
  .chart-scroll {{ max-width: 100%; overflow-x: auto; background: var(--color-bg);
    border: 1px solid var(--color-border); border-radius: 14px; padding: 20px; }}
  img.static-chart {{ max-width: 100%; min-width: 600px; height: auto; border-radius: 6px; display: block; }}
  /* Mismo criterio que el sol/luna y los thumbnails de la landing: dos
     <img>, se muestra una u otra según el tema. */
  img.static-chart-dark {{ display: none; }}
  html[data-theme="dark"] img.static-chart-light {{ display: none; }}
  html[data-theme="dark"] img.static-chart-dark {{ display: block; }}
  @media (max-width: 640px) {{
    header {{ padding: 12px 16px; }}
    main {{ padding: 20px 16px 40px; }}
    .chart-scroll {{ padding: 12px; }}
    .site-logo {{ height: 24px; }}
  }}
</style>
</head>
<body>
<header>
  <a class="crumb" href="../{section_slug}.html">&larr; {section_name}</a>
  <div class="header-right">
    <a class="site-logo-link" href="../index.html">
      <img class="site-logo" src="../assets/logo.png" alt="FutViz — volver al inicio">
    </a>
    {theme_toggle}
  </div>
</header>
<main><div class="chart-scroll">{body}</div></main>
{theme_toggle_script}
</body>
</html>
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
BRAND_ROOT_CSS = """
  :root {
    --color-bg: #EFEDF7;
    --color-surface: #FFFFFF;
    --color-primary: #2C4C54;
    --color-brand-accent: #399906;
    --color-brand-accent-soft: rgba(57, 153, 6, 0.12);
    --color-interactive: #2E7A06;
    --color-interactive-soft: rgba(46, 122, 6, 0.10);
    --color-text-body: #1A2E33;
    --color-muted: #57707A;
    --color-border: #DEDBEA;
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
  html { -webkit-text-size-adjust: 100%; background: var(--color-bg); }
  body { margin: 0; font-family: "Inter", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
    background: var(--color-bg); color: var(--color-text-body);
    animation: futviz-fade-in .2s ease-out;
    transition: background-color .15s ease, color .15s ease; }
  .wordmark { font-family: "Sansita", "Inter", system-ui, sans-serif; }
  @keyframes futviz-fade-in { from { opacity: 0; } to { opacity: 1; } }
  @media (prefers-reduced-motion: reduce) { body { animation: none; } }

  .theme-toggle { flex: none; display: inline-flex; align-items: center; justify-content: center;
    width: 34px; height: 34px; border-radius: 8px; border: 1px solid var(--color-border);
    background: var(--color-surface); color: var(--color-primary); cursor: pointer; padding: 0;
    transition: border-color .15s ease, background-color .15s ease, color .15s ease; }
  .theme-toggle:hover { border-color: var(--color-interactive); }
  .theme-toggle:focus-visible { outline: 2px solid var(--color-interactive); outline-offset: 2px; }
  .theme-toggle svg { width: 18px; height: 18px; }
  .theme-toggle .icon-sun { display: none; }
  html[data-theme="dark"] .theme-toggle .icon-sun { display: block; }
  html[data-theme="dark"] .theme-toggle .icon-moon { display: none; }
"""

INDEX_TEMPLATE = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FutViz — EDA 5 grandes ligas</title>
<link rel="icon" type="image/png" href="favicon.png">
{theme_init_script}
{font_links}
<style>
{brand_root}
  /* La landing no tiene barra de nav — el toggle queda fijo arriba a la
     derecha de toda la página, no dentro del header centrado. */
  .theme-toggle--floating {{ position: fixed; top: 16px; right: 16px; z-index: 20;
    box-shadow: 0 2px 10px rgba(18, 24, 26, 0.10); }}

  /* Textura de puntos (misma pareja de colores del logo) en toda la
     página, muy tenue — no es ningún motivo futbolero, es un patrón
     geométrico abstracto — más los dos degradados suaves de siempre. */
  body {{
    min-height: 100vh;
    background:
      radial-gradient(640px circle at 12% 10%, rgba(57, 153, 6, 0.07), transparent 60%),
      radial-gradient(720px circle at 88% 14%, rgba(44, 76, 84, 0.06), transparent 60%),
      radial-gradient(rgba(44, 76, 84, 0.077) 1.4px, transparent 1.6px),
      radial-gradient(rgba(57, 153, 6, 0.066) 1.4px, transparent 1.6px),
      var(--color-bg);
    background-size: auto, auto, 22px 22px, 22px 22px, auto;
    background-position: 0 0, 0 0, 0 0, 11px 11px, 0 0;
  }}

  .hero-header {{ text-align: center; padding: 56px 20px 40px; }}
  .logo-large {{ display: block; width: min(460px, 88vw); height: auto; margin: 0 auto 28px; }}

  /* Motivación: es una frase, no una cifra, así que va en tamaño de
     subtítulo y en --color-text-body — el verde queda reservado a las
     dos palabras clave (--color-interactive, no --color-brand-accent:
     es texto chico, tiene que pasar AA). */
  .motivation {{ color: var(--color-text-body); font-size: 14.5px; line-height: 1.6;
    max-width: 56ch; margin: 0 auto; }}
  .motivation .accent-word {{ color: var(--color-interactive); font-weight: 600; }}

  .hub-main {{ max-width: 900px; margin: 0 auto; padding: 44px 20px 56px; text-align: center; }}
  .cards {{ display: flex; flex-direction: column; align-items: center; gap: 20px; }}
  .foot {{ color: var(--color-muted); font-size: 12.5px; margin: 48px 0 0; }}

  /* Columna flex (no block) para que el chip de abajo se pueda empujar al
     fondo de la tarjeta — ver .hub-count. */
  a.hub-card {{ display: flex; flex-direction: column; width: 100%; max-width: 380px;
    text-align: left;
    text-decoration: none; color: inherit; cursor: pointer; overflow: hidden;
    background: var(--color-surface); border: 1px solid var(--color-border);
    border-radius: 18px;
    transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease; }}
  a.hub-card:hover, a.hub-card:focus-visible {{
    transform: translateY(-4px);
    box-shadow: 0 18px 34px rgba(44, 76, 84, 0.16);
    border-color: var(--color-interactive);
  }}
  a.hub-card:focus-visible {{ outline: 2px solid var(--color-interactive); outline-offset: 3px; }}
  .hub-thumb {{ display: block; width: 100%; aspect-ratio: 16 / 10; object-fit: cover;
    background: var(--color-bg); }}
  /* Igual criterio que el toggle sol/luna: dos <img>, se muestra una u
     otra según el tema — el thumbnail oscuro es una captura real en
     oscuro (ver build_previews() en build.py), no un filtro CSS. */
  .hub-thumb-dark {{ display: none; }}
  html[data-theme="dark"] .hub-thumb-light {{ display: none; }}
  html[data-theme="dark"] .hub-thumb-dark {{ display: block; }}
  .hub-body {{ padding: 22px 24px 26px; display: flex; flex-direction: column; flex: 1; }}
  .hub-title {{ font-size: 21px; font-weight: 700; color: var(--color-primary); margin-bottom: 8px; }}
  .hub-sub {{ font-size: 14px; color: var(--color-text-body); line-height: 1.5; margin-bottom: 18px; }}
  /* `margin-top: auto` pega el chip al fondo de la tarjeta: así los tres
     quedan alineados entre sí aunque una descripción ocupe un renglón más
     que las otras (antes el chip flotaba justo debajo del texto y se veía
     desparejo). `align-self` evita que el flex lo estire a todo el ancho. */
  .hub-count {{ display: inline-block; align-self: flex-start; margin-top: auto;
    font-size: 12px; font-weight: 700; text-transform: uppercase;
    letter-spacing: .05em; color: var(--color-primary); background: var(--color-brand-accent-soft);
    border: 1px solid rgba(57, 153, 6, 0.35); border-radius: 999px; padding: 5px 12px; }}

  @media (min-width: 640px) {{
    .hero-header {{ padding: 64px 20px 48px; }}
    .logo-large {{ width: min(560px, 60vw); }}
    .motivation {{ font-size: 16px; }}
    .cards {{ flex-direction: row; justify-content: center; align-items: stretch; gap: 24px; }}
    a.hub-card {{ flex: 1 1 320px; }}
  }}
</style>
</head>
<body>
<div class="theme-toggle--floating">{theme_toggle}</div>
<header class="hero-header">
  <img class="logo-large" src="assets/logo.png" alt="FutViz">
  <p class="motivation">Nació de juntar mi pasión por el <span class="accent-word">fútbol</span> con la
    <span class="accent-word">ciencia de datos</span>: partir de información pública y simple, y sacarle
    todo el jugo posible.</p>
</header>
<main class="hub-main">
  <div class="cards">{cards}</div>
  <p class="foot">{fuentes}</p>
</main>
{theme_toggle_script}
</body>
</html>
"""

HUB_CARD_TEMPLATE = """<a class="hub-card" href="{slug}.html">
  <img class="hub-thumb hub-thumb-light" src="assets/{preview}" alt="Vista previa — {name}">
  <img class="hub-thumb hub-thumb-dark" src="assets/{preview_dark}" alt="Vista previa — {name}">
  <div class="hub-body">
    <div class="hub-title">{name}</div>
    <div class="hub-sub">{description}</div>
    <div class="hub-count">{count} {noun}</div>
  </div>
</a>
"""

SECTION_PAGE_TEMPLATE = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{name} · FutViz</title>
<link rel="icon" type="image/png" href="favicon.png">
{theme_init_script}
{font_links}
<style>
{brand_root}
  /* Misma textura de puntos que la landing (opacidad ya subida ~10%),
     pero acá solo en el header — no en toda la página. */
  header {{ padding: 20px 20px 24px; border-bottom: 1px solid var(--color-border);
    background-image:
      radial-gradient(rgba(44, 76, 84, 0.077) 1.4px, transparent 1.6px),
      radial-gradient(rgba(57, 153, 6, 0.066) 1.4px, transparent 1.6px);
    background-size: 22px 22px, 22px 22px;
    background-position: 0 0, 11px 11px; }}
  .topbar {{ display: flex; align-items: center; justify-content: space-between; gap: 12px; }}
  .crumb-current {{ color: var(--color-muted); font-size: 13px; font-weight: 500; }}
  .crumb-current .wordmark {{ font-weight: 700; }}
  .header-right {{ display: flex; align-items: center; gap: 14px; }}
  .site-logo-link {{ flex: none; line-height: 0; }}
  .site-logo {{ height: 30px; width: auto; display: block; }}
  h1 {{ position: relative; font-size: 24px; font-weight: 700; letter-spacing: -0.01em;
    color: var(--color-primary); margin: 16px 0 8px; padding-left: 14px; }}
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
  .card-badge {{ display: inline-block; margin-bottom: 8px; padding: 3px 9px;
    font-size: 10.5px; font-weight: 700; text-transform: uppercase; letter-spacing: .06em;
    color: var(--color-primary); background: var(--color-surface);
    border: 1px solid rgba(57, 153, 6, 0.35); border-radius: 999px; }}
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
  <div class="topbar">
    <span class="crumb-current"><span class="wordmark">FutViz</span> / {name}</span>
    <div class="header-right">
      <a class="site-logo-link" href="index.html">
        <img class="site-logo" src="assets/logo.png" alt="FutViz — volver al inicio">
      </a>
      {theme_toggle}
    </div>
  </div>
  <h1>{name}</h1>
  <div class="lead">{description}</div>
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
# una clase extra porque lleva cosas que las otras no tienen: el rótulo de
# "herramienta" y la llamada a la acción. Ver `a.card--tool` en el CSS de la
# página de sección para por qué se distingue.
TOOL_CARD_TEMPLATE = """<a class="card card--tool" href="{href}">
  <div class="card-icon">{icon}</div>
  <div>
    <span class="card-badge">Herramienta</span>
    <div class="card-title">{title}</div>
    <div class="card-sub">{subtitle}</div>
  </div>
  <span class="card-cta">Armar el gráfico
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"
      stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
  </span>
</a>
"""


ARTICLE_PAGE_TEMPLATE = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · FutViz</title>
<link rel="icon" type="image/png" href="../favicon.png">
<meta name="description" content="{subtitle}">
{theme_init_script}
{font_links}
<style>
{brand_root}
  header {{ padding: 14px 20px; border-bottom: 1px solid var(--color-border);
    display: flex; align-items: center; justify-content: space-between; gap: 12px;
    position: sticky; top: 0; z-index: 20;
    background: color-mix(in srgb, var(--color-bg) 88%, transparent);
    backdrop-filter: blur(8px); }}
  .crumb {{ color: var(--color-muted); text-decoration: none; font-size: 13px; font-weight: 500; }}
  .crumb:hover {{ color: var(--color-interactive); }}
  .header-right {{ display: flex; align-items: center; gap: 14px; }}
  .site-logo-link {{ flex: none; line-height: 0; }}
  .site-logo {{ height: 26px; width: auto; display: block; }}

  /* Barra de progreso de lectura: en un artículo largo da idea de cuánto
     falta, que es justo lo que una grilla de gráficos no necesita. */
  #progress {{ position: fixed; top: 0; left: 0; height: 3px; width: 0%;
    background: var(--color-brand-accent); z-index: 30; transition: width .1s linear; }}

  main {{ padding: 0 20px 80px; }}

  /* Dos anchos: la prosa se lee en una columna angosta (~68 caracteres) y
     los gráficos pueden respirar más. Ambos centrados sobre el mismo eje. */
  .wrap {{ max-width: 720px; margin: 0 auto; }}
  .wrap-wide {{ max-width: 940px; margin: 0 auto; }}

  .hero {{ padding: 48px 0 28px; }}
  .kicker {{ display: inline-block; font-size: 12px; font-weight: 600; letter-spacing: .06em;
    text-transform: uppercase; color: var(--color-primary); background: var(--color-brand-accent-soft);
    padding: 5px 11px; border-radius: 999px; margin-bottom: 18px; }}
  .hero h1 {{ font-size: 32px; line-height: 1.15; font-weight: 800; letter-spacing: -0.02em;
    color: var(--color-primary); margin: 0 0 16px; }}
  .deck {{ font-size: 17px; line-height: 1.6; color: var(--color-muted); margin: 0; }}
  /* Rejilla de 2 columnas y no flex-wrap: con flex cada dato se dimensiona por
     su contenido, así que se apilaban todos a la izquierda y la segunda columna
     no coincidía entre filas (58px de diferencia), dejando medio ancho vacío.
     Dos columnas porque el dato más largo mide ~300px: con cuatro se partiría
     en dos líneas. */
  .meta {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 18px 32px; margin-top: 26px; padding-top: 20px;
    border-top: 1px solid var(--color-border); }}
  .meta div {{ font-size: 12.5px; color: var(--color-muted); }}
  .meta b {{ display: block; font-size: 10.5px; font-weight: 600; letter-spacing: .06em;
    text-transform: uppercase; color: var(--color-primary); margin-bottom: 3px; }}

  article {{ font-size: 16.5px; line-height: 1.72; }}
  article h2 {{ font-size: 25px; line-height: 1.25; font-weight: 700; letter-spacing: -0.015em;
    color: var(--color-primary); margin: 60px 0 6px; scroll-margin-top: 70px; }}
  article h2 .step {{ display: block; font-size: 12px; font-weight: 600; letter-spacing: .06em;
    text-transform: uppercase; color: var(--color-brand-accent); margin-bottom: 8px; }}
  article h3 {{ font-size: 18px; font-weight: 700; color: var(--color-primary); margin: 38px 0 4px; }}
  article p {{ margin: 16px 0; }}
  article ul {{ margin: 16px 0; padding-left: 22px; }}
  article li {{ margin: 9px 0; }}
  article strong {{ color: var(--color-primary); font-weight: 650; }}
  article a {{ color: var(--color-interactive); }}
  article code {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: .88em;
    background: var(--color-brand-accent-soft); padding: 2px 6px; border-radius: 5px;
    color: var(--color-primary); }}

  /* Bloque de gráfico: mismo tratamiento de tarjeta que las páginas de
     chart (.chart-scroll) para que se sienta el mismo sitio. */
  figure {{ margin: 34px auto; }}
  .chart-scroll {{ max-width: 100%; overflow-x: auto; background: var(--color-bg);
    border: 1px solid var(--color-border); border-radius: 14px; padding: 18px; }}
  figcaption {{ font-size: 13px; line-height: 1.5; color: var(--color-muted); margin-top: 12px;
    padding-left: 12px; border-left: 2px solid var(--color-border); }}

  .callout {{ margin: 34px 0; padding: 20px 22px; border-radius: 12px;
    background: var(--color-surface); border: 1px solid var(--color-border);
    border-left: 4px solid var(--color-brand-accent); }}
  .callout.warn {{ border-left-color: #E0891C; }}
  .callout .callout-title {{ font-size: 12px; font-weight: 700; letter-spacing: .06em;
    text-transform: uppercase; color: var(--color-primary); margin-bottom: 8px; }}
  .callout p {{ margin: 8px 0 0; font-size: 15.5px; }}
  .callout p:first-of-type {{ margin-top: 0; }}

  /* Dato grande: para el número que sostiene el argumento. */
  .stat {{ margin: 34px 0; padding: 26px 24px; border-radius: 14px; text-align: center;
    background: var(--color-surface); border: 1px solid var(--color-border); }}
  .stat .stat-value {{ font-size: 46px; font-weight: 800; letter-spacing: -0.02em; line-height: 1;
    color: var(--color-brand-accent); }}
  .stat .stat-label {{ font-size: 14px; color: var(--color-muted); margin-top: 12px; line-height: 1.5; }}

  .table-scroll {{ overflow-x: auto; margin: 30px 0; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 14px; min-width: 520px; }}
  th, td {{ text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--color-border);
    vertical-align: top; }}
  thead th {{ font-size: 11.5px; font-weight: 700; letter-spacing: .05em; text-transform: uppercase;
    color: var(--color-primary); border-bottom-width: 2px; }}
  td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  tbody tr:hover {{ background: var(--color-interactive-soft); }}

  .article-end {{ margin: 56px 0 0; padding-top: 26px; border-top: 1px solid var(--color-border);
    display: flex; flex-wrap: wrap; gap: 12px; align-items: center; justify-content: space-between; }}
  .article-end a {{ font-size: 14px; font-weight: 600; text-decoration: none;
    color: var(--color-interactive); }}
  .article-end .note {{ font-size: 12.5px; color: var(--color-muted); }}

  @media (max-width: 640px) {{
    main {{ padding: 0 16px 56px; }}
    .hero {{ padding: 32px 0 22px; }}
    .hero h1 {{ font-size: 26px; }}
    .deck {{ font-size: 15.5px; }}
    /* en móvil dos columnas dejarían ~140px por dato: una sola y a lo alto */
    .meta {{ grid-template-columns: 1fr; gap: 14px; }}
    article {{ font-size: 16px; }}
    article h2 {{ font-size: 21px; margin-top: 46px; }}
    .chart-scroll {{ padding: 12px; }}
    .stat .stat-value {{ font-size: 36px; }}
  }}
</style>
</head>
<body>
<div id="progress"></div>
<header>
  <a class="crumb" href="../{section_slug}.html">&larr; {section_name}</a>
  <div class="header-right">
    <a class="site-logo-link" href="../index.html">
      <img class="site-logo" src="../assets/logo.png" alt="FutViz — volver al inicio">
    </a>
    {theme_toggle}
  </div>
</header>
<main>
  <div class="wrap hero">
    <span class="kicker">{section_name}</span>
    <h1>{title}</h1>
    <p class="deck">{deck}</p>
    <div class="meta">{meta}</div>
  </div>
  <article>{body}</article>
  <div class="wrap article-end">
    <a href="../{section_slug}.html">&larr; Volver a {section_name}</a>
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
    var ink = dark ? '#C7D3D6' : '#52514e';
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

META_ITEM_TEMPLATE = "<div><b>{label}</b>{value}</div>"


def write_article_page(page: "ArticlePage", dist_dir: Path) -> Path:
    """Escribe un análisis largo en `dist/analisis/{slug}.html`."""
    out_dir = dist_dir / page.href_prefix.strip("/")
    out_dir.mkdir(parents=True, exist_ok=True)

    meta_html = "".join(META_ITEM_TEMPLATE.format(label=label, value=value)
                        for label, value in page.meta)
    section_meta = SECTION_META.get(page.section, {})

    html = ARTICLE_PAGE_TEMPLATE.format(
        title=page.title, subtitle=page.subtitle, deck=page.deck, body=page.body_html,
        meta=meta_html, fuente=page.fuente, section_name=page.section,
        section_slug=section_meta.get("slug", "index"),
        brand_root=BRAND_ROOT_CSS, font_links=FONT_LINKS,
        theme_init_script=THEME_INIT_SCRIPT, theme_toggle=THEME_TOGGLE_HTML,
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
        font_links=FONT_LINKS, brand_root=BRAND_ROOT_CSS,
        theme_init_script=THEME_INIT_SCRIPT, theme_toggle=THEME_TOGGLE_HTML,
        theme_toggle_script=PLOTLY_THEME_SCRIPT,
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
        cards = "".join(
            (TOOL_CARD_TEMPLATE if p.kind == "explorer" else CARD_TEMPLATE).format(
                href=f"{p.href_prefix}{p.slug}.html", title=p.title,
                subtitle=p.subtitle, icon=CHART_ICONS[p.kind])
            for p in section_pages
        )
        html = SECTION_PAGE_TEMPLATE.format(
            name=name, description=meta["description"], cards=cards,
            brand_root=BRAND_ROOT_CSS, font_links=FONT_LINKS,
            theme_init_script=THEME_INIT_SCRIPT, theme_toggle=THEME_TOGGLE_HTML,
            theme_toggle_script=THEME_TOGGLE_SCRIPT,
        )
        out_path = dist_dir / f"{meta['slug']}.html"
        out_path.write_text(html, encoding="utf-8")
        out_paths.append(out_path)
    return out_paths


def write_index(pages: list[ChartPage], dist_dir: Path) -> Path:
    counts: dict[str, int] = {}
    for page in pages:
        counts[page.section] = counts.get(page.section, 0) + 1

    def _noun(meta, n):
        # "análisis" es invariable en plural, "gráfica" no — por eso el
        # plural se resuelve acá y no concatenando una "s" en la plantilla.
        singular = meta.get("noun", "gráfica")
        return singular if n == 1 else ("análisis" if singular == "análisis" else f"{singular}s")

    cards = "".join(
        HUB_CARD_TEMPLATE.format(
            slug=meta["slug"], name=name, description=meta["description"], preview=meta["preview"],
            preview_dark=meta["preview"].replace(".png", "-dark.png"),
            count=counts.get(name, 0), noun=_noun(meta, counts.get(name, 0)),
        )
        for name, meta in SECTION_META.items()
        if name in counts
    )

    html = INDEX_TEMPLATE.format(
        cards=cards, fuentes=FUENTES_SITIO, brand_root=BRAND_ROOT_CSS, font_links=FONT_LINKS,
        theme_init_script=THEME_INIT_SCRIPT, theme_toggle=THEME_TOGGLE_HTML,
        theme_toggle_script=THEME_TOGGLE_SCRIPT,
    )
    out_path = dist_dir / "index.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path


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
