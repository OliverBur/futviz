"""xG y goles de cada equipo por partido, sin penales, a partir de los tiros de Understat.

Las vistas de Equipos usaban proxies de FBref (tiros a puerta, asistencias) que miden mal lo que
dicen medir: el azar explica ~70-90% de la dispersión de los goles por tiro a puerta entre equipos, y
las asistencias son el gol con otra etiqueta. Con los tiros de Understat (`shots_all_seasons.csv`, uno
por remate con su xG) se puede medir lo que sí interesa: cuántas ocasiones crea y cuántas concede cada
equipo, y cuántos goles le salen y le entran contra eso.

Todo va **sin penales** (`situation == "Penalty"`): un penal vale ~0.78 de xG y casi siempre lo decide
una acción, no el juego, así que meterlo mueve a los equipos que los cobran por razones que no son las
de estas gráficas. Y **sin autogoles** (`result == "Own Goal"`, con xG 0): no salen de ninguna ocasión
del equipo. Son ~1.3 por equipo y temporada.

**Cruce de nombres.** Understat y FBref escriben distinto a los clubes («Wolverhampton Wanderers» y
«Wolves»), y FBref les cambia el nombre de una temporada a otra («PSG» y luego «Paris SG»). El puente es
`nombres.club_visible`, el diccionario que el sitio ya usa para mostrar los nombres: los dos lados se
pasan por él y se cruzan por el resultado. Si a un club de un lado le falta pareja en el otro, o sobra
uno, la función se detiene con el detalle en vez de dejar nulos callados.

**Partidos.** El xG por partido divide entre los partidos que Understat trae de ese equipo (no entre los
`ov_Playing Time_MP` de FBref), para que el numerador y el denominador cubran los mismos partidos. Los
dos conteos coinciden salvo en unos pocos equipos-temporada (a Understat le falta o le sobra un partido;
el detalle lo imprime `web/tests/test_xg_equipos.py`).

**Partidos de un solo equipo.** En 4 de los 9,252 partidos Understat no trae ni un tiro de uno de los
dos equipos y deja `rival` vacío en los del otro. Esos tiros cuentan como xG A FAVOR del que tiró; para
el xG EN CONTRA hay que saber a quién se lo hicieron. Se deduce: es el único equipo de esa liga y
temporada al que le falta un partido en los tiros frente a sus partidos de FBref **y** que no jugó
otro partido ese día. En los cuatro casos queda uno solo (Genoa, Werder Bremen, Real Sociedad y Pisa).
Si no queda exactamente uno, se detiene.
"""

import pandas as pd

from nombres import club_visible

COLS_TIROS = ["temporada", "liga", "game_id", "date", "team", "rival", "xg", "situation", "result"]
PENAL, GOL = "Penalty", "Goal"
COL_PARTIDOS = "ov_Playing Time_MP"

# Lo que se agrega a la tabla de equipos: por partido y sin penales (`xg_dif` es a favor menos en contra)
# y los partidos de Understat sobre los que se divide.
COLUMNAS = ["xg_fav", "xg_con", "gol_fav", "gol_con", "xg_dif", "xg_partidos"]


def cargar_tiros(ruta):
    """Los tiros con solo lo que hace falta. Los vacíos se leen como nulo y nada más: `rival` queda
    vacío en los partidos de un solo equipo con tiros, y "NA" no es un club."""
    return pd.read_csv(ruta, usecols=COLS_TIROS, encoding="utf-8-sig", keep_default_na=False,
                       na_values=[""])


def _preparar(tiros, equipos):
    """Los tiros y los equipos con el nombre ya cruzado (`equipo`, `rival_v`), y las dos validaciones de
    que los clubes de un lado y otro son los mismos en cada liga y temporada."""
    t = tiros[COLS_TIROS].copy()
    t["equipo"] = t["team"].map(club_visible)
    t["rival_v"] = t["rival"].map(lambda n: club_visible(n) if isinstance(n, str) else None)
    t["dia"] = t["date"].astype(str).str[:10]
    e = equipos[["temporada", "liga", "Squad", COL_PARTIDOS]].copy()
    e["equipo"] = e["Squad"].map(club_visible)
    if e.duplicated(["temporada", "liga", "equipo"]).any():
        raise ValueError("xG de equipos: dos clubes de FBref quedan con el mismo nombre.")
    for (temporada, liga), g in e.groupby(["temporada", "liga"]):
        d = t[(t["temporada"] == temporada) & (t["liga"] == liga)]
        us = set(d["equipo"]) | set(d["rival_v"].dropna())
        fb = set(g["equipo"])
        if us != fb:
            raise ValueError(
                f"xG de equipos: los clubes de Understat y de FBref no coinciden en {temporada} {liga}. "
                f"Solo en Understat: {sorted(us - fb)}. Solo en FBref: {sorted(fb - us)}. "
                f"Se arregla en `nombres.CLUBES`.")
    return t, e


