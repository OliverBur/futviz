"""Vistas de Equipos del sitio, en React + MUI X Charts.

Mismas decisiones que `code/eda_teams.ipynb` (el laboratorio de cada gráfico), pero acá no se dibuja
nada: se carga y limpia la tabla de equipos, se registra UNA tabla compartida
(`react_views.registrar_tabla("equipos", ...)`) y se arma por vista la configuración que necesita el
bundle de React. Filtros, rankings y texto dinámico se calculan en el navegador.

Las cuatro vistas de ataque y defensa miden con xG (Understat), por partido y sin penales; el cálculo
está en `xg_equipos.py` y `load_data` lo pega a la tabla de FBref.
"""

import pandas as pd

import equipos_tiros
import insights as ins
import origen_xg
import react_views
import tabla_esperada
import venn_equipos
import xg_equipos
from consolidate_data import ELO_TOP, NIVELES
from nombres import aplicar_a_equipos, club_visible
from preguntas import PREGUNTAS
from site_utils import DATA_DIR, PROCESSED_DIR, ChartPage, temporadas_en_curso
from viz_theme import (
    DIVERGING, FUENTE_FBREF, FUENTE_UNDERSTAT, LEAGUE_COLORS, LEAGUE_COLORS_DARK, LEAGUE_ORDER,
)

SECTION = "Equipos"

# Las variables que se pueden poner en cada eje de "Tu propio gráfico" y en "Nivel por liga":
# (columna, etiqueta, grupo del desplegable, decimales con los que se muestra).
#
# Están casi todas por 90 minutos y no en total a propósito. Las cinco ligas no juegan la misma
# cantidad de partidos (la Bundesliga 34, las otras 38) y Ligue 1 cambió de 20 a 18 equipos en
# 2023-24, así que cualquier total mete esa diferencia dentro del dato y la mitad de los cruces
# terminarían midiendo "cuántos partidos jugó". Las excepciones son las que ya vienen normalizadas
# (porcentajes, promedios) y las rojas, que son tan pocas por partido que la tasa se vuelve ruido.
# Las de xG y goles de Understat van por partido (no hay minutos en los tiros) y sin penales.
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

    ("xg_fav", "xG a favor por partido (sin penales)", "Ocasiones y goles sin penales", 2),
    ("xg_con", "xG en contra por partido (sin penales)", "Ocasiones y goles sin penales", 2),
    ("xg_dif", "Diferencia de xG por partido (a favor − en contra)", "Ocasiones y goles sin penales", 2),
    ("gol_fav", "Goles por partido (sin penales)", "Ocasiones y goles sin penales", 2),
    ("gol_con", "Goles recibidos por partido (sin penales)", "Ocasiones y goles sin penales", 2),
    ("tiros_pp", "Tiros por partido (sin penales)", "Ocasiones y goles sin penales", 1),
    ("xg_tiro", "xG por tiro (sin penales)", "Ocasiones y goles sin penales", 3),
    ("xg_dif_local", "Diferencia de xG por partido de local", "Ocasiones y goles sin penales", 2),
    ("xg_dif_visita", "Diferencia de xG por partido de visitante", "Ocasiones y goles sin penales", 2),
    ("xp_local_pp", "Puntos esperados por partido de local", "Local y visitante", 2),
    ("xp_visita_pp", "Puntos esperados por partido de visitante", "Local y visitante", 2),
    ("pts_local_pp", "Puntos por partido de local", "Local y visitante", 2),
    ("pts_visita_pp", "Puntos por partido de visitante", "Local y visitante", 2),

    ("p90_Fls", "Faltas cometidas por 90'", "Disciplina", 2),
    ("p90_Fld", "Faltas recibidas por 90'", "Disciplina", 2),
    ("p90_CrdY", "Amarillas por 90'", "Disciplina", 2),
    ("ms_Performance_CrdR", "Rojas (total)", "Disciplina", 0),

    ("ov_Poss", "Posesión (%)", "Contexto y resultado", 1),
    ("ov_Age", "Edad media de la plantilla", "Contexto y resultado", 1),
    ("pt_Team Success_PPM", "Puntos por partido", "Contexto y resultado", 2),
    ("pt_Team Success_+/-90", "Diferencia de goles por 90'", "Contexto y resultado", 2),

    # El ELO de clubelo es una sola escala para todos los clubes de Europa: la única variable de la lista
    # que permite comparar ligas entre sí. Solo `elo_pre` se mide ANTES de la temporada; el medio y el
    # final ya contienen sus resultados. 2026-27 no tiene ELO todavía.
    ("elo_pre", "ELO al arrancar la temporada", "Nivel del club (ELO)", 0),
    ("elo_medio", "ELO medio de la temporada", "Nivel del club (ELO)", 0),
    ("elo_fin", "ELO al terminar la temporada", "Nivel del club (ELO)", 0),
]

