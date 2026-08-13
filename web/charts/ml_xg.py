"""Los dos análisis que salen del dato de tiros: construir un modelo de xG, y
usarlo para preguntar si la definición es una habilidad.

Van juntos en un módulo porque comparten lo caro: cargar los 221.922 tiros,
armar las features geométricas y entrenar los modelos. `_preparar()` hace todo
eso una sola vez y los dos artículos lo reusan.

Portado 1:1 desde `code/ml_xg_model.ipynb` y `code/ml_finishing_skill.ipynb`.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

sys.path.insert(0, str(Path(__file__).resolve().parent))

from site_utils import DATA_DIR, ArticlePage  # noqa: E402
from viz_theme import SEQUENTIAL_BLUE, DIVERGING, INK, plot_html  # noqa: E402

# Los helpers de maquetado del artículo ya existen en `ml.py` y son los mismos
# para cualquier análisis largo: se reusan en vez de duplicarlos.
from ml import _callout, _figure, _heading, _prose, _stat, _table  # noqa: E402

SECTION = "Machine Learning"
RNG = 42

LARGO, ANCHO, PORTERIA = 105.0, 68.0, 7.32
SEASONS = ["2021-22", "2022-23", "2023-24", "2024-25", "2025-26"]

_CACHE = {}


# ---------------------------------------------------------------------------
# datos y modelos (se calculan una vez para los dos artículos)
# ---------------------------------------------------------------------------

def _preparar():
    """Tiros con features, el modelo principal y el xG fuera de muestra.

    El xG fuera de muestra se calcula dejando una temporada fuera cada vez: es
    imprescindible para el análisis de definición, porque un modelo entrenado
    con los goles de un jugador le sube el xG hasta borrarle la habilidad.
    """
    if _CACHE:
        return _CACHE

    from xgboost import XGBClassifier

    d = pd.read_csv(DATA_DIR / "processed" / "shots_all_seasons.csv", encoding="utf-8-sig")
    d = d[d.result != "Own Goal"].copy()
    d["gol"] = (d.result == "Goal").astype(int)

    penales = d[d.situation == "Penalty"]
    _CACHE["penales"] = {"n": len(penales), "conversion": penales.gol.mean(),
                          "xg_understat": penales.xg.mean()}

    d = d[d.situation != "Penalty"].copy()

    px, py = d.location_x * LARGO, d.location_y * ANCHO
    d["dist"] = np.hypot(LARGO - px, ANCHO / 2 - py)
    a = np.hypot(LARGO - px, ANCHO / 2 + PORTERIA / 2 - py)
    b = np.hypot(LARGO - px, ANCHO / 2 - PORTERIA / 2 - py)
    d["angulo"] = np.arccos(np.clip((a ** 2 + b ** 2 - PORTERIA ** 2) / (2 * a * b), -1, 1))
    d["dist_y"] = (d.location_y - 0.5).abs() * ANCHO
    d["asistido"] = d.assist_player.notna().astype(int)
    d["rebote"] = (d.groupby(["game_id", "team", "minute"])["shot_id"]
                    .transform("size") > 1).astype(int)

    # Fuera los remates con la portería prácticamente invisible (menos de 2° de
    # ángulo): son goles olímpicos tirados desde el banderín, y su muestra está
    # sesgada por selección — Understat solo cuenta un córner como tiro si iba a
    # puerta, así que ahí conviven 22 remates con 12 goles. Sin este filtro el
    # modelo predice 0.85 de xG en la esquina; con él, 0.08. Las métricas no se
    # mueven (son 22 tiros de 221.922).
    ANGULO_MINIMO = np.radians(2)
    _CACHE["olimpicos"] = {"n": int((d.angulo < ANGULO_MINIMO).sum()),
                            "goles": int(d.loc[d.angulo < ANGULO_MINIMO, "gol"].sum())}
    d = d[d.angulo >= ANGULO_MINIMO].copy()

    X = pd.get_dummies(
        d[["dist", "angulo", "dist_y", "location_x", "location_y",
           "asistido", "rebote", "situation", "body_part"]],
        columns=["situation", "body_part"], dtype=float)
    y = d.gol.values

    params = dict(learning_rate=0.05, max_depth=5, min_child_weight=20,
                  subsample=0.8, colsample_bytree=0.8, reg_lambda=1.0,
                  eval_metric="logloss", random_state=RNG, n_jobs=4)

    # modelo principal: partición temporal, la que se reporta en la tabla
    tr = d.temporada.isin(SEASONS[:3]).values
    va = (d.temporada == SEASONS[3]).values
    te = (d.temporada == SEASONS[4]).values
    modelo = XGBClassifier(n_estimators=2000, early_stopping_rounds=50, **params)
    modelo.fit(X[tr], y[tr], eval_set=[(X[va], y[va])], verbose=False)

    # xG fuera de muestra para todos los tiros
    d["xg_propio"] = np.nan
    for s in SEASONS:
        fuera = (d.temporada == s).values
        m = XGBClassifier(n_estimators=800, **params)
        m.fit(X[~fuera], y[~fuera], verbose=False)
        d.loc[fuera, "xg_propio"] = m.predict_proba(X[fuera])[:, 1]

    _CACHE.update({"d": d, "X": X, "y": y, "modelo": modelo,
                    "tr": tr, "va": va, "te": te, "feats": list(X.columns)})
    return _CACHE


def _predecir_frontal(modelo, feats, dist_m, parte, situacion="Open Play"):
    """xG de un tiro de frente a la portería, a `dist_m` metros."""
    fila = pd.DataFrame([{c: 0.0 for c in feats}])
    fila["dist"], fila["dist_y"] = dist_m, 0.0
    fila["angulo"] = np.arccos(np.clip((2 * dist_m ** 2 - PORTERIA ** 2) / (2 * dist_m ** 2), -1, 1))
    fila["location_x"], fila["location_y"] = 1 - dist_m / LARGO, 0.5
    fila["asistido"] = 1.0
    fila[f"situation_{situacion}"] = 1.0
    fila[f"body_part_{parte}"] = 1.0
    return modelo.predict_proba(fila[feats])[0, 1]


# ---------------------------------------------------------------------------
# gráficos — artículo del modelo de xG
# ---------------------------------------------------------------------------

def _fig_calibracion(p_nuestro, p_understat, real):
    cal = pd.DataFrame({"nuestro": p_nuestro, "understat": p_understat, "gol": real})
    cal["bin"] = pd.qcut(cal.nuestro, 12, labels=False, duplicates="drop")
    curva = cal.groupby("bin").agg(n=("gol", "size"), nuestro=("nuestro", "mean"),
                                    understat=("understat", "mean"), real=("gol", "mean"))
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[0, 0.65], y=[0, 0.65], mode="lines", name="calibración perfecta",
                             line=dict(color=INK["axis"], width=1.5, dash="dash"), hoverinfo="skip"))
    for col, nombre, color in [("nuestro", "Mi modelo", SEQUENTIAL_BLUE[6]),
                                ("understat", "xG de Understat", DIVERGING["neg"])]:
        fig.add_trace(go.Scatter(
            x=curva[col], y=curva["real"], mode="lines+markers", name=nombre,
            line=dict(color=color, width=2.5),
            marker=dict(size=9, line=dict(color=INK["surface"], width=1.5)),
            customdata=curva["n"],
            hovertemplate=f"<b>{nombre}</b><br>predice %{{x:.3f}}<br>entra %{{y:.3f}}"
                          "<br>(%{customdata} tiros)<extra></extra>"))
    fig.update_layout(
        title=dict(text="Cuando el modelo dice 0.30, ¿entra el 30%?",
                   subtitle=dict(text="Por debajo de la diagonal el modelo promete más goles "
                                      "de los que entran")),
        xaxis=dict(title="xG predicho (media del grupo)"),
        yaxis=dict(title="Goles reales (proporción)"),
        legend=dict(orientation="h", y=-0.17, x=0))
    return fig


def _fig_sesgo_understat(por_temp):
    fig = go.Figure()
    fig.add_trace(go.Bar(x=por_temp.index, y=por_temp.goles, name="Goles reales",
                         marker=dict(color=SEQUENTIAL_BLUE[2], line=dict(width=0)),
                         hovertemplate="%{x}<br>%{y} goles<extra></extra>"))
    fig.add_trace(go.Bar(x=por_temp.index, y=por_temp.xg_understat, name="xG de Understat",
                         marker=dict(color=DIVERGING["neg"], line=dict(width=0)),
                         hovertemplate="%{x}<br>%{y:.0f} de xG<extra></extra>"))
    fig.add_trace(go.Scatter(x=por_temp.index, y=por_temp["sesgo"], name="Sobreestimación (%)",
                             yaxis="y2", mode="lines+markers",
                             line=dict(color=INK["secondary"], width=2.5),
                             marker=dict(size=10, line=dict(color=INK["surface"], width=2)),
                             hovertemplate="%{x}<br>sobreestima %{y:.1f}%<extra></extra>"))
    fig.update_layout(
        barmode="group", bargap=0.3,
        title=dict(text="El xG de Understat se aleja de la realidad, año tras año",
                   subtitle=dict(text="Mismos tiros, sin penales · la brecha pasa de 7% a 17%")),
        xaxis=dict(title=None), yaxis=dict(title="Goles / xG acumulado"),
        yaxis2=dict(title="Sobreestimación (%)", overlaying="y", side="right",
                    showgrid=False, rangemode="tozero"),
        legend=dict(orientation="h", y=-0.17, x=0))
    return fig


def _fig_superficie(modelo, feats, d):
    nx, ny = 60, 44
    xs, ys = np.linspace(0.55, 0.995, nx), np.linspace(0.06, 0.94, ny)
    malla = pd.DataFrame([(a, b) for b in ys for a in xs], columns=["location_x", "location_y"])
    mx, my = malla.location_x * LARGO, malla.location_y * ANCHO
    malla["dist"] = np.hypot(LARGO - mx, ANCHO / 2 - my)
    pa = np.hypot(LARGO - mx, ANCHO / 2 + PORTERIA / 2 - my)
    pb = np.hypot(LARGO - mx, ANCHO / 2 - PORTERIA / 2 - my)
    malla["angulo"] = np.arccos(np.clip((pa ** 2 + pb ** 2 - PORTERIA ** 2) / (2 * pa * pb), -1, 1))
    malla["dist_y"] = (malla.location_y - 0.5).abs() * ANCHO
    for c in feats:
        if c not in malla:
            malla[c] = 0.0
    malla["asistido"] = 1.0
    malla["situation_Open Play"] = 1.0
    malla["body_part_Right Foot"] = 1.0
    z = modelo.predict_proba(malla[feats])[:, 1].reshape(ny, nx)

    # No se dibuja donde el modelo no tiene con qué sostener la predicción. En
    # las franjas laterales hay ~84 tiros contra ~30.000 en el centro a la misma
    # distancia, y encima la mitad son tiros libres directos: el mapa pide
    # jugada abierta pero ahí el modelo casi solo ha visto faltas, así que
    # devolvía valores altísimos pegados a la banda. Un modelo de árboles no
    # avisa de que está extrapolando; hay que taparlo a mano.
    jugada = d[d.situation == "Open Play"]
    bordes_x = np.r_[xs - (xs[1] - xs[0]) / 2, xs[-1] + (xs[1] - xs[0]) / 2]
    bordes_y = np.r_[ys - (ys[1] - ys[0]) / 2, ys[-1] + (ys[1] - ys[0]) / 2]
    conteo, _, _ = np.histogram2d(jugada.location_y, jugada.location_x,
                                  bins=[bordes_y, bordes_x])
    # se suma el vecindario 3x3 para no castigar a una celda por el ruido de su
    # propio recuento
    vecindario = sum(np.roll(np.roll(conteo, i, 0), j, 1)
                     for i in (-1, 0, 1) for j in (-1, 0, 1))
    z = np.where(vecindario >= 15, z, np.nan)

    fig = go.Figure(go.Heatmap(
        z=z, x=xs * LARGO, y=ys * ANCHO, colorscale=SEQUENTIAL_BLUE, zsmooth=False,
        colorbar=dict(title=dict(text="xG", side="right"), thickness=14, outlinewidth=0),
        hovertemplate="a %{x:.0f} m de la línea de fondo<br>%{y:.0f} m de ancho"
                      "<br>xG %{z:.3f}<extra></extra>"))
    for x0, y0, x1, y1 in [(LARGO - 16.5, ANCHO / 2 - 20.16, LARGO, ANCHO / 2 + 20.16),
                            (LARGO - 5.5, ANCHO / 2 - 9.16, LARGO, ANCHO / 2 + 9.16)]:
        fig.add_shape(type="rect", x0=x0, y0=y0, x1=x1, y1=y1,
                      line=dict(color=INK["surface"], width=1.5), opacity=0.55)
    fig.add_shape(type="line", x0=LARGO, y0=ANCHO / 2 - PORTERIA / 2, x1=LARGO,
                  y1=ANCHO / 2 + PORTERIA / 2, line=dict(color=DIVERGING["neg"], width=4))
    fig.update_layout(
        title=dict(text="El mapa de valor del tiro",
                   subtitle=dict(text="xG de un remate con el pie derecho, de jugada y asistido")),
        xaxis=dict(title="Metros", constrain="domain"),
        yaxis=dict(title=None, scaleanchor="x", scaleratio=1, showticklabels=False))
    return fig


def _fig_cabeza(modelo, feats):
    distancias = np.arange(4, 31)
    fig = go.Figure()
    for parte, nombre, color in [("Right Foot", "Pie derecho", SEQUENTIAL_BLUE[6]),
                                  ("Head", "Cabeza", DIVERGING["neg"])]:
        serie = [_predecir_frontal(modelo, feats, x, parte) for x in distancias]
        fig.add_trace(go.Scatter(x=distancias, y=serie, mode="lines", name=nombre,
                                 line=dict(color=color, width=3),
                                 hovertemplate=f"<b>{nombre}</b><br>a %{{x}} m: "
                                               "xG %{y:.3f}<extra></extra>"))
    fig.update_layout(
        title=dict(text="A igual distancia, un cabezazo vale mucho menos",
                   subtitle=dict(text="Tiro de frente, jugada abierta · la tabla cruda daba "
                                      "9.9% para los dos")),
        xaxis=dict(title="Distancia a la portería (m)"), yaxis=dict(title="xG predicho"),
        legend=dict(orientation="h", y=-0.17, x=0))
    return fig


def _fig_importancia(modelo):
    imp = (pd.Series(modelo.get_booster().get_score(importance_type="gain"))
           .sort_values(ascending=True))
    fig = go.Figure(go.Bar(
        x=imp.values, y=imp.index, orientation="h",
        marker=dict(color=SEQUENTIAL_BLUE[5], line=dict(width=0)),
        hovertemplate="<b>%{y}</b><br>ganancia media %{x:.1f}<extra></extra>"))
    fig.update_layout(
        title=dict(text="De qué se agarra el modelo",
                   subtitle=dict(text="Ganancia media por corte · la distancia pesa poco porque "
                                      "el ángulo ya la contiene")),
        xaxis=dict(title="Ganancia"), yaxis=dict(title=None), margin=dict(l=190))
    return fig


# ---------------------------------------------------------------------------
# gráficos — artículo de la definición
# ---------------------------------------------------------------------------

def _fig_nulo_z(z_obs, z_nulo):
    fig = go.Figure()
    bins = dict(start=-4, end=4, size=0.25)
    fig.add_trace(go.Histogram(x=z_nulo, xbins=bins, name="Si la definición no existiera",
                               marker=dict(color=INK["grid"]), opacity=0.85,
                               hovertemplate="z %{x}<br>%{y} jugadores<extra></extra>"))
    fig.add_trace(go.Histogram(x=z_obs, xbins=bins, name="Observado",
                               marker=dict(color=SEQUENTIAL_BLUE[5]), opacity=0.7,
                               hovertemplate="z %{x}<br>%{y} jugadores<extra></extra>"))
    fig.update_layout(
        barmode="overlay",
        title=dict(text="La definición existe, pero apenas ensancha la nube",
                   subtitle=dict(text="Sobre-actuación normalizada por jugador-temporada "
                                      "(≥30 tiros)")),
        xaxis=dict(title="z  (goles sobre lo esperado, en desviaciones binomiales)"),
        yaxis=dict(title="Jugador-temporada"),
        legend=dict(orientation="h", y=-0.19, x=0))
    return fig


def _fig_persistencia(A, B, C, D):
    fig = make_subplots(rows=1, cols=2, horizontal_spacing=0.11,
                        subplot_titles=(f"Definición — r = {np.corrcoef(A, B)[0,1]:.2f}",
                                        f"Volumen de tiro — r = {np.corrcoef(C, D)[0,1]:.2f}"))
    for j, (xx, yy, color) in enumerate([(A, B, DIVERGING["neg"]),
                                          (C, D, SEQUENTIAL_BLUE[5])], start=1):
        fig.add_trace(go.Scatter(x=xx, y=yy, mode="markers",
                                 marker=dict(size=5.5, color=color, opacity=0.45,
                                             line=dict(width=0)),
                                 hovertemplate="t: %{x:.1f}<br>t+1: %{y:.1f}<extra></extra>",
                                 showlegend=False), row=1, col=j)
        fit = np.poly1d(np.polyfit(xx, yy, 1))
        xs = np.array([min(xx), max(xx)])
        fig.add_trace(go.Scatter(x=xs, y=fit(xs), mode="lines",
                                 line=dict(color=INK["secondary"], width=2, dash="dash"),
                                 hoverinfo="skip", showlegend=False), row=1, col=j)
    for col, t in [(1, "goles sobre lo esperado por 100 tiros"), (2, "tiros por temporada")]:
        fig.update_xaxes(title_text=f"Temporada t — {t}", row=1, col=col)
        fig.update_yaxes(title_text="Temporada t+1", row=1, col=col)
    fig.update_layout(
        title=dict(text="Así se ve una habilidad, y así se ve la definición",
                   subtitle=dict(text="Mismos jugadores y mismas temporadas en los dos paneles")),
        margin=dict(t=150))
    return fig


def _fig_credibilidad(pj):
    o = pj.sort_values("tiros")
    fig = go.Figure(go.Scatter(
        x=o.tiros, y=o.credibilidad, mode="markers",
        marker=dict(size=5, color=SEQUENTIAL_BLUE[5], opacity=0.5, line=dict(width=0)),
        customdata=o.player,
        hovertemplate="<b>%{customdata}</b><br>%{x} tiros<br>credibilidad %{y:.2f}<extra></extra>"))
    fig.add_hline(y=0.5, line=dict(color=INK["axis"], width=1, dash="dash"))
    fig.add_annotation(x=pj.tiros.max(), y=0.5, text="la mitad es señal", showarrow=False,
                       xanchor="right", yanchor="bottom",
                       font=dict(size=10.5, color=INK["muted"]))
    fig.update_layout(
        title=dict(text="Cuántos tiros hacen falta para creerle a un delantero",
                   subtitle=dict(text="Fracción de la sobre-actuación observada que es "
                                      "habilidad y no azar")),
        xaxis=dict(title="Tiros en cinco temporadas"),
        yaxis=dict(title="Credibilidad", range=[0, 0.6]), showlegend=False)
    return fig


# ---------------------------------------------------------------------------
# artículo 1 — el modelo de xG
# ---------------------------------------------------------------------------

def build_xg_article() -> ArticlePage:
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import log_loss, brier_score_loss, roc_auc_score

    c = _preparar()
    d, X, y, modelo, feats = c["d"], c["X"], c["y"], c["modelo"], c["feats"]
    tr, te = c["tr"], c["te"]
    pen, olimpicos = c["penales"], c["olimpicos"]

    p_xgb = modelo.predict_proba(X[te])[:, 1]
    p_und = d.xg.values[te]

    logit = LogisticRegression(max_iter=1000).fit(X.loc[tr, ["dist", "angulo"]], y[tr])
    p_log = logit.predict_proba(X.loc[te, ["dist", "angulo"]])[:, 1]

    def fila(nombre, p):
        return [nombre, f"{log_loss(y[te], p):.4f}", f"{brier_score_loss(y[te], p):.4f}",
                f"{roc_auc_score(y[te], p):.3f}", f"{(p.sum()/y[te].sum()-1)*100:+.1f}%"]

    crudo = d.groupby("body_part").agg(tiros=("gol", "size"), tasa=("gol", "mean"),
                                        dist=("dist", "mean"))
    por_temp = d.groupby("temporada").agg(goles=("gol", "sum"), xg_understat=("xg", "sum"))
    por_temp["sesgo"] = (por_temp.xg_understat / por_temp.goles - 1) * 100

    # dónde se concentra el exceso: agrupando por el propio xG de Understat se
    # ve que casi todo viene de las ocasiones claras, no de los tiros malos
    banda = d.copy()
    banda["tramo"] = pd.cut(banda.xg, [0, 0.03, 0.06, 0.10, 0.15, 0.25, 0.40, 1.0])
    por_banda = banda.groupby("tramo", observed=True).agg(
        tiros=("gol", "size"), predice=("xg", "mean"), entra=("gol", "mean"))
    por_banda["exceso"] = (por_banda.predice - por_banda.entra) * por_banda.tiros

    p = []
    p.append(_heading("01", "Un número que decide cosas caras", "problema"))
    p.append(_prose(
        "<p>Cada vez que alguien dice que un equipo «mereció ganar» o que «generó más "
        "ocasiones que el rival», hay un número atrás. Casi siempre es el mismo: el xG, "
        "los goles esperados. Y hoy ese número interviene en decisiones que cuestan "
        "dinero — cuánto vale un delantero en el mercado, si un entrenador conserva el "
        "puesto, qué fichaje se aprueba y cuál no.</p>"
        "<p>Lo que responde es sencillo: <strong>dado desde dónde y cómo se remató, ¿qué "
        "tan probable era que entrara?</strong> Pero esa respuesta no la da el fútbol, la "
        "da un modelo que alguien construyó tomando decisiones, y que puede estar "
        "equivocado. Casi nadie lo comprueba, porque comprobarlo exige tener los datos y "
        "un modelo propio con el cual comparar.</p>"
        "<p>Eso es exactamente lo que hice: construí uno desde cero con 221.922 "
        "tiros de cinco temporadas, y después lo usé para auditar el que todo el mundo "
        "cita. Understat publica su xG para cada tiro, así que hay contra qué medirse — "
        "y, como se va a ver, también algo que encontrarle.</p>"))

    p.append(_heading("02", "Por qué no basta una tabla", "tabla"))
    p.append(_prose(
        "<p>Antes de entrenar nada, el ejemplo que justifica todo el trabajo. Ésta es "
        "la tasa de gol cruda según con qué se remató:</p>"))
    p.append(_table(
        ["Parte del cuerpo", "Tiros", "Tasa de gol", "Distancia media"],
        [[i, f"{int(r.tiros):,}".replace(",", "."), f"{r.tasa:.1%}", f"{r.dist:.1f} m"]
         for i, r in crudo.iterrows()]))
    p.append(_prose(
        "<p><strong>Los cabezazos convierten al 9.9%, igual que los pies.</strong> Y sin "
        "embargo cualquiera que haya visto fútbol sabe que un cabezazo es peor que un "
        "remate con el pie desde el mismo sitio.</p>"
        "<p>La tabla no miente, esconde: los cabezazos se rematan a <strong>9.7 metros "
        "de media</strong>, contra 19-20 de los pies. Están más cerca <em>porque</em> son "
        "cabezazos — llegan de centros y córners al área chica. Las dos cosas se cancelan "
        "y el promedio queda plano. Desenredar eso es, literalmente, para lo que sirve "
        "un modelo.</p>"))

    p.append(_heading("03", "Las features y la partición", "features"))
    p.append(_prose(
        "<p>Dos cantidades hacen casi todo el trabajo: la <strong>distancia</strong> a la "
        "portería y el <strong>ángulo</strong> que subtienden los dos palos desde el punto "
        "de tiro. El ángulo es lo que distingue rematar de frente desde el borde del área "
        "de hacerlo desde la línea de fondo a la misma distancia: mismo radio, portería "
        "casi invisible.</p>"
        "<p>A eso se suman la situación (jugada, córner, balón parado, tiro libre), la "
        "parte del cuerpo, si el tiro venía asistido, y un proxy de rebote: otro tiro del "
        "mismo equipo en el mismo minuto.</p>"
        "<p>Las coordenadas crudas entran <em>además</em> de la distancia y el ángulo, aunque "
        "sean redundantes en teoría. La razón es que un modelo de árboles no calcula: parte "
        "el espacio en cajas y le asigna un valor a cada una. Darle la posición en bruto le "
        "permite aislar zonas con comportamiento propio —el segundo palo, la frontal— que "
        "la distancia y el ángulo por sí solos mezclarían con puntos geométricamente "
        "equivalentes pero futbolísticamente distintos.</p>"
        "<p>Eso tiene una contrapartida, y la digo de una vez: en las zonas donde casi no hay "
        "tiros, el modelo no interpola con suavidad sino que arrastra el valor de la caja "
        "vecina. Donde hay datos, esa flexibilidad es una ventaja; donde no los hay, es una "
        "fuente de disparates. El caso más claro me costó encontrarlo.</p>"))
    p.append(_callout(
        f"Los {olimpicos['n']} tiros que rompían el modelo",
        f"<p>Al mirar el mapa de valor del tiro aparecía una zona brillante en las esquinas: "
        "el modelo daba <strong>0.85 de xG a un remate desde el banderín</strong>, un "
        "sinsentido. No era el modelo inventando en el vacío — eran datos reales.</p>"
        f"<p>Son <strong>goles olímpicos</strong>: {olimpicos['n']} remates registrados a "
        f"menos de dos grados de portería visible, de los cuales {olimpicos['goles']} "
        "acabaron en gol. Una conversión del 55% desde la esquina.</p>"
        "<p>La explicación no es que meter un gol olímpico sea fácil, sino <strong>cómo se "
        "cuentan</strong>. Understat registra un córner como <em>tiro</em> solo si iba "
        "dirigido a puerta; los cientos de córners normales que se centran al área son "
        "pases y no aparecen. Así que el denominador está mal: la muestra en el banderín no "
        "es «los córners», es «los córners que buscaban gol», que está llena de los que "
        "entraron. Es sesgo de selección de manual.</p>"
        "<p>Los saqué del entrenamiento. Son 22 tiros sobre 221.922, así que las métricas "
        "no se mueven ni en la tercera cifra, pero el xG en la esquina cae de 0.85 a 0.08. "
        "Vale la pena señalar que Understat les asigna 0.013: en este punto concreto su "
        "modelo lo tenía bien y el mío no.</p>"))
    p.append(_callout(
        "La partición no puede ser aleatoria",
        "<p>Acá se cae la mayoría de los tutoriales de xG. Dos tiros del mismo partido "
        "—y sobre todo de la misma jugada— no son independientes: repartirlos entre "
        "entrenamiento y prueba filtra información e infla el resultado.</p>"
        "<p>La partición honesta es temporal, que además es como se usaría el modelo de "
        "verdad: se entrena con 2021-24, se valida en 2024-25 y se prueba en "
        "<strong>2025-26, que el modelo no ve nunca</strong>.</p>"))

    p.append(_heading("04", "Resultados", "resultados"))
    p.append(_table(
        ["Modelo", "Log-loss", "Brier", "ROC-AUC", "Sesgo"],
        [fila("Tasa global (baseline)", np.full(te.sum(), y[tr].mean())),
         fila("Logística (distancia + ángulo)", p_log),
         fila(f"XGBoost ({modelo.best_iteration} árboles)", p_xgb),
         fila("xG de Understat", p_und)], wide=True))
    p.append(_prose(
        "<p>Las tres primeras columnas miden lo mismo desde ángulos distintos: qué tan "
        "equivocado está el modelo. En las dos primeras, menos es mejor; en la tercera, "
        "más. La última dice si el modelo, sumado sobre toda la temporada, acierta el "
        "número de goles que de verdad se marcaron.</p>"
        "<p>El resultado es que <strong>mi modelo empata con el de producción</strong>: "
        "0.2597 contra 0.2589 de log-loss, una diferencia del 0.3%, y de hecho distingue "
        "un poco mejor los tiros que acaban en gol de los que no. Todo eso con geometría y "
        "cuatro variables de contexto, sin ver un solo defensor ni dónde estaba el "
        "portero.</p>"
        "<p>La tabla también muestra hasta dónde llega cada cosa. La geometría sola —esa regresión de "
        "dos variables— ya recorre más de la mitad del camino desde el punto de partida "
        "hasta el mejor modelo. El resto lo aporta el contexto: cabeza contra pie, córner "
        "contra jugada abierta, si hubo barullo en el área.</p>"
        "<p>Y queda la última columna, que es donde empieza la parte interesante del "
        "artículo.</p>"))

    p.append(_heading("05", "Calibración: la prueba que importa", "calibracion"))
    p.append(_prose(
        "<p>Un xG no se usa para ordenar tiros, se usa para <strong>sumarlos</strong>. "
        "Cuando se dice «el equipo generó 2.3 de xG» se está afirmando que esos tiros "
        "valían 2.3 goles. Por eso lo que hay que exigirle no es que acierte cuál entra "
        "—eso es el AUC— sino que <strong>cuando dice 0.30, entre el 30%</strong>.</p>"
        "<p>Son dos propiedades que se pueden tener por separado, y eso explica la tabla "
        "de arriba. El AUC solo mira el <em>orden</em>: si a todas las predicciones de un "
        "modelo bien calibrado se les suma un 20%, el orden no cambia y el AUC queda "
        "idéntico, aunque ahora el modelo prometa un 20% más de goles de los que habrá. "
        "Un xG puede distinguir perfectamente los remates peligrosos de los inofensivos y "
        "aun así estar sistemáticamente inflado.</p>"
        "<p>Por eso comparo por deciles y no con un número global: "
        "agrupando los tiros según lo que el modelo predijo y contando cuántos acabaron "
        "en gol dentro de cada grupo, se ve <em>en qué tramo</em> se desvía. Un promedio "
        "que cuadre puede estar escondiendo que el modelo se pasa con los tiros fáciles y "
        "se queda corto con los difíciles.</p>"))
    p.append(_figure(_fig_calibracion(p_xgb, p_und, y[te]),
                     "Cada punto agrupa un doceavo de los tiros de 2025-26, ordenados por "
                     "xG predicho. La diagonal es la calibración perfecta.", height=540))

    p.append(_heading("06", "El hallazgo que no se buscaba", "sesgo"))
    p.append(_stat(f"+{por_temp.sesgo.iloc[-1]:.0f}%",
                   "sobreestima el xG de Understat los goles de 2025-26"))
    p.append(_figure(_fig_sesgo_understat(por_temp),
                     "Sin penales, para que la comparación sea la misma que la del modelo.",
                     height=520))
    p.append(_prose(
        "<p>La brecha no es cosa de una temporada mala. Empezó en un 7% hace cinco años y "
        "ha subido en cada una de las siguientes, sin excepción. Aparece igual en las cinco "
        "ligas, y responde a dos movimientos que van en sentidos contrarios: los goles "
        "reales bajan temporada tras temporada, mientras que el xG que les asigna Understat "
        "sube.</p>"
        "<p>Antes de buscar culpables quise ver <em>dónde</em> se produce el exceso, "
        "porque no está repartido. Agrupando los tiros por el propio xG que les pone "
        "Understat:</p>"))
    p.append(_table(
        ["Tramo de xG", "Tiros", "Predice", "Entra", "Goles de más"],
        [[f"{iv.left:.2f} – {iv.right:.2f}", f"{int(r.tiros):,}".replace(",", "."),
          f"{r.predice:.3f}", f"{r.entra:.3f}", f"{r.exceso:+.0f}"]
         for iv, r in por_banda.iterrows()], wide=True))
    p.append(_prose(
        "<p>El problema no está en los tiros malos, que son la enorme mayoría y salen "
        "prácticamente bien. Está arriba: en las ocasiones que Understat califica de 0.40 "
        "para arriba —las claras, las que uno esperaría que un modelo tuviera bien "
        "aprendidas— predice 0.547 y entra 0.468. Son casi ocho puntos porcentuales de "
        "más, y ese solo tramo aporta 1.382 de los 2.651 goles de exceso: más de la mitad, "
        "con apenas el 8% de los tiros.</p>"
        "<p>Dicho de otro modo, su modelo cree que una ocasión clara es mejor de lo que "
        "realmente es.</p>"))
    p.append(_callout(
        "Y con los penales le pasa lo contrario",
        f"<p>Los {pen['n']:,} penales los dejé fuera del modelo y los trato como "
        "constante: son tiros desde exactamente el mismo punto, y si entraran el modelo "
        "aprendería un pico en una coordenada que contaminaría todo su vecindario. "
        f"<strong>Un penal vale {pen['conversion']:.2f}</strong>, que es la conversión real "
        "de estas cinco temporadas.</p>"
        f"<p>Understat les asigna <strong>{pen['xg_understat']:.3f}</strong>, es decir por "
        "<em>debajo</em> de lo que entran. Y eso importa para el diagnóstico: si su xG "
        "estuviera simplemente inflado, todo iría en la misma dirección. Que se pase con "
        "las ocasiones claras y se quede corto con los penales dice que no es un problema "
        "de escala, sino de cómo aprendió la parte alta de la tabla.</p>".replace(",", ".")))
    p.append(_prose(
        "<p>La explicación más natural para que la brecha crezca cada año es que el modelo "
        "envejece. Si el fútbol cambia —mejores porteros, otra selección de tiro— un xG "
        "entrenado hace tiempo se va quedando desactualizado, y el desajuste se acumula "
        "temporada tras temporada.</p>"
        "<p>Lo bueno de esa hipótesis es que la puedo poner a prueba con lo que ya tengo. "
        "Si el envejecimiento fuera la causa, me bastaría con entrenar mi propio modelo "
        "usando una sola temporada y medirlo siempre contra 2025-26: cuanto más vieja la "
        "temporada de entrenamiento, mayor debería ser el sesgo.</p>"
        "<p>Lo hice, y la dirección es la esperada. Entrenando con la temporada más "
        "antigua el modelo se pasa un 4.9%; entrenando con la más reciente, un 2.0%. El "
        "envejecimiento existe y se mide.</p>"))
    p.append(_callout(
        "Pero solo alcanza para 3 de los 17 puntos",
        "<p>La diferencia entre esos dos extremos es de unos tres puntos porcentuales. "
        "Understat se aleja diecisiete. El envejecimiento explica una parte pequeña y el "
        "resto tiene que venir de otro lado — de decisiones del modelo que no se pueden "
        "diagnosticar desde fuera, porque no publican ni sus variables ni cómo lo "
        "entrenaron.</p>", warn=True))
    p.append(_prose(
        "<p>Quiero decirlo con precisión, sin inflar el hallazgo. Esto no significa que "
        "su xG «esté mal» para todo: distingue los tiros peligrosos de los inofensivos casi "
        "tan bien como el mío, así que para comparar dos remates entre sí sirve "
        "perfectamente. Lo que no se puede hacer es sumarlo sin corregir — cuando se lee "
        "que un equipo generó 1.8 de xG, en goles eso vale más cerca de 1.55.</p>"
        "<p>Y queda la lección de fondo: <strong>un número publicado por una fuente "
        "respetada no es la verdad, es otro modelo.</strong> Comprobarlo contra lo que de "
        "verdad pasó cuesta cuatro líneas de código, y casi nunca se hace.</p>"))

    p.append(_heading("07", "Qué aprendió el modelo", "aprendio"))
    p.append(_prose(
        "<p>Un modelo de árboles no viene con una fórmula que se pueda leer, pero sí se le "
        "puede preguntar por casos concretos. Vale la pena hacerlo con la pregunta que "
        "abrió el artículo: <strong>¿cuánto cuesta rematar de cabeza?</strong></p>"))
    p.append(_figure(_fig_cabeza(modelo, feats),
                     "Cada línea es el mismo tiro de frente a la portería, cambiando solo "
                     "con qué se remata. Más allá del área la curva deja de ser fiable: hay "
                     "muy pocos cabezazos tan lejos.", height=490))
    p.append(_prose(
        "<p>La tabla de la sección 02 decía 9.9% para los dos. Fijando la geometría, el "
        "modelo dice otra cosa muy distinta, y depende muchísimo de la distancia. "
        "<strong>Pegado a la portería, a seis metros, un cabezazo vale el 91% de lo que "
        "vale un remate con el pie</strong> — casi lo mismo, porque desde ahí entra casi "
        "todo y da un poco igual con qué le pegues. A diez metros ya baja al 43%. Y desde "
        "el borde del área grande, a dieciséis, se queda en el 16%: seis veces menos que "
        "el mismo tiro con el pie.</p>"
        "<p>Eso es lo que el promedio crudo escondía. No es que cabecear sea peor en "
        "general; es que cabecear <em>lejos</em> es malísimo, y como casi todos los "
        "cabezazos ocurren cerca, el promedio salía plano.</p>"))
    p.append(_figure(_fig_superficie(modelo, feats, d),
                     "En blanco, las zonas donde no hay suficientes tiros de jugada para "
                     "sostener una predicción: el modelo respondería igual, pero estaría "
                     "inventando.", height=560))
    p.append(_figure(_fig_importancia(modelo),
                     "La distancia pesa poco porque el ángulo ya la contiene en buena "
                     "medida. Lo que aporta información nueva es el contexto.", height=520))

    p.append(_heading("08", "Conclusión", "conclusion"))
    p.append(_prose(
        "<p>Un xG competitivo se construye con geometría y cuatro variables de contexto: la "
        "mayor parte de lo que determina si un tiro acaba en gol está en dónde y cómo se "
        "remató, y eso está al alcance de cualquiera con los datos públicos.</p>"
        "<p>La diferencia real entre los dos modelos no aparece en si aciertan qué tiro "
        "entra, sino en si el total cuadra al final de la temporada. Es la propiedad que "
        "casi nunca se revisa y la única que importa cuando el xG se usa para sumar.</p>"
        "<p>Sobre el sesgo de Understat: sobreestima un 17% en la última temporada, la "
        "brecha crece cada año, y viene sobre todo de las ocasiones claras. Propuse que "
        "fuera envejecimiento del modelo y medí que eso explica apenas una sexta parte; "
        "el resto no se puede diagnosticar sin saber cómo está construido.</p>"
        "<p><strong>Limitaciones</strong>: no sé dónde estaban el portero ni los "
        "defensores, que es la información que más falta y probablemente lo que le pone "
        "techo a los dos modelos. El indicador de rebote solo distingue el minuto, no el "
        "segundo. Y no se distingue qué tipo de pase precedió al tiro, que en los modelos "
        "comerciales es una de las variables fuertes.</p>"))

    return ArticlePage(
        slug="modelo-xg",
        section=SECTION,
        title="Cómo se construye un xG",
        subtitle="Entrené un modelo de goles esperados con 221.922 tiros. Empata con el "
                  "de Understat — y de paso encuentra que el suyo sobreestima un 17%.",
        deck="Un clasificador binario sobre cinco temporadas de las cinco grandes ligas: "
             "geometría, calibración, y por qué un número publicado no es la verdad.",
        body_html="".join(p),
        meta=[("Datos", "221.922 tiros · top 5 ligas · 2021-26"),
              ("Métodos", "XGBoost · regresión logística · calibración"),
              ("Validación", "Partición temporal, prueba en 2025-26"),
              ("Lectura", "~9 min")],
    )


# ---------------------------------------------------------------------------
# artículo 2 — la definición
# ---------------------------------------------------------------------------

def build_definicion_article() -> ArticlePage:
    c = _preparar()
    d = c["d"]
    rng = np.random.default_rng(0)

    ps = d.groupby(["player", "temporada"]).agg(
        tiros=("gol", "size"), goles=("gol", "sum"), xg=("xg_propio", "sum"),
        var=("xg_propio", lambda x: (x * (1 - x)).sum())).reset_index()
    ps["sobre100"] = (ps.goles - ps.xg) / ps.tiros * 100
    ps["z"] = (ps.goles - ps.xg) / np.sqrt(ps["var"])

    p_all = d.xg_propio.values
    grupos = d.groupby(["player", "temporada"]).indices

    def z_simulado(claves, sim):
        return np.array([(sim[grupos[k]].sum() - p_all[grupos[k]].sum()) /
                         np.sqrt((p_all[grupos[k]] * (1 - p_all[grupos[k]])).sum())
                         for k in claves])

    filas_nulo = []
    for umbral in [20, 30, 50]:
        sub = ps[ps.tiros >= umbral]
        claves = list(zip(sub.player, sub.temporada))
        sds = [np.std(z_simulado(claves, (rng.random(len(p_all)) < p_all).astype(int)))
               for _ in range(40)]
        filas_nulo.append([umbral, f"{len(sub):,}".replace(",", "."), f"{sub.z.std():.3f}",
                           f"{np.mean(sds):.3f}", f"+{(sub.z.std()-np.mean(sds))/np.std(sds):.1f}"])

    sub30 = ps[ps.tiros >= 30]
    z_nulo = z_simulado(list(zip(sub30.player, sub30.temporada)),
                        (rng.random(len(p_all)) < p_all).astype(int))

    # persistencia
    A, B, C, D = [], [], [], []
    filas_pers = []
    for umbral in [20, 30, 50]:
        aa, bb, cc, dd = [], [], [], []
        for s1, s2 in zip(SEASONS, SEASONS[1:]):
            m = (ps[(ps.temporada == s1) & (ps.tiros >= umbral)][["player", "sobre100", "tiros"]]
                 .merge(ps[(ps.temporada == s2) & (ps.tiros >= umbral)][["player", "sobre100", "tiros"]],
                        on="player", suffixes=("_t", "_t1")))
            aa += list(m.sobre100_t); bb += list(m.sobre100_t1)
            cc += list(m.tiros_t);    dd += list(m.tiros_t1)
        filas_pers.append([umbral, len(aa), f"{np.corrcoef(aa, bb)[0,1]:.3f}",
                           f"{np.corrcoef(cc, dd)[0,1]:.3f}"])
        if umbral == 30:
            A, B, C, D = aa, bb, cc, dd

    # empirical bayes
    pj = d.groupby("player").agg(
        tiros=("gol", "size"), goles=("gol", "sum"), xg=("xg_propio", "sum"),
        var=("xg_propio", lambda x: (x * (1 - x)).sum())).reset_index()
    pj = pj[pj.tiros >= 30].copy()
    pj["bruto100"] = (pj.goles - pj.xg) / pj.tiros * 100
    pj["var_muestral"] = pj["var"] / pj.tiros ** 2
    var_total = ((pj.goles - pj.xg) / pj.tiros).var()
    var_ruido = pj.var_muestral.mean()
    tau2 = max(var_total - var_ruido, 0)
    pj["credibilidad"] = tau2 / (tau2 + pj.var_muestral)
    pj["skill100"] = pj.bruto100 * pj.credibilidad

    def tabla_jugadores(sub):
        return _table(
            ["Jugador", "Tiros", "Goles", "xG", "Bruto /100", "Credib.", "Habilidad /100"],
            [[r.player, int(r.tiros), int(r.goles), f"{r.xg:.1f}", f"{r.bruto100:+.2f}",
              f"{r.credibilidad:.2f}", f"{r.skill100:+.2f}"] for _, r in sub.iterrows()],
            wide=True)

    p = []
    p.append(_heading("01", "La pregunta", "pregunta"))
    p.append(_prose(
        "<p>«Ese delantero se come los goles». «Ese la mete siempre». Son afirmaciones "
        "sobre una habilidad —<strong>la definición</strong>— que se da por supuesta pero "
        "casi nunca se mide.</p>"
        "<p>Con un xG propio sí puedo. Si un jugador remató 100 veces desde sitios que "
        "valían 12 goles y metió 17, le sacó 5 goles a sus ocasiones. La pregunta es si "
        "eso <strong>es una habilidad suya o le pasó</strong>. Y hay una forma de "
        "distinguirlas: una habilidad se repite; la suerte, no.</p>"))

    p.append(_callout(
        "El xG no puede haber visto los goles del jugador",
        "<p>Ésta es la trampa que invalidaría el análisis entero. Si Mbappé está en el "
        "entrenamiento, el modelo ya aprendió que los tiros desde donde él remata acaban "
        "en gol más a menudo, y le sube el xG hasta hacerlo parecer promedio. La habilidad "
        "se autodestruye.</p>"
        "<p>La solución es <strong>validación cruzada por temporada</strong>: para predecir "
        "2023-24 se entrena con las otras cuatro. Cada tiro recibe un xG de un modelo que "
        "nunca lo vio. El resultado queda calibrado al <strong>+0.3%</strong> sobre 22.099 "
        "goles — contra el +12% del xG de Understat en los mismos tiros, que es la otra "
        "razón por la que no se podía usar el suyo.</p>"))

    p.append(_heading("02", "¿Hay algo que buscar?", "nulo"))
    p.append(_prose(
        "<p>Cada tiro es una moneda cargada: entra con probabilidad igual a su xG. Un "
        "jugador con 50 tiros que suman 5 de xG puede meter 8 sin ser especial — es el "
        "equivalente a sacar 8 caras en 50 tiradas de una moneda que sale cara el 10% de "
        "las veces. Pasa.</p>"
        "<p>Si la definición <em>no existiera</em>, la sobre-actuación de cada jugador "
        "seguiría exactamente la dispersión binomial, y al normalizarla tendría desviación "
        "típica 1. Si existe, más de 1. Lo comparo contra un nulo por simulación que "
        "vuelve a tirar los 221.922 tiros con su propia probabilidad.</p>"))
    p.append(_table(["Mínimo de tiros", "Jugador-temporada", "SD observada",
                     "SD si fuera azar", "z del exceso"], filas_nulo))
    p.append(_figure(_fig_nulo_z(sub30.z, z_nulo),
                     "Las dos distribuciones se pisan casi por completo: la diferencia es "
                     "real pero pequeña.", height=480))
    p.append(_prose(
        "<p><strong>La definición existe</strong> — con z = +5.0 el exceso de dispersión no "
        "es un empate técnico. Pero hay que ver cuánto: 1.076 contra 1.000. Traducido a "
        "varianza, la habilidad aporta el <strong>14%</strong> y el azar el 86% restante.</p>"))

    p.append(_heading("03", "La prueba decisiva: ¿se repite?", "persistencia"))
    p.append(_prose(
        "<p>Para saber si el número que salga es alto o bajo hace falta una vara. Uso "
        "la mejor que tengo: <strong>el volumen de tiro</strong>, medido sobre los mismos "
        "jugadores y las mismas temporadas. Que un jugador genere muchos tiros es una "
        "habilidad que nadie discute, así que su persistencia es el «así se ve una "
        "habilidad de verdad» contra el que comparar.</p>"))
    p.append(_table(["Mínimo de tiros", "Pares (t, t+1)", "r — definición",
                     "r — volumen de tiro"], filas_pers))
    p.append(_figure(_fig_persistencia(A, B, C, D),
                     "La nube de la izquierda no tiene forma; la de la derecha es una "
                     "diagonal clara.", width=900, height=470))
    p.append(_prose(
        "<p>La diferencia entre 0.14 y 0.53 es la que separa un resultado de una habilidad. "
        "Saber que un jugador sobre-definió el año pasado no ayuda casi nada a predecir lo "
        "que hará este; saber que tiró mucho, en cambio, permite apostar con bastante "
        "confianza a que volverá a tirar mucho.</p>"))

    p.append(_heading("04", "Cuánto creerse de lo que se ve", "encogimiento"))
    p.append(_prose(
        "<p>Sabiendo que la mayor parte de la sobre-actuación es ruido, la pregunta "
        "práctica es: dado que un jugador lleva +6 goles sobre su xG, <strong>¿cuánto de "
        "eso es él?</strong></p>"
        "<p>La respuesta es el <strong>encogimiento</strong>: estimo cuánta varianza hay "
        "de verdad entre jugadores y cuánta produce el azar, y acerco cada observación "
        "a la media en proporción a lo ruidosa que sea.</p>"))
    p.append(_stat(f"{pj.credibilidad.mean():.2f}",
                   "de credibilidad media — de +6 goles observados, créete menos de 1"))
    p.append(_figure(_fig_credibilidad(pj),
                     "Ni los jugadores con más de 400 tiros en cinco años llegan a que la "
                     "mitad de lo observado sea señal.", height=470))
    p.append(_prose(
        f"<p>El <strong>{var_ruido/var_total:.0%} de la variación entre jugadores es azar</strong> "
        f"y el {tau2/var_total:.0%} habilidad. La habilidad real tiene una desviación típica "
        f"de <strong>{np.sqrt(tau2)*100:.2f} goles por cada 100 tiros</strong>: un delantero "
        "excepcional, a un desvío por encima, le saca un gol por temporada a sus ocasiones "
        "respecto de uno promedio.</p>"))

    p.append(_heading("05", "Entonces, ¿quiénes son los mejores?", "ranking"))
    p.append(tabla_jugadores(pj.nlargest(15, "skill100")))
    p.append(_prose(
        "<p>Los nombres son la mejor validación que puede tener el método: <strong>Mbappé "
        "y Kane</strong> arriba. Nunca le dije al modelo quién es bueno; salió de encoger "
        "22.099 goles contra su xG.</p>"
        "<p>Ahora bien, vale la pena mirar la magnitud. Mbappé, el mejor definidor de las cinco "
        "ligas en cinco temporadas, le saca <strong>2.4 goles por cada 100 tiros</strong> a sus "
        "ocasiones. Con 690 tiros son unos 17 goles en cinco años — real y valioso, pero "
        "muy lejos de la mitología del «killer del área».</p>"))
    p.append(_prose("<h3>Y los que menos</h3>"))
    p.append(tabla_jugadores(pj.nsmallest(10, "skill100")))

    p.append(_heading("06", "Lo que pasaría sin encoger", "sin-encoger"))
    p.append(_prose(
        "<p>Ésta es la razón de ser del artículo. Ordenando por la sobre-actuación bruta "
        "—que es lo que hace cualquier ranking de «mejores definidores» que circula por "
        "ahí— el podio se llena de jugadores con 30 o 40 tiros que tuvieron un buen "
        "rato.</p>"))
    p.append(tabla_jugadores(pj.nlargest(10, "bruto100")))
    p.append(_callout(
        "Una racha no es una habilidad",
        "<p>El primero de esta tabla aparece con <strong>+14.6 goles por 100 tiros</strong>: "
        "metió 9 con 3.47 de xG. En 38 tiros. El encogimiento lo baja a 0.91, por debajo de "
        "una docena de jugadores con muestras de verdad.</p>"
        "<p>Es el modo de fallo de cualquier método que busque <em>rarezas</em> sin mirar "
        "el <strong>tamaño de muestra</strong>: detectar como élite a quien tuvo suerte con "
        "pocos intentos. La corrección no es un detalle técnico, es lo que separa un "
        "ranking de un sinsentido.</p>", warn=True))

    p.append(_heading("07", "Conclusión", "conclusion"))
    p.append(_prose(
        "<ol><li><strong>La definición existe</strong> (z = +5.0 contra un nulo por "
        "simulación), pero explica el 10-14% de la variación entre jugadores.</li>"
        "<li><strong>Apenas se repite</strong>: r ≈ 0.10-0.14 entre temporadas, contra "
        "r ≈ 0.53 del volumen de tiro sobre los mismos jugadores.</li>"
        "<li><strong>Hay que encoger al 13%</strong> lo observado. Sin eso, cualquier "
        "ranking de definidores es una lista de rachas.</li>"
        "<li><strong>Con la corrección hecha los nombres son los correctos</strong> y las "
        "magnitudes, mucho más modestas de lo que dice el folklore.</li></ol>"
        "<p><strong>La lección transferible</strong>: <em>generar</em> ocasiones es una "
        "habilidad estable y medible; <em>convertirlas</em> por encima de lo esperado es "
        "casi todo ruido. Para juzgar a un delantero, el xG que genera dice mucho más que "
        "la diferencia entre sus goles y su xG.</p>"
        "<p><strong>Limitaciones</strong>: el xG propio no ve al portero ni a los defensores, "
        "así que parte de lo que acá se llama «definición» podría ser seleccionar mejores "
        "momentos dentro de una misma casilla de xG. Y se le asigna a cada jugador una "
        "habilidad fija en cinco temporadas, lo que subestima a quien mejoró o empeoró de "
        "verdad.</p>"))

    return ArticlePage(
        slug="definicion",
        section=SECTION,
        title="¿Existen los definidores natos?",
        subtitle="Medí si superar el xG es una habilidad o suerte. Existe — y es mucho "
                  "más chica de lo que cuenta el folklore.",
        deck="Nulo binomial, persistencia entre temporadas y encogimiento bayesiano sobre "
             "22.099 goles, para separar al definidor del afortunado.",
        body_html="".join(p),
        meta=[("Datos", "221.922 tiros · 4.551 jugadores · 2021-26"),
              ("Métodos", "xG cruzado · nulo por simulación · empirical Bayes"),
              ("Hallazgo", "10-14% habilidad, el resto azar"),
              ("Lectura", "~8 min")],
    )


def build(assets_dir=None) -> list:
    return [build_xg_article(), build_definicion_article()]
