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
  body {{ margin: 0; font-family: "Segoe UI", Arial, sans-serif;
    background: {surface}; color: {primary}; }}
  header {{ padding: 22px 32px 6px; }}
  header a {{ color: {muted}; text-decoration: none; font-size: 13px; }}
  header a:hover {{ color: {primary}; }}
  h1 {{ font-size: 22px; margin: 12px 0 4px; }}
  .subtitle {{ color: {secondary}; font-size: 14px; margin-bottom: 22px; max-width: 780px; }}
  main {{ padding: 0 32px 60px; overflow-x: auto; }}
  img.static-chart {{ max-width: 100%; height: auto; border-radius: 6px; }}
</style>
</head>
<body>
<header>
  <a href="../index.html">&larr; Volver</a>
  <h1>{title}</h1>
  <div class="subtitle">{subtitle}</div>
</header>
<main>{body}</main>
</body>
</html>
"""

INDEX_TEMPLATE = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>top5ligas — EDA 5 grandes ligas</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; font-family: "Segoe UI", Arial, sans-serif;
    background: {surface}; color: {primary}; }}
  header {{ padding: 40px 32px 10px; }}
  h1 {{ font-size: 28px; margin: 0 0 6px; }}
  .lead {{ color: {secondary}; font-size: 15px; max-width: 700px; }}
  main {{ padding: 10px 32px 60px; }}
  h2 {{ font-size: 15px; text-transform: uppercase; letter-spacing: .04em;
    color: {muted}; margin: 34px 0 14px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
    gap: 16px; }}
  a.card {{ display: block; padding: 16px 18px; border: 1px solid {axis};
    border-radius: 10px; text-decoration: none; color: inherit;
    background: {surface}; transition: border-color .15s; }}
  a.card:hover {{ border-color: {primary}; }}
  a.card .card-title {{ font-size: 15px; font-weight: 600; margin-bottom: 6px; }}
  a.card .card-sub {{ font-size: 12.5px; color: {secondary}; line-height: 1.4; }}
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

SECTION_TEMPLATE = """<h2>{name}</h2>
<div class="grid">{cards}</div>
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

    html = INDEX_TEMPLATE.format(
        sections="".join(sections_html),
        surface=INK["surface"], primary=INK["primary"],
        secondary=INK["secondary"], muted=INK["muted"], axis=INK["axis"],
    )
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
