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
FONT_LINKS = """<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">"""


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
# metadatos de la card correspondiente en la landing.
SECTION_META = {
    "Equipos": {
        "slug": "equipos",
        "description": "Rendimiento, estilo de juego y disciplina a nivel de equipo.",
        # Chip verde-menta — la card de Equipos "es" el acento principal de marca.
        "chip_class": "mint",
        "icon": (
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
            'stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="10" width="4" height="11"/>'
            '<rect x="10" y="5" width="4" height="16"/><rect x="17" y="13" width="4" height="8"/></svg>'
        ),
    },
    "Jugadores": {
        "slug": "jugadores",
        "description": "Producción individual, eficiencia y perfiles ofensivos.",
        # Chip azul petróleo — distingue la card de Jugadores de la de Equipos
        # sin salirse de la paleta fija de 5 colores del proyecto.
        "chip_class": "petrol",
        "icon": (
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
            'stroke-linecap="round" stroke-linejoin="round"><circle cx="6" cy="15" r="2.4"/>'
            '<circle cx="13" cy="7" r="2.4"/><circle cx="19" cy="17" r="2.4"/>'
            '<path d="M8 13.5 11 9M15 8.5 17.5 15"/></svg>'
        ),
    },
}

PAGE_TEMPLATE = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · FutViz</title>
{font_links}
<style>
{brand_root}
  header {{ display: flex; align-items: center; justify-content: space-between; gap: 12px;
    padding: 14px 32px; border-bottom: 1px solid var(--color-border); }}
  .crumb {{ color: var(--color-muted); text-decoration: none; font-size: 13px; font-weight: 500; }}
  .crumb:hover {{ color: var(--color-primary); }}
  .site-logo-link {{ flex: none; line-height: 0; }}
  .site-logo {{ height: 30px; width: auto; display: block; }}
  main {{ padding: 28px 32px 60px; }}
  .chart-scroll {{ max-width: 100%; overflow-x: auto; background: var(--color-surface);
    border: 1px solid var(--color-border); border-radius: 14px; padding: 20px; }}
  img.static-chart {{ max-width: 100%; min-width: 600px; height: auto; border-radius: 6px; display: block; }}
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
  <a class="site-logo-link" href="../index.html">
    <img class="site-logo" src="../assets/logo.png" alt="FutViz — volver al inicio">
  </a>
</header>
<main><div class="chart-scroll">{body}</div></main>
</body>
</html>
"""

# CSS compartido por la landing y las páginas de sección: mismo :root de
# variables de marca para que el sitio se sienta consistente de punta a
# punta, aunque el rediseño estructural fuerte solo aplique a la landing.
BRAND_ROOT_CSS = """
  :root {
    --color-primary: #2D5661;
    --color-bg: #EFEDF7;
    --color-accent: #0EED95;
    --color-text-body: #1A2E33;
    --color-accent-soft: rgba(14, 237, 149, 0.125); /* = #0EED9520 */
    --color-surface: #FFFFFF;
    --color-muted: #57707A;
    --color-border: #DEDBEA;
  }
  * { box-sizing: border-box; }
  html { -webkit-text-size-adjust: 100%; }
  body { margin: 0; font-family: "Inter", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
    background: var(--color-bg); color: var(--color-text-body); }
"""

INDEX_TEMPLATE = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FutViz — EDA 5 grandes ligas</title>
{font_links}
<style>
{brand_root}
  body {{ min-height: 100vh; display: flex; align-items: center; justify-content: center;
    padding: 48px 20px;
    background:
      radial-gradient(640px circle at 12% 18%, rgba(14, 237, 149, 0.09), transparent 60%),
      radial-gradient(720px circle at 88% 82%, rgba(45, 86, 97, 0.07), transparent 60%),
      var(--color-bg);
  }}

  .hero {{ max-width: 900px; text-align: center; }}
  h1 {{ margin: 0 0 20px; }}
  .logo-large {{ display: block; width: min(380px, 75vw); height: auto; margin: 0 auto; }}
  .lead {{ color: var(--color-muted); font-size: 16px; line-height: 1.6;
    max-width: 60ch; margin: 0 auto; }}
  .foot {{ color: var(--color-muted); font-size: 12.5px; margin: 56px 0 0; }}

  .cards {{ display: flex; flex-direction: column; align-items: center;
    gap: 20px; margin-top: 44px; }}

  a.hub-card {{ display: block; width: 100%; max-width: 340px; text-align: left;
    text-decoration: none; color: inherit; cursor: pointer;
    background: var(--color-surface); border: 1.5px solid var(--color-primary);
    border-radius: 18px; padding: 30px 28px;
    transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease, background-color .18s ease; }}
  a.hub-card.mint {{ border-color: rgba(14, 237, 149, 0.55); }}
  a.hub-card:hover, a.hub-card:focus-visible {{
    transform: translateY(-4px);
    box-shadow: 0 18px 34px rgba(45, 86, 97, 0.16);
    border-color: var(--color-accent);
    background: var(--color-accent-soft);
  }}
  a.hub-card:focus-visible {{
    outline: 2px solid var(--color-primary);
    outline-offset: 3px;
  }}
  .hub-icon {{ display: flex; align-items: center; justify-content: center;
    width: 56px; height: 56px; border-radius: 14px; margin-bottom: 20px; }}
  .hub-icon svg {{ width: 26px; height: 26px; }}
  .hub-icon.mint {{ background: var(--color-accent-soft); color: var(--color-primary); }}
  .hub-icon.petrol {{ background: rgba(45, 86, 97, 0.10); color: var(--color-primary); }}
  .hub-title {{ font-size: 21px; font-weight: 700; color: var(--color-primary); margin-bottom: 8px; }}
  .hub-sub {{ font-size: 14px; color: var(--color-text-body); line-height: 1.5; margin-bottom: 18px; }}
  .hub-count {{ display: inline-block; font-size: 12px; font-weight: 700; text-transform: uppercase;
    letter-spacing: .05em; color: var(--color-primary); background: var(--color-accent-soft);
    border: 1px solid rgba(14, 237, 149, 0.4); border-radius: 999px; padding: 5px 12px; }}

  @media (min-width: 640px) {{
    .lead {{ font-size: 17px; }}
    .cards {{ flex-direction: row; justify-content: center; align-items: stretch; gap: 24px; }}
    a.hub-card {{ flex: 1 1 300px; }}
  }}
</style>
</head>
<body>
<div class="hero">
  <h1><img class="logo-large" src="assets/logo.png" alt="FutViz"></h1>
  <p class="lead">Análisis de datos públicos de fbref y Understat de las 5 grandes ligas de la temporada 2025/2026</p>
  <div class="cards">{cards}</div>
  <p class="foot">Datos: fbref (equipos) &amp; Understat (jugadores) · Temporada 2025/2026</p>
</div>
</body>
</html>
"""

