"""Análisis de Machine Learning para el sitio — versión narrada de
`code/ml_style_clusters.ipynb`.

A diferencia de `teams.py`/`players.py`, que producen un `ChartPage` por
gráfico, acá se produce un `ArticlePage`: el análisis sostiene un argumento
(los grupos que parecían estilos eran, en buena medida, la tabla de
posiciones) y ese argumento se pierde si se parte en gráficos sueltos.

Igual que los otros módulos de `charts/`, el pipeline se porta a mano desde
el notebook — el notebook sigue siendo donde se prototipa.
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from site_utils import SEASON, SEASON_DIR, ArticlePage
from viz_theme import (CLUSTER_COLORS, DIVERGING, FUENTE_FBREF, INK, SEQUENTIAL_BLUE,
                        plot_html)

SECTION = "Machine Learning"
RNG = 42

DIVERGING_SCALE = [[0.0, DIVERGING["neg"]], [0.5, DIVERGING["mid"]], [1.0, DIVERGING["pos"]]]

# Las 19 features de la primera pasada (con métricas de eficacia adentro:
# es justamente lo que el análisis termina cuestionando).
FEATURES = {
    "ov_Poss": "Posesión (%)",
    "ov_Per 90 Minutes_Gls": "Goles/90",
    "ov_Per 90 Minutes_Ast": "Asistencias/90",
    "sh_Standard_Sh/90": "Tiros/90",
    "sh_Standard_SoT/90": "Tiros a puerta/90",
    "sh_Standard_SoT%": "Precisión de tiro (%)",
    "sh_Standard_G/Sh": "Goles por tiro",
    "sh_Standard_G/SoT": "Goles por tiro a puerta",
    "p90_CrdY": "Amarillas/90",
    "p90_CrdR": "Rojas/90",
    "p90_Fls": "Faltas cometidas/90",
    "p90_Fld": "Faltas recibidas/90",
    "p90_Off": "Fuera de juego/90",
    "p90_Crs": "Centros/90",
    "p90_Int": "Intercepciones/90",
    "p90_TklW": "Tackles ganados/90",
    "gk_Performance_GA90": "Goles recibidos/90",
    "gk_Performance_Save%": "Atajadas (%)",
    "p90_SoTA": "Tiros a puerta recibidos/90",
}

# Etiquetas cortas para el biplot: con los nombres largos el texto se pisa
# en el abanico de métricas ofensivas y además estira los ejes.
SHORT_LABELS = [
    "Posesión", "Gls/90", "Ast/90", "Sh/90", "SoT/90", "SoT%", "G/Sh", "G/SoT",
    "Amarillas", "Rojas", "Faltas", "Faltas rec.", "Fuera juego", "Centros",
    "Intercep.", "Tackles", "GA/90", "Save%", "SoTA/90",
]

# Segunda pasada: solo conducta. Fuera goles, asistencias, conversión,
# precisión, goles recibidos y atajadas (miden eficacia, o sea nivel), y
# fuera las rojas (casi puro ruido: ~3.6 por temporada).
FEATURES_ESTILO = {
    "ov_Poss": "Posesión (%)",
    "sh_Standard_Sh/90": "Tiros/90",
    "p90_Crs": "Centros/90",
    "p90_Off": "Fuera de juego/90",
    "p90_Fls": "Faltas cometidas/90",
    "p90_Fld": "Faltas recibidas/90",
    "p90_CrdY": "Amarillas/90",
    "p90_Int": "Intercepciones/90",
    "p90_TklW": "Tackles ganados/90",
    "p90_SoTA": "Tiros a puerta recibidos/90",
}

ESTILO_NOMBRES = {
    0: "Vertical y áspero",
    1: "Ataque por banda",
    2: "Dominio central",
    3: "Sin duelos",
    4: "Replegados y expuestos",
    5: "Trabado, sin bandas",
}

# Los mismos nombres partidos en dos líneas, para el eje del mapa de calor:
# en una sola línea no entran y Plotly los rota hasta pisar el título.
ESTILO_NOMBRES_CORTOS = {
    0: "Vertical<br>y áspero",
    1: "Ataque<br>por banda",
    2: "Dominio<br>central",
    3: "Sin<br>duelos",
    4: "Replegados<br>y expuestos",
    5: "Trabado,<br>sin bandas",
}


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
        raw = flatten_columns(pd.read_csv(SEASON_DIR / fname, header=[0, 1]))
        assert len(raw) == len(liga_col), f"{fname}: filas inesperadas"
        raw["liga"] = liga_col
        stat_cols = [c for c in raw.columns if c not in ("Squad", "liga")]
        frames[tag] = raw.rename(columns={c: f"{tag}_{c}" for c in stat_cols})

    df = frames["ov"]
    for tag in ["sh", "pt", "ms", "gk"]:
        df = df.merge(frames[tag].drop(columns=["liga"]), on="Squad", how="left")

    # Las columnas `90s` son partidos jugados del equipo (verificado: iguales
    # a MP en los 96), así que esto da tasas por partido — comparables aunque
    # los equipos lleven distinto número de jornadas (33 a 38).
    for col in ["ms_Performance_Fls", "ms_Performance_Off", "ms_Performance_Int",
                "ms_Performance_TklW", "ms_Performance_CrdY", "ms_Performance_CrdR",
                "ms_Performance_Crs", "ms_Performance_Fld"]:
        df[col.replace("ms_Performance_", "p90_")] = df[col] / df["ms_90s"]
    df["p90_SoTA"] = df["gk_Performance_SoTA"] / df["gk_Playing Time_90s"]
    return df.copy()


# ---------------------------------------------------------------------------
# helpers de maquetado — la prosa va en columna angosta, los gráficos anchos
# ---------------------------------------------------------------------------

def _prose(html):
    return f'<div class="wrap">{html}</div>'


def _heading(step, title, anchor):
    return (f'<div class="wrap"><h2 id="{anchor}">'
            f'<span class="step">{step}</span>{title}</h2></div>')


def _figure(fig, caption, width=880, height=560, fuente=FUENTE_FBREF):
    """El default es FBref porque este análisis sale de las tablas de equipo;
    los de `ml_xg.py`, que salen del detalle de tiros, pasan Understat (ver el
    envoltorio `_figure` de ese módulo)."""
    return (f'<figure class="wrap-wide"><div class="chart-scroll">'
            f'{plot_html(fig, width=width, height=height, fuente=fuente)}</div>'
            f'<figcaption>{caption}</figcaption></figure>')


def _callout(title, html, warn=False):
    cls = "callout warn" if warn else "callout"
    return (f'<div class="wrap"><div class="{cls}">'
            f'<div class="callout-title">{title}</div>{html}</div></div>')


def _stat(value, label):
    return (f'<div class="wrap"><div class="stat"><div class="stat-value">{value}</div>'
            f'<div class="stat-label">{label}</div></div></div>')


def _table(headers, rows, wide=False):
    head = "".join(f"<th>{h}</th>" for h in headers)
    body = "".join(
        "<tr>" + "".join(
            f'<td class="num">{c}</td>' if isinstance(c, (int, float)) else f"<td>{c}</td>"
            for c in row
        ) + "</tr>"
        for row in rows
    )
    wrap = "wrap-wide" if wide else "wrap"
    return (f'<div class="{wrap}"><div class="table-scroll"><table>'
            f"<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div></div>")


# ---------------------------------------------------------------------------
# gráficos
# ---------------------------------------------------------------------------

def _fig_biplot(scores, loadings, feature_cols, pc1_var, pc2_var, hover):
    arrow_scale = (np.abs(scores[:, :2]).max() / np.abs(loadings[:, :2]).max()) * 0.82
    tips = loadings[:, :2] * arrow_scale
    angles = np.arctan2(tips[:, 1], tips[:, 0])

    # Los choques de etiquetas se resuelven en píxeles (no empujando por el
    # radio): varias métricas ofensivas comparten dirección Y magnitud, así
    # que separarlas en unidades de dato no alcanza y estira los ejes.
    plot_w, plot_h, gap, line_h, char_w = 700, 500, 15, 14, 5.6
    pts = np.vstack([scores[:, :2], tips])
    span = pts.max(axis=0) - pts.min(axis=0)
    x_range = [pts[:, 0].min() - span[0] * 0.10, pts[:, 0].max() + span[0] * 0.16]
    y_range = [pts[:, 1].min() - span[1] * 0.08, pts[:, 1].max() + span[1] * 0.08]

    def to_px(x, y):
        return ((x - x_range[0]) / (x_range[1] - x_range[0]) * plot_w,
                (1 - (y - y_range[0]) / (y_range[1] - y_range[0])) * plot_h)

    shift, placed = np.zeros(len(feature_cols), dtype=int), []
    for i in np.argsort(-np.hypot(tips[:, 0], tips[:, 1])):
        dx, dy = np.cos(angles[i]), np.sin(angles[i])
        px, py = to_px(tips[i, 0] + dx * 0.4, tips[i, 1] + dy * 0.4)
        w = len(SHORT_LABELS[i]) * char_w + 4
        x0 = px if dx > 0.25 else px - w if dx < -0.25 else px - w / 2
        down = 0
        while down <= 90:
            box = (x0, py + down - line_h / 2, x0 + w, py + down + line_h / 2)
            if not any(box[0] < b[2] and b[0] < box[2] and box[1] < b[3] and b[1] < box[3]
                       for b in placed):
                break
            down += gap
        placed.append((x0, py + down - line_h / 2, x0 + w, py + down + line_h / 2))
        shift[i] = -down

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=scores[:, 0], y=scores[:, 1], mode="markers",
        marker=dict(size=9, color=SEQUENTIAL_BLUE[4], opacity=0.82,
                    line=dict(color=INK["surface"], width=1.5)),
        customdata=hover,
        hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]}"
                      "<br>PC1: %{x:.2f}<br>PC2: %{y:.2f}<extra></extra>",
        showlegend=False,
    ))

    annotations = []
    for i, short in enumerate(SHORT_LABELS):
        fx, fy = tips[i]
        dx, dy = np.cos(angles[i]), np.sin(angles[i])
        annotations.append(dict(
            x=fx, y=fy, ax=0, ay=0, xref="x", yref="y", axref="x", ayref="y",
            showarrow=True, arrowhead=2, arrowsize=1.1, arrowwidth=1.2,
            arrowcolor=INK["secondary"], opacity=0.85,
        ))
        annotations.append(dict(
            x=fx + dx * 0.4, y=fy + dy * 0.4, xref="x", yref="y", yshift=int(shift[i]),
            showarrow=False, text=short, font=dict(size=9.5, color=INK["secondary"]),
            xanchor="left" if dx > 0.25 else "right" if dx < -0.25 else "center",
            yanchor="middle",
        ))

    fig.add_hline(y=0, line=dict(color=INK["grid"], width=1))
    fig.add_vline(x=0, line=dict(color=INK["grid"], width=1))
    fig.update_layout(
        title=dict(text="El vocabulario de estilo",
                   subtitle=dict(text="Cada flecha es una métrica: hacia dónde empuja y cuánto pesa")),
        xaxis=dict(title=f"PC1 ({pc1_var:.1%} de la varianza)", range=x_range),
        yaxis=dict(title=f"PC2 ({pc2_var:.1%} de la varianza)", range=y_range),
        annotations=annotations,
    )
    return fig


def _fig_clusters(scores, labels, hover, pc1_var, pc2_var):
    fig = go.Figure()
    for c in sorted(set(labels)):
        m = labels == c
        fig.add_trace(go.Scatter(
            x=scores[m, 0], y=scores[m, 1], mode="markers", name=f"Grupo {c}",
            marker=dict(size=10, color=CLUSTER_COLORS[c], opacity=0.88,
                        line=dict(color=INK["surface"], width=1.5)),
            customdata=hover[m],
            hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]}<extra></extra>",
        ))
    fig.add_hline(y=0, line=dict(color=INK["grid"], width=1))
    fig.add_vline(x=0, line=dict(color=INK["grid"], width=1))
    fig.update_layout(
        title=dict(text="Los seis grupos, en el plano principal",
                   subtitle=dict(text="Pasa el mouse sobre un punto para ver el equipo")),
        xaxis=dict(title=f"PC1 ({pc1_var:.1%})"),
        yaxis=dict(title=f"PC2 ({pc2_var:.1%})"),
        legend=dict(orientation="h", y=-0.17, x=0),
    )
    return fig


def _fig_pc1_vs_ppm(scores, ppm, labels, hover, pc1_var):
    fig = go.Figure()
    for c in sorted(set(labels)):
        m = labels == c
        fig.add_trace(go.Scatter(
            x=scores[m, 0], y=ppm[m], mode="markers", name=f"Grupo {c}",
            marker=dict(size=10, color=CLUSTER_COLORS[c], opacity=0.88,
                        line=dict(color=INK["surface"], width=1.5)),
            customdata=hover[m],
            hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]}"
                          "<br>%{y:.2f} puntos por partido<extra></extra>",
        ))
    r = np.corrcoef(scores[:, 0], ppm)[0, 1]
    fit = np.poly1d(np.polyfit(scores[:, 0], ppm, 1))
    xs = np.array([scores[:, 0].min(), scores[:, 0].max()])
    fig.add_trace(go.Scatter(x=xs, y=fit(xs), mode="lines", name=f"r = {r:.2f}",
                             line=dict(color=INK["muted"], width=2, dash="dash"),
                             hoverinfo="skip"))
    fig.update_layout(
        title=dict(text="El primer componente es la tabla de posiciones",
                   subtitle=dict(text="Los puntos por partido nunca entraron al modelo")),
        xaxis=dict(title=f'PC1 — supuesto "dominio ofensivo" ({pc1_var:.1%})'),
        yaxis=dict(title="Puntos por partido (fuera del modelo)"),
        legend=dict(orientation="h", y=-0.17, x=0),
    )
    return fig


def _fig_profile(profile, labels_x, feature_names, title):
    """Mapa de calor de perfiles. Sin subtítulo a propósito: con las
    etiquetas de columna arriba (`side='top'`) el subtítulo les cae encima,
    y en el artículo esa explicación ya va en el pie de figura."""
    fig = go.Figure(go.Heatmap(
        z=profile.T.values, x=labels_x, y=feature_names,
        colorscale=DIVERGING_SCALE, zmid=0, xgap=2, ygap=2,
        colorbar=dict(title=dict(text="z-score", side="right"), thickness=14, outlinewidth=0),
        hovertemplate="%{x}<br>%{y}<br>%{z:+.2f} desviaciones vs. el promedio<extra></extra>",
    ))
    fig.update_layout(
        title=dict(text=title),
        # tickangle=0 + etiquetas en dos líneas: en una sola línea Plotly las
        # rota en diagonal y quedan ilegibles encima del título.
        xaxis=dict(side="top", title=None, showgrid=False, tickangle=0,
                    tickfont=dict(size=11)),
        yaxis=dict(autorange="reversed", title=None, showgrid=False),
        margin=dict(l=190, t=125),
    )
    return fig


# ---------------------------------------------------------------------------
# el análisis
# ---------------------------------------------------------------------------

def build_estilos_article() -> ArticlePage:
    df = load_data()
    ppm = df["pt_Team Success_PPM"].values
    hover = np.stack([df["Squad"], df["liga"].astype(str)], axis=-1)

    # --- pasada 1: 19 features, sin blanquear -----------------------------
    feature_cols = list(FEATURES)
    X = pd.DataFrame(StandardScaler().fit_transform(df[feature_cols]), columns=feature_cols)
    pca_full = PCA(random_state=RNG).fit(X)
    explained = pca_full.explained_variance_ratio_
    n_components = int(np.searchsorted(np.cumsum(explained), 0.80) + 1)

    pca = PCA(n_components=n_components, random_state=RNG)
    scores = pca.fit_transform(X)
    loadings = pca.components_.T * np.sqrt(pca.explained_variance_)
    pc1_var, pc2_var = pca.explained_variance_ratio_[:2]

    inertias, silhouettes = [], []
    for k in range(2, 11):
        km = KMeans(n_clusters=k, random_state=RNG, n_init=10).fit(scores)
        inertias.append(km.inertia_)
        silhouettes.append(silhouette_score(scores, km.labels_))
    ganancia = [(inertias[i - 1] - inertias[i]) / inertias[i - 1] * 100
                for i in range(1, len(inertias))]

    K = 6
    labels = KMeans(n_clusters=K, random_state=RNG, n_init=10).fit_predict(scores)
    df["grupo"] = labels

    r_pc1 = np.corrcoef(scores[:, 0], ppm)[0, 1]
    pred = df.groupby("grupo")["pt_Team Success_PPM"].transform("mean")
    eta2 = 1 - ((ppm - pred) ** 2).sum() / ((ppm - ppm.mean()) ** 2).sum()

    # test de nulo: ¿hay clusters o es una nube continua?
    rng = np.random.default_rng(0)
    cov = np.cov(X, rowvar=False)
    nulo_rows = []
    for k in [2, 4, 6, 8]:
        real = silhouette_score(scores, KMeans(n_clusters=k, random_state=RNG,
                                               n_init=10).fit_predict(scores))
        sims = []
        for _ in range(30):
            xn = rng.multivariate_normal(np.zeros(len(feature_cols)), cov, size=len(df))
            sn = PCA(n_components=n_components, random_state=RNG).fit_transform(
                StandardScaler().fit_transform(xn))
            sims.append(silhouette_score(sn, KMeans(n_clusters=k, random_state=RNG,
                                                    n_init=10).fit_predict(sn)))
        nulo_rows.append((k, round(real, 3), round(float(np.mean(sims)), 3),
                          round(float((real - np.mean(sims)) / np.std(sims)), 1)))

    profile_z = X.groupby(labels).mean()

    # --- pasada 2: solo conducta + whitening ------------------------------
    estilo_cols = list(FEATURES_ESTILO)
    X_estilo = pd.DataFrame(StandardScaler().fit_transform(df[estilo_cols]), columns=estilo_cols)
    n_estilo = int(np.searchsorted(
        np.cumsum(PCA(random_state=RNG).fit(X_estilo).explained_variance_ratio_), 0.80) + 1)
    scores_estilo = PCA(n_components=n_estilo, whiten=True, random_state=RNG).fit_transform(X_estilo)
    labels_estilo = KMeans(n_clusters=K, random_state=RNG, n_init=10).fit_predict(scores_estilo)
    df["estilo"] = labels_estilo

    pred_e = df.groupby("estilo")["pt_Team Success_PPM"].transform("mean")
    eta2_estilo = 1 - ((ppm - pred_e) ** 2).sum() / ((ppm - ppm.mean()) ** 2).sum()
    profile_estilo = X_estilo.groupby(labels_estilo).mean()

    def ejemplos(grupo_col, c, n=5):
        sub = df[df[grupo_col] == c].nlargest(n, "pt_Team Success_PPM")
        return ", ".join(sub["Squad"])

    # --- el artículo -------------------------------------------------------
    parts = []

    parts.append(_heading("01 · La pregunta", "¿Existen los estilos de juego?", "pregunta"))
    parts.append(_prose(f"""
