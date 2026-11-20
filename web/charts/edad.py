"""«Edad»: cuánto se juega a cada edad. Una sola gráfica: los minutos por edad.

Todo el cálculo vive aquí (en el build, determinista) y al navegador viaja SOLO lo que se dibuja: una tabla
chica por posición en `dist/react/datos-edad.js`.

**Minutos por edad** (foto de cada edad): la mediana del porcentaje de los minutos disponibles de su club que
jugó cada jugador-temporada, con su rango típico (percentil 25 a 75). Aquí NO se corta por minutos: lo que se
quiere ver es justo cuánto juega quien juega poco, y `players.load_data()` recorta a los de 500 minutos o más.
Usa solo las temporadas CERRADAS (la que va en curso no tiene temporada completa que medir).

(Hubo un segundo panel, «rendimiento por edad», con el cambio de un año al siguiente del mismo jugador; se quitó el
2026-11-19 a pedido del usuario: los datos no sostenían un pico claro y el panel hacía más difícil leer el de minutos.)
"""

import numpy as np
import pandas as pd

import react_views
from nombres import club_visible
from preguntas import PREGUNTAS
from site_utils import PROCESSED_DIR, ChartPage, temporadas_en_curso
from viz_theme import FUENTE_FBREF, FUENTE_UNDERSTAT

SECTION = "Jugadores"
SLUG = "edad"
TITULO = "Edad"

EDAD_MIN, EDAD_MAX = 17, 38          # el eje
MIN_JUGADORES = 30                   # una edad con menos jugador-temporadas no se dibuja
GRUPOS_EDAD = ((17, 20), (21, 24), (25, 29), (30, 34), (35, 38))

CAMPO = "campo"
POSICIONES_MINUTOS = [CAMPO, "Portero", "Defensa", "Medio", "Delantero"]
ETIQUETA_CAMPO = "Jugadores de campo"


# --- edad y minutos disponibles -------------------------------------------------------------------

def edad_de(temporada, nacimiento):
    """Edad en una temporada: el año en que arranca ("2025-26" -> 2025) menos el año de nacimiento. Es la
    misma definición que `players.load_data()` y que el filtro sub-21 (FBref solo publica el año)."""
    return pd.to_numeric(pd.Series(temporada).str[:4]).to_numpy() - np.asarray(nacimiento, dtype=float)


def partidos_por_club(teams):
    """{(temporada, liga, club tal como se muestra): partidos jugados} de la tabla de equipos de FBref.
    Los jugadores traen el club con el nombre de Understat y la tabla de equipos con el de FBref; los dos
    coinciden después de `club_visible` (los 484 equipo-temporada cruzan sin un alias más)."""
    return {(t, l, club_visible(c)): int(mp) for t, l, c, mp in
            zip(teams["temporada"], teams["liga"], teams["Squad"], teams["ov_Playing Time_MP"])}


def minutos_disponibles(temporada, liga, equipo, partidos):
    """Minutos que su club jugó en la temporada: partidos × 90. Un jugador con dos clubes en la misma
    temporada ('A,B') toma el club con MÁS partidos: sus minutos se suman, así que el denominador es una
    temporada completa y no la de un club en el que solo estuvo unos meses. Nulo si ningún club cruza."""
    mp = [partidos.get((temporada, liga, club_visible(c.strip()))) for c in str(equipo).split(",")]
    mp = [m for m in mp if m is not None]
    return 90 * max(mp) if mp else np.nan


def jugador_temporadas(players, partidos, temporadas):
    """Una fila por jugador y temporada cerrada, SIN corte de minutos.

    Quien jugó en dos ligas en la misma temporada (un fichaje de enero: Understat publica cada liga por
    separado) viene en dos filas y se junta en una: los minutos suman; el denominador es el del club con
    más partidos (ver `minutos_disponibles`); la posición es la de la fila donde más jugó. Quien no tiene año
    de nacimiento (≈5%, no cruzó con FBref) queda fuera: sin él no hay edad."""
    p = players[players["temporada"].isin(temporadas)].copy()
    sin_nacimiento = int(p["born"].isna().sum())
    p = p[p["born"].notna()].copy()
    p["edad"] = edad_de(p["temporada"], p["born"])
    p["clave"] = p["player_fbref"].fillna(p["player"]) if "player_fbref" in p.columns else p["player"]
    p["disp"] = [minutos_disponibles(t, l, e, partidos) for t, l, e in zip(p["temporada"], p["liga"], p["team"])]
    p = p.sort_values("min", ascending=False, kind="stable")
    g = p.groupby(["temporada", "clave", "born"], sort=False, dropna=False)
    jt = g.agg(min=("min", "sum"), disp=("disp", "max"), posicion=("posicion", "first"),
               edad=("edad", "first")).reset_index()
    jt["pct"] = (100 * jt["min"] / jt["disp"]).clip(upper=100)
    jt.attrs["sin_nacimiento"] = sin_nacimiento
    jt.attrs["sin_club"] = int(jt["disp"].isna().sum())
    return jt


