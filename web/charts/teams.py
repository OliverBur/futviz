"""Gráficos a nivel de equipo para el sitio — mismo código/decisiones que
`code/eda_teams.ipynb`, portado a funciones que devuelven `ChartPage` en vez
de mostrar el gráfico en un notebook. Si un gráfico cambia en el notebook,
el cambio se porta acá a mano (el notebook sigue siendo donde se prototipa)."""

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from functools import partial

import insights as ins
from site_utils import PROCESSED_DIR, ChartPage
from viz_theme import (
    LEAGUE_ORDER, SEQUENTIAL_BLUE, INK, FUENTE_FBREF,
    league_color, league_box_season_html,
)
from viz_theme import explorer_chart_html as _explorer_chart_html
from viz_theme import sidebar_chart_html as _sidebar_chart_html
from viz_theme import select_chart_html as _select_chart_html

SECTION = "Equipos"

# Los nueve gráficos de la sección salen de las mismas tablas de equipo de
# FBref, así que el crédito que va debajo de cada uno se fija una sola vez acá
# en vez de repetirse en cada llamada — un gráfico nuevo lo hereda en vez de
# quedarse sin fuente por olvido.
sidebar_chart_html = partial(_sidebar_chart_html, fuente=FUENTE_FBREF)
select_chart_html = partial(_select_chart_html, fuente=FUENTE_FBREF)
explorer_chart_html = partial(_explorer_chart_html, fuente=FUENTE_FBREF)

# Las variables que se pueden poner en cada eje de "Crea tu gráfico":
# (columna, etiqueta, grupo del desplegable, decimales con los que se muestra).
#
# Están casi todas por 90 minutos y no en total a propósito. Las cinco ligas no
# juegan la misma cantidad de partidos (la Bundesliga 34, las otras 38) y Ligue 1
# cambió de 20 a 18 equipos en 2023-24, así que cualquier total mete esa
# diferencia dentro del dato y la mitad de los cruces terminarían midiendo
# "cuántos partidos jugó" en vez de lo que dice la etiqueta. Las excepciones son
# las que ya vienen normalizadas (porcentajes, promedios) y las rojas, que son
# tan pocas por partido que la tasa se vuelve ruido.
VARIABLES = [
    ("ov_Per 90 Minutes_Gls", "Goles por 90'", "Ataque", 2),
    ("ov_Per 90 Minutes_Ast", "Asistencias por 90'", "Ataque", 2),
    ("sh_Standard_Sh/90", "Tiros por 90'", "Ataque", 2),
    ("sh_Standard_SoT/90", "Tiros a puerta por 90'", "Ataque", 2),
    ("sh_Standard_SoT%", "% de tiros que van a puerta", "Ataque", 1),
    ("sh_Standard_G/Sh", "Goles por tiro", "Ataque", 2),
    ("sh_Standard_G/SoT", "Goles por tiro a puerta", "Ataque", 2),
    ("p90_Crs", "Centros por 90'", "Ataque", 2),
    ("p90_Off", "Fueras de juego por 90'", "Ataque", 2),

    ("gk_Performance_GA90", "Goles recibidos por 90'", "Defensa y portería", 2),
    ("p90_SoTA", "Tiros a puerta recibidos por 90'", "Defensa y portería", 2),
    ("gk_Performance_Save%", "% de paradas", "Defensa y portería", 1),
    ("gk_Performance_CS%", "% de porterías a cero", "Defensa y portería", 1),
    ("p90_TklW", "Entradas ganadas por 90'", "Defensa y portería", 2),
    ("p90_Int", "Intercepciones por 90'", "Defensa y portería", 2),

    ("p90_Fls", "Faltas cometidas por 90'", "Disciplina", 2),
    ("p90_Fld", "Faltas recibidas por 90'", "Disciplina", 2),
    ("p90_CrdY", "Amarillas por 90'", "Disciplina", 2),
    ("ms_Performance_CrdR", "Rojas (total)", "Disciplina", 0),

    ("ov_Poss", "Posesión (%)", "Contexto y resultado", 1),
    ("ov_Age", "Edad media de la plantilla", "Contexto y resultado", 1),
    ("pt_Team Success_PPM", "Puntos por partido", "Contexto y resultado", 2),
    ("pt_Team Success_+/-90", "Diferencia de goles por 90'", "Contexto y resultado", 2),
]

