"""Gráficos a nivel de jugador para el sitio — mismo código/decisiones que
`code/eda_players.ipynb`, portado a funciones que devuelven `ChartPage`."""

from functools import partial

import pandas as pd
import plotly.graph_objects as go

import insights as ins
import shot_map
from consolidate_data import ELO_TOP, NIVELES, POSICIONES
from site_utils import NIVEL_FILTER, PROCESSED_DIR, ChartPage
from site_utils import nivel_filter as _nivel_filter
from viz_theme import (
    LEAGUE_ORDER, FUENTE_FBREF, FUENTE_UNDERSTAT, league_color,
)
from viz_theme import explorer_chart_html as _explorer_chart_html
from viz_theme import sidebar_chart_html as _sidebar_chart_html

SECTION = "Jugadores"

# Casi todo lo de esta sección sale de Understat (es quien publica xG/xA a
# nivel de jugador; FBref dejó de hacerlo), así que ese crédito es el default y
# se fija una vez acá.
#
# Las dos gráficas puramente defensivas son al revés: cada punto es una cuenta
# de FBref dividida por minutos de FBref, y Understat no aporta ni una. Por eso
# llevan su propio pie —`FUENTE_FBREF`— en vez del default: acreditar a
# Understat un dato que no publica sería sencillamente falso.
#
# Y hay dos mixtas, que acreditan a las dos: "Crea tu gráfico", que cruza
# columnas de ambas, y "Perfil de dos fases", cuyos ejes vienen uno de cada
# fuente (producción esperada de Understat, recuperaciones de FBref).
sidebar_chart_html = partial(_sidebar_chart_html, fuente=FUENTE_UNDERSTAT)
explorer_chart_html = partial(_explorer_chart_html,
                               fuente=f"{FUENTE_UNDERSTAT} y {FUENTE_FBREF}")

# Las variables que se pueden poner en cada eje de "Crea tu gráfico":
# (columna, etiqueta, grupo del desplegable, decimales con los que se muestra).
# Los totales conviven con sus tasas por 90' a propósito: son preguntas
# distintas —quién produjo más en la temporada contra quién produce más cuando
# está en la cancha— y cruzar una contra la otra es una de las cosas
# interesantes que se pueden hacer acá.
VARIABLES = [
    ("goals", "Goles", "Producción", 0),
    ("a", "Asistencias", "Producción", 0),
    ("np_goals", "Goles sin penalti", "Producción", 0),
    ("g90", "Goles por 90'", "Producción", 2),
    ("a90", "Asistencias por 90'", "Producción", 2),

    ("xG", "xG", "Esperado", 1),
    ("xA", "xA", "Esperado", 1),
    ("np_xg", "xG sin penalti", "Esperado", 1),
    ("xG90", "xG por 90'", "Esperado", 2),
    ("xA90", "xA por 90'", "Esperado", 2),
    ("xga90", "Producción esperada por 90' (xG + xA)", "Esperado", 2),
    ("xg_chain", "xG de las jugadas en que participó", "Esperado", 1),
    ("xg_buildup", "xG de construcción (sin tiro ni asistencia)", "Esperado", 1),

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

    # Lo único defensivo que existe a nivel jugador: viene de fbref, no de
    # Understat, y por eso puede faltar (ver `variables_disponibles`).
    ("recoveries90", "Recuperaciones por 90'", "Defensa", 2),
    ("tkl_w90", "Entradas ganadas por 90'", "Defensa", 2),
    ("interceptions90", "Intercepciones por 90'", "Defensa", 2),
    ("fouls90", "Faltas cometidas por 90'", "Defensa", 2),
    ("recoveries", "Recuperaciones", "Defensa", 0),
]

MIN_MINUTES = 500

