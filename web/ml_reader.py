"""Página de la sección Machine Learning: un lector, no una grilla de cards.

Antes la sección era una lista de cards que llevaba a una página por artículo. Ahora abre
directamente con un artículo y, a la izquierda, un carrusel de mini cards permite cambiar de
uno a otro sin salir de la página (en móvil el carrusel pasa a ser una tira horizontal arriba).

**Cómo se carga.** Igual que las vistas del análisis exploratorio (`section_views.py`): la página
es un cascarón liviano y cada artículo vive aparte, como un fragmento en
`dist/vistas/ml/{slug}.js` que llama a `window.futvizArticulo(slug, html)` y se pide con un
`<script src>` (no `fetch`) para que funcione también abierta desde `file://`. El primero se
precarga; los demás se piden al apuntar o enfocar su card y quedan montados al volver a ellos.

El artículo sigue existiendo como página suelta (`analisis/{slug}.html`, ver
`site_utils.write_article_page`): el cascarón y la página suelta comparten el CSS de lectura
(`ARTICLE_CSS`) y el HTML del cuerpo, así que un artículo nuevo entra al lector solo, sin tocar
este archivo. Los que todavía no existen se listan en `SECTION_META[...]["proximos"]`.
"""

import html
import json
import re
from pathlib import Path

from site_utils import (
    ARTICLE_CSS, BRAND_ROOT_CSS, FONT_LINKS, THEME_COLOR_META, favicon_links, PAGE_HEADER_CSS, PAGE_HEADER_HTML, PLOTLY_THEME_SCRIPT, SECTION_META,
    THEME_INIT_SCRIPT, THEME_TOGGLE_HTML, ArticlePage,
)

PALABRAS_POR_MINUTO = 200

# Reloj de arena para las cards de lo que viene: dice "todavía no" sin parecer un error.
ICONO_PROXIMO = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 3h12M6 21h12"/>'
    '<path d="M7 3v3a5 5 0 0 0 2 4l3 2-3 2a5 5 0 0 0-2 4v3M17 3v3a5 5 0 0 1-2 4l-3 2 3 2a5 5 0 0 1 2 4v3"/></svg>'
)
FLECHA = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" '
          'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{}</svg>')
FLECHA_DER = FLECHA.format('<path d="M5 12h14M13 6l6 6-6 6"/>')
CHEVRON_IZQ = FLECHA.format('<path d="m15 18-6-6 6-6"/>')
CHEVRON_DER = FLECHA.format('<path d="m9 18 6-6-6-6"/>')

