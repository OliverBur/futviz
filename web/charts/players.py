"""Vistas de Jugadores del sitio, en React + MUI X Charts.

Mismas decisiones que `code/eda_players.ipynb` (que sigue siendo el laboratorio de cada gráfico),
pero acá ya no se dibuja nada: este módulo carga y limpia los datos, registra UNA tabla compartida
(`react_views.registrar_tabla("jugadores", ...)`) y arma, por vista, la configuración que el bundle
de React necesita (ejes, referencias, filtros, textos fijos). Los filtros, los rankings y el texto
dinámico los calcula el navegador sobre la tabla — ver `react_views` y `web/react/src`.
"""

import pandas as pd

import insights as ins
import react_views
import shot_map
from consolidate_data import ELO_TOP, NIVELES, POSICIONES
from nombres import JUGADORES, aplicar_a_jugadores, club_visible
from preguntas import PREGUNTAS
from site_utils import PROCESSED_DIR, ChartPage, temporadas_en_curso
from viz_theme import (
    DIVERGING, FUENTE_FBREF, FUENTE_UNDERSTAT, LEAGUE_COLORS, LEAGUE_COLORS_DARK, LEAGUE_ORDER,
    PITCH_ZONAS,
)

SECTION = "Jugadores"

# Casi todo lo de esta sección sale de Understat (es quien publica xG/xA a nivel de jugador; FBref
# dejó de hacerlo), así que ese crédito es el default. Las dos gráficas puramente defensivas son al
# revés: cada punto es una cuenta de FBref dividida por minutos de FBref, y Understat no aporta ni
# una; acreditar a Understat un dato que no publica sería sencillamente falso. Hay mixtas que
# acreditan a las dos: "Crea tu gráfico" (los centros y la producción contra la recuperación quedan ahí como variables).
FUENTE_MIXTA = f"{FUENTE_UNDERSTAT} y {FUENTE_FBREF}"

# Las variables que se pueden poner en cada eje de "Crea tu gráfico":
# (columna, etiqueta, grupo del desplegable, decimales con los que se muestra).
# Los totales conviven con sus tasas por 90' a propósito: son preguntas distintas —quién produjo
# más en la temporada contra quién produce más cuando está en la cancha— y cruzar una contra la
# otra es una de las cosas interesantes que se pueden hacer acá.
VARIABLES = [
    ("goals", "Goles", "Producción", 0),
    ("a", "Asistencias", "Producción", 0),
    ("np_goals", "Goles sin penales", "Producción", 0),
    ("g90", "Goles por 90'", "Producción", 2),
    ("npg90", "Goles sin penales por 90'", "Producción", 2),
    ("a90", "Asistencias por 90'", "Producción", 2),

    ("xG", "xG", "Esperado", 1),
    ("xA", "xA", "Esperado", 1),
    ("np_xg", "xG sin penales", "Esperado", 1),
    ("xG90", "xG por 90'", "Esperado", 2),
    ("npxg90", "xG sin penales por 90' (npxG/90)", "Esperado", 2),
    ("xA90", "xA por 90'", "Esperado", 2),
    ("xga90", "Producción esperada por 90' (xG + xA)", "Esperado", 2),
    ("xg_chain", "xG de las jugadas en que participó", "Esperado", 1),
    ("xg_buildup", "xG de construcción (sin tiro ni asistencia)", "Esperado", 1),
    ("xgchain90", "xG de las jugadas en que participó, por 90'", "Esperado", 2),
    ("xgbuild90", "xG de construcción por 90'", "Esperado", 2),

    ("shots", "Tiros", "Volumen de juego", 0),
    ("sh90", "Tiros por 90'", "Volumen de juego", 2),
    ("key_passes", "Pases clave", "Volumen de juego", 0),
    ("kp90", "Pases clave por 90'", "Volumen de juego", 2),
    ("crosses90", "Centros por 90'", "Volumen de juego", 2),
    ("offsides90", "Fueras de juego por 90'", "Volumen de juego", 2),

    ("min", "Minutos jugados", "Contexto y disciplina", 0),
    ("edad", "Edad", "Contexto y disciplina", 0),
    ("yellow_cards", "Amarillas", "Contexto y disciplina", 0),
    ("red_cards", "Rojas", "Contexto y disciplina", 0),
    ("fouled90", "Faltas recibidas por 90'", "Contexto y disciplina", 2),

    # Lo único defensivo que existe a nivel jugador: viene de fbref, no de Understat, y por eso puede
    # faltar (ver `variables_disponibles`).
    ("recoveries90", "Recuperaciones por 90'", "Defensa", 2),
    ("tkl_w90", "Entradas ganadas por 90'", "Defensa", 2),
    ("interceptions90", "Intercepciones por 90'", "Defensa", 2),
    ("fouls90", "Faltas cometidas por 90'", "Defensa", 2),
    ("recoveries", "Recuperaciones", "Defensa", 0),
]