# Corte de minutos por temporada. `MIN_MINUTES` (500) asume una temporada
# cerrada — con 5 jornadas jugadas nadie llega ahí y el corte deja SOLO a la
# liga que va más adelantada en el calendario (las 5 no arrancan el mismo día).
# Para la temporada que está en curso el corte baja a una fracción de los
# minutos máximos que se jugaron hasta ahora, así las 5 ligas muestran algo
# desde el arranque y el número se va ajustando solo, jornada a jornada, sin
# volver a tocar el código. El piso evita que un corte casi en 0 (recién
# arrancada la temporada) deje pasar a cualquiera con un cuarto de hora en
# cancha. Se calcula en `load_data()`, sobre los datos SIN filtrar.
MIN_MINUTES_FRACCION = 0.4
MIN_MINUTES_PISO = 90
MIN_MINUTES_POR_TEMPORADA = {}  # {temporada: corte} — lo llena `load_data()`


# Filtro sub-21 de los scatter. `sub21` la calcula `consolidate_data.py` a
# partir del año de nacimiento que aporta fbref (Understat no publica edad), con
# el criterio de las categorías sub-N de UEFA: cuenta el año, no el cumpleaños.
# Los jugadores cuyo nombre no cruzó con fbref quedan sin edad, y por lo tanto
# fuera del filtro — es lo correcto: edad desconocida no es sub-21.
SUB21_FILTER = {
    "col": "sub21",
    # Sin rótulo arriba: la casilla ya se explica sola, y un "EDAD" encima de
    # "Jugadores sub-21" era decir lo mismo dos veces. El corte de minutos
    # tampoco va acá — ya está en el subtítulo de cada gráfica.
    "label": None,
    "text": "Jugadores sub-21",
    "hint": "Menos de 21 al arrancar la temporada, cuenta el año de nacimiento.",
    # La nota va en una (i) al lado de la casilla, igual que la del nivel de
    # club: es una aclaración de criterio, no algo que haga falta leer para
    # entender qué hace la casilla.
    "info": True,
    # Cómo se nombra el filtro en el rótulo de la caja de lectura ("2025-26 ·
    # Ligue 1 · sub-21"), que es lo que le dice al lector sobre qué población
    # están hechas las afirmaciones que está leyendo.
    "estado": "sub-21",
}

# Filtro de posición. Es el segundo dato que aporta FBref (ver `sub21` arriba):
# Understat publica el conjunto de puestos en los que un jugador apareció, pero
# no cuál es el principal, así que la categoría la arma `consolidate_data.py`
# cruzando por nombre igual que la edad.
#
# Existe porque sin él "Perfil ofensivo" compara a un central con un extremo
# como si midieran lo mismo: casi toda la separación vertical y horizontal de
# esa nube es la posición, no el jugador. Con el filtro puesto la comparación
# pasa a ser dentro del puesto, que es la única en la que un xG90 alto quiere
# decir algo.
POSICION_FILTER_BASE = {
    "col": "posicion",
    "label": "Posición",
    "all_label": "Todas las posiciones",
    # Prefijo del segmento que este filtro agrega a la clave de la caja de
    # lectura ("2025-26|__all__|pos:Medio|sub21").
    "clave": "pos",
}
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

    global MIN_MINUTES_POR_TEMPORADA
    MIN_MINUTES_POR_TEMPORADA = {
        temporada: max(MIN_MINUTES_PISO,
                        min(MIN_MINUTES, round(MIN_MINUTES_FRACCION * maximo)))
        for temporada, maximo in df.groupby("temporada")["min"].max().items()
    }
    umbral = df["temporada"].map(MIN_MINUTES_POR_TEMPORADA)
    df = df[df["min"] >= umbral].reset_index(drop=True)

    # Derivadas para "Crea tu gráfico". Las tasas por 90' van sobre los minutos
    # reales y no sobre los partidos: `apps` cuenta también las entradas desde
    # el banco, así que dividir por ahí le daría una tasa inflada a cualquier
    # suplente. La edad sale del año de nacimiento con el mismo criterio que
    # `sub21` (cuenta el año, no el cumpleaños), y queda nula para quien no
    # cruzó con FBref.
    noventas = df["min"] / 90
    df = pd.concat([df, pd.DataFrame({
        "g90": df["goals"] / noventas,
        "a90": df["a"] / noventas,
        "sh90": df["shots"] / noventas,
        "kp90": df["key_passes"] / noventas,
        # Producción esperada total, para el perfil de dos fases. Se suma acá y
        # no en la consolidación porque es una derivada de análisis (qué se
        # considera "producir"), no un dato de la fuente.
        "xga90": df["xG90"] + df["xA90"],
        "edad": df["temporada"].str[:4].astype(int) - df["born"],
    })], axis=1)
    return df


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


