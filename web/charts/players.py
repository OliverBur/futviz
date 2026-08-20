"""Gráficos a nivel de jugador para el sitio — mismo código/decisiones que
`code/eda_players.ipynb`, portado a funciones que devuelven `ChartPage`."""

from functools import partial

import pandas as pd
import plotly.graph_objects as go

import insights as ins
import shot_map
from site_utils import PROCESSED_DIR, ChartPage
from viz_theme import (
    LEAGUE_ORDER, FUENTE_UNDERSTAT, league_color, league_box_season_html,
)
from viz_theme import explorer_chart_html as _explorer_chart_html
from viz_theme import sidebar_chart_html as _sidebar_chart_html
from viz_theme import select_chart_html as _select_chart_html

SECTION = "Jugadores"

# Todo lo de esta sección sale de Understat (es quien publica xG/xA a nivel de
# jugador; FBref dejó de hacerlo), así que el crédito se fija una vez acá. La
# única excepción es el año de nacimiento del filtro sub-21, que sí viene de
# FBref y se aclara en el propio filtro.
sidebar_chart_html = partial(_sidebar_chart_html, fuente=FUENTE_UNDERSTAT)
select_chart_html = partial(_select_chart_html, fuente=FUENTE_UNDERSTAT)
explorer_chart_html = partial(_explorer_chart_html, fuente=FUENTE_UNDERSTAT)

# Las variables que se pueden poner en cada eje de "Crea tu gráfico":
# (columna, etiqueta, grupo del desplegable, decimales con los que se muestra).
# Los totales conviven con sus tasas por 90' a propósito: son preguntas
# distintas —quién produjo más en la temporada contra quién produce más cuando
# está en la cancha— y cruzar una contra la otra es una de las cosas
# interesantes que se pueden hacer acá.
VARIABLES = [
    ("goals", "Goles", "Producción", 0),
    ("a", "Asistencias", "Producción", 0),
    ("np_goals", "Goles sin penalti", "Producción", 0),
    ("g90", "Goles por 90'", "Producción", 2),
    ("a90", "Asistencias por 90'", "Producción", 2),

    ("xG", "xG", "Esperado", 1),
    ("xA", "xA", "Esperado", 1),
    ("np_xg", "xG sin penalti", "Esperado", 1),
    ("xG90", "xG por 90'", "Esperado", 2),
    ("xA90", "xA por 90'", "Esperado", 2),
    ("xg_chain", "xG de las jugadas en que participó", "Esperado", 1),
    ("xg_buildup", "xG de construcción (sin tiro ni asistencia)", "Esperado", 1),

    ("shots", "Tiros", "Volumen de juego", 0),
    ("sh90", "Tiros por 90'", "Volumen de juego", 2),
    ("key_passes", "Pases clave", "Volumen de juego", 0),
    ("kp90", "Pases clave por 90'", "Volumen de juego", 2),

    ("min", "Minutos jugados", "Contexto y disciplina", 0),
    ("edad", "Edad", "Contexto y disciplina", 0),
    ("yellow_cards", "Amarillas", "Contexto y disciplina", 0),
    ("red_cards", "Rojas", "Contexto y disciplina", 0),
]

MIN_MINUTES = 500

# Filtro sub-21 de los scatter. `sub21` la calcula `consolidate_data.py` a
# partir del año de nacimiento que aporta fbref (Understat no publica edad), con
# el criterio de las categorías sub-N de UEFA: cuenta el año, no el cumpleaños.
# Los jugadores cuyo nombre no cruzó con fbref quedan sin edad, y por lo tanto
# fuera del filtro — es lo correcto: edad desconocida no es sub-21.
SUB21_FILTER = {
    "col": "sub21",
    "label": "Edad",
    "text": "Solo sub-21",
    "hint": "Menos de 21 al arrancar la temporada — cuenta el año de "
            "nacimiento, no el cumpleaños. La edad es el único dato de esta "
            "sección que no sale de Understat, que no la publica: viene de FBref.",
    # Cómo se nombra el filtro en el rótulo de la caja de lectura ("2025-26 ·
    # Ligue 1 · sub-21"), que es lo que le dice al lector sobre qué población
    # están hechas las afirmaciones que está leyendo.
    "estado": "sub-21",
}
BASE_SIZE = 8  # tamaño del punto; se le pasa al buscador para que al resaltar
               # y volver no cambie de tamaño respecto del estado inicial