# Métricas del radar de perfil de liga. El criterio de selección (eta² +
# rango relativo + no redundancia) está documentado en la bitácora; acá solo
# se listan en el orden en que se dibujan los ejes.
RADAR_METRICS = [
    ("sh_Standard_Sh/90", "Tiros"), ("ov_Per 90 Minutes_Gls", "Goles"),
    ("sh_Standard_G/Sh", "G/Sh"), ("gk_Performance_CS%", "CS%"),
    ("p90_TklW", "Tackles"), ("p90_Int", "Intercep."),
    ("p90_Off", "Offsides"), ("p90_Fls", "Faltas"),
]


def load_data():
    """Las 5 temporadas ya consolidadas por `code/consolidate_data.py`.

    Antes se leían los 5 CSV crudos de una temporada y se asignaba la liga por
    bloques de filas *hardcodeados* (18/20/18/20/20). Eso no sobrevive a las 5
    temporadas: Ligue 1 tuvo 20 equipos hasta 2022-23 y 18 desde 2023-24, así
    que dos temporadas habrían quedado con la liga mal etiquetada en silencio.
    El consolidado ya trae `temporada` y `liga` resueltas (detecta los bloques
    por orden alfabético y verifica los tamaños)."""
    df = pd.read_csv(PROCESSED_DIR / "teams_all_seasons.csv")

    # Las derivadas se arman de una sola vez (un `df[nueva] = ...` por columna
    # sobre un frame de 171 columnas lo fragmenta y pandas avisa).
    derivadas = {
        col.replace("ms_Performance_", "p90_"): df[col] / df["ms_90s"]
        for col in ["ms_Performance_Fls", "ms_Performance_Off", "ms_Performance_Int",
                    "ms_Performance_TklW", "ms_Performance_CrdY", "ms_Performance_Crs",
                    "ms_Performance_Fld"]
    }
    derivadas["p90_SoTA"] = df["gk_Performance_SoTA"] / df["gk_Playing Time_90s"]
    derivadas["gk_ppm"] = ((df["gk_Performance_W"] * 3 + df["gk_Performance_D"])
                            / df["gk_Playing Time_MP"])
    df = pd.concat([df, pd.DataFrame(derivadas)], axis=1)

    df["liga"] = pd.Categorical(df["liga"], categories=LEAGUE_ORDER, ordered=True)
    cols = ["temporada", "Squad", "liga"] + [c for c in df.columns
                                              if c not in ("temporada", "Squad", "liga")]
    return df[cols]


def seasons_of(df):
    """Temporadas disponibles, de la más vieja a la más nueva."""
    return sorted(df["temporada"].unique())


def season_scatter_data(df, seasons):
    """`{temporada: [(liga, sub_df), ...]}` en el orden de `LEAGUE_ORDER`, que
    es lo que espera `sidebar_chart_html` para el selector de temporada."""
    return {s: [(liga, df[(df["temporada"] == s) & (df["liga"] == liga)])
                for liga in LEAGUE_ORDER]
            for s in seasons}


def radar_norm(df, seasons):
    """Promedio por liga-temporada de cada métrica del radar, escalado.

    Decisión de método: el divisor es el máximo sobre **las 25 liga-temporada**,
    no sobre las 5 ligas de cada temporada por separado. Con un máximo por
    temporada el punto de referencia se movería en cada una y las formas no
    serían comparables entre temporadas — que es justo lo que se quiere mirar
    acá. Dividir por una constante global no altera en nada la comparación
    *entre ligas dentro de* una temporada (todas se dividen por lo mismo), así
    que no se pierde lo que el gráfico ya hacía; solo se gana poder moverse
    entre temporadas. Se mantiene `value/max` como normalización (y no min-max
    ni z-score) por las razones documentadas en la bitácora: el 0 del eje es el
    0 real de la métrica y la separación refleja la proporción real."""
    metric_cols = [c for c, _ in RADAR_METRICS]
    avg = (df[df["temporada"].isin(seasons)]
           .groupby(["temporada", "liga"], observed=True)[metric_cols].mean())
    return avg / avg.max(), avg


def _radar_closed(values):
    """Un radar cierra la figura repitiendo el primer punto al final."""
    return list(values) + [values[0]]


