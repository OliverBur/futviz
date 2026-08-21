"""Identidad visual compartida para los notebooks de futviz_pl / top5ligas.

Un solo lugar para paleta y estilo matplotlib: se importa igual en todos
los notebooks del proyecto para que cada gráfico se vea consistente.
"""

import contextlib

import matplotlib as mpl

LEAGUE_ORDER = ["Bundesliga", "Serie A", "Ligue 1", "La Liga", "Premier League"]

LEAGUE_COLORS = {
    "Bundesliga": "#e34948",      # rojo
    "Serie A": "#2a78d6",         # azul
    "Ligue 1": "#2e413a",         # aqua
    "La Liga": "#eda100",         # amarillo
    "Premier League": "#e87ba4",  # magenta
}

# Rampa secuencial (magnitud, un solo equipo/métrica), claro -> oscuro
SEQUENTIAL_BLUE = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]

# Paleta categórica para CLUSTERS de estilo (ml_style_clusters.ipynb), en orden
# fijo de slot — nunca ciclada, nunca reasignada por ranking. Es distinta de
# LEAGUE_COLORS a propósito: en ese notebook el color significa "arquetipo de
# estilo", no "liga", y mezclar ambos significados confundiría al lector.
#
# Validada con el validador de la skill de dataviz (puerto Python del
# validate_palette.js, mismos umbrales y misma simulación Machado 2009) sobre
# la superficie clara del proyecto (#fcfcfb), en modo `--pairs all` porque se
# usa en scatter y en grafo (no solo en barras/leyenda, donde bastaría el
# pairlist adyacente):
#   - peor par bajo daltonismo (mín. protan/deutan): ΔE 8.3  (objetivo ≥ 8.0)
#   - peor par en visión normal:                      ΔE 15.1 (piso duro ≥ 15.0)
#   - banda de luminosidad y piso de croma: OK en los 6 slots
# Amarillo y magenta quedan por debajo de 3:1 de contraste contra la superficie
# clara: aplica la "regla de relieve" — en el notebook siempre van acompañados
# de hover con el nombre del arquetipo y de las tablas de membresía, así que la
# identidad nunca depende solo del color.
CLUSTER_COLORS = ["#256abf", "#d95926", "#199e70", "#eda100", "#9085e9", "#e87ba4"]

# Par divergente (sobre/bajo lo esperado): positivo vs negativo, gris en cero
DIVERGING = {"pos": "#2a78d6", "neg": "#e34948", "mid": "#cfcecb"}

INK = {
    "surface": "#fcfcfb",
    "primary": "#0b0b0b",
    "secondary": "#52514e",
    "muted": "#898781",
    "grid": "#e1e0d9",
    "axis": "#c3c2b7",
}

# Tinta para la variante oscura de los PNG de matplotlib (radar, ranking de
# porterías) — mismos roles que INK, valores que matchean la paleta oscura
# del sitio (ver BRAND_ROOT_CSS en web/site_utils.py). No reemplaza a INK:
# se usa solo dentro de dark_ink() para renderizar una segunda vez.
DARK_INK = {
    "surface": "#1B2426",
    "primary": "#D7E4E7",
    "secondary": "#C7D3D6",
    "muted": "#8CA0A5",
    "grid": "#2C393C",
    "axis": "#3A4A4E",
}


@contextlib.contextmanager
def dark_ink():
    """Cambia INK a la paleta oscura (mutación in-place del dict — todo lo
    que hizo `from viz_theme import INK` ve el cambio sin re-importar) y
    re-aplica el tema de matplotlib, para renderizar la misma figura una
    segunda vez en oscuro. Restaura la paleta clara al salir."""
    original = dict(INK)
    INK.update(DARK_INK)
    apply_theme()
    try:
        yield
    finally:
        INK.update(original)
        apply_theme()


def apply_theme():
    """Aplica el tema a matplotlib. Llamar una vez al inicio del notebook."""
    mpl.rcParams.update({
        # Transparente (no INK["surface"]) para que el PNG final no traiga
        # un rectángulo blanco/casi-blanco propio — en el sitio deja ver el
        # fondo grisáceo de `.chart-scroll`, en el notebook cae sobre el
        # blanco de Jupyter. INK["surface"] se sigue usando aparte para
        # cosas como el borde de los marcadores (necesita ser un color
        # opaco, no transparente).
        "figure.facecolor": "none",
        "axes.facecolor": "none",
        "savefig.facecolor": "none",
        "axes.edgecolor": INK["axis"],
        "axes.labelcolor": INK["secondary"],
        "text.color": INK["primary"],
        "xtick.color": INK["muted"],
        "ytick.color": INK["muted"],
        "grid.color": INK["grid"],
        "grid.linewidth": 0.6,
        "axes.grid": True,
        "axes.axisbelow": True,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.spines.left": False,
        "font.family": "sans-serif",
        "font.sans-serif": ["Segoe UI", "DejaVu Sans", "Arial"],
        "font.size": 11,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "axes.titlepad": 14,
        "figure.dpi": 110,
        "savefig.dpi": 150,
        "legend.frameon": False,
        "legend.fontsize": 9.5,
    })


def league_color(liga):
    return LEAGUE_COLORS.get(liga, INK["muted"])


def apply_plotly_theme(opaque_surface=False):
    """Registra y activa un template de Plotly con la misma identidad visual
    (superficie, tinta, grid) que apply_theme() usa para matplotlib. Llamar
    una vez al inicio de un notebook que use gráficos Plotly.

    `opaque_surface=True` pinta la superficie del gráfico con INK["surface"]
    en vez de dejarla transparente. Es para los notebooks: ahí el `.ipynb` se
    lee tal cual, sobre el fondo que ponga el visor (VS Code en tema oscuro,
    Jupyter en claro), y un fondo transparente hace que el gráfico herede ese
    fondo y se vea inconsistente de un visor a otro. Con superficie opaca el
    gráfico siempre se ve claro, como está diseñado. El default sigue siendo
    transparente porque el SITIO sí necesita transparencia: ahí el fondo lo
    pone la página (`.chart-scroll`) y cambia con el toggle claro/oscuro."""
    import plotly.graph_objects as go
    import plotly.io as pio

    # Misma familia tipográfica (Inter) que el resto del sitio (landing,
    # secciones, chrome de las páginas de chart) — antes el gráfico en sí
    # quedaba en Segoe UI/Arial, lo que lo delataba como un widget de
    # Plotly insertado en vez de sentirse parte del diseño.
    font_family = "Inter, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"

    axis = dict(
        gridcolor=INK["grid"],
        zerolinecolor=INK["axis"],
        linecolor=INK["axis"],
        tickfont=dict(family=font_family, color=INK["muted"], size=11),
        title=dict(font=dict(family=font_family, color=INK["secondary"], size=12)),
    )
    surface = INK["surface"] if opaque_surface else "rgba(0,0,0,0)"
    pio.templates["futviz"] = go.layout.Template(
        layout=go.Layout(
            # Transparente por default: en el sitio deja ver el fondo grisáceo
            # de la página (`.chart-scroll` ya no es una tarjeta blanca). Ver
            # el docstring para por qué los notebooks la piden opaca.
            paper_bgcolor=surface,
            plot_bgcolor=surface,
            font=dict(family=font_family, color=INK["primary"], size=12),
            title=dict(
                font=dict(size=18, color=INK["primary"], family=font_family),
                subtitle=dict(font=dict(family=font_family, size=12.5, color=INK["secondary"])),
                x=0.03, xanchor="left",
            ),
            xaxis=axis,
            yaxis=axis,
            legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(family=font_family, color=INK["secondary"], size=11)),
            hoverlabel=dict(bgcolor=INK["surface"], bordercolor=INK["axis"],
                             font=dict(family=font_family, color=INK["primary"], size=12)),
            margin=dict(t=90, r=40, b=60, l=70),
        )
    )
    pio.templates.default = "futviz"


# Valor del filtro de liga cuando no hay ninguna seleccionada. Es también la
# mitad "liga" de la clave de estado de la caja de lectura ("temporada|liga").
_ALL = "__all__"

# Lo que ocupa la columna de controles a la derecha del gráfico: el gap del
# layout más el ancho máximo de la barra lateral (ver `_sidebar_css`). El
# bloque entero mide entonces `width + SIDEBAR_ANCHO`, que es lo que hace falta
# saber para centrarlo — la fila de abajo (caja de lectura + top 5) mide algo
# menos, así que entra en el mismo ancho.
SIDEBAR_ANCHO = 20 + 260


def _centrado(html, width, extra=SIDEBAR_ANCHO):
    """Centra el bloque entero de un gráfico dentro del contenedor de la página.

    El gráfico y sus controles suman un ancho FIJO, pero la tarjeta que los
    contiene se estira a lo ancho de la ventana: sin esto, en un monitor grande
    queda todo pegado al borde izquierdo con medio ancho vacío a la derecha.

    Se centra el bloque completo y no cada pieza por separado a propósito: las
    piezas están alineadas entre sí —el crédito de la fuente va al borde derecho
    del gráfico, la caja de lectura al izquierdo— y centrarlas una por una, con
    sus max-width distintos, las desalinearía. `max-width` y no `width` para que
    en pantalla angosta se siga achicando como hasta ahora."""
    return (f'<div style="max-width: {width + extra}px; margin-inline: auto;">'
            f'{html}</div>')


def _md_inline(texto):
    """Convierte el subconjunto de markdown que usan los textos de `insights.py`
    (`**negrita**`, `` `código` ``, párrafos separados por línea en blanco) a
    HTML. Se escapa primero: el texto trae nombres de equipo que vienen de los
    datos, no de un literal del código."""
    import html as _html
    import re as _re

    partes = []
    for parrafo in texto.split("\n\n"):
        p = _html.escape(parrafo.strip())
        p = _re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", p)
        p = _re.sub(r"`(.+?)`", r"<code>\1</code>", p)
        partes.append(f"<p>{p}</p>")
    return "".join(partes)


# Cómo se nombra cada origen en el crédito que va debajo de cada gráfico. Están
# acá y no en cada módulo del sitio porque los mismos gráficos se muestran en
# los notebooks: el crédito tiene que decir lo mismo en los dos lados.
FUENTE_FBREF = "FBref"
FUENTE_UNDERSTAT = "Understat"


def _fuente_html(div_id, width, fuente):
    """El crédito de la fuente de datos, alineado al borde derecho del gráfico.

    Va como HTML debajo del gráfico y no como anotación dentro de la figura
    porque cada gráfico del sitio tiene sus propios márgenes, leyenda y títulos
    de eje: una anotación anclada al papel termina encimándose a alguno de esos
    en cuanto la figura cambia de forma, y un crédito no tiene por qué depender
    de eso. `max-width` es el mismo ancho del gráfico, así que "a la derecha"
    es el borde derecho del gráfico y no el de la página."""
    if not fuente:
        return ""
    return f"""
<style>
  #{div_id}_fuente {{ font-family: "Inter", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
    max-width: {width}px; margin: 8px 0 0; text-align: right; font-size: 11.5px;
    color: var(--color-muted, {INK["muted"]}); }}
</style>
<p id="{div_id}_fuente">Datos: {fuente}</p>"""