HUB_CARD_TEMPLATE = """<a class="hub-card {chip_class}" href="{slug}.html">
  <div class="hub-icon {chip_class}">{icon}</div>
  <div class="hub-title">{name}</div>
  <div class="hub-sub">{description}</div>
  <div class="hub-count">{count} gráfica{plural}</div>
</a>
"""

SECTION_PAGE_TEMPLATE = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{name} · FutViz</title>
{font_links}
<style>
{brand_root}
  header {{ padding: 20px 20px 24px; border-bottom: 1px solid var(--color-border); }}
  .topbar {{ display: flex; align-items: center; justify-content: space-between; gap: 12px; }}
  .crumb-current {{ color: var(--color-muted); font-size: 13px; font-weight: 500; }}
  .site-logo-link {{ flex: none; line-height: 0; }}
  .site-logo {{ height: 30px; width: auto; display: block; }}
  h1 {{ font-size: 24px; font-weight: 700; letter-spacing: -0.01em;
    color: var(--color-primary); margin: 16px 0 8px; }}
  .lead {{ color: var(--color-muted); font-size: 14px; line-height: 1.55; max-width: 640px; }}

  main {{ padding: 28px 20px 64px; max-width: 1180px; margin: 0 auto; }}
  .grid {{ display: grid; grid-template-columns: 1fr; gap: 16px; }}

  a.card {{ display: flex; gap: 14px; align-items: flex-start; padding: 18px 20px; border-radius: 12px;
    text-decoration: none; color: inherit; background: var(--color-surface);
    border: 1px solid var(--color-border); box-shadow: 0 1px 2px rgba(45, 86, 97, 0.05);
    transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease, background-color .18s ease; }}
  a.card:hover, a.card:focus-visible {{
    transform: translateY(-2px);
    box-shadow: 0 12px 28px rgba(45, 86, 97, 0.14);
    border-color: var(--color-accent);
    background: var(--color-accent-soft);
  }}
  .card-icon {{ flex: none; display: flex; align-items: center; justify-content: center;
    width: 36px; height: 36px; border-radius: 10px; background: var(--color-accent-soft);
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
    <span class="crumb-current">FutViz / {name}</span>
    <a class="site-logo-link" href="index.html">
      <img class="site-logo" src="assets/logo.png" alt="FutViz — volver al inicio">
    </a>
  </div>
  <h1>{name}</h1>
  <div class="lead">{description}</div>
</header>
<main><div class="grid">{cards}</div></main>
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
    html = PAGE_TEMPLATE.format(
        title=page.title, body=page.body_html,
        section_slug=section_slug, section_name=page.section,
        font_links=FONT_LINKS, brand_root=BRAND_ROOT_CSS,
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
            slug=meta["slug"], name=name, description=meta["description"], icon=meta["icon"],
            chip_class=meta["chip_class"],
            count=counts.get(name, 0), plural="" if counts.get(name, 0) == 1 else "s",
        )
        for name, meta in SECTION_META.items()
        if name in counts
    )

    html = INDEX_TEMPLATE.format(cards=cards, brand_root=BRAND_ROOT_CSS, font_links=FONT_LINKS)
    out_path = dist_dir / "index.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path


def matplotlib_chart_body(fig, slug: str, assets_dir: Path, alt_text: str) -> str:
    """Guarda `fig` (matplotlib) como PNG en `assets_dir` y devuelve el
    fragmento <img> que la referencia (ruta relativa a la página del
    gráfico, que vive un nivel arriba de assets_dir)."""
    assets_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(assets_dir / f"{slug}.png", bbox_inches="tight")
    return f'<img class="static-chart" src="assets/{slug}.png" alt="{alt_text}">'
