"""«Forma durante la temporada»: la diferencia de xG por partido de un equipo, en ventana móvil de 6 partidos.

Una sola gráfica con selector de temporada y de equipo (y un segundo equipo opcional para comparar). Dibuja
la diferencia de xG por partido (a favor menos en contra, sin penales) promediada en ventanas de `VENTANA`
partidos seguidos, la diferencia de goles en la misma ventana (más tenue) y el resultado de cada partido
(G/E/P, de local o de visita).

Todo el cálculo vive aquí (en el build, determinista). Al navegador viaja una tabla chica por equipo y
temporada con los arrays por partido y las dos ventanas ya calculadas (`dist/react/datos-forma.js`); el texto
«Con estos filtros» se arma en el navegador (`formaLectura.js`).

**xG por partido.** Sale de los tiros de Understat (`shots_all_seasons.csv`), con la misma regla de
`xg_equipos.py`: sin penales (`situation == "Penalty"`); los autogoles ya vienen con xG 0. A diferencia de
`xg_equipos.py` aquí no hace falta deducir el `rival` de los tiros: el partido se identifica por `game_id` y
los dos equipos salen de `partidos.csv` (`local` y `visita`), así que el xG EN CONTRA de un equipo es
simplemente el xG A FAVOR del otro en ese `game_id`. En los 4 partidos donde Understat solo trae los tiros de
uno de los dos equipos el que no tiró queda con xG 0 (igual que en `xg_equipos.py`). En el único partido de
`partidos.csv` sin ningún tiro en Understat, el xG queda sin dato (no se inventa) y cualquier ventana que lo
contenga no se dibuja.

**Goles.** Salen del marcador de `partidos.csv`, con penales y autogoles (es lo que cuenta la tabla y lo que
decide G/E/P). Es una diferencia de criterio con el xG (sin penales) que el texto «Por qué así» dice.

**Orden.** Los partidos de un equipo se ordenan por fecha (y por `game_id` si hay dos el mismo día). El
número de partido es el lugar en ese orden, no la jornada oficial: un partido aplazado queda donde se jugó.
"""

import math

import numpy as np
import pandas as pd

import react_views
from nombres import club_visible
from preguntas import PREGUNTAS
from site_utils import PROCESSED_DIR, DATA_DIR, ChartPage, temporadas_en_curso
from viz_theme import DIVERGING, FUENTE_UNDERSTAT

SECTION = "Equipos"
SLUG = "forma"
TITULO = "Forma durante la temporada"
BAJADA = "Diferencia de xG por partido en ventanas de 6 partidos, con el resultado de cada uno."

VENTANA = 6          # partidos por ventana
TRAMO = 12           # partidos del primer y del último tramo que compara la tendencia (en el navegador)
K_RUIDO = 2          # la tendencia solo se llama mejora o caída si pasa de K_RUIDO errores típicos
PENAL = "Penalty"
COLS_TIROS = ["temporada", "liga", "game_id", "team", "xg", "situation", "result"]
COLS_PARTIDOS = ["temporada", "liga", "game_id", "fecha", "local", "visita", "goles_l", "goles_v"]
EPOCA = pd.Timestamp("1970-01-01")


# --- el cálculo ----------------------------------------------------------------------------------

def ventana_movil(valores, n=VENTANA):
    """Promedio móvil de `n` valores seguidos, uno por posición. Las primeras `n - 1` no tienen ventana
    completa y quedan en `None`; una ventana con algún valor sin dato (`None` o NaN) también."""
    out = []
    for i in range(len(valores)):
        w = valores[i - n + 1:i + 1] if i >= n - 1 else []
        if len(w) < n or any(v is None or (isinstance(v, float) and math.isnan(v)) for v in w):
            out.append(None)
        else:
            out.append(float(sum(w)) / n)
    return out


def resultado(gf, gc):
    return "G" if gf > gc else "P" if gf < gc else "E"


def xg_por_partido(tiros):
    """{(game_id, team): xG sin penales} de los tiros (un par que no está no tiró: xG 0)."""
    sp = tiros[tiros["situation"] != PENAL]
    return sp.groupby(["game_id", "team"])["xg"].sum().to_dict()


