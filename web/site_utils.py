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


PAGE_TEMPLATE = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · top5ligas</title>
<style>
  * {{ box-sizing: border-box; }}
  html {{ -webkit-text-size-adjust: 100%; }}
  body {{ margin: 0; font-family: "Segoe UI", Arial, sans-serif;
    background: {surface}; color: {primary}; }}
  header {{ padding: 22px 32px 6px; }}
  header a {{ color: {muted}; text-decoration: none; font-size: 13px; }}
  header a:hover {{ color: {primary}; }}
  h1 {{ font-size: 22px; margin: 12px 0 4px; }}
  .subtitle {{ color: {secondary}; font-size: 14px; margin-bottom: 22px; max-width: 780px; }}
  main {{ padding: 0 32px 60px; }}
  .chart-scroll {{ max-width: 100%; overflow-x: auto; }}
  img.static-chart {{ max-width: 100%; min-width: 600px; height: auto; border-radius: 6px; display: block; }}
  @media (max-width: 640px) {{
    header {{ padding: 16px 16px 4px; }}
    h1 {{ font-size: 19px; }}
    .subtitle {{ font-size: 13px; margin-bottom: 16px; }}
    main {{ padding: 0 16px 40px; }}
  }}
</style>
</head>
<body>
<header>
  <a href="../index.html">&larr; Volver</a>
  <h1>{title}</h1>
  <div class="subtitle">{subtitle}</div>
</header>
<main><div class="chart-scroll">{body}</div></main>
</body>
</html>
"""

INDEX_TEMPLATE = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>top5ligas — EDA 5 grandes ligas</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root {{
    --color-primary: #2D5661;
    --color-bg: #EFEDF7;
    --color-accent: #0EED95;
    --color-text-body: #1A2E33;
    --color-accent-soft: rgba(14, 237, 149, 0.125); /* = #0EED9520 */
    --color-surface: #FFFFFF;
    --color-muted: #57707A;
    --color-border: #DEDBEA;
  }}
  * {{ box-sizing: border-box; }}
  html {{ -webkit-text-size-adjust: 100%; }}
  body {{ margin: 0; font-family: "Inter", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
    background: var(--color-bg); color: var(--color-text-body); }}

  /* Header: separado del resto con un borde inferior sutil */
  header {{ padding: 32px 20px 24px; border-bottom: 1px solid var(--color-border); }}
  h1 {{ font-size: 24px; font-weight: 700; letter-spacing: -0.01em;
    color: var(--color-primary); margin: 0 0 8px; }}
  .lead {{ color: var(--color-muted); font-size: 14px; line-height: 1.55; max-width: 640px; }}

  main {{ padding: 28px 20px 64px; max-width: 1180px; margin: 0 auto; }}
  section + section {{ margin-top: 40px; }}

  /* "Eyebrow": el nombre de sección como badge en verde menta. El verde se
     usa de FONDO (no como texto) — como texto sobre este fondo claro no
     llega al contraste mínimo AA (~1.3:1); el texto va en --color-primary,
     que sobre el verde sí cumple AA cómodo. */
  h2 {{ display: inline-block; font-size: 11.5px; font-weight: 700; text-transform: uppercase;
    letter-spacing: .07em; color: var(--color-primary); margin: 0 0 16px;
    background: var(--color-accent-soft); border: 1px solid rgba(14, 237, 149, 0.4);
    border-radius: 999px; padding: 6px 14px; }}

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

  /* Mobile-first: base = 1 columna; a partir de 640px, 2; desde 960px, 3 */
  @media (min-width: 640px) {{
    header {{ padding: 44px 32px 28px; }}
    h1 {{ font-size: 28px; }}
    .lead {{ font-size: 15px; }}
    main {{ padding: 36px 32px 72px; }}
    section + section {{ margin-top: 48px; }}
    .grid {{ grid-template-columns: repeat(2, 1fr); gap: 18px; }}
  }}
  @media (min-width: 960px) {{
    .grid {{ grid-template-columns: repeat(3, 1fr); gap: 20px; }}
  }}
</style>
</head>
<body>
<header>
  <h1>Top 5 ligas — EDA</h1>
  <div class="lead">Exploración de datos de las 5 grandes ligas europeas, temporada 2025-26.
    A nivel de equipo (fbref) y de jugador (Understat).</div>
</header>
<main>{sections}</main>
</body>
</html>
"""

SECTION_TEMPLATE = """<section>
<h2>{name}</h2>
<div class="grid">{cards}</div>
</section>
"""

CARD_TEMPLATE = """<a class="card" href="charts/{slug}.html">
  <div class="card-title">{title}</div>
  <div class="card-sub">{subtitle}</div>
</a>
"""


def write_chart_page(page: ChartPage, charts_dir: Path) -> Path:
    html = PAGE_TEMPLATE.format(
        title=page.title, subtitle=page.subtitle, body=page.body_html,
        surface=INK["surface"], primary=INK["primary"],
        secondary=INK["secondary"], muted=INK["muted"],
    )
    out_path = charts_dir / f"{page.slug}.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path


def write_index(pages: list[ChartPage], dist_dir: Path) -> Path:
    sections = {}
    for page in pages:
        sections.setdefault(page.section, []).append(page)

    sections_html = []
    for name, section_pages in sections.items():
        cards = "".join(
            CARD_TEMPLATE.format(slug=p.slug, title=p.title, subtitle=p.subtitle)
            for p in section_pages
        )
        sections_html.append(SECTION_TEMPLATE.format(name=name, cards=cards))

    html = INDEX_TEMPLATE.format(sections="".join(sections_html))
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