def chart_radar_subplots(df, seasons, norm, avg):
    """Un radar por liga, lado a lado. Migrado de matplotlib a Plotly para que
    (a) tenga el selector de temporada como el resto de los gráficos y (b) el
    hover pueda mostrar el valor real de la métrica además del escalado, que
    era lo que a la imagen estática le faltaba para poder leerse sola."""
    labels = [l for _, l in RADAR_METRICS]
    metric_cols = [c for c, _ in RADAR_METRICS]
    theta = _radar_closed(labels)

    def r_for(season, liga):
        return _radar_closed(norm.loc[(season, liga), metric_cols].tolist())

    def raw_for(season, liga):
        return _radar_closed(avg.loc[(season, liga), metric_cols].tolist())

    default = seasons[-1]
    fig = make_subplots(rows=1, cols=5, specs=[[{"type": "polar"}] * 5],
                         subplot_titles=[l.upper() for l in LEAGUE_ORDER],
                         horizontal_spacing=0.045)

    for i, liga in enumerate(LEAGUE_ORDER, start=1):
        color = league_color(liga)
        fig.add_trace(go.Scatterpolar(
            r=r_for(default, liga), theta=theta, name=liga,
            mode="lines+markers", fill="toself",
            fillcolor=_rgba(color, 0.20),
            line=dict(color=color, width=2.2),
            marker=dict(color=color, size=5, line=dict(color=INK["surface"], width=0.6)),
            customdata=raw_for(default, liga), showlegend=False,
            hovertemplate="<b>%{theta}</b><br>valor: %{customdata:.2f}"
                           "<br>escala: %{r:.2f}<extra>" + liga + "</extra>",
        ), row=1, col=i)

    for ann, liga in zip(fig.layout.annotations, LEAGUE_ORDER):
        ann.font.color = league_color(liga)
        ann.font.size = 11.5

    fig.update_polars(radialaxis=dict(range=[0, 1], showticklabels=False, ticks="",
                                       gridcolor=INK["grid"], linecolor=INK["axis"]),
                       angularaxis=dict(tickfont=dict(size=9.5, color=INK["secondary"]),
                                         gridcolor=INK["grid"], linecolor=INK["axis"]),
                       bgcolor="rgba(0,0,0,0)")
    fig.update_layout(
        title=dict(text="Perfil de estilo por liga",
                   subtitle=dict(text=_radar_subtitle(default))),
        margin=dict(t=110, b=40, l=40, r=40),
    )

    updates = {
        s: {"restyle": {"r": [r_for(s, l) for l in LEAGUE_ORDER],
                        "customdata": [raw_for(s, l) for l in LEAGUE_ORDER]},
            "relayout": {"title.subtitle.text": _radar_subtitle(s)}}
        for s in seasons
    }
    labels_por_col = dict(RADAR_METRICS)
    body = select_chart_html(
        fig,
        [{"id": "season", "label": "Temporada", "options": seasons,
          "default": default, "updates": updates}],
        width=1080, height=420, min_width=760,
        hint="Los ejes están escalados contra el máximo de las 25 liga-temporada, "
              "así que las formas se pueden comparar entre temporadas.",
        insights={
            "que_mirar": ins.radar_que_mirar(),
            "por_que": ins.radar_por_que(),
            "dinamico": {s: dict(zip(("fija", "salta"),
                                      ins.radar(avg, labels_por_col, s, seasons)))
                          for s in seasons},
        },
    )
    return ChartPage(
        slug="perfil-liga-radar", section=SECTION, title="Perfil de estilo por liga",
        subtitle="8 métricas de estilo por liga, escaladas contra el máximo de las 5 ligas y 5 temporadas.",
        body_html=body, kind="radar",
    )


def _radar_subtitle(season):
    return (f"Promedio por equipo · escala proporcional al máximo de las 25 liga-temporada "
            f"· métricas por 90' · {season}")