def _insight_css(div_id, width):
    """La caja de lectura debajo del gráfico. Los colores salen de las variables
    del sitio con los tonos de `INK` como respaldo, igual que la barra lateral:
    así la misma caja sirve en el sitio (claro y oscuro) y en un notebook, que
    no tiene ese `:root`."""
    return f"""
  #{div_id}_insight {{ font-family: "Inter", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
    max-width: {width}px; margin: 18px 0 4px; display: flex; flex-direction: column; gap: 14px;
    font-size: 13.5px; line-height: 1.58; color: var(--color-text-body, {INK["secondary"]}); }}
  #{div_id}_insight h4 {{ margin: 0 0 5px; font-size: 11px; font-weight: 700;
    text-transform: uppercase; letter-spacing: .05em;
    color: var(--color-muted, {INK["muted"]}); }}
  #{div_id}_insight p {{ margin: 0 0 7px; }}
  #{div_id}_insight p:last-child {{ margin-bottom: 0; }}
  #{div_id}_insight strong {{ color: var(--color-primary, {INK["primary"]}); font-weight: 600; }}
  #{div_id}_insight code {{ font-size: 12.5px;
    background: var(--color-bg, {INK["grid"]}); padding: 1px 4px; border-radius: 3px; }}
  #{div_id}_insight .fv-dyn {{ border-left: 3px solid var(--color-interactive, {INK["axis"]});
    padding: 2px 0 2px 13px; }}
  #{div_id}_insight .fv-estado {{ color: var(--color-interactive, {INK["axis"]});
    font-weight: 700; letter-spacing: .03em; }}
  #{div_id}_insight .fv-salta {{ margin-top: 6px; }}
  #{div_id}_insight details {{ border-top: 1px solid var(--color-border, {INK["grid"]});
    padding-top: 11px; }}
  #{div_id}_insight summary {{ cursor: pointer; font-size: 11px; font-weight: 700;
    text-transform: uppercase; letter-spacing: .05em;
    color: var(--color-muted, {INK["muted"]}); list-style: none; }}
  #{div_id}_insight summary::-webkit-details-marker {{ display: none; }}
  #{div_id}_insight summary::after {{ content: " +"; }}
  #{div_id}_insight details[open] summary::after {{ content: " −"; }}
  #{div_id}_insight details[open] summary {{ margin-bottom: 9px; }}
  #{div_id}_insight summary:hover {{ color: var(--color-interactive, {INK["primary"]}); }}"""


def _div_id(fig, *extra):
    """Id del `<div>` del gráfico, derivado de su contenido.

    Era `uuid4()`, o sea uno distinto en cada build. Como el id aparece decenas
    de veces dentro del JS de la página, reconstruir el sitio sin cambiar nada
    ensuciaba **todos** los `web/dist/*.html` con un diff enorme y escondía los
    cambios de verdad. Derivándolo del contenido, el id solo cambia cuando
    cambia el gráfico — que es justo cuando el diff tiene que aparecer.

    `extra` son las cosas que definen el gráfico pero no viven en la figura
    (columnas, payload de temporadas): sin ellas dos gráficos que se ven igual
    pero se comportan distinto compartirían id, y el JS del segundo terminaría
    manipulando el primero."""
    import hashlib
    import plotly.io as pio

    semilla = pio.to_json(fig) + "|" + "|".join(str(e) for e in extra)
    return "chart_" + hashlib.sha1(semilla.encode("utf-8")).hexdigest()[:8]


def _insight_html(div_id, ins, key, estado):
    d = ins["dinamico"][key]
    salta = d.get("salta")
    return f"""
<div id="{div_id}_insight">
  <div>
    <h4>Qué mirar aquí</h4>
    {_md_inline(ins["que_mirar"])}
  </div>
  <div class="fv-dyn">
    <h4>En lo que estás viendo · <span class="fv-estado" id="{div_id}_ins_estado">{estado}</span></h4>
    <p id="{div_id}_ins_fija">{_md_inline(d["fija"])[3:-4]}</p>
    <p class="fv-salta" id="{div_id}_ins_salta"{'' if salta else ' style="display:none"'}>{
        _md_inline(salta)[3:-4] if salta else ''}</p>
  </div>
  <details>
    <summary>Por qué estas variables</summary>
    <div>{_md_inline(ins["por_que"])}</div>
  </details>
</div>"""


def _insight_js(div_id, ins):
    """Los textos ya vienen en HTML desde Python (una sola conversión de
    markdown, en el build) — acá solo se intercambian."""
    import json

    payload = {k: {"fija": _md_inline(v["fija"])[3:-4],
                    "salta": _md_inline(v["salta"])[3:-4] if v.get("salta") else None}
               for k, v in ins["dinamico"].items()}
    return f"""
  var insights = {json.dumps(payload, ensure_ascii=False)};
  function setInsight(key, estado) {{
    var d = insights[key];
    if (!d) return;
    document.getElementById('{div_id}_ins_estado').textContent = estado;
    document.getElementById('{div_id}_ins_fija').innerHTML = d.fija;
    var s = document.getElementById('{div_id}_ins_salta');
    s.innerHTML = d.salta || '';
    s.style.display = d.salta ? '' : 'none';
  }}"""


def _toplist_css(div_id, width):
    """La columna del top 5, a la derecha de la caja de lectura.

    Va debajo del gráfico y no dentro de la barra lateral porque no es un
    control: no cambia nada, cuenta lo que ya se está viendo. Y va al lado de la
    caja de lectura, no debajo, porque las dos responden a lo mismo desde
    ángulos distintos —una en prosa, la otra en nombres— y leerlas juntas es lo
    que hace que el número de la prosa tenga cara.

    El ancho de la columna (250px) es el mismo de la barra lateral de arriba,
    así que las dos quedan alineadas en el mismo borde derecho."""
    return f"""
  #{div_id}_below {{ display: flex; flex-wrap: wrap; align-items: flex-start; gap: 26px; }}
  /* Anula el max-width de la caja de lectura para que comparta la fila. La
     columna de texto queda más angosta que los 760px de antes, que además se
     lee mejor. */
  #{div_id}_insight {{ flex: 1 1 380px; max-width: {width}px; }}
  #{div_id}_toplist {{ flex: 0 1 250px; min-width: 190px; margin: 18px 0 4px;
    font-family: "Inter", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }}
  #{div_id}_toplist h4 {{ margin: 0 0 6px; font-size: 11px; font-weight: 700;
    text-transform: uppercase; letter-spacing: .05em; line-height: 1.4;
    color: var(--color-muted, {INK["muted"]}); }}
  #{div_id}_toplist ol {{ list-style: none; margin: 0 0 18px; padding: 0; }}
  #{div_id}_toplist li {{ display: flex; align-items: baseline; gap: 8px; padding: 5px 0;
    font-size: 12.5px; border-bottom: 1px solid var(--color-border, {INK["grid"]}); }}
  #{div_id}_toplist li:last-child {{ border-bottom: none; }}
  #{div_id}_toplist .pos {{ flex: none; width: 12px; text-align: right;
    color: var(--color-muted, {INK["muted"]}); font-variant-numeric: tabular-nums; }}
  #{div_id}_toplist .nom {{ flex: 1 1 auto; min-width: 0; overflow: hidden;
    text-overflow: ellipsis; white-space: nowrap;
    color: var(--color-primary, {INK["primary"]}); }}
  #{div_id}_toplist .val {{ flex: none; font-weight: 600; font-variant-numeric: tabular-nums;
    color: var(--color-text-body, {INK["secondary"]}); }}"""


def _toplist_html(div_id, top_n):
    return f"""
<div id="{div_id}_toplist">
  <h4>Top {top_n} · <span id="{div_id}_top_x_label"></span></h4>
  <ol id="{div_id}_top_x"></ol>
  <h4>Top {top_n} · <span id="{div_id}_top_y_label"></span></h4>
  <ol id="{div_id}_top_y"></ol>
</div>"""


def _toplist_js(div_id, top_n):
    """Define `pintarTop(labelX, labelY, nombres, xs, ys)`.

    Las listas se arman en el navegador, sobre los mismos arreglos que Plotly
    tiene dibujados, y no precalculadas desde Python: así respetan solas los
    tres filtros (temporada, liga y el de puntos) sin que haya que precalcular
    una lista por combinación, y no pueden mostrar a alguien que no está en el
    gráfico. Es el mismo criterio del r² del explorador."""
    return f"""
  var TOP_N = {top_n};
  function _esc(t) {{
    return String(t).replace(/&/g, '&amp;').replace(/</g, '&lt;')
                     .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }}
  // Los decimales salen de los propios valores: la misma columna sirve para
  // goles (enteros), para xG (una decimal) y para tasas por 90' (dos), y
  // pedirle al llamador que los declare por eje sería un parámetro más que se
  // desincroniza del gráfico.
  function _dec(vals) {{
    var v = vals.filter(function(a) {{ return a !== null && isFinite(a); }});
    if (!v.length) return 0;
    if (v.every(function(a) {{ return a === Math.round(a); }})) return 0;
    var mx = Math.max.apply(null, v.map(Math.abs));
    return mx < 10 ? 2 : 1;
  }}
  function _llenar(id, nombres, vals) {{
    var lista = document.getElementById('{div_id}_' + id);
    if (!lista) return;
    var idx = [];
    for (var i = 0; i < vals.length; i++) {{
      if (vals[i] !== null && isFinite(vals[i])) idx.push(i);
    }}
    idx.sort(function(a, b) {{ return vals[b] - vals[a]; }});
    var dec = _dec(vals);
    lista.innerHTML = idx.slice(0, TOP_N).map(function(i, k) {{
      return '<li><span class="pos">' + (k + 1) + '</span>' +
             '<span class="nom" title="' + _esc(nombres[i]) + '">' + _esc(nombres[i]) + '</span>' +
             '<span class="val">' + vals[i].toFixed(dec) + '</span></li>';
    }}).join('') || '<li><span class="nom">Sin datos</span></li>';
  }}
  function pintarTop(labelX, labelY, nombres, xs, ys) {{
    var ex = document.getElementById('{div_id}_top_x_label');
    var ey = document.getElementById('{div_id}_top_y_label');
    if (ex) ex.textContent = labelX;
    if (ey) ey.textContent = labelY;
    _llenar('top_x', nombres, xs);
    _llenar('top_y', nombres, ys);
  }}"""


def _sidebar_css(div_id, width, aspect_ratio, mobile_aspect=None):
    """Estilos de la barra lateral de controles (gráfico a la izquierda,
    controles en una columna aparte a la derecha, nunca superpuestos).

    Compartido por `sidebar_chart_html` (buscador + filtros) y
    `select_chart_html` (solo desplegables), para que los dos tipos de
    gráfico interactivo del sitio se vean exactamente igual.

    En pantalla angosta el gráfico se vuelve más cuadrado: a lo ancho de un
    teléfono, un scatter con la proporción del escritorio queda demasiado
    aplastado para distinguir los puntos. `mobile_aspect` anula esa regla para
    los gráficos donde la proporción no es una preferencia sino parte del
    contenido — el mapa de tiros dibuja una cancha, y estirar la caja a lo alto
    no agranda la cancha: solo agrega franjas vacías arriba y abajo."""
    movil = mobile_aspect or max(aspect_ratio * 0.6, 0.85)
    return f"""
  #{div_id}_layout {{ display:flex; flex-wrap: wrap; align-items:flex-start; gap:20px; max-width: 100%; }}
  #{div_id}_plotwrap {{ position: relative; flex: 1 1 280px; width: 100%; max-width: {width}px;
    aspect-ratio: {aspect_ratio}; min-width: 0; }}
  #{div_id}_plotwrap > div {{ position: absolute; inset: 0; }}
  #{div_id}_sidebar {{ font-family: "Inter", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
    padding-top: 54px; flex: 1 1 190px; max-width: 260px; box-sizing: border-box; }}
  #{div_id}_sidebar .block {{ margin-bottom: 22px; }}
  #{div_id}_sidebar label {{ display: block; font-size: 11px; color: var(--color-muted, {INK["muted"]});
    text-transform: uppercase; letter-spacing: .03em; margin-bottom: 5px; }}
  #{div_id}_sidebar .hint {{ font-size: 11.5px; line-height: 1.45; color: var(--color-muted, {INK["muted"]});
    text-transform: none; letter-spacing: 0; margin-top: -14px; }}
  /* Casilla de filtro por punto (ej. "solo sub-21"). Necesita anular el
     `width:100%` de los inputs de arriba, pensado para el buscador. */
  #{div_id}_sidebar .toggle {{ display: flex; align-items: center; gap: 8px; }}
  #{div_id}_sidebar .toggle input {{ width: auto; flex: none; margin: 0; padding: 0;
    accent-color: var(--color-interactive, {INK["axis"]}); cursor: pointer; }}
  #{div_id}_sidebar .toggle span {{ font-size: 13px; cursor: pointer;
    color: var(--color-primary, {INK["primary"]}); }}
  #{div_id}_sidebar .toggle + .hint {{ margin-top: 7px; }}
  #{div_id}_sidebar select + .hint {{ margin-top: 7px; }}
  #{div_id}_sidebar input, #{div_id}_sidebar select {{ width: 100%; box-sizing: border-box;
    padding: 7px 9px; font-size: 13px; font-family: inherit; color: var(--color-primary, {INK["primary"]});
    background: var(--color-surface, {INK["surface"]}); border: 1px solid var(--color-border, {INK["axis"]});
    border-radius: 6px; transition: border-color .15s ease; }}
  #{div_id}_sidebar input:focus, #{div_id}_sidebar select:focus {{
    outline: none; border-color: var(--color-interactive, {INK["axis"]}); }}
  @media (max-width: 520px) {{
    #{div_id}_sidebar {{ padding-top: 4px; max-width: 100%; }}
    #{div_id}_plotwrap {{ aspect-ratio: {movil}; }}
  }}"""


