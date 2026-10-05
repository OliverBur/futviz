"""Vistas de Equipos del sitio, en React + MUI X Charts.

Mismas decisiones que `code/eda_teams.ipynb` (el laboratorio de cada gráfico), pero acá no se dibuja
nada: se carga y limpia la tabla de equipos, se registra UNA tabla compartida
(`react_views.registrar_tabla("equipos", ...)`) y se arma por vista la configuración que necesita el
bundle de React. Filtros, rankings y texto dinámico se calculan en el navegador.
"""

import pandas as pd

import insights as ins
import react_views
from consolidate_data import ELO_TOP, NIVELES
from site_utils import PROCESSED_DIR, ChartPage
from viz_theme import DIVERGING, FUENTE_FBREF, LEAGUE_COLORS, LEAGUE_COLORS_DARK, LEAGUE_ORDER

SECTION = "Equipos"

# Las variables que se pueden poner en cada eje de "Crea tu gráfico" y en "Nivel por liga":
# (columna, etiqueta, grupo del desplegable, decimales con los que se muestra).
#
# Están casi todas por 90 minutos y no en total a propósito. Las cinco ligas no juegan la misma
# cantidad de partidos (la Bundesliga 34, las otras 38) y Ligue 1 cambió de 20 a 18 equipos en
# 2023-24, así que cualquier total mete esa diferencia dentro del dato y la mitad de los cruces
# terminarían midiendo "cuántos partidos jugó". Las excepciones son las que ya vienen normalizadas
# (porcentajes, promedios) y las rojas, que son tan pocas por partido que la tasa se vuelve ruido.
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

# Nota del filtro de nivel de club cuando cada punto ES un club.
AYUDAS = {
    "nivel": (f"Corte en {ELO_TOP} de ELO (clubelo) al arrancar la temporada: el 20% más alto de las 5 "
              f"ligas. Se mide antes de que empiece, así que una gran temporada de un club chico no lo "
              f"saca del grupo. Si la temporada aún no tiene ELO, se usa el último nivel conocido del "
              f"club."),
}


def niveles_de(df):
    """Las opciones que de verdad aparecen, en orden fijo (top primero)."""
    if "nivel" not in df.columns:
        return []
    return [n for n in NIVELES if (df["nivel"] == n).any()]


def load_data():
    """Las temporadas ya consolidadas por `code/consolidate_data.py`.

    Antes se asignaba la liga por bloques de filas *hardcodeados* (18/20/18/20/20), que no
    sobrevivían a las 5 temporadas (Ligue 1 pasó de 20 a 18 equipos en 2023-24). El consolidado ya
    trae `temporada` y `liga` resueltas y verifica los tamaños."""
    df = pd.read_csv(PROCESSED_DIR / "teams_all_seasons.csv")

    # Las derivadas se arman de una sola vez (un `df[nueva] = ...` por columna sobre un frame de 171
    # columnas lo fragmenta y pandas avisa).
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
    return sorted(df["temporada"].unique())


# --- configuración de las vistas ---------------------------------------------------------------

def _eje(col, label, corto, dec):
    """Un eje: `dec` son los decimales del tooltip, la tabla y la lista Top 5."""
    return {"col": col, "label": label, "corto": corto, "dec": dec}


def _pagina(slug, titulo, descripcion, config, tipo="scatter", kind="scatter"):
    config = {"id": slug, "titulo": titulo, **config}
    return ChartPage(
        slug=slug, section=SECTION, title=titulo, subtitle=descripcion,
        body_html=react_views.montar_html(tipo, slug, config), kind=kind)


def _scatter(df, slug, titulo, descripcion, *, x, y, cuadrantes, subtitulo, textos, insight):
    """Un scatter de equipos con el par fijo: líneas en el promedio de cada eje (el de las temporadas
    juntas, para que "por encima del promedio" signifique lo mismo al cambiar de temporada) y un
    rótulo por cuadrante."""
    que_mirar, por_que = textos
    return _pagina(slug, titulo, descripcion, {
        "tabla": "equipos", "entidad": "equipos",
        "x": x, "y": y,
        "referencia": {"tipo": "promedios", "cuadrantes": cuadrantes},
        "requiere": [x["col"], y["col"]],
        "subtitulo": subtitulo,
        "filtros": {"nivel": True},
        "metricas": [
            {"id": "dist", "etiqueta": "Alejados",
             "ayuda": "Los que más se alejan del centro de la nube (en desviaciones estándar)"},
            {"id": "x", "etiqueta": x["corto"], "ayuda": f"Los de mayor {x['label']}"},
            {"id": "y", "etiqueta": y["corto"], "ayuda": f"Los de mayor {y['label']}"},
        ],
        "queMirar": que_mirar(), "porQue": por_que(df),
        "insight": insight, "fuente": FUENTE_FBREF, "colorPor": ["liga"],
    })


def chart_def_efficiency(df):
    return _scatter(
        df, "eficiencia-definicion", "Eficiencia de definición",
        "Precisión (SoT%) vs. definición (G/SoT) — un punto por equipo.",
        x=_eje("sh_Standard_SoT%", "Precisión — % de tiros que van a puerta (SoT%)", "Precisión", 1),
        y=_eje("sh_Standard_G/SoT", "Definición — goles por tiro a puerta (G/SoT)", "Definición", 2),
        cuadrantes={"tr": "certeros y letales", "tl": "poco a puerta, pero letales",
                    "br": "mucho a puerta, poca pegada", "bl": "ni certeros ni letales"},
        subtitulo="Precisión (llegar a puerta) vs. definición (marcar una vez ahí) · {temporada}",
        textos=(ins.definicion_que_mirar, ins.definicion_por_que), insight="definicion")


