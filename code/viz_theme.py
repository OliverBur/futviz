"""Identidad visual compartida para los notebooks de futviz_pl / top5ligas.

Un solo lugar para paleta y estilo matplotlib: se importa igual en todos
los notebooks del proyecto para que cada gráfico se vea consistente.
"""

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


def apply_theme():
    """Aplica el tema a matplotlib. Llamar una vez al inicio del notebook."""
    mpl.rcParams.update({
        "figure.facecolor": INK["surface"],
        "axes.facecolor": INK["surface"],
        "savefig.facecolor": INK["surface"],
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


def apply_plotly_theme():
    """Registra y activa un template de Plotly con la misma identidad visual
    (superficie, tinta, grid) que apply_theme() usa para matplotlib. Llamar
    una vez al inicio de un notebook que use gráficos Plotly."""
    import plotly.graph_objects as go
    import plotly.io as pio

    axis = dict(
        gridcolor=INK["grid"],
        zerolinecolor=INK["axis"],
        linecolor=INK["axis"],
        tickfont=dict(color=INK["muted"], size=11),
        title=dict(font=dict(color=INK["secondary"], size=12)),
    )
    pio.templates["futviz"] = go.layout.Template(
        layout=go.Layout(
            paper_bgcolor=INK["surface"],
            plot_bgcolor=INK["surface"],
            font=dict(family="Segoe UI, Arial, sans-serif", color=INK["primary"], size=12),
            title=dict(
                font=dict(size=18, color=INK["primary"], family="Segoe UI Semibold, Segoe UI, Arial"),
                subtitle=dict(font=dict(size=12.5, color=INK["secondary"])),
                x=0.03, xanchor="left",
            ),
            xaxis=axis,
            yaxis=axis,
            legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=INK["secondary"], size=11)),
            hoverlabel=dict(bgcolor=INK["surface"], bordercolor=INK["axis"],
                             font=dict(color=INK["primary"], size=12)),
            margin=dict(t=90, r=40, b=60, l=70),
        )
    )
    pio.templates.default = "futviz"