READER_PAGE_TEMPLATE = """<!doctype html>
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

  /* Barra de progreso de lectura del artículo abierto (no de la página: el encabezado y el
     carrusel no cuentan). */
  #progress { position: fixed; top: 0; left: 0; height: 3px; width: 100%; z-index: 30;
    background: var(--color-brand-accent); transform: scaleX(0); transform-origin: left;
    transition: transform .1s linear; }

  .pane:focus { outline: none; }   /* destino del salto: se enfoca por código, no con el teclado */

  /* Pantalla ancha: lista de artículos | lectura | índice, casi de borde a borde. */
  .reader { display: grid; grid-template-columns: minmax(0, 1fr); max-width: 1880px; margin: 0 auto;
    padding: 0 16px 80px; }
  .pane { min-width: 0; }
  .pane article p, .pane article li, .pane .deck { text-wrap: pretty; }

  /* ---------- Lista de artículos ---------- */
  .rail { padding: 20px 0 8px; min-width: 0; }
  .rail-head { display: flex; align-items: center; justify-content: space-between; gap: 10px;
    margin: 0 0 10px 14px; }
  .rail-label { font-size: 11px; font-weight: 600; color: var(--color-muted); }
  .rail-label b { color: var(--color-primary); font-variant-numeric: tabular-nums; font-weight: 600; }
  .rail-arrows { display: flex; gap: 4px; }
  .rail-arrows button { width: 32px; height: 32px; display: inline-flex; align-items: center; justify-content: center;
    padding: 0; border-radius: 8px; border: 0; background: transparent; color: var(--color-muted);
    cursor: pointer; touch-action: manipulation; transition: background-color .15s ease, color .15s ease; }
  .rail-arrows button svg { width: 15px; height: 15px; }
  @media (hover: hover) {
    .rail-arrows button:hover:not(:disabled) { background: var(--color-surface); color: var(--color-primary); }
  }
  .rail-arrows button:disabled { opacity: .35; cursor: default; }
  .rail-arrows button:focus-visible { outline: 2px solid var(--color-interactive); outline-offset: 1px; }

  /* Sin portadas, sombras ni colores de marca: una fila de texto por artículo. La seleccionada
     se marca con fondo neutro y una barra del color del texto. */
  .minis { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 2px; }
  a.mini { display: block; text-decoration: none; color: inherit; padding: 12px 14px; border-radius: 10px;
    touch-action: manipulation; transition: background-color .15s ease, box-shadow .15s ease; }
  @media (hover: hover) { a.mini:hover { background: var(--color-surface); } }
  a.mini:focus-visible { outline: 2px solid var(--color-interactive); outline-offset: -2px; }
  a.mini[aria-current="page"] { background: var(--color-surface); box-shadow: inset 2px 0 0 var(--color-primary); }
  .mini-meta { display: flex; gap: 8px; font-size: 11px; font-weight: 500; color: var(--color-muted);
    font-variant-numeric: tabular-nums; margin-bottom: 5px; }
  .mini-title { display: block; font-size: 14px; font-weight: 600; line-height: 1.35; color: var(--color-primary); }
  .mini-sub { display: block; margin-top: 5px; font-size: 12.5px; line-height: 1.55; color: var(--color-muted); }
  a.mini--soon .mini-title { color: var(--color-muted); }

  /* Índice del artículo abierto: columna propia a la derecha, solo en pantalla ancha. */
  .toc { display: none; }
  .toc-label { font-size: 11px; font-weight: 600; color: var(--color-muted); margin: 0 0 10px 12px; }
  .toc ol { list-style: none; margin: 0; padding: 0; border-left: 1px solid var(--color-border); }
  .toc a { display: flex; gap: 10px; align-items: baseline; margin-left: -1px; padding: 6px 8px 6px 12px;
    border-left: 1px solid transparent; font-size: 12.5px; line-height: 1.4; color: var(--color-muted);
    text-decoration: none; touch-action: manipulation; transition: color .15s ease, border-color .15s ease; }
  @media (hover: hover) { .toc a:hover { color: var(--color-primary); } }
  .toc a:focus-visible { outline: 2px solid var(--color-interactive); outline-offset: -2px; }
  .toc a[aria-current="true"] { color: var(--color-primary); font-weight: 600; border-left-color: var(--color-primary); }
  .toc .n { flex: none; font-size: 10.5px; font-weight: 600; font-variant-numeric: tabular-nums; opacity: .7; }


  /* ---------- Panel de lectura ---------- */
  .view { animation: view-in .26s ease-out; }
  .view[hidden] { display: none; }
  @keyframes view-in { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }
  .hero { padding-top: 28px; }
  .hero h2.hero-title { font-size: 30px; line-height: 1.15; font-weight: 800; letter-spacing: -0.02em;
    color: var(--color-primary); margin: 0 0 16px; text-wrap: balance; }
  .soon-panel { max-width: 720px; margin: 0 auto; padding: 56px 0 24px; text-align: center; }
  .soon-art { width: 84px; height: 84px; margin: 0 auto 22px; border-radius: 22px; display: flex;
    align-items: center; justify-content: center; color: var(--color-muted);
    border: 1px dashed var(--color-muted); }
  .soon-art svg { width: 34px; height: 34px; }
  .soon-panel h2 { font-size: 28px; font-weight: 800; letter-spacing: -0.02em; color: var(--color-primary); margin: 0 0 10px; }
  .soon-panel p { color: var(--color-muted); font-size: 15.5px; line-height: 1.6; margin: 0 auto 24px; max-width: 46ch; }
  .btn { display: inline-flex; align-items: center; gap: 8px; font: 600 13.5px "Inter", system-ui, sans-serif;
    padding: 10px 16px; border-radius: 10px; text-decoration: none; color: var(--color-primary);
    background: var(--color-surface); border: 1px solid var(--color-border); touch-action: manipulation;
    transition: border-color .15s ease; }
  @media (hover: hover) { .btn:hover { border-color: var(--color-muted); } }
  .btn:focus-visible { outline: 2px solid var(--color-interactive); outline-offset: 2px; }
  .btn svg { width: 16px; height: 16px; }

  .view-loading { min-height: 460px; display: flex; flex-direction: column; align-items: center;
    justify-content: center; gap: 14px; color: var(--color-muted); font-size: 13.5px; }
  .view-loading i { width: 30px; height: 30px; border-radius: 50%; border: 3px solid var(--color-border);
    border-top-color: var(--color-interactive); animation: spin .8s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }
  .view-error button { font: 600 13px "Inter", system-ui, sans-serif; padding: 8px 16px; border-radius: 8px; cursor: pointer;
    border: 1px solid var(--color-interactive); background: var(--color-surface); color: var(--color-primary); }

  @media (min-width: 640px) {
    .reader { padding: 0 24px 80px; }
  }

  /* Hasta 960 px la lista es una tira horizontal con snap; la siguiente asoma para que se note
     que se desliza. */
  @media (max-width: 959px) {
    .minis { flex-direction: row; gap: 10px; overflow-x: auto; scroll-snap-type: x mandatory;
      scrollbar-width: none; overscroll-behavior-x: contain; padding: 0 0 10px; }
    .minis::-webkit-scrollbar { display: none; }
    .minis li { flex: 0 0 min(80%, 300px); scroll-snap-align: start; display: flex; }
    a.mini { width: 100%; background: var(--color-surface); border: 1px solid var(--color-border); }
    a.mini[aria-current="page"] { border-color: var(--color-primary); box-shadow: none; }
    .rail-head { margin-left: 2px; }
    .rail-arrows button { width: 40px; height: 40px; }
  }
  @media (min-width: 960px) {
    .reader { grid-template-columns: 260px minmax(0, 1fr); gap: 0 36px; align-items: start; }
    .rail { position: sticky; top: 0; max-height: 100vh; max-height: 100dvh; overflow-y: auto; overscroll-behavior: contain;
      padding: 24px 0; scrollbar-width: thin; scrollbar-color: var(--color-border) transparent; }
    .hero { padding-top: 24px; }
  }
  @media (min-width: 1360px) {
    .reader { grid-template-columns: 260px minmax(0, 1fr) 210px; }
    .toc:not([hidden]) { display: block; position: sticky; top: 0; max-height: 100vh; max-height: 100dvh;
      overflow-y: auto; overscroll-behavior: contain; padding: 28px 0; scrollbar-width: thin; scrollbar-color: var(--color-border) transparent; }
  }
  @media (max-width: 640px) {
    .reader { padding: 0 16px 56px; }
    .hero h2.hero-title { font-size: 25px; }
    .soon-panel { padding-top: 36px; }
  }

  @media (prefers-reduced-motion: reduce) {
    .view { animation: none; } .view-loading i { animation-duration: 2s; }
    a.mini, #progress, .toc a { transition: none; }
  }
__ARTICLE_CSS__
  .pane .wrap { max-width: 920px; }
  .pane .wrap-wide { max-width: 1240px; }
</style>
</head>
<body>
<a class="skip" href="#pane" id="skip">Saltar al artículo</a>
<div id="progress" role="presentation"></div>
<div class="sr-only" id="anuncio" role="status" aria-live="polite"></div>
__PAGE_HEADER__
<div class="reader">
  <nav class="rail" aria-label="Artículos de __NAME__" id="rail">
    <div class="rail-head">
      <span class="rail-label">Artículos · <b id="rail-pos">1</b>/__TOTAL__</span>
      <span class="rail-arrows">
        <button type="button" id="prev" aria-label="Artículo anterior">__CHEVRON_IZQ__</button>
        <button type="button" id="next" aria-label="Artículo siguiente">__CHEVRON_DER__</button>
      </span>
    </div>
    <ul class="minis" id="minis">__CARDS__</ul>
  </nav>
  <main class="pane" id="pane" tabindex="-1">__PANELS__</main>
  <aside class="toc" id="toc" aria-label="En este artículo" hidden>
    <div class="toc-label">En este artículo</div>
    <ol id="toc-list"></ol>
  </aside>
</div>
<script>
(function() {
  var ARTICULOS = __ARTICLES_JSON__;
  var DEFECTO = ARTICULOS[0].slug;
  var cards = Array.prototype.slice.call(document.querySelectorAll('a.mini'));
  var minis = document.getElementById('minis');
  var rail = document.getElementById('rail');
  var toc = document.getElementById('toc');
  var tocList = document.getElementById('toc-list');
  var pos = document.getElementById('rail-pos');
  var barra = document.getElementById('progress');
  var btnPrev = document.getElementById('prev');
  var btnNext = document.getElementById('next');
  var anuncio = document.getElementById('anuncio');
  var pane = document.getElementById('pane');
  var cargas = {};   // slug -> Promise del montaje (hecho o en curso)
  var pedidos = {};  // slug -> Promise del texto del fragmento (también lo usa el prefetch)
  var esperando = {};
  var actual = null;
  var secciones = [];  // h2 del artículo abierto, para el índice
  var sinMovimiento = window.matchMedia('(prefers-reduced-motion: reduce)');

  function articulo(slug) { return ARTICULOS.filter(function(a) { return a.slug === slug; })[0]; }
  function panel(slug) { return document.getElementById('v-' + slug); }
  function indice(slug) { return ARTICULOS.indexOf(articulo(slug)); }

  // Cada fragmento se anuncia con futvizArticulo(slug, html). <script src> y no fetch para que
  // funcione también desde file://.
  window.futvizArticulo = function(slug, html) { if (esperando[slug]) esperando[slug](html); };
  function pedir(slug) {
    if (!pedidos[slug]) {
      pedidos[slug] = new Promise(function(resolve, reject) {
        esperando[slug] = resolve;
        var tag = document.createElement('script');
        tag.src = articulo(slug).src;
        tag.onerror = function() { tag.remove(); reject(new Error('carga')); };
        document.head.appendChild(tag);
      });
      pedidos[slug].catch(function() { delete pedidos[slug]; delete esperando[slug]; });  // permite reintentar
    }
    return pedidos[slug];
  }

  // Los <script> que entran por innerHTML no se ejecutan: se sacan y se vuelven a crear, en
  // orden, con el DOM ya puesto. (Los de cada gráfico dejan su configuración en window.futvizVistas.)
  function ejecutar(host, scripts) {
    scripts.forEach(function(viejo) {
      var s = document.createElement('script');
      if (viejo.src) s.src = viejo.src; else s.text = viejo.textContent;
      host.appendChild(s);
    });
  }

  function montar(slug) {
    if (cargas[slug]) return cargas[slug];
    var host = panel(slug);
    if (!articulo(slug).src) return Promise.resolve();   // "próximamente": el panel ya viene escrito
    host.innerHTML = '<div class="view-loading"><i></i><span>Cargando el artículo…</span></div>';
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
      host.innerHTML = '<div class="view-loading view-error"><span>No se pudo cargar este artículo.</span>' +
        '<button type="button">Reintentar</button></div>';
      host.querySelector('button').addEventListener('click', function() { montar(slug).then(armarIndice); });
    });
    return cargas[slug];
  }

  /* ---- Carrusel ---- */
  function centrarCard(card) {
    // Horizontal (móvil): centra la card en la tira. Vertical (escritorio): solo la mantiene a la
    // vista dentro del carrusel. Se mueve el contenedor, no la página (scrollIntoView la movería).
    if (minis.scrollWidth > minis.clientWidth + 2) {
      minis.scrollTo({left: card.parentNode.offsetLeft - (minis.clientWidth - card.parentNode.offsetWidth) / 2,
                      behavior: sinMovimiento.matches ? 'auto' : 'smooth'});
    } else if (rail.scrollHeight > rail.clientHeight) {
      var r = card.getBoundingClientRect(), c = rail.getBoundingClientRect();
      if (r.top < c.top) rail.scrollTop += r.top - c.top - 12;
      else if (r.bottom > c.bottom) rail.scrollTop += r.bottom - c.bottom + 12;
    }
  }

  /* ---- Índice del artículo + progreso ---- */
  function armarIndice() {
    tocList.innerHTML = '';
    secciones = [];
    var host = actual && panel(actual);
    var hs = host ? Array.prototype.slice.call(host.querySelectorAll('article h2[id]')) : [];
    hs.forEach(function(h) {
      var paso = h.querySelector('.step');
      var titulo = h.textContent.replace(paso ? paso.textContent : '', '').trim();
      var li = document.createElement('li');
      var a = document.createElement('a');
      a.href = '#' + actual + '/' + h.id;   // enlazable: abre el artículo y baja a esa sección
      a.innerHTML = '<span class="n"></span><span class="t"></span>';
      a.querySelector('.n').textContent = paso ? paso.textContent : '';
      a.querySelector('.t').textContent = titulo;
      a.addEventListener('click', function(e) {
        if (e.button || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;   // abrir en otra pestaña: normal
        e.preventDefault();
        if (location.hash !== a.hash) history.pushState(null, '', a.hash);
        irASeccion(h.id);
      });
      li.appendChild(a);
      tocList.appendChild(li);
      secciones.push({h: h, a: a});
    });
    toc.hidden = !secciones.length;
    marcar();
  }

  var pendiente = false;
  function marcar() {
    pendiente = false;
    var host = actual && panel(actual);
    if (host && !host.hidden && articulo(actual).src) {
      var r = host.getBoundingClientRect();
      var total = r.height - window.innerHeight;
      var avance = total > 0 ? Math.min(1, Math.max(0, -r.top / total)) : 0;
      barra.style.transform = 'scaleX(' + avance.toFixed(3) + ')';
    } else {
      barra.style.transform = 'scaleX(0)';
    }
    var activa = null;
    secciones.forEach(function(s) { if (s.h.getBoundingClientRect().top <= 110) activa = s; });
    var alFinal = window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 4;
    if (alFinal && secciones.length) activa = secciones[secciones.length - 1];
    secciones.forEach(function(s) {
      var on = s === activa;
      if (on) s.a.setAttribute('aria-current', 'true'); else s.a.removeAttribute('aria-current');
    });
    if (activa && toc.scrollHeight > toc.clientHeight) {
      var r2 = activa.a.getBoundingClientRect(), c = toc.getBoundingClientRect();
      if (r2.top < c.top + 8 || r2.bottom > c.bottom - 8) toc.scrollTop += r2.top - c.top - c.height / 2;
    }
  }
  function pedirMarcar() { if (!pendiente) { pendiente = true; requestAnimationFrame(marcar); } }
  window.addEventListener('scroll', pedirMarcar, {passive: true});
  window.addEventListener('resize', pedirMarcar);

  /* ---- Navegación ---- */
  // El hash es `#articulo` o `#articulo/seccion`: la URL dice qué se está leyendo y se puede compartir.
  function ruta() {
    var partes = decodeURIComponent(location.hash.slice(1)).split('/');
    return {slug: partes[0], sec: partes[1] || ''};
  }
  function irASeccion(id, instantaneo) {
    var host = actual && panel(actual);
    var h = host && id && host.querySelector('[id="' + id.replace(/"/g, '') + '"]');
    if (h) h.scrollIntoView({behavior: (instantaneo || sinMovimiento.matches) ? 'auto' : 'smooth', block: 'start'});
  }
  var movio = false;
  ['wheel', 'touchstart', 'keydown', 'pointerdown'].forEach(function(t) {
    window.addEventListener(t, function() { movio = true; }, {passive: true});
  });
  // Al abrir con `#articulo/seccion` las gráficas de arriba todavía no tienen su alto final:
  // se vuelve a la sección un par de veces, salvo que la persona ya se haya movido.
  function anclar(id) {
    movio = false;
    irASeccion(id, true);
    [700, 1800].forEach(function(ms) { setTimeout(function() { if (!movio) irASeccion(id, true); }, ms); });
  }
  function irArriba() {
    var tope = document.querySelector('.reader').getBoundingClientRect().top + window.scrollY;
    if (window.scrollY > tope) window.scrollTo({top: Math.max(0, tope), behavior: 'auto'});
  }

  function activar(slug, sec) {
    if (!articulo(slug)) slug = DEFECTO;
    if (slug === actual) { if (sec) irASeccion(sec); else irArriba(); return; }
    var primera = actual === null;
    movio = false;   // lo que cuenta es lo que la persona haga a partir de ahora
    actual = slug;
    ARTICULOS.forEach(function(a) { panel(a.slug).hidden = a.slug !== slug; });
    cards.forEach(function(c) {
      if (c.dataset.slug === slug) c.setAttribute('aria-current', 'page'); else c.removeAttribute('aria-current');
    });
    var i = indice(slug);
    pos.textContent = i + 1;
    btnPrev.disabled = i === 0;
    btnNext.disabled = i === ARTICULOS.length - 1;
    document.title = articulo(slug).title + ' · __NAME__ · FutViz';
    tocList.innerHTML = ''; secciones = []; toc.hidden = true;
    var carta = cards[i];
    centrarCard(carta);
    // Al cambiar de artículo se vuelve al inicio del panel; al abrir la página no se toca el scroll.
    if (!primera) irArriba();
    anuncio.textContent = articulo(slug).title;
    barra.style.transform = 'scaleX(0)';
    montar(slug).then(function() {
      if (actual !== slug) return;
      armarIndice();
      if (sec) anclar(sec);
      else if (!primera && !movio) irArriba();   // el navegador puede haber "anclado" la página al terminar de cargar
    });
    // Adelantar el siguiente mientras se lee este.
    var sig = ARTICULOS[i + 1];
    if (sig && sig.src) setTimeout(function() { pedir(sig.slug).catch(function() {}); }, 1200);
  }

  cards.forEach(function(c, i) {
    // Pedir el fragmento al apuntar o enfocar: cuando llega el clic ya suele estar descargado.
    function adelantar() { if (articulo(c.dataset.slug).src) pedir(c.dataset.slug).catch(function() {}); }
    c.addEventListener('pointerenter', adelantar);
    c.addEventListener('focus', adelantar);
    c.addEventListener('keydown', function(e) {
      var d = (e.key === 'ArrowDown' || e.key === 'ArrowRight') ? 1 : (e.key === 'ArrowUp' || e.key === 'ArrowLeft') ? -1 : 0;
      if (!d || !cards[i + d]) return;
      e.preventDefault();
      cards[i + d].focus();
      centrarCard(cards[i + d]);
    });
  });
  function ir(d) { var j = indice(actual) + d; if (ARTICULOS[j]) location.hash = ARTICULOS[j].slug; }
  btnPrev.addEventListener('click', function() { ir(-1); });
  btnNext.addEventListener('click', function() { ir(1); });
  function alHash() { var r = ruta(); activar(r.slug || DEFECTO, r.sec); }
  window.addEventListener('hashchange', alHash);
  document.getElementById('skip').addEventListener('click', function(e) { e.preventDefault(); pane.focus({preventScroll: false}); });


  alHash();
})();
</script>
__THEME_SCRIPT__
</body>
</html>
"""