MIN_MINUTES = 500

# Corte de minutos por temporada. `MIN_MINUTES` (500) asume una temporada cerrada — con 5 jornadas
# jugadas nadie llega ahí y el corte deja SOLO a la liga que va más adelantada en el calendario.
# Para la temporada en curso el corte baja a una fracción de los minutos máximos que se jugaron
# hasta ahora, así las 5 ligas muestran algo desde el arranque y el número se ajusta solo, jornada
# a jornada. El piso evita que un corte casi en 0 deje pasar a cualquiera con un cuarto de hora en
# cancha. Se calcula en `load_data()`, sobre los datos SIN filtrar.
MIN_MINUTES_FRACCION = 0.4
MIN_MINUTES_PISO = 90
MIN_MINUTES_POR_TEMPORADA = {}  # {temporada: corte} — lo llena `load_data()`

# Las vistas "por 90'" (xG por 90 vs. goles por 90, etc.) piden más: con 500 minutos una tasa por 90 se dispara con un solo
# gol. Mismo criterio que arriba, con tope 900 en las temporadas cerradas; la que va en curso conserva su corte relativo.
MIN_MINUTES_90 = 900
MIN_MINUTES_90_POR_TEMPORADA = {}  # {temporada: corte} — lo llena `load_data()`

# Notas de los filtros (la (i) junto al control).
AYUDAS = {
    # Sub-21: `sub21` la calcula `consolidate_data.py` con el año de nacimiento que aporta fbref
    # (Understat no publica edad); quien no cruzó por nombre queda sin edad, o sea fuera del filtro.
    "sub21": "Menos de 21 al arrancar la temporada, cuenta el año de nacimiento.",
    # Nivel del club: el umbral está en `consolidate_data.ELO_TOP`. El punto es una persona, así que
    # el filtro habla del equipo en el que jugó esa temporada (el último, si cambió a mitad).
    "nivel": (f"Corte en {ELO_TOP} de ELO (clubelo) del club al arrancar la temporada: el 20% más alto "
              f"de las 5 ligas. Quien cambió de club cuenta por el último, que es el que muestra el "
              f"hover. Si la temporada aún no tiene ELO, se usa el último nivel conocido del club."),
}

# Las columnas defensivas que trae fbref vía `consolidate_data.MISC_COLS`. Son opcionales igual que
# `sub21`: `fbref-players.csv` puede no estar, y entonces las gráficas defensivas no se dibujan.
DEF_COLS = ["recoveries90", "tkl_w90", "interceptions90", "fouls90"]


