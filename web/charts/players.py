"""Gráficos a nivel de jugador para el sitio — mismo código/decisiones que
`code/eda_players.ipynb`, portado a funciones que devuelven `ChartPage`."""

import html

import pandas as pd
import plotly.graph_objects as go

from site_utils import DATA_DIR, ChartPage
from viz_theme import LEAGUE_ORDER, league_color, sidebar_chart_html, plot_html, league_box_figure

SECTION = "Jugadores"
MIN_MINUTES = 900

FILES = {
    "bundes-players.csv": "Bundesliga",
    "seriea-players.csv": "Serie A",
    "ligue1-players.csv": "Ligue 1",
    "laliga-players.csv": "La Liga",
    "premier-players.csv": "Premier League",
}


def load_data():
    dfs = []
    for fname, liga in FILES.items():
        d = pd.read_csv(DATA_DIR / fname, sep=";", encoding="utf-8")
        d["liga"] = liga
        dfs.append(d)
    df = pd.concat(dfs, ignore_index=True)

    df["player"] = df["player"].apply(html.unescape)
    df["team"] = df["team"].str.split(",").str[-1].str.strip()

    return df[df["min"] >= MIN_MINUTES].reset_index(drop=True)


def chart_goals_vs_xg(df):
    mx = max(df["goals"].max(), df["xG"].max()) * 1.05

    fig = go.Figure()
    scatter_data = []
    for liga in LEAGUE_ORDER:
        sub = df[df["liga"] == liga]
        scatter_data.append((liga, sub))
        fig.add_trace(go.Scatter(
            x=sub["xG"], y=sub["goals"], mode="markers", name=liga,
            marker=dict(color=league_color(liga), size=8, opacity=0.75,
                        line=dict(width=0.5, color="white")),
            customdata=sub[["player", "team"]],
            hovertemplate="<b>%{customdata[0]}</b> (%{customdata[1]})<br>"
                           "xG: %{x:.1f}<br>Goles: %{y:.0f}<extra></extra>",
        ))

    fig.add_trace(go.Scatter(
        x=[0, mx], y=[0, mx], mode="lines",
        line=dict(color="#c3c2b7", dash="dash", width=1.4),
        hoverinfo="skip", showlegend=False,
    ))

    fig.update_layout(
        title=dict(text="Goles vs. xG",
                   subtitle=dict(text="¿Quién sobre/bajo-rendimió su expected goals? "
                                       f"Jugadores con ≥{MIN_MINUTES} min, 2025-26")),
        xaxis_title="xG", yaxis_title="Goles",
    )
    body = sidebar_chart_html(fig, scatter_data, "xG", "goals", extra_traces=1,
                               name_col="player", search_label="jugador", width=760, height=580)
    return ChartPage(
        slug="goles-vs-xg", section=SECTION, title="Goles vs. xG",
        subtitle="Sobre/bajo-rendimiento de definición — un punto por jugador.",
        body_html=body,
    )


def chart_assists_vs_xa(df):
    mx2 = max(df["a"].max(), df["xA"].max()) * 1.05

    fig2 = go.Figure()
    scatter_data2 = []
    for liga in LEAGUE_ORDER:
        sub = df[df["liga"] == liga]
        scatter_data2.append((liga, sub))
        fig2.add_trace(go.Scatter(
            x=sub["xA"], y=sub["a"], mode="markers", name=liga,
            marker=dict(color=league_color(liga), size=8, opacity=0.75,
                        line=dict(width=0.5, color="white")),
            customdata=sub[["player", "team"]],
            hovertemplate="<b>%{customdata[0]}</b> (%{customdata[1]})<br>"
                           "xA: %{x:.1f}<br>Asistencias: %{y:.0f}<extra></extra>",
        ))

    fig2.add_trace(go.Scatter(
        x=[0, mx2], y=[0, mx2], mode="lines",
        line=dict(color="#c3c2b7", dash="dash", width=1.4),
        hoverinfo="skip", showlegend=False,
    ))

    fig2.update_layout(
        title=dict(text="Asistencias vs. xA",
                   subtitle=dict(text="¿Quién sobre/bajo-rendimió su expected assists? "
                                       f"Jugadores con ≥{MIN_MINUTES} min, 2025-26")),
        xaxis_title="xA", yaxis_title="Asistencias",
    )
    body = sidebar_chart_html(fig2, scatter_data2, "xA", "a", extra_traces=1,
                               name_col="player", search_label="jugador", width=760, height=580)
    return ChartPage(
        slug="asistencias-vs-xa", section=SECTION, title="Asistencias vs. xA",
        subtitle="Sobre/bajo-rendimiento de creación — un punto por jugador.",
        body_html=body,
    )


