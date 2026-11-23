"""«Tabla real vs. esperada»: los puntos que sumó cada equipo contra los que valían sus ocasiones (xPts).

Todo el cálculo vive aquí, en el build y determinista. Al navegador viaja SOLO una tabla por equipo y
temporada (`dist/react/datos-tabla-esperada.js`, unos 580 renglones); los textos que dependen de la liga y la
temporada elegidas los arma `TablaEsperadaVista.jsx` sobre esa tabla.

**Método (xPts).** De cada partido salen las probabilidades de ganar, empatar y perder de cada equipo a
partir del xG de cada tiro, y de ahí los puntos esperados: 3 por la probabilidad de ganar más 1 por la de
empatar. Los goles de cada equipo se modelan como la suma de un Bernoulli por tiro (la probabilidad de
cada uno es su `xg`), con tiros independientes entre sí y los dos equipos independientes entre sí. El
resultado es la distribución exacta de goles de cada equipo (una binomial de Poisson, por convolución), no
una simulación: no hay azar en el build.

**Alternativa que se compara.** Poisson sobre el xG total del partido: los goles de cada equipo con media
igual a la suma del xG de sus tiros. Es la manera común de convertir el xG de un partido en un resultado.
Ignora que el xG está repartido en tiros chicos y grandes (una ocasión de 0.9 y diez de 0.09 suman lo mismo
y no se parecen), y por eso reparte los goles con más dispersión. La vista usa la de tiros; `validar` y el
texto «Por qué así» muestran las dos con sus cifras.

**Penales y autogoles.** Los penales ENTRAN: cada uno es un tiro más con su xG (~0.78), porque los puntos
reales también los llevan y dejarlos fuera le quitaría puntos esperados justo a los equipos que más penales
cobran. Es distinto a las demás vistas de Equipos, que miran el xG sin penales. Los autogoles tienen xG 0,
así que no suman a los esperados (no salen de ninguna ocasión) y sí a los puntos reales: fueron puntos de
verdad, y esa es parte de la suerte que la vista quiere mostrar.

**Partidos que no cuadran.** Si en un partido los goles que traen los tiros no son los del marcador, los
tiros están incompletos o repetidos y no sirven para armar los goles: ese partido se calcula con Poisson
sobre el xG del partido que da Understat. Si ni siquiera hay tiros, el partido NO entra en ningún total (ni
en los puntos reales ni en los esperados) y los dos equipos figuran con un partido menos. Se detecta en
los datos, no a mano.

**Puntos reales y tabla.** Los puntos salen de los marcadores de `partidos.csv`: 3 por ganar y 1 por
empatar. No descuentan sanciones de la liga. La posición real ordena por puntos, luego diferencia de goles,
luego goles a favor (no todas las ligas desempatan así); la posición esperada, por xPts.

**Cruce de nombres.** Los partidos traen los nombres de Understat. Se pasan por `nombres.club_visible` y se
comparan con los clubes de FBref de cada liga y temporada (la misma comprobación que `xg_equipos`): si a
un club le falta pareja de un lado o del otro, el build se detiene con el detalle.
"""

import math
import re
from collections import defaultdict

import numpy as np
import pandas as pd

import react_views
from nombres import club_visible
from preguntas import PREGUNTAS
from site_utils import DATA_DIR, PROCESSED_DIR, ChartPage, temporadas_en_curso
from viz_theme import DIVERGING, FUENTE_UNDERSTAT, LEAGUE_ORDER

SECTION = "Equipos"
SLUG = "tabla-esperada"
TITULO = "Tabla real vs. esperada"
BAJADA = "Puntos reales contra los que valían las ocasiones de cada equipo, por liga y temporada."