def _entrada(generador, df, season, liga):
    """El par (fija, salta) de una combinación, o un aviso si no queda nadie a
    quien describir.

    Hoy ninguna combinación queda vacía —la más chica tiene 14 sub-21—, pero los
    generadores piden el máximo del subconjunto y sobre un DataFrame vacío eso
    revienta; subir el corte de minutos bastaría para provocarlo."""
    d = df[df["temporada"] == season]
    if liga != ins.LIGA_TODAS:
        d = d[d["liga"] == liga]
    if d.empty:
        return {"fija": "Ningún jugador cumple los filtros elegidos.", "salta": None}
    return dict(zip(("fija", "salta"), generador(df, season, liga)))


def _por_temporada_y_liga(generador, df, seasons):
    """Una entrada por cada temporada x liga, y por cada combinación de los dos
    filtros por punto encima de esas — que son las que se muestran al tocarlos.

    Las claves tienen que coincidir con las que arma el JS de la barra lateral:
    `temporada|liga`, más `|pos:<posición>`, `|nivel:<nivel>` y `|sub21` cuando
    cada filtro está puesto, **en ese orden** — que es el mismo en que se le
    pasan los filtros a `sidebar_chart_html`. Cada variante se deriva de TODAS
    las anteriores y no solo de la base, porque los tres filtros se combinan en
    la pantalla; son 30 variantes x 30 combinaciones de temporada y liga.

    Se calculan acá, en el build, porque los textos salen de operar sobre los
    datos y el sitio es estático: en el navegador no hay con qué rehacerlos."""
    variantes = [("", df)]
    variantes += [(f"|{POSICION_FILTER_BASE['clave']}:{p}", df[df["posicion"] == p])
                   for p in posiciones_de(df)]
    # El nivel se combina con la posición: cada variante de arriba se vuelve a
    # partir en top/underground, igual que después las parte el sub-21.
    variantes += [(f"{sufijo}|{NIVEL_FILTER['clave']}:{n}", datos[datos["nivel"] == n])
                   for sufijo, datos in list(variantes)
                   for n in niveles_de(df)]
    if "sub21" in df.columns:
        variantes += [(f"{sufijo}|{SUB21_FILTER['col']}", datos[datos["sub21"] == True])
                       for sufijo, datos in list(variantes)]
    return {
        f"{s}|{liga}{sufijo}": _entrada(generador, datos, s, liga)
        for sufijo, datos in variantes
        for s in seasons
        for liga in [ins.LIGA_TODAS] + list(LEAGUE_ORDER)
    }


def _player_sidebar(fig, scatter_data, x_col, y_col, seasons, season_data, subtitle,
                     extra_traces=0, insights=None, point_filter=None,
                     cat_filter=None, width=760, height=580,
                     fuente=None):
    # `subtitle` trae `{min_min}` y `{temporada}` sin resolver (ver los
    # `chart_*` de más arriba): acá se resuelve por temporada, porque el corte
    # de minutos no es el mismo número en las seis (ver `MIN_MINUTES_POR_TEMPORADA`).
    subtitle_por_temporada = {
        s: subtitle.format(min_min=MIN_MINUTES_POR_TEMPORADA[s], temporada=s)
        for s in seasons
    }
    return sidebar_chart_html(
        fig, scatter_data, x_col, y_col, extra_traces=extra_traces,
        name_col="player", search_label="jugador", width=width, height=height,
        base_size=BASE_SIZE, season_data=season_data,
        custom_cols=["player", "team"], subtitle_template=subtitle_por_temporada,
        insights=insights, point_filter=point_filter, cat_filter=cat_filter,
        **({"fuente": fuente} if fuente else {}),
    )


def sub21_filter(df):
    """El filtro, o None si los datos no traen edades.

    `fbref-players.csv` es opcional en la consolidación, así que el sitio se
    tiene que poder construir sin él: sin la columna (o sin un solo sub-21 que
    llegue al corte de minutos) la casilla no se dibuja, en vez de aparecer y
    no hacer nada al marcarla."""
    if "sub21" not in df.columns or not df["sub21"].fillna(False).any():
        return None
    return SUB21_FILTER


