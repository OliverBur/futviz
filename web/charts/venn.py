"""«Jugador completo»: diagramas de Venn de tres criterios por posición.

Cada círculo es «estar en el X% de arriba de su posición» en una medida; el cruce de los tres es el jugador que hace bien
las tres cosas. Hay tres diagramas (defensa, medio y delantero) y el corte lo mueve quien mira.

El cálculo vive en el navegador (`web/react/src/VennVista.jsx`), porque el corte es un deslizador: aquí solo se arma la
tabla de jugadores y los textos fijos. `percentiles` y `regiones` son la MISMA regla en Python, para los tests y para que
los textos fijos no inventen cifras.

La regla, que el navegador repite al pie de la letra:

* El percentil de un valor se calcula DENTRO de su posición y su temporada, sobre quien pasa el corte de minutos de las
  vistas por 90' (900 en una temporada cerrada; la que va en curso conserva su corte relativo). Los empates comparten
  el promedio de sus lugares: `p = (rango_promedio - 0.5) / n`.
* Está en el círculo quien tiene `p >= 1 - corte`.
* Quien no cruzó con FBref (sin entradas ni intercepciones) queda fuera.
"""

import numpy as np
import pandas as pd

import react_views
from preguntas import PREGUNTAS
from site_utils import ChartPage, temporadas_en_curso
from viz_theme import FUENTE_FBREF, FUENTE_UNDERSTAT, LEAGUE_COLORS, LEAGUE_COLORS_DARK, LEAGUE_ORDER

SECTION = "Jugadores"
SLUG = "jugador-completo"
TITULO = "Jugador completo"

POSICIONES = ["Defensa", "Medio", "Delantero"]
CORTE_MIN, CORTE_MAX, CORTE_INI = 5, 30, 15     # el deslizador, en % de arriba de cada posición

# Columnas del payload, en orden: (clave corta, columna del DataFrame). Las filas viajan como listas en este orden,
# después de [nombre, club, liga, posición, minutos].
MEDIDAS = [("rec", "recoveries90"), ("xga", "xga90"), ("bld", "xgbuild90"), ("npx", "npxg90"), ("xa", "xA90")]
DECIMALES = {"rec": 2, "xga": 3, "bld": 3, "npx": 3, "xa": 3}
PREFIJO = 5                                      # nombre, club, liga, posición, minutos

REC = "Entradas ganadas + intercepciones por 90'"
XGA = "xG + xA por 90'"
BLD = "xG de construcción por 90' (jugadas en que participa sin tirar ni asistir)"

# Cada diagrama: tres círculos; `col` es la clave de MEDIDAS. El primero va arriba, el segundo abajo a la izquierda y
# el tercero abajo a la derecha.
VENNS = [
    {"id": "defensa", "tab": "Defensa completo", "pos": "Defensa", "plural": "defensas", "titulo": "El defensa completo",
     "sets": [{"nombre": "Recupera", "col": "rec", "def": REC}, {"nombre": "Aporta en ataque", "col": "xga", "def": XGA},
              {"nombre": "Construye", "col": "bld", "def": BLD}]},
    {"id": "medio", "tab": "Medio completo", "pos": "Medio", "plural": "mediocampistas", "titulo": "El mediocampista completo",
     "sets": [{"nombre": "Recupera", "col": "rec", "def": REC}, {"nombre": "Aporta en ataque", "col": "xga", "def": XGA},
              {"nombre": "Construye", "col": "bld", "def": BLD}]},
    {"id": "delantero", "tab": "Delantero que presiona", "pos": "Delantero", "plural": "delanteros",
     "titulo": "El delantero que también presiona",
     "sets": [{"nombre": "Remata", "col": "npx", "def": "xG sin penales por 90'"},
              {"nombre": "Asiste", "col": "xa", "def": "xA por 90'"},
              {"nombre": "Presiona", "col": "rec", "def": REC}]},
]

# Los tres colores de círculo (validados contra el fondo claro y el oscuro con el validador de paletas de dataviz).
COLORES_CIRCULO = {"claro": ["#6d4ad6", "#dc6420", "#0f9d8a"], "oscuro": ["#8a6fe6", "#d9702a", "#17a08c"]}


# --- la regla, en Python ----------------------------------------------------------------------------

def percentiles(valores):
    """Percentil de cada valor dentro de su población; los empates comparten el promedio de sus lugares."""
    s = pd.Series(np.asarray(valores, dtype=float))
    return ((s.rank(method="average") - 0.5) / len(s)).to_numpy()


def regiones(valores_por_set, corte):
    """Las 7 regiones del diagrama. `valores_por_set` son tres listas de la misma población; `corte` es la fracción de
    arriba (0.15 = el 15%). Devuelve {máscara 1..7: cuántos}, con el bit j de la máscara = «está en el círculo j»."""
    pct = [percentiles(v) for v in valores_por_set]
    mascara = sum((p >= 1 - corte).astype(int) << j for j, p in enumerate(pct))
    return {m: int((mascara == m).sum()) for m in range(1, 8)}


