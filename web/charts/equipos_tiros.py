"""Cuatro columnas más por equipo y temporada, de los tiros y los partidos de Understat: cuántos tiros dispara
y qué tan buenos son (`tiros_pp`, `xg_tiro`) y cómo le va de local y de visitante (`xg_dif_local`,
`xg_dif_visita`). Alimentan las vistas «Cantidad vs. calidad de los tiros» y «Local vs. visitante».

Misma convención que `xg_equipos.py`, y se apoya en él para los cruces de nombres y los huecos de Understat:

- **Sin penales** (`situation == "Penalty"`) y **sin autogoles** (`result == "Own Goal"`, que no son un tiro:
  traen xG 0 y no salen de ninguna ocasión del equipo).
- **Por partido**, sobre los partidos que Understat trae de ese equipo (`xg_partidos` de `xg_equipos`), para que
  numerador y denominador cubran los mismos partidos.
- Los nombres de los clubes se pasan por `nombres.club_visible`; `xg_equipos._con_rival` valida que los clubes de
  los tiros y los de FBref son los mismos (y rellena el `rival` que Understat deja vacío en 4 partidos).

**Tiros por partido y xG por tiro.** `tiros_pp` es el número de tiros (con xG, sin penales) entre los partidos del
equipo; `xg_tiro` es su xG sin penales entre esos mismos tiros. Si el equipo no tiró nunca, `xg_tiro` queda sin dato.

**Local y visitante.** El partido se identifica por `game_id` y los dos equipos salen de `partidos.csv` (`local` y
`visita`): el xG A FAVOR de un equipo es el de sus tiros en ese `game_id` y el xG EN CONTRA, el de los tiros del
otro. Así el rival no hace falta. Si en un partido solo hay tiros de uno de los dos (4 casos), el otro queda con
xG 0, igual que en `xg_equipos`. Un partido sin ningún tiro en Understat no se cuenta ni de local ni de visitante
(no se inventa un 0). `xg_dif_local` y `xg_dif_visita` son el promedio por partido de (xG a favor − xG en contra)
en los partidos de cada sede. Un equipo sin partidos de una sede (puede pasar en la temporada que va en curso)
queda sin dato en esa columna y la fila no se dibuja.
"""

import numpy as np
import pandas as pd

import xg_equipos as xe
from nombres import club_visible

TIROS_PP, XG_TIRO = "tiros_pp", "xg_tiro"
DIF_LOCAL, DIF_VISITA = "xg_dif_local", "xg_dif_visita"
PARTIDOS_LOCAL, PARTIDOS_VISITA = "partidos_local", "partidos_visita"
COLUMNAS = [TIROS_PP, XG_TIRO, DIF_LOCAL, DIF_VISITA]
# Las que se calculan pero no viajan como variable (cuántos partidos hay detrás de cada diferencia).
EXTRAS = [PARTIDOS_LOCAL, PARTIDOS_VISITA]
COLS_PARTIDOS = ["temporada", "liga", "game_id", "fecha", "local", "visita"]
AUTOGOL = "Own Goal"


def cargar_partidos(carpeta, temporadas):
    """`partidos.csv` de cada temporada de `temporadas` bajo `carpeta` (la `data/` del repo), juntos."""
    return pd.concat([pd.read_csv(carpeta / t / "partidos.csv", usecols=COLS_PARTIDOS, encoding="utf-8-sig")
                      for t in temporadas], ignore_index=True)


def _tiros_por_equipo(t):
    """Tiros (sin penales ni autogoles) y su xG por (temporada, liga, equipo), y los partidos de Understat."""
    sp = t[(t["situation"] != xe.PENAL) & (t["result"] != AUTOGOL)]
    g = sp.groupby(["temporada", "liga", "equipo"]).agg(tiros=("xg", "size"), xg=("xg", "sum"))
    return g.join(xe._partidos_con_tiros(t).rename("partidos"), how="outer")


def _partidos_de_equipos(partidos, equipos_e):
    """`partidos` con los nombres cruzados, solo las temporadas de `equipos_e`; se detiene si los clubes de un
    lado y otro no son los mismos (un alias que falta dejaría a un equipo con la mitad de sus partidos)."""
    p = partidos[partidos["temporada"].isin(set(equipos_e["temporada"]))].copy()
    p["local_v"] = p["local"].map(club_visible)
    p["visita_v"] = p["visita"].map(club_visible)
    for (temporada, liga), g in equipos_e.groupby(["temporada", "liga"]):
        d = p[(p["temporada"] == temporada) & (p["liga"] == liga)]
        mios, suyos = set(d["local_v"]) | set(d["visita_v"]), set(g["equipo"])
        if mios != suyos:
            raise ValueError(
                f"Equipos (local y visitante): los clubes de partidos.csv y los de FBref no coinciden en "
                f"{temporada} {liga}. Solo en los partidos: {sorted(mios - suyos)}. Solo en FBref: "
                f"{sorted(suyos - mios)}. Se arregla en `nombres.CLUBES`.")
    return p


def _por_sede(t, p):
    """Por (temporada, liga, equipo): partidos y diferencia de xG por partido de local y de visitante."""
    sp = t[t["situation"] != xe.PENAL]
    xg = sp.groupby(["game_id", "equipo"])["xg"].sum().to_dict()
    con_tiros = set(t["game_id"])
    filas = []
    for r in p.itertuples(index=False):
        if r.game_id not in con_tiros:        # Understat no trae ni un tiro: sin dato, no un 0
            continue
        xl, xv = xg.get((r.game_id, r.local_v), 0.0), xg.get((r.game_id, r.visita_v), 0.0)
        filas.append((r.temporada, r.liga, r.local_v, "local", xl - xv))
        filas.append((r.temporada, r.liga, r.visita_v, "visita", xv - xl))
    d = pd.DataFrame(filas, columns=["temporada", "liga", "equipo", "sede", "dif"])
    g = d.groupby(["temporada", "liga", "equipo", "sede"])["dif"].agg(["mean", "size"]).unstack("sede")
    g = g.reindex(columns=pd.MultiIndex.from_product([["mean", "size"], ["local", "visita"]]))
    return pd.DataFrame({DIF_LOCAL: g[("mean", "local")], DIF_VISITA: g[("mean", "visita")],
                         PARTIDOS_LOCAL: g[("size", "local")], PARTIDOS_VISITA: g[("size", "visita")]})


def agregar(tiros, equipos, partidos):
    """`equipos` (la tabla de FBref: `temporada`, `liga`, `Squad` y `ov_Playing Time_MP`) con las columnas de
    `COLUMNAS` y `EXTRAS`, en el mismo orden de filas. `tiros` y `partidos` como los cargan
    `xg_equipos.cargar_tiros` y `cargar_partidos`."""
    t, e = xe._con_rival(tiros, equipos)
    clave = ["temporada", "liga", "equipo"]
    por_equipo = _tiros_por_equipo(t)
    sede = _por_sede(t, _partidos_de_equipos(partidos, e))
    out = e.join(por_equipo, on=clave).join(sede, on=clave)
    if out["partidos"].isna().any():
        raise ValueError("Equipos (tiros): hay clubes sin ningún partido en los tiros.")
    out[TIROS_PP] = out["tiros"].fillna(0) / out["partidos"]
    out[XG_TIRO] = (out["xg"] / out["tiros"]).where(out["tiros"] > 0, np.nan)
    return out[COLUMNAS + EXTRAS]