def iso_lines(fig, niveles, x_range, y_range, combinar="suma", puntos=80,
               color=None, ancho=1.4, etiqueta_en="inicio"):
    """Curvas de nivel del indicador que combina los dos ejes del scatter.

    Es el recurso que en la prensa de datos marca "de acá para arriba están los
    mejores": cada curva une los puntos que valen lo mismo en el indicador
    combinado, así que a un lado están los que llegan a ese nivel y al otro los
    que no — sin tener que elegir cuál de los dos ejes importa más.

    **Hoy no lo usa ningún gráfico del sitio, a propósito.** Se probó en el
    perfil ofensivo (xG90 vs. xA90) y en la eficiencia de definición y se quitó
    de los dos: el problema no era el dibujo sino meterlo en gráficos que ya
    tenían su propio sistema de referencia. El perfil ofensivo divide por tipo
    de jugador con las líneas de promedio, y las diagonales dividen por nivel;
    superponer las dos varas sobre 1.900 puntos obliga a leer cada punto dos
    veces, y encima las diagonales cruzaban sobre todo el hueco de arriba a la
    izquierda para separar 19 jugadores. Queda acá porque el recurso es bueno
    cuando el gráfico se diseña alrededor de él — no cuando se le encaja
    encima.

    Solo tiene sentido cuando combinar los dos ejes significa algo:

    - `combinar="suma"` (`x + y = k`, rectas) pide que los dos ejes estén en la
      misma unidad. xG90 y xA90 lo están: los dos son "goles esperados por 90",
      y sumarlos da la contribución ofensiva total.
    - `combinar="producto"` (`x · y = k`, hipérbolas) pide que el producto sea
      una magnitud real. SoT% × G/SoT es exactamente goles por tiro, así que
      cada hipérbola es un nivel de eficiencia de remate.

    Cruzar dos ejes que no cumplen ninguna de las dos cosas y dibujarles una
    frontera igual es inventar un ranking: la curva estaría diciendo que un
    punto de posesión vale lo mismo que un punto de porterías a cero.

    `niveles` es una lista de `(valor, etiqueta)`. Las curvas se recortan a la
    caja del gráfico, así que el rango de los ejes no cambia por dibujarlas.
    `etiqueta_en` elige de qué punta cuelga el rótulo — `"inicio"` (arriba a la
    izquierda) o `"fin"` (abajo a la derecha): las dos son zonas vacías por
    definición, y cuál conviene depende de qué más haya escrito en el gráfico.

    Devuelve las anotaciones de las etiquetas — hay que pasarlas a la figura
    (`annotations=`) y al helper de la barra lateral (`base_annotations=`), o
    desaparecen en cuanto alguien busca una entidad. Las trazas se agregan a
    `fig`, y como el filtro de liga asume que las trazas extra van DESPUÉS de
    las de liga, esto se llama con la figura ya armada y hay que contarlas en
    `extra_traces`."""
    import numpy as np
    import plotly.graph_objects as go

    color = color or INK["axis"]
    (x_lo, x_hi), (y_lo, y_hi) = x_range, y_range
    anotaciones = []

    for k, etiqueta in niveles:
        if combinar == "suma":
            x1, x2 = max(x_lo, k - y_hi), min(x_hi, k - y_lo)
            xs = np.array([x1, x2])
            ys = k - xs
        else:
            # Con producto el dominio se limita a x > 0: la hipérbola no cruza
            # el eje, y a la izquierda del cero no hay nada que dibujar.
            x1 = max(x_lo, k / y_hi if y_hi > 0 else x_lo, 1e-9)
            x2 = min(x_hi, k / y_lo if y_lo > 0 else x_hi)
            if x2 <= x1:
                continue
            xs = np.linspace(x1, x2, puntos)
            ys = k / xs
        if xs[-1] <= xs[0]:
            continue

        fig.add_trace(go.Scatter(
            x=xs, y=ys, mode="lines", showlegend=False, hoverinfo="skip",
            line=dict(color=color, width=ancho, dash="dash")))

        # La etiqueta cuelga de una de las dos puntas de la curva, corrida un
        # poco hacia adentro para no pegarse al eje. Las dos puntas son zona
        # vacía por definición —arriba a la izquierda y abajo a la derecha son
        # los extremos que casi nadie ocupa—, que es de lo que habla la curva.
        inicio = etiqueta_en == "inicio"
        x_lab = (xs[0] + 0.02 * (x_hi - x_lo)) if inicio else (xs[-1] - 0.02 * (x_hi - x_lo))
        y_lab = (k - x_lab) if combinar == "suma" else (k / x_lab)
        anotaciones.append(dict(
            x=x_lab, y=y_lab, text=etiqueta, showarrow=False,
            xanchor="left" if inicio else "right",
            yanchor="bottom" if inicio else "top",
            font=dict(size=10.5, color=INK["muted"])))

    return anotaciones


def top_levels(serie, percentiles):
    """`[(valor, "Top N%"), ...]` a partir de los percentiles de `serie`.

    Los cortes salen de las 5 temporadas juntas y no de la que se está
    mostrando: si se recalcularan con cada cambio del selector, "estar sobre la
    línea del top 1%" significaría algo distinto en cada temporada y comparar
    entre ellas dejaría de tener sentido. Es la misma razón por la que los ejes
    tampoco se reescalan."""
    return [(float(serie.quantile(1 - p / 100)), f"Top {p:g}%") for p in percentiles]


def _control_options(c):
    """La lista plana de valores de un control, los declare como `options` o
    solo dentro de `groups`."""
    return c.get("options") or [o for _, opciones in c["groups"] for o in opciones]


def _rotulo(control, respaldo="Filtrar"):
    """El `<label>` de un control de la barra lateral, o nada.

    `"label": None` lo saca a propósito: una casilla cuyo texto ya dice qué
    hace ("Jugadores sub-21") no necesita además un encabezado arriba, que
    termina diciendo lo mismo dos veces."""
    texto = control.get("label", respaldo)
    return f"\n      <label>{texto}</label>" if texto else ""


def _select_options(c):
    """Los `<option>` de un control, envueltos en `<optgroup>` si declara
    `groups` = `[(etiqueta o None, [opciones]), ...]`.

    Agrupar hace falta cuando un mismo desplegable mezcla dos taxonomías —el
    mapa de tiros filtra por jugada Y por parte del cuerpo en un solo control—:
    sin los grupos la lista se lee como si las opciones fueran excluyentes
    entre sí, y "cabezazo" y "córner" no lo son."""
    labels = c.get("labels", {})

    def opt(o):
        return f'<option value="{o}">{labels.get(o, o)}</option>'

    if not c.get("groups"):
        return "".join(opt(o) for o in c["options"])
    partes = []
    for etiqueta, opciones in c["groups"]:
        interior = "".join(opt(o) for o in opciones)
        partes.append(f'<optgroup label="{etiqueta}">{interior}</optgroup>'
                      if etiqueta else interior)
    return "".join(partes)


def select_chart_html(fig, controls, width=760, height=560, hint=None, min_width=None,
                       insights=None, insight_control=None, joint_updates=None,
                       mobile_aspect=None, fuente=None):
    """Gráfico Plotly con una barra lateral de desplegables genéricos.

    Es el hermano simple de `sidebar_chart_html`: sirve para gráficos que no
    tienen una entidad por punto que buscar (el radar de perfil de liga, la
    evolución por temporada) pero sí necesitan controles.

    `controls` es una lista de dicts:
        {"id": "season", "label": "Temporada", "default": "2025-26",
         "options": ["2021-22", ...],
         "updates": {opcion: {"restyle": {...}, "relayout": {...}}}}

    `restyle` puede ser un dict (se aplica a todas las trazas) o una lista de
    pasos `{"update": {...}, "traces": [i, j]}` para cuando un mismo control
    tiene que tocar propiedades distintas en trazas distintas (ej. el radar
    sobrepuesto, que actualiza el polar y la barra de separación a la vez).

    Cada control es independiente y aplica su propio `restyle`/`relayout`, así
    que combinarlos funciona mientras toquen propiedades distintas (igual que
    el filtro de liga y el buscador del otro helper). `hint` es un texto de
    ayuda opcional debajo de los controles.

    `joint_updates` es para los gráficos donde eso **no** alcanza: un mapa de
    calor no tiene una propiedad por control que se pueda tocar por separado —
    la matriz `z` depende de la temporada Y del tipo de tiro a la vez, así que
    dos `restyle` independientes se pisarían. Es un dict
    `{"valor1|valor2": {"restyle": ..., "relayout": ...}}` con una entrada por
    combinación de los controles, en el orden en que están declarados, que se
    aplica después de los `updates` propios de cada control. Con
    `joint_updates` la caja de lectura también pasa a pedir esa clave
    compuesta, porque ahí ningún control por sí solo describe lo que se ve.

    Un control puede declarar sus opciones agrupadas (`groups`, ver
    `_select_options`) en vez de planas.

    `min_width` fuerza un ancho mínimo del gráfico en px: para figuras que no
    se pueden achicar sin volverse ilegibles (el radar de 5 subplots), es
    preferible que el contenedor `.chart-scroll` de la página scrollee en
    horizontal a que el gráfico se comprima — mismo criterio que ya se usó
    con las imágenes de matplotlib.

    Devuelve el HTML como string."""
    import json
    import plotly.io as pio

    div_id = _div_id(fig, controls, joint_updates)
    fig.update_layout(autosize=True)
    plot_html = pio.to_html(fig, full_html=False, include_plotlyjs="cdn",
                             div_id=div_id, config={"displaylogo": False, "responsive": True, "displayModeBar": False},
                             default_width="100%", default_height="100%")

    blocks, specs = [], []
    for c in controls:
        blocks.append(f"""
    <div class="block">
      <label>{c["label"]}</label>
      <select id="{div_id}_{c["id"]}">{_select_options(c)}</select>
    </div>""")
        specs.append({"id": c["id"], "default": c.get("default", _control_options(c)[0]),
                       "updates": c.get("updates", {}), "labels": c.get("labels", {})})
    if hint:
        blocks.append(f'\n    <div class="block"><div class="hint">{hint}</div></div>')

    min_width_css = (f"\n  #{div_id}_plotwrap {{ min-width: {min_width}px; }}"
                     if min_width else "")

    # La caja de lectura la maneja el control que se indique (por defecto el
    # primero): en el radar es la temporada, en el de evolución la métrica. Con
    # `joint_updates` la maneja el estado entero, por la misma razón por la que
    # el gráfico se actualiza por combinación.
    driver = insight_control or (controls[0]["id"] if controls else None)
    insight_css = insight_box = insight_js = ""
    if insights:
        if joint_updates:
            key0 = "|".join(s["default"] for s in specs)
            estado0 = " · ".join(s["labels"].get(s["default"], s["default"]) for s in specs)
        else:
            ctrl = next(c for c in controls if c["id"] == driver)
            key0 = ctrl.get("default", _control_options(ctrl)[0])
            # El rótulo del estado es la etiqueta legible del control, no su
            # valor: en el de evolución el valor es un nombre de columna
            # (`p90_Fls`).
            estado0 = ctrl.get("labels", {}).get(key0, key0)
        insight_css = _insight_css(div_id, width)
        insight_box = _insight_html(div_id, insights, key0, estado0)
        insight_js = _insight_js(div_id, insights)

    html = f"""
<style>{_sidebar_css(div_id, width, width / height, mobile_aspect)}{min_width_css}{insight_css}
</style>
<div id="{div_id}_layout">
  <div id="{div_id}_plotwrap">{plot_html}</div>
  <div id="{div_id}_sidebar">{"".join(blocks)}
  </div>
</div>{_fuente_html(div_id, width, fuente)}{insight_box}
<script>
(function() {{
  var specs = {json.dumps(specs)};
  var joint = {json.dumps(joint_updates or {}, ensure_ascii=False)};
  var useJoint = {json.dumps(bool(joint_updates))};
  var driver = {json.dumps(driver)};{insight_js}
  function valor(spec) {{ return document.getElementById('{div_id}_' + spec.id).value; }}
  function estado() {{ return specs.map(valor).join('|'); }}
  function apply(u) {{
    if (!u) return;
    if (u.restyle) {{
      // dict = todas las trazas; lista = pasos con sus propios índices
      var steps = Array.isArray(u.restyle) ? u.restyle : [{{update: u.restyle}}];
      steps.forEach(function(s) {{
        if (s.traces) Plotly.restyle('{div_id}', s.update, s.traces);
        else Plotly.restyle('{div_id}', s.update);
      }});
    }}
    if (u.relayout) Plotly.relayout('{div_id}', u.relayout);
  }}
  specs.forEach(function(spec) {{
    var el = document.getElementById('{div_id}_' + spec.id);
    el.value = spec.default;
    el.addEventListener('change', function(e) {{
      apply(spec.updates[e.target.value]);
      if (useJoint) apply(joint[estado()]);
      if (typeof setInsight !== 'function') return;
      if (useJoint) {{
        setInsight(estado(), specs.map(function(s) {{
          var v = valor(s); return s.labels[v] || v;
        }}).join(' · '));
      }} else if (spec.id === driver) {{
        setInsight(e.target.value, spec.labels[e.target.value] || e.target.value);
      }}
    }});
  }});
}})();
</script>
"""
    return _centrado(html, width)


