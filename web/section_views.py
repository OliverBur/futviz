"""Páginas de sección con vistas: Equipos y Jugadores.

Antes cada sección era una página de cards que llevaba a una página por gráfico.
Ahora la sección ES el gráfico: una sola página (`dist/{seccion}.html`) con un
control segmentado arriba para cambiar de vista, sin salir de ella.

**Una sola página para Equipos y Jugadores** (`analisis-exploratorio.html`): una fila de arriba
elige la entidad y la de abajo, sus vistas.

**Cómo se carga.** Cada vista pesa ~2 MB (los datos de las 6 temporadas van
dentro del HTML del gráfico), así que meter las ocho en la misma página la
llevaría a ~15 MB. En su lugar la página es un cascarón liviano y cada vista
vive aparte, como un fragmento en `dist/vistas/{seccion}/{slug}.js`, que
el cascarón carga la primera vez que se activa su pestaña y deja montado: al
volver a una vista se conservan sus filtros tal como se dejaron.

Los fragmentos son archivos `.js` que llaman a `window.futvizVista(slug, html)`
y se cargan con un `<script src>`, no con `fetch`: así la página funciona igual
abierta con doble clic (`file://`, donde Chrome bloquea el `fetch`) que servida.

**Todas las vistas son de React** (`web/react_views.py`). Cada fragmento es un contenedor mínimo y su
configuración; el cascarón carga el bundle (`react/futviz-react.js`) una sola vez y, cada vez que
inserta un fragmento, le pide que monte lo que encuentre (`window.futvizReact.montar()`). Los datos
viven en tablas compartidas por entidad que el bundle pide la primera vez que las necesita. Ya no se
carga Plotly aquí.
"""

import json
from pathlib import Path

from site_utils import (
    BRAND_ROOT_CSS, FONT_LINKS, THEME_COLOR_META, favicon_links, PAGE_HEADER_CSS, page_header_html, PLOTLY_THEME_SCRIPT, SECTION_META,
    THEME_INIT_SCRIPT, THEME_TOGGLE_HTML,
)