def load_data():
    """Las 5 temporadas de Understat ya consolidadas.

    `consolidate_data.py` ya decodifica las entidades HTML de los nombres
    (`O&#039;Reilly`), pero a propósito NO toca `team`: los jugadores que
    cambiaron de club a mitad de temporada traen los dos separados por coma y
    quedarse con uno es decisión de análisis. Acá se toma el último, que es la
    misma decisión que en `eda_players.ipynb`."""
    df = pd.read_csv(PROCESSED_DIR / "players_all_seasons.csv")
    df["team"] = df["team"].str.split(",").str[-1].str.strip()
    df["liga"] = pd.Categorical(df["liga"], categories=LEAGUE_ORDER, ordered=True)
    df = df[df["min"] >= MIN_MINUTES].reset_index(drop=True)

    # Derivadas para "Crea tu gráfico". Las tasas por 90' van sobre los minutos
    # reales y no sobre los partidos: `apps` cuenta también las entradas desde
    # el banco, así que dividir por ahí le daría una tasa inflada a cualquier
    # suplente. La edad sale del año de nacimiento con el mismo criterio que
    # `sub21` (cuenta el año, no el cumpleaños), y queda nula para quien no
    # cruzó con FBref.
    noventas = df["min"] / 90
    df = pd.concat([df, pd.DataFrame({
        "g90": df["goals"] / noventas,
        "a90": df["a"] / noventas,
        "sh90": df["shots"] / noventas,
        "kp90": df["key_passes"] / noventas,
        "edad": df["temporada"].str[:4].astype(int) - df["born"],
    })], axis=1)
    return df


def seasons_of(df):
    return sorted(df["temporada"].unique())


def season_scatter_data(df, seasons):
    return {s: [(liga, df[(df["temporada"] == s) & (df["liga"] == liga)])
                for liga in LEAGUE_ORDER]
            for s in seasons}


def _padded(serie, frac=0.06):
    lo, hi = serie.min(), serie.max()
    pad = (hi - lo) * frac
    return [lo - pad, hi + pad]


def _scatter_traces(fig, scatter_data, x_col, y_col, x_label, y_label, x_fmt, y_fmt):
    for liga, sub in scatter_data:
        fig.add_trace(go.Scatter(
            x=sub[x_col], y=sub[y_col], mode="markers", name=liga,
            marker=dict(color=league_color(liga), size=BASE_SIZE, opacity=0.75,
                        line=dict(width=0.5, color="white")),
            customdata=sub[["player", "team"]],
            hovertemplate="<b>%{customdata[0]}</b> (%{customdata[1]})<br>"
                           f"{x_label}: %{{x:{x_fmt}}}<br>{y_label}: %{{y:{y_fmt}}}<extra></extra>",
        ))


def _entrada(generador, df, season, liga):
    """El par (fija, salta) de una combinación, o un aviso si no queda nadie a
    quien describir.

    Hoy ninguna combinación queda vacía —la más chica tiene 14 sub-21—, pero los
    generadores piden el máximo del subconjunto y sobre un DataFrame vacío eso
    revienta; subir el corte de minutos bastaría para provocarlo."""
    d = df[df["temporada"] == season]
    if liga != ins.LIGA_TODAS:
        d = d[d["liga"] == liga]
    if d.empty:
        return {"fija": "Ningún jugador cumple los filtros elegidos.", "salta": None}
    return dict(zip(("fija", "salta"), generador(df, season, liga)))


def _por_temporada_y_liga(generador, df, seasons):
    """Una entrada por cada temporada x liga, más esas mismas restringidas a los
    sub-21 — que son las que se muestran con la casilla marcada.

    Las claves tienen que coincidir con las que arma el JS de la barra lateral:
    `temporada|liga`, y con el filtro puesto `temporada|liga|sub21`. Las dos
    versiones se calculan acá, en el build, porque los textos salen de operar
    sobre los datos y el sitio es estático: en el navegador no hay con qué
    rehacerlos."""
    variantes = [("", df)]
    if "sub21" in df.columns:
        variantes.append((f"|{SUB21_FILTER['col']}", df[df["sub21"] == True]))
    return {
        f"{s}|{liga}{sufijo}": _entrada(generador, datos, s, liga)
        for sufijo, datos in variantes
        for s in seasons
        for liga in [ins.LIGA_TODAS] + list(LEAGUE_ORDER)
    }


def _player_sidebar(fig, scatter_data, x_col, y_col, seasons, season_data, subtitle,
                     extra_traces=0, insights=None, point_filter=None):
    return sidebar_chart_html(
        fig, scatter_data, x_col, y_col, extra_traces=extra_traces,
        name_col="player", search_label="jugador", width=760, height=580,
        base_size=BASE_SIZE, season_data=season_data,
        custom_cols=["player", "team"], subtitle_template=subtitle,
        insights=insights, point_filter=point_filter,
    )


def sub21_filter(df):
    """El filtro, o None si los datos no traen edades.

    `fbref-players.csv` es opcional en la consolidación, así que el sitio se
    tiene que poder construir sin él: sin la columna (o sin un solo sub-21 que
    llegue al corte de minutos) la casilla no se dibuja, en vez de aparecer y
    no hacer nada al marcarla."""
    if "sub21" not in df.columns or not df["sub21"].fillna(False).any():
        return None
    return SUB21_FILTER