def chart_profile(df):
    fig3 = go.Figure()
    scatter_data3 = []
    for liga in LEAGUE_ORDER:
        sub = df[df["liga"] == liga]
        scatter_data3.append((liga, sub))
        fig3.add_trace(go.Scatter(
            x=sub["xG90"], y=sub["xA90"], mode="markers", name=liga,
            marker=dict(color=league_color(liga), size=8, opacity=0.75,
                        line=dict(width=0.5, color="white")),
            customdata=sub[["player", "team"]],
            hovertemplate="<b>%{customdata[0]}</b> (%{customdata[1]})<br>"
                           "xG90: %{x:.2f}<br>xA90: %{y:.2f}<extra></extra>",
        ))

    xm, ym = df["xG90"].mean(), df["xA90"].mean()
    fig3.add_hline(y=ym, line=dict(color="#c3c2b7", width=1, dash="dot"))
    fig3.add_vline(x=xm, line=dict(color="#c3c2b7", width=1, dash="dot"))

    fig3.update_layout(
        title=dict(text="Perfil ofensivo: xG90 vs. xA90",
                   subtitle=dict(text="Killer puro, creador puro o todocampo — "
                                       f"jugadores con ≥{MIN_MINUTES} min, 2025-26")),
        xaxis_title="xG por 90'", yaxis_title="xA por 90'",
    )
    body = sidebar_chart_html(fig3, scatter_data3, "xG90", "xA90",
                               name_col="player", search_label="jugador", width=760, height=580)
    return ChartPage(
        slug="perfil-ofensivo", section=SECTION, title="Perfil ofensivo: xG90 vs. xA90",
        subtitle="Tasas por 90' — killer puro, creador puro o todocampo.",
        body_html=body,
    )


def chart_box_xg90(df):
    figb1 = league_box_figure(df, "xG90", "xG por 90'", hover_fmt=".2f", name_col="player")
    figb1.update_layout(
        title=dict(text="Nivel goleador esperado por liga",
                   subtitle=dict(text=f"xG por 90' — jugadores con ≥{MIN_MINUTES} min, 2025-26")),
        yaxis_title="xG90",
    )
    return ChartPage(
        slug="nivel-goleador-liga", section=SECTION, title="Nivel goleador esperado por liga",
        subtitle="xG por 90' de todos los jugadores, agrupados por liga.",
        body_html=plot_html(figb1, width=800, height=520),
    )


def chart_box_xa90(df):
    figb2 = league_box_figure(df, "xA90", "xA por 90'", hover_fmt=".2f", name_col="player")
    figb2.update_layout(
        title=dict(text="Nivel de creación esperado por liga",
                   subtitle=dict(text=f"xA por 90' — jugadores con ≥{MIN_MINUTES} min, 2025-26")),
        yaxis_title="xA90",
    )
    return ChartPage(
        slug="nivel-creacion-liga", section=SECTION, title="Nivel de creación esperado por liga",
        subtitle="xA por 90' de todos los jugadores, agrupados por liga.",
        body_html=plot_html(figb2, width=800, height=520),
    )


def build(assets_dir) -> list:
    df = load_data()
    return [
        chart_goals_vs_xg(df),
        chart_assists_vs_xa(df),
        chart_profile(df),
        chart_box_xg90(df),
        chart_box_xa90(df),
    ]