VIEWS_PAGE_TEMPLATE = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__NAME__ · FutViz</title>
<meta name="description" content="__DESCRIPTION__">
__THEME_COLOR__
__FAVICON__
__THEME_INIT__
__FONT_LINKS__
<script src="react/futviz-react.js" defer></script>
<link rel="preload" as="script" href="__PRELOAD__">
<style>
__BRAND_ROOT__
__PAGE_HEADER_CSS__

  /* Dos columnas: el menú a la izquierda (fijo al hacer scroll) y la gráfica con todo el ancho que
     queda. Antes el menú iba arriba y se comía ~330 px antes de ver la primera gráfica. */
  /* Sin scroll anchoring en la página: al cargar la vista nueva, el navegador "ancla" el scroll a algún
     nodo y la manda al fondo (el menú es fijo, así que casi siempre se cambia de vista con la página
     scrolleada). Hay que ponerlo en `html`: en un hijo no basta. */
  html { overflow-anchor: none; }
  .shell { display: grid; grid-template-columns: minmax(0, 1fr); max-width: 1880px; margin: 0 auto;
    padding: 0 16px 64px; }
  .content { min-width: 0; padding-top: 16px; }
  .content:focus { outline: none; }   /* destino del salto: se enfoca por código, no con el teclado */
  .rail { min-width: 0; padding: 18px 0 4px; }

  /* Entidad (jugadores o equipos): primer nivel de navegación. */
  .ent-nav { margin: 0 0 20px; }
  .ent-nav .seg { display: grid; grid-template-columns: 1fr 1fr; gap: 2px; padding: 3px; border-radius: 11px;
    background: var(--color-surface); border: 1px solid var(--color-border); }
  .ent-nav .seg button { font: 600 13.5px "Inter", system-ui, sans-serif; cursor: pointer; padding: 9px 12px;
    border: 0; border-radius: 8px; background: transparent; color: var(--color-muted); touch-action: manipulation;
    transition: background-color .15s ease, color .15s ease, box-shadow .15s ease; }
  .ent-nav .seg button[aria-selected="true"] { background: var(--color-bg); color: var(--color-primary);
    box-shadow: 0 0 0 1px var(--color-border); }

  /* Vistas: filas de texto agrupadas por familia de preguntas (qué tan bien define, cómo defiende...),
     sin colores de marca. La seleccionada: fondo neutro y una barra del color del texto. */
  .seg-nav { display: flex; flex-direction: column; gap: 18px; }
  .seg-nav[hidden] { display: none; }
  .seg-group { min-width: 0; }
  .seg-label { font-size: 11px; font-weight: 600; color: var(--color-muted); margin: 0 0 6px 12px; }
  .seg-group .seg { display: flex; flex-direction: column; gap: 2px; }
  .seg-group .seg button { font: 500 13.5px/1.35 "Inter", system-ui, sans-serif; text-align: left; width: 100%;
    cursor: pointer; padding: 8px 12px; border: 0; border-radius: 8px; background: transparent;
    color: var(--color-text-body); touch-action: manipulation;
    transition: background-color .15s ease, box-shadow .15s ease, color .15s ease; }
  .seg-group .seg button[aria-selected="true"] { background: var(--color-surface); color: var(--color-primary);
    font-weight: 600; box-shadow: inset 2px 0 0 var(--color-primary); }
  .seg button:focus-visible { outline: 2px solid var(--color-interactive); outline-offset: -2px; }
  @media (hover: hover) {
    .ent-nav .seg button:hover:not([aria-selected="true"]) { color: var(--color-primary); }
    .seg-group .seg button:hover:not([aria-selected="true"]) { background: var(--color-surface); color: var(--color-primary); }
  }

  .view-desc { color: var(--color-text-body); font-size: 14px; line-height: 1.5; margin: 0 0 14px 2px; min-height: 21px; }
  .chart-scroll { max-width: 100%; overflow-x: auto; background: var(--color-bg);
    border: 1px solid var(--color-border); border-radius: 14px; padding: 20px; }
  .view { animation: view-in .24s ease-out; }
  .view[hidden] { display: none; }
  @keyframes view-in { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }
  .view-loading { min-height: 460px; display: flex; flex-direction: column; align-items: center;
    justify-content: center; gap: 14px; color: var(--color-muted); font-size: 13.5px; }
  .view-loading i { width: 30px; height: 30px; border-radius: 50%; border: 3px solid var(--color-border);
    border-top-color: var(--color-interactive); animation: spin .8s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }
  .view-error button { font: 600 13px "Inter", system-ui, sans-serif; padding: 8px 16px; border-radius: 8px; cursor: pointer;
    border: 1px solid var(--color-interactive); background: var(--color-surface); color: var(--color-primary); }

  @media (min-width: 640px) { .shell { padding: 0 24px 72px; } }

  /* Hasta 960 px el menú queda arriba y cada familia es una tira de chips que se desliza. */
  @media (max-width: 959px) {
    .seg-group .seg { flex-direction: row; gap: 6px; overflow-x: auto; scrollbar-width: none; overscroll-behavior-x: contain;
      padding-bottom: 2px; }
    .seg-group .seg::-webkit-scrollbar { display: none; }
    .seg-group .seg button { width: auto; flex: none; white-space: nowrap; padding: 9px 14px;
      border: 1px solid var(--color-border); background: var(--color-surface); }
    .seg-group .seg button[aria-selected="true"] { border-color: var(--color-primary); box-shadow: none; }
    .seg-label { margin-left: 2px; margin-bottom: 5px; }
    .seg-nav { gap: 10px; }
    .ent-nav { margin-bottom: 14px; }
    .seg-group .seg button { padding: 7px 12px; }
    .rail { padding-bottom: 8px; }
  }
  @media (min-width: 960px) {
    .shell { grid-template-columns: 250px minmax(0, 1fr); gap: 0 32px; align-items: start; }
    .rail { position: sticky; top: 0; max-height: 100vh; max-height: 100dvh; overflow-y: auto; overscroll-behavior: contain;
      padding: 24px 0; scrollbar-width: thin; scrollbar-color: var(--color-border) transparent; }
    .content { padding-top: 24px; }
  }
  @media (max-width: 640px) { .chart-scroll { padding: 12px; } }
  @media (prefers-reduced-motion: reduce) {
    .view { animation: none; } .view-loading i { animation-duration: 2s; }
    .ent-nav .seg button, .seg-group .seg button { transition: none; }
  }