def _rgba(hex_color, alpha):
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def chart_radar_overlay(df, seasons, norm, avg):
    """Las 5 ligas sobrepuestas + la separación por eje. En Plotly son dos
    subplots (polar + barras) en vez de dibujar la tabla a mano con `text()`
    sobre unos ejes apagados, que era lo que hacía la versión de matplotlib.

    El orden de las barras se fija con el promedio de las 5 temporadas y NO se
    reordena al cambiar de temporada: si las filas saltaran de lugar en cada
    cambio no se podría ver qué eje sube y cuál baja, que es justo lo que se
    quiere mirar. Lo que cambia es el largo de la barra."""
    labels = [l for _, l in RADAR_METRICS]
    metric_cols = [c for c, _ in RADAR_METRICS]
    col2label = dict(RADAR_METRICS)
    theta = _radar_closed(labels)
    default = seasons[-1]

    def sep_for(season):
        """1 − (mín ÷ máx) entre las 5 ligas de esa temporada, en %."""
        sub = avg.loc[season]
        return ((1 - sub.min() / sub.max()) * 100).reindex(metric_cols)

    orden = (pd.concat([sep_for(s) for s in seasons], axis=1).mean(axis=1)
             .sort_values(ascending=True).index.tolist())
    bar_labels = [col2label[c] for c in orden]

    fig = make_subplots(rows=1, cols=2, column_widths=[0.6, 0.4],
                         specs=[[{"type": "polar"}, {"type": "xy"}]],
                         horizontal_spacing=0.12,
                         subplot_titles=["", "Separación por eje (%)"])

    for liga in LEAGUE_ORDER:
        color = league_color(liga)
        fig.add_trace(go.Scatterpolar(
            r=_radar_closed(norm.loc[(default, liga), metric_cols].tolist()),
            theta=theta, name=liga, mode="lines", fill="toself",
            fillcolor=_rgba(color, 0.06), line=dict(color=color, width=2.4),
            customdata=_radar_closed(avg.loc[(default, liga), metric_cols].tolist()),
            hovertemplate="<b>%{theta}</b><br>valor: %{customdata:.2f}"
                           "<br>escala: %{r:.2f}<extra>" + liga + "</extra>",
        ), row=1, col=1)

    sep0 = sep_for(default)
    fig.add_trace(go.Bar(
        x=sep0.reindex(orden).tolist(), y=bar_labels, orientation="h",
        marker=dict(color=SEQUENTIAL_BLUE[3]), showlegend=False,
        hovertemplate="<b>%{y}</b><br>separación: %{x:.0f}%<extra></extra>",
    ), row=1, col=2)

    fig.update_polars(radialaxis=dict(range=[0, 1], showticklabels=False, ticks="",
                                       gridcolor=INK["grid"], linecolor=INK["axis"]),
                       angularaxis=dict(tickfont=dict(size=11, color=INK["secondary"]),
                                         gridcolor=INK["grid"], linecolor=INK["axis"]),
                       bgcolor="rgba(0,0,0,0)")
    # Rango fijo: si el eje se reescalara con cada temporada, una barra igual
    # de larga significaría separaciones distintas en cada una.
    xmax = max(sep_for(s).max() for s in seasons) * 1.12
    fig.update_xaxes(range=[0, xmax], ticksuffix="%", row=1, col=2)
    fig.update_yaxes(tickfont=dict(size=10.5), row=1, col=2)
    fig.update_layout(
        title=dict(text="Dónde se separa cada liga",
                   subtitle=dict(text=_overlay_subtitle(default))),
        legend=dict(orientation="h", y=-0.12, x=0.5, xanchor="center"),
        margin=dict(t=110, b=80, l=40, r=30),
    )

    updates = {
        s: {"restyle": [
                {"update": {"r": [_radar_closed(norm.loc[(s, l), metric_cols].tolist())
                                   for l in LEAGUE_ORDER],
                             "customdata": [_radar_closed(avg.loc[(s, l), metric_cols].tolist())
                                             for l in LEAGUE_ORDER]},
                 "traces": list(range(len(LEAGUE_ORDER)))},
                {"update": {"x": [sep_for(s).reindex(orden).tolist()]},
                 "traces": [len(LEAGUE_ORDER)]},
            ],
            "relayout": {"title.subtitle.text": _overlay_subtitle(s)}}
        for s in seasons
    }
    body = select_chart_html(
        fig,
        [{"id": "season", "label": "Temporada", "options": seasons,
          "default": default, "updates": updates}],
        width=980, height=560, min_width=680,
        hint="Las barras conservan siempre el mismo orden y la misma escala, "
              "para que al cambiar de temporada se vea qué eje sube y cuál baja.",
        insights={
            "que_mirar": ins.overlay_que_mirar(),
            "por_que": ins.overlay_por_que(),
            "dinamico": {s: dict(zip(("fija", "salta"),
                                      ins.overlay(avg, col2label, s, seasons)))
                          for s in seasons},
        },
    )
    return ChartPage(
        slug="perfil-liga-overlay", section=SECTION, title="Dónde se separa cada liga",
        subtitle="Las 5 formas del radar sobrepuestas, con la separación por eje al lado.",
        body_html=body, kind="radar",
    )


def _overlay_subtitle(season):
    return f"Las 5 ligas sobrepuestas · separación = 1 − (mín ÷ máx) entre ligas · {season}"