def chart_creation(df):
    """Control del balón contra lo que se crea con él. Con los datos de equipo que quedan en fbref
    (sin pases clave ni xA: eso lo borró Opta) la creación se mide por su producto —asistencias por
    90'— contra la posesión. Lo interesante son las esquinas que no siguen la diagonal."""
    return _scatter(
        df, "creacion", "Creación",
        "Cuánto balón tiene cada equipo contra cuántas asistencias genera — un punto por equipo.",
        x=_eje("ov_Poss", "Posesión (%)", "Posesión", 1),
        y=_eje("ov_Per 90 Minutes_Ast", "Asistencias por 90'", "Asistencias", 2),
        cuadrantes={"tr": "dominan y crean", "tl": "crean sin el balón",
                    "br": "tienen el balón, crean poco", "bl": "ni balón ni creación"},
        subtitulo="Posesión vs. asistencias por 90' · {temporada}",
        textos=(ins.creacion_que_mirar, ins.creacion_por_que), insight="creacion")


def chart_defense(df):
    """Cuánto le tiran a puerta a un equipo contra cuánto le entra. Los dos ejes son "menos es
    mejor", así que el cuadrante bueno es el de abajo a la izquierda."""
    return _scatter(
        df, "defensa", "Defensa",
        "Tiros a puerta que recibe cada equipo contra los goles que le entran — un punto por equipo.",
        x=_eje("p90_SoTA", "Tiros a puerta recibidos por 90'", "Tiros recibidos", 2),
        y=_eje("gk_Performance_GA90", "Goles recibidos por 90'", "Goles recibidos", 2),
        cuadrantes={"tr": "los bombardean y encajan", "tl": "pocos tiros, pero encajan",
                    "br": "muchos tiros, no les entra", "bl": "sólidos"},
        subtitulo="Tiros a puerta que recibe vs. goles que le entran, por 90' · {temporada}",
        textos=(ins.defensa_que_mirar, ins.defensa_por_que), insight="defensa")


def chart_league_level(df):
    """Nivel por liga a nivel de equipo: una caja por liga para la variable que se elija. Es la
    comparación que hacían los radares de liga (quitados), pero sobre UNA variable a la vez y viendo
    cada equipo: así se ve si una liga se distingue por su promedio o por sus extremos."""
    variables = [{"col": c, "label": e, "dec": d} for c, e, _, d in VARIABLES
                 if c in df.columns and c != "ms_Performance_CrdR"]
    return _pagina(
        "nivel-por-liga-equipos", "Nivel por liga",
        "Cómo se reparten los equipos de cada liga en la variable que elijas.",
        {"tabla": "equipos", "entidad": "equipos", "variables": variables,
         "variable": "pt_Team Success_+/-90", "subtitulo": "{variable} · {temporada}",
         "filtros": {"nivel": True}, "fuente": FUENTE_FBREF, "colorPor": ["liga"],
         "queMirar": ins.nivel_liga_equipos_que_mirar()},
        tipo="cajas", kind="box")


def chart_explorer(df):
    """"Crea tu gráfico": el lector elige las dos variables. Lleva el r² del par elegido, calculado en
    el navegador sobre los puntos dibujados."""
    return _pagina(
        "crea-tu-grafico-equipos", "Crea tu gráfico",
        f"Cruza cualquier par de las {len(VARIABLES)} variables de equipo — y el r² te dice si de verdad son dos cosas distintas o la misma medida dos veces.",
        {"tabla": "equipos", "entidad": "equipos",
         "explorador": {
             "variables": [{"col": c, "label": e, "grupo": g, "dec": d} for c, e, g, d in VARIABLES],
             "x": "ov_Poss", "y": "pt_Team Success_PPM"},
         "filtros": {"nivel": True}, "fuente": FUENTE_FBREF, "colorPor": ["liga"]},
        kind="explorer")


# Orden y agrupación de las pestañas de la sección: (slug, texto corto, familia). Se quitaron del
# sitio los radares de liga, la evolución del estilo, las dos de portería y las tres de identidad de
# liga (paridad, edad, disciplina); siguen en `code/eda_teams.ipynb`.
PESTANAS = [
    ("eficiencia-definicion", "Eficiencia de definición", "Ataque"),
    ("creacion", "Creación", "Creación"),
    ("defensa", "Defensa", "Defensa"),
    ("nivel-por-liga-equipos", "Nivel por liga", "Comparar"),
    ("crea-tu-grafico-equipos", "Crea tu gráfico", "Comparar"),
]


def _registrar_tabla(df, seasons):
    ligas = list(LEAGUE_ORDER)
    return react_views.registrar_tabla(
        "equipos", df, nombre_col="Squad", columnas=[v[0] for v in VARIABLES], ligas=ligas,
        temporadas=seasons, niveles=niveles_de(df),
        extra={
            "colores": {"claro": {l: LEAGUE_COLORS[l] for l in ligas},
                        "oscuro": {l: LEAGUE_COLORS_DARK[l] for l in ligas}},
            "divergente": dict(DIVERGING),
            "ayudas": AYUDAS,
        })


def build(assets_dir) -> list:
    df = load_data()
    seasons = seasons_of(df)
    _registrar_tabla(df, seasons)
    paginas = {p.slug: p for p in (
        chart_def_efficiency(df),
        chart_creation(df),
        chart_defense(df),
        chart_league_level(df),
        chart_explorer(df),
    )}
    salida = []
    for slug, tab, grupo in PESTANAS:
        paginas[slug].tab, paginas[slug].group = tab, grupo
        salida.append(paginas[slug])
    return salida
