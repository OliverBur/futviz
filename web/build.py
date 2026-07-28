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


def _trim_transparent(im, pad=30):
    """Recorta el margen y hace transparente el fondo plano de un logo
    fuente (blanco, celeste, gris, lo que sea — no es fijo entre versiones
    del logo, ni perfectamente uniforme, así que se compara contra el pixel
    de la esquina con tolerancia en vez de pedir diferencia exacta de cero).
    Devuelve una imagen RGBA recortada al contenido + `pad` de margen."""
    import numpy as np

    arr = np.asarray(im.convert("RGB")).astype(int)
    bg_color = arr[0, 0]
    diff = np.abs(arr - bg_color).sum(axis=2)

    # Alfa suave: 0 en el fondo, sube a 255 a medida que un pixel se aleja
    # del color de fondo — evita un borde 100% duro/con dientes de sierra.
    alpha = np.clip((diff - 20) * 3, 0, 255).astype("uint8")
    rgba = np.dstack([arr.astype("uint8"), alpha])
    from PIL import Image
    im = Image.fromarray(rgba, mode="RGBA")

    mask = diff > 30
    rows, cols = np.where(mask)
    if len(rows):
        bbox = (max(int(cols.min()) - pad, 0), max(int(rows.min()) - pad, 0),
                 min(int(cols.max()) + pad, im.width), min(int(rows.max()) + pad, im.height))
        im = im.crop(bbox)
    return im


def build_logo():
    """Recorta y hace transparente el logo fuente (`img/futviz.png`, no
    versionado) y lo copia a `dist/assets/logo.png` para usarlo en la
    landing y el header de cada subpágina. Así el logo se ve bien sin
    importar el color de fondo del sitio, sin tener que matchear ningún
    color a mano. Si no existe el archivo fuente (ej. clon nuevo sin el
    logo todavía), no rompe el build."""
    src = IMG_DIR / "futviz.png"
    if not src.exists():
        print("  (sin img/futviz.png — se omite el logo)")
        return

    from PIL import Image

    im = _trim_transparent(Image.open(src))
    SITE_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    im.save(SITE_ASSETS_DIR / "logo.png")
    print(f"  logo -> {(SITE_ASSETS_DIR / 'logo.png').relative_to(DIST_DIR)}")


def build_favicon():
    """Favicon a partir de `img/futviz-logo-only.png` (no versionado) —
    solo el ícono, sin el wordmark, recortado a fondo transparente y
    centrado en un lienzo cuadrado para que no se vea deformado en la
    pestaña del navegador. Si no existe el archivo fuente, no rompe el
    build (el sitio se queda sin favicon, no con uno roto)."""
    src = IMG_DIR / "futviz-logo-only.png"
    if not src.exists():
        print("  (sin img/futviz-logo-only.png — se omite el favicon)")
        return

    from PIL import Image

    im = _trim_transparent(Image.open(src), pad=16)

    # Centrar en lienzo cuadrado (el ícono es más ancho que alto) antes de
    # bajar la resolución, para que no quede estirado.
    side = max(im.width, im.height)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(im, ((side - im.width) // 2, (side - im.height) // 2), im)
    canvas = canvas.resize((256, 256), Image.LANCZOS)

    canvas.save(DIST_DIR / "favicon.png")
    print(f"  favicon -> {(DIST_DIR / 'favicon.png').relative_to(DIST_DIR)}")


# Qué gráfico real representa a cada sección en su thumbnail de la
# landing — elegidos por el usuario, no cualquiera de los 9/5 de cada
# sección sirve igual de bien como preview.
PREVIEW_SOURCE_CHART = {
    "equipos": "perfil-liga-overlay",   # "Dónde se separa cada liga"
    "jugadores": "perfil-ofensivo",     # "Perfil ofensivo: xG90 vs. xA90"
}


def _screenshot_chart_card(chart_slug, dark=False):
    """Captura la tarjeta `.chart-scroll` (el gráfico ya renderizado, sin
    el header/breadcrumb de la página) de `dist/charts/{chart_slug}.html`
    con Playwright. `dark=True` clickea el toggle real de la página antes
    de capturar (mismo flujo que un usuario, no duplica la lógica de
    PLOTLY_THEME_SCRIPT). Devuelve una imagen PIL o `None` si algo falla —
    un thumbnail roto es peor que caer al placeholder de texto."""
    import io

    path = CHARTS_DIR / f"{chart_slug}.html"
    if not path.exists():
        return None

    try:
        from playwright.sync_api import sync_playwright
        from PIL import Image

        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1100, "height": 800})
            page.goto(path.resolve().as_uri())
            page.wait_for_timeout(400)  # deja terminar de dibujar Plotly
            if dark:
                page.click("#theme-toggle")
                page.wait_for_timeout(300)
            locator = page.locator(".chart-scroll")
            locator.wait_for(state="visible", timeout=5000)
            png_bytes = locator.screenshot()
            browser.close()
        return Image.open(io.BytesIO(png_bytes)).convert("RGB")
    except Exception as e:
        print(f"  (no se pudo capturar {chart_slug} para preview: {e})")
        return None