def chart_style_evolution(df, seasons):
    """Gráfico nuevo, imposible con una sola temporada: cómo se mueve cada
    métrica de estilo a lo largo de las 5, una línea por liga.

    Es el complemento del radar: el radar es la forma de una temporada, esto
    es un eje del radar a través del tiempo. Va en valor real (no escalado)
    porque acá la pregunta es de magnitud — cuántas faltas menos se pitan
    ahora que en 2021-22 — y escalar lo escondería."""
    metric_cols = [c for c, _ in RADAR_METRICS]
    col2label = dict(RADAR_METRICS)
    avg = (df.groupby(["temporada", "liga"], observed=True)[metric_cols]
           .mean().reset_index())

    default_metric = "ov_Per 90 Minutes_Gls"  # los goles: es de lo que se habla

    def _series_y_rango(col):
        """Las 5 series de una métrica y el rango de su eje, con un poco de
        aire: sin fijarlo Plotly reescala a cada cambio y una caída chica puede
        verse como un desplome."""
        ys = [avg[avg["liga"] == liga].sort_values("temporada")[col].tolist()
              for liga in LEAGUE_ORDER]
        lo = min(min(y) for y in ys)
        hi = max(max(y) for y in ys)
        pad = (hi - lo) * 0.12 or 0.1
        return ys, [lo - pad, hi + pad]

    fig = go.Figure()
    for liga in LEAGUE_ORDER:
        sub = avg[avg["liga"] == liga].sort_values("temporada")
        fig.add_trace(go.Scatter(
            x=sub["temporada"], y=sub[default_metric], name=liga, mode="lines+markers",
            line=dict(color=league_color(liga), width=2.6),
            marker=dict(color=league_color(liga), size=8,
                        line=dict(color=INK["surface"], width=1)),
            hovertemplate="<b>%{x}</b><br>%{y:.2f}<extra>" + liga + "</extra>",
        ))

    fig.update_layout(
        title=dict(text="Evolución del estilo por liga",
                   subtitle=dict(text=_evolution_subtitle(col2label[default_metric]))),
        xaxis_title="Temporada", yaxis_title=col2label[default_metric],
        xaxis=dict(type="category"),
        # El mismo rango que le toca a esta métrica en `updates`, y no el que
        # Plotly calcule solo: si no, el gráfico se movía un poco al elegir
        # otra métrica y volver a la inicial.
        yaxis=dict(range=_series_y_rango(default_metric)[1]),
    )

    updates = {}
    for col in metric_cols:
        ys, rango = _series_y_rango(col)
        updates[col] = {
            "restyle": {"y": ys},
            "relayout": {"yaxis.title.text": col2label[col],
                          "yaxis.range": rango,
                          "title.subtitle.text": _evolution_subtitle(col2label[col])},
        }

    body = select_chart_html(
        fig,
        [{"id": "metric", "label": "Métrica", "options": metric_cols,
          "labels": col2label, "default": default_metric, "updates": updates}],
        width=820, height=540,
        hint="Promedio por equipo de cada liga, temporada a temporada. "
              "Las métricas son las mismas 8 ejes del radar.",
        insights={
            "que_mirar": ins.evolucion_que_mirar(),
            "por_que": ins.evolucion_por_que(),
            "dinamico": {c: dict(zip(("fija", "salta"),
                                      ins.evolucion(avg, col2label, c, seasons)))
                          for c in metric_cols},
        },
    )
    return ChartPage(
        slug="evolucion-estilo", section=SECTION, title="Evolución del estilo por liga",
        subtitle="Cómo se movió cada métrica de estilo a lo largo de las 5 temporadas.",
        body_html=body, kind="line",
    )


def _evolution_subtitle(label):
    return f"{label} — promedio por equipo de cada liga, temporada a temporada"