def partidos_por_equipo(partidos, tiros):
    """Una fila por equipo y partido, con el nombre ya cruzado (`club_visible`) y en orden de fecha:

    `temporada, liga, equipo, rival, local (1/0), fecha, game_id, gf, gc, xf, xc, res`. `xf` y `xc` son el xG
    a favor y en contra sin penales; NaN si Understat no trae ningún tiro de ese partido. Solo las temporadas
    que tienen tiros."""
    p = partidos[partidos["temporada"].isin(set(tiros["temporada"]))]
    xg = xg_por_partido(tiros)
    con_tiros = set(tiros["game_id"])
    filas = []
    for r in p.itertuples(index=False):
        hay = r.game_id in con_tiros
        xl = xg.get((r.game_id, r.local), 0.0) if hay else np.nan
        xv = xg.get((r.game_id, r.visita), 0.0) if hay else np.nan
        fecha = pd.Timestamp(r.fecha)
        for equipo, rival, local, gf, gc, xf, xc in (
                (r.local, r.visita, 1, r.goles_l, r.goles_v, xl, xv),
                (r.visita, r.local, 0, r.goles_v, r.goles_l, xv, xl)):
            filas.append((r.temporada, r.liga, club_visible(equipo), club_visible(rival), local, fecha,
                          int(r.game_id), int(gf), int(gc), xf, xc, resultado(gf, gc)))
    df = pd.DataFrame(filas, columns=["temporada", "liga", "equipo", "rival", "local", "fecha", "game_id",
                                      "gf", "gc", "xf", "xc", "res"])
    return df.sort_values(["temporada", "liga", "equipo", "fecha", "game_id"], kind="stable").reset_index(drop=True)


def con_ventanas(pe, n=VENTANA):
    """`pe` más `vx` y `vg`: la diferencia de xG y de goles por partido en la ventana de `n` partidos que
    TERMINA en cada partido del equipo (`None` donde no hay ventana completa o falta un xG)."""
    pe = pe.copy()
    pe["dx"] = pe["xf"] - pe["xc"]
    pe["dg"] = pe["gf"] - pe["gc"]
    vx, vg = [], []
    for _, g in pe.groupby(["temporada", "liga", "equipo"], sort=False):
        vx += ventana_movil([None if pd.isna(v) else float(v) for v in g["dx"]], n)
        vg += ventana_movil([float(v) for v in g["dg"]], n)
    pe["vx"], pe["vg"] = vx, vg
    return pe


def ruido_por_partido(pe, temporadas):
    """Desviación típica de la diferencia de xG de UN partido alrededor del promedio de su equipo y su
    temporada (suma de cuadrados de las desviaciones entre los grados de libertad). Es el «ruido» de un
    partido: lo que se mueve la diferencia de xG de un partido a otro con el nivel del equipo fijo."""
    d = pe[pe["temporada"].isin(temporadas)].dropna(subset=["dx"])
    desv = d["dx"] - d.groupby(["temporada", "liga", "equipo"])["dx"].transform("mean")
    grupos = d.groupby(["temporada", "liga", "equipo"]).ngroups
    return float(math.sqrt((desv ** 2).sum() / (len(d) - grupos)))