# --- los datos --------------------------------------------------------------------------------------

def preparar(df, minimos):
    """Los jugadores de campo que pasan el corte de minutos de su temporada y tienen las cinco medidas."""
    d = df[df["posicion"].isin(POSICIONES)].dropna(subset=[c for _, c in MEDIDAS]).copy()
    corte = d["temporada"].map(minimos)
    return d[d["min"] >= corte].reset_index(drop=True)


def tabla(df, minimos):
    """{temporada: {"minimo", "jug": [[nombre, club, liga, posición, minutos, rec, xga, bld, npx, xa], ...]}}."""
    d = preparar(df, minimos)
    salida = {}
    for t in sorted(d["temporada"].unique()):
        x = d[d["temporada"] == t]
        cols = [x[c].round(DECIMALES[k]).tolist() for k, c in MEDIDAS]
        filas = [[n, club, LEAGUE_ORDER.index(str(l)), POSICIONES.index(p), int(m), *vals]
                 for n, club, l, p, m, *vals in zip(x["player"], x["team"], x["liga"], x["posicion"], x["min"], *cols)]
        salida[t] = {"minimo": int(minimos[t]), "jug": filas}
    return salida


def textos():
    que_mirar = (
        f"Muestra quién está entre los mejores de su posición en tres cosas a la vez. Cada círculo agrupa a "
        f"los jugadores que destacan en una de ellas; quien cae en el centro destaca en las tres y las "
        f"regiones de en medio son combinaciones de dos. El deslizador define qué tan exigente es «entre los "
        f"mejores»: el porcentaje de arriba de su posición, de {CORTE_MIN}% a {CORTE_MAX}%.")

    por_que = (
        "**Población.** Jugadores de campo de las cinco ligas con el corte de minutos de las vistas por 90' (900 en una "
        "temporada cerrada; menos en la que va en curso) y cruzados con FBref. Cada diagrama compara solo a los de una "
        "posición.\n\n"
        f"**Cómo se corta.** El corte es un percentil dentro de la posición y la temporada elegidas («el {CORTE_INI}% de "
        f"arriba de los medios»), no un valor fijo, y es una decisión de quien mira: con otro, cambia quién queda en el "
        f"centro. Los grupos no son naturales; la gente en estos datos se reparte en un continuo y el diagrama la separa "
        f"por un umbral.\n\n"
        "**Qué se mide.** *Recupera*: entradas ganadas + intercepciones por 90' (FBref). *Aporta en ataque*: xG + xA por "
        "90' (Understat). *Construye*: xG de construcción por 90' (Understat). En el delantero: *Remata* es el xG sin "
        "penales por 90', *Asiste* el xA y *Presiona* las mismas entradas ganadas + intercepciones.")
    return que_mirar, por_que


def payload(df, minimos, en_curso):
    return {
        "entidad": SLUG,
        "ligas": LEAGUE_ORDER, "posiciones": POSICIONES,
        "medidas": [k for k, _ in MEDIDAS], "prefijo": PREFIJO,
        "temporadas": tabla(df, minimos),
        "enCurso": sorted(en_curso),
        "colores": {"claro": [LEAGUE_COLORS[l] for l in LEAGUE_ORDER], "oscuro": [LEAGUE_COLORS_DARK[l] for l in LEAGUE_ORDER]},
        "coloresCirculo": COLORES_CIRCULO,
        "corte": {"min": CORTE_MIN, "max": CORTE_MAX, "ini": CORTE_INI},
    }


def chart_venn(df, minimos) -> ChartPage:
    """`df` es la tabla de jugadores de `players.load_data()`; `minimos` el corte de minutos por 90' de cada temporada."""
    p = payload(df, minimos, temporadas_en_curso())
    react_views.registrar_payload(SLUG, p)
    que_mirar, _ = textos()
    bajada = "El jugador que está en el top de su posición en tres cosas a la vez, y cuántos hay."
    assert len(bajada) <= 160, f"{SLUG}: la bajada mide {len(bajada)} caracteres"
    cfg = {
        "id": SLUG, "titulo": TITULO, "bajada": bajada, "pregunta": PREGUNTAS[SLUG], "tabla": SLUG,
        "queMirar": que_mirar,
        "fuente": f"{FUENTE_UNDERSTAT} y {FUENTE_FBREF}",
        "venns": VENNS,
    }
    return ChartPage(slug=SLUG, section=SECTION, title=TITULO, subtitle=bajada,
                     body_html=react_views.montar_html("venn", SLUG, cfg, alto_min=900), kind="venn")
