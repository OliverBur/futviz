"""«Edad»: cuánto se juega y cuándo se rinde mejor, por edad. Una vista con dos paneles que comparten el eje.

Todo el cálculo vive aquí (en el build, determinista) y al navegador viaja SOLO lo que se dibuja: una tabla
chica por posición en `dist/react/datos-edad.js`. Las dos preguntas necesitan métodos distintos:

* **Minutos por edad** (foto de cada edad): la mediana del porcentaje de los minutos disponibles de su club que
  jugó cada jugador-temporada, con su rango típico (percentil 25 a 75). Aquí NO se corta por minutos: lo que se
  quiere ver es justo cuánto juega quien juega poco, y `players.load_data()` recorta a los de 500 minutos o más.
* **Rendimiento por edad** (método del cambio de un año al siguiente): la foto de cada edad no sirve para
  estimar el pico, porque a los 34 solo quedan los que siguen siendo buenos. Se compara al MISMO jugador en
  dos temporadas consecutivas y se encadena el cambio de cada edad a la siguiente.

Las dos usan solo las temporadas CERRADAS (la que va en curso no tiene temporada completa que medir).
"""

import numpy as np
import pandas as pd

import react_views
from nombres import club_visible
from preguntas import PREGUNTAS
from site_utils import PROCESSED_DIR, ChartPage, temporadas_en_curso
from viz_theme import FUENTE_FBREF, FUENTE_UNDERSTAT, PITCH_ZONAS

SECTION = "Jugadores"
SLUG = "edad"
TITULO = "Edad"

EDAD_MIN, EDAD_MAX = 17, 38          # el eje que comparten los dos paneles
MIN_JUGADORES = 30                   # una edad con menos jugador-temporadas no se dibuja (panel de minutos)
MINUTOS_CAMBIO = 900                 # minutos en CADA una de las dos temporadas (el corte de las vistas por 90')
PARES_MIN_TRANSICION = 30            # una transición a -> a+1 con menos pares no entra a la cadena
ANCLA = 22                           # la curva de rendimiento vale 100 a esta edad
REPLICAS = 2000                      # réplicas del bootstrap
SEMILLA = 2026                       # fija: el build es determinista
NIVEL_IC = 0.90                      # intervalo del 5% al 95% de las réplicas
GRUPOS_EDAD = ((17, 20), (21, 24), (25, 29), (30, 34), (35, 38))

CAMPO = "campo"
POSICIONES_MINUTOS = [CAMPO, "Portero", "Defensa", "Medio", "Delantero"]
ETIQUETA_CAMPO = "Jugadores de campo"
POSICIONES_RENDIMIENTO = ["Defensa", "Medio", "Delantero"]