def posiciones_de(df):
    """Las posiciones que de verdad aparecen en los datos, en orden de cancha.

    Se listan las que están y no las cuatro fijas por el mismo motivo que el
    sub-21: un desplegable no debe ofrecer una opción que deje el gráfico
    vacío."""
    if "posicion" not in df.columns:
        return []
    return [p for p in POSICIONES if (df["posicion"] == p).any()]


def posicion_filter(df):
    """El filtro de posición, o None si los datos no la traen.

    Va sin nota al pie por decisión del usuario: el desplegable solo. Lo que
    decía —que es la posición principal, que sale de FBref y que quien no cruza
    por nombre queda fuera al elegir una— está documentado en
    `POSICION_FILTER_BASE` y en `consolidate_data.posicion_fbref`."""
    opciones = posiciones_de(df)
    if not opciones:
        return None
    return {**POSICION_FILTER_BASE, "options": opciones}


# Filtro de nivel del club. El control y el porqué están en
# `site_utils.NIVEL_FILTER`; el umbral, en `consolidate_data.ELO_TOP`. Acá solo
# queda lo propio de esta sección.
#
# Qué significa en Jugadores: el punto es una persona, no un club, así que el
# filtro habla del equipo en el que jugó esa temporada. Sirve para lo que el de
# posición no arregla — buena parte de la separación de estas nubes es el club
# y no el jugador, porque quien juega en un grande recibe más y mejores balones
# que quien juega en un recién ascendido. Cruzado con el sub-21 sale la
# pregunta interesante: las promesas que NO están en un grande.
#
# El club es el mismo que muestra el hover: quien cambió a mitad de temporada
# se clasifica por el último (ver `consolidate_data.ultimo_club_col`).
NIVEL_HINT = (f"Corte en {ELO_TOP} de ELO (clubelo) del club al arrancar la "
              f"temporada: el 20% más alto de las 5 ligas. Quien cambió de club "
              f"cuenta por el último, que es el que muestra el hover.")


def nivel_filter(df):
    return _nivel_filter(df, NIVEL_HINT)


def niveles_de(df):
    if "nivel" not in df.columns:
        return []
    return [n for n in NIVELES if (df["nivel"] == n).any()]


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
                "Jugadores con ≥{min_min} min · {temporada}")
    fig.update_layout(
        title=dict(text="Goles vs. xG", subtitle=dict(text=subtitle.format(
            min_min=MIN_MINUTES_POR_TEMPORADA[seasons[-1]], temporada=seasons[-1]))),
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
                                   },
                                   point_filter=sub21_filter(df),
                                   cat_filter=[posicion_filter(df), nivel_filter(df)]),
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
                "Jugadores con ≥{min_min} min · {temporada}")
    fig.update_layout(
        title=dict(text="Asistencias vs. xA", subtitle=dict(text=subtitle.format(
            min_min=MIN_MINUTES_POR_TEMPORADA[seasons[-1]], temporada=seasons[-1]))),
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
                                   },
                                   point_filter=sub21_filter(df),
                                   cat_filter=[posicion_filter(df), nivel_filter(df)]),
    )