PENAL, GOL, AUTOGOL = "Penalty", "Goal", "Own Goal"
COLS_TIROS = ["game_id", "team", "xg", "situation", "result"]
KMAX_POISSON = 30            # más goles que estos no pasan en un partido; el resto se junta en el último
COL_PARTIDOS_FBREF = "ov_Playing Time_MP"
COL_PPM = "pt_Team Success_PPM"
DECIMALES = 6                # con los que viajan los xPts y los xG

COLUMNAS = ["temporada", "liga", "equipo", "pj", "pts", "xp", "xp_poisson", "gf", "gc", "xgf", "xgc",
            "pos_real", "pos_esp"]


# --- del xG de los tiros a los puntos esperados ----------------------------------------------------

def pmf_goles(xgs):
    """Distribución de los goles de un equipo: cada tiro es un Bernoulli con probabilidad `xg`, todos
    independientes. `p[k]` es la probabilidad de exactamente k goles; sin tiros, 0 goles seguro."""
    p = np.array([1.0])
    for x in xgs:
        x = min(max(float(x), 0.0), 1.0)
        p = np.convolve(p, (1.0 - x, x))
    return p


def pmf_poisson(media, kmax=KMAX_POISSON):
    """Poisson truncada en `kmax` goles (la cola, que es ínfima, se junta en el último valor para que
    sume 1)."""
    p = np.empty(kmax + 1)
    p[0] = math.exp(-media)
    for k in range(1, kmax + 1):
        p[k] = p[k - 1] * media / k
    p[kmax] += max(0.0, 1.0 - p.sum())
    return p


def probs_resultado(p_local, p_visita):
    """(gana el local, empatan, gana la visita) a partir de la distribución de goles de cada uno, con los
    dos equipos independientes."""
    n = max(len(p_local), len(p_visita))
    pl = np.pad(p_local, (0, n - len(p_local)))
    pv = np.pad(p_visita, (0, n - len(p_visita)))
    cl, cv = np.cumsum(pl), np.cumsum(pv)
    gana_l = float(np.sum(pl[1:] * cv[:-1]))
    gana_v = float(np.sum(pv[1:] * cl[:-1]))
    empate = float(np.sum(pl * pv))
    return gana_l, empate, gana_v


def puntos_esperados(gana, empata):
    """Los puntos que vale un partido para un equipo con esas probabilidades."""
    return 3.0 * gana + 1.0 * empata


def puntos_de(goles_a_favor, goles_en_contra):
    return 3 if goles_a_favor > goles_en_contra else 1 if goles_a_favor == goles_en_contra else 0


def calcular_partidos(partidos, tiros):
    """Una fila por partido con sus probabilidades por los dos métodos.

    `partidos`: `game_id, temporada, liga, local, visita, goles_l, goles_v, xg_l, xg_v` (nombres de
    Understat). `tiros`: `game_id, team, xg, result` de Understat. Columnas de salida: las del partido más
    `xg_l`/`xg_v` usados (la suma del xG de los tiros; el del partido si los tiros no cuadran), `metodo`
    (`tiros` o `partido`), `bw, bd, bl` (ganar local, empatar, ganar visita con tiros Bernoulli) y `qw, qd, ql`
    (lo mismo con Poisson sobre el xG total). `attrs["sin_tiros"]` lista los partidos que no tienen tiros y
    quedan fuera; `attrs["con_poisson"]`, los que se calculan con el xG del partido."""
    por_juego = defaultdict(dict)
    for (juego, equipo), g in tiros.groupby(["game_id", "team"], sort=False):
        por_juego[juego][equipo] = g["xg"].to_numpy(dtype=float)
    goles_tiros = (tiros[tiros["result"].isin([GOL, AUTOGOL])].groupby("game_id").size()).to_dict()

    filas, sin_tiros, con_poisson = [], [], []
    for r in partidos.itertuples(index=False):
        if r.game_id not in por_juego:
            sin_tiros.append(r)
            continue
        xl = por_juego[r.game_id].get(r.local, np.array([]))
        xv = por_juego[r.game_id].get(r.visita, np.array([]))
        cuadra = goles_tiros.get(r.game_id, 0) == r.goles_l + r.goles_v
        if cuadra:
            lam_l, lam_v = float(xl.sum()), float(xv.sum())
            b = probs_resultado(pmf_goles(xl), pmf_goles(xv))
            metodo = "tiros"
        else:
            lam_l, lam_v = float(r.xg_l), float(r.xg_v)
            b = probs_resultado(pmf_poisson(lam_l), pmf_poisson(lam_v))
            metodo = "partido"
            con_poisson.append(r)
        q = probs_resultado(pmf_poisson(lam_l), pmf_poisson(lam_v))
        filas.append((r.game_id, r.temporada, r.liga, r.local, r.visita, int(r.goles_l), int(r.goles_v),
                      lam_l, lam_v, metodo, *b, *q))
    out = pd.DataFrame(filas, columns=["game_id", "temporada", "liga", "local", "visita", "goles_l", "goles_v",
                                       "xg_l", "xg_v", "metodo", "bw", "bd", "bl", "qw", "qd", "ql"])
    out.attrs["sin_tiros"] = sin_tiros
    out.attrs["con_poisson"] = con_poisson
    return out