def load_data():
    """Las temporadas de Understat ya consolidadas.

    `consolidate_data.py` ya decodifica las entidades HTML de los nombres, pero a propósito NO toca
    `team`: los jugadores que cambiaron de club a mitad de temporada traen los dos separados por coma
    y quedarse con uno es decisión de análisis. Acá se toma el último, que es la misma decisión que
    en `eda_players.ipynb`."""
    df = pd.read_csv(PROCESSED_DIR / "players_all_seasons.csv")
    df["team"] = df["team"].str.split(",").str[-1].str.strip()
    df = aplicar_a_jugadores(df)       # nombres como se dicen: «Kylian Mbappé», «Atlético Madrid»
    df["liga"] = pd.Categorical(df["liga"], categories=LEAGUE_ORDER, ordered=True)

    global MIN_MINUTES_POR_TEMPORADA, MIN_MINUTES_90_POR_TEMPORADA
    MIN_MINUTES_POR_TEMPORADA = {
        temporada: max(MIN_MINUTES_PISO,
                        min(MIN_MINUTES, round(MIN_MINUTES_FRACCION * maximo)))
        for temporada, maximo in df.groupby("temporada")["min"].max().items()
    }
    MIN_MINUTES_90_POR_TEMPORADA = {
        temporada: max(MIN_MINUTES_PISO,
                        min(MIN_MINUTES_90, round(MIN_MINUTES_FRACCION * maximo)))
        for temporada, maximo in df.groupby("temporada")["min"].max().items()
    }
    umbral = df["temporada"].map(MIN_MINUTES_POR_TEMPORADA)
    df = df[df["min"] >= umbral].reset_index(drop=True)

    # Derivadas. Las tasas por 90' van sobre los minutos reales y no sobre los partidos: `apps` cuenta
    # también las entradas desde el banco, así que dividir por ahí inflaría la tasa de cualquier
    # suplente. La edad sale del año de nacimiento con el mismo criterio que `sub21`.
    noventas = df["min"] / 90
    df = pd.concat([df, pd.DataFrame({
        "g90": df["goals"] / noventas,
        "npg90": df["np_goals"] / noventas,
        "npxg90": df["np_xg"] / noventas,
        "a90": df["a"] / noventas,
        "sh90": df["shots"] / noventas,
        "kp90": df["key_passes"] / noventas,
        # Producción esperada total, para el perfil de dos fases: se suma acá y no en la consolidación
        # porque es una derivada de análisis (qué se considera "producir"), no un dato de la fuente.
        "xga90": df["xG90"] + df["xA90"],
        # xG Chain / Buildup vienen como TOTAL de la temporada; por 90' para poder compararlos.
        "xgchain90": df["xg_chain"] / noventas,
        "xgbuild90": df["xg_buildup"] / noventas,
        "edad": df["temporada"].str[:4].astype(int) - df["born"],
    })], axis=1)
    return con_percentiles_defensa(df)


def con_percentiles_defensa(df):
    """`pct_stopper` y `pct_cover` (0 a 100, un decimal; vacío para quien no es defensa o no pasa el corte por 90').
    El percentil se saca DENTRO de cada temporada entre los defensas que pasan `MIN_MINUTES_90_POR_TEMPORADA` y tienen
    las tres cuentas de fbref: así el cambio de criterio de las intercepciones entre temporadas no mueve a nadie.
    Stopper = promedio de los percentiles de entradas ganadas y de faltas cometidas; Cover = percentil de
    intercepciones (las recuperaciones de este proyecto son entradas + intercepciones: no son una variable más)."""
    df = df.copy()
    cols = ["tkl_w90", "fouls90", "interceptions90"]
    if not all(c in df.columns for c in cols):
        df["pct_stopper"] = df["pct_cover"] = float("nan")
        return df
    pop = ((df["posicion"] == "Defensa") & df[cols].notna().all(axis=1)
           & (df["min"] >= df["temporada"].map(MIN_MINUTES_90_POR_TEMPORADA)))
    pct = {c: df[c].where(pop).groupby(df["temporada"]).rank(pct=True) * 100 for c in cols}
    df["pct_stopper"] = ((pct["tkl_w90"] + pct["fouls90"]) / 2).round(1)
    df["pct_cover"] = pct["interceptions90"].round(1)
    return df


def seasons_of(df):
    return sorted(df["temporada"].unique())


def posiciones_de(df):
    """Las posiciones que de verdad aparecen en los datos, en orden de cancha: un control no ofrece
    una opción que dejaría el gráfico vacío."""
    if "posicion" not in df.columns:
        return []
    return [p for p in POSICIONES if (df["posicion"] == p).any()]


def niveles_de(df):
    if "nivel" not in df.columns:
        return []
    return [n for n in NIVELES if (df["nivel"] == n).any()]


def hay_defensivas(df):
    return all(c in df.columns and df[c].notna().any() for c in DEF_COLS)


def variables_disponibles(df):
    """Las variables que el explorador puede ofrecer con estos datos (las de fbref pueden faltar)."""
    return [v for v in VARIABLES if v[0] in df.columns]


# --- configuración de las vistas ---------------------------------------------------------------

def _eje(col, label, corto, dec, dec_lista=None):
    """Un eje. `dec` son los decimales del tooltip y de la tabla; `dec_lista`, los de la lista Top 5 y
    las etiquetas, cuando hace falta distinguir más (un xG de 9.06 contra 9.1)."""
    eje = {"col": col, "label": label, "corto": corto, "dec": dec}
    if dec_lista is not None:
        eje["decLista"] = dec_lista
    return eje


