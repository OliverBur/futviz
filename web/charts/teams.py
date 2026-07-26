"""Gráficos a nivel de equipo para el sitio — mismo código/decisiones que
`code/eda_teams.ipynb`, portado a funciones que devuelven `ChartPage` en vez
de mostrar el gráfico en un notebook. Si un gráfico cambia en el notebook,
el cambio se porta acá a mano (el notebook sigue siendo donde se prototipa)."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from site_utils import DATA_DIR, ChartPage, matplotlib_chart_body
from viz_theme import (
    LEAGUE_ORDER, SEQUENTIAL_BLUE, INK,
    league_color, sidebar_chart_html, plot_html, league_box_figure,
)

SECTION = "Equipos"


def load_data():
    raw_files = {
        "ov": "leagues_overall.csv",
        "sh": "leagues_shoot.csv",
        "pt": "leagues_playtime.csv",
        "ms": "leagues_misc.csv",
        "gk": "leagues_gk.csv",
    }
    league_blocks = [
        ("Bundesliga", 18), ("Serie A", 20), ("Ligue 1", 18),
        ("La Liga", 20), ("Premier League", 20),
    ]
    liga_col = [liga for liga, n in league_blocks for _ in range(n)]

    def flatten_columns(raw):
        cols = []
        for top, bot in raw.columns:
            top = "" if str(top).startswith("Unnamed") else str(top).strip()
            bot = str(bot).strip()
            cols.append(f"{top}_{bot}" if top else bot)
        raw.columns = cols
        return raw

    frames = {}
    for tag, fname in raw_files.items():
        raw = pd.read_csv(DATA_DIR / fname, header=[0, 1])
        raw = flatten_columns(raw)
        assert len(raw) == len(liga_col), f"{fname}: filas inesperadas"
        raw["liga"] = liga_col
        stat_cols = [c for c in raw.columns if c not in ("Squad", "liga")]
        raw = raw.rename(columns={c: f"{tag}_{c}" for c in stat_cols})
        frames[tag] = raw

    df = frames["ov"]
    for tag in ["sh", "pt", "ms", "gk"]:
        df = df.merge(frames[tag].drop(columns=["liga"]), on="Squad", how="left")

    df = df.drop(columns=["ms_Performance_PKwon", "ms_Performance_PKcon"])

    for col in ["ms_Performance_Fls", "ms_Performance_Off",
                "ms_Performance_Int", "ms_Performance_TklW", "ms_Performance_CrdY"]:
        df[col.replace("ms_Performance_", "p90_")] = df[col] / df["ms_90s"]

    df["liga"] = pd.Categorical(df["liga"], categories=LEAGUE_ORDER, ordered=True)
    cols = ["Squad", "liga"] + [c for c in df.columns if c not in ("Squad", "liga")]
    return df[cols]


def chart_radar_subplots(df, assets_dir):
    radar_metrics = [
        ("sh_Standard_Sh/90", "Tiros"), ("ov_Per 90 Minutes_Gls", "Goles"),
        ("sh_Standard_G/Sh", "G/Sh"), ("gk_Performance_CS%", "CS%"),
        ("p90_TklW", "Tackles"), ("p90_Int", "Intercep."),
        ("p90_Off", "Offsides"), ("p90_Fls", "Faltas"),
    ]
    metric_cols = [c for c, _ in radar_metrics]
    labels = [l for _, l in radar_metrics]

    league_avg = df.groupby("liga", observed=True)[metric_cols].mean()
    norm = league_avg / league_avg.max()

    n = len(labels)
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
    angles += angles[:1]

    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 5, figsize=(18, 4.8), subplot_kw=dict(polar=True))
    for ax, liga in zip(axes, LEAGUE_ORDER):
        values = norm.loc[liga, metric_cols].tolist()
        values += values[:1]
        color = league_color(liga)
        ax.plot(angles, values, color=color, linewidth=2.2, solid_capstyle="round",
                 marker="o", markersize=3.5, markerfacecolor=color,
                 markeredgecolor=INK["surface"], markeredgewidth=0.6, zorder=3)
        ax.fill(angles, values, color=color, alpha=0.20, zorder=2)
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(labels, fontsize=8.5, color=INK["secondary"])
        ax.tick_params(axis="x", pad=4)
        ax.set_yticks([0.5])
        ax.set_yticklabels([])
        ax.set_ylim(0, 1)
        ax.set_rlabel_position(0)
        ax.grid(color=INK["grid"], linewidth=0.7)
        ax.spines["polar"].set_color(INK["axis"])
        ax.spines["polar"].set_linewidth(1.0)
        ax.set_title(liga.upper(), color=color, fontsize=11, fontweight="bold", pad=13)

    fig.text(0.015, 0.99, "Perfil de estilo por liga", ha="left", va="top",
              fontsize=19, fontweight="bold", color=INK["primary"])
    fig.text(0.015, 0.92, "Promedio por equipo  ·  escala proporcional al máximo de las 5 ligas  ·  métricas por 90'",
              ha="left", va="top", fontsize=10.5, style="italic", color=INK["secondary"])
    fig.text(0.985, 0.02, "Datos: fbref  ·  temporada 2025-26",
              ha="right", va="bottom", fontsize=8.5, color=INK["muted"])
    plt.tight_layout(rect=[0, 0.03, 1, 0.83])

    body = matplotlib_chart_body(fig, "perfil-liga-radar", assets_dir, "Perfil de estilo por liga")
    plt.close(fig)
    return ChartPage(
        slug="perfil-liga-radar", section=SECTION, title="Perfil de estilo por liga",
        subtitle="8 métricas de estilo por liga, escaladas contra el máximo de las 5.",
        body_html=body, kind="radar",
    ), norm, metric_cols, labels, angles, league_avg, radar_metrics


def chart_radar_overlay(norm, metric_cols, labels, angles, league_avg, radar_metrics, assets_dir):
    import matplotlib.pyplot as plt
    fig = plt.figure(figsize=(12.2, 7.8))
    gs = fig.add_gridspec(1, 2, width_ratios=[1, 0.46], wspace=0.20,
                           left=0.045, right=0.97, top=0.85, bottom=0.11)
    ax = fig.add_subplot(gs[0], polar=True)
    tax = fig.add_subplot(gs[1])

    for liga in LEAGUE_ORDER:
        values = norm.loc[liga, metric_cols].tolist()
        values += values[:1]
        color = league_color(liga)
        ax.plot(angles, values, color=color, linewidth=2.4, solid_capstyle="round", label=liga, zorder=3)
        ax.fill(angles, values, color=color, alpha=0.06, zorder=2)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, fontsize=11, color=INK["secondary"])
    ax.tick_params(axis="x", pad=8)
    ax.set_yticks([0.25, 0.5, 0.75])
    ax.set_yticklabels([])
    ax.set_ylim(0, 1)
    ax.set_rlabel_position(0)
    ax.grid(color=INK["grid"], linewidth=0.7)
    ax.spines["polar"].set_color(INK["axis"])
    ax.spines["polar"].set_linewidth(1.0)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.06), ncol=5, fontsize=9.5,
              columnspacing=1.3, handletextpad=0.5, handlelength=1.3)

    sep_pct = ((1 - league_avg.min() / league_avg.max()) * 100).reindex(metric_cols).sort_values(ascending=False)
    col2label = dict(radar_metrics)

    tax.set_xlim(0, 1); tax.set_ylim(0, 1); tax.axis("off")
    tax.text(0.0, 0.965, "Separación por eje", transform=tax.transAxes, ha="left", va="top",
              fontsize=13, fontweight="bold", color=INK["primary"])
    tax.text(0.0, 0.905, "1 − (mín ÷ máx) de las 5 ligas  ·  más alto = más se separan", transform=tax.transAxes,
              ha="left", va="top", fontsize=8.5, style="italic", color=INK["secondary"])
    y0 = 0.80
    tax.text(0.0, y0, "EJE", ha="left", va="center", fontsize=8.5, fontweight="bold", color=INK["muted"])
    tax.text(1.0, y0, "SEPARACIÓN", ha="right", va="center", fontsize=8.5, fontweight="bold", color=INK["muted"])
    tax.plot([0, 1], [y0 - 0.035, y0 - 0.035], color=INK["axis"], lw=1.0)

    rows = list(sep_pct.items())
    ys = np.linspace(y0 - 0.11, 0.05, len(rows))
    bx0, bx1 = 0.30, 0.70
    maxv = sep_pct.max()
    for (col, val), y in zip(rows, ys):
        tax.text(0.0, y, col2label.get(col, col), ha="left", va="center", fontsize=10.5, color=INK["primary"])
        tax.plot([bx0, bx1], [y, y], color=INK["grid"], lw=3.2, solid_capstyle="round", zorder=1)
        tax.plot([bx0, bx0 + (bx1 - bx0) * (val / maxv)], [y, y], color=SEQUENTIAL_BLUE[3], lw=3.2,
                  solid_capstyle="round", zorder=2)
        tax.text(1.0, y, f"{val:.0f}%", ha="right", va="center", fontsize=10.5, color=INK["secondary"])

    fig.text(0.045, 0.975, "Dónde se separa cada liga", ha="left", va="top",
              fontsize=18, fontweight="bold", color=INK["primary"])
    fig.text(0.045, 0.925, "Las 5 ligas sobrepuestas, con el detalle de separación por eje a la derecha",
              ha="left", va="top", fontsize=10.5, style="italic", color=INK["secondary"])
    fig.text(0.97, 0.02, "Datos: fbref  ·  temporada 2025-26", ha="right", va="bottom",
              fontsize=8.5, color=INK["muted"])

    body = matplotlib_chart_body(fig, "perfil-liga-overlay", assets_dir, "Dónde se separa cada liga")
    plt.close(fig)
    return ChartPage(
        slug="perfil-liga-overlay", section=SECTION, title="Dónde se separa cada liga",
        subtitle="Las 5 formas del radar sobrepuestas, con la tabla de separación por eje.",
        body_html=body, kind="radar",
    )


def chart_def_efficiency(df):
    x_col, y_col = "sh_Standard_SoT%", "sh_Standard_G/SoT"
    x_mean, y_mean = df[x_col].mean(), df[y_col].mean()
    scatter_data = [(liga, df[df["liga"] == liga]) for liga in LEAGUE_ORDER]

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

    fig.update_layout(
        title=dict(text="Eficiencia de definición",
                   subtitle=dict(text="Precisión (llegar a puerta) vs. definición (marcar una vez ahí)")),
        xaxis_title="Precisión — % de tiros que van a puerta (SoT%)",
        yaxis_title="Definición — goles por tiro a puerta (G/SoT)",
        annotations=quadrant_annotations,
    )
    body = sidebar_chart_html(fig, scatter_data, x_col, y_col, base_annotations=quadrant_annotations,
                               width=760, height=580)
    return ChartPage(
        slug="eficiencia-definicion", section=SECTION, title="Eficiencia de definición",
        subtitle="Precisión (SoT%) vs. definición (G/SoT) — un punto por equipo.",
        body_html=body,
    )


def chart_gk_ranking(df, assets_dir):
    def zscore(s):
        return (s - s.mean()) / s.std()

    df = df.copy()
    df["gk_score"] = zscore(df["gk_Performance_Save%"]) - zscore(df["gk_Performance_GA90"])
    ranked = df.sort_values("gk_score", ascending=False)
    top12 = ranked.head(12)
    bot12 = ranked.tail(12).sort_values("gk_score")

    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(12, 6), sharex=True)
    for ax, sub, title in zip(axes, [top12, bot12], ["Mejores paredes", "Porterías más flojas"]):
        colors = [league_color(l) for l in sub["liga"]]
        ax.barh(sub["Squad"], sub["gk_score"], color=colors)
        ax.invert_yaxis()
        ax.set_title(title, fontsize=11)
        ax.axvline(0, color=INK["axis"], linewidth=0.8)

    fig.suptitle("Ranking de porterías (Save% − GA90, estandarizado)",
                 x=0.02, ha="left", fontsize=13, fontweight="bold")
    plt.tight_layout(rect=[0, 0, 1, 0.93])

    body = matplotlib_chart_body(fig, "ranking-porterias", assets_dir, "Ranking de porterías")
    plt.close(fig)
    return ChartPage(
        slug="ranking-porterias", section=SECTION, title="Ranking de porterías",
        subtitle="Índice Save% − GA90 (estandarizado) — mejores y peores 12 del conjunto de las 5 ligas.",
        body_html=body, kind="bar",
    )


def chart_gk_vs_result(df):
    df = df.copy()
    df["gk_ppm"] = (df["gk_Performance_W"] * 3 + df["gk_Performance_D"]) / df["gk_Playing Time_MP"]
    x_col3, y_col3 = "gk_Performance_CS%", "gk_ppm"
    scatter_data3 = [(liga, df[df["liga"] == liga]) for liga in LEAGUE_ORDER]

    fig = go.Figure()
    for liga, sub in scatter_data3:
        fig.add_trace(go.Scatter(
            x=sub[x_col3], y=sub[y_col3], mode="markers", name=liga,
            marker=dict(color=league_color(liga), size=[11] * len(sub), opacity=0.88,
                        line=dict(color=INK["surface"], width=1)),
            customdata=sub["Squad"],
            hovertemplate=f"<b>%{{customdata}}</b><br>{liga}<br>CS%%: %{{x:.1f}}%<br>Puntos/partido: %{{y:.2f}}<extra></extra>",
        ))

    fig.update_layout(
        title=dict(text="¿Cuánto pesa la portería en el resultado?",
                   subtitle=dict(text="Porterías a cero vs. puntos por partido")),
        xaxis_title="Porterías a cero (%)", yaxis_title="Puntos por partido",
    )
    body = sidebar_chart_html(fig, scatter_data3, x_col3, y_col3, width=760, height=580)
    return ChartPage(
        slug="porteria-vs-resultado", section=SECTION, title="Portería vs. resultado del equipo",
        subtitle="Porterías a cero (%) vs. puntos por partido — un punto por equipo.",
        body_html=body,
    )


def chart_gk_demand(df):
    x_col4, y_col4 = "gk_Performance_SoTA", "gk_Performance_Save%"
    x_mean4, y_mean4 = df[x_col4].mean(), df[y_col4].mean()
    scatter_data4 = [(liga, df[df["liga"] == liga]) for liga in LEAGUE_ORDER]

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

    fig.update_layout(
        title=dict(text="Exigencia vs. rendimiento",
                   subtitle=dict(text="Tiros a puerta enfrentados vs. tasa de atajadas")),
        xaxis_title="Tiros a puerta enfrentados en la temporada (SoTA)",
        yaxis_title="Tasa de atajadas (Save%)",
        annotations=quadrant_annotations4,
    )
    body = sidebar_chart_html(fig, scatter_data4, x_col4, y_col4, base_annotations=quadrant_annotations4,
                               width=760, height=580)
    return ChartPage(
        slug="exigencia-rendimiento", section=SECTION, title="Exigencia vs. rendimiento",
        subtitle="Tiros a puerta enfrentados (SoTA) vs. tasa de atajadas (Save%) — un punto por equipo.",
        body_html=body,
    )


def chart_parity(df):
    fig = league_box_figure(df, "pt_Team Success_PPM", "Puntos por partido", hover_fmt=".2f", annotate_cv=True)
    fig.update_layout(
        title=dict(text="Paridad competitiva",
                   subtitle=dict(text="Puntos por partido de cada equipo, agrupados por liga · % = coeficiente de variación")),
        yaxis_title="Puntos por partido", xaxis_title=None,
    )
    return ChartPage(
        slug="paridad-competitiva", section=SECTION, title="Paridad competitiva",
        subtitle="Dispersión de puntos por partido dentro de cada liga.",
        body_html=plot_html(fig, width=800, height=520), kind="box",
    )


def chart_age(df):
    fig = league_box_figure(df, "ov_Age", "Edad", hover_fmt=".1f")
    fig.update_layout(
        title=dict(text="Edad de plantilla",
                   subtitle=dict(text="Edad promedio de cada equipo, agrupados por liga")),
        yaxis_title="Edad promedio", xaxis_title=None,
    )
    return ChartPage(
        slug="edad-plantilla", section=SECTION, title="Edad de plantilla",
        subtitle="Edad promedio por equipo, agrupados por liga.",
        body_html=plot_html(fig, width=800, height=520), kind="box",
    )


def chart_discipline(df):
    fig = league_box_figure(df, "p90_CrdY", "Amarillas/90", hover_fmt=".2f")
    fig.update_layout(
        title=dict(text="Disciplina: tarjetas amarillas",
                   subtitle=dict(text="Amarillas por 90 minutos de cada equipo, agrupados por liga")),
        yaxis_title="Amarillas por 90", xaxis_title=None,
    )
    return ChartPage(
        slug="disciplina-amarillas", section=SECTION, title="Disciplina: tarjetas amarillas",
        subtitle="Amarillas por 90' de cada equipo, agrupados por liga.",
        body_html=plot_html(fig, width=800, height=520), kind="box",
    )


def build(assets_dir) -> list:
    df = load_data()
    pages = []

    radar1_page, norm, metric_cols, labels, angles, league_avg, radar_metrics = chart_radar_subplots(df, assets_dir)
    pages.append(radar1_page)
    pages.append(chart_radar_overlay(norm, metric_cols, labels, angles, league_avg, radar_metrics, assets_dir))
    pages.append(chart_def_efficiency(df))
    pages.append(chart_gk_ranking(df, assets_dir))
    pages.append(chart_gk_vs_result(df))
    pages.append(chart_gk_demand(df))
    pages.append(chart_parity(df))
    pages.append(chart_age(df))
    pages.append(chart_discipline(df))
    return pages