def chart_def_efficiency(df, seasons, season_data):
    x_col, y_col = "sh_Standard_SoT%", "sh_Standard_G/SoT"
    x_mean, y_mean = df[x_col].mean(), df[y_col].mean()
    scatter_data = season_data[seasons[-1]]

    fig = go.Figure()
    for liga, sub in scatter_data:
        fig.add_trace(go.Scatter(
            x=sub[x_col], y=sub[y_col], mode="markers", name=liga,
            marker=dict(color=league_color(liga), size=[11] * len(sub), opacity=0.88,
                        line=dict(color=INK["surface"], width=1)),
            customdata=sub["Squad"],
            hovertemplate=f"<b>%{{customdata}}</b><br>{liga}<br>SoT%%: %{{x:.1f}}%<br>G/SoT: %{{y:.2f}}<extra></extra>",
        ))

    fig.add_vline(x=x_mean, line=dict(color=INK["axis"], width=1, dash="dash"))
    fig.add_hline(y=y_mean, line=dict(color=INK["axis"], width=1, dash="dash"))

    quadrant_annotations = [
        dict(x=x_mean + 0.4, y=df[y_col].max() + 0.005, text="certeros y letales",
             showarrow=False, font=dict(size=10.5, color=INK["muted"]), xanchor="left", yanchor="bottom"),
        dict(x=x_mean - 0.4, y=df[y_col].max() + 0.005, text="poco a puerta, pero letales",
             showarrow=False, font=dict(size=10.5, color=INK["muted"]), xanchor="right", yanchor="bottom"),
        dict(x=x_mean + 0.4, y=df[y_col].min() - 0.01, text="mucho a puerta, poca pegada",
             showarrow=False, font=dict(size=10.5, color=INK["muted"]), xanchor="left", yanchor="top"),
        dict(x=x_mean - 0.4, y=df[y_col].min() - 0.01, text="ni certeros ni letales",
             showarrow=False, font=dict(size=10.5, color=INK["muted"]), xanchor="right", yanchor="top"),
    ]

    subtitle = "Precisión (llegar a puerta) vs. definición (marcar una vez ahí) · {temporada}"
    fig.update_layout(
        title=dict(text="Eficiencia de definición",
                   subtitle=dict(text=subtitle.format(temporada=seasons[-1]))),
        xaxis_title="Precisión — % de tiros que van a puerta (SoT%)",
        yaxis_title="Definición — goles por tiro a puerta (G/SoT)",
        annotations=quadrant_annotations,
        # Rango fijo sobre las 5 temporadas: sin esto cada cambio de temporada
        # reescala los ejes y los puntos parecen moverse más de lo que se mueven.
        xaxis=dict(range=_padded(df[x_col])), yaxis=dict(range=_padded(df[y_col])),
    )
    body = sidebar_chart_html(fig, scatter_data, x_col, y_col, base_annotations=quadrant_annotations,
                               # El título de estos ejes es una frase entera y no
                               # entra en la columna del top 5.
                               top_labels=("Precisión (SoT%)", "Definición (G/SoT)"),
                               width=760, height=580, season_data=season_data,
                               custom_cols=["Squad"], subtitle_template=subtitle,
                               insights={
                                   "que_mirar": ins.definicion_que_mirar(),
                                   "por_que": ins.definicion_por_que(df),
                                   "dinamico": _por_temporada_y_liga(ins.definicion, df, seasons),
                               })
    return ChartPage(
        slug="eficiencia-definicion", section=SECTION, title="Eficiencia de definición",
        subtitle="Precisión (SoT%) vs. definición (G/SoT) — un punto por equipo.",
        body_html=body,
    )


def _por_temporada_y_liga(generador, df, seasons):
    """La caja de los scatters depende de los dos controles, así que hay que
    generar una entrada por cada combinación temporada x liga ("__all__" = sin
    filtro). La clave tiene que coincidir con la que arma el JS."""
    return {
        f"{s}|{liga}": dict(zip(("fija", "salta"), generador(df, s, liga)))
        for s in seasons
        for liga in [ins.LIGA_TODAS] + list(LEAGUE_ORDER)
    }


def _padded(serie, frac=0.06):
    """Rango de un eje con aire, calculado sobre TODAS las temporadas."""
    lo, hi = serie.min(), serie.max()
    pad = (hi - lo) * frac
    return [lo - pad, hi + pad]


def chart_gk_vs_result(df, seasons, season_data):
    x_col3, y_col3 = "gk_Performance_CS%", "gk_ppm"
    scatter_data3 = season_data[seasons[-1]]

    fig = go.Figure()
    for liga, sub in scatter_data3:
        fig.add_trace(go.Scatter(
            x=sub[x_col3], y=sub[y_col3], mode="markers", name=liga,
            marker=dict(color=league_color(liga), size=[11] * len(sub), opacity=0.88,
                        line=dict(color=INK["surface"], width=1)),
            customdata=sub["Squad"],
            hovertemplate=f"<b>%{{customdata}}</b><br>{liga}<br>CS%%: %{{x:.1f}}%<br>Puntos/partido: %{{y:.2f}}<extra></extra>",
        ))

    subtitle3 = "Porterías a cero vs. puntos por partido · {temporada}"
    fig.update_layout(
        title=dict(text="¿Cuánto pesa la portería en el resultado?",
                   subtitle=dict(text=subtitle3.format(temporada=seasons[-1]))),
        xaxis_title="Porterías a cero (%)", yaxis_title="Puntos por partido",
        xaxis=dict(range=_padded(df[x_col3])), yaxis=dict(range=_padded(df[y_col3])),
    )
    body = sidebar_chart_html(fig, scatter_data3, x_col3, y_col3, width=760, height=580,
                               season_data=season_data, custom_cols=["Squad"],
                               subtitle_template=subtitle3,
                               insights={
                                   "que_mirar": ins.porteria_que_mirar(),
                                   "por_que": ins.porteria_por_que(df),
                                   "dinamico": _por_temporada_y_liga(
                                       ins.porteria, df, seasons),
                               })
    return ChartPage(
        slug="porteria-vs-resultado", section=SECTION, title="Portería vs. resultado del equipo",
        subtitle="Porterías a cero (%) vs. puntos por partido — un punto por equipo.",
        body_html=body,
    )