# Las columnas de xG y goles viajan con toda su precisión (ver `react_views.registrar_tabla`): los textos
# restan una de otra y ajustan una recta, y un redondeo al viajar podría cambiar una cifra o un empate
# respecto de la que da Python.
EXACTAS = ["xg_fav", "xg_con", "xg_dif", "gol_fav", "gol_con", *equipos_tiros.COLUMNAS]

# Lo que se agrega al final del texto del explorador (el aviso del ELO es solo de equipos).
NOTA_EXPLORADOR = (
    "El ELO medio y el final ya contienen los resultados de esa temporada, así que compararlos con puntos o diferencia de "
    "goles es en parte circular; el de arranque no."
)

FUENTE_XG = FUENTE_UNDERSTAT
FUENTE_TODAS = f"{FUENTE_FBREF}, {FUENTE_UNDERSTAT} (xG) y clubelo (ELO)"

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
    """Las temporadas ya consolidadas por `code/consolidate_data.py`, con el xG de cada equipo.

    Antes se asignaba la liga por bloques de filas *hardcodeados* (18/20/18/20/20), que no
    sobrevivían a las 5 temporadas (Ligue 1 pasó de 20 a 18 equipos en 2023-24). El consolidado ya
    trae `temporada` y `liga` resueltas y verifica los tamaños.

    El xG, los goles y los partidos de Understat se calculan acá, sobre los tiros, y no en el
    consolidado: así `teams_all_seasons.csv` queda como lo dejó `consolidate_data.py`. El cruce de
    nombres entre Understat y FBref va ANTES de `aplicar_a_equipos`, con los nombres de origen."""
    crudo = pd.read_csv(PROCESSED_DIR / "teams_all_seasons.csv")
    tiros = xg_equipos.cargar_tiros(PROCESSED_DIR / "shots_all_seasons.csv")
    xg = xg_equipos.agregar(tiros, crudo)
    # Tiros por partido, xG por tiro y la diferencia de xG de local y de visitante (`equipos_tiros.py`).
    partidos = equipos_tiros.cargar_partidos(DATA_DIR, sorted(crudo["temporada"].unique()))
    tiros_sede = equipos_tiros.agregar(tiros, crudo, partidos)
    # Puntos esperados y reales por partido de local y de visitante (los mismos xPts de «Tabla real vs. esperada»).
    sede = tabla_esperada.puntos_por_sede(tiros, sorted(crudo["temporada"].unique()))
    clave = pd.DataFrame({"temporada": crudo["temporada"], "liga": crudo["liga"], "equipo": crudo["Squad"].map(club_visible)})
    puntos_sede = clave.join(sede, on=["temporada", "liga", "equipo"])[tabla_esperada.SEDE_COLS]
    df = aplicar_a_equipos(pd.concat([crudo, xg, tiros_sede, puntos_sede], axis=1))

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

def _eje(col, label, corto, dec, invertir=False):
    """Un eje: `dec` son los decimales del tooltip, la tabla y la lista Top 5. Con `invertir` se dibuja al revés (lo más
    bajo, arriba): para que arriba a la derecha estén los mejores cuando menos es mejor."""
    eje = {"col": col, "label": label, "corto": corto, "dec": dec}
    if invertir:
        eje["invertir"] = True
    return eje


def _pagina(slug, titulo, descripcion, config, tipo="scatter", kind="scatter"):
    """`descripcion` es la bajada de la tarjeta: una o dos líneas de cómo leer la gráfica, de unos 140
    caracteres como máximo."""
    assert len(descripcion) <= 160, f"{slug}: la bajada mide {len(descripcion)} caracteres"
    config = {"id": slug, "titulo": titulo, "bajada": descripcion, "pregunta": PREGUNTAS[slug], **config}
    return ChartPage(
        slug=slug, section=SECTION, title=titulo, subtitle=descripcion,
        body_html=react_views.montar_html(tipo, slug, config), kind=kind)


