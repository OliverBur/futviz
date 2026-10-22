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

from site_utils import (  # noqa: E402
    COLOR_BG_CLARO, SECTION_META, write_article_page, write_chart_page, write_index, write_section_pages,
)
from section_views import write_section_views  # noqa: E402
from ml_reader import write_ml_reader  # noqa: E402
import react_views  # noqa: E402
from viz_theme import apply_theme, apply_plotly_theme  # noqa: E402
import teams as teams_charts  # noqa: E402
import players as players_charts  # noqa: E402
import ml_xg as ml_xg_articles  # noqa: E402

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

    bbox = _caja_contenido(diff, pad)
    if bbox:
        im = im.crop(bbox)
    return im


def _caja_contenido(diff, pad):
    """`(izq, arriba, der, abajo)` de lo que no es fondo (`diff` > 30) más `pad` de margen, o `None` si
    no hay nada. La comparten la versión clara y la oscura del logo para que midan exactamente lo mismo."""
    import numpy as np

    rows, cols = np.where(diff > 30)
    if not len(rows):
        return None
    alto, ancho = diff.shape
    return (max(int(cols.min()) - pad, 0), max(int(rows.min()) - pad, 0),
            min(int(cols.max()) + pad, ancho), min(int(rows.max()) + pad, alto))


# Colores del logo fuente. El slate ("Fut" y el arco) es lo único que se recolorea para el tema oscuro: sobre
# #12181A daba ~1.9:1. El destino es el MISMO slate aclarado, no el casi blanco de `--color-primary`: mismo matiz
# (~193°) y saturación (30 %), luminosidad de 25 % a 36 %, para que el logo siga siendo el azul-teal de la marca y
# quede lo más cerca posible del logo claro. Es una decisión de diseño que prioriza parecerse al original sobre el
# contraste: da 3.06:1 sobre #12181A y 2.70:1 sobre #1B2426, o sea por debajo del 3:1 que se pide a un gráfico
# sobre la superficie oscura (con #4F8392, 44 %, daba 4.26:1 y 3.76:1; con #6099A9, 52 %, 5.7:1 y 5.0:1).
# Los verdes se quedan como están (son ≥ 4.3:1 sobre los dos fondos oscuros).
LOGO_SLATE = (44, 76, 84)             # #2C4C54
LOGO_SLATE_OSCURO = (63, 107, 120)    # #3F6B78