<p>Todo el mundo habla de estilos: que un equipo es de posesión, que otro
presiona alto, que aquel se repliega. Pero si nadie le dice a una computadora
qué es un estilo y le doy solamente los números de los <strong>96 equipos de
las cinco grandes ligas</strong>, ¿los encuentra sola?</p>
<p>Eso es el <em>aprendizaje no supervisado</em>: no hay respuestas correctas
con las que entrenar, solo datos y la pregunta de si tienen estructura. Le
di {len(feature_cols)} métricas de la temporada 2025-26 —posesión, tiros,
faltas, centros, tackles, atajadas— y le pedí que agrupara.</p>
<p>Funcionó. Y al revisar por qué funcionaba, apareció que estaba midiendo otra
cosa. Ese desvío terminó siendo más interesante que el plan original, así que
el recorrido está contado tal como pasó.</p>"""))

    parts.append(_heading("02 · El método", "Comprimir 19 métricas en unos pocos ejes", "pca"))
    parts.append(_prose(f"""
<p>Las métricas se pisan entre sí: un equipo que tira mucho también suele
rematar mucho a puerta. <strong>PCA</strong> resume esa redundancia en unos
pocos ejes independientes que conservan casi toda la información — acá bastan
<strong>{n_components} componentes para el 80%</strong> de la variación.</p>
<p>El gráfico de abajo es un <em>biplot</em>: los puntos son equipos y las
flechas, las métricas originales. Flechas que apuntan al mismo lado son
métricas que van juntas; flechas largas son las que más pesan en este plano.</p>"""))
    parts.append(_figure(
        _fig_biplot(scores, loadings, feature_cols, pc1_var, pc2_var, hover),
        "Las métricas ofensivas (derecha) apuntan casi todas en la misma dirección: "
        "esa redundancia es lo que hace que el primer eje pese tanto.",
        width=880, height=680))
    parts.append(_prose(f"""