def _metricas(x, y, referencia):
    """Qué se puede ordenar en el Top 5 (y por lo tanto qué se rotula en la gráfica): las dos variables."""
    return [{"id": "x", "etiqueta": x["corto"], "ayuda": f"Ordenados por {x['label']}"},
            {"id": "y", "etiqueta": y["corto"], "ayuda": f"Ordenados por {y['label']}"}]


def _diagonal(x, y, dif, sobre="Sobrerrendimiento", bajo="Bajo rendimiento", banda=None, dec_dif=None):
    """La diagonal "marcó lo esperado". `banda`: la franja de azar (el valor z de una Poisson alrededor del xG, 1.64 =
    90%); sin ella en las vistas por 90'. `dec_dif`: decimales de la diferencia (por 90' son centésimas: 2)."""
    ref = {"tipo": "diagonal", "dif": dif, "sobre": sobre, "bajo": bajo}
    if banda:
        ref["banda"] = banda
    if dec_dif is not None:
        ref["decDif"] = dec_dif
    return ref


PROMEDIOS = {"tipo": "promedios"}   # líneas punteadas en el promedio de cada eje (de TODAS las temporadas)


# Las posiciones que se marcan al abrir las vistas de ataque y creación (sin porteros, que hacen casi todo "cero").
POSICIONES_INI = ["Defensa", "Medio", "Delantero"]


def _promedios(cuadrantes, cuantil=ins.LINEA_PCT):
    """Las líneas punteadas con un rótulo por cuadrante (`tr`, `tl`, `br`, `bl`). Van en el percentil `cuantil` de lo que se ve
    en cada eje (no en el promedio): así arriba a la derecha quedan solo los más destacados. `cuantil=None`: el promedio de
    las temporadas juntas."""
    ref = {"tipo": "promedios", "cuadrantes": cuadrantes}
    if cuantil:
        ref["cuantil"] = cuantil
    return ref


def _pagina(slug, titulo, descripcion, config, kind="scatter"):
    """`descripcion` es la bajada de la tarjeta: una o dos líneas de cómo leer la gráfica, de unos 140
    caracteres como máximo (en el teléfono es lo que cabe sin que nadie la salte)."""
    assert len(descripcion) <= 160, f"{slug}: la bajada mide {len(descripcion)} caracteres"
    config = {"id": slug, "titulo": titulo, "bajada": descripcion, "pregunta": PREGUNTAS[slug], **config}
    return ChartPage(
        slug=slug, section=SECTION, title=titulo, subtitle=descripcion,
        body_html=react_views.montar_html("scatter", slug, config), kind=kind)


def con_minimo_por90(df):
    """Los jugador-temporada que pasan el corte de las vistas "por 90'" (`MIN_MINUTES_90_POR_TEMPORADA`)."""
    return df[df["min"] >= df["temporada"].map(MIN_MINUTES_90_POR_TEMPORADA)].reset_index(drop=True)


def _scatter(slug, titulo, descripcion, *, x, y, referencia, subtitulo, textos, insight, poblacion,
             fuente=FUENTE_UNDERSTAT, extra_requiere=(), color_por=None, minimo_por90=False,
             posiciones_ini=None, posicion=True, nota=None):
    """Una vista de dispersión con un par de variables fijo.

    `poblacion` es el DataFrame sobre el que se calculan los textos fijos ("por qué estas variables");
    lo que se ve en pantalla se restringe a las filas con dato en `requiere`, que es la misma
    población. `minimo_por90`: la vista usa el corte de minutos de las tasas por 90' (en el navegador
    lo aplica `ScatterVista`; aquí se recorta la población de los textos). `posiciones_ini`: las posiciones
    marcadas al abrir (la lista vacía de siempre = todas menos porteros)."""
    if minimo_por90:
        poblacion = con_minimo_por90(poblacion)
    que_mirar, por_que = textos
    cfg = {
        "tabla": "jugadores", "entidad": "jugadores",
        "x": x, "y": y, "referencia": referencia,
        "requiere": [x["col"], y["col"], *extra_requiere],
        "subtitulo": subtitulo,
        "filtros": {"posicion": posicion, "nivel": True, "sub21": True},
        "metricas": _metricas(x, y, referencia),
        "queMirar": que_mirar(), "porQue": por_que(poblacion),
        "insight": insight, "fuente": fuente,
        "colorPor": color_por or ["liga"],
    }
    if nota:
        cfg["nota"] = nota
    if minimo_por90:
        cfg["minimoPor90"] = True
    if posiciones_ini:
        cfg["posicionesIni"] = list(posiciones_ini)
    return _pagina(slug, titulo, descripcion, cfg)