def _diagonal(dif, sobre, bajo, invertir=False):
    """Referencia y = x. `dif` es el nombre de la resta (y − x) que se muestra en el tooltip, la tabla y
    la lista. `sobre` y `bajo` rotulan cada lado. Con `invertir`, estar debajo de la diagonal es lo
    bueno (la defensa: menos goles de los que valían las ocasiones) y los colores se cambian. Las
    diferencias por partido son de centésimas: se muestran con dos decimales."""
    ref = {"tipo": "diagonal", "dif": dif, "sobre": sobre, "bajo": bajo, "decDif": 2}
    if invertir:
        ref["invertir"] = True
    return ref


def _promedios(cuadrantes, cuantil=None, fijo=None, etiqueta=None):
    """Líneas punteadas y un rótulo por cuadrante. Por omisión van en el promedio de cada eje (el de las temporadas
    juntas, para que "por encima del promedio" signifique lo mismo al cambiar de temporada). Con `cuantil`, en ese
    percentil de lo que se ve en cada eje (como `players._promedios`: arriba a la derecha quedan solo los más
    destacados). Con `fijo` (`{"x": 0, "y": 0}`), en esos valores, y `etiqueta` es lo que dice el pie de la gráfica
    de esas líneas."""
    ref = {"tipo": "promedios", "cuadrantes": cuadrantes}
    if cuantil:
        ref["cuantil"] = cuantil
    if fijo:
        ref["fijo"] = fijo
    if etiqueta:
        ref["etiqueta"] = etiqueta
    return ref


def _metricas(x, y, referencia, menos_es_mejor=None):
    """Qué se puede ordenar en el Top 5 (y por lo tanto qué se rotula en la gráfica): las dos variables. En los ejes
    donde menos es mejor (xG o goles en contra) la lista abre por los que menos tienen: `menos_es_mejor` dice, por
    eje, cómo se llama a esos en la ayuda."""
    menos_es_mejor = menos_es_mejor or {}

    def metrica(id_, e):
        if id_ in menos_es_mejor:
            m = {"id": id_, "etiqueta": e["corto"], "ayuda": f"Ordenados por {e['label']}: primero {menos_es_mejor[id_]}"}
            if not e.get("invertir"):    # un eje dibujado al revés ya ordena así: lo más bajo es lo más alto de la gráfica
                m["menosEsMejor"] = True
            return m
        return {"id": id_, "etiqueta": e["corto"], "ayuda": f"Ordenados por {e['label']}"}

    return [metrica("x", x), metrica("y", y)]


def _scatter(df, slug, titulo, descripcion, *, x, y, referencia, subtitulo, textos, insight,
             fuente=FUENTE_XG, menos_es_mejor=None):
    """Un scatter de equipos con el par fijo."""
    que_mirar, _ = textos
    return _pagina(slug, titulo, descripcion, {
        "tabla": "equipos", "entidad": "equipos",
        "x": x, "y": y,
        "referencia": referencia,
        "requiere": [x["col"], y["col"]],
        "subtitulo": subtitulo,
        "filtros": {"nivel": True},
        "metricas": _metricas(x, y, referencia, menos_es_mejor),
        "queMirar": que_mirar(),
        "insight": insight, "fuente": fuente, "colorPor": ["liga"],
    })


def chart_def_efficiency(df):
    """Goles contra xG: cuánto marca cada equipo de lo que sus ocasiones valían."""
    x = _eje("xg_fav", "xG a favor por partido (sin penales)", "xG", 2)
    y = _eje("gol_fav", "Goles por partido (sin penales)", "Goles", 2)
    return _scatter(
        df, "eficiencia-definicion", "Goles vs. xG del equipo",
        "A la derecha, más xG por partido; arriba, más goles. Sobre la diagonal el equipo marcó más de lo que valían sus ocasiones.",
        x=x, y=y,
        referencia=_diagonal("goles − xG", "Marcan más de lo esperado", "Marcan menos de lo esperado"),
        subtitulo="Equipos de las 5 ligas · {temporada} · por partido, sin penales",
        textos=(ins.definicion_que_mirar, ins.definicion_por_que), insight="definicion")