def calcular(partidos, tiros, equipos=None, en_curso=None):
    """Todo el cálculo de la vista (los tests lo llaman con datos sintéticos). `equipos` es la tabla de
    FBref (`temporada, liga, Squad, ov_Playing Time_MP, ov_Performance_Gls`) para comprobar partidos y goles;
    sin ella esas dos comprobaciones quedan vacías."""
    en_curso = set(en_curso if en_curso is not None else temporadas_en_curso())
    pe = con_ventanas(partidos_por_equipo(partidos, tiros))
    temporadas = sorted(pe["temporada"].unique())
    cerradas = [t for t in temporadas if t not in en_curso]

    tc = tiros[tiros["temporada"].isin(cerradas) & (tiros["situation"] != PENAL)]
    goles_np = int((tc["result"] == "Goal").sum())
    por_partido = tiros.groupby("game_id")["team"].nunique()
    penales = tiros.loc[tiros["situation"] == PENAL, "xg"]

    r = {"pe": pe, "temporadas": temporadas, "en_curso": en_curso, "cerradas": cerradas,
         "sigma": ruido_por_partido(pe, cerradas) if cerradas else float("nan"),
         "xg_np": float(tc["xg"].sum()), "goles_np": goles_np,
         "xg_penal": float(penales.mean()) if len(penales) else float("nan"),
         "partidos_sin_tiros": int((~partidos[partidos["temporada"].isin(temporadas)]["game_id"]
                                    .isin(set(tiros["game_id"]))).sum()),
         "partidos_un_equipo": int((por_partido == 1).sum()),
         "autogoles": int((tiros["result"] == "Own Goal").sum()),
         "n_partidos": len(partidos[partidos["temporada"].isin(temporadas)]),
         "descuadres": [], "dif_goles": None}
    pj = pe.groupby(["temporada", "equipo"]).size()
    r["en_curso_n"] = {t: int(pj[t].max()) for t in temporadas if t in en_curso}
    r["pj_min"] = int(pj.loc[cerradas].min()) if cerradas else 0
    r["pj_max"] = int(pj.loc[cerradas].max()) if cerradas else 0
    if equipos is not None:
        r["descuadres"], r["dif_goles"] = comprobar_con_fbref(pe, equipos)
    return r


def comprobar_con_fbref(pe, equipos):
    """(equipo-temporadas cuyo número de partidos no es el de FBref, diferencia total de goles a favor).

    Los partidos de FBref son los jugados (`ov_Playing Time_MP`); los de `partidos.csv` salen de Understat.
    Devuelve `([(temporada, liga, equipo, partidos aquí, partidos FBref)], goles aquí − goles FBref)`."""
    e = equipos.copy()
    e["equipo"] = e["Squad"].map(club_visible)
    mias = pe.groupby(["temporada", "liga", "equipo"]).agg(n=("gf", "size"), g=("gf", "sum")).reset_index()
    m = mias.merge(e[["temporada", "liga", "equipo", "ov_Playing Time_MP", "ov_Performance_Gls"]],
                   on=["temporada", "liga", "equipo"], how="outer", indicator=True)
    if (m["_merge"] != "both").any():
        raise ValueError(f"Forma: equipos sin pareja entre partidos.csv y FBref: "
                         f"{m.loc[m['_merge'] != 'both', ['temporada', 'equipo']].values.tolist()}")
    mal = m[m["n"] != m["ov_Playing Time_MP"]]
    descuadres = [(t, l, e, int(n), int(mp)) for t, l, e, n, mp in
                  zip(mal["temporada"], mal["liga"], mal["equipo"], mal["n"], mal["ov_Playing Time_MP"])]
    return descuadres, int(m["g"].sum() - m["ov_Performance_Gls"].sum())


# --- el payload ----------------------------------------------------------------------------------

def _x(v, dec=3):
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else round(float(v), dec)


def _dia(f):
    return int((f - EPOCA).days)


def payload(r, inicial):
    """Lo que viaja al navegador. Por temporada y equipo, arrays por partido en orden de fecha:
    `r` rival (índice en `nombres`), `h` 1 si fue de local, `gf` y `gc` goles, `xf` y `xc` xG sin penales (null
    si Understat no trae los tiros del partido), `d` días desde 1970-01-01, y las dos ventanas `vx` y `vg`
    (diferencia de xG y de goles por partido de los últimos `VENTANA`, null sin ventana completa)."""
    pe = r["pe"]
    nombres = sorted(set(pe["equipo"]))
    idx = {n: i for i, n in enumerate(nombres)}
    t = {}
    for (temp, equipo), g in pe.groupby(["temporada", "equipo"], sort=True):
        t.setdefault(temp, {})[equipo] = {
            "l": g["liga"].iloc[0],
            "r": [idx[x] for x in g["rival"]],
            "h": [int(v) for v in g["local"]],
            "gf": [int(v) for v in g["gf"]],
            "gc": [int(v) for v in g["gc"]],
            "xf": [_x(v) for v in g["xf"]],
            "xc": [_x(v) for v in g["xc"]],
            "d": [_dia(f) for f in g["fecha"]],
            "vx": [_x(v) for v in g["vx"]],
            "vg": [_x(v, 4) for v in g["vg"]],
        }
    return {"entidad": SLUG, "temporadas": r["temporadas"], "enCurso": r["en_curso_n"],
            "ventana": VENTANA, "tramo": TRAMO, "kRuido": K_RUIDO, "sigma": round(r["sigma"], 4),
            "nombres": nombres, "inicial": inicial, "t": t}