def chart_xg_goals_90(df):
    """xG por 90' contra goles por 90', sin penales, con la línea de la élite en ocasiones y tres zonas rotuladas."""
    x = _eje("npxg90", "xG sin penales por 90'", "xG por 90'", 2)
    y = _eje("npg90", "Goles sin penales por 90'", "Goles por 90'", 2)
    ref = _diagonal(x, y, "goles − xG sin penales por 90'", dec_dif=2)
    # Cuatro zonas: la línea vertical de la élite en ocasiones y la diagonal (marcó lo esperado). tr/tl/br/bl: arriba o
    # abajo, derecha o izquierda.
    ref["zonas"] = {"pct": ins.ELITE_PCT, "tr": "Grandes ocasiones y finalizadores de élite",
                    "br": "Grandes ocasiones con peor finalización", "bl": "Sin ocasiones y peor finalizador",
                    "tl": "Pocas chances y gran finalizador"}
    return _scatter(
        "xg-vs-goles-90", "xG vs. goles por 90'",
        f"Sobre la diagonal marcó más que su xG; a la derecha de la línea, el {ins._pct_elite()} con más xG.",
        x=x, y=y, referencia=ref,
        subtitulo="Jugadores con ≥{min} min · {temporada}",
        textos=(ins.xg_goles_90_que_mirar, ins.xg_goles_90_por_que), insight="xg_goles_90", poblacion=df,
        color_por=["liga", "rendimiento"], minimo_por90=True, posiciones_ini=POSICIONES_INI)


def chart_xa_assists_90(df):
    x, y = _eje("xA90", "xA por 90'", "xA por 90'", 2), _eje("a90", "Asistencias por 90'", "Asistencias por 90'", 2)
    ref = _diagonal(x, y, "asistencias − xA por 90'", dec_dif=2,
                    sobre="Asiste más de lo esperado", bajo="Asiste menos de lo esperado")
    # La vertical (el 20% con más xA) y la diagonal (dio lo esperado) parten la gráfica en cuatro zonas.
    ref["zonas"] = {"pct": ins.LINEA_PCT, "variable": "xA por 90'", "tl": "Asisten más de lo esperado",
                    "tr": "Élite en creación", "bl": "Poco involucramiento", "br": "Asisten menos de lo esperado"}
    return _scatter(
        "xa-vs-asistencias-90", "xA vs. asistencias por 90'",
        "Sobre la diagonal dio más asistencias que su xA; a la derecha de la línea, el 20% con más xA.",
        x=x, y=y, referencia=ref,
        subtitulo="Jugadores con ≥{min} min · {temporada}",
        textos=(ins.xa_asist_90_que_mirar, ins.xa_asist_90_por_que), insight="xa_asist_90", poblacion=df,
        color_por=["liga", "rendimiento"], minimo_por90=True, posiciones_ini=POSICIONES_INI)


def chart_profile(df):
    x, y = _eje("xG90", "xG por 90'", "xG90", 2), _eje("xA90", "xA por 90'", "xA90", 2)
    return _scatter(
        "perfil-ofensivo", "Perfil ofensivo: xG90 vs. xA90",
        "A la derecha, más xG por 90' (remata); arriba, más xA por 90' (crea). Abre con medios y delanteros.",
        x=x, y=y,
        referencia=_promedios({"tl": "Élite en creación, pocos remates: generan",
                               "tr": "Élite en creación y remates: generan y finalizan",
                               "br": "Poca creación y élite en remates: finalizan",
                               "bl": "Poca creación y pocos remates: poco involucramiento"}),
        subtitulo="Jugadores con ≥{min} min · {temporada}",
        textos=(ins.perfil_que_mirar, ins.perfil_por_que), insight="perfil", poblacion=df,
        posiciones_ini=["Medio", "Delantero"])   # el de atacantes: no incluye defensas