def _trim_oscuro(im, pad=30):
    """La versión del logo para el tema oscuro: mismo recorte, formas y proporciones que `_trim_transparent`,
    con el slate cambiado por `LOGO_SLATE_OSCURO`.

    Recolorear los píxeles tal cual dejaría un halo: el alfa de `_trim_transparent` sale de la distancia al
    fondo, pero el RGB de los píxeles de borde sigue siendo una MEZCLA del primer plano con ese fondo claro
    (celeste grisáceo), y sobre un fondo oscuro se vería como un contorno claro. Por eso aquí se desmezcla:
    cada píxel se explica como mezcla de dos colores de {fondo, colores sólidos del logo} (la pareja que deja
    menos error; cubre tanto fondo-primer plano como slate-verde, donde se tocan las letras) y se reconstruye
    el color de primer plano y la cobertura real. Devuelve una imagen RGBA."""
    import numpy as np
    from PIL import Image

    rgb = np.asarray(im.convert("RGB")).astype(float)
    fondo = rgb[0, 0]
    diff = np.abs(rgb - fondo).sum(axis=2)
    caja = _caja_contenido(diff, pad)
    if caja:
        rgb = rgb[caja[1]:caja[3], caja[0]:caja[2]]
        diff = diff[caja[1]:caja[3], caja[0]:caja[2]]
    alto, ancho = rgb.shape[:2]
    pix = rgb.reshape(-1, 3)

    # Los colores sólidos de primer plano: los que cubren más del 1 % de lo que no es fondo (los del
    # borde suavizado son miles de tonos con unos cientos de píxeles cada uno).
    unicos, cuentas = np.unique(pix.astype(np.uint8), axis=0, return_counts=True)
    umbral = 0.01 * int((diff > 30).sum())
    solidos = [u.astype(float) for u, c in zip(unicos, cuentas)
               if c > umbral and np.abs(u - fondo).sum() > 30]
    destino = [np.array(LOGO_SLATE_OSCURO, float) if np.abs(c - LOGO_SLATE).sum() < 12 else c for c in solidos]
    print("  logo oscuro: " + ", ".join(
        f"#{int(c[0]):02X}{int(c[1]):02X}{int(c[2]):02X}->#{int(d[0]):02X}{int(d[1]):02X}{int(d[2]):02X}"
        for c, d in zip(solidos, destino)))

    colores = np.vstack([fondo] + solidos)       # K x 3; el 0 es el fondo
    k = len(colores)
    peso = np.zeros((len(pix), k))
    mejor = np.full(len(pix), np.inf)
    for i in range(k):
        for j in range(i + 1, k):
            d = colores[i] - colores[j]
            t = np.clip(((pix - colores[j]) @ d) / (d @ d), 0, 1)
            error = ((pix - (colores[j] + t[:, None] * d)) ** 2).sum(axis=1)
            gana = error < mejor
            peso[gana] = 0
            peso[gana, i] = t[gana]
            peso[gana, j] = 1 - t[gana]
            mejor[gana] = error[gana]

    alfa = 1 - peso[:, 0]                                    # cobertura del primer plano
    pre = peso[:, 1:] @ np.vstack(destino)                   # color premultiplicado por la cobertura
    color = pre / np.maximum(alfa, 1e-6)[:, None]
    rgba = np.dstack([np.clip(np.rint(color), 0, 255).reshape(alto, ancho, 3),
                      np.clip(np.rint(alfa * 255), 0, 255).reshape(alto, ancho, 1)]).astype("uint8")
    return Image.fromarray(rgba, mode="RGBA")


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

    SITE_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    im = _trim_transparent(Image.open(src))
    im.save(SITE_ASSETS_DIR / "logo.png")
    print(f"  logo -> {(SITE_ASSETS_DIR / 'logo.png').relative_to(DIST_DIR)}")
    # El mismo logo para el tema oscuro (se muestra con `html[data-theme="dark"]`, ver `site_utils.logo_img`).
    _trim_oscuro(Image.open(src)).save(SITE_ASSETS_DIR / "logo-dark.png")
    print(f"  logo oscuro -> {(SITE_ASSETS_DIR / 'logo-dark.png').relative_to(DIST_DIR)}")


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

    def cuadrado(im):
        # Centrar en lienzo cuadrado (el ícono es más ancho que alto) antes de
        # bajar la resolución, para que no quede estirado.
        side = max(im.width, im.height)
        canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        canvas.paste(im, ((side - im.width) // 2, (side - im.height) // 2), im)
        return canvas.resize((256, 256), Image.LANCZOS)

    cuadrado(_trim_transparent(Image.open(src), pad=16)).save(DIST_DIR / "favicon.png")
    print(f"  favicon -> {(DIST_DIR / 'favicon.png').relative_to(DIST_DIR)}")
    # Para pestañas oscuras: con el arco slate el ícono casi desaparece (ver `site_utils.FAVICON_LINKS`).
    cuadrado(_trim_oscuro(Image.open(src), pad=16)).save(DIST_DIR / "favicon-dark.png")
    print(f"  favicon oscuro -> {(DIST_DIR / 'favicon-dark.png').relative_to(DIST_DIR)}")


# Qué gráfico real representa a cada sección en su thumbnail de la
# landing — elegidos por el usuario, no cualquiera de los 9/5 de cada
# sección sirve igual de bien como preview. Es `(página, índice del
# gráfico dentro de esa página)`: las páginas de chart tienen uno solo,
# pero un análisis tiene varios y hay que decir cuál representa mejor.
PREVIEW_SOURCE_CHART = {
    # Es una página con vistas: el `#...` elige cuál se ve.
    "analisis-exploratorio": ("analisis-exploratorio.html#perfil-ofensivo", 0),  # "Perfil ofensivo: xG90 vs. xA90"
    "machine-learning": ("analisis/modelo-xg.html", 8),     # el mapa de valor del tiro (9.ª figura)
}


def _serve_dist():
    """Sirve `dist/` por http en un puerto libre y devuelve `(servidor, base_url)`.

    La captura va por http y no por `file://` para parecerse a como se ve el sitio
    publicado."""
    import functools
    import http.server
    import threading

    class _Callado(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    servidor = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0), functools.partial(_Callado, directory=str(DIST_DIR)))
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    return servidor, f"http://127.0.0.1:{servidor.server_address[1]}"


def _screenshot_chart_card(source, base_url, dark=False):
    """Captura una tarjeta `.chart-scroll` (el gráfico ya renderizado, sin
    el header/breadcrumb) de una página ya generada en `dist/`, con
    Playwright. `source` es `(ruta relativa a dist/, índice del gráfico)`.
    `dark=True` clickea el toggle real de la página antes de capturar
    (mismo flujo que un usuario, no duplica la lógica de
    PLOTLY_THEME_SCRIPT). Devuelve una imagen PIL o `None` si algo falla —
    un thumbnail roto es peor que caer al placeholder de texto."""
    import io

    rel_path, index = source
    if not (DIST_DIR / rel_path.split("#")[0]).exists():
        return None

    try:
        from playwright.sync_api import sync_playwright
        from PIL import Image

        with sync_playwright() as p:
            browser = p.chromium.launch()
            # 1360 y no 1100: la página del análisis exploratorio tiene un menú de 250 px a la izquierda y con
            # 1100 el gráfico del thumbnail salía más chico que el cuadro que lo muestra.
            page = browser.new_page(viewport={"width": 1360, "height": 900})
            page.goto(f"{base_url}/{rel_path}")
            page.wait_for_timeout(600)
            if dark:
                page.click("#theme-toggle")
                page.wait_for_timeout(400)
            locator = page.locator(".chart-scroll").nth(index)
            locator.wait_for(state="visible", timeout=5000)
            locator.scroll_into_view_if_needed()
            # Que el contenedor exista no significa que ya haya algo dibujado
            # dentro: los gráficos que están más abajo en un análisis largo
            # tardan varios segundos, y sin esperarlos el thumbnail sale en
            # blanco. Qué esperar depende del tipo de gráfico — los de React
            # pintan puntos (`.rx-chart svg circle`) o celdas, los de Plotly un
            # `.main-svg` y los de matplotlib son un `<img>` embebido.
            # `:visible` importa en los de matplotlib: llevan dos <img>, una por
            # tema, y la del tema inactivo está oculta por CSS — sin filtrar,
            # la espera se queda mirando la que nunca se va a mostrar.
            locator.locator(".main-svg, .rx-chart svg circle, .rx-chart svg rect[data-celda], img:visible").first.wait_for(
                state="visible", timeout=20000)
            # Las vistas de React entran con una animación (~1 s) y sus etiquetas aparecen al final.
            page.wait_for_timeout(1600 if locator.locator(".rx-chart").count() else 400)
            png_bytes = locator.screenshot()
            browser.close()
        return Image.open(io.BytesIO(png_bytes)).convert("RGB")
    except Exception as e:
        print(f"  (no se pudo capturar {rel_path} para preview: {e})")
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
    bg = tuple(int(COLOR_BG_CLARO[i:i + 2], 16) for i in (1, 3, 5))      # --color-bg
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
    labels = {"analisis-exploratorio": "Análisis exploratorio", "machine-learning": "Machine Learning"}
    servidor, base_url = _serve_dist()

    for slug, label in labels.items():
        dest_light = SITE_ASSETS_DIR / f"preview-{slug}.png"
        dest_dark = SITE_ASSETS_DIR / f"preview-{slug}-dark.png"
        src = IMG_DIR / f"preview-{slug}.png"
        source = PREVIEW_SOURCE_CHART[slug]

        if src.exists():
            shutil.copy(src, dest_light)
            shutil.copy(src, dest_dark)  # sin variante oscura manual todavía
            print(f"  preview {slug} -> {dest_light.relative_to(DIST_DIR)} (fuente real)")
            continue

        shot = _screenshot_chart_card(source, base_url)
        if shot is not None:
            _fit_preview_canvas(shot).save(dest_light)
            print(f"  preview {slug} -> {dest_light.relative_to(DIST_DIR)} (captura de {source[0]})")
        else:
            _placeholder_preview(label).save(dest_light)
            print(f"  preview {slug} -> {dest_light.relative_to(DIST_DIR)} (placeholder)")

        shot_dark = _screenshot_chart_card(source, base_url, dark=True)
        if shot_dark is not None:
            _fit_preview_canvas(shot_dark).save(dest_dark)
            print(f"  preview {slug} (oscuro) -> {dest_dark.relative_to(DIST_DIR)}")
        else:
            shutil.copy(dest_light, dest_dark)

    servidor.shutdown()


def main():
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    CHARTS_DIR.mkdir(parents=True)
    ASSETS_DIR.mkdir(parents=True)

    # Todas las vistas del análisis exploratorio son de React: cargan un bundle que compila
    # Vite aparte (`npm run build` en web/react); acá solo se copia a dist/.
    react_views.exigir_bundle()
    print(f"  react -> {react_views.copiar_bundle(DIST_DIR).relative_to(DIST_DIR)}")

    build_logo()
    build_favicon()

    apply_theme()
    apply_plotly_theme()

    pages = []
    print("Generando gráficos de equipos...")
    pages += teams_charts.build(ASSETS_DIR)
    print("Generando gráficos de jugadores...")
    pages += players_charts.build(ASSETS_DIR)
    # Las tablas de datos que comparten las vistas (una por entidad) las registraron los `build()`.
    for ruta in react_views.escribir_datos(DIST_DIR):
        print(f"  datos -> {ruta.relative_to(DIST_DIR)} ({ruta.stat().st_size / 1024:.0f} KB)")

    # Equipos y Jugadores comparten UNA página con vistas (cascarón + un
    # fragmento por gráfico); cualquier otra sección con páginas de chart sueltas
    # seguiría el camino de siempre.
    hubs = {}
    for page in pages:
        hub = SECTION_META[page.section].get("hub")
        if hub:
            hubs.setdefault(hub, {}).setdefault(page.section, []).append(page)
        else:
            out = write_chart_page(page, CHARTS_DIR)
            print(f"  {page.slug} -> {out.relative_to(DIST_DIR)}")
    for hub, entidades in hubs.items():
        outs = write_section_views(hub, entidades, DIST_DIR)
        print(f"  {hub}: {sum(len(v) for v in entidades.values())} vistas -> {outs[0].relative_to(DIST_DIR)}")

    # Los análisis son otro tipo de página (prosa + gráficos, no un gráfico
    # suelto), pero entran a la misma lista: `write_section_pages` y
    # `write_index` solo miran `.section` y arman el href con `.href_prefix`.
    print("Generando análisis de machine learning...")
    # `ml_xg` entrena el modelo de xG al construirse (221.922 tiros, con
    # early stopping), así que es de los pasos más lentos del build.
    articles = ml_xg_articles.build(ASSETS_DIR)
    for page in articles:
        out = write_article_page(page, DIST_DIR)
        print(f"  {page.slug} -> {out.relative_to(DIST_DIR)}")
    pages += articles
    # La sección de ML es un lector: un artículo abierto y el carrusel de los demás a la izquierda.
    outs = write_ml_reader("Machine Learning", articles, DIST_DIR)
    print(f"  Machine Learning: {len(articles)} artículos -> {outs[0].relative_to(DIST_DIR)}")
    # Los análisis registran sus propias tablas para React (`datos-xg.js`): se escriben ahora.
    for ruta in react_views.escribir_datos(DIST_DIR):
        print(f"  datos -> {ruta.relative_to(DIST_DIR)} ({ruta.stat().st_size / 1024:.0f} KB)")

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
