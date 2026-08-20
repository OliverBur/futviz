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


def _sidebar_css(div_id, width, aspect_ratio):
    """Estilos de la barra lateral de controles (gráfico a la izquierda,
    controles en una columna aparte a la derecha, nunca superpuestos).

    Compartido por `sidebar_chart_html` (buscador + filtros) y
    `select_chart_html` (solo desplegables), para que los dos tipos de
    gráfico interactivo del sitio se vean exactamente igual."""
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
  #{div_id}_sidebar input, #{div_id}_sidebar select {{ width: 100%; box-sizing: border-box;
    padding: 7px 9px; font-size: 13px; font-family: inherit; color: var(--color-primary, {INK["primary"]});
    background: var(--color-surface, {INK["surface"]}); border: 1px solid var(--color-border, {INK["axis"]});
    border-radius: 6px; transition: border-color .15s ease; }}
  #{div_id}_sidebar input:focus, #{div_id}_sidebar select:focus {{
    outline: none; border-color: var(--color-interactive, {INK["axis"]}); }}
  @media (max-width: 520px) {{
    #{div_id}_sidebar {{ padding-top: 4px; max-width: 100%; }}
    #{div_id}_plotwrap {{ aspect-ratio: {max(aspect_ratio * 0.6, 0.85)}; }}
  }}"""


def select_chart_html(fig, controls, width=760, height=560, hint=None, min_width=None,
                       insights=None, insight_control=None):
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

    `min_width` fuerza un ancho mínimo del gráfico en px: para figuras que no
    se pueden achicar sin volverse ilegibles (el radar de 5 subplots), es
    preferible que el contenedor `.chart-scroll` de la página scrollee en
    horizontal a que el gráfico se comprima — mismo criterio que ya se usó
    con las imágenes de matplotlib.

    Devuelve el HTML como string."""
    import json
    import plotly.io as pio

    div_id = _div_id(fig, controls)
    fig.update_layout(autosize=True)
    plot_html = pio.to_html(fig, full_html=False, include_plotlyjs="cdn",
                             div_id=div_id, config={"displaylogo": False, "responsive": True, "displayModeBar": False},
                             default_width="100%", default_height="100%")

    blocks, specs = [], []
    for c in controls:
        opts = "".join(f'<option value="{o}">{c.get("labels", {}).get(o, o)}</option>' for o in c["options"])
        blocks.append(f"""
    <div class="block">
      <label>{c["label"]}</label>
      <select id="{div_id}_{c["id"]}">{opts}</select>
    </div>""")
        specs.append({"id": c["id"], "default": c.get("default", c["options"][0]),
                       "updates": c["updates"], "labels": c.get("labels", {})})
    if hint:
        blocks.append(f'\n    <div class="block"><div class="hint">{hint}</div></div>')

    min_width_css = (f"\n  #{div_id}_plotwrap {{ min-width: {min_width}px; }}"
                     if min_width else "")

    # La caja de lectura la maneja el control que se indique (por defecto el
    # primero): en el radar es la temporada, en el de evolución la métrica.
    driver = insight_control or (controls[0]["id"] if controls else None)
    insight_css = insight_box = insight_js = insight_hook = ""
    if insights:
        ctrl = next(c for c in controls if c["id"] == driver)
        key0 = ctrl.get("default", ctrl["options"][0])
        insight_css = _insight_css(div_id, width)
        insight_box = _insight_html(div_id, insights, key0,
                                     ctrl.get("labels", {}).get(key0, key0))
        insight_js = _insight_js(div_id, insights)
        # El rótulo del estado es la etiqueta legible del control, no su valor:
        # en el de evolución el valor es un nombre de columna (`p90_Fls`).
        insight_hook = f"""
      if (spec.id === {json.dumps(driver)}) {{
        setInsight(e.target.value, spec.labels[e.target.value] || e.target.value);
      }}"""

    html = f"""
<style>{_sidebar_css(div_id, width, width / height)}{min_width_css}{insight_css}
</style>
<div id="{div_id}_layout">
  <div id="{div_id}_plotwrap">{plot_html}</div>
  <div id="{div_id}_sidebar">{"".join(blocks)}
  </div>
</div>{insight_box}
<script>
(function() {{
  var specs = {json.dumps(specs)};{insight_js}
  specs.forEach(function(spec) {{
    var el = document.getElementById('{div_id}_' + spec.id);
    el.value = spec.default;
    el.addEventListener('change', function(e) {{
      var u = spec.updates[e.target.value];{insight_hook}
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
    }});
  }});
}})();
</script>
"""
    return html


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
                        insights=None, point_filter=None):
    """Arma el HTML/JS de un gráfico Plotly con una barra lateral genuina a
    la derecha (no superpuesta, es un elemento aparte en un layout flex):
    - `<select>` de temporada (solo si se pasa `season_data`).
    - Buscador con autocompletado NATIVO del navegador (`<input list>` +
      `<datalist>`) sobre `name_col` (ej. "Squad" para equipos, "player"
      para jugadores) — escribes unas letras y aparecen las opciones que
      matchean, sin necesidad de Dash ni de un menú con cientos de opciones.
    - `<select>` para filtrar por liga.
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
    <div class="block">
      <label>{point_filter.get("label", "Filtrar")}</label>
      <div class="toggle">
        <input type="checkbox" id="{div_id}_pfilter">
        <label for="{div_id}_pfilter" style="display:inline; text-transform:none;
          letter-spacing:0; margin:0;"><span>{point_filter.get("text", "Filtrar")}</span></label>
      </div>
      {f'<p class="hint">{point_filter["hint"]}</p>' if point_filter.get("hint") else ''}
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

    html = f"""
