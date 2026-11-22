"""«Equipo completo»: un diagrama de Venn de tres criterios para equipos (el hermano de `venn.py`, el de jugadores).

Cada círculo es «estar en el X% de arriba» de las cinco ligas en esa temporada: crear mucho xG (Ataca), conceder poco
(Defiende) y tener el balón (Controla). El centro son los equipos que destacan en las tres; las regiones de dos
círculos distinguen estilos. La vista es la misma de jugadores (`web/react/src/VennVista.jsx`), con la bandera `equipo`.

La regla es la de `venn.py`: el percentil se calcula entre los equipos de las cinco ligas de la misma temporada, los
empates comparten el promedio de sus lugares y está en el círculo quien tiene `p >= 1 - corte`. Defiende va al revés
(`inv`): cuenta el que concede MENOS xG, así que sus percentiles se calculan sobre el xG en contra cambiado de signo.
"""

import pandas as pd

import react_views
from preguntas import PREGUNTAS
from site_utils import ChartPage, temporadas_en_curso
from venn import COLORES_CIRCULO, CORTE_MAX, CORTE_MIN, percentiles, regiones
from viz_theme import FUENTE_FBREF, FUENTE_UNDERSTAT, LEAGUE_COLORS, LEAGUE_COLORS_DARK, LEAGUE_ORDER

SECTION = "Equipos"
SLUG = "equipo-completo"
TITULO = "Equipo completo"
CORTE_INI = 25                                   # el deslizador arranca en su máximo: con 96 equipos, 15% deja el centro casi vacío
AMBITO = "de los equipos de las cinco ligas"
POSICIONES = ["Equipo"]                          # la vista de jugadores filtra por posición; aquí hay una sola población

# Columnas del payload, en orden: (clave corta, columna del DataFrame). Las filas viajan como listas en este orden,
# después de [nombre, "", liga, 0, partidos].
MEDIDAS = [("ataca", "xg_fav"), ("defiende", "xg_con"), ("controla", "ov_Poss")]
DECIMALES = {"ataca": 3, "defiende": 3, "controla": 1}
PREFIJO = 5
COL_PARTIDOS = "pt_Playing Time_MP"

# Un solo diagrama. `inv`: menos es mejor (el percentil se calcula con el signo cambiado). `dec`: decimales al mostrarlo.
VENNS = [
    {"id": "equipo", "tab": "Equipo completo", "pos": "Equipo", "plural": "equipos", "titulo": "El equipo completo",
     "sets": [
         {"nombre": "Ataca", "col": "ataca", "dec": 2, "def": "xG a favor por partido, sin penales"},
         {"nombre": "Defiende", "col": "defiende", "dec": 2, "inv": True,
          "def": "xG en contra por partido, sin penales: cuenta el que concede menos"},
         {"nombre": "Controla", "col": "controla", "dec": 1, "def": "Posesión del balón, en %"},
     ]},
]


def percentiles_de(valores, inv=False):
    """Los percentiles de un círculo; con `inv`, sobre el signo cambiado (el menor valor es el mejor)."""
    return percentiles([-v for v in valores] if inv else valores)


def regiones_de(valores_por_set, corte):
    """Las 7 regiones del diagrama (como `venn.regiones`), respetando `inv` de cada círculo de `VENNS[0]`."""
    sets = VENNS[0]["sets"]
    return regiones([[-v for v in vals] if s.get("inv") else vals for s, vals in zip(sets, valores_por_set)], corte)


def tabla(df):
    """{temporada: {"minimo": 0, "jug": [[nombre, "", liga, 0, partidos, ataca, defiende, controla], ...]}}.

    Se llama `jug` por la vista, que es la misma que la de jugadores; cada fila es un equipo."""
    d = df.dropna(subset=[c for _, c in MEDIDAS]).copy()
    salida = {}
    for t in sorted(d["temporada"].unique()):
        x = d[d["temporada"] == t]
        cols = [x[c].round(DECIMALES[k]).tolist() for k, c in MEDIDAS]
        filas = [[n, "", LEAGUE_ORDER.index(str(l)), 0, int(mp), *vals]
                 for n, l, mp, *vals in zip(x["Squad"], x["liga"], x[COL_PARTIDOS], *cols)]
        salida[t] = {"minimo": 0, "jug": filas}
    return salida