# --- minutos por edad -------------------------------------------------------------------------------

def de_la_posicion(jt, clave):
    """"campo" son los jugadores de campo: Defensa, Medio y Delantero, más los pocos de posición ambigua. Los
    porteros quedan aparte: casi todos juegan el 100% o el 0% y mezclarlos movería la mediana de cualquier edad
    sin decir nada del resto."""
    if clave == CAMPO:
        return jt[jt["posicion"] != "Portero"]
    return jt[jt["posicion"] == clave]


def _cuantiles(x):
    q = np.percentile(x, [25, 50, 75])
    return [round(float(v), 1) for v in q]


def minutos_por_edad(jt, clave):
    """Por edad con al menos `MIN_JUGADORES` jugador-temporadas: n y percentiles 25, 50, 75 del % de minutos
    disponibles. Devuelve también las edades ocultas por tener muy pocos."""
    d = de_la_posicion(jt, clave)
    d = d[d["pct"].notna()]
    e, n, p25, med, p75, ocultas = [], [], [], [], [], []
    for edad in range(EDAD_MIN, EDAD_MAX + 1):
        x = d.loc[d["edad"] == edad, "pct"].to_numpy()
        if len(x) < MIN_JUGADORES:
            if len(x):
                ocultas.append(edad)
            continue
        a, b, c = _cuantiles(x)
        e.append(edad); n.append(int(len(x))); p25.append(a); med.append(b); p75.append(c)
    grupos = []
    for lo, hi in GRUPOS_EDAD:
        x = d.loc[(d["edad"] >= lo) & (d["edad"] <= hi), "pct"].to_numpy()
        if len(x) < MIN_JUGADORES:
            continue
        a, b, c = _cuantiles(x)
        grupos.append({"de": lo, "a": hi, "n": int(len(x)), "p25": a, "med": b, "p75": c,
                       "mas50": round(float(100 * np.mean(x >= 50)), 1)})
    return {"e": e, "n": n, "p25": p25, "med": med, "p75": p75, "ocultas": ocultas, "grupos": grupos,
            "total": int(((d["edad"] >= EDAD_MIN) & (d["edad"] <= EDAD_MAX)).sum())}


# --- la vista --------------------------------------------------------------------------------------

def calcular(players, teams, en_curso=None):
    """Todo el cálculo de la vista a partir de las tablas crudas (los tests lo llaman con datos sintéticos)."""
    en_curso = set(en_curso if en_curso is not None else temporadas_en_curso())
    temporadas = sorted(t for t in players["temporada"].unique() if t not in en_curso)
    jt = jugador_temporadas(players, partidos_por_club(teams), temporadas)
    return {"temporadas": temporadas, "jt": jt,
            "minutos": {k: minutos_por_edad(jt, k) for k in POSICIONES_MINUTOS}}


def _cargar():
    # Sin `players.load_data()`: ese recorta a quien tiene ≥500 minutos (ver el docstring del módulo).
    # Los nombres de club se dejan como vienen de Understat; `partidos_por_club` los cruza con FBref.
    players = pd.read_csv(PROCESSED_DIR / "players_all_seasons.csv", encoding="utf-8-sig")
    teams = pd.read_csv(PROCESSED_DIR / "teams_all_seasons.csv", encoding="utf-8-sig",
                        usecols=["temporada", "liga", "Squad", "ov_Playing Time_MP"])
    return players, teams


def _n(n):
    return f"{int(n):,}"