</style>
</head>
<body>
<a class="skip" href="#contenido" id="skip">Saltar a la gráfica</a>
__PAGE_HEADER__
<div class="shell">
  <nav class="rail" aria-label="Vistas de __NAME__" id="rail">
    <div class="ent-nav"><div class="seg" role="tablist" aria-label="Qué analizar">__ENTIDADES__</div></div>
    __TABS__
  </nav>
  <main class="content" id="contenido" tabindex="-1">
    <p class="view-desc" id="view-desc" aria-live="polite"></p>
    <div class="chart-scroll">__PANELS__</div>
  </main>
</div>
<script>
(function() {
  var VIEWS = __VIEWS_JSON__;
  var DEFECTO = VIEWS[0].slug;
  var tabs = Array.prototype.slice.call(document.querySelectorAll('.seg-nav [role="tab"]'));
  var entTabs = Array.prototype.slice.call(document.querySelectorAll('.ent-nav [role="tab"]'));
  var navs = Array.prototype.slice.call(document.querySelectorAll('.seg-nav'));
  var ultima = {};  // entidad -> última vista que se miró, para volver a ella
  var desc = document.getElementById('view-desc');
  var contenido = document.getElementById('contenido');
  var cargas = {};   // slug -> Promise del montaje (ya hecho o en curso)
  var pedidos = {};  // slug -> Promise del texto del fragmento (también lo usa el prefetch)
  var actual = null;

  function vista(slug) { return VIEWS.filter(function(v) { return v.slug === slug; })[0]; }
  // El hash es `#vista` o `#vista?filtro=valor&...`: lo que va tras el `?` son los filtros de esa vista, que
  // ella misma lee y mantiene (react/src/urlEstado.js). Aquí solo importa de qué vista se trata.
  function slugDe(hash) { return decodeURIComponent(hash.split('?')[0]); }
  function panel(slug) { return document.getElementById('v-' + slug); }

  // Cada fragmento es un .js que se anuncia con futvizVista(slug, html). Se usa
  // <script src> y no fetch para que funcione también desde file://.
  var esperando = {};
  window.futvizVista = function(slug, html) {
    if (esperando[slug]) esperando[slug](html);
  };
  function pedir(slug) {
    if (!pedidos[slug]) {
      pedidos[slug] = new Promise(function(resolve, reject) {
        esperando[slug] = resolve;
        var tag = document.createElement('script');
        tag.src = vista(slug).src;
        tag.onerror = function() { tag.remove(); reject(new Error('carga')); };
        document.head.appendChild(tag);
      });
      pedidos[slug].catch(function() { delete pedidos[slug]; delete esperando[slug]; });  // permite reintentar
    }
    return pedidos[slug];
  }

  // Los <script> que entran por innerHTML no se ejecutan: se sacan y se vuelven
  // a crear, en orden, una vez que el resto del DOM ya está puesto. (Los de las vistas son
  // inline: dejan su configuración en window.futvizVistas.)
  function ejecutar(host, scripts) {
    scripts.forEach(function(viejo) {
      var s = document.createElement('script');
      if (viejo.src) s.src = viejo.src;
      else s.text = viejo.textContent;
      host.appendChild(s);
    });
  }

  function montar(slug) {
    if (cargas[slug]) return cargas[slug];
    var host = panel(slug);
    host.innerHTML = '<div class="view-loading"><i></i><span>Cargando la vista…</span></div>';
    cargas[slug] = pedir(slug).then(function(html) {
      var t = document.createElement('template');
      t.innerHTML = html;
      var scripts = Array.prototype.slice.call(t.content.querySelectorAll('script'));
      scripts.forEach(function(s) { s.remove(); });
      host.innerHTML = '';
      host.appendChild(t.content);
      ejecutar(host, scripts);
      // El bundle se carga con `defer`: si todavía no llegó, monta lo pendiente al arrancar él mismo.
      if (window.futvizReact) window.futvizReact.montar();
    }).catch(function() {
      delete cargas[slug];
      host.innerHTML = '<div class="view-loading view-error"><span>No se pudo cargar esta vista.</span>' +
        '<button type="button">Reintentar</button></div>';
      host.querySelector('button').addEventListener('click', function() { montar(slug); });
    });
    return cargas[slug];
  }

  // El menú es fijo: al cambiar de vista desde abajo, la nueva se ve desde su inicio.
  function irArriba() {
    var tope = document.querySelector('.shell').getBoundingClientRect().top + window.scrollY;
    if (window.scrollY > tope) window.scrollTo({top: Math.max(0, tope), behavior: 'auto'});
  }

  // Avisa a las vistas de cuál quedó activa: la que sea repone sus filtros en el hash (cambiar de pestaña
  // lo deja en `#vista` a secas, aunque la vista conserve sus filtros porque sigue montada).
  function avisar(slug) {
    document.dispatchEvent(new CustomEvent('futviz-vista-activa', {detail: {slug: slug}}));
  }

  function activar(slug) {
    if (!vista(slug)) slug = DEFECTO;
    if (slug === actual) { avisar(slug); return; }
    var primera = actual === null;
    actual = slug;
    VIEWS.forEach(function(v) { panel(v.slug).hidden = v.slug !== slug; });
    var ent = vista(slug).entity;
    ultima[ent] = slug;
    navs.forEach(function(n) { n.hidden = n.dataset.entity !== ent; });
    entTabs.forEach(function(t) {
      var on = t.dataset.entity === ent;
      t.setAttribute('aria-selected', on ? 'true' : 'false');
      t.tabIndex = on ? 0 : -1;
    });
    tabs.forEach(function(t) {
      var on = t.dataset.slug === slug;
      t.setAttribute('aria-selected', on ? 'true' : 'false');
      t.tabIndex = on ? 0 : -1;
    });
    desc.textContent = vista(slug).subtitle;
    document.title = vista(slug).tab + ' · ' + ent + ' · FutViz';
    if (!primera) irArriba();
    avisar(slug);
    // Una vista de React se vuelve a medir sola (ResizeObserver) y sigue el tema por su cuenta
    // (observa data-theme), así que al volver a una pestaña ya montada no hay nada que rehacer.
    montar(slug);
  }

  tabs.forEach(function(t) {
    t.addEventListener('click', function() { location.hash = t.dataset.slug; });
    // Pedir el fragmento al apuntar con el mouse o al enfocar: cuando llega el clic ya
    // suele estar descargado.
    t.addEventListener('pointerenter', function() { pedir(t.dataset.slug).catch(function() {}); });
    t.addEventListener('focus', function() { pedir(t.dataset.slug).catch(function() {}); });
    t.addEventListener('keydown', function(e) {
      // La lista es vertical en escritorio y horizontal en móvil: las cuatro flechas valen.
      var salto = (e.key === 'ArrowRight' || e.key === 'ArrowDown') ? 1 : (e.key === 'ArrowLeft' || e.key === 'ArrowUp') ? -1
        : e.key === 'Home' ? -99 : e.key === 'End' ? 99 : 0;
      if (!salto) return;
      e.preventDefault();
      var mias = tabs.filter(function(x) { return x.closest('.seg-nav') === t.closest('.seg-nav'); });
      var i = mias.indexOf(t);
      var j = Math.max(0, Math.min(mias.length - 1, Math.abs(salto) === 99 ? (salto < 0 ? 0 : mias.length - 1) : i + salto));
      location.hash = mias[j].dataset.slug;
      mias[j].focus();
    });
  });
  entTabs.forEach(function(t) {
    t.addEventListener('click', function() {
      location.hash = ultima[t.dataset.entity] || VIEWS.filter(function(v) { return v.entity === t.dataset.entity; })[0].slug;
    });
    t.addEventListener('keydown', function(e) {
      var i = entTabs.indexOf(t), j = e.key === 'ArrowRight' ? i + 1 : e.key === 'ArrowLeft' ? i - 1 : -1;
      if (j < 0 || j >= entTabs.length) return;
      e.preventDefault();
      entTabs[j].click(); entTabs[j].focus();
    });
  });
  document.getElementById('skip').addEventListener('click', function(e) { e.preventDefault(); contenido.focus(); });


  window.addEventListener('hashchange', function() { activar(slugDe(location.hash.slice(1))); });
  activar(slugDe(location.hash.slice(1)) || DEFECTO);
})();
</script>
__THEME_SCRIPT__
</body>
</html>
"""


def _tabs_html(pages, entidad):
    """Las vistas de UNA entidad, un grupo por cada valor distinto de `group`, en
    el orden en que aparecen. Las demás entidades tienen su propia fila, oculta."""
    grupos = {}
    for p in pages:
        grupos.setdefault(p.group, []).append(p)
    partes = []
    for nombre, miembros in grupos.items():
        botones = "".join(
            f'<button type="button" role="tab" id="t-{p.slug}" data-slug="{p.slug}" '
            f'aria-controls="v-{p.slug}" aria-selected="false" tabindex="-1">{p.tab or p.title}</button>'
            for p in miembros)
        rotulo = f'<div class="seg-label">{nombre}</div>' if nombre else ""
        partes.append(f'<div class="seg-group" role="presentation">{rotulo}<div class="seg" role="presentation">{botones}</div></div>')
    return (f'<nav class="seg-nav" role="tablist" data-entity="{entidad}" '
            f'aria-label="Vistas de {entidad}" hidden>{"".join(partes)}</nav>')


def write_section_views(section, entities, dist_dir: Path):
    """Escribe `dist/{slug}.html` (el cascarón) y un fragmento por vista.

    `entities` es `{nombre: [ChartPage, ...]}`: cada entidad (Jugadores, Equipos)
    es un botón de la fila de arriba con sus propias vistas debajo. La primera
    vista de la primera entidad es la que abre la página; las demás se cargan al
    activarlas. Devuelve las rutas escritas."""
    meta = SECTION_META[section]
    salidas, vistas, tabs, paneles, botones_ent = [], [], [], [], []
    orden = meta.get("entidades") or list(entities)
    for entidad in (e for e in orden if e in entities):
        pages = entities[entidad]
        slug_ent = SECTION_META[entidad]["slug"]
        frag_dir = dist_dir / "vistas" / slug_ent
        frag_dir.mkdir(parents=True, exist_ok=True)
        for p in pages:
            html = p.body_html
            ruta = frag_dir / f"{p.slug}.js"
            # json.dumps escapa comillas y saltos de línea y, con ensure_ascii, no
            # depende de la codificación con que el navegador lea el .js.
            ruta.write_text(f"window.futvizVista({json.dumps(p.slug)},{json.dumps(html)});", encoding="utf-8")
            salidas.append(ruta)
            vistas.append({"slug": p.slug, "tab": p.tab or p.title, "subtitle": p.subtitle,
                           "entity": entidad, "src": f"vistas/{slug_ent}/{p.slug}.js"})
            paneles.append(f'<div class="view" id="v-{p.slug}" role="tabpanel" aria-labelledby="t-{p.slug}" hidden></div>')
        tabs.append(_tabs_html(pages, entidad))
        botones_ent.append(
            f'<button type="button" role="tab" data-entity="{entidad}" aria-selected="false" '
            f'tabindex="-1">{entidad}</button>')

    ids = json.dumps(vistas, ensure_ascii=False).replace("</", "<\\/")
    html = (VIEWS_PAGE_TEMPLATE
            .replace("__THEME_COLOR__", THEME_COLOR_META)
            .replace("__FAVICON__", favicon_links())
            .replace("__PAGE_HEADER_CSS__", PAGE_HEADER_CSS)
            .replace("__PAGE_HEADER__", page_header_html(section))
            .replace("__NAME__", section)
            .replace("__DESCRIPTION__", meta["description"])
            .replace("__PRELOAD__", vistas[0]["src"])
            .replace("__ENTIDADES__", "".join(botones_ent))
            .replace("__TABS__", "".join(tabs))
            .replace("__PANELS__", "".join(paneles))
            .replace("__VIEWS_JSON__", ids)
            .replace("__THEME_INIT__", THEME_INIT_SCRIPT)
            .replace("__FONT_LINKS__", FONT_LINKS)
            .replace("__BRAND_ROOT__", BRAND_ROOT_CSS)
            .replace("__THEME_TOGGLE__", THEME_TOGGLE_HTML)
            .replace("__THEME_SCRIPT__", PLOTLY_THEME_SCRIPT))
    out = dist_dir / f"{meta['slug']}.html"
    out.write_text(html, encoding="utf-8")
    return [out] + salidas