<p>El primer eje se lleva el <strong>{pc1_var:.0%}</strong> de la variación, y
lo forman posesión, goles, asistencias y tiros tirando todos para el mismo
lado. Lo bauticé <em>dominio ofensivo</em>. Guarda ese nombre: en la sección
5 se cae.</p>"""))

    parts.append(_heading("03 · Cuántos grupos", "Elegir un número sin elegirlo a dedo", "k"))
    parts.append(_prose(f"""
<p>K-means necesita que le diga cuántos grupos buscar. Para no inventarlo se
miran dos señales. La <strong>inercia</strong> mide qué tan apretados quedan
los grupos: cada grupo nuevo la baja, y el "codo" está donde deja de
compensar. Acá cada grupo hasta el sexto baja la inercia entre
{min(ganancia[:5]):.0f}% y {max(ganancia[:5]):.0f}%; el séptimo solo
<strong>{ganancia[5]:.1f}%</strong>, la mitad. Ahí está el codo.</p>
<p>La <strong>silueta</strong> mide qué tan separados quedan, y su máximo está
en k=2 ({max(silhouettes):.3f}). Pero k=2 solo parte a los equipos en "buenos"
y "malos", que es casi ordenar la tabla. Entre las divisiones más finas, k=6 es
la mejor. Me quedé con <strong>seis</strong>.</p>"""))

    parts.append(_callout("Un atajo que no tomé", """