def _largo(juegos):
    """Un renglón por equipo y partido: sus puntos, sus xPts por los dos métodos, goles y xG a favor y en contra."""
    def lado(local):
        a, b = ("goles_l", "goles_v") if local else ("goles_v", "goles_l")
        gana, pierde = ("bw", "bl") if local else ("bl", "bw")
        gq, pq = ("qw", "ql") if local else ("ql", "qw")
        xa, xb = ("xg_l", "xg_v") if local else ("xg_v", "xg_l")
        return pd.DataFrame({
            "temporada": juegos["temporada"], "liga": juegos["liga"],
            "equipo": juegos["local" if local else "visita"].map(club_visible),
            "sede": "local" if local else "visita",
            "pts": [puntos_de(i, j) for i, j in zip(juegos[a], juegos[b])],
            "xp": puntos_esperados(juegos[gana], juegos["bd"]),
            "xp_poisson": puntos_esperados(juegos[gq], juegos["qd"]),
            "gf": juegos[a], "gc": juegos[b], "xgf": juegos[xa], "xgc": juegos[xb]})
    return pd.concat([lado(True), lado(False)], ignore_index=True)


SEDE_COLS = ["xp_local_pp", "xp_visita_pp", "pts_local_pp", "pts_visita_pp"]


def por_sede(juegos):
    """Por (temporada, liga, equipo): puntos esperados (los de la tabla, por los tiros) y puntos reales por partido de local
    y de visitante. Alimenta «Local vs. visitante» y las variables de «Tu propio gráfico»."""
    g = (_largo(juegos).groupby(["temporada", "liga", "equipo", "sede"])
         .agg(xp=("xp", "mean"), pts=("pts", "mean")).unstack("sede"))
    return pd.DataFrame({"xp_local_pp": g[("xp", "local")], "xp_visita_pp": g[("xp", "visita")],
                         "pts_local_pp": g[("pts", "local")], "pts_visita_pp": g[("pts", "visita")]})


def puntos_por_sede(tiros, temporadas):
    """`por_sede` de los partidos de `temporadas` (la `data/` del repo) con los `tiros` ya cargados."""
    archivos = sorted(p for p in DATA_DIR.glob("*/partidos.csv") if re.fullmatch(r"\d{4}-\d{2}", p.parent.name))
    partidos = pd.concat([pd.read_csv(p, encoding="utf-8-sig") for p in archivos], ignore_index=True)
    partidos = partidos[partidos["temporada"].isin(set(temporadas))].reset_index(drop=True)
    return por_sede(calcular_partidos(partidos, tiros))