# Qué mide cada posición en el panel de rendimiento y cómo se llama en la vista.
METRICAS = {
    "Delantero": {"etiqueta": "npxG + xA por 90'", "corta": "xG sin penales + xA por 90'", "fuente": FUENTE_UNDERSTAT},
    "Medio": {"etiqueta": "npxG + xA por 90'", "corta": "xG sin penales + xA por 90'", "fuente": FUENTE_UNDERSTAT},
    "Defensa": {"etiqueta": "entradas ganadas + intercepciones por 90'", "corta": "entradas ganadas + intercepciones por 90'",
                "fuente": FUENTE_FBREF},
}


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
    separado) viene en dos filas y se junta en una: minutos y xG/xA suman; el denominador es el del club con
    más partidos (ver `minutos_disponibles`); la posición es la de la fila donde más jugó. Quien no tiene año
    de nacimiento (≈5%, no cruzó con FBref) queda fuera: sin él no hay edad."""
    p = players[players["temporada"].isin(temporadas)].copy()
    sin_nacimiento = int(p["born"].isna().sum())
    p = p[p["born"].notna()].copy()
    p["edad"] = edad_de(p["temporada"], p["born"])
    p["clave"] = p["player_fbref"].fillna(p["player"]) if "player_fbref" in p.columns else p["player"]
    p["disp"] = [minutos_disponibles(t, l, e, partidos) for t, l, e in zip(p["temporada"], p["liga"], p["team"])]
    # recoveries90 de la vista (entradas ganadas + intercepciones por 90', no las recuperaciones de FBref).
    # Cada tasa es por los minutos de FBref, no los de Understat, así que al juntar dos filas se pondera por minutos
    # solo entre las que la tienen.
    p["def90"] = p["tkl_w90"] + p["interceptions90"]
    p["_peso"] = p["def90"] * p["min"]
    p["_min_def"] = p["min"].where(p["def90"].notna())
    p = p.sort_values("min", ascending=False, kind="stable")
    g = p.groupby(["temporada", "clave", "born"], sort=False, dropna=False)
    jt = g.agg(min=("min", "sum"), np_xg=("np_xg", "sum"), xA=("xA", "sum"), disp=("disp", "max"),
               posicion=("posicion", "first"), edad=("edad", "first"),
               _peso=("_peso", "sum"), _min_def=("_min_def", "sum")).reset_index()
    jt["def90"] = jt["_peso"] / jt["_min_def"].where(jt["_min_def"] > 0)
    jt["ofe90"] = (jt["np_xg"] + jt["xA"]) / (jt["min"] / 90)
    jt["pct"] = (100 * jt["min"] / jt["disp"]).clip(upper=100)
    jt = jt.drop(columns=["_peso", "_min_def"])
    jt.attrs["sin_nacimiento"] = sin_nacimiento
    jt.attrs["sin_club"] = int(jt["disp"].isna().sum())
    return jt


# --- panel 1: minutos por edad ----------------------------------------------------------------------

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


# --- panel 2: rendimiento por edad, método del cambio de un año al siguiente --------------------------

def metrica_de(posicion):
    return "def90" if posicion == "Defensa" else "ofe90"


def pares_consecutivos(jt, posicion, temporadas):
    """Los jugadores que aparecen en DOS temporadas cerradas seguidas con ≥ `MINUTOS_CAMBIO` en cada una, en la misma
    posición y con la métrica de esa posición en las dos. Una fila por par: edad en la primera temporada, valor
    de la métrica en la primera (m0) y en la segunda (m1) y un identificador de jugador (para remuestrear
    jugadores y no pares: un mismo jugador aporta un par por cada edad)."""
    col = metrica_de(posicion)
    idx = {t: i for i, t in enumerate(temporadas)}
    d = jt[(jt["posicion"] == posicion) & (jt["min"] >= MINUTOS_CAMBIO) & jt[col].notna()
           & jt["temporada"].isin(idx)].copy()
    d["ti"] = d["temporada"].map(idx)
    a = d[["clave", "born", "ti", "edad", col]].rename(columns={col: "m0"})
    b = d[["clave", "born", "ti", col]].rename(columns={col: "m1"})
    b["ti"] = b["ti"] - 1
    pares = a.merge(b, on=["clave", "born", "ti"])
    pares["pid"] = pares.groupby(["clave", "born"], sort=False).ngroup()
    return pares[["pid", "edad", "m0", "m1"]].reset_index(drop=True)


def _tramo(n_por_edad, ancla):
    """Las edades de salida a, contiguas, con suficientes pares y que incluyen la transición pegada al ancla."""
    ok = lambda a: n_por_edad.get(a, 0) >= PARES_MIN_TRANSICION  # noqa: E731
    if ok(ancla):
        semilla = ancla
    elif ok(ancla - 1):
        semilla = ancla - 1
    else:
        return None
    lo = hi = semilla
    while ok(lo - 1):
        lo -= 1
    while ok(hi + 1):
        hi += 1
    return lo, hi


def curva_de_cambios(pares, replicas=REPLICAS, semilla=SEMILLA, ancla=ANCLA, nivel=NIVEL_IC):
    """La curva de rendimiento por edad encadenando el cambio de una edad a la siguiente.

    Para cada edad de salida `a`: R(a) = Σ m1 / Σ m0 sobre los pares de esa edad (cuánto sube o baja en promedio
    la métrica de esos jugadores de una temporada a la siguiente, en proporción; el cociente de sumas es mucho más
    estable que el promedio de cocientes cuando hay jugadores cerca de 0). La curva se encadena con esos R y se
    expresa relativa a su valor a los `ancla` años (= 100). El intervalo es un bootstrap por JUGADOR (se remuestrean
    jugadores, no pares, porque un mismo jugador aporta un par por edad) con `replicas` réplicas y semilla fija.
    También devuelve cuántas veces cada edad fue el máximo de la curva.

    Devuelve None si no hay un tramo de transiciones con suficientes pares alrededor del ancla."""
    n_edad = pares.groupby("edad").size().to_dict()
    tramo = _tramo({int(a): int(n) for a, n in n_edad.items()}, ancla)
    if tramo is None:
        return None
    lo, hi = tramo
    salidas = list(range(lo, hi + 1))
    p = pares[pares["edad"].between(lo, hi)].reset_index(drop=True)
    ia = (p["edad"].to_numpy() - lo).astype(int)
    onehot = np.zeros((len(p), len(salidas)))
    onehot[np.arange(len(p)), ia] = 1.0
    m0, m1 = p["m0"].to_numpy(float), p["m1"].to_numpy(float)
    pid = p["pid"].to_numpy()
    jugadores = int(pid.max()) + 1
    nodos = list(range(lo, hi + 2))                         # edades de la curva: la de salida más la última de llegada
    k_ancla = nodos.index(ancla)                            # siempre está: el tramo incluye la transición 22 o la 21
    # cuántos pares y jugadores distintos aporta cada transición, para decirlo en el tooltip
    n_pares = [int(n_edad.get(a, 0)) for a in salidas]
    n_jug = [int(p.loc[p["edad"] == a, "pid"].nunique()) for a in salidas]

    def a_curva(w):
        s1 = (w * m1) @ onehot
        s0 = (w * m0) @ onehot
        logr = np.log(s1 / s0)                              # (…, transiciones)
        log = np.zeros(logr.shape[:-1] + (len(nodos),))
        log[..., 1:] = np.cumsum(logr, axis=-1)
        log -= log[..., [k_ancla]]                          # 0 en el ancla: la curva vale 100 ahí
        return 100 * np.exp(log)

    estimada = a_curva(np.ones(len(p)))
    rng = np.random.default_rng(semilla)
    cuentas = np.stack([np.bincount(rng.integers(0, jugadores, jugadores), minlength=jugadores)
                        for _ in range(replicas)])
    curvas = a_curva(cuentas[:, pid].astype(float))         # (réplicas, nodos)
    alfa = (1 - nivel) / 2
    inf, sup = np.quantile(curvas, [alfa, 1 - alfa], axis=0)
    pico = int(np.argmax(estimada))
    picos = np.argmax(curvas, axis=1)
    prob = np.bincount(picos, minlength=len(nodos)) / len(picos)
    p10, p90 = np.quantile(np.array(nodos)[picos], [0.10, 0.90])
    return {
        "e": nodos, "curva": [round(float(v), 1) for v in estimada],
        "lo": [round(float(v), 1) for v in inf], "hi": [round(float(v), 1) for v in sup],
        "pares": n_pares, "jugadoresPorTransicion": n_jug,
        "ancla": nodos[k_ancla], "pares_total": int(len(p)), "jugadores": jugadores,
        "pico": nodos[pico], "picoValor": round(float(estimada[pico]), 1),
        "picoP10": int(p10), "picoP90": int(p90),
        "picoProb": {str(nodos[i]): round(float(v), 3) for i, v in enumerate(prob) if v > 0},
    }


def rendimiento_por_edad(jt, temporadas):
    salida = {}
    for i, pos in enumerate(POSICIONES_RENDIMIENTO):
        pares = pares_consecutivos(jt, pos, temporadas)
        r = curva_de_cambios(pares, semilla=SEMILLA + i) if len(pares) else None
        if r:
            r["metrica"] = METRICAS[pos]["etiqueta"]
            salida[pos] = r
    return salida


# --- la vista --------------------------------------------------------------------------------------

def calcular(players, teams, en_curso=None):
    """Todo el cálculo de la vista a partir de las tablas crudas (los tests lo llaman con datos sintéticos)."""
    en_curso = set(en_curso if en_curso is not None else temporadas_en_curso())
    temporadas = sorted(t for t in players["temporada"].unique() if t not in en_curso)
    jt = jugador_temporadas(players, partidos_por_club(teams), temporadas)
    return {"temporadas": temporadas, "jt": jt,
            "minutos": {k: minutos_por_edad(jt, k) for k in POSICIONES_MINUTOS},
            "rendimiento": rendimiento_por_edad(jt, temporadas)}


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
    nivel = round(100 * NIVEL_IC)
    cola = round((100 - nivel) / 2)
    sin_nac = jt.attrs["sin_nacimiento"]
    ambiguos = int(jt["posicion"].isna().sum())
    rend = r["rendimiento"]
    pares = "; ".join(f"{pos} {_n(rend[pos]['pares_total'])} pares de {_n(rend[pos]['jugadores'])} jugadores"
                      for pos in POSICIONES_RENDIMIENTO if pos in rend)
    que_mirar = (
        "Arriba, la línea es la **mediana** y la franja el **rango típico** (del percentil 25 al 75): la mitad de los "
        "jugadores de esa edad cae dentro de la franja. Las barras de abajo cuentan los jugador-temporadas de cada edad: "
        "donde son pocos, la línea se mueve más.\n\n"
        f"Abajo, la curva no compara edades distintas: sigue al **mismo jugador** de una temporada a la siguiente y "
        f"encadena esos cambios. Vale 100 a los {ANCLA} años y la franja es el intervalo del {cola}% al {100 - cola}% de "
        f"{_n(REPLICAS)} réplicas. Si las franjas de dos edades se traslapan, la diferencia entre ellas no es firme.\n\n"
        "Pasa el cursor o toca una edad para leer los números de los dos paneles a la vez.")
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
        f"**Cómo se estima el rendimiento.** Comparar el promedio de cada edad engaña: a los 34 solo siguen jugando los que "
        f"siguen siendo buenos. Por eso se toman los jugadores con al menos {MINUTOS_CAMBIO} minutos en dos temporadas "
        f"seguidas, en la misma posición, y para cada edad se calcula cuánto cambia en conjunto su métrica del año a al a+1 "
        f"(la suma del año siguiente entre la suma del anterior). Esos cambios se encadenan en una curva que vale 100 a "
        f"los {ANCLA} años, y solo entran las transiciones con al menos {PARES_MIN_TRANSICION} pares. Muestra usada: {pares}.\n\n"
        f"**Qué se mide.** Delantero y Medio: xG sin penales + xA por 90' (Understat). Defensa: entradas ganadas + "
        f"intercepciones por 90' (FBref). Eso es actividad defensiva y no calidad: puede bajar con la edad porque el jugador "
        f"se coloca mejor y necesita menos acciones, no porque defienda peor. El portero queda fuera: ninguna de las dos "
        f"métricas lo describe.\n\n"
        f"**El intervalo.** Es un bootstrap por jugador: {_n(REPLICAS)} réplicas que remuestrean jugadores completos "
        f"(uno aporta un par por cada edad, y remuestrear pares aparentaría más datos de los que hay), con semilla fija. La "
        f"franja va del {cola}% al {100 - cola}%; a los {ANCLA} años no tiene ancho porque ahí la curva vale 100 por "
        f"construcción. El «pico» es la edad donde la curva estimada es más alta, y para saber qué tan firme es se vuelve a "
        f"buscar el máximo en cada réplica.\n\n"
        f"**Qué sesgo queda.** Solo se mide a quien sigue jugando {MINUTOS_CAMBIO} minutos o más dos años seguidos: quien se "
        f"lesiona, se retira o pierde la titularidad sale del cálculo, y eso hace que las edades mayores se vean mejor de lo "
        f"que son. Además, quien tuvo un año fuera de lo normal tiende a volver a su nivel al siguiente. La curva describe a "
        f"quien se mantiene como titular, no a todos los de esa edad.")
    return que_mirar, por_que


AVISO_SESGO = (f"Solo cuenta a quien sigue jugando {MINUTOS_CAMBIO} minutos o más dos años seguidos: quien se retira o pierde "
               f"su sitio no está, y las edades mayores se ven mejor de lo que son.")


def payload(r):
    """Lo que viaja al navegador: por posición, una tabla corta por edad. Nada de jugadores uno por uno."""
    return {
        "entidad": SLUG,
        "temporadas": r["temporadas"],
        "edades": [EDAD_MIN, EDAD_MAX],
        "minJugadores": MIN_JUGADORES, "minutosCambio": MINUTOS_CAMBIO, "ancla": ANCLA,
        "replicas": REPLICAS, "nivelIc": round(100 * NIVEL_IC),
        "minutos": {k: {c: v for c, v in d.items()} for k, d in r["minutos"].items()},
        "rendimiento": r["rendimiento"],
        "coloresPos": {z[0]: z[2] for z in PITCH_ZONAS},
    }


def chart_age() -> ChartPage:
    players, teams = _cargar()
    r = calcular(players, teams)
    react_views.registrar_payload(SLUG, payload(r))
    que_mirar, por_que = textos(r)
    bajada = ("Arriba, qué parte de los minutos de su club juega cada edad. Abajo, cómo cambia el rendimiento del mismo "
              "jugador de un año al siguiente.")
    assert len(bajada) <= 160, f"{SLUG}: la bajada mide {len(bajada)} caracteres"
    cfg = {
        "id": SLUG, "titulo": TITULO, "bajada": bajada, "pregunta": PREGUNTAS[SLUG], "tabla": SLUG,
        "queMirar": que_mirar, "porQue": por_que, "avisoSesgo": AVISO_SESGO,
        "fuente": f"{FUENTE_UNDERSTAT} y {FUENTE_FBREF}",
        "posiciones": [{"id": CAMPO, "etiqueta": ETIQUETA_CAMPO}] + [{"id": p, "etiqueta": p} for p in POSICIONES_MINUTOS[1:]],
        "metricas": {p: m["etiqueta"] for p, m in METRICAS.items()},
        "edades": [EDAD_MIN, EDAD_MAX],
    }
    return ChartPage(slug=SLUG, section=SECTION, title=TITULO, subtitle=bajada,
                     body_html=react_views.montar_html("edad", SLUG, cfg, alto_min=900), kind="line")