def render_select_chart(fig, *args, **kwargs):
    """Muestra en el notebook el resultado de `select_chart_html(fig, ...)`."""
    from IPython.display import HTML, display
    display(HTML(select_chart_html(fig, *args, **kwargs)))


def _default_season(seasons, scatter_data, season_data):
    """Qué temporada es la que ya está dibujada en `fig`. Se identifica por
    identidad del objeto en vez de pedirle al llamador que la repita como
    argumento: `scatter_data` tiene que ser, literalmente, el valor que está
    en `season_data`, así que si no coincide es que el llamador se equivocó y
    conviene fallar acá y no dejar el gráfico inicial desincronizado del
    selector."""
    for s in seasons:
        if season_data[s] is scatter_data:
            return s
    raise ValueError(
        "scatter_data tiene que ser uno de los valores de season_data "
        "(es la temporada que se muestra al abrir el gráfico)"
    )


def sidebar_chart_html(fig, scatter_data, x_col, y_col, base_annotations=None,
                        extra_traces=0, base_size=11, highlight_size=20,
                        width=680, height=560, name_col="Squad", search_label="club",
                        season_data=None, custom_cols=None, subtitle_template=None,
                        insights=None, point_filter=None, cat_filter=None, fuente=None,
                        top_n=5, top_labels=None):
    """Arma el HTML/JS de un gráfico Plotly con una barra lateral genuina a
    la derecha (no superpuesta, es un elemento aparte en un layout flex). Los
    controles van **de lo que acota la población a lo que busca dentro de
    ella**, que es el orden en que se usan:
    - `<select>` de temporada (solo si se pasa `season_data`).
    - `<select>` para filtrar por liga.
    - `<select>` de `cat_filter`, si se pasa (ej. la posición).
    - Buscador con autocompletado NATIVO del navegador (`<input list>` +
      `<datalist>`) sobre `name_col` (ej. "Squad" para equipos, "player"
      para jugadores) — escribes unas letras y aparecen las opciones que
      matchean, sin necesidad de Dash ni de un menú con cientos de opciones.
    - Casilla de `point_filter`, si se pasa (ej. sub-21).
    Los controles manipulan el gráfico ya renderizado vía
    `Plotly.restyle`/`Plotly.relayout` en JS puro: no depende de un kernel
    vivo (ni de Python en general una vez generado el HTML), así que sirve
    tanto para incrustar en un notebook como para un archivo `.html`
    standalone servido como sitio estático.

    `fig` debe tener exactamente una traza por liga, en el mismo orden que
    `scatter_data` (lista de (liga, sub_df)), seguidas opcionalmente de
    `extra_traces` trazas que no varían con los filtros (ej. línea de
    tendencia) — esas trazas extra deben agregarse DESPUÉS de las de liga
    en `fig`, o el filtro de liga y el resaltado de búsqueda quedan
    desalineados (índice de traza vs. índice esperado). `base_annotations`
    son anotaciones fijas del gráfico (ej. etiquetas de cuadrante) que se
    preservan al buscar.

    Multitemporada: `season_data` es `{temporada: [(liga, sub_df), ...]}` con
    la misma estructura de `scatter_data` para cada temporada, y
    `scatter_data` debe ser la de la temporada que se muestra al abrir. El
    número de trazas NO cambia entre temporadas: son siempre las 5 ligas y lo
    que se intercambia son los datos que llevan dentro (`x`, `y`,
    `customdata`). Se eligió así, y no una traza por liga-temporada, porque
    mantener fijos los índices de traza es lo que evita el desalineado
    descrito arriba. `custom_cols` son las columnas del `customdata` (hace
    falta para poder reconstruirlo al cambiar de temporada) y
    `subtitle_template` un texto con `{temporada}` para actualizar el
    subtítulo.

    Responsivo: el gráfico no lleva ancho/alto fijo en px, sino que ocupa el
    100% de su contenedor con relación de aspecto `width:height` fija (así
    no se deforma) hasta un tope de `width`px; en pantallas angostas la
    barra lateral pasa a apilarse debajo del gráfico en vez de achicarlo.

    `top_n` es el largo de la lista de los que más puntúan en cada eje, que va
    a la derecha de la caja de lectura (`None` la saca). Los nombres de los ejes
    salen del título de cada eje de la figura; `top_labels` es un par para
    acortarlos cuando ese título es una frase larga que no entra en la columna.

    `point_filter` agrega una casilla que filtra PUNTOS (no trazas enteras,
    como hace el filtro de liga): un dict
    `{"col", "label", "text", "hint", "nota"}` donde `col` es una columna
    booleana de los sub-DataFrames — ej. `sub21`. Se implementa cambiando los
    datos de cada traza, igual que el cambio de temporada, porque "sub-21" es
    una propiedad de cada jugador y no de la traza de su liga; los valores
    nulos se tratan como False (edad desconocida no es sub-21). El filtro se
    combina con el de liga sin interferir: uno cambia los datos y el otro la
    visibilidad. `estado` es cómo se nombra el filtro en el rótulo de la caja
    de lectura, cuyos textos se piden con la clave `...|<col>` al activarlo.

    `cat_filter` es el mismo mecanismo pero para una columna CATEGÓRICA en vez
    de booleana — un `<select>` en lugar de una casilla:
    `{"col", "label", "options", "all_label", "hint", "clave"}`. Los puntos
    cuyo valor no está en `options` (dato faltante) quedan fuera al elegir
    cualquier categoría, igual que los nulos del filtro booleano. Se combina
    con los otros dos, y la clave de la caja de lectura pasa a ser
    `temporada|liga|<clave>:<categoría>[|<col booleana>]` — los segmentos se
    agregan solo cuando el filtro está puesto, así que las claves de un gráfico
    sin estos filtros no cambian.

    Devuelve el HTML como string (no lo muestra) — ver `render_with_sidebar`
    para mostrarlo directo en un notebook."""
    import json
    import plotly.io as pio

    div_id = _div_id(fig, x_col, y_col, name_col, sorted(season_data or ()))
    fig.update_layout(autosize=True)
    plot_html = pio.to_html(fig, full_html=False, include_plotlyjs="cdn",
                             div_id=div_id, config={"displaylogo": False, "responsive": True, "displayModeBar": False},
                             default_width="100%", default_height="100%")
    aspect_ratio = width / height
    _ALL_JSON = json.dumps(_ALL)

    base_annotations = list(base_annotations or [])
    trace_indices = list(range(len(scatter_data)))
    league_order = [liga for liga, _ in scatter_data]

    # Con una sola temporada se usa la clave "" y el selector no se dibuja, así
    # que el camino de un período es el mismo código que el de cinco.
    single_season = season_data is None
    if single_season:
        season_data = {"": scatter_data}
    seasons = list(season_data)
    default_season = seasons[-1] if single_season else _default_season(seasons, scatter_data, season_data)

    def _payload(sd):
        """Todo lo que hace falta para pintar y filtrar UNA temporada.

        Los nombres van una sola vez por traza y el arreglo de tamaños de
        marcador se arma en JS al buscar. La versión anterior precalculaba en
        Python un arreglo de tamaños completo *por cada entidad*, o sea O(N²):
        con los 1.583 jugadores de una temporada eran 2,5 millones de números
        embebidos y la página pesaba 10 MB; con las 5 temporadas (8.017
        jugadores) serían ~64 millones, unos 190 MB por página. Por lo mismo
        de cada entidad se guardan solo sus coordenadas y su liga, y la
        anotación de la búsqueda se arma en JS a partir de eso."""
        ents = {}
        for liga, sub in sd:
            for _, r in sub.iterrows():
                ents[r[name_col]] = {"l": liga, "x": r[x_col], "y": r[y_col]}
        payload = {
            "names": [sub[name_col].tolist() for _, sub in sd],
            "x": [sub[x_col].tolist() for _, sub in sd],
            "y": [sub[y_col].tolist() for _, sub in sd],
            "ents": ents,
        }
        if point_filter:
            # Un booleano por punto, no un juego duplicado de x/y/custom: el
            # filtrado se hace en JS. Duplicar los arreglos costaría el doble
            # de peso de página, y ya son la parte pesada (ver arriba).
            payload["f"] = [
                sub[point_filter["col"]].fillna(False).astype(bool).tolist()
                for _, sub in sd
            ]
        if cat_filter:
            # El ÍNDICE de la categoría, no su nombre: son miles de puntos y
            # repetir "Delantero" en cada uno pesa diez veces más que un entero.
            # -1 es "sin dato", que no pertenece a ninguna categoría.
            codigo = {v: i for i, v in enumerate(cat_filter["options"])}
            payload["g"] = [[codigo.get(v, -1) for v in sub[cat_filter["col"]]]
                             for _, sub in sd]
        if custom_cols:
            # Una sola columna va plana (`%{customdata}` en el hovertemplate);
            # varias, como filas (`%{customdata[0]}`) — igual que lo que arman
            # los llamadores al construir la figura.
            payload["custom"] = [
                sub[custom_cols[0]].tolist() if len(custom_cols) == 1
                else sub[list(custom_cols)].values.tolist()
                for _, sub in sd
            ]
        return payload

    seasons_payload = {s: _payload(sd) for s, sd in season_data.items()}
    subtitles = ({s: subtitle_template.format(temporada=s) for s in seasons}
                 if subtitle_template else {})

    season_options = "".join(f'<option value="{s}">{s}</option>' for s in seasons)
    league_options = "".join(f'<option value="{liga}">{liga}</option>' for liga in league_order)
    season_block = "" if single_season else f"""
    <div class="block">
      <label>Temporada</label>
      <select id="{div_id}_season">{season_options}</select>
    </div>"""

    filter_block = "" if not point_filter else f"""
    <div class="block">{_rotulo(point_filter)}
      <div class="toggle">
        <input type="checkbox" id="{div_id}_pfilter">
        <label for="{div_id}_pfilter" style="display:inline; text-transform:none;
          letter-spacing:0; margin:0;"><span>{point_filter.get("text", "Filtrar")}</span></label>
      </div>
      {f'<p class="hint">{point_filter["hint"]}</p>' if point_filter.get("hint") else ''}
    </div>"""

    cat_options = "" if not cat_filter else "".join(
        f'<option value="{o}">{o}</option>' for o in cat_filter["options"])
    cat_block = "" if not cat_filter else f"""
    <div class="block">{_rotulo(cat_filter, "Categoría")}
      <select id="{div_id}_cat">
        <option value="{_ALL}">{cat_filter.get("all_label", "Todas")}</option>
        {cat_options}
      </select>
      {f'<p class="hint">{cat_filter["hint"]}</p>' if cat_filter.get("hint") else ''}
    </div>"""

    # Caja de lectura. La clave del estado es "temporada|liga" ("__all__" cuando
    # no hay filtro de liga), así que se actualiza con cualquiera de los dos
    # controles. Con una sola temporada la clave es "|liga".
    insight_css = insight_box = insight_js = ""
    if insights:
        key0 = f"{default_season}|{_ALL}"
        # Mismo formato que arma refreshInsight() en JS, o el rótulo cambiaría
        # de forma en cuanto el usuario tocara cualquiera de los dos controles.
        estado0 = " · ".join(x for x in (default_season, "Todas las ligas") if x)
        insight_css = _insight_css(div_id, width)
        insight_box = _insight_html(div_id, insights, key0, estado0)
        insight_js = _insight_js(div_id, insights)

    # Los rótulos de las dos listas: el título de cada eje, salvo que el
    # llamador pase versiones cortas (hay títulos que son una frase entera).
    def _titulo(eje, respaldo):
        t = getattr(getattr(fig.layout, eje).title, "text", None)
        return t or respaldo

    top_css = top_html = top_js = ""
    below = insight_box
    if top_n:
        etiquetas = top_labels or (_titulo("xaxis", x_col), _titulo("yaxis", y_col))
        top_css = _toplist_css(div_id, width)
        top_html = _toplist_html(div_id, top_n)
        top_js = _toplist_js(div_id, top_n)
        below = f'<div id="{div_id}_below">{insight_box}{top_html}</div>'

    html = f"""
<style>{_sidebar_css(div_id, width, aspect_ratio)}{insight_css}{top_css}
</style>""" + f"""
<div id="{div_id}_layout">
  <div id="{div_id}_plotwrap">{plot_html}</div>
  <div id="{div_id}_sidebar">{season_block}
    <div class="block">
      <label>Filtrar por liga</label>
      <select id="{div_id}_league">
        <option value="{_ALL}">Todas las ligas</option>
        {league_options}
      </select>
    </div>{cat_block}
    <div class="block">
      <label>Buscar {search_label}</label>
      <input list="{div_id}_clubs" id="{div_id}_search" placeholder="Escribe un {search_label}…" autocomplete="off">
      <datalist id="{div_id}_clubs"></datalist>
    </div>{filter_block}
  </div>
</div>{_fuente_html(div_id, width, fuente)}{below}
<script>
(function() {{
  var TOP_LABELS = {json.dumps(list(etiquetas) if top_n else [], ensure_ascii=False)};{top_js}
  var seasons = {json.dumps(seasons_payload)};
  var subtitles = {json.dumps(subtitles)};
  var baseAnnotations = {json.dumps(base_annotations)};
  var traceIndices = {json.dumps(trace_indices)};
  var leagueOrder = {json.dumps(league_order)};
  var extraTraces = {extra_traces};
  var BASE_SIZE = {base_size}, HIGHLIGHT_SIZE = {highlight_size};
  var current = {json.dumps(default_season)};

  var filterOn = false;
  var FILTER_KEY = {json.dumps((point_filter or {}).get("col", ""))};
  var FILTER_ESTADO = {json.dumps((point_filter or {}).get("estado", ""))};

  var catSel = {_ALL_JSON};
  var CAT_OPTIONS = {json.dumps((cat_filter or {}).get("options", []), ensure_ascii=False)};
  var CAT_CLAVE = {json.dumps((cat_filter or {}).get("clave", "cat"), ensure_ascii=False)};

  // La "vista" es lo que se está mostrando: la temporada elegida y, si hay
  // algún filtro por punto puesto, solo los que pasan. Se recalcula entera en
  // vez de guardarse precalculada desde Python por el mismo motivo que los
  // tamaños (ver _payload): duplicar x/y/custom pesa el doble — y con dos
  // filtros combinables serían seis juegos de arreglos, no dos.
  function computeView() {{
    var d = seasons[current];
    var usaFiltro = filterOn && !!d.f;
    var usaCat = catSel !== {_ALL_JSON} && !!d.g;
    if (!usaFiltro && !usaCat) return d;
    var cat = usaCat ? CAT_OPTIONS.indexOf(catSel) : -1;
    var v = {{names: [], x: [], y: [], ents: {{}}}};
    if (d.custom) v.custom = [];
    for (var t = 0; t < d.names.length; t++) {{
      var nn = [], xx = [], yy = [], cc = [];
      for (var i = 0; i < d.names[t].length; i++) {{
        if (usaFiltro && !d.f[t][i]) continue;
        if (usaCat && d.g[t][i] !== cat) continue;
        nn.push(d.names[t][i]); xx.push(d.x[t][i]); yy.push(d.y[t][i]);
        if (d.custom) cc.push(d.custom[t][i]);
        v.ents[d.names[t][i]] = d.ents[d.names[t][i]];
      }}
      v.names.push(nn); v.x.push(xx); v.y.push(yy);
      if (d.custom) v.custom.push(cc);
    }}
    return v;
  }}
  var V = computeView();

  function clubMap() {{ return V.ents; }}
  function traceNames() {{ return V.names; }}

  // Solo las trazas visibles: el filtro de liga esconde trazas enteras, así que
  // la lista tiene que preguntarle a la figura y no a los datos.
  function refreshTop() {{
    if (typeof pintarTop !== 'function') return;
    var lg = document.getElementById('{div_id}_league');
    var liga = lg ? lg.value : {_ALL_JSON};
    var nombres = [], xs = [], ys = [];
    for (var t = 0; t < V.names.length; t++) {{
      if (liga !== {_ALL_JSON} && leagueOrder[t] !== liga) continue;
      for (var i = 0; i < V.names[t].length; i++) {{
        nombres.push(V.names[t][i]); xs.push(V.x[t][i]); ys.push(V.y[t][i]);
      }}
    }}
    pintarTop(TOP_LABELS[0], TOP_LABELS[1], nombres, xs, ys);
  }}
{insight_js}
  // La caja de lectura depende de los DOS controles, así que se recalcula
  // desde el estado actual en vez de que cada handler arme su propia clave.
  function refreshInsight() {{
    if (typeof setInsight !== 'function') return;
    var lg = document.getElementById('{div_id}_league');
    var liga = lg ? lg.value : {_ALL_JSON};
    // Con un filtro puesto se pide OTRA clave, no la misma con una advertencia:
    // los textos de cada subconjunto vienen calculados aparte desde Python, así
    // que la caja describe siempre la población que se está viendo. El orden de
    // los segmentos es fijo (categoría antes que casilla) porque tiene que dar
    // exactamente la misma cadena que arma Python al generar las claves.
    var conCat = catSel !== {_ALL_JSON};
    var clave = current + '|' + liga + (conCat ? '|' + CAT_CLAVE + ':' + catSel : '')
                + (filterOn ? '|' + FILTER_KEY : '');
    var etiqueta = [current, liga === {_ALL_JSON} ? 'Todas las ligas' : liga,
                    conCat ? catSel : null, filterOn ? FILTER_ESTADO : null]
      .filter(Boolean).join(' · ');
    setInsight(clave, etiqueta);
  }}

  // Los tamaños se calculan acá y no vienen precalculados desde Python: uno
  // por entidad sería O(N²) (ver el comentario en sidebar_chart_html).
  // Resaltar por nombre, no por índice, mantiene el comportamiento anterior
  // en el caso de nombres repetidos (dos jugadores homónimos se resaltan los
  // dos, igual que antes).
  function sizesFor(name) {{
    return traceNames().map(function(names) {{
      return names.map(function(n) {{ return n === name ? HIGHLIGHT_SIZE : BASE_SIZE; }});
    }});
  }}
  function baseSizes() {{
    return traceNames().map(function(names) {{
      return names.map(function() {{ return BASE_SIZE; }});
    }});
  }}

  function updateLegendLayout() {{
    var w = document.getElementById('{div_id}').offsetWidth;
    if (w < 420) {{
      Plotly.relayout('{div_id}', {{'legend.orientation': 'h', 'legend.x': 0, 'legend.y': -0.46,
        'legend.yanchor': 'top', 'margin.r': 20, 'margin.t': 70, 'margin.b': 140}});
    }} else {{
      Plotly.relayout('{div_id}', {{'legend.orientation': 'v', 'legend.x': 1.02, 'legend.y': 1,
        'legend.yanchor': 'top', 'margin.r': 40, 'margin.t': 90, 'margin.b': 60}});
    }}
  }}
  window.addEventListener('resize', updateLegendLayout);
  updateLegendLayout();

  // La anotación de búsqueda se arma acá y no viene hecha desde Python
  // (guardar una por entidad pesa de más, ver el comentario en _payload) —
  // y de paso se pinta con el color del tema actual, que es lo que arregló
  // el bug de la anotación que se quedaba en negro sobre fondo oscuro. Se
  // vuelve a llamar cada vez que cambia el tema (listener de
  // 'futviz-theme-change' más abajo), no solo al tipear.
  function themedAnnotation(name, info) {{
    var dark = document.documentElement.getAttribute('data-theme') === 'dark';
    return {{
      x: info.x, y: info.y, text: name, showarrow: true, arrowhead: 2, ax: 0, ay: -32,
      arrowcolor: dark ? '#3A4A4E' : {json.dumps(INK["axis"])},
      font: {{size: 11, color: dark ? '#D7E4E7' : {json.dumps(INK["primary"])}}},
    }};
  }}

  function applySearch(val) {{
    var map = clubMap();
    if (map.hasOwnProperty(val)) {{
      Plotly.restyle('{div_id}', {{'marker.size': sizesFor(val)}}, traceIndices);
      Plotly.relayout('{div_id}', {{annotations: baseAnnotations.concat([themedAnnotation(val, map[val])])}});
    }} else if (val === '') {{
      Plotly.restyle('{div_id}', {{'marker.size': baseSizes()}}, traceIndices);
      Plotly.relayout('{div_id}', {{annotations: baseAnnotations}});
    }}
  }}

  // El datalist se llena desde JS y no desde el HTML porque las entidades
  // cambian con la temporada (un jugador puede no estar en otra, un club
  // puede haber estado en segunda).
  function fillDatalist() {{
    var names = Object.keys(clubMap()).sort();
    document.getElementById('{div_id}_clubs').innerHTML =
      names.map(function(n) {{ return '<option value="' + n.replace(/"/g, '&quot;') + '"></option>'; }}).join('');
  }}
  fillDatalist();

  document.getElementById('{div_id}_search').addEventListener('input', function(e) {{
    applySearch(e.target.value);
  }});
  document.addEventListener('futviz-theme-change', function() {{
    applySearch(document.getElementById('{div_id}_search').value);
  }});

  // Repinta las trazas con la vista actual. Lo llaman los dos controles que
  // cambian QUÉ puntos hay (temporada y filtro); el de liga no lo necesita,
  // porque ese solo cambia la visibilidad de trazas ya pintadas.
  function applyData() {{
    V = computeView();
    var update = {{x: V.x, y: V.y, 'marker.size': baseSizes()}};
    if (V.custom) update.customdata = V.custom;
    Plotly.restyle('{div_id}', update, traceIndices);
    fillDatalist();
    // Lo buscado puede no seguir en la vista nueva (otra temporada, o filtrado);
    // y aunque siga, sus coordenadas son otras, así que se re-aplica.
    var searchInput = document.getElementById('{div_id}_search');
    if (!clubMap().hasOwnProperty(searchInput.value)) searchInput.value = '';
    applySearch(searchInput.value);
    refreshInsight();
    refreshTop();
  }}

  var seasonSelect = document.getElementById('{div_id}_season');
  if (seasonSelect) {{
    seasonSelect.value = current;
    seasonSelect.addEventListener('change', function(e) {{
      current = e.target.value;
      if (subtitles[current]) {{
        Plotly.relayout('{div_id}', {{'title.subtitle.text': subtitles[current]}});
      }}
      applyData();
    }});
  }}

  var filterBox = document.getElementById('{div_id}_pfilter');
  if (filterBox) {{
    filterBox.checked = false;  // el navegador recuerda el estado al recargar
    filterBox.addEventListener('change', function(e) {{
      filterOn = e.target.checked;
      applyData();
    }});
  }}

  var catSelect = document.getElementById('{div_id}_cat');
  if (catSelect) {{
    catSelect.value = catSel;  // el navegador recuerda el estado al recargar
    catSelect.addEventListener('change', function(e) {{
      catSel = e.target.value;
      applyData();
    }});
  }}

  document.getElementById('{div_id}_league').addEventListener('change', function(e) {{
    var val = e.target.value;
    var vis = (val === {_ALL_JSON})
      ? leagueOrder.map(function() {{ return true; }})
      : leagueOrder.map(function(lg) {{ return lg === val; }});
    for (var i = 0; i < extraTraces; i++) vis.push(true);
    Plotly.restyle('{div_id}', {{visible: vis}});

    var searchInput = document.getElementById('{div_id}_search');
    var searched = clubMap()[searchInput.value];
    if (searched && val !== {_ALL_JSON} && searched.l !== val) {{
      searchInput.value = '';
      Plotly.restyle('{div_id}', {{'marker.size': baseSizes()}}, traceIndices);
      Plotly.relayout('{div_id}', {{annotations: baseAnnotations}});
    }}
    refreshInsight();
    refreshTop();
  }});

  refreshTop();
}})();
</script>
"""
    return _centrado(html, width)