def chart_profile(df, seasons, season_data):
    """Perfil ofensivo: xG90 contra xA90, un punto por jugador."""
    scatter_data = season_data[seasons[-1]]

    fig = go.Figure()
    _scatter_traces(fig, scatter_data, "xG90", "xA90", "xG90", "xA90", ".2f", ".2f")

    # Las líneas de referencia van en el promedio de las 5 temporadas, no en
    # el de la temporada mostrada: si se movieran con cada cambio, "estar por
    # encima del promedio" significaría algo distinto en cada temporada.
    fig.add_hline(y=df["xA90"].mean(), line=dict(color="#c3c2b7", width=1, dash="dot"))
    fig.add_vline(x=df["xG90"].mean(), line=dict(color="#c3c2b7", width=1, dash="dot"))

    ancho, alto = 820, 620

    subtitle = ("Killer puro, creador puro o todocampo — "
                "jugadores con ≥{min_min} min · {temporada}")
    fig.update_layout(
        title=dict(text="Perfil ofensivo: xG90 vs. xA90",
                   subtitle=dict(text=subtitle.format(
                       min_min=MIN_MINUTES_POR_TEMPORADA[seasons[-1]], temporada=seasons[-1]))),
        xaxis_title="xG por 90'", yaxis_title="xA por 90'",
        xaxis=dict(range=_padded(df["xG90"])), yaxis=dict(range=_padded(df["xA90"])),
    )
    return ChartPage(
        slug="perfil-ofensivo", section=SECTION, title="Perfil ofensivo: xG90 vs. xA90",
        subtitle="Tasas por 90' — killer puro, creador puro o todocampo, un punto por jugador.",
        body_html=_player_sidebar(fig, scatter_data, "xG90", "xA90", seasons, season_data,
                                   subtitle, width=ancho, height=alto,
                                   insights={
                                       "que_mirar": ins.perfil_que_mirar(),
                                       "por_que": ins.perfil_por_que(df),
                                       "dinamico": _por_temporada_y_liga(
                                           ins.perfil, df, seasons),
                                   },
                                   point_filter=sub21_filter(df),
                                   cat_filter=[posicion_filter(df), nivel_filter(df)]),
    )


# Las columnas defensivas que trae fbref vía `consolidate_data.MISC_COLS`. Son
# opcionales igual que `sub21`: `fbref-players.csv` puede no estar, y entonces
# las dos gráficas defensivas no se dibujan en vez de salir vacías.
DEF_COLS = ["recoveries90", "tkl_w90", "interceptions90", "fouls90"]


def hay_defensivas(df):
    return all(c in df.columns and df[c].notna().any() for c in DEF_COLS)


def solo_defensivas(df):
    """Los jugadores que SÍ tienen dato defensivo.

    Las dos gráficas defensivas trabajan sobre esta población y no sobre la
    entera: quien no cruzó por nombre con fbref no tiene coordenadas, y dejarlo
    dentro lo metería igual en el buscador y en el top 5 —con valor nulo— aunque
    no haya ningún punto suyo que encontrar."""
    return df[df["recoveries90"].notna()].reset_index(drop=True)


def seasons_defensivas(df_def, seasons):
    """Las temporadas que de verdad tienen dato defensivo.

    `fbref-players.csv` se baja temporada a temporada y una corrida puede
    quedarse a medias, así que una temporada puede no tener ninguna. Ofrecerla
    igual en el selector dejaría el gráfico en blanco al elegirla — mismo
    criterio que `posiciones_de`: un control no lista lo que vaciaría el
    gráfico."""
    return [s for s in seasons if (df_def["temporada"] == s).any()]


def _defensa_subtitulo(df, df_def):
    """El corte de minutos de estas dos es el de Understat, pero las cuentas y
    su divisor son de fbref (ver `attach_fbref`). Cuántos quedan fuera por no
    cruzar entre las dos fuentes se dice en el subtítulo, en vez de dejar que
    el lector suponga que están todos."""
    # Solo sobre las temporadas que se muestran: contar contra las cinco
    # mezclaría a quien no cruzó por nombre con quien no tiene dato porque su
    # temporada todavía no se bajó, que son dos cosas distintas.
    dentro = df[df["temporada"].isin(set(df_def["temporada"]))]
    faltan = len(dentro) - len(df_def)
    # "jugador-temporada" y no "jugadores": el subtítulo se lee al lado de la
    # temporada elegida, y un número a secas ahí se entendería como si fuera de
    # esa temporada sola cuando es el total de las cinco.
    return f" · {faltan} jugador-temporada sin cruce en fbref" if faltan else ""