def tabla_equipos(juegos):
    """Una fila por equipo, liga y temporada (columnas de `COLUMNAS`), ordenada por temporada, liga y tabla
    real. La posición real desempata por diferencia de goles y luego goles a favor; la esperada ordena por
    xPts."""
    largo = _largo(juegos)
    t = (largo.groupby(["temporada", "liga", "equipo"], sort=True)
         .agg(pj=("pts", "size"), pts=("pts", "sum"), xp=("xp", "sum"), xp_poisson=("xp_poisson", "sum"),
              gf=("gf", "sum"), gc=("gc", "sum"), xgf=("xgf", "sum"), xgc=("xgc", "sum"))
         .reset_index())
    t["dg"] = t["gf"] - t["gc"]
    clave = ["temporada", "liga"]
    real = t.sort_values(clave + ["pts", "dg", "gf", "equipo"], ascending=[True, True, False, False, False, True],
                         kind="stable")
    real["pos_real"] = real.groupby(clave).cumcount() + 1
    esp = real.sort_values(clave + ["xp", "equipo"], ascending=[True, True, False, True], kind="stable")
    esp["pos_esp"] = esp.groupby(clave).cumcount() + 1
    t = real.assign(pos_esp=esp["pos_esp"].reindex(real.index))
    return t.sort_values(clave + ["pos_real"]).reset_index(drop=True)[COLUMNAS]


def comprobar_nombres(tabla, fbref):
    """Los clubes de los partidos son los de FBref en cada liga y temporada (después de `club_visible`). Si no,
    se detiene con el detalle: así un alias que falta no deja un equipo con la mitad de sus partidos."""
    fb = fbref.assign(equipo=fbref["Squad"].map(club_visible))
    for (temporada, liga), g in fb.groupby(["temporada", "liga"]):
        mios = set(tabla.loc[(tabla["temporada"] == temporada) & (tabla["liga"] == liga), "equipo"])
        suyos = set(g["equipo"])
        if mios != suyos:
            raise ValueError(
                f"Tabla esperada: los clubes de los partidos y los de FBref no coinciden en {temporada} {liga}. "
                f"Solo en los partidos: {sorted(mios - suyos)}. Solo en FBref: {sorted(suyos - mios)}. "
                f"Se arregla en `nombres.CLUBES`.")
    ligas_t = set(zip(tabla["temporada"], tabla["liga"]))
    if ligas_t != set(zip(fb["temporada"], fb["liga"])):
        raise ValueError("Tabla esperada: las ligas y temporadas de los partidos y las de FBref no son las mismas.")


# --- validación -------------------------------------------------------------------------------------

def _corr(a, b):
    return float(np.corrcoef(a, b)[0, 1])


def metricas_partido(juegos):
    """Cómo acierta cada método el resultado de cada partido: RPS (el error del pronóstico ordenado
    ganar-empatar-perder; menos es mejor), Brier, y la probabilidad media de cada resultado contra la
    frecuencia real."""
    res = np.sign(juegos["goles_l"] - juegos["goles_v"]).to_numpy()
    salida = {"real": {"local": float((res > 0).mean()), "empate": float((res == 0).mean()),
                       "visita": float((res < 0).mean())}, "n": int(len(juegos))}
    for nombre, (w, d, l) in {"tiros": ("bw", "bd", "bl"), "poisson": ("qw", "qd", "ql")}.items():
        pw, pe, pl = (juegos[c].to_numpy() for c in (w, d, l))
        brier = ((res > 0) - pw) ** 2 + ((res == 0) - pe) ** 2 + ((res < 0) - pl) ** 2
        rps = (((pw - (res > 0)) ** 2) + ((pw + pe - (res >= 0)) ** 2)) / 2
        salida[nombre] = {"rps": float(rps.mean()), "brier": float(brier.mean()), "local": float(pw.mean()),
                          "empate": float(pe.mean()), "visita": float(pl.mean())}
    return salida