def sidebar_chart_html(fig, scatter_data, x_col, y_col, base_annotations=None,
                        extra_traces=0, base_size=11, highlight_size=20,
                        width=680, height=560, name_col="Squad", search_label="club"):
    """Arma el HTML/JS de un gráfico Plotly con una barra lateral genuina a
    la derecha (no superpuesta, es un elemento aparte en un layout flex):
    - Buscador con autocompletado NATIVO del navegador (`<input list>` +
      `<datalist>`) sobre `name_col` (ej. "Squad" para equipos, "player"
      para jugadores) — escribes unas letras y aparecen las opciones que
      matchean, sin necesidad de Dash ni de un menú con cientos de opciones.
    - `<select>` para filtrar por liga.
    Los dos controles manipulan el gráfico ya renderizado vía
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

    Responsivo: el gráfico no lleva ancho/alto fijo en px, sino que ocupa el
    100% de su contenedor con relación de aspecto `width:height` fija (así
    no se deforma) hasta un tope de `width`px; en pantallas angostas la
    barra lateral pasa a apilarse debajo del gráfico en vez de achicarlo.

    Devuelve el HTML como string (no lo muestra) — ver `render_with_sidebar`
    para mostrarlo directo en un notebook."""
    import json
    import uuid
    import plotly.io as pio

    div_id = f"chart_{uuid.uuid4().hex[:8]}"
    fig.update_layout(autosize=True)
    plot_html = pio.to_html(fig, full_html=False, include_plotlyjs="cdn",
                             div_id=div_id, config={"displaylogo": False, "responsive": True},
                             default_width="100%", default_height="100%")
    aspect_ratio = width / height

    base_annotations = list(base_annotations or [])
    base_sizes = [[base_size] * len(sub) for _, sub in scatter_data]
    trace_indices = list(range(len(scatter_data)))
    league_order = [liga for liga, _ in scatter_data]

    entity_map = {}
    for liga, sub in scatter_data:
        for _, r in sub.iterrows():
            name = r[name_col]
            sizes = [[highlight_size if s == name else base_size for s in s2[name_col]]
                     for _, s2 in scatter_data]
            entity_map[name] = {
                "sizes": sizes,
                "league": liga,
                "annotation": dict(x=r[x_col], y=r[y_col], text=name, showarrow=True,
                                    arrowhead=2, arrowcolor=INK["axis"], ax=0, ay=-32,
                                    font=dict(size=11, color=INK["primary"])),
            }
    club_map = entity_map
    club_options = "".join(f'<option value="{name}"></option>' for name in sorted(entity_map))
    league_options = "".join(f'<option value="{liga}">{liga}</option>' for liga in league_order)

    html = f"""
<style>
  #{div_id}_layout {{ display:flex; flex-wrap: wrap; align-items:flex-start; gap:20px; max-width: 100%; }}
  #{div_id}_plotwrap {{ position: relative; flex: 1 1 280px; width: 100%; max-width: {width}px;
    aspect-ratio: {aspect_ratio}; min-width: 0; }}
  #{div_id}_plotwrap > div {{ position: absolute; inset: 0; }}
  #{div_id}_sidebar {{ font-family: "Segoe UI", Arial, sans-serif; padding-top: 54px;
    flex: 1 1 190px; max-width: 260px; box-sizing: border-box; }}
  #{div_id}_sidebar .block {{ margin-bottom: 22px; }}
  #{div_id}_sidebar label {{ display: block; font-size: 11px; color: {INK["muted"]};
    text-transform: uppercase; letter-spacing: .03em; margin-bottom: 5px; }}
  #{div_id}_sidebar input, #{div_id}_sidebar select {{ width: 100%; box-sizing: border-box;
    padding: 7px 9px; font-size: 13px; font-family: inherit; color: {INK["primary"]};
    background: {INK["surface"]}; border: 1px solid {INK["axis"]}; border-radius: 6px; }}
  @media (max-width: 520px) {{
    #{div_id}_sidebar {{ padding-top: 4px; max-width: 100%; }}
    #{div_id}_plotwrap {{ aspect-ratio: {max(aspect_ratio * 0.6, 0.85)}; }}
  }}
</style>
<div id="{div_id}_layout">
  <div id="{div_id}_plotwrap">{plot_html}</div>
  <div id="{div_id}_sidebar">
    <div class="block">
      <label>Buscar {search_label}</label>
      <input list="{div_id}_clubs" id="{div_id}_search" placeholder="Escribe un {search_label}…" autocomplete="off">
      <datalist id="{div_id}_clubs">{club_options}</datalist>
    </div>
    <div class="block">
      <label>Filtrar por liga</label>
      <select id="{div_id}_league">
        <option value="__all__">Todas las ligas</option>
        {league_options}
      </select>
    </div>
  </div>
</div>
<script>
(function() {{
  var clubMap = {json.dumps(club_map)};
  var baseSizes = {json.dumps(base_sizes)};
  var baseAnnotations = {json.dumps(base_annotations)};
  var traceIndices = {json.dumps(trace_indices)};
  var leagueOrder = {json.dumps(league_order)};
  var extraTraces = {extra_traces};

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

  document.getElementById('{div_id}_search').addEventListener('input', function(e) {{
    var val = e.target.value;
    if (clubMap.hasOwnProperty(val)) {{
      Plotly.restyle('{div_id}', {{'marker.size': clubMap[val].sizes}}, traceIndices);
      Plotly.relayout('{div_id}', {{annotations: baseAnnotations.concat([clubMap[val].annotation])}});
    }} else if (val === '') {{
      Plotly.restyle('{div_id}', {{'marker.size': baseSizes}}, traceIndices);
      Plotly.relayout('{div_id}', {{annotations: baseAnnotations}});
    }}
  }});

  document.getElementById('{div_id}_league').addEventListener('change', function(e) {{
    var val = e.target.value;
    var vis = (val === '__all__')
      ? leagueOrder.map(function() {{ return true; }})
      : leagueOrder.map(function(lg) {{ return lg === val; }});
    for (var i = 0; i < extraTraces; i++) vis.push(true);
    Plotly.restyle('{div_id}', {{visible: vis}});

    var searchInput = document.getElementById('{div_id}_search');
    var searched = clubMap[searchInput.value];
    if (searched && val !== '__all__' && searched.league !== val) {{
      searchInput.value = '';
      Plotly.restyle('{div_id}', {{'marker.size': baseSizes}}, traceIndices);
      Plotly.relayout('{div_id}', {{annotations: baseAnnotations}});
    }}
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
    import uuid
    import plotly.io as pio

    div_id = f"chart_{uuid.uuid4().hex[:8]}"
    fig.update_layout(autosize=True)
    inner = pio.to_html(fig, full_html=False, include_plotlyjs="cdn",
                         div_id=div_id, config={"displaylogo": False, "responsive": True},
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
        ymax = df[y_col].max()
        yspan = df[y_col].max() - df[y_col].min()
        for liga in LEAGUE_ORDER:
            sub = df[df["liga"] == liga]
            cv = sub[y_col].std() / sub[y_col].mean() * 100
            fig.add_annotation(x=liga, y=ymax + yspan * 0.06, text=f"{cv:.0f}%", showarrow=False,
                                font=dict(size=11, color=INK["secondary"]))
    return fig