<p>La red de similitud que probé después también encontró 6 comunidades por
su cuenta, y era tentador usarlo como confirmación. No lo es: ese número
depende de cuántos vecinos se conecten en el grafo, y moviendo ese parámetro da
9, 7, 6, 5 o 3. Daba 6 <em>porque</em> elegí 5 vecinos. Coincidencias así
son fáciles de vender y no prueban nada.</p>"""))

    parts.append(_figure(
        _fig_clusters(scores, labels, hover, pc1_var, pc2_var),
        "Los seis grupos que encontró el modelo, sin que nadie le dijera qué buscar. "
        "Se ven ordenados de izquierda a derecha: eso, que parece un detalle, es la pista.",
        width=880, height=620))

    parts.append(_heading("04 · La prueba que casi nadie corre",
                          "¿Y si no hay grupos?", "nulo"))
    parts.append(_prose("""
<p>Una silueta de 0.16 es baja. ¿Baja comparada con qué? La única forma de
saberlo es correr el mismo procedimiento sobre <strong>datos falsos sin grupos
por construcción</strong>: una nube con la misma forma general pero sin
estructura interna. Si k-means saca la misma nota de una nube sin grupos que de
los equipos reales, entonces no encontró grupos.</p>"""))
    parts.append(_table(
        ["Grupos", "Silueta real", "Nube sin grupos", "Diferencia (z)"],
        [(f"k={k}", real, nulo, f"{z:+.1f}") for k, real, nulo, z in nulo_rows]))
    parts.append(_callout("No hay tribus, hay un continuo", """