def explorer_chart_html(season_data, variables, name_col="Squad", search_label="club",
                         entidad="equipos", default_x=None, default_y=None,
                         width=760, height=580, base_size=8, highlight_size=20,
                         team_col=None, point_filter=None, cat_filter=None,
                         fuente=None, top_n=5):
    """Scatter donde las dos variables las elige quien mira, no quien lo escribió.

    Es el tercer tipo de gráfico interactivo del sitio, y existe porque los
    otros dos no cubren este caso: `sidebar_chart_html` dibuja UN par de
    columnas fijo y `select_chart_html` cambia la figura con updates
    precalculados. Acá los pares posibles son N×N, o sea cientos, y
    precalcularlos sería absurdo — así que el payload lleva la **tabla** (todas
    las variables de todas las entidades, una sola vez) y el JS arma el par que
    se le pida. Termina pesando menos que un scatter fijo con la misma cantidad
    de puntos, porque no duplica nada por combinación.

    `variables` es la lista de `(columna, etiqueta, grupo, decimales)`, en el
    orden en que se listan en los dos desplegables; el grupo las junta en un
    `<optgroup>` ("Ataque", "Defensa", ...) y los decimales fijan tanto el
    redondeo del payload como el formato del hover.

    `season_data` es `{temporada: [(liga, sub_df), ...]}`, la misma estructura
    que espera `sidebar_chart_html`; `point_filter` el mismo dict de la casilla
    de filtro por punto (sub-21) y `cat_filter` el del desplegable de filtro
    categórico (posición). Acá no hay claves de caja de lectura que armar —el
    texto se calcula en el navegador— así que de `cat_filter` solo se usan
    `col`, `label`, `options`, `all_label` y `hint`.

    La caja de lectura NO lleva "qué mirar": el texto de un gráfico que cambia
    de variables no se puede escribir de antemano. Lo que lleva es el r² del par
    que se está viendo, **calculado en el navegador sobre los mismos arreglos
    que Plotly tiene dibujados** — que es la versión fuerte de la regla de
    `insights.py`: acá el texto no puede contradecir al gráfico ni siquiera en
    principio.
    """
    import json

    import plotly.graph_objects as go
    import plotly.io as pio

    cols = [c for c, _, _, _ in variables]
    etiquetas = {c: e for c, e, _, _ in variables}
    decimales = {c: d for c, _, _, d in variables}

    # Grupos del <optgroup>, en el orden en que aparecen en la lista.
    grupos = []
    for c, _, g, _ in variables:
        if not grupos or grupos[-1][0] != g:
            grupos.append((g, []))
        grupos[-1][1].append(c)

    x0 = default_x or cols[0]
    y0 = default_y or cols[1]
    seasons = list(season_data)
    default_season = seasons[-1]
    league_order = [liga for liga, _ in season_data[default_season]]

    def _valores(sub, col):
        """La columna redondeada a como se va a mostrar, con los nulos como
        `null`: los deja fuera del cálculo del r² y Plotly no los dibuja."""
        d = decimales[col]
        return [None if v != v else round(float(v), d) for v in sub[col]]

    def _payload(sd):
        p = {"n": [sub[name_col].astype(str).tolist() for _, sub in sd],
             "v": {c: [_valores(sub, c) for _, sub in sd] for c in cols}}
        if team_col:
            p["c"] = [sub[team_col].astype(str).tolist() for _, sub in sd]
        if point_filter:
            p["f"] = [sub[point_filter["col"]].fillna(False).astype(bool).tolist()
                      for _, sub in sd]
        if cat_filter:
            # Índice de la categoría, no su nombre (-1 = sin dato); mismo
            # criterio de peso que en `sidebar_chart_html`.
            codigo = {v: i for i, v in enumerate(cat_filter["options"])}
            p["g"] = [[codigo.get(v, -1) for v in sub[cat_filter["col"]]]
                       for _, sub in sd]
        return p

    datos = {s: _payload(sd) for s, sd in season_data.items()}

    # Rango de cada eje sobre TODAS las temporadas, no sobre la que se muestra:
    # misma regla que en los otros scatter — cambiar de temporada mueve los
    # puntos, no la escala. Acá además hace que cambiar de variable y volver
    # deje el gráfico exactamente como estaba.
    rangos = {}
    for c in cols:
        vals = [v for s in seasons for tr in datos[s]["v"][c] for v in tr if v is not None]
        lo, hi = (min(vals), max(vals)) if vals else (0.0, 1.0)
        pad = (hi - lo) * 0.06 or (abs(hi) * 0.06 or 1.0)
        rangos[c] = [lo - pad, hi + pad]

    fig = go.Figure()
    for liga, sub in season_data[default_season]:
        fig.add_trace(go.Scatter(
            x=_valores(sub, x0), y=_valores(sub, y0), mode="markers", name=liga,
            marker=dict(color=league_color(liga), size=base_size, opacity=0.75,
                        line=dict(width=0.5, color="white")),
        ))
    fig.update_layout(
        title=dict(text="Crea tu gráfico",
                   subtitle=dict(text=f"{etiquetas[y0]} vs. {etiquetas[x0]} · {default_season}")),
        xaxis=dict(title=etiquetas[x0], range=rangos[x0]),
        yaxis=dict(title=etiquetas[y0], range=rangos[y0]),
    )

    div_id = _div_id(fig, cols, name_col, sorted(season_data))
    fig.update_layout(autosize=True)
    grafico = pio.to_html(
        fig, full_html=False, include_plotlyjs="cdn", div_id=div_id,
        config={"displaylogo": False, "responsive": True, "displayModeBar": False},
        default_width="100%", default_height="100%")

    def _opciones(elegida):
        partes = []
        for grupo, columnas in grupos:
            interior = "".join(
                f'<option value="{c}"{" selected" if c == elegida else ""}>{etiquetas[c]}</option>'
                for c in columnas)
            partes.append(f'<optgroup label="{grupo}">{interior}</optgroup>' if grupo else interior)
        return "".join(partes)

    season_options = "".join(f'<option value="{s}">{s}</option>' for s in seasons)
    league_options = "".join(f'<option value="{lg}">{lg}</option>' for lg in league_order)
    filter_block = "" if not point_filter else f"""
    <div class="block">{_rotulo(point_filter)}
      <div class="toggle">
        <input type="checkbox" id="{div_id}_pfilter">
        <label for="{div_id}_pfilter" style="display:inline; text-transform:none;
          letter-spacing:0; margin:0;"><span>{point_filter.get("text", "Filtrar")}</span></label>
      </div>
      {f'<p class="hint">{point_filter["hint"]}</p>' if point_filter.get("hint") else ''}
    </div>"""

    cat_options = "" if not cat_filter else "".join(
        f'<option value="{o}">{o}</option>' for o in cat_filter["options"])
    cat_block = "" if not cat_filter else f"""
    <div class="block">{_rotulo(cat_filter, "Categoría")}
      <select id="{div_id}_cat">
        <option value="{_ALL}">{cat_filter.get("all_label", "Todas")}</option>
        {cat_options}
      </select>
      {f'<p class="hint">{cat_filter["hint"]}</p>' if cat_filter.get("hint") else ''}
    </div>"""

    ojo = _md_inline(
        "El r² mide **relación lineal, y nada más**. Dos variables pueden tener un r² "
        "bajo y estar bien relacionadas de otra forma (en U, por ejemplo), y un r² alto "
        "no dice cuál causa cuál: puede haber una tercera cosa moviendo a las dos.\n\n"
        "Ojo también con los pares que comparten aritmética. Un total y su tasa por 90' "
        "(goles y goles por 90'), o una parte y su todo (goles y goles + asistencias), "
        "van a dar un r² altísimo porque contienen literalmente el mismo dato — eso no "
        "es un hallazgo, es la definición.\n\n"
        "Y el r² depende de la población: con el filtro de liga puesto se calcula sobre "
        "veinte y pico de puntos, donde salta mucho de una temporada a otra."
    )

    top_css = _toplist_css(div_id, width) if top_n else ""
    top_html = _toplist_html(div_id, top_n) if top_n else ""
    top_js = _toplist_js(div_id, top_n) if top_n else ""

    return _centrado(f"""
<style>{_sidebar_css(div_id, width, width / height)}{_insight_css(div_id, width)}{top_css}
</style>""" + f"""
<div id="{div_id}_layout">
  <div id="{div_id}_plotwrap">{grafico}</div>
  <div id="{div_id}_sidebar">
    <div class="block">
      <label>Eje horizontal</label>
      <select id="{div_id}_xvar">{_opciones(x0)}</select>
    </div>
    <div class="block">
      <label>Eje vertical</label>
      <select id="{div_id}_yvar">{_opciones(y0)}</select>
    </div>
    <div class="block">
      <label>Temporada</label>
      <select id="{div_id}_season">{season_options}</select>
    </div>
    <div class="block">
      <label>Filtrar por liga</label>
      <select id="{div_id}_league">
        <option value="{_ALL}">Todas las ligas</option>
        {league_options}
      </select>
    </div>{cat_block}
    <div class="block">
      <label>Buscar {search_label}</label>
      <input list="{div_id}_names" id="{div_id}_search" placeholder="Escribe un {search_label}…" autocomplete="off">
      <datalist id="{div_id}_names"></datalist>
    </div>{filter_block}
  </div>
</div>{_fuente_html(div_id, width, fuente)}
<div id="{div_id}_below">
<div id="{div_id}_insight">
  <div class="fv-dyn">
    <h4>En lo que estás viendo · <span class="fv-estado" id="{div_id}_ins_estado"></span></h4>
    <p id="{div_id}_ins_fija"></p>
    <p class="fv-salta" id="{div_id}_ins_salta"></p>
  </div>
  <details>
    <summary>Qué no dice el r²</summary>
    <div>{ojo}</div>
  </details>
</div>{top_html}
</div>
<script>
(function() {{{top_js}
  var DATOS = {json.dumps(datos, ensure_ascii=False)};
  var RANGOS = {json.dumps(rangos)};
  var ETIQUETAS = {json.dumps(etiquetas, ensure_ascii=False)};
  var DECIMALES = {json.dumps(decimales)};
  var LIGAS = {json.dumps(league_order, ensure_ascii=False)};
  var TRAZAS = {json.dumps(list(range(len(league_order))))};
  var ENTIDAD = {json.dumps(entidad, ensure_ascii=False)};
  var TODAS = {json.dumps(_ALL)};
  var BASE = {base_size}, RESALTE = {highlight_size};
  var CON_EQUIPO = {json.dumps(bool(team_col))};
  var FILTRO_ESTADO = {json.dumps((point_filter or {}).get("estado", ""), ensure_ascii=False)};
  var CAT_OPCIONES = {json.dumps((cat_filter or {}).get("options", []), ensure_ascii=False)};

  var temporada = {json.dumps(default_season)};
  var filtroOn = false;
  var categoria = TODAS;
  var IDX = [], NOMBRES = [], XS = [], YS = [];

  function el(sufijo) {{ return document.getElementById('{div_id}_' + sufijo); }}
  function ejeX() {{ return el('xvar').value; }}
  function ejeY() {{ return el('yvar').value; }}

  // Los filtros por punto se resuelven una vez como lista de índices y las
  // columnas se leen a través de ella: filtrar las N variables cada vez que se
  // toca un control sería tirar trabajo, porque solo dos están en pantalla.
  function recalcularIndices() {{
    var d = DATOS[temporada];
    var usaCat = categoria !== TODAS && !!d.g;
    var cat = usaCat ? CAT_OPCIONES.indexOf(categoria) : -1;
    IDX = d.n.map(function(nombres, t) {{
      var idx = [];
      for (var i = 0; i < nombres.length; i++) {{
        if (filtroOn && d.f && !d.f[t][i]) continue;
        if (usaCat && d.g[t][i] !== cat) continue;
        idx.push(i);
      }}
      return idx;
    }});
    NOMBRES = d.n.map(function(nombres, t) {{
      return IDX[t].map(function(i) {{ return nombres[i]; }});
    }});
  }}
  function columna(c) {{
    var v = DATOS[temporada].v[c];
    return IDX.map(function(idx, t) {{ return idx.map(function(i) {{ return v[t][i]; }}); }});
  }}
  function equipos() {{
    var c = DATOS[temporada].c;
    if (!c) return null;
    return IDX.map(function(idx, t) {{ return idx.map(function(i) {{ return c[t][i]; }}); }});
  }}
  function tamanos(nombre) {{
    return NOMBRES.map(function(nn) {{
      return nn.map(function(n) {{ return n === nombre ? RESALTE : BASE; }});
    }});
  }}

  // --- r² sobre lo que se está viendo ---------------------------------------
  // Solo las trazas visibles (filtro de liga) y solo los puntos que tienen las
  // dos variables: un nulo en cualquiera de las dos deja el par afuera.
  function paresVisibles() {{
    var liga = el('league').value, xs = [], ys = [];
    XS.forEach(function(arr, t) {{
      if (liga !== TODAS && LIGAS[t] !== liga) return;
      for (var i = 0; i < arr.length; i++) {{
        var a = arr[i], b = YS[t][i];
        if (a === null || b === null) continue;
        xs.push(a); ys.push(b);
      }}
    }});
    return [xs, ys];
  }}

  // Para el top 5 no se piden pares completos como para el r²: un punto con la
  // variable X presente y la Y nula tiene que seguir contando en la lista de X.
  function puntosVisibles() {{
    var liga = el('league').value, nombres = [], xs = [], ys = [];
    NOMBRES.forEach(function(nn, t) {{
      if (liga !== TODAS && LIGAS[t] !== liga) return;
      for (var i = 0; i < nn.length; i++) {{
        nombres.push(nn[i]); xs.push(XS[t][i]); ys.push(YS[t][i]);
      }}
    }});
    return [nombres, xs, ys];
  }}
  function refreshTop() {{
    if (typeof pintarTop !== 'function') return;
    var p = puntosVisibles();
    pintarTop(ETIQUETAS[ejeX()], ETIQUETAS[ejeY()], p[0], p[1], p[2]);
  }}
  // Devuelve el r, o por qué no hay r: 'pocos' (no alcanzan los puntos) y
  // 'plano' (alguno de los dos ejes no varía) se distinguen porque son cosas
  // distintas y el aviso tiene que decir cuál es — con el filtro de categoría
  // 'plano' es fácil de encontrar (porteros contra tiros, por ejemplo).
  function pearson(xs, ys) {{
    var n = xs.length, i;
    if (n < 3) return 'pocos';
    var mx = 0, my = 0;
    for (i = 0; i < n; i++) {{ mx += xs[i]; my += ys[i]; }}
    mx /= n; my /= n;
    var sxy = 0, sxx = 0, syy = 0;
    for (i = 0; i < n; i++) {{
      var dx = xs[i] - mx, dy = ys[i] - my;
      sxy += dx * dy; sxx += dx * dx; syy += dy * dy;
    }}
    if (sxx === 0 || syy === 0) return 'plano';
    return sxy / Math.sqrt(sxx * syy);
  }}
  function banda(r) {{
    var a = Math.abs(r);
    if (a < 0.3) return 'Casi no se pisan: cada una mide algo que la otra no capta, ' +
                        'así que el gráfico está comparando dos cosas de verdad distintas.';
    if (a < 0.6) return 'Se pisan a medias: hay tendencia, pero queda mucha variación ' +
                        'que una no explica de la otra.';
    if (a < 0.85) return 'Se pisan bastante: saber una ya dice buena parte de la otra.';
    return 'Son casi la misma información: una se puede predecir desde la otra, y ' +
           'ponerlas en ejes distintos no agrega nada.';
  }}

  function actualizarTexto() {{
    var liga = el('league').value;
    el('ins_estado').textContent =
      [temporada, liga === TODAS ? 'Todas las ligas' : liga,
       categoria !== TODAS ? categoria : null,
       filtroOn ? FILTRO_ESTADO : null].filter(Boolean).join(' · ');

    var p = paresVisibles(), r = pearson(p[0], p[1]);
    var ex = ETIQUETAS[ejeX()], ey = ETIQUETAS[ejeY()];
    if (typeof r === 'string') {{
      el('ins_fija').innerHTML = r === 'plano'
        ? 'Con estos filtros, <strong>' + ex + '</strong> o <strong>' + ey + '</strong> vale ' +
          'lo mismo en los ' + p[0].length + ' ' + ENTIDAD + ' que quedan: sin variación en ' +
          'uno de los dos ejes no hay relación que medir.'
        : 'No hay puntos suficientes para medir la relación entre <strong>' + ex +
          '</strong> y <strong>' + ey + '</strong> con estos filtros.';
      el('ins_salta').style.display = 'none';
      return;
    }}
    el('ins_fija').innerHTML =
      '<strong>r² = ' + (r * r * 100).toFixed(0) + '%</strong> entre <strong>' + ex +
      '</strong> y <strong>' + ey + '</strong> (r = ' + (r >= 0 ? '+' : '−') +
      Math.abs(r).toFixed(2) + '), sobre ' + p[0].length + ' ' + ENTIDAD + '.';
    el('ins_salta').innerHTML = banda(r) + ' El r² es la parte de la variación de una que ' +
      'queda explicada por la otra: <strong>cuanto más chico, más distintas son</strong>. ' +
      (r >= 0 ? 'El signo es positivo: suben juntas.'
              : 'El signo es negativo: cuando una sube, la otra baja.');
    el('ins_salta').style.display = '';
  }}

  // --- dibujo ---------------------------------------------------------------
  function hoverTemplate() {{
    var cx = ejeX(), cy = ejeY();
    var quien = CON_EQUIPO ? '<b>%{{customdata[0]}}</b> (%{{customdata[1]}})'
                            : '<b>%{{customdata}}</b>';
    return quien + '<br>' + ETIQUETAS[cx] + ': %{{x:.' + DECIMALES[cx] + 'f}}' +
           '<br>' + ETIQUETAS[cy] + ': %{{y:.' + DECIMALES[cy] + 'f}}<extra></extra>';
  }}

  function llenarDatalist() {{
    var todos = [];
    NOMBRES.forEach(function(nn) {{ todos = todos.concat(nn); }});
    todos.sort();
    el('names').innerHTML = todos.map(function(n) {{
      return '<option value="' + n.replace(/"/g, '&quot;') + '"></option>';
    }}).join('');
  }}

  function anotacion(nombre) {{
    for (var t = 0; t < NOMBRES.length; t++) {{
      var i = NOMBRES[t].indexOf(nombre);
      if (i === -1 || XS[t][i] === null || YS[t][i] === null) continue;
      var oscuro = document.documentElement.getAttribute('data-theme') === 'dark';
      return {{
        x: XS[t][i], y: YS[t][i], text: nombre, showarrow: true, arrowhead: 2, ax: 0, ay: -32,
        arrowcolor: oscuro ? '#3A4A4E' : {json.dumps(INK["axis"])},
        font: {{size: 11, color: oscuro ? '#D7E4E7' : {json.dumps(INK["primary"])}}}
      }};
    }}
    return null;
  }}

  function aplicarBusqueda(valor) {{
    var an = valor ? anotacion(valor) : null;
    Plotly.restyle('{div_id}', {{'marker.size': tamanos(an ? valor : null)}}, TRAZAS);
    Plotly.relayout('{div_id}', {{annotations: an ? [an] : []}});
  }}

  function redibujar() {{
    recalcularIndices();
    XS = columna(ejeX()); YS = columna(ejeY());
    var eq = equipos();
    Plotly.restyle('{div_id}', {{
      x: XS, y: YS, 'marker.size': tamanos(null),
      hovertemplate: TRAZAS.map(hoverTemplate),
      customdata: CON_EQUIPO
        ? NOMBRES.map(function(nn, t) {{ return nn.map(function(n, i) {{ return [n, eq[t][i]]; }}); }})
        : NOMBRES
    }}, TRAZAS);
    Plotly.relayout('{div_id}', {{
      'xaxis.title.text': ETIQUETAS[ejeX()], 'yaxis.title.text': ETIQUETAS[ejeY()],
      'xaxis.range': RANGOS[ejeX()], 'yaxis.range': RANGOS[ejeY()],
      'title.subtitle.text': ETIQUETAS[ejeY()] + ' vs. ' + ETIQUETAS[ejeX()] + ' · ' + temporada
    }});
    llenarDatalist();
    var buscador = el('search');
    var sigue = NOMBRES.some(function(nn) {{ return nn.indexOf(buscador.value) !== -1; }});
    if (!sigue) buscador.value = '';
    aplicarBusqueda(buscador.value);
    actualizarTexto();
    refreshTop();
  }}

  function acomodarLeyenda() {{
    var w = document.getElementById('{div_id}').offsetWidth;
    if (w < 420) {{
      Plotly.relayout('{div_id}', {{'legend.orientation': 'h', 'legend.x': 0, 'legend.y': -0.46,
        'legend.yanchor': 'top', 'margin.r': 20, 'margin.t': 70, 'margin.b': 140}});
    }} else {{
      Plotly.relayout('{div_id}', {{'legend.orientation': 'v', 'legend.x': 1.02, 'legend.y': 1,
        'legend.yanchor': 'top', 'margin.r': 40, 'margin.t': 90, 'margin.b': 60}});
    }}
  }}

  el('xvar').addEventListener('change', redibujar);
  el('yvar').addEventListener('change', redibujar);
  el('season').addEventListener('change', function(e) {{ temporada = e.target.value; redibujar(); }});
  el('search').addEventListener('input', function(e) {{ aplicarBusqueda(e.target.value); }});
  el('league').addEventListener('change', function(e) {{
    var v = e.target.value;
    Plotly.restyle('{div_id}', {{visible: LIGAS.map(function(lg) {{
      return v === TODAS || lg === v;
    }})}}, TRAZAS);
    // Lo buscado puede haber quedado en una liga que ya no se muestra.
    var buscador = el('search');
    if (buscador.value && v !== TODAS) {{
      var t = -1;
      NOMBRES.forEach(function(nn, i) {{ if (t === -1 && nn.indexOf(buscador.value) !== -1) t = i; }});
      if (t !== -1 && LIGAS[t] !== v) {{ buscador.value = ''; aplicarBusqueda(''); }}
    }}
    actualizarTexto();
    refreshTop();
  }});
  var casilla = el('pfilter');
  if (casilla) {{
    casilla.checked = false;   // el navegador recuerda el estado al recargar
    casilla.addEventListener('change', function(e) {{ filtroOn = e.target.checked; redibujar(); }});
  }}
  var selectorCat = el('cat');
  if (selectorCat) {{
    selectorCat.value = categoria;   // ídem
    selectorCat.addEventListener('change', function(e) {{ categoria = e.target.value; redibujar(); }});
  }}
  document.addEventListener('futviz-theme-change', function() {{
    aplicarBusqueda(el('search').value);
  }});
  window.addEventListener('resize', acomodarLeyenda);

  el('season').value = temporada;
  acomodarLeyenda();
  redibujar();
}})();
</script>
""", width)