<style>{_sidebar_css(div_id, width, aspect_ratio)}{insight_css}
</style>
<div id="{div_id}_layout">
  <div id="{div_id}_plotwrap">{plot_html}</div>
  <div id="{div_id}_sidebar">{season_block}
    <div class="block">
      <label>Buscar {search_label}</label>
      <input list="{div_id}_clubs" id="{div_id}_search" placeholder="Escribe un {search_label}…" autocomplete="off">
      <datalist id="{div_id}_clubs"></datalist>
    </div>
    <div class="block">
      <label>Filtrar por liga</label>
      <select id="{div_id}_league">
        <option value="{_ALL}">Todas las ligas</option>
        {league_options}
      </select>
    </div>{filter_block}
  </div>
</div>{insight_box}
<script>
(function() {{
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

  // La "vista" es lo que se está mostrando: la temporada elegida y, si la
  // casilla está marcada, solo los puntos que pasan el filtro. Se recalcula
  // entera en vez de guardarse precalculada desde Python por el mismo motivo
  // que los tamaños (ver _payload): duplicar x/y/custom pesa el doble.
  function computeView() {{
    var d = seasons[current];
    if (!filterOn || !d.f) return d;
    var v = {{names: [], x: [], y: [], ents: {{}}}};
    if (d.custom) v.custom = [];
    for (var t = 0; t < d.names.length; t++) {{
      var nn = [], xx = [], yy = [], cc = [];
      for (var i = 0; i < d.names[t].length; i++) {{
        if (!d.f[t][i]) continue;
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
{insight_js}
  // La caja de lectura depende de los DOS controles, así que se recalcula
  // desde el estado actual en vez de que cada handler arme su propia clave.
  function refreshInsight() {{
    if (typeof setInsight !== 'function') return;
    var lg = document.getElementById('{div_id}_league');
    var liga = lg ? lg.value : {_ALL_JSON};
    // Con el filtro puesto se pide OTRA clave, no la misma con una advertencia:
    // los textos del subconjunto vienen calculados aparte desde Python, así que
    // la caja describe siempre la población que se está viendo.
    var clave = current + '|' + liga + (filterOn ? '|' + FILTER_KEY : '');
    var etiqueta = [current, liga === {_ALL_JSON} ? 'Todas las ligas' : liga,
                    filterOn ? FILTER_ESTADO : null]
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
  }});
}})();
</script>
"""
    return html


def render_with_sidebar(fig, *args, **kwargs):
    """Muestra en el notebook el resultado de `sidebar_chart_html(fig, ...)`.
    Mismos argumentos que esa función."""
    from IPython.display import HTML, display

    display(HTML(sidebar_chart_html(fig, *args, **kwargs)))


def plot_html(fig, width=680, height=480):
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
<div id="{div_id}_wrap">{inner}</div>
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
                            width=800, height=520, season_col="temporada"):
    """Box plot por liga con selector de temporada.

    El eje Y se fija con el rango de LAS 5 temporadas y no con el de cada una:
    si se reescalara en cada cambio, dos cajas del mismo alto significarían
    dispersiones distintas y el gráfico mentiría justo en lo que se quiere
    comparar. Por lo mismo las anotaciones de CV se recalculan pero se dibujan
    siempre a la misma altura."""
    default = seasons[-1]
    sub_default = df[df[season_col] == default]
    fig = league_box_figure(sub_default, y_col, y_axis_title, hover_fmt=hover_fmt,
                             name_col=name_col)

    lo, hi = df[y_col].min(), df[y_col].max()
    pad = (hi - lo) * 0.10
    cv_y = hi + pad * 0.55
    fig.update_yaxes(range=[lo - pad, hi + pad * 1.25])
    if annotate_cv:
        fig.update_layout(annotations=_cv_annotations(sub_default, y_col, name_col, y_at=cv_y))

    updates = {}
    for s in seasons:
        d = df[df[season_col] == s]
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
        updates[s] = upd

    return fig, [{"id": "season", "label": "Temporada", "options": list(seasons),
                   "default": default, "updates": updates}]
