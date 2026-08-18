"""Gráficos a nivel de jugador para el sitio — mismo código/decisiones que
`code/eda_players.ipynb`, portado a funciones que devuelven `ChartPage`."""

import pandas as pd
import plotly.graph_objects as go

import insights as ins
from site_utils import PROCESSED_DIR, ChartPage
from viz_theme import (
    LEAGUE_ORDER, league_color, sidebar_chart_html, select_chart_html,
    league_box_season_html,
)

SECTION = "Jugadores"
MIN_MINUTES = 900
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
    return df[df["min"] >= MIN_MINUTES].reset_index(drop=True)


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


def _por_temporada_y_liga(generador, df, seasons, *args):
    """Una entrada por cada combinación temporada x liga; la clave tiene que
    coincidir con la que arma el JS de la barra lateral."""
    return {
        f"{s}|{liga}": dict(zip(("fija", "salta"), generador(df, s, *args, liga)))
        for s in seasons
        for liga in [ins.LIGA_TODAS] + list(LEAGUE_ORDER)
    }


def _player_sidebar(fig, scatter_data, x_col, y_col, seasons, season_data, subtitle,
                     extra_traces=0, insights=None):
    return sidebar_chart_html(
        fig, scatter_data, x_col, y_col, extra_traces=extra_traces,
        name_col="player", search_label="jugador", width=760, height=580,
        base_size=BASE_SIZE, season_data=season_data,
        custom_cols=["player", "team"], subtitle_template=subtitle,
        insights=insights,
    )


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
                                   }),
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
                                   }),
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
                                   }),
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
    ]