def chart_cover_stopper(df):
    """Defensa: percentil de Cover (intercepciones) contra percentil de Stopper (entradas ganadas y faltas), entre los
    defensas con el corte por 90'. Los percentiles los calcula `load_data` (`pct_cover`, `pct_stopper`)."""
    x = _eje("pct_cover", "Cobertura: percentil de intercepciones por 90'", "Cobertura", 0)
    y = _eje("pct_stopper", "Corte: percentil de entradas ganadas y faltas por 90'", "Corte", 0)
    return _scatter(
        "corte-vs-cobertura", "Corte vs. Cobertura",
        "Arriba, los defensas que van al choque (corte); a la derecha, los que leen el pase (cobertura).",
        x=x, y=y,
        referencia={"tipo": "promedios", "fijo": {"x": ins.LINEA_PERCENTIL, "y": ins.LINEA_PERCENTIL},
                    "cuadrantes": {"tr": "Corte y cobertura", "tl": "Corte", "br": "Cobertura", "bl": "Casi no aparecen"}},
        subtitulo="Defensas con ≥{min} min · {temporada}",
        textos=(ins.cover_stopper_que_mirar, ins.cover_stopper_por_que), insight="cover_stopper",
        poblacion=df[df["pct_stopper"].notna()].reset_index(drop=True), fuente=FUENTE_FBREF,
        minimo_por90=True, posicion=False,
        nota="Solo hay entradas ganadas, intercepciones y faltas: sin despejes, bloqueos ni duelos aéreos.")


def _chart_creacion(df, *, slug, titulo, x, y, subtitulo, descripcion, textos, insight, referencia=PROMEDIOS,
                    fuente=FUENTE_UNDERSTAT, minimo_por90=False, posiciones_ini=None):
    """Una vista de creación de juego: dos tasas por 90' y una línea en el promedio de cada eje.
    Se trabaja sobre los jugadores que tienen las dos columnas (los centros vienen de fbref y no todos
    cruzaron), y las temporadas del selector son las que de verdad tienen dato."""
    d = df[df[x["col"]].notna() & df[y["col"]].notna()].reset_index(drop=True)
    return _scatter(slug, titulo, descripcion, x=x, y=y, referencia=referencia, subtitulo=subtitulo,
                    textos=textos, insight=insight, poblacion=d, fuente=fuente, minimo_por90=minimo_por90,
                    posiciones_ini=posiciones_ini)


def chart_key_passes_assists(df):
    return _chart_creacion(
        df, slug="pases-clave-vs-asistencias", titulo="Pases clave vs. asistencias por 90'",
        x=_eje("kp90", "Pases clave por 90'", "Pases clave por 90'", 2),
        y=_eje("a90", "Asistencias por 90'", "Asistencias por 90'", 2),
        subtitulo="Jugadores con ≥{min} min · {temporada}",
        descripcion="A la derecha, más pases clave por 90' (los que acaban en tiro); arriba, más asistencias por 90'.",
        referencia=_promedios({"tl": "Pocos pases clave, muy aprovechados", "tr": "Élite en creación y finalizan",
                               "bl": "Poco involucramiento", "br": "Élite en creación pero no finalizan"}),
        textos=(ins.pases_asist_que_mirar, ins.pases_asist_por_que), insight="pases_asist", minimo_por90=True,
        posiciones_ini=POSICIONES_INI)


def chart_build_vs_produce(df):
    return _chart_creacion(
        df, slug="construir-vs-producir", titulo="Construcción vs. producción",
        x=_eje("xgbuild90", "xG de construcción por 90'", "Construcción", 2),
        y=_eje("xga90", "Producción esperada por 90' (xG + xA)", "Producción", 2),
        subtitulo="Jugadores con ≥{min} min · {temporada}",
        descripcion="A la derecha, quien más construye (xG de construcción por 90'); arriba, quien más produce directo (xG + xA).",
        referencia=_promedios({"tl": "Finalizadores", "tr": "Élite en construcción y finalización",
                               "bl": "Poco involucramiento", "br": "Creación de juego"}),
        textos=(ins.construir_que_mirar, ins.construir_por_que), insight="construir", posiciones_ini=POSICIONES_INI)