def _minutos(body_html: str) -> int:
    texto = re.sub(r"<script.*?</script>|<[^>]+>", " ", body_html, flags=re.S)
    return max(1, round(len(texto.split()) / PALABRAS_POR_MINUTO))


def _card(slug, n, titulo, subtitulo, meta, soon=False):
    clase = "mini mini--soon" if soon else "mini"
    return (
        f'<li><a class="{clase}" href="#{slug}" data-slug="{slug}">'
        f'<span class="mini-meta"><span>{n:02d}</span><span>{meta}</span></span>'
        f'<span class="mini-title">{html.escape(titulo)}</span>'
        f'<span class="mini-sub">{html.escape(subtitulo)}</span></a></li>'
    )


def _panel_proximo(p, primero):
    leer = ""
    if primero:
        leer = (f'<a class="btn" href="#{primero.slug}">Leer «{html.escape(primero.title)}» {FLECHA_DER}</a>')
    return (
        f'<div class="soon-panel"><div class="soon-art">{ICONO_PROXIMO}</div>'
        f'<span class="kicker">Próximamente</span>'
        f'<h2>{html.escape(p["title"])}</h2>'
        f'<p>Este artículo todavía está en preparación. Mientras tanto, hay otro listo para leer.</p>{leer}</div>'
    )