def textos(r):
    """(qué más mirar, por qué así): los textos fijos de la vista. Cada cifra sale de las constantes de este
    módulo o de los datos calculados; no hay números escritos a mano."""
    jt = r["jt"]
    ts = r["temporadas"]
    sin_nac = jt.attrs["sin_nacimiento"]
    ambiguos = int(jt["posicion"].isna().sum())
    que_mirar = (
        "La línea es la **mediana** y la franja el **rango típico** (del percentil 25 al 75): la mitad de los "
        "jugadores de esa edad cae dentro de la franja. Las barras de abajo cuentan los jugador-temporadas de cada edad: "
        "donde son pocos, la línea se mueve más.\n\n"
        "Pasa el cursor o toca una edad para leer los números.")
    por_que = (
        f"**De dónde salen los minutos.** Cada jugador-temporada de las {len(ts)} temporadas cerradas ({ts[0]} a {ts[-1]}; "
        f"la que va en curso no entra) se mide contra los minutos que jugó su club ese año: partidos del equipo × 90, de la "
        f"tabla de equipos de FBref. No hay corte de minutos: quien jugó 20 minutos también cuenta, porque lo que se quiere "
        f"ver es cuánto juega la gente joven que juega poco. El porcentaje se topa en 100 (el tiempo añadido puede dar "
        f"más de 90 minutos por partido). Quien jugó en dos ligas el mismo año viene en dos filas y se junta en una: "
        f"minutos sumados, contra los partidos del club con más partidos.\n\n"
        f"**Qué población es.** Hay {_n(len(jt))} jugador-temporadas con edad. Solo aparece quien jugó al menos un minuto, "
        f"así que quien nunca pisó la cancha no está, y la mediana de los más jóvenes es la de los que sí llegaron a jugar. "
        f"Se dejan fuera {_n(sin_nac)} sin año de nacimiento (no cruzaron con FBref) y no se dibuja una edad con menos de "
        f"{MIN_JUGADORES} jugador-temporadas. «{ETIQUETA_CAMPO}» son Defensa, Medio y Delantero (con {_n(ambiguos)} de posición "
        f"ambigua que no cuentan en ninguna posición suelta); los porteros van aparte porque casi todos juegan el 100% o "
        f"casi nada, y mezclarlos movería la mediana de cualquier edad. La edad es el año en que arranca la temporada menos "
        f"el año de nacimiento, como en los demás filtros del sitio: FBref solo publica el año, así que puede pasarse por uno.\n\n"
        f"**Qué no dice.** Los minutos dependen del equipo y de lo que el entrenador decide, no solo del jugador: un "
        f"joven que juega poco puede ser suplente de un titular indiscutido o estar lesionado.")
    return que_mirar, por_que


def payload(r):
    """Lo que viaja al navegador: por posición, una tabla corta por edad. Nada de jugadores uno por uno."""
    return {
        "entidad": SLUG,
        "temporadas": r["temporadas"],
        "edades": [EDAD_MIN, EDAD_MAX],
        "minJugadores": MIN_JUGADORES,
        "minutos": {k: {c: v for c, v in d.items()} for k, d in r["minutos"].items()},
    }


def chart_age() -> ChartPage:
    players, teams = _cargar()
    r = calcular(players, teams)
    react_views.registrar_payload(SLUG, payload(r))
    que_mirar, por_que = textos(r)
    bajada = "Qué parte de los minutos de su club juega cada edad: mediana y rango típico, por posición."
    assert len(bajada) <= 160, f"{SLUG}: la bajada mide {len(bajada)} caracteres"
    cfg = {
        "id": SLUG, "titulo": TITULO, "bajada": bajada, "pregunta": PREGUNTAS[SLUG], "tabla": SLUG,
        "queMirar": que_mirar, "porQue": por_que,
        "fuente": f"{FUENTE_UNDERSTAT} y {FUENTE_FBREF}",
        "posiciones": [{"id": CAMPO, "etiqueta": ETIQUETA_CAMPO}] + [{"id": p, "etiqueta": p} for p in POSICIONES_MINUTOS[1:]],
        "edades": [EDAD_MIN, EDAD_MAX],
    }
    return ChartPage(slug=SLUG, section=SECTION, title=TITULO, subtitle=bajada,
                     body_html=react_views.montar_html("edad", SLUG, cfg, alto_min=420), kind="line")