def chart_explorer(df):
    """"Crea tu gráfico": el lector elige las dos variables. No lleva "qué mirar" (no hay un "acá" del
    que hablar cuando el "acá" lo elige quien mira); lleva el r² del par elegido, calculado en el
    navegador sobre los puntos que están dibujados."""
    variables = variables_disponibles(df)
    cfg = {
        "tabla": "jugadores", "entidad": "jugadores",
        "explorador": {
            "variables": [{"col": c, "label": e, "grupo": g, "dec": d} for c, e, g, d in variables],
            "x": "shots", "y": "goals",
        },
        "filtros": {"posicion": True, "nivel": True, "sub21": True},
        "fuente": FUENTE_MIXTA, "colorPor": ["liga"],
    }
    return _pagina(
        "crea-tu-grafico-jugadores", "Crea tu gráfico",
        f"Cruza cualquier par de las {len(variables)} variables de jugador. El r² dice si son dos cosas distintas o la misma medida dos veces.",
        cfg, kind="explorer")


def _nombre_jugador_de_tiros():
    """`f(temporada, nombre de Understat)` -> el nombre como lo ve el resto del sitio (el de FBref cuando cruzó, los
    alias de `nombres.py` cuando no). Los tiros no traen el cruce con FBref; lo trae la tabla de jugadores."""
    p = pd.read_csv(PROCESSED_DIR / "players_all_seasons.csv", encoding="utf-8-sig",
                    usecols=["temporada", "player", "team", "player_fbref"]).drop_duplicates(["temporada", "player"])
    p["visible"] = aplicar_a_jugadores(p)["player"].to_numpy()
    mapa = dict(zip(zip(p["temporada"], p["player"]), p["visible"]))
    return lambda t, nombre: mapa.get((t, nombre)) or JUGADORES.get(nombre, nombre)


def chart_shot_map():
    """Mapa de calor de los tiros: el único gráfico de la sección que no sale de la tabla de jugadores
    sino del detalle de tiros, y el único cuyo punto no es un jugador sino un remate."""
    df, descartes = shot_map.load(PROCESSED_DIR / "shots_all_seasons.csv")
    seasons = sorted(df["temporada"].unique())
    react_views.registrar_payload("tiros", shot_map.tabla_agregada(df, descartes, seasons))
    # los tiros uno por uno, una tabla por temporada: el navegador pide la de la temporada que se mira cuando
    # alguien elige un jugador o un equipo (el mapa de todos no la necesita)
    nombre_jugador = _nombre_jugador_de_tiros()
    for t in seasons:
        react_views.registrar_payload(f"tiros-{t}", shot_map.tabla_temporada(df, t, nombre_jugador, club_visible))
    cfg = {
        "tabla": "tiros", "fuente": FUENTE_UNDERSTAT, "enCurso": temporadas_en_curso(),
        "queMirar": ins.tiros_que_mirar(),
        "porQue": ins.tiros_por_que(len(df), descartes["penales"], descartes["fuera"]),
    }
    bajada = "Cada celda es el % de los tiros que salió de ahí, no un conteo: oscuro es una parte grande del total."
    config = {"id": "mapa-tiros", "titulo": "Mapa de calor de los tiros", "bajada": bajada,
              "pregunta": PREGUNTAS["mapa-tiros"], **cfg}
    return ChartPage(
        slug="mapa-tiros", section=SECTION, title="Mapa de calor de los tiros",
        subtitle=bajada,
        body_html=react_views.montar_html("tiros", "mapa-tiros", config), kind="heatmap")


# Orden y agrupación de las pestañas de la sección: (slug, texto corto, familia). Lo que no esté acá
# no se muestra, así que una vista nueva obliga a decidir en qué familia vive.
PESTANAS = [
    ("xg-vs-goles-90", "xG vs. goles por 90", "Ataque"),          # la primera: es la que abre la página
    ("perfil-ofensivo", "Rematar vs. crear", "Ataque"),
    ("mapa-tiros", "Mapa de tiros", "Ataque"),
    ("xa-vs-asistencias-90", "xA vs. asistencias por 90", "Creación"),
    ("pases-clave-vs-asistencias", "Pases clave vs. asistencias", "Creación"),
    ("construir-vs-producir", "Construcción vs. producción", "Creación"),
    ("corte-vs-cobertura", "Corte vs. Cobertura", "Defensa"),
    ("jugador-completo", "Jugador completo", "_explorar"),
    ("edad", "Edad", "_explorar"),
    ("crea-tu-grafico-jugadores", "Crea tu gráfico", "_explorar"),   # "_": grupo aparte, sin rótulo
]