def chart_gk_demand(df, seasons, season_data):
    x_col4, y_col4 = "gk_Performance_SoTA", "gk_Performance_Save%"
    x_mean4, y_mean4 = df[x_col4].mean(), df[y_col4].mean()
    scatter_data4 = season_data[seasons[-1]]

    fig = go.Figure()
    for liga, sub in scatter_data4:
        fig.add_trace(go.Scatter(
            x=sub[x_col4], y=sub[y_col4], mode="markers", name=liga,
            marker=dict(color=league_color(liga), size=[11] * len(sub), opacity=0.88,
                        line=dict(color=INK["surface"], width=1)),
            customdata=sub["Squad"],
            hovertemplate=f"<b>%{{customdata}}</b><br>{liga}<br>SoTA: %{{x}}<br>Save%%: %{{y:.1f}}%<extra></extra>",
        ))

    fig.add_vline(x=x_mean4, line=dict(color=INK["axis"], width=1, dash="dash"))
    fig.add_hline(y=y_mean4, line=dict(color=INK["axis"], width=1, dash="dash"))

    quadrant_annotations4 = [
        dict(x=x_mean4 + 3, y=df[y_col4].max() + 0.3, text="muy exigido y rinde",
             showarrow=False, font=dict(size=10.5, color=INK["muted"]), xanchor="left", yanchor="bottom"),
        dict(x=x_mean4 - 3, y=df[y_col4].max() + 0.3, text="poco exigido y rinde",
             showarrow=False, font=dict(size=10.5, color=INK["muted"]), xanchor="right", yanchor="bottom"),
        dict(x=x_mean4 + 3, y=df[y_col4].min() - 0.6, text="muy exigido, le cuesta",
             showarrow=False, font=dict(size=10.5, color=INK["muted"]), xanchor="left", yanchor="top"),
        dict(x=x_mean4 - 3, y=df[y_col4].min() - 0.6, text="poco exigido y rinde poco",
             showarrow=False, font=dict(size=10.5, color=INK["muted"]), xanchor="right", yanchor="top"),
    ]

    subtitle4 = "Tiros a puerta enfrentados vs. tasa de atajadas · {temporada}"
    fig.update_layout(
        title=dict(text="Exigencia vs. rendimiento",
                   subtitle=dict(text=subtitle4.format(temporada=seasons[-1]))),
        xaxis_title="Tiros a puerta enfrentados en la temporada (SoTA)",
        yaxis_title="Tasa de atajadas (Save%)",
        annotations=quadrant_annotations4,
        xaxis=dict(range=_padded(df[x_col4])), yaxis=dict(range=_padded(df[y_col4])),
    )
    body = sidebar_chart_html(fig, scatter_data4, x_col4, y_col4, base_annotations=quadrant_annotations4,
                               top_labels=("Tiros enfrentados (SoTA)", "Atajadas (Save%)"),
                               width=760, height=580, season_data=season_data,
                               custom_cols=["Squad"], subtitle_template=subtitle4,
                               insights={
                                   "que_mirar": ins.exigencia_que_mirar(),
                                   "por_que": ins.exigencia_por_que(df),
                                   "dinamico": _por_temporada_y_liga(
                                       ins.exigencia, df, seasons),
                               })
    return ChartPage(
        slug="exigencia-rendimiento", section=SECTION, title="Exigencia vs. rendimiento",
        subtitle="Tiros a puerta enfrentados (SoTA) vs. tasa de atajadas (Save%) — un punto por equipo.",
        body_html=body,
    )


def _box_page(df, seasons, *, y_col, y_axis_title, slug, title, subtitle, chart_title,
               chart_subtitle, hover_fmt=".1f", annotate_cv=False, insights=None):
    fig, controls, _ = league_box_season_html(
        df, y_col, y_axis_title, seasons, hover_fmt=hover_fmt, annotate_cv=annotate_cv,
        subtitle_template=chart_subtitle,
    )
    fig.update_layout(
        title=dict(text=chart_title,
                   subtitle=dict(text=chart_subtitle.format(temporada=seasons[-1]))),
        yaxis_title=y_axis_title, xaxis_title=None,
    )
    return ChartPage(
        slug=slug, section=SECTION, title=title, subtitle=subtitle,
        body_html=select_chart_html(fig, controls, width=800, height=520,
                                     insights=insights),
        kind="box",
    )