def equipo_inicial(r):
    """El club con más diferencia de xG por partido en la última temporada cerrada: abre la vista con un
    equipo que tiene algo que contar y sin escribir un nombre a mano."""
    pe = r["pe"]
    ultima = r["cerradas"][-1]
    d = pe[pe["temporada"] == ultima].groupby("equipo")["dx"].mean()
    return str(d.idxmax())


# --- los textos fijos ----------------------------------------------------------------------------

def _n(n):
    return f"{int(n):,}"


def _contraste_fbref(r):
    """El párrafo de cómo cuadran los partidos y los goles con la tabla de FBref (vacío sin esa tabla)."""
    if r["dif_goles"] is None:
        return ""
    t = ("**Contra FBref.** Los partidos y los marcadores salen de Understat. Sumados, los goles a favor de los equipos "
         f"son {_n(r['dif_goles'])} más que los de la tabla de FBref; Understat registra {_n(r['autogoles'])} autogoles en esos "
         "partidos: el marcador los cuenta como gol del equipo beneficiado y la columna de goles de FBref (la de los jugadores) no.")
    if r["descuadres"]:
        lista = ", ".join(f"{e} {t_} ({n} partidos aquí y {mp} en FBref)" for t_, _l, e, n, mp in r["descuadres"])
        t += f" En {len(r['descuadres'])} equipo-temporadas el número de partidos tampoco coincide: {lista}."
    return t + "\n\n"


def textos(r):
    """(qué más mirar, por qué así). Cada cifra sale de las constantes de este módulo o de los datos."""
    sigma = r["sigma"]
    s = lambda n: sigma / math.sqrt(n)        # el error típico de un promedio de n partidos independientes
    cerradas = r["cerradas"]
    menos = 100 * (1 - r["goles_np"] / r["xg_np"])
    que_mirar = (
        f"Cada punto de la línea es el **promedio de los últimos {VENTANA} partidos**: el del partido 12 resume del 7 al 12, "
        f"el del 13 del 8 al 13. Por eso la línea es más suave que los partidos sueltos y por eso tarda en reaccionar: "
        f"un partido muy bueno entra en seis puntos seguidos y luego sale de golpe.\n\n"
        f"**Qué es ruido.** Un solo partido mueve la diferencia de xG en torno a ±{sigma:.1f} aunque el equipo no cambie "
        f"(desviación típica dentro de cada equipo y temporada). Un promedio de {VENTANA} partidos todavía se mueve ±{s(VENTANA):.2f} "
        f"solo por azar, así que un bache o un repunte de unas décimas no dice que el equipo haya cambiado. Mira mejor tramos "
        f"largos en un mismo lado del cero y que el xG y los goles vayan juntos.\n\n"
        f"Pasa el cursor o toca un partido para ver el rival, el marcador y el xG de cada lado.")
    por_que = (
        f"**La ventana.** El eje es el orden en que el equipo jugó sus partidos (por fecha), no la jornada oficial. Cada punto "
        f"promedia los {VENTANA} partidos que terminan en él, así que la línea empieza en el partido {VENTANA}: antes no hay "
        f"{VENTANA} partidos y no se dibuja nada en vez de promediar menos. Si Understat no trae los tiros de un partido "
        f"({_n(r['partidos_sin_tiros'])} de los {_n(r['n_partidos'])}), su xG queda sin dato y las ventanas que lo contienen no "
        f"se dibujan.\n\n"
        f"**Por qué {VENTANA}.** Es el {round(100 * VENTANA / r['pj_max'])}% de una temporada de {r['pj_max']} partidos "
        f"(los equipos juegan entre {r['pj_min']} y {r['pj_max']} según la liga): sigue los cambios de rumbo sin quedar en "
        f"manos de un solo partido. Con 3 partidos el ruido de azar sería de ±{s(3):.2f} (contra ±{s(VENTANA):.2f} con {VENTANA}); "
        f"con 10 bajaría a ±{s(10):.2f}, pero cada punto tardaría más en notar un cambio y a cada equipo le quedarían menos "
        f"ventanas. Esas cifras suponen partidos independientes entre sí: son una guía, no una garantía.\n\n"
        f"**Por qué xG sin penales.** Un penal vale {r['xg_penal']:.2f} de xG en promedio y lo decide una acción, no cómo juega el equipo. Quitarlo "
        f"es lo que hace el resto del sitio (los xG de los equipos son sin penales y sin autogoles). La línea tenue de "
        f"**goles** sale del marcador, con penales y autogoles, porque es lo que cuenta la tabla y lo que decide G, E o P: "
        f"un equipo que cobra muchos penales verá su línea de goles un poco por encima de la de xG sin que eso sea juego.\n\n"
        f"**Límites.** Un partido es muy poca muestra: el resultado depende mucho del azar y el xG lo mide solo en parte. "
        f"El xG de Understat suma más de lo que entra: en las {len(cerradas)} temporadas cerradas ({cerradas[0]} a {cerradas[-1]}) "
        f"los tiros sin penales valen {_n(round(r['xg_np']))} de xG y terminaron en {_n(r['goles_np'])} goles, {menos:.0f}% menos. "
        f"La diferencia (a favor menos en contra) no se sesga por eso, porque lo que le sobra al que tira le sobra también al "
        f"rival que concede; pero el xG de cada lado en el hover queda, en promedio, por encima de los goles. "
        f"Un empate en el marcador puede esconder un dominio claro, y una victoria un partido que el rival mereció. Y el xG "
        f"no ve quién jugó: una plantilla con bajas importantes o recién reforzada cambia de nivel sin que la ventana lo explique.\n\n"
        f"{_contraste_fbref(r)}"
        f"**La temporada en curso** se marca como tal. Con tan pocos partidos no tiene ventanas suficientes para decir nada sobre su forma: "
        f"se muestran los partidos y el texto no concluye.")
    return que_mirar, por_que