def chart_goals_vs_xg(df, seasons, season_data):
    scatter_data = season_data[seasons[-1]]
    mx = max(df["goals"].max(), df["xG"].max()) * 1.05

    fig = go.Figure()
    _scatter_traces(fig, scatter_data, "xG", "goals", "xG", "Goles", ".1f", ".0f")
    # La línea y=x va DESPUÉS de las trazas de liga: `sidebar_chart_html`
    # asume ese orden y si se agrega antes los índices quedan desalineados
    # (el filtro esconde la liga equivocada).
    fig.add_trace(go.Scatter(
        x=[0, mx], y=[0, mx], mode="lines",
        line=dict(color="#c3c2b7", dash="dash", width=1.4),
        hoverinfo="skip", showlegend=False,
    ))

    subtitle = ("¿Quién sobre/bajo-rendimió su expected goals? "
                f"Jugadores con ≥{MIN_MINUTES} min · {{temporada}}")
    fig.update_layout(
        title=dict(text="Goles vs. xG", subtitle=dict(text=subtitle.format(temporada=seasons[-1]))),
        xaxis_title="xG", yaxis_title="Goles",
        xaxis=dict(range=_padded(df["xG"])), yaxis=dict(range=_padded(df["goals"])),
    )
    return ChartPage(
        slug="goles-vs-xg", section=SECTION, title="Goles vs. xG",
        subtitle="Sobre/bajo-rendimiento de definición — un punto por jugador.",
        body_html=_player_sidebar(fig, scatter_data, "xG", "goals", seasons, season_data,
                                   subtitle, extra_traces=1,
                                   insights={
                                       "que_mirar": ins.goles_xg_que_mirar(),
                                       "por_que": ins.goles_xg_por_que(df),
                                       "dinamico": _por_temporada_y_liga(
                                           ins.goles_xg, df, seasons),
                                   },
                                   point_filter=sub21_filter(df)),
    )


def chart_assists_vs_xa(df, seasons, season_data):
    scatter_data = season_data[seasons[-1]]
    mx = max(df["a"].max(), df["xA"].max()) * 1.05

    fig = go.Figure()
    _scatter_traces(fig, scatter_data, "xA", "a", "xA", "Asistencias", ".1f", ".0f")
    fig.add_trace(go.Scatter(
        x=[0, mx], y=[0, mx], mode="lines",
        line=dict(color="#c3c2b7", dash="dash", width=1.4),
        hoverinfo="skip", showlegend=False,
    ))

    subtitle = ("¿Quién sobre/bajo-rendimió su expected assists? "
                f"Jugadores con ≥{MIN_MINUTES} min · {{temporada}}")
    fig.update_layout(
        title=dict(text="Asistencias vs. xA", subtitle=dict(text=subtitle.format(temporada=seasons[-1]))),
        xaxis_title="xA", yaxis_title="Asistencias",
        xaxis=dict(range=_padded(df["xA"])), yaxis=dict(range=_padded(df["a"])),
    )
    return ChartPage(
        slug="asistencias-vs-xa", section=SECTION, title="Asistencias vs. xA",
        subtitle="Sobre/bajo-rendimiento de creación — un punto por jugador.",
        body_html=_player_sidebar(fig, scatter_data, "xA", "a", seasons, season_data,
                                   subtitle, extra_traces=1,
                                   insights={
                                       "que_mirar": ins.asist_xa_que_mirar(),
                                       "por_que": ins.asist_xa_por_que(df),
                                       "dinamico": _por_temporada_y_liga(
                                           ins.asist_xa, df, seasons),
                                   },
                                   point_filter=sub21_filter(df)),
    )