def _partidos_con_tiros(t):
    """Cuántos partidos distintos tiene cada (temporada, liga, equipo) en los tiros, como tirador o como
    rival. Un partido en el que el equipo no tiró y el rival quedó sin nombre no cuenta."""
    a = t[["temporada", "liga", "equipo", "game_id"]]
    b = (t.loc[t["rival_v"].notna(), ["temporada", "liga", "rival_v", "game_id"]]
         .rename(columns={"rival_v": "equipo"}))
    return pd.concat([a, b]).drop_duplicates().groupby(["temporada", "liga", "equipo"]).size()


def _rellenar_rival(t, jugados):
    """Pone el rival en los tiros que no lo traen (ver el docstring del módulo). `jugados` son los
    partidos de FBref por (temporada, liga, equipo)."""
    sin = t["rival_v"].isna()
    if not sin.any():
        return t
    falta = (jugados - _partidos_con_tiros(t).reindex(jugados.index).fillna(0)).loc[lambda s: s > 0]
    t = t.copy()
    for (temporada, liga, game_id), g in t[sin].groupby(["temporada", "liga", "game_id"]):
        tirador, dia = g["equipo"].iloc[0], g["dia"].iloc[0]
        otros = t[(t["temporada"] == temporada) & (t["liga"] == liga) & (t["dia"] == dia)
                  & (t["game_id"] != game_id)]
        juegan_ese_dia = set(otros["equipo"]) | set(otros["rival_v"].dropna())
        candidatos = [e for (tt, ll, e) in falta.index
                      if tt == temporada and ll == liga and e != tirador and e not in juegan_ese_dia]
        if len(candidatos) != 1:
            raise ValueError(
                f"xG de equipos: en {temporada} {liga} el partido {game_id} no trae rival y no se puede "
                f"deducir (candidatos: {candidatos}).")
        t.loc[g.index, "rival_v"] = candidatos[0]
    return t


def _con_rival(tiros, equipos):
    t, e = _preparar(tiros, equipos)
    jugados = e.set_index(["temporada", "liga", "equipo"])[COL_PARTIDOS]
    return _rellenar_rival(t, jugados), e


def agregar(tiros, equipos):
    """`equipos` (la tabla de FBref: `temporada`, `liga`, `Squad` y `ov_Playing Time_MP`) con las columnas
    de `COLUMNAS`, en el mismo orden de filas. Las de xG y goles son por partido y sin penales."""
    t, e = _con_rival(tiros, equipos)
    clave = ["temporada", "liga"]
    sp = t[t["situation"] != PENAL].assign(gol=lambda d: (d["result"] == GOL).astype(float))
    favor = sp.groupby(clave + ["equipo"]).agg(xg_fav=("xg", "sum"), gol_fav=("gol", "sum"))
    contra = (sp.groupby(clave + ["rival_v"]).agg(xg_con=("xg", "sum"), gol_con=("gol", "sum"))
              .rename_axis(clave + ["equipo"]))
    total = favor.join(contra, how="outer").fillna(0.0)
    total["xg_partidos"] = _partidos_con_tiros(t)

    out = e.join(total, on=clave + ["equipo"])
    if out["xg_partidos"].isna().any():
        raise ValueError("xG de equipos: hay clubes sin ningún partido en los tiros.")
    for c in ["xg_fav", "xg_con", "gol_fav", "gol_con"]:
        out[c] = out[c] / out["xg_partidos"]
    out["xg_dif"] = out["xg_fav"] - out["xg_con"]
    return out[COLUMNAS]