<p>La diferencia nunca supera 1.5 desviaciones: el resultado real es
indistinguible del de una nube sin estructura. <strong>Los equipos europeos no
se dividen en tribus con fronteras naturales.</strong></p>
<p>Eso no tira el análisis, pero cambia qué significa: los seis grupos son una
<em>segmentación</em> —como los rangos de edad o los tramos de un impuesto—,
útil para describir y comparar, siempre que no se afirme que existe una línea
real entre uno y otro.</p>""", warn=True))

    parts.append(_heading("05 · El giro", "Los grupos no eran estilos", "giro"))
    parts.append(_prose("""
<p>Con los seis grupos armados, tocaba ponerles nombre. Y ahí apareció algo
raro: ordenándolos por cualquiera de las columnas ofensivas, salían siempre en
el mismo orden. Demasiado prolijo.</p>
<p>Había una forma directa de comprobar la sospecha. Los <strong>puntos por
partido</strong> se dejaron deliberadamente fuera del modelo, por ser resultado
y no estilo. Si los grupos igual los predicen, es que reconstruyeron la tabla
sin permiso.</p>"""))
    parts.append(_figure(
        _fig_pc1_vs_ppm(scores, ppm, labels, hover, pc1_var),
        "Cada punto es un equipo. El eje horizontal salió solo de métricas de juego; "
        "el vertical son los puntos que el modelo nunca vio.",
        width=880, height=580))
    parts.append(_stat(f"r = {r_pc1:.2f}",
                       "Correlación entre el primer componente y los puntos por partido, "
                       "una variable que se excluyó del modelo a propósito"))
    parts.append(_prose(f"""
