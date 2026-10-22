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
    SECTION_META, write_article_page, write_chart_page, write_section_pages,
)
from section_views import write_section_views  # noqa: E402
from ml_reader import write_ml_reader  # noqa: E402
import landing  # noqa: E402
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
    # suelto), pero entran a la misma lista: `write_section_pages` y la
    # landing solo miran `.section` y arman el href con `.href_prefix`.
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

    for out in write_section_pages(pages, DIST_DIR):
        print(f"  sección -> {out.relative_to(DIST_DIR)}")

    # La landing va al final: su índice de búsqueda y su mapa de calor salen de las tablas y vistas que
    # registraron los pasos anteriores (ver landing.py). El buscador es un .js estático que solo se copia.
    shutil.copy(WEB_DIR / "static" / "buscador.js", SITE_ASSETS_DIR / "buscador.js")
    r = landing.escribir_landing(pages, DIST_DIR)
    print(f"Landing -> {r['index'].relative_to(DIST_DIR)} · og:image -> {r['og'].relative_to(DIST_DIR)}")
    print(f"  buscador -> {r['indice'].relative_to(DIST_DIR)}: {r['jugadores']} jugadores (de "
          f"{r['jugadores_tabla']} en las tablas), {r['equipos']} equipos, {r['vistas']} gráficas, "
          f"{r['lecturas']} lecturas · {r['kb']:.0f} KB, {r['kb_gz']:.1f} KB gzip")
    print(f"\n{len(pages)} páginas generadas en {DIST_DIR}")


if __name__ == "__main__":
    main()