def render_explorer_chart(*args, **kwargs):
    """Muestra en el notebook el resultado de `explorer_chart_html(...)`."""
    from IPython.display import HTML, display

    display(HTML(explorer_chart_html(*args, **kwargs)))


def render_with_sidebar(fig, *args, **kwargs):
    """Muestra en el notebook el resultado de `sidebar_chart_html(fig, ...)`.
    Mismos argumentos que esa función."""
    from IPython.display import HTML, display

    display(HTML(sidebar_chart_html(fig, *args, **kwargs)))


def plot_html(fig, width=680, height=480, fuente=None):
    """Igual que la parte de gráfico de sidebar_chart_html pero sin barra
    lateral — para gráficos donde las 5 ligas ya están comparadas una al
    lado de la otra (ej. un box plot por liga) y no hace falta filtrar.
    Responsivo con el mismo criterio (contenedor con relación de aspecto
    fija en vez de tamaño en px). Devuelve el HTML como string; ver
    `render_plot` para mostrarlo directo en un notebook."""
    import plotly.io as pio

    div_id = _div_id(fig)
    fig.update_layout(autosize=True)
    inner = pio.to_html(fig, full_html=False, include_plotlyjs="cdn",
                         div_id=div_id, config={"displaylogo": False, "responsive": True, "displayModeBar": False},
                         default_width="100%", default_height="100%")
    aspect_ratio = width / height
    return f"""
<style>
  #{div_id}_wrap {{ position: relative; width: 100%; max-width: {width}px;
    aspect-ratio: {aspect_ratio}; }}
  #{div_id}_wrap > div {{ position: absolute; inset: 0; }}
  @media (max-width: 520px) {{
    #{div_id}_wrap {{ aspect-ratio: {max(aspect_ratio * 0.85, 1.0)}; }}
  }}
</style>
<div id="{div_id}_wrap">{inner}</div>{_fuente_html(div_id, width, fuente)}
<script>
(function() {{
  function updateLegendLayout() {{
    var w = document.getElementById('{div_id}').offsetWidth;
    if (w < 420) {{
      Plotly.relayout('{div_id}', {{'margin.r': 20, 'margin.t': 70}});
    }} else {{
      Plotly.relayout('{div_id}', {{'margin.r': 40, 'margin.t': 90}});
    }}
  }}
  window.addEventListener('resize', updateLegendLayout);
  updateLegendLayout();
}})();
</script>
"""