def _fragmento(page: ArticlePage, n: int) -> str:
    """El contenido de un artículo dentro del lector: la misma portada, cuerpo y cierre que la
    página suelta, sin la cabecera ni la barra de progreso (las pone el cascarón)."""
    meta = "".join(f"<div><b>{label}</b>{value}</div>" for label, value in page.meta)
    meta += f"<div><b>Lectura</b>≈&nbsp;{_minutos(page.body_html)}&nbsp;min</div>"
    return (
        f'<div class="wrap hero"><span class="kicker">Artículo {n:02d}</span>'
        f'<h2 class="hero-title">{page.title}</h2><p class="deck">{page.deck}</p>'
        f'<div class="meta">{meta}</div></div>'
        f'<article>{page.body_html}</article>'
        f'<div class="wrap-wide article-end"><span class="note">Datos: {page.fuente}</span></div>'
    )


def write_ml_reader(section: str, articles: list, dist_dir: Path):
    """Escribe `dist/{slug}.html` (el lector) y un fragmento por artículo en `dist/vistas/ml/`.
    El primer artículo es el que abre la página; después van los "próximamente". Devuelve las rutas."""
    meta = SECTION_META[section]
    proximos = meta.get("proximos", [])
    todos = ([{"slug": a.slug, "title": a.title, "src": f"vistas/ml/{a.slug}.js"} for a in articles]
             + [{"slug": p["slug"], "title": p["title"], "src": ""} for p in proximos])

    frag_dir = dist_dir / "vistas" / "ml"
    frag_dir.mkdir(parents=True, exist_ok=True)
    salidas, cards, paneles = [], [], []
    for i, a in enumerate(articles):
        n = i + 1
        ruta = frag_dir / f"{a.slug}.js"
        # json.dumps escapa comillas y saltos de línea y, con ensure_ascii, no depende de la
        # codificación con que el navegador lea el .js.
        ruta.write_text(
            f"window.futvizArticulo({json.dumps(a.slug)},{json.dumps(_fragmento(a, n))});", encoding="utf-8")
        salidas.append(ruta)
        cards.append(_card(a.slug, n, a.title, a.subtitle, f"{_minutos(a.body_html)}&nbsp;min de lectura"))
        paneles.append(f'<section class="view" id="v-{a.slug}" aria-label="{html.escape(a.title)}" hidden></section>')
    primero = articles[0] if articles else None
    for j, p in enumerate(proximos):
        n = len(articles) + j + 1
        cards.append(_card(p["slug"], n, p["title"], p["subtitle"], "Próximamente", soon=True))
        paneles.append(f'<section class="view" id="v-{p["slug"]}" aria-label="{html.escape(p["title"])}" '
                       f'hidden>{_panel_proximo(p, primero)}</section>')

    datos = json.dumps(todos, ensure_ascii=False).replace("</", "<\\/")
    pagina = (READER_PAGE_TEMPLATE
              .replace("__THEME_COLOR__", THEME_COLOR_META)
              .replace("__FAVICON__", favicon_links())
              .replace("__PAGE_HEADER_CSS__", PAGE_HEADER_CSS)
              .replace("__PAGE_HEADER__", PAGE_HEADER_HTML)
              .replace("__NAME__", section)
              .replace("__DESCRIPTION__", html.escape(meta["description"]))
              .replace("__PRELOAD__", todos[0]["src"])
              .replace("__TOTAL__", str(len(todos)))
              .replace("__CHEVRON_IZQ__", CHEVRON_IZQ)
              .replace("__CHEVRON_DER__", CHEVRON_DER)
              .replace("__CARDS__", "".join(cards))
              .replace("__PANELS__", "".join(paneles))
              .replace("__ARTICLES_JSON__", datos)
              .replace("__ARTICLE_CSS__", ARTICLE_CSS)
              .replace("__THEME_INIT__", THEME_INIT_SCRIPT)
              .replace("__FONT_LINKS__", FONT_LINKS)
              .replace("__BRAND_ROOT__", BRAND_ROOT_CSS)
              .replace("__THEME_TOGGLE__", THEME_TOGGLE_HTML)
              .replace("__THEME_SCRIPT__", PLOTLY_THEME_SCRIPT))
    out = dist_dir / f"{meta['slug']}.html"
    out.write_text(pagina, encoding="utf-8")
    return [out] + salidas
