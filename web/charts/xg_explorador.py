"""Las tablas del explorador de tiros: una por temporada cerrada, en columnas de enteros.

Cada tiro lleva su posición, el xG de Understat, el de mi modelo (el de `xg_temporadas.py`, de un
modelo que NO había visto esa temporada), el resultado y lo que hace falta para contarlo: quién,
contra quién, cuándo, cómo. Incluye los penales (con la tasa de conversión de las cuatro temporadas
anteriores como xG propio, porque el modelo no los modela) y deja fuera autogoles y los remates a
menos de 2° de portería, que tampoco entran al modelo.

Los enteros son para pesar poco: posición en milésimas de cancha, xG en diezmilésimas.
"""

import numpy as np
import pandas as pd

import react_views
import xg_modelo as xm
import xg_temporadas as xt

SITUACIONES = ["Open Play", "From Corner", "Set Piece", "Direct Freekick", "Penalty"]
PARTES = ["Right Foot", "Left Foot", "Head", "Other"]
RESULTADOS = ["Goal", "Saved Shot", "Missed Shot", "Blocked Shot", "Shot On Post"]
ACCIONES = xm.ACCIONES + ["Otra"]
ORIGEN = pd.Timestamp("2021-07-01")
LIGAS = ["Premier League", "La Liga", "Serie A", "Bundesliga", "Ligue 1"]


def _tasa_penales():
    """Conversión de los penales, por temporada, con la que se estima el de la siguiente."""
    temps = xm.HISTORICAS + xm.CERRADAS
    out = {}
    for t in temps:
        d = pd.read_csv(xm.DATA_DIR / t / "shots.csv", encoding="utf-8-sig", usecols=["situation", "result"])
        d = d[d.situation == "Penalty"]
        out[t] = (int((d.result == "Goal").sum()), int(len(d)))
    return out, temps


def tablas(temporadas=None):
    temporadas = temporadas or xm.CERRADAS
    pred = xt.predicciones().drop_duplicates("shot_id").set_index("shot_id")["p"]
    pen, temps = _tasa_penales()
    salida = {}
    for t in temporadas:
        i = temps.index(t)
        previas = temps[max(0, i - 4):i]
        g = sum(pen[x][0] for x in previas)
        n = sum(pen[x][1] for x in previas)
        tasa_pen = g / n
        s = xm._cargar([t])
        s = s[s.result != "Own Goal"].drop_duplicates("shot_id").reset_index(drop=True)
        p = s.shot_id.map(pred)
        es_pen = s.situation == "Penalty"
        p = p.where(~es_pen, tasa_pen)
        s = s[p.notna()].copy()
        s["p"] = p[p.notna()].values
        jug, jug_nombres = pd.factorize(pd.concat([s.player, s.assist_player]).dropna())
        jug_idx = {n_: k for k, n_ in enumerate(jug_nombres)}
        eq_nombres = sorted(set(s.team) | set(s.rival))
        eq_idx = {n_: k for k, n_ in enumerate(eq_nombres)}
        accion = s.last_action.where(s.last_action.isin(xm.ACCIONES), "Otra")
        c = {
            "x": np.round(s.location_x.values * 1000).astype(int).tolist(),
            "y": np.round(s.location_y.values * 1000).astype(int).tolist(),
            "me": np.round(s.p.values * 10000).astype(int).tolist(),
            "us": np.round(s.xg.values * 10000).astype(int).tolist(),
            "r": [RESULTADOS.index(v) for v in s.result],
            "m": s.minute.astype(int).tolist(),
            "j": [jug_idx[v] for v in s.player],
            "q": [jug_idx[v] if isinstance(v, str) else -1 for v in s.assist_player],
            "e": [eq_idx[v] for v in s.team],
            "v": [eq_idx[v] for v in s.rival],
            "h": s.es_local.astype(int).tolist(),
            "l": [LIGAS.index(v) for v in s.liga],
            "s": [SITUACIONES.index(v) for v in s.situation],
            "p": [PARTES.index(v) for v in s.body_part],
            "a": [ACCIONES.index(v) for v in accion],
            "d": (s.fecha.dt.normalize() - ORIGEN).dt.days.astype(int).tolist(),
        }
        payload = {"t": t, "n": int(len(s)), "jug": [str(v) for v in jug_nombres], "eq": eq_nombres, "c": c}
        react_views.registrar_payload(f"xgtiros-{t}", payload)
        salida[t] = {"n": int(len(s)), "penal": tasa_pen}
    return salida