<p>El "dominio ofensivo" no era un estilo: <strong>era qué tan bueno es cada
equipo</strong>. Los seis grupos explican el <strong>{eta2:.0%}</strong> de la
variación en puntos y, ordenados por su promedio, quedan como una tabla de
posiciones.</p>
<p>¿Cómo entró el resultado si lo había excluido? Por una grieta en mi propio
criterio: saqué la <em>diferencia de gol</em> por ser resultado, pero dejé
<em>goles marcados</em> y <em>goles recibidos</em>, que son exactamente
sus dos ingredientes. Excluí la etiqueta y conservé la receta.</p>
<p>Hubo una segunda causa, más técnica: al agrupar, los ejes conservaban su
tamaño original, y el primero pesa unas ocho veces más que el último. Aunque
las métricas hubieran sido perfectas, la balanza ya estaba inclinada.</p>"""))

    parts.append(_heading("06 · La corrección", "Quitar el nivel y volver a mirar", "correccion"))
    parts.append(_prose(f"""
<p>Se rehízo todo con dos cambios. Primero, fuera las métricas de
<em>eficacia</em>: goles, asistencias, conversión, precisión, goles recibidos y
atajadas. Todas responden <em>qué tan bien le sale</em>, no <em>qué intenta</em>.
Quedan {len(estilo_cols)} métricas de pura conducta: cuánta pelota tiene, cuánto
tira, por dónde ataca, cuánto interrumpe y cuánto le llegan. Segundo, se
igualó el peso de los ejes para que ninguno mande por tamaño.</p>
<p>El peso del nivel cae del <strong>{eta2:.0%}</strong> al
<strong>{eta2_estilo:.0%}</strong>. No baja a cero, y está bien que así sea: en
el fútbol real los buenos equipos <em>de verdad</em> tienen más la pelota y
tiran más. Eso es realidad, no contaminación.</p>"""))
    parts.append(_figure(
        _fig_profile(profile_estilo, [ESTILO_NOMBRES_CORTOS[c] for c in profile_estilo.index],
                     [FEATURES_ESTILO[f] for f in estilo_cols],
                     "Qué hace distinto a cada estilo"),
        "<strong>Azul</strong> = por encima del promedio de los 96 equipos, "
        "<strong>rojo</strong> = por debajo. Ahora los grupos se distinguen por conducta: "
        "por dónde atacan, cuánto interrumpen y cuánto les llegan.",
        width=880, height=520))

    parts.append(_table(
        ["Estilo", "Qué lo define", "Ejemplos"],
        [
            (f"<strong>{ESTILO_NOMBRES[2]}</strong>",
             "Posesión y tiros por las nubes, pero pocos centros y las menos faltas: atacan por dentro y casi no interrumpen.",
             ejemplos("estilo", 2)),
            (f"<strong>{ESTILO_NOMBRES[1]}</strong>",
             "Los más centros del estudio, con buena posesión y volumen de tiro. Control, pero llegando por fuera.",
             ejemplos("estilo", 1)),
            (f"<strong>{ESTILO_NOMBRES[0]}</strong>",
             "Los más fuera de juego y las más amarillas: ataque de ruptura a la espalda, defensa a base de interrumpir.",
             ejemplos("estilo", 0)),
            (f"<strong>{ESTILO_NOMBRES[5]}</strong>",
             "Faltas altas en los dos sentidos y los menos centros: partido cortado, poco juego por fuera.",
             ejemplos("estilo", 5)),
            (f"<strong>{ESTILO_NOMBRES[3]}</strong>",
             "Los menos tackles e intercepciones de todos. Ni presionan ni cortan: dejan jugar y esperan.",
             ejemplos("estilo", 3)),
            (f"<strong>{ESTILO_NOMBRES[4]}</strong>",
             "Los más tiros a puerta en contra, con la menor posesión y volumen de tiro. El bloque que aguanta.",
             ejemplos("estilo", 4)),
        ], wide=True))

    parts.append(_callout("La señal de que ahora sí mide estilo", f"""