def chart_profile(df, seasons, season_data):
    scatter_data = season_data[seasons[-1]]

    fig = go.Figure()
    _scatter_traces(fig, scatter_data, "xG90", "xA90", "xG90", "xA90", ".2f", ".2f")

    # Las líneas de referencia van en el promedio de las 5 temporadas, no en
    # el de la temporada mostrada: si se movieran con cada cambio, "estar por
    # encima del promedio" significaría algo distinto en cada temporada.
    fig.add_hline(y=df["xA90"].mean(), line=dict(color="#c3c2b7", width=1, dash="dot"))
    fig.add_vline(x=df["xG90"].mean(), line=dict(color="#c3c2b7", width=1, dash="dot"))

    subtitle = ("Killer puro, creador puro o todocampo — "
                f"jugadores con ≥{MIN_MINUTES} min · {{temporada}}")
    fig.update_layout(
        title=dict(text="Perfil ofensivo: xG90 vs. xA90",
                   subtitle=dict(text=subtitle.format(temporada=seasons[-1]))),
        xaxis_title="xG por 90'", yaxis_title="xA por 90'",
        xaxis=dict(range=_padded(df["xG90"])), yaxis=dict(range=_padded(df["xA90"])),
    )
    return ChartPage(
        slug="perfil-ofensivo", section=SECTION, title="Perfil ofensivo: xG90 vs. xA90",
        subtitle="Tasas por 90' — killer puro, creador puro o todocampo.",
        body_html=_player_sidebar(fig, scatter_data, "xG90", "xA90", seasons, season_data,
                                   subtitle,
                                   insights={
                                       "que_mirar": ins.perfil_que_mirar(),
                                       "por_que": ins.perfil_por_que(df),
                                       "dinamico": _por_temporada_y_liga(
                                           ins.perfil, df, seasons),
                                   },
                                   point_filter=sub21_filter(df)),
    )


def _box_page(df, seasons, *, y_col, y_axis_title, slug, title, subtitle, chart_title,
               chart_subtitle):
    insights = {
        "que_mirar": ins.nivel_que_mirar("gol" if y_col == "xG90" else "juego"),
        "por_que": ins.nivel_por_que(y_col),
        "dinamico": {s: dict(zip(("fija", "salta"), ins.nivel(df, y_col, s)))
                      for s in seasons},
    }
    fig, controls = league_box_season_html(
        df, y_col, y_axis_title, seasons, hover_fmt=".2f", name_col="player",
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


def chart_box_xg90(df, seasons):
    return _box_page(
        df, seasons, y_col="xG90", y_axis_title="xG90",
        slug="nivel-goleador-liga", title="Nivel goleador esperado por liga",
        subtitle="xG por 90' de todos los jugadores, agrupados por liga.",
        chart_title="Nivel goleador esperado por liga",
        chart_subtitle=f"xG por 90' — jugadores con ≥{MIN_MINUTES} min · {{temporada}}",
    )


def chart_box_xa90(df, seasons):
    return _box_page(
        df, seasons, y_col="xA90", y_axis_title="xA90",
        slug="nivel-creacion-liga", title="Nivel de creación esperado por liga",
        subtitle="xA por 90' de todos los jugadores, agrupados por liga.",
        chart_title="Nivel de creación esperado por liga",
        chart_subtitle=f"xA por 90' — jugadores con ≥{MIN_MINUTES} min · {{temporada}}",
    )


def chart_shot_map():
    """Mapa de calor de los tiros.

    Es el único gráfico de la sección que no sale de
    `players_all_seasons.csv` sino del detalle de tiros, y el único cuyo punto
    no es un jugador sino un remate. Entra igual en Jugadores porque responde a
    una pregunta de la misma familia que los otros: no cuántos goles hace
    alguien, sino desde dónde se remata."""
    df, descartes = shot_map.load(PROCESSED_DIR / "shots_all_seasons.csv")
    seasons = sorted(df["temporada"].unique())
    return ChartPage(
        slug="mapa-tiros", section=SECTION, title="Mapa de calor de los tiros",
        subtitle="Desde dónde se remata, con filtro de temporada y tipo de tiro.",
        body_html=shot_map.shot_map_html(df, descartes, seasons),
        kind="heatmap",
    )


def chart_explorer(df, seasons, season_data):
    """"Crea tu gráfico": el lector elige las dos variables.

    No lleva caja de "qué mirar" porque no hay un "acá" del que hablar: el par
    de variables lo elige quien mira. Lo que sí lleva es el r² del par elegido,
    calculado en el navegador sobre los puntos que están dibujados (ver
    `viz_theme.explorer_chart_html`)."""
    return ChartPage(
        slug="crea-tu-grafico-jugadores", section=SECTION, title="Crea tu gráfico",
        subtitle=f"Cruza cualquier par de las {len(VARIABLES)} variables de jugador — y el r² te dice si de verdad son dos cosas distintas o la misma medida dos veces.",
        body_html=explorer_chart_html(
            season_data, VARIABLES, name_col="player", search_label="jugador",
            entidad="jugadores", default_x="shots", default_y="goals",
            team_col="team", base_size=BASE_SIZE, point_filter=sub21_filter(df)),
        kind="explorer",
    )


def build(assets_dir) -> list:
    df = load_data()
    seasons = seasons_of(df)
    season_data = season_scatter_data(df, seasons)
    return [
        chart_goals_vs_xg(df, seasons, season_data),
        chart_assists_vs_xa(df, seasons, season_data),
        chart_profile(df, seasons, season_data),
        chart_box_xg90(df, seasons),
        chart_box_xa90(df, seasons),
        chart_shot_map(),
        chart_explorer(df, seasons, season_data),
    ]
