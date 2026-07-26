"""Genera el sitio estático en `web/dist/` a partir de los gráficos
definidos en `web/charts/`. Uso: `python build.py` (desde `web/`).

No se despliega nada acá — esto solo produce los archivos. El deploy a
Vercel se hace aparte, apuntando `dist/` como directorio de salida."""

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "charts"))

import matplotlib

matplotlib.use("Agg")

from site_utils import write_chart_page, write_index  # noqa: E402
from viz_theme import apply_theme, apply_plotly_theme  # noqa: E402
import teams as teams_charts  # noqa: E402
import players as players_charts  # noqa: E402

WEB_DIR = Path(__file__).resolve().parent
DIST_DIR = WEB_DIR / "dist"
CHARTS_DIR = DIST_DIR / "charts"
ASSETS_DIR = CHARTS_DIR / "assets"


def main():
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    CHARTS_DIR.mkdir(parents=True)
    ASSETS_DIR.mkdir(parents=True)

    apply_theme()
    apply_plotly_theme()

    pages = []
    print("Generando gráficos de equipos...")
    pages += teams_charts.build(ASSETS_DIR)
    print("Generando gráficos de jugadores...")
    pages += players_charts.build(ASSETS_DIR)

    for page in pages:
        out = write_chart_page(page, CHARTS_DIR)
        print(f"  {page.slug} -> {out.relative_to(DIST_DIR)}")

    index_path = write_index(pages, DIST_DIR)
    print(f"Índice -> {index_path.relative_to(DIST_DIR)}")
    print(f"\n{len(pages)} páginas generadas en {DIST_DIR}")


if __name__ == "__main__":
    main()