def textos():
    que_mirar = (
        "Muestra qué equipos están entre los mejores de las cinco ligas en tres cosas a la vez: el xG que crean, el xG "
        "que conceden y el tiempo que tienen el balón. Cada círculo agrupa a los que destacan en una de ellas, y el "
        "centro reúne a los que destacan en las tres.\n"
        f"El deslizador define qué tan exigente es «entre los mejores»: es el porcentaje de arriba de las cinco ligas "
        f"en esa temporada, de {CORTE_MIN}% a {CORTE_MAX}%. Las regiones de dos círculos distinguen estilos, porque "
        f"crear y conceder poco sin tener el balón no es lo mismo que tenerlo y no crear.")
    por_que = (
        "**Población.** Los equipos de las cinco ligas de cada temporada, comparados solo con los de esa temporada. La "
        "temporada en curso cuenta con los partidos jugados hasta ahora.\n\n"
        f"**Cómo se corta.** El corte es un percentil entre las cinco ligas juntas («el {CORTE_INI}% de arriba»), no un "
        "valor fijo, y es una decisión de quien mira. Las ligas no tienen el mismo nivel, y el xG por partido de un "
        "equipo se mide contra los rivales de su liga.\n\n"
        "**Qué se mide.** *Ataca*: xG a favor por partido, sin penales (Understat). *Defiende*: xG en contra por partido, "
        "sin penales, donde menos es mejor (Understat). *Controla*: posesión, en % (FBref). Los tres criterios se "
        "parecen entre sí (los mejores equipos suelen ser buenos en los tres), así que el centro es una lista de élite "
        "y lo que distingue a los equipos está en las regiones de dos círculos.")
    return que_mirar, por_que


def payload(df, en_curso):
    return {
        "entidad": SLUG,
        "ligas": LEAGUE_ORDER, "posiciones": POSICIONES,
        "medidas": [k for k, _ in MEDIDAS], "prefijo": PREFIJO,
        "temporadas": tabla(df),
        "enCurso": sorted(en_curso),
        "colores": {"claro": [LEAGUE_COLORS[l] for l in LEAGUE_ORDER], "oscuro": [LEAGUE_COLORS_DARK[l] for l in LEAGUE_ORDER]},
        "coloresCirculo": COLORES_CIRCULO,
        "corte": {"min": CORTE_MIN, "max": CORTE_MAX, "ini": CORTE_INI},
    }


def chart_venn_equipos(df: pd.DataFrame) -> ChartPage:
    """`df` es la tabla de equipos de `teams.load_data()`."""
    p = payload(df, temporadas_en_curso())
    react_views.registrar_payload(SLUG, p)
    que_mirar, _ = textos()
    bajada = "Los equipos que están en el top de las cinco ligas en ataque, defensa y posesión a la vez, y cuántos hay."
    assert len(bajada) <= 160, f"{SLUG}: la bajada mide {len(bajada)} caracteres"
    cfg = {
        "id": SLUG, "titulo": TITULO, "bajada": bajada, "pregunta": PREGUNTAS[SLUG], "tabla": SLUG,
        "queMirar": que_mirar,
        "fuente": f"{FUENTE_UNDERSTAT} y {FUENTE_FBREF}",
        "venns": VENNS, "equipo": True, "ambito": AMBITO,
    }
    return ChartPage(slug=SLUG, section=SECTION, title=TITULO, subtitle=bajada,
                     body_html=react_views.montar_html("venn", SLUG, cfg, alto_min=900), kind="venn")