def render_plot(fig, width=680, height=480):
    """Muestra en el notebook el resultado de `plot_html(fig, ...)`."""
    from IPython.display import HTML, display

    display(HTML(plot_html(fig, width=width, height=height)))


def league_box_figure(df, y_col, y_axis_title, hover_fmt=".1f", annotate_cv=False, name_col="Squad"):
    """Box plot + puntos (un punto = un equipo o jugador, con hover) por
    liga, en el orden fijo de LEAGUE_ORDER. Pensado para propiedades de LA
    LIGA como sistema (paridad, edad de plantilla, disciplina, nivel
    ofensivo) — no el perfil de una entidad puntual, por eso no lleva
    buscador ni filtro: las 5 ligas ya están una al lado de la otra para
    compararlas directamente.

    `name_col` es la columna que identifica cada punto en el hover ("Squad"
    para equipos, "player" para jugadores).

    `annotate_cv=True` agrega el coeficiente de variación (std/mean, %) de
    cada liga como anotación arriba de su caja — útil para paridad
    competitiva, donde la dispersión ES el hallazgo."""
    import plotly.graph_objects as go

    fig = go.Figure()
    for liga in LEAGUE_ORDER:
        sub = df[df["liga"] == liga]
        color = league_color(liga)
        fig.add_trace(go.Box(
            y=sub[y_col], x=[liga] * len(sub), name=liga,
            boxpoints="all", jitter=0.5, pointpos=0,
            marker=dict(color=color, size=6, opacity=0.7),
            line=dict(color=color), fillcolor="rgba(0,0,0,0)",
            customdata=sub[name_col],
            hovertemplate="<b>%{customdata}</b><br>" + y_axis_title + (": %{y:" + hover_fmt + "}<extra></extra>"),
            showlegend=False,
        ))
    if annotate_cv:
        for ann in _cv_annotations(df, y_col, name_col):
            fig.add_annotation(**ann)
    return fig