<p>El grupo <em>{ESTILO_NOMBRES[3]}</em> junta a
<strong>{ejemplos("estilo", 3, 3)}</strong> con equipos de mitad de tabla como
Freiburg o Cremonese. Son niveles muy distintos que comparten una forma de no
defender: son los que menos tackles e intercepciones hacen de las cinco ligas.</p>
<p>En la primera versión eso era imposible — el nivel los mandaba a grupos
separados antes de mirarles el estilo.</p>"""))

    parts.append(_heading("07 · Conclusión", "Qué queda de todo esto", "conclusion"))
    parts.append(_prose(f"""
<p><strong>Con datos públicos, lo que más separa a los equipos europeos no es
cómo juegan sino qué tan buenos son.</strong> No hizo falta creerlo: el primer
eje correlaciona {r_pc1:.2f} con unos puntos que nunca entraron al modelo. Es
la intuición de cualquiera que mire estas ligas —los mejores son muy mejores y
eso tiñe todas las métricas— pero acá está medida.</p>
<p><strong>Y no hay arquetipos naturales, hay un continuo.</strong> Los grupos
son cortes útiles sobre una nube, no tribus. Cualquier análisis que prometa
"los 6 tipos de equipo" debería poder mostrar esta prueba.</p>
<p>Quitando la eficacia, sí aparece estilo: atacar por dentro o por banda,
buscar la espalda o cortar con falta, presionar o dejar jugar. Para ir más
lejos harían falta métricas de acción y ubicación —dónde recupera, con qué
velocidad progresa— que los datos públicos no traen. Con ellas el estilo
dejaría de tener que inferirse desde faltas y centros.</p>"""))

    return ArticlePage(
        slug="estilos-de-juego",
        section=SECTION,
        title="¿Existe el estilo de juego, o solo el nivel?",
        subtitle="Agrupé a los 96 equipos sin decirle al modelo qué buscar. "
                  "Encontró seis grupos — y después descubrí qué estaba midiendo en realidad.",
        deck="Un ejercicio de aprendizaje no supervisado sobre las cinco grandes ligas: "
             "PCA, k-means y una prueba incómoda que cambió la conclusión del análisis.",
        body_html="".join(parts),
        meta=[
            ("Datos", "96 equipos · top 5 ligas · 2025-26"),
            ("Métodos", "PCA · K-means · test de nulo"),
            ("Métricas", f"{len(feature_cols)} de estilo, sin datos avanzados"),
            ("Lectura", "~8 min"),
        ],
        fuente=f"{FUENTE_FBREF} · temporada {SEASON}",
    )


def build(assets_dir=None) -> list:
    return [build_estilos_article()]