def metricas_equipos(tabla, col, cerradas):
    """Puntos reales contra la columna `col` de xPts en las temporadas cerradas: correlación por liga y
    temporada (mediana, mínima y máxima), error absoluto medio, desviación de la diferencia y cuánto suman los
    xPts de una liga y temporada contra sus puntos (mínimo, promedio y máximo)."""
    c = tabla[tabla["temporada"].isin(cerradas)]
    dif = c["pts"] - c[col]
    por = c.groupby(["temporada", "liga"])
    cors = por.apply(lambda g: _corr(g["pts"], g[col]), include_groups=False)
    tot = por[["pts", col]].sum()
    razon = tot[col] / tot["pts"]
    return {"corr_mediana": float(cors.median()), "corr_min": float(cors.min()), "corr_max": float(cors.max()),
            "mae": float(dif.abs().mean()), "sd": float(dif.std()), "media_dif": float(dif.mean()),
            "razon_min": float(razon.min()), "razon_media": float(razon.mean()), "razon_max": float(razon.max()),
            "pts_total": int(tot["pts"].sum()), "xp_total": float(tot[col].sum()),
            "n_ligas_temporadas": int(len(tot)), "n_equipos": int(len(c))}


def persistencia(tabla, col, cerradas):
    """Cuánto de (puntos − xPts) se repite de una temporada cerrada a la siguiente del mismo club: la
    correlación de esa diferencia entre las dos, con su intervalo aproximado (Fisher). También, para
    comparar, cuánto predicen los puntos y los xPts de un año los puntos del siguiente."""
    c = tabla[tabla["temporada"].isin(cerradas)].copy()
    c["res"] = c["pts"] - c[col]
    # Todo por partido: así 34 y 38 jornadas (y un equipo al que le falta un partido) entran en la misma escala.
    c["res_pp"] = c["res"] / c["pj"]
    c["ppp"] = c["pts"] / c["pj"]
    c["xpp"] = c[col] / c["pj"]
    c["año"] = c["temporada"].str[:4].astype(int)
    sig = c[["año", "equipo", "res_pp", "ppp", "xpp"]].copy()
    sig["año"] -= 1
    m = c.merge(sig, on=["año", "equipo"], suffixes=("", "_sig"))
    n = int(len(m))
    r = _corr(m["res_pp"], m["res_pp_sig"])
    z, se = math.atanh(min(max(r, -0.999999), 0.999999)), 1.0 / math.sqrt(n - 3)
    return {"r": r, "n": n, "lo": math.tanh(z - 1.96 * se), "hi": math.tanh(z + 1.96 * se),
            "r_pts_pts": _corr(m["ppp"], m["ppp_sig"]), "r_xp_pts": _corr(m["xpp"], m["ppp_sig"]),
            "transiciones": int(m[["año"]].drop_duplicates().shape[0])}


def validar(tabla, juegos, cerradas):
    """Todas las cifras de validación, para los dos métodos."""
    return {"partidos": metricas_partido(juegos),
            "tiros": {"equipos": metricas_equipos(tabla, "xp", cerradas), "persistencia": persistencia(tabla, "xp", cerradas)},
            "poisson": {"equipos": metricas_equipos(tabla, "xp_poisson", cerradas),
                        "persistencia": persistencia(tabla, "xp_poisson", cerradas)}}


# --- carga -----------------------------------------------------------------------------------------

def _cargar():
    """(partidos, tiros, FBref) de las temporadas que tienen tabla de equipos."""
    fbref = pd.read_csv(PROCESSED_DIR / "teams_all_seasons.csv", usecols=["temporada", "liga", "Squad", COL_PARTIDOS_FBREF, COL_PPM])
    temporadas = set(fbref["temporada"])
    archivos = sorted(p for p in DATA_DIR.glob("*/partidos.csv") if re.fullmatch(r"\d{4}-\d{2}", p.parent.name))
    partidos = pd.concat([pd.read_csv(p, encoding="utf-8-sig") for p in archivos], ignore_index=True)
    partidos = partidos[partidos["temporada"].isin(temporadas)].reset_index(drop=True)
    tiros = pd.read_csv(PROCESSED_DIR / "shots_all_seasons.csv", usecols=COLS_TIROS, encoding="utf-8-sig",
                        keep_default_na=False, na_values=[""])
    return partidos, tiros, fbref