def _fit_preview_canvas(im, target_width=960):
    """Solo reescala, sin recortar — `.hub-thumb` en el CSS ya tiene
    `aspect-ratio: 16/10; object-fit: cover`, así que el navegador hace el
    recorte final al mostrarlo. Recortar acá también duplicaría el
    recorte y, en gráficos con barra lateral (más anchos que 16:10),
    terminaba comiéndose el título del lado izquierdo."""
    from PIL import Image

    ratio = target_width / im.width
    return im.resize((target_width, round(im.height * ratio)), Image.LANCZOS)


def _placeholder_preview(label):
    """Placeholder de texto simple — para cuando no hay ni fuente manual
    en img/ ni se pudo capturar el gráfico real."""
    from PIL import Image, ImageDraw, ImageFont

    w, h = 960, 600
    bg = (239, 237, 247)      # --color-bg
    primary = (44, 76, 84)    # --color-primary
    accent = (57, 153, 6)     # --color-brand-accent
    img = Image.new("RGB", (w, h), bg)
    draw = ImageDraw.Draw(img)
    # Una franja de acento simple en la esquina (misma pareja de colores
    # del logo, no una cancha ni un balón), sin cruzar el texto centrado.
    draw.rectangle([0, 0, w, 10], fill=accent)
    draw.rectangle([0, 0, 10, h], fill=primary)
    try:
        font_big = ImageFont.truetype("segoeui.ttf", 46)
        font_small = ImageFont.truetype("segoeui.ttf", 24)
    except OSError:
        font_big = ImageFont.load_default(size=46)
        font_small = ImageFont.load_default(size=24)

    def centered(text, y, font, color):
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        draw.text(((w - tw) / 2, y), text, font=font, fill=color)

    centered(label, h / 2 - 46, font_big, primary)
    centered("vista previa próximamente", h / 2 + 18, font_small, (87, 112, 122))
    return img


def build_previews():
    """Thumbnail de preview (claro y oscuro) para cada card de la landing
    (`dist/assets/preview-{slug}.png` / `preview-{slug}-dark.png`). Orden
    de prioridad para el claro: 1) `img/preview-{slug}.png` a mano (no
    versionado, igual que el logo), 2) captura real de
    `PREVIEW_SOURCE_CHART[slug]` (requiere correr esto *después* de
    escribir las páginas de chart), 3) placeholder de texto. El oscuro
    sigue el mismo orden — todas las páginas de chart soportan el toggle
    (Plotly se recolorea en runtime, matplotlib tiene una segunda imagen
    pre-renderizada, ver viz_theme.dark_ink())."""
    SITE_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    labels = {"equipos": "Equipos", "jugadores": "Jugadores"}

    for slug, label in labels.items():
        dest_light = SITE_ASSETS_DIR / f"preview-{slug}.png"
        dest_dark = SITE_ASSETS_DIR / f"preview-{slug}-dark.png"
        src = IMG_DIR / f"preview-{slug}.png"
        chart_slug = PREVIEW_SOURCE_CHART[slug]

        if src.exists():
            shutil.copy(src, dest_light)
            shutil.copy(src, dest_dark)  # sin variante oscura manual todavía
            print(f"  preview {slug} -> {dest_light.relative_to(DIST_DIR)} (fuente real)")
            continue

        shot = _screenshot_chart_card(chart_slug)
        if shot is not None:
            _fit_preview_canvas(shot).save(dest_light)
            print(f"  preview {slug} -> {dest_light.relative_to(DIST_DIR)} (captura de {chart_slug})")
        else:
            _placeholder_preview(label).save(dest_light)
            print(f"  preview {slug} -> {dest_light.relative_to(DIST_DIR)} (placeholder)")

        shot_dark = _screenshot_chart_card(chart_slug, dark=True)
        if shot_dark is not None:
            _fit_preview_canvas(shot_dark).save(dest_dark)
            print(f"  preview {slug} (oscuro) -> {dest_dark.relative_to(DIST_DIR)}")
        else:
            shutil.copy(dest_light, dest_dark)


def main():
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    CHARTS_DIR.mkdir(parents=True)
    ASSETS_DIR.mkdir(parents=True)

    build_logo()
    build_favicon()

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

    # Después de escribir las páginas de chart: los previews de la landing
    # capturan una de esas páginas ya generadas (ver PREVIEW_SOURCE_CHART).
    build_previews()

    for out in write_section_pages(pages, DIST_DIR):
        print(f"  sección -> {out.relative_to(DIST_DIR)}")

    index_path = write_index(pages, DIST_DIR)
    print(f"Índice -> {index_path.relative_to(DIST_DIR)}")
    print(f"\n{len(pages)} páginas generadas en {DIST_DIR}")


if __name__ == "__main__":
    main()