def chart_recoveries_vs_fouls(df, df_def, seasons, season_data):
    """Cuánta pelota recupera cada jugador y a qué precio.

    Es la primera gráfica defensiva de la sección, que hasta el 2026-09-01 era
    100% de ataque. Va con las dos únicas familias de acción defensiva que
    fbref sigue publicando —entradas ganadas más intercepciones, contra faltas
    cometidas—; el porqué de que sean solo esas está en
    `fetch_fbref_players.EXTRA_TABLAS`.

    El eje X suma las dos formas de quitar la pelota en vez de separarlas
    porque acá la pregunta no es CÓMO la quita sino CUÁNTA quita: quién la
    recupera y quién, para el mismo volumen, necesita cortar con falta. La
    separación entre disputar y anticipar es la otra gráfica."""
    scatter_data = season_data[seasons[-1]]

    fig = go.Figure()
    _scatter_traces(fig, scatter_data, "recoveries90", "fouls90",
                     "Recuperaciones por 90'", "Faltas por 90'", ".2f", ".2f")
    # Mismo criterio que en "Perfil ofensivo": el promedio es el de las 5
    # temporadas y no el de la mostrada, para que "por encima del promedio"
    # signifique lo mismo al cambiar de temporada.
    fig.add_hline(y=df_def["fouls90"].mean(), line=dict(color="#c3c2b7", width=1, dash="dot"))
    fig.add_vline(x=df_def["recoveries90"].mean(), line=dict(color="#c3c2b7", width=1, dash="dot"))

    ancho, alto = 820, 620

    subtitle = ("¿Quién recupera limpio y quién corta con falta? "
                "Jugadores con ≥{min_min} min · {temporada}"
                + _defensa_subtitulo(df, df_def))
    fig.update_layout(
        title=dict(text="Quitar vs. cortar con falta",
                   subtitle=dict(text=subtitle.format(
                       min_min=MIN_MINUTES_POR_TEMPORADA[seasons[-1]], temporada=seasons[-1]))),
        xaxis_title="Recuperaciones por 90'", yaxis_title="Faltas cometidas por 90'",
        xaxis=dict(range=_padded(df_def["recoveries90"])),
        yaxis=dict(range=_padded(df_def["fouls90"])),
    )
    return ChartPage(
        slug="recuperacion-vs-faltas", section=SECTION,
        title="Quitar vs. cortar con falta",
        subtitle="Cuánta pelota recupera cada jugador y a qué precio — un punto por jugador.",
        body_html=_player_sidebar(fig, scatter_data, "recoveries90", "fouls90",
                                   seasons, season_data, subtitle,
                                   width=ancho, height=alto,
                                   fuente=FUENTE_FBREF,
                                   insights={
                                       "que_mirar": ins.recuperar_que_mirar(),
                                       "por_que": ins.recuperar_por_que(df_def),
                                       "dinamico": _por_temporada_y_liga(
                                           ins.recuperar, df_def, seasons),
                                   },
                                   point_filter=sub21_filter(df_def),
                                   cat_filter=[posicion_filter(df_def),
                                                nivel_filter(df_def)]),
    )