def _ordenar_pestanas(paginas):
    por_slug = {p.slug: p for p in paginas}
    salida = []
    for slug, tab, grupo in PESTANAS:
        if slug in por_slug:
            p = por_slug.pop(slug)
            p.tab, p.group = tab, grupo
            salida.append(p)
    assert not por_slug, f"vistas sin pestaña definida: {sorted(por_slug)}"
    return salida


# Columnas que no viajan: el navegador las deriva con la MISMA operación que `load_data` y
# `consolidate_data` (ver `react_views.registrar_tabla`). Las tasas por 90' son conteo / (minutos / 90).
DERIVADAS = {
    "xga90": ["suma", "xG90", "xA90"],
    "recoveries90": ["suma", "tkl_w90", "interceptions90"],
    "g90": ["por90", "goals"], "npg90": ["por90", "np_goals"], "npxg90": ["por90", "np_xg"], "a90": ["por90", "a"], "sh90": ["por90", "shots"],
    "kp90": ["por90", "key_passes"], "xgchain90": ["por90", "xg_chain"],
    "xgbuild90": ["por90", "xg_buildup"],
}
# Los operandos de `recoveries90` (cuentas de fbref ÷ minutos de fbref, que no viajan) y de `xga90`.
EXACTAS = ["tkl_w90", "interceptions90", "xG90", "xA90"]


def _registrar_tabla(df, seasons):
    # Las columnas que alimentan una derivada viajan aunque no estén entre las variables (conteos).
    columnas = [v[0] for v in VARIABLES] + ["xg_chain", "xg_buildup", "key_passes", "shots", "pct_stopper", "pct_cover"]
    ligas = list(LEAGUE_ORDER)
    posiciones = posiciones_de(df)
    return react_views.registrar_tabla(
        "jugadores", df, nombre_col="player", equipo_col="team", columnas=columnas, ligas=ligas,
        temporadas=seasons, posiciones=posiciones, niveles=niveles_de(df), sub21_col="sub21",
        derivadas=DERIVADAS, exactas=EXACTAS,
        extra={
            "colores": {"claro": {l: LEAGUE_COLORS[l] for l in ligas},
                        "oscuro": {l: LEAGUE_COLORS_DARK[l] for l in ligas}},
            "divergente": dict(DIVERGING),
            # Los colores de posición son los de la mini cancha (`viz_theme.PITCH_ZONAS`): solo los
            # usa el control de posición (al elegirla) y la tabla.
            "coloresPos": {z[0]: z[2] for z in PITCH_ZONAS if z[0] in posiciones},
            "minimos": {s: int(MIN_MINUTES_POR_TEMPORADA[s]) for s in seasons},
            "minimos90": {s: int(MIN_MINUTES_90_POR_TEMPORADA[s]) for s in seasons},
            "ayudas": AYUDAS,
            "enCurso": temporadas_en_curso(),
        })


def build(assets_dir) -> list:
    df = load_data()
    seasons = seasons_of(df)
    _registrar_tabla(df, seasons)
    paginas = [
        chart_xg_goals_90(df),
        chart_xa_assists_90(df),
        chart_profile(df),
        chart_key_passes_assists(df),
        chart_build_vs_produce(df),
    ]
    # Defensa: solo si fbref aportó sus columnas (ver `DEF_COLS`).
    if hay_defensivas(df):
        paginas.append(chart_cover_stopper(df))
    else:
        print("  (sin columnas defensivas de fbref — se omite Cover vs. Stopper)")
    import venn   # igual que `edad`: lee el DataFrame que se le pasa y no depende de este módulo al importarse
    import edad   # aquí y no arriba: `edad` lee las mismas tablas y no debe depender de este módulo al importarse
    return _ordenar_pestanas(paginas + [chart_shot_map(), venn.chart_venn(df, MIN_MINUTES_90_POR_TEMPORADA),
                                        edad.chart_age(), chart_explorer(df)])