def chart_creation(df):
    """Ocasiones a favor contra ocasiones en contra. El eje vertical va al revés (el xG en contra más bajo, arriba) para
    que el cuadrante de arriba a la derecha sea el de los mejores."""
    x = _eje("xg_fav", "xG a favor por partido (sin penales)", "xG a favor", 2)
    y = _eje("xg_con", "xG en contra por partido (sin penales); menos, arriba", "xG en contra", 2, invertir=True)
    return _scatter(
        df, "creacion", "Ocasiones a favor y en contra",
        "A la derecha, más xG a favor; arriba, menos xG en contra. Arriba a la derecha dominan las ocasiones.",
        x=x, y=y,
        referencia=_promedios({"tr": "Dominan las ocasiones", "tl": "Partidos cerrados",
                               "br": "Partidos abiertos", "bl": "Dominan los rivales"}),
        subtitulo="Equipos de las 5 ligas · {temporada} · por partido, sin penales",
        textos=(ins.creacion_que_mirar, ins.creacion_por_que), insight="creacion",
        menos_es_mejor={"y": "los que menos ocasiones conceden"})


def chart_defense(df):
    """xG en contra contra goles recibidos, con los dos ejes al revés (menos, a la derecha y arriba) para que los mejores
    queden arriba a la derecha. El xG en contra no ve a dónde va el tiro: la distancia a la diagonal junta al portero, a la
    defensa que bloquea y a la suerte, y no se llama "mejor portero"."""
    x = _eje("xg_con", "xG en contra por partido (sin penales); menos, a la derecha", "xG en contra", 2, invertir=True)
    y = _eje("gol_con", "Goles recibidos por partido (sin penales); menos, arriba", "Goles recibidos", 2, invertir=True)
    return _scatter(
        df, "defensa", "Goles recibidos vs. xG en contra",
        "A la derecha, menos xG en contra; arriba, menos goles recibidos. Arriba a la derecha, los mejores.",
        x=x, y=y,
        referencia=_diagonal("goles recibidos − xG en contra", "Reciben menos de lo esperado",
                             "Reciben más de lo esperado"),
        subtitulo="Equipos de las 5 ligas · {temporada} · por partido, sin penales",
        textos=(ins.defensa_que_mirar, ins.defensa_por_que), insight="defensa",
        menos_es_mejor={"x": "los que menos ocasiones conceden", "y": "los que menos goles reciben"})


def chart_shots_quantity_quality(df):
    """Tiros por partido contra xG por tiro: si el equipo dispara mucho o espera la ocasión clara. Las líneas están en el
    percentil `ins.LINEA_PCT` de lo que se ve, como en las vistas de jugadores. Multiplicados, los dos ejes dan el xG a
    favor por partido de «Ocasiones a favor y en contra»."""
    x = _eje("tiros_pp", "Tiros por partido (sin penales)", "Tiros por partido", 1)
    y = _eje("xg_tiro", "xG por tiro (sin penales)", "xG por tiro", 3)
    return _scatter(
        df, "cantidad-calidad", "Cantidad vs. calidad de los tiros",
        "A la derecha, más tiros por partido; arriba, más xG por tiro. Las líneas dejan al 20% con más de cada uno.",
        x=x, y=y,
        referencia=_promedios({"tr": "Muchos tiros y buena calidad", "tl": "Pocos tiros pero buena calidad",
                               "br": "Muchos tiros pero poca calidad", "bl": "Pocos tiros y poca calidad"},
                              cuantil=ins.LINEA_PCT),
        subtitulo="Equipos de las 5 ligas · {temporada} · por partido, sin penales",
        textos=(ins.cantidad_calidad_que_mirar, ins.cantidad_calidad_por_que), insight="cantidad_calidad")


def chart_home_away(df):
    """Puntos esperados por partido de local contra de visitante: lo que valían las ocasiones de cada partido, en puntos.
    Las líneas punteadas son el promedio de cada sede (el de las temporadas juntas)."""
    x = _eje("xp_local_pp", "Puntos esperados por partido, de local", "De local", 2)
    y = _eje("xp_visita_pp", "Puntos esperados por partido, de visitante", "De visitante", 2)
    return _scatter(
        df, "local-visitante", "Local vs. visitante",
        "A la derecha, más puntos esperados de local; arriba, de visitante. Las líneas son el promedio de cada sede.",
        x=x, y=y,
        referencia=_promedios({"tr": "Fuertes de local y de visita", "tl": "Fuertes solo de visita",
                               "br": "Fuertes solo de local", "bl": "Flojos de local y de visita"}),
        subtitulo="Equipos de las 5 ligas · {temporada} · puntos esperados por partido, por sus ocasiones",
        textos=(ins.local_visitante_que_mirar, ins.local_visitante_por_que), insight="local_visitante")


