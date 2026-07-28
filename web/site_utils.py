"""Helpers para armar el sitio estático a partir de los mismos gráficos que
viven en los notebooks de `code/`. No son parte del EDA — solo empaquetan
el HTML de un gráfico (Plotly vía `viz_theme.sidebar_chart_html`/`plot_html`,
o una figura de matplotlib exportada a PNG) dentro de una página con la
identidad visual del proyecto, más un índice que las enlaza."""

import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
CODE_DIR = REPO_ROOT / "code"

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

  function patchFor(theme) {
    var c = theme === 'dark' ? DARK : LIGHT;
    return {
      'font.color': c.primary, 'title.font.color': c.primary,
      'xaxis.tickfont.color': c.muted, 'xaxis.title.font.color': c.secondary,
      'xaxis.gridcolor': c.grid, 'xaxis.zerolinecolor': c.axis, 'xaxis.linecolor': c.axis,
      'yaxis.tickfont.color': c.muted, 'yaxis.title.font.color': c.secondary,
      'yaxis.gridcolor': c.grid, 'yaxis.zerolinecolor': c.axis, 'yaxis.linecolor': c.axis,
      'legend.font.color': c.secondary,
      'hoverlabel.bgcolor': c.surface, 'hoverlabel.font.color': c.primary
    };
  }

  function syncPlotly() {
    if (!window.Plotly) return;
    var theme = document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
    var patch = patchFor(theme);
    document.querySelectorAll('.js-plotly-plot').forEach(function(gd) { Plotly.relayout(gd, patch); });
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

  a.hub-card {{ display: block; width: 100%; max-width: 380px; text-align: left;
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
  .hub-body {{ padding: 22px 24px 26px; }}
  .hub-title {{ font-size: 21px; font-weight: 700; color: var(--color-primary); margin-bottom: 8px; }}
  .hub-sub {{ font-size: 14px; color: var(--color-text-body); line-height: 1.5; margin-bottom: 18px; }}
  .hub-count {{ display: inline-block; font-size: 12px; font-weight: 700; text-transform: uppercase;
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
  <p class="foot">Datos: FBref (equipos) &amp; Understat (jugadores) · Temporada 2025/2026</p>
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
    <div class="hub-count">{count} gráfica{plural}</div>
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
  .lead {{ color: var(--color-muted); font-size: 14px; line-height: 1.55; max-width: 640px; }}

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

  @media (min-width: 640px) {{
    header {{ padding: 20px 32px 28px; }}
    h1 {{ font-size: 28px; }}
    .lead {{ font-size: 15px; }}
    main {{ padding: 36px 32px 72px; }}
    .grid {{ grid-template-columns: repeat(2, 1fr); gap: 18px; }}
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

CARD_TEMPLATE = """<a class="card" href="charts/{slug}.html">
  <div class="card-icon">{icon}</div>
  <div>
    <div class="card-title">{title}</div>
    <div class="card-sub">{subtitle}</div>
  </div>
</a>
"""


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
            CARD_TEMPLATE.format(slug=p.slug, title=p.title, subtitle=p.subtitle,
                                  icon=CHART_ICONS[p.kind])
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

    cards = "".join(
        HUB_CARD_TEMPLATE.format(
            slug=meta["slug"], name=name, description=meta["description"], preview=meta["preview"],
            preview_dark=meta["preview"].replace(".png", "-dark.png"),
            count=counts.get(name, 0), plural="" if counts.get(name, 0) == 1 else "s",
        )
        for name, meta in SECTION_META.items()
        if name in counts
    )

    html = INDEX_TEMPLATE.format(
        cards=cards, brand_root=BRAND_ROOT_CSS, font_links=FONT_LINKS,
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
