"""Los datos del análisis exploratorio del artículo de xG: lo que se mira ANTES de modelar.

Solo cuentas sobre los tiros (sin penales, autogoles ni remates a menos de 2° de portería, el mismo
conjunto con el que se entrena). No entrena nada: se recalcula en cada construcción en unos segundos
y no necesita caché.
"""

import numpy as np
import pandas as pd

import xg_modelo as xm

LIGAS = ["Premier League", "La Liga", "Serie A", "Bundesliga", "Ligue 1"]


def _wilson(k, n, z=1.96):
    """Intervalo de Wilson de una proporción: sirve con pocos tiros y tasas cerca de cero."""
    k, n = np.asarray(k, float), np.asarray(n, float)
    p = k / np.maximum(n, 1)
    den = 1 + z ** 2 / n
    c = (p + z ** 2 / (2 * n)) / den
    h = z * np.sqrt(p * (1 - p) / n + z ** 2 / (4 * n ** 2)) / den
    return c - h, c + h


def _mapa(s):
    """Rejilla de la media cancha de ataque: tiros, tasa de gol y xG de Understat por celda. Es la
    misma rejilla del mapa de valor del modelo (`xg_modelo._aprendio`), para que se lean igual."""
    nx, ny = 40, 32
    xmin, xmax, ymin, ymax = 0.55, 0.995, 0.06, 0.94
    bx = np.linspace(xmin, xmax, nx + 1)
    by = np.linspace(ymin, ymax, ny + 1)
    # las celdas son centradas en las marcas de la rejilla del modelo
    px = (xmax - xmin) / (nx - 1)
    py = (ymax - ymin) / (ny - 1)
    bx = np.r_[np.linspace(xmin, xmax, nx) - px / 2, xmax + px / 2]
    by = np.r_[np.linspace(ymin, ymax, ny) - py / 2, ymax + py / 2]
    n, _, _ = np.histogram2d(s.location_y, s.location_x, bins=[by, bx])
    g, _, _ = np.histogram2d(s.location_y, s.location_x, bins=[by, bx], weights=s.gol)
    u, _, _ = np.histogram2d(s.location_y, s.location_x, bins=[by, bx], weights=s.xg)
    minimo = 25
    with np.errstate(invalid="ignore", divide="ignore"):
        tasa = np.where(n >= minimo, g / n, np.nan)
        xg_und = np.where(n >= minimo, u / n, np.nan)

    def lista(a, dec):
        return [None if np.isnan(v) else round(float(v), dec) for v in a.ravel()]
    return {"nx": nx, "ny": ny, "xmin": xmin, "xmax": xmax, "ymin": ymin, "ymax": ymax,
            "largo": xm.LARGO, "ancho": xm.ANCHO, "minimo": minimo,
            "metricas": {"tiros": [int(v) for v in n.ravel()], "tasa": lista(tasa, 4), "xg_und": lista(xg_und, 4)}}


def _bandas(s):
    """Tasa de gol por zonas alrededor de la portería: franjas de distancia y de ángulo, de todos los tiros
    y de los de pie y los de cabeza por separado. Son las zonas que el mapa dibuja sobre la cancha."""
    ang = np.degrees(s.angulo.values)
    grupos = {"todos": np.ones(len(s), bool), "cabeza": (s.body_part == "Head").values,
              "pie": s.body_part.isin(["Right Foot", "Left Foot"]).values}
    gol = s.gol.values

    def zonas(valor, bordes, tope):
        out = []
        for d, h in zip(bordes[:-1], bordes[1:]):
            dentro = (valor >= d) & (valor < h)
            b = {"desde": d, "hasta": min(h, tope)}
            for gid, g in grupos.items():
                k = dentro & g
                n = int(k.sum())
                b[gid] = {"n": n, "tasa": float(gol[k].mean()) if n else 0.0}
            out.append(b)
        return out
    return {"distancia": zonas(s.dist.values, [0, 5, 10, 15, 20, 25, 30, 1000], 60),
            "angulo": zonas(ang, [0, 10, 20, 30, 45, 1000], 180)}


def _tasas(s):
    """Tasa de gol por categoría: cuerpo, situación y acción previa."""
    def tabla(col, orden=None, minimo=1000):
        g = s.groupby(col).agg(n=("gol", "size"), gol=("gol", "sum"), dist=("dist", "mean"), xg=("xg", "mean"))
        g = g[g.n >= minimo]
        g["tasa"] = g.gol / g.n * 100
        return g
    return {"cuerpo": tabla("body_part", minimo=50), "situacion": tabla("situation", minimo=50),
            "accion": tabla("accion", minimo=1000)}


def _por_temporada(s):
    """Goles por tiro y xG medio de Understat por tiro, por temporada: lo que entra y lo que predice."""
    t = s.groupby("temporada").agg(n=("gol", "size"), gol=("gol", "sum"), xg=("xg", "sum"), juegos=("game_id", "nunique"))
    return {"temporadas": list(t.index),
            "tiros": [int(v) for v in t.n], "goles": [int(v) for v in t.gol],
            "gol_por_tiro": [round(float(v), 5) for v in (t.gol / t.n)],
            "xg_und_por_tiro": [round(float(v), 5) for v in (t.xg / t.n)],
            "tiros_por_partido": [round(float(v), 2) for v in (t.n / t.juegos)]}


def _por_minuto(s):
    m = s.minute.clip(upper=95)
    cubos = (m // 5).astype(int)
    g = s.groupby(cubos).agg(n=("gol", "size"), gol=("gol", "sum"))
    return [[int(i) * 5 + 2.5, round(float(r.gol / r.n * 100), 3), int(r.n)] for i, r in g.iterrows() if r.n >= 500]


def calcular():
    cerradas, historicas = xm.temporadas_disponibles()
    s, meta = xm._armar(cerradas, historicas)
    por_temporada_liga = s.groupby(["temporada", "liga"]).size().unstack("liga")[LIGAS]
    return {
        "n": int(len(s)), "goles": int(s.gol.sum()), "temporadas": sorted(s.temporada.unique()),
        "partidos": int(s.game_id.nunique()), "jugadores": int(s.player_id.nunique()), "meta": meta,
        "tiros_por_temporada": {t: {lg: int(por_temporada_liga.loc[t, lg]) for lg in LIGAS}
                                for t in por_temporada_liga.index},
        "mapa": _mapa(s), "bandas": _bandas(s),
        "tasas": {k: v.reset_index().to_dict("records") for k, v in _tasas(s).items()},
        "temporada": _por_temporada(s), "minuto": _por_minuto(s),
        "raw": {"filas": int(meta["n_total"]), "penales": meta["penales"], "olimpicos": meta["olimpicos"]},
    }