# --- la vista ------------------------------------------------------------------------------------

def _cargar():
    cols = ["temporada", "liga", "Squad", "ov_Playing Time_MP", "ov_Performance_Gls"]
    equipos = pd.read_csv(PROCESSED_DIR / "teams_all_seasons.csv", usecols=cols, encoding="utf-8-sig")
    tiros = pd.read_csv(PROCESSED_DIR / "shots_all_seasons.csv", usecols=COLS_TIROS, encoding="utf-8-sig",
                        keep_default_na=False, na_values=[""])
    temporadas = sorted(tiros["temporada"].unique())
    partidos = pd.concat([pd.read_csv(DATA_DIR / t / "partidos.csv", usecols=COLS_PARTIDOS, encoding="utf-8-sig")
                          for t in temporadas], ignore_index=True)
    return partidos, tiros, equipos


def chart_forma() -> ChartPage:
    partidos, tiros, equipos = _cargar()
    en_curso = temporadas_en_curso()
    r = calcular(partidos, tiros, equipos, en_curso)
    react_views.registrar_payload(SLUG, payload(r, equipo_inicial(r)))
    que_mirar, por_que = textos(r)
    assert len(BAJADA) <= 108, f"{SLUG}: la bajada mide {len(BAJADA)} caracteres"
    cfg = {
        "id": SLUG, "titulo": TITULO, "bajada": BAJADA, "pregunta": PREGUNTAS[SLUG], "tabla": SLUG,
        "queMirar": que_mirar, "porQue": por_que,
        "fuente": FUENTE_UNDERSTAT,
        # El equipo principal va en la tinta del sitio y el de comparación en ámbar (no azul ni rojo: son los del resultado).
        "colores": {"claro": {"a": "#2C4C54", "b": "#B35A00"}, "oscuro": {"a": "#D7E4E7", "b": "#F0A04B"}},
        "resultado": {"G": DIVERGING["pos"], "P": DIVERGING["neg"]},
    }
    return ChartPage(slug=SLUG, section=SECTION, title=TITULO, subtitle=BAJADA,
                     body_html=react_views.montar_html("forma", SLUG, cfg, alto_min=520), kind="line")