def _cv_annotations(df, y_col, name_col="Squad", y_at=None):
    """Coeficiente de variación de cada liga, como anotación sobre su caja."""
    ymax, ymin = df[y_col].max(), df[y_col].min()
    y_pos = ymax + (ymax - ymin) * 0.06 if y_at is None else y_at
    anns = []
    for liga in LEAGUE_ORDER:
        sub = df[df["liga"] == liga]
        cv = sub[y_col].std() / sub[y_col].mean() * 100
        anns.append(dict(x=liga, y=y_pos, text=f"{cv:.0f}%", showarrow=False,
                          font=dict(size=11, color=INK["secondary"])))
    return anns


def league_box_season_html(df, y_col, y_axis_title, seasons, hover_fmt=".1f",
                            annotate_cv=False, name_col="Squad", subtitle_template=None,
                            width=800, height=520, season_col="temporada",
                            cat_filter=None):
    """Box plot por liga con selector de temporada.

    El eje Y se fija con el rango de LAS 5 temporadas y no con el de cada una:
    si se reescalara en cada cambio, dos cajas del mismo alto significarían
    dispersiones distintas y el gráfico mentiría justo en lo que se quiere
    comparar. Por lo mismo las anotaciones de CV se recalculan pero se dibujan
    siempre a la misma altura. Y por lo mismo el rango tampoco depende de
    `cat_filter`: si al elegir "Delantero" la escala se ajustara, la caja de
    los delanteros se vería igual de alta que la de los defensas.

    `cat_filter` agrega un segundo desplegable que filtra por una columna
    categórica (`{"col", "label", "options", "all_label", "clave"}`, el mismo
    dict que reciben los otros helpers). Cuando está, los dos controles no
    pueden actualizar el gráfico por separado —los dos cambian la misma `y`,
    así que se pisarían— y lo que se devuelve son `joint_updates`, una entrada
    por combinación, que es el mecanismo que `select_chart_html` ya tiene para
    ese caso.

    Devuelve `(fig, controls, joint_updates)`, con `joint_updates` en None
    cuando no hay `cat_filter`."""
    default = seasons[-1]
    todas = cat_filter.get("all_label", "Todas") if cat_filter else None
    cat_options = [_ALL] + list(cat_filter["options"]) if cat_filter else [None]

    sub_default = df[df[season_col] == default]
    fig = league_box_figure(sub_default, y_col, y_axis_title, hover_fmt=hover_fmt,
                             name_col=name_col)

    lo, hi = df[y_col].min(), df[y_col].max()
    pad = (hi - lo) * 0.10
    cv_y = hi + pad * 0.55
    fig.update_yaxes(range=[lo - pad, hi + pad * 1.25])
    if annotate_cv:
        fig.update_layout(annotations=_cv_annotations(sub_default, y_col, name_col, y_at=cv_y))

    def _update(d, s):
        parts = [d[d["liga"] == liga] for liga in LEAGUE_ORDER]
        upd = {
            "restyle": {
                "y": [p[y_col].tolist() for p in parts],
                "x": [[liga] * len(p) for liga, p in zip(LEAGUE_ORDER, parts)],
                "customdata": [p[name_col].tolist() for p in parts],
            }
        }
        relayout = {}
        if subtitle_template:
            relayout["title.subtitle.text"] = subtitle_template.format(temporada=s)
        if annotate_cv:
            relayout["annotations"] = _cv_annotations(d, y_col, name_col, y_at=cv_y)
        if relayout:
            upd["relayout"] = relayout
        return upd

    season_control = {"id": "season", "label": "Temporada", "options": list(seasons),
                       "default": default}
    if not cat_filter:
        season_control["updates"] = {s: _update(df[df[season_col] == s], s)
                                      for s in seasons}
        return fig, [season_control], None

    joint = {}
    for s in seasons:
        d = df[df[season_col] == s]
        for cat in cat_options:
            sub = d if cat == _ALL else d[d[cat_filter["col"]] == cat]
            joint[f"{s}|{cat}"] = _update(sub, s)

    cat_control = {"id": cat_filter.get("clave", "cat"),
                    "label": cat_filter.get("label", "Categoría"),
                    "options": cat_options, "default": _ALL,
                    "labels": {_ALL: todas}}
    return fig, [season_control, cat_control], joint