def chart_league_level(df):
    """Nivel por liga a nivel de equipo: una banda y una mediana por liga para la variable que se elija. Es la
    comparación que hacían los radares de liga (quitados), pero sobre UNA variable a la vez y viendo
    cada equipo: así se ve si una liga se distingue por su promedio o por sus extremos."""
    variables = [{"col": c, "label": e, "dec": d} for c, e, _, d in VARIABLES
                 if c in df.columns and c != "ms_Performance_CrdR"]
    return _pagina(
        "nivel-por-liga-equipos", "Distribución por liga",
        "Cada liga lleva una raya en la mediana y una banda con la mitad central de sus equipos; cada punto es un equipo.",
        {"tabla": "equipos", "entidad": "equipos", "variables": variables,
         # Abre en goles por 90': la diferencia de goles suma cero dentro de cada liga y todas las
         # medianas quedaban en 0 (ver `nivel_liga_equipos_que_mirar`).
         "variable": "ov_Per 90 Minutes_Gls", "subtitulo": "{variable} · {temporada}",
         "filtros": {"nivel": True}, "fuente": FUENTE_TODAS, "colorPor": ["liga"],
         "queMirar": ins.nivel_liga_equipos_que_mirar()},
        tipo="cajas", kind="box")


def chart_explorer(df):
    """"Tu propio gráfico": el lector elige las dos variables. Es un lienzo libre: el texto solo dice quién va arriba en cada
    eje, y se calcula en el navegador sobre los puntos dibujados."""
    return _pagina(
        "crea-tu-grafico-equipos", "Tu propio gráfico",
        f"Cruza cualquier par de las {len(VARIABLES)} variables de equipo. Tú eliges los dos ejes.",
        {"tabla": "equipos", "entidad": "equipos",
         "explorador": {
             "variables": [{"col": c, "label": e, "grupo": g, "dec": d} for c, e, g, d in VARIABLES],
             "x": "ov_Poss", "y": "pt_Team Success_PPM", "nota": NOTA_EXPLORADOR},
         "filtros": {"nivel": True}, "fuente": FUENTE_TODAS, "colorPor": ["liga"]},
        kind="explorer")


# Orden y agrupación de las pestañas de la sección: (slug, texto corto, familia). Se quitaron del
# sitio los radares de liga, la evolución del estilo, las dos de portería y las tres de identidad de
# liga (paridad, edad, disciplina); siguen en `code/eda_teams.ipynb`.
PESTANAS = [
    ("tabla-esperada", "Tabla real vs. esperada", "Temporada"),    # la primera: es la que abre la sección
    ("eficiencia-definicion", "Goles vs. xG", "Ocasiones"),
    ("creacion", "Ocasiones a favor y en contra", "Ocasiones"),
    ("origen-xg", "Cómo generan peligro", "Ocasiones"),
    ("cantidad-calidad", "Cantidad vs. calidad de los tiros", "Ocasiones"),
    ("defensa", "Goles recibidos vs. xG", "Defensa"),
    ("equipo-completo", "Equipo completo", "Contexto"),
    ("local-visitante", "Local vs. visitante", "Contexto"),
    ("nivel-por-liga-equipos", "Distribución por liga", "Contexto"),
    ("crea-tu-grafico-equipos", "Tu propio gráfico", "_explorar"),   # "_": grupo aparte, sin rótulo
]


def _registrar_tabla(df, seasons):
    ligas = list(LEAGUE_ORDER)
    return react_views.registrar_tabla(
        "equipos", df, nombre_col="Squad", columnas=[v[0] for v in VARIABLES], ligas=ligas,
        temporadas=seasons, niveles=niveles_de(df), exactas=EXACTAS,
        extra={
            "colores": {"claro": {l: LEAGUE_COLORS[l] for l in ligas},
                        "oscuro": {l: LEAGUE_COLORS_DARK[l] for l in ligas}},
            "divergente": dict(DIVERGING),
            "ayudas": AYUDAS,
            "enCurso": temporadas_en_curso(),
        })


def build(assets_dir) -> list:
    df = load_data()
    seasons = seasons_of(df)
    _registrar_tabla(df, seasons)
    paginas = {p.slug: p for p in (
        chart_def_efficiency(df),
        chart_creation(df),
        chart_defense(df),
        venn_equipos.chart_venn_equipos(df),
        chart_shots_quantity_quality(df),
        chart_home_away(df),
        origen_xg.chart_origen_xg(),
        chart_league_level(df),
        chart_explorer(df),
        tabla_esperada.chart_tabla_esperada(),
    )}
    salida = []
    for slug, tab, grupo in PESTANAS:
        paginas[slug].tab, paginas[slug].group = tab, grupo
        salida.append(paginas[slug])
    return salida