def chart_defensive_profile(df, df_def, seasons, season_data):
    """El espejo de "Perfil ofensivo", eje por eje.

    Donde el ofensivo cruza las dos formas de producir (rematar contra crear),
    este cruza las dos de quitar la pelota: ir a disputarla contra leer el pase.
    Mismos cuadrantes —puro de una cosa, puro de la otra, o las dos— y mismas
    líneas de promedio, para que la grilla de la sección muestre que son la
    misma pregunta en las dos mitades de la cancha.

    Se separa de "Quitar vs. cortar con falta" —ahí los dos ejes van sumados—
    porque son preguntas distintas: cuánta recupera contra cómo la recupera. El
    riesgo de esta es que los dos ejes midan lo mismo (volumen defensivo) y la
    nube salga una diagonal; por eso la caja de lectura publica la correlación,
    igual que hace el perfil ofensivo con xG90 y xA90."""
    scatter_data = season_data[seasons[-1]]

    fig = go.Figure()
    _scatter_traces(fig, scatter_data, "tkl_w90", "interceptions90",
                     "Entradas ganadas por 90'", "Intercepciones por 90'", ".2f", ".2f")
    fig.add_hline(y=df_def["interceptions90"].mean(), line=dict(color="#c3c2b7", width=1, dash="dot"))
    fig.add_vline(x=df_def["tkl_w90"].mean(), line=dict(color="#c3c2b7", width=1, dash="dot"))

    ancho, alto = 820, 620

    subtitle = ("Disputar, anticipar o las dos cosas — "
                "jugadores con ≥{min_min} min · {temporada}"
                + _defensa_subtitulo(df, df_def))
    fig.update_layout(
        title=dict(text="Perfil defensivo: entradas vs. intercepciones",
                   subtitle=dict(text=subtitle.format(
                       min_min=MIN_MINUTES_POR_TEMPORADA[seasons[-1]], temporada=seasons[-1]))),
        xaxis_title="Entradas ganadas por 90'", yaxis_title="Intercepciones por 90'",
        xaxis=dict(range=_padded(df_def["tkl_w90"])),
        yaxis=dict(range=_padded(df_def["interceptions90"])),
    )
    return ChartPage(
        slug="perfil-defensivo", section=SECTION,
        title="Perfil defensivo: entradas vs. intercepciones",
        subtitle="Tasas por 90' — el que va al choque, el que lee el pase o las dos cosas, un punto por jugador.",
        body_html=_player_sidebar(fig, scatter_data, "tkl_w90", "interceptions90",
                                   seasons, season_data, subtitle,
                                   width=ancho, height=alto,
                                   fuente=FUENTE_FBREF,
                                   insights={
                                       "que_mirar": ins.disputar_que_mirar(),
                                       "por_que": ins.disputar_por_que(df_def),
                                       "dinamico": _por_temporada_y_liga(
                                           ins.disputar, df_def, seasons),
                                   },
                                   point_filter=sub21_filter(df_def),
                                   cat_filter=[posicion_filter(df_def),
                                                nivel_filter(df_def)]),
    )


def chart_two_phase(df, df_def, seasons, season_data):
    """En qué mitad de la cancha pesa cada jugador.

    Es la primera gráfica de la sección cuyos dos ejes vienen de fuentes
    distintas: la producción esperada es de Understat y las recuperaciones de
    FBref. Por eso acredita a las dos.

    El eje X suma xG90 y xA90 —que el perfil ofensivo separa— porque acá la
    pregunta no es qué tipo de ataque aporta sino cuánto aporta arriba, para
    poder contrastarlo con lo que quita atrás. Es la misma decisión que toma
    "Quitar vs. cortar con falta" al sumar entradas e intercepciones.

    Lo que la hace valer la pena es que el compromiso entre las dos fases NO es
    universal: existe en el mediocampo y desaparece en la defensa. La caja de
    lectura publica esa correlación por posición, que es lo que convierte el
    filtro de posición en parte del análisis y no en un adorno."""
    scatter_data = season_data[seasons[-1]]

    fig = go.Figure()
    _scatter_traces(fig, scatter_data, "xga90", "recoveries90",
                     "xG90 + xA90", "Recuperaciones por 90'", ".2f", ".2f")
    fig.add_hline(y=df_def["recoveries90"].mean(), line=dict(color="#c3c2b7", width=1, dash="dot"))
    fig.add_vline(x=df_def["xga90"].mean(), line=dict(color="#c3c2b7", width=1, dash="dot"))

    subtitle = ("¿Pesa arriba, atrás o en las dos? "
                "Jugadores con ≥{min_min} min · {temporada}"
                + _defensa_subtitulo(df, df_def))
    fig.update_layout(
        title=dict(text="Perfil de dos fases",
                   subtitle=dict(text=subtitle.format(
                       min_min=MIN_MINUTES_POR_TEMPORADA[seasons[-1]], temporada=seasons[-1]))),
        xaxis_title="Producción esperada por 90' (xG + xA)",
        yaxis_title="Recuperaciones por 90'",
        xaxis=dict(range=_padded(df_def["xga90"])),
        yaxis=dict(range=_padded(df_def["recoveries90"])),
    )
    return ChartPage(
        slug="perfil-dos-fases", section=SECTION, title="Perfil de dos fases",
        subtitle="Lo que produce arriba contra lo que recupera atrás — el atacante puro, el recuperador puro y los raros que hacen las dos.",
        body_html=_player_sidebar(fig, scatter_data, "xga90", "recoveries90",
                                   seasons, season_data, subtitle,
                                   fuente=f"{FUENTE_UNDERSTAT} y {FUENTE_FBREF}",
                                   insights={
                                       "que_mirar": ins.dos_fases_que_mirar(),
                                       "por_que": ins.dos_fases_por_que(df_def),
                                       "dinamico": _por_temporada_y_liga(
                                           ins.dos_fases, df_def, seasons),
                                   },
                                   point_filter=sub21_filter(df_def),
                                   cat_filter=[posicion_filter(df_def),
                                                nivel_filter(df_def)]),
    )