def chart_parity(df, seasons):
    return _box_page(
        df, seasons, y_col="pt_Team Success_PPM", y_axis_title="Puntos por partido",
        slug="paridad-competitiva", title="Paridad competitiva",
        subtitle="Dispersión de puntos por partido dentro de cada liga.",
        chart_title="Paridad competitiva",
        chart_subtitle="Puntos por partido de cada equipo · % = coeficiente de variación · {temporada}",
        hover_fmt=".2f", annotate_cv=True,
        insights={
            "que_mirar": ins.paridad_que_mirar(),
            "por_que": ins.paridad_por_que(),
            "dinamico": {s: dict(zip(("fija", "salta"), ins.paridad(df, s, seasons)))
                          for s in seasons},
        },
    )


def chart_age(df, seasons):
    return _box_page(
        df, seasons, y_col="ov_Age", y_axis_title="Edad promedio",
        slug="edad-plantilla", title="Edad de plantilla",
        subtitle="Edad promedio por equipo, agrupados por liga.",
        chart_title="Edad de plantilla",
        chart_subtitle="Edad promedio de cada equipo, agrupados por liga · {temporada}",
        insights={
            "que_mirar": ins.edad_que_mirar(),
            "por_que": ins.edad_por_que(df),
            "dinamico": {s: dict(zip(("fija", "salta"), ins.edad(df, s, seasons)))
                          for s in seasons},
        },
    )


def chart_discipline(df, seasons):
    return _box_page(
        df, seasons, y_col="p90_CrdY", y_axis_title="Amarillas por 90",
        slug="disciplina-amarillas", title="Disciplina: tarjetas amarillas",
        subtitle="Amarillas por 90' de cada equipo, agrupados por liga.",
        chart_title="Disciplina: tarjetas amarillas",
        chart_subtitle="Amarillas por 90 minutos de cada equipo · {temporada}",
        hover_fmt=".2f",
        insights={
            "que_mirar": ins.disciplina_que_mirar(),
            "por_que": ins.disciplina_por_que(),
            "dinamico": {s: dict(zip(("fija", "salta"), ins.disciplina(df, s, seasons)))
                          for s in seasons},
        },
    )


def chart_explorer(df, seasons, season_data):
    """"Crea tu gráfico": el lector elige las dos variables.

    No lleva caja de "qué mirar" porque no hay un "acá" del que hablar: el par
    de variables lo elige quien mira. Lo que sí lleva es el r² del par elegido,
    calculado en el navegador sobre los puntos que están dibujados (ver
    `viz_theme.explorer_chart_html`)."""
    return ChartPage(
        slug="crea-tu-grafico-equipos", section=SECTION, title="Crea tu gráfico",
        subtitle=f"Cruza cualquier par de las {len(VARIABLES)} variables de equipo — y el r² te dice si de verdad son dos cosas distintas o la misma medida dos veces.",
        body_html=explorer_chart_html(
            season_data, VARIABLES, name_col="Squad", search_label="club",
            entidad="equipos", default_x="ov_Poss", default_y="pt_Team Success_PPM",
            base_size=11),
        kind="explorer",
    )


def build(assets_dir) -> list:
    df = load_data()
    seasons = seasons_of(df)
    season_data = season_scatter_data(df, seasons)
    norm, avg = radar_norm(df, seasons)
    pages = []

    # Ya no queda ningún gráfico de matplotlib en esta sección: los radares
    # pasaron a Plotly y el ranking de porterías se quitó. Todo se dibuja en
    # runtime, así que no hay PNG que pre-renderizar por tema.
    pages.append(chart_radar_subplots(df, seasons, norm, avg))
    pages.append(chart_radar_overlay(df, seasons, norm, avg))
    pages.append(chart_style_evolution(df, seasons))
    pages.append(chart_def_efficiency(df, seasons, season_data))

    pages.append(chart_gk_vs_result(df, seasons, season_data))
    pages.append(chart_gk_demand(df, seasons, season_data))
    pages.append(chart_parity(df, seasons))
    pages.append(chart_age(df, seasons))
    pages.append(chart_discipline(df, seasons))
    pages.append(chart_explorer(df, seasons, season_data))
    return pages
