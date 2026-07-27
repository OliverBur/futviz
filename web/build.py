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

from site_utils import write_chart_page, write_index, write_section_pages  # noqa: E402
from viz_theme import apply_theme, apply_plotly_theme  # noqa: E402
import teams as teams_charts  # noqa: E402
import players as players_charts  # noqa: E402

WEB_DIR = Path(__file__).resolve().parent
REPO_ROOT = WEB_DIR.parent
IMG_DIR = REPO_ROOT / "img"
DIST_DIR = WEB_DIR / "dist"
CHARTS_DIR = DIST_DIR / "charts"
ASSETS_DIR = CHARTS_DIR / "assets"
SITE_ASSETS_DIR = DIST_DIR / "assets"


def build_logo():
    """Recorta el margen y hace transparente el fondo plano del logo fuente
    (`img/futviz.png`, no versionado) y lo copia a `dist/assets/logo.png`
    para usarlo en la landing y el header de cada subpágina. Así el logo se
    ve bien sin importar el color de fondo del sitio, sin tener que matchear
    ningún color a mano. Si no existe el archivo fuente (ej. clon nuevo sin
    el logo todavía), no rompe el build."""
    src = IMG_DIR / "futviz.png"
    if not src.exists():
        print("  (sin img/futviz.png — se omite el logo)")
        return

    import numpy as np
    from PIL import Image

    im = Image.open(src).convert("RGB")
    arr = np.asarray(im).astype(int)
    # El color de fondo puede cambiar entre versiones del logo (blanco,
    # celeste, etc.) y no es perfectamente uniforme (leve ruido/gradiente),
    # así que se compara contra el pixel de la esquina con tolerancia en
    # vez de pedir una diferencia exacta de cero.
    bg_color = arr[0, 0]
    diff = np.abs(arr - bg_color).sum(axis=2)

    # Alfa suave: 0 en el fondo, sube a 255 a medida que un pixel se aleja
    # del color de fondo — evita un borde 100% duro/con dientes de sierra
    # alrededor del texto e ícono.
    alpha = np.clip((diff - 20) * 3, 0, 255).astype("uint8")
    rgba = np.dstack([np.asarray(im), alpha])
    im = Image.fromarray(rgba, mode="RGBA")

    mask = diff > 30
    rows, cols = np.where(mask)
    if len(rows):
        pad = 30
        bbox = (max(int(cols.min()) - pad, 0), max(int(rows.min()) - pad, 0),
                 min(int(cols.max()) + pad, im.width), min(int(rows.max()) + pad, im.height))
        im = im.crop(bbox)

    SITE_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    im.save(SITE_ASSETS_DIR / "logo.png")
    print(f"  logo -> {(SITE_ASSETS_DIR / 'logo.png').relative_to(DIST_DIR)}")


def main():
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    CHARTS_DIR.mkdir(parents=True)
    ASSETS_DIR.mkdir(parents=True)

    build_logo()

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

    for out in write_section_pages(pages, DIST_DIR):
        print(f"  sección -> {out.relative_to(DIST_DIR)}")

    index_path = write_index(pages, DIST_DIR)
    print(f"Índice -> {index_path.relative_to(DIST_DIR)}")
    print(f"\n{len(pages)} páginas generadas en {DIST_DIR}")


if __name__ == "__main__":
    main()
