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
    BRAND_ROOT_CSS, FONT_LINKS, PLOTLY_THEME_SCRIPT, SECTION_META, THEME_INIT_SCRIPT,
    THEME_TOGGLE_HTML,
)

VIEWS_PAGE_TEMPLATE = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__NAME__ · FutViz</title>
<link rel="icon" type="image/png" href="favicon.png">
__THEME_INIT__
__FONT_LINKS__
<script src="react/futviz-react.js" defer></script>
<link rel="preload" as="script" href="__PRELOAD__">
<style>
__BRAND_ROOT__
  header { display: flex; align-items: center; justify-content: space-between; gap: 12px;
    padding: 14px 32px; border-bottom: 1px solid var(--color-border); }
  .crumb { color: var(--color-muted); text-decoration: none; font-size: 13px; font-weight: 500; }
  .crumb:hover { color: var(--color-interactive); }
  .header-right { display: flex; align-items: center; gap: 14px; }
  .site-logo-link { flex: none; line-height: 0; }
  .site-logo { height: 30px; width: auto; display: block; }
  main { padding: 26px 32px 60px; max-width: 1400px; margin: 0 auto; }
  h1 { position: relative; font-size: 26px; font-weight: 700; letter-spacing: -0.01em;
    color: var(--color-primary); margin: 0 0 6px; padding-left: 14px; }
  h1::before { content: ""; position: absolute; left: 0; top: 4px; bottom: 4px; width: 4px;
    border-radius: 2px; background: var(--color-brand-accent); }
  .lead { color: var(--color-muted); font-size: 14px; line-height: 1.5; max-width: 760px; margin: 0 0 22px 14px; }

  /* Control segmentado. Los grupos tienen rótulo propio porque son familias de
     preguntas distintas (qué tan bien define, cómo defiende...) y ocho pestañas
     seguidas, sin agrupar, se leen como una lista de nombres sin orden. */
  /* flex-end: un grupo sin rótulo (Crea tu gráfico) no tiene el texto de arriba que
     tienen los demás; alineado al borde inferior su botón queda a la altura de los
     botones vecinos en vez de subir hasta la altura de los rótulos. */
  .seg-nav { display: flex; flex-wrap: wrap; align-items: flex-end; gap: 14px 26px; margin-bottom: 14px; }
  .seg-group { min-width: 0; max-width: 100%; }
  /* Fila de arriba: qué se analiza (jugadores o equipos). Más grande que la de las
     vistas para que se lea como el primer nivel de navegación. */
  .ent-nav { margin: 0 0 18px; }
  .ent-nav .seg { padding: 4px; border-radius: 13px; }
  .ent-nav .seg button { font-size: 14.5px; padding: 9px 22px; border-radius: 10px; }
  .seg-nav[hidden] { display: none; }
  .seg-label { font-size: 10.5px; font-weight: 700; text-transform: uppercase; letter-spacing: .07em;
    color: var(--color-muted); margin: 0 0 6px 4px; }
  .seg { display: inline-flex; gap: 2px; padding: 3px; border-radius: 11px; background: var(--color-surface);
    border: 1px solid var(--color-border); max-width: 100%; overflow-x: auto; scrollbar-width: none; }
  .seg::-webkit-scrollbar { display: none; }
  .seg button { font: 600 13px "Inter", system-ui, sans-serif; white-space: nowrap; cursor: pointer;
    padding: 8px 14px; border: 0; border-radius: 8px; background: transparent; color: var(--color-muted);
    transition: background-color .16s ease, color .16s ease, transform .1s ease; }
  .seg button:hover { color: var(--color-primary); background: var(--color-interactive-soft); }
  .seg button:active { transform: scale(.97); }
  .seg button[aria-selected="true"] { background: var(--color-primary); color: var(--color-bg); }
  .seg button:focus-visible { outline: 2px solid var(--color-interactive); outline-offset: 1px; }

  .view-desc { color: var(--color-text-body); font-size: 14px; line-height: 1.5; margin: 0 0 14px 4px; min-height: 21px; }
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
  @media (prefers-reduced-motion: reduce) { .view { animation: none; } .view-loading i { animation-duration: 2s; } }
  @media (max-width: 640px) {
    header { padding: 12px 16px; }
    main { padding: 20px 16px 40px; }
    .chart-scroll { padding: 12px; }
    .site-logo { height: 24px; }
    .lead { margin-left: 0; }
    .seg-nav { gap: 12px; }
  }
</style>
</head>
<body>
<header>
  <a class="crumb" href="index.html">&larr; Inicio</a>
  <div class="header-right">
    <a class="site-logo-link" href="index.html">
      <img class="site-logo" src="assets/logo.png" alt="FutViz — volver al inicio">
    </a>
    __THEME_TOGGLE__
  </div>
</header>
<main>
  <h1>__NAME__</h1>
  <p class="lead">__DESCRIPTION__</p>
  <div class="ent-nav"><div class="seg" role="tablist" aria-label="Qué analizar">__ENTIDADES__</div></div>
  __TABS__
  <p class="view-desc" id="view-desc" aria-live="polite"></p>
  <div class="chart-scroll">__PANELS__</div>
</main>
<script>
(function() {
  var VIEWS = __VIEWS_JSON__;
  var DEFECTO = VIEWS[0].slug;
  var tabs = Array.prototype.slice.call(document.querySelectorAll('.seg-nav [role="tab"]'));
  var entTabs = Array.prototype.slice.call(document.querySelectorAll('.ent-nav [role="tab"]'));
  var navs = Array.prototype.slice.call(document.querySelectorAll('.seg-nav'));
  var ultima = {};  // entidad -> última vista que se miró, para volver a ella
  var desc = document.getElementById('view-desc');
  var cargas = {};   // slug -> Promise del montaje (ya hecho o en curso)
  var pedidos = {};  // slug -> Promise del texto del fragmento (también lo usa el prefetch)
  var actual = null;

  function vista(slug) { return VIEWS.filter(function(v) { return v.slug === slug; })[0]; }
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

  function activar(slug, enfocar) {
    if (!vista(slug)) slug = DEFECTO;
    if (slug === actual) return;
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
      if (on && enfocar) t.focus();
    });
    desc.textContent = vista(slug).subtitle;
    document.title = vista(slug).tab + ' · ' + ent + ' · FutViz';
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
      var salto = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : e.key === 'Home' ? -99 : e.key === 'End' ? 99 : 0;
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
  window.addEventListener('hashchange', function() { activar(location.hash.slice(1)); });
  activar(location.hash.slice(1) || DEFECTO);
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