def calcular(partidos, tiros, fbref, en_curso=None):
    """Todo el cálculo de la vista (los tests lo llaman con datos sintéticos)."""
    en_curso = dict(en_curso if en_curso is not None else temporadas_en_curso())
    juegos = calcular_partidos(partidos, tiros)
    tabla = tabla_equipos(juegos)
    comprobar_nombres(tabla, fbref)
    temporadas = sorted(tabla["temporada"].unique())
    en_curso = {t: n for t, n in en_curso.items() if t in temporadas}
    cerradas = [t for t in temporadas if t not in en_curso]
    de_cerradas = set(juegos.loc[juegos["temporada"].isin(cerradas), "game_id"])
    autogoles = int(((tiros["result"] == AUTOGOL) & tiros["game_id"].isin(de_cerradas)).sum())
    return {"juegos": juegos, "tabla": tabla, "temporadas": temporadas, "en_curso": en_curso, "cerradas": cerradas,
            "validacion": validar(tabla, juegos[juegos["temporada"].isin(cerradas)], cerradas),
            "autogoles_por_equipo": autogoles / max(1, int(tabla["temporada"].isin(cerradas).sum())),
            "goles_entre_xg": _goles_entre_xg(juegos, cerradas),
            "discrepancias_fbref": discrepancias_fbref(tabla, fbref, cerradas)}


def discrepancias_fbref(tabla, fbref, cerradas):
    """Equipos y temporadas cerradas cuyos puntos (de los marcadores de Understat) no son los de FBref (puntos por partido
    por partidos, redondeado): `(cuántos, diferencia máxima en puntos, cuántos equipos-temporada se comparan)`. Un marcador
    mal capturado en alguno de los dos lados, o el partido que se quitó por no tener tiros."""
    if COL_PPM not in fbref.columns:
        return None
    fb = fbref.assign(equipo=fbref["Squad"].map(club_visible),
                      pts_fb=(fbref[COL_PPM] * fbref[COL_PARTIDOS_FBREF]).round())
    m = tabla[tabla["temporada"].isin(cerradas)].merge(fb[["temporada", "liga", "equipo", "pts_fb"]],
                                                       on=["temporada", "liga", "equipo"])
    d = (m["pts"] - m["pts_fb"]).abs()
    return int((d > 0).sum()), int(d.max()), int(len(m))


def _goles_entre_xg(juegos, cerradas):
    """Goles reales entre xG total de las temporadas cerradas (Understat suma más xG del que entra)."""
    j = juegos[juegos["temporada"].isin(cerradas)]
    return float((j["goles_l"] + j["goles_v"]).sum() / (j["xg_l"] + j["xg_v"]).sum())


# --- lo que viaja y los textos ----------------------------------------------------------------------

def payload(r):
    """La tabla por equipo y temporada, en columnas. Los xPts y el xG con `DECIMALES`."""
    t = r["tabla"]
    nombres, idx = pd.factorize(t["equipo"])
    v = r["validacion"]
    ligas = [l for l in LEAGUE_ORDER if l in set(t["liga"])]
    return {
        "entidad": SLUG,
        "ligas": ligas,
        "temporadas": r["temporadas"],
        "enCurso": r["en_curso"],
        "nombres": [str(n) for n in idx],
        "divergente": dict(DIVERGING),
        "errorMedio": round(v["tiros"]["equipos"]["mae"], 4),
        "persistencia": {k: round(x, 4) if isinstance(x, float) else x for k, x in v["tiros"]["persistencia"].items()},
        "f": {
            "l": [ligas.index(x) for x in t["liga"]],
            "t": [r["temporadas"].index(x) for x in t["temporada"]],
            "e": [int(i) for i in nombres],
            "pj": [int(x) for x in t["pj"]],
            "pts": [int(x) for x in t["pts"]],
            "xp": [round(float(x), DECIMALES) for x in t["xp"]],
            "gf": [int(x) for x in t["gf"]],
            "gc": [int(x) for x in t["gc"]],
            "xgf": [round(float(x), DECIMALES) for x in t["xgf"]],
            "xgc": [round(float(x), DECIMALES) for x in t["xgc"]],
            "pr": [int(x) for x in t["pos_real"]],
            "pe": [int(x) for x in t["pos_esp"]],
        },
    }