def chart_shot_map():
    """Mapa de calor de los tiros.

    Es el único gráfico de la sección que no sale de
    `players_all_seasons.csv` sino del detalle de tiros, y el único cuyo punto
    no es un jugador sino un remate. Entra igual en Jugadores porque responde a
    una pregunta de la misma familia que los otros: no cuántos goles hace
    alguien, sino desde dónde se remata."""
    df, descartes = shot_map.load(PROCESSED_DIR / "shots_all_seasons.csv")
    seasons = sorted(df["temporada"].unique())
    return ChartPage(
        slug="mapa-tiros", section=SECTION, title="Mapa de calor de los tiros",
        subtitle="Desde dónde se remata, con filtro de temporada y tipo de tiro.",
        body_html=shot_map.shot_map_html(df, descartes, seasons),
        kind="heatmap",
    )


def variables_disponibles(df):
    """Las variables que el explorador puede ofrecer con estos datos.

    Las defensivas salen de fbref, que es una fuente opcional: sin
    `fbref-players.csv` la columna no existe y el desplegable no debe listar
    una opción que dejaría el gráfico vacío — mismo criterio que
    `posiciones_de` y que la casilla de sub-21."""
    return [v for v in VARIABLES if v[0] in df.columns]


def chart_explorer(df, seasons, season_data):
    """"Crea tu gráfico": el lector elige las dos variables.

    No lleva caja de "qué mirar" porque no hay un "acá" del que hablar: el par
    de variables lo elige quien mira. Lo que sí lleva es el r² del par elegido,
    calculado en el navegador sobre los puntos que están dibujados (ver
    `viz_theme.explorer_chart_html`)."""
    return ChartPage(
        slug="crea-tu-grafico-jugadores", section=SECTION, title="Crea tu gráfico",
        subtitle=f"Cruza cualquier par de las {len(variables_disponibles(df))} variables de jugador — y el r² te dice si de verdad son dos cosas distintas o la misma medida dos veces.",
        body_html=explorer_chart_html(
            season_data, variables_disponibles(df), name_col="player", search_label="jugador",
            entidad="jugadores", default_x="shots", default_y="goals",
            team_col="team", base_size=BASE_SIZE, point_filter=sub21_filter(df),
            cat_filter=[posicion_filter(df), nivel_filter(df)]),
        kind="explorer",
    )


def build(assets_dir) -> list:
    df = load_data()
    seasons = seasons_of(df)
    season_data = season_scatter_data(df, seasons)
    paginas = [
        chart_goals_vs_xg(df, seasons, season_data),
        chart_assists_vs_xa(df, seasons, season_data),
        chart_profile(df, seasons, season_data),
    ]
    # Defensivas: solo si fbref aportó sus columnas (ver `DEF_COLS`).
    if hay_defensivas(df):
        df_def = solo_defensivas(df)
        seasons_def = seasons_defensivas(df_def, seasons)
        datos_def = season_scatter_data(df_def, seasons_def)
        paginas += [
            chart_recoveries_vs_fouls(df, df_def, seasons_def, datos_def),
            chart_defensive_profile(df, df_def, seasons_def, datos_def),
            chart_two_phase(df, df_def, seasons_def, datos_def),
        ]
        if len(seasons_def) < len(seasons):
            faltan = sorted(set(seasons) - set(seasons_def))
            print(f"  (defensivas: sin datos de fbref en {', '.join(faltan)})")
    else:
        print("  (sin columnas defensivas de fbref — se omiten sus 2 gráficas)")
    return paginas + [
        chart_shot_map(),
        chart_explorer(df, seasons, season_data),
    ]
