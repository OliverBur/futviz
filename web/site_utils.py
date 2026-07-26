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
from viz_theme import INK  # noqa: E402


@dataclass
class ChartPage:
    slug: str
    section: str
    title: str
    subtitle: str
    body_html: str


# Slug de archivo para la página de cada sección (dist/{slug}.html) y
# metadatos de la card correspondiente en la landing.
SECTION_META = {
    "Equipos": {
        "slug": "equipos",
        "description": "Rendimiento, estilo de juego y disciplina a nivel de equipo.",
        "icon": (
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
            'stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="10" width="4" height="11"/>'
            '<rect x="10" y="5" width="4" height="16"/><rect x="17" y="13" width="4" height="8"/></svg>'
        ),
    },
    "Jugadores": {
        "slug": "jugadores",
        "description": "Producción individual, eficiencia y perfiles ofensivos.",
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
<style>
  * {{ box-sizing: border-box; }}
  html {{ -webkit-text-size-adjust: 100%; }}
  body {{ margin: 0; font-family: "Segoe UI", Arial, sans-serif;
    background: {surface}; color: {primary}; }}
  header {{ padding: 22px 32px; }}
  header a {{ color: {muted}; text-decoration: none; font-size: 13px; }}
  header a:hover {{ color: {primary}; }}
  main {{ padding: 0 32px 60px; }}
  .chart-scroll {{ max-width: 100%; overflow-x: auto; }}
  img.static-chart {{ max-width: 100%; min-width: 600px; height: auto; border-radius: 6px; display: block; }}
  @media (max-width: 640px) {{
    header {{ padding: 16px; }}
    main {{ padding: 0 16px 40px; }}
  }}
</style>
</head>
<body>
<header>
  <a href="../{section_slug}.html">&larr; Volver a {section_name}</a>
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
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
{brand_root}
  body {{ min-height: 100vh; display: flex; align-items: center; justify-content: center;
    padding: 48px 20px; }}

  .hero {{ max-width: 900px; text-align: center; }}
  h1 {{ font-size: 40px; font-weight: 800; letter-spacing: -0.02em;
    color: var(--color-primary); margin: 0 0 16px; }}
  .lead {{ color: var(--color-muted); font-size: 16px; line-height: 1.6;
    max-width: 60ch; margin: 0 auto; }}

  .cards {{ display: flex; flex-direction: column; align-items: center;
    gap: 20px; margin-top: 44px; }}

  a.hub-card {{ display: block; width: 100%; max-width: 340px; text-align: left;
    text-decoration: none; color: inherit; cursor: pointer;
    background: var(--color-surface); border: 1.5px solid var(--color-primary);
    border-radius: 18px; padding: 30px 28px;
    transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease, background-color .18s ease; }}
  a.hub-card:hover, a.hub-card:focus-visible {{
    transform: translateY(-4px);
    box-shadow: 0 18px 34px rgba(45, 86, 97, 0.16);
    border-color: var(--color-accent);
    background: var(--color-accent-soft);
    outline: none;
  }}
  .hub-icon {{ color: var(--color-accent); width: 40px; height: 40px; margin-bottom: 18px; }}
  .hub-icon svg {{ width: 100%; height: 100%; }}
  .hub-title {{ font-size: 21px; font-weight: 700; color: var(--color-primary); margin-bottom: 8px; }}
  .hub-sub {{ font-size: 14px; color: var(--color-text-body); line-height: 1.5; margin-bottom: 18px; }}
  .hub-count {{ display: inline-block; font-size: 12px; font-weight: 700; text-transform: uppercase;
    letter-spacing: .05em; color: var(--color-primary); background: var(--color-accent-soft);
    border: 1px solid rgba(14, 237, 149, 0.4); border-radius: 999px; padding: 5px 12px; }}

  @media (min-width: 640px) {{
    h1 {{ font-size: 52px; }}
    .lead {{ font-size: 17px; }}
    .cards {{ flex-direction: row; justify-content: center; align-items: stretch; gap: 24px; }}
    a.hub-card {{ flex: 1 1 300px; }}
  }}
</style>
</head>
<body>
<div class="hero">
  <h1>FutViz</h1>
  <p class="lead">Análisis de datos públicos de fbref y Understat de las 5 grandes ligas de la temporada 2025/2026</p>
  <div class="cards">{cards}</div>
</div>
</body>
</html>
"""

HUB_CARD_TEMPLATE = """<a class="hub-card" href="{slug}.html">
  <div class="hub-icon">{icon}</div>
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
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
{brand_root}
  header {{ padding: 32px 20px 24px; border-bottom: 1px solid var(--color-border); }}
  header a {{ color: var(--color-muted); text-decoration: none; font-size: 13px; font-weight: 500; }}
  header a:hover {{ color: var(--color-primary); }}
  h1 {{ font-size: 24px; font-weight: 700; letter-spacing: -0.01em;
    color: var(--color-primary); margin: 14px 0 8px; }}
  .lead {{ color: var(--color-muted); font-size: 14px; line-height: 1.55; max-width: 640px; }}

  main {{ padding: 28px 20px 64px; max-width: 1180px; margin: 0 auto; }}
  .grid {{ display: grid; grid-template-columns: 1fr; gap: 16px; }}

  a.card {{ display: block; padding: 18px 20px; border-radius: 12px;
    text-decoration: none; color: inherit; background: var(--color-surface);
    border: 1px solid var(--color-border); box-shadow: 0 1px 2px rgba(45, 86, 97, 0.05);
    transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease, background-color .18s ease; }}
  a.card:hover, a.card:focus-visible {{
    transform: translateY(-2px);
    box-shadow: 0 12px 28px rgba(45, 86, 97, 0.14);
    border-color: var(--color-accent);
    background: var(--color-accent-soft);
  }}
  a.card .card-title {{ font-size: 15.5px; font-weight: 600; color: var(--color-primary);
    line-height: 1.35; margin-bottom: 6px; }}
  a.card .card-sub {{ font-size: 13px; font-weight: 400; color: var(--color-muted); line-height: 1.5; }}

  @media (min-width: 640px) {{
    header {{ padding: 44px 32px 28px; }}
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
  <a href="index.html">&larr; Volver</a>
  <h1>{name}</h1>
  <div class="lead">{description}</div>
</header>
<main><div class="grid">{cards}</div></main>
</body>
</html>
"""

CARD_TEMPLATE = """<a class="card" href="charts/{slug}.html">
  <div class="card-title">{title}</div>
  <div class="card-sub">{subtitle}</div>
</a>
"""


def write_chart_page(page: ChartPage, charts_dir: Path) -> Path:
    section_slug = SECTION_META.get(page.section, {}).get("slug", "index")
    html = PAGE_TEMPLATE.format(
        title=page.title, subtitle=page.subtitle, body=page.body_html,
        surface=INK["surface"], primary=INK["primary"],
        secondary=INK["secondary"], muted=INK["muted"],
        section_slug=section_slug, section_name=page.section,
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
            CARD_TEMPLATE.format(slug=p.slug, title=p.title, subtitle=p.subtitle)
            for p in section_pages
        )
        html = SECTION_PAGE_TEMPLATE.format(
            name=name, description=meta["description"], cards=cards, brand_root=BRAND_ROOT_CSS,
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
            count=counts.get(name, 0), plural="" if counts.get(name, 0) == 1 else "s",
        )
        for name, meta in SECTION_META.items()
        if name in counts
    )

    html = INDEX_TEMPLATE.format(cards=cards, brand_root=BRAND_ROOT_CSS)
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