def _n(n):
    return f"{int(n):,}"


def _f(x, d=2):
    return f"{x:.{d}f}".replace("-", "−")


def _pct(x, d=1):
    return f"{100 * x:.{d}f}%"


def _cuanto(r):
    """Misma regla que `tablaEsperadaLectura.js`: cuánto se repite, según el tamaño de la correlación."""
    a = abs(r)
    return "casi nada" if a < 0.2 else "algo" if a < 0.4 else "bastante"


def _partido(r):
    return f"{club_visible(r.local)} contra {club_visible(r.visita)}, {r.temporada}"


def textos(r):
    """(qué más mirar, por qué así): los textos fijos de la vista. Cada cifra sale de los datos calculados o de
    las constantes de este módulo; no hay números escritos a mano."""
    v = r["validacion"]
    vt, vp = v["tiros"], v["poisson"]
    et, ep = vt["equipos"], vp["equipos"]
    pt, pp = vt["persistencia"], vp["persistencia"]
    mp = v["partidos"]
    juegos = r["juegos"]
    sin_tiros = juegos.attrs["sin_tiros"]
    n_tot = len(juegos) + len(sin_tiros)
    ts = r["cerradas"]
    en_curso = r["en_curso"]
    pj = r["tabla"].groupby("temporada")["pj"].agg(["min", "max"])
    que_mirar = (
        "Compara los puntos reales de cada equipo con los que valían sus ocasiones, partido a partido (xPts). "
        "El punto relleno son los puntos reales y el anillo, los esperados, y la línea que los une es la "
        "diferencia.\n"
        "La línea va en azul si el equipo sumó más de lo esperado y en rojo si sumó menos. A la derecha "
        "aparece el lugar que ocuparía en la tabla por xPts y cuántos lugares está por encima (+) o por "
        "debajo (−).")


    ausentes = ""
    if sin_tiros:
        ausentes = (f" Hay {_n(len(sin_tiros))} partido{'s' if len(sin_tiros) != 1 else ''} de {_n(n_tot)} sin un solo tiro "
                    f"en Understat ({', '.join(_partido(x) for x in sin_tiros)}) y no entra{'n' if len(sin_tiros) != 1 else ''} "
                    f"en ningún total.")
    d = r.get("discrepancias_fbref")
    fbref = ""
    if d and d[0]:
        fbref = (f" Los puntos coinciden con los de FBref salvo en {_n(d[0])} de {_n(d[2])} equipos-temporada (por "
                 f"{_n(d[1])} punto{'s' if d[1] != 1 else ''} como máximo).")
    cola_curso = ""
    if en_curso:
        txt = ", ".join(f"{t} (de {int(pj.loc[t, 'min'])} a {int(pj.loc[t, 'max'])} partidos por equipo)" for t in en_curso)
        cola_curso = (f"\n\n**La temporada en curso.** {txt}: la diferencia es sobre todo azar y la muestra es mínima. Se "
                      f"dibuja en gris y los textos no concluyen nada de ella.")
    por_que = (
        "**Qué son los xPts.** Para cada partido, cada tiro es una moneda cargada que cae gol con la probabilidad de su xG. "
        "De ahí sale la probabilidad de cada marcador y, sumando, la de ganar, empatar y perder. Los xPts del partido son 3 "
        "por la probabilidad de ganar más 1 por la de empatar; los del equipo, la suma de sus partidos. No son los puntos "
        "que «merecía»: son los que sumaría, en promedio, si ese partido se repitiera muchas veces con esas ocasiones.\n\n"
        "**Penales y autogoles.** Los penales entran como un tiro más con su xG, porque los puntos reales también los "
        "llevan (las demás vistas de Equipos los miran sin penales). Los autogoles no tienen xG: no suman a los esperados, "
        "pero sí a los puntos reales.\n\n"
        f"**Por qué tiros y no Poisson.** La alternativa común es tomar el xG total del partido como la media de una "
        f"Poisson. Por partido casi no se distinguen (RPS {_f(mp['tiros']['rps'], 4)} con tiros y "
        f"{_f(mp['poisson']['rps'], 4)} con Poisson, en {_n(mp['n'])} partidos), pero por temporada los puntos reales se "
        f"alejan {_f(et['mae'], 1)} puntos de los xPts con tiros y {_f(ep['mae'], 1)} con Poisson. Se usa la de tiros.\n\n"
        f"**Qué tan bien coinciden.** En las {_n(et['n_ligas_temporadas'])} ligas y temporadas cerradas, puntos reales y "
        f"xPts correlacionan entre {_f(et['corr_min'])} y {_f(et['corr_max'])} (mediana {_f(et['corr_mediana'])}). Los xPts "
        f"suman entre {_f(et['razon_min'], 3)} y {_f(et['razon_max'], 3)} veces los puntos reales, porque el xG de "
        f"Understat suma {'más' if r['goles_entre_xg'] < 1 else 'menos'} de lo que entra y hay más empates reales que en el "
        f"modelo: el cero de la diferencia no es el promedio de la liga.\n\n"
        f"**Cuánto se repite.** Entre temporadas cerradas consecutivas del mismo club ({_n(pt['n'])} pares), la diferencia "
        f"(puntos − xPts) por partido correlaciona {_f(pt['r'])}: se repite {_cuanto(pt['r'])}. Los puntos por partido "
        f"correlacionan {_f(pt['r_pts_pts'])} con los del año siguiente y los xPts, {_f(pt['r_xp_pts'])}.\n\n"
        f"**Qué no ve.** Un partido no es una muestra, y 34 o 38 tampoco quitan el azar. El xG no sabe de las expulsiones "
        f"ni del marcador, ni distingue al portero o al delantero muy bueno o muy malo. Los puntos salen de los marcadores, "
        f"sin sanciones, y la posición desempata por diferencia de goles, así que puede no coincidir con la tabla "
        f"oficial.{ausentes}{fbref}{cola_curso}")
    return que_mirar, por_que


def chart_tabla_esperada() -> ChartPage:
    partidos, tiros, fbref = _cargar()
    r = calcular(partidos, tiros, fbref)
    react_views.registrar_payload(SLUG, payload(r))
    que_mirar, _ = textos(r)
    assert len(BAJADA) <= 108, f"{SLUG}: la bajada mide {len(BAJADA)} caracteres"
    ligas = [l for l in LEAGUE_ORDER if l in set(r["tabla"]["liga"])]
    cfg = {
        "id": SLUG, "titulo": TITULO, "bajada": BAJADA, "pregunta": PREGUNTAS[SLUG], "tabla": SLUG,
        "queMirar": que_mirar, "fuente": FUENTE_UNDERSTAT,
        "ligas": ligas, "ligaInicial": "Premier League" if "Premier League" in ligas else ligas[0],
        "temporadaInicial": r["cerradas"][-1] if r["cerradas"] else r["temporadas"][-1],
    }
    return ChartPage(slug=SLUG, section=SECTION, title=TITULO, subtitle=BAJADA,
                     body_html=react_views.montar_html("tabla_esperada", SLUG, cfg, alto_min=640), kind="line")
