"""«De dónde sale el xG»: cuánto del xG de cada equipo nace de jugada abierta, de córner, de tiro libre
directo o de otro balón parado, a favor y en contra.

El cálculo vive aquí (en el build, determinista) y al navegador viaja SOLO una fila por equipo-temporada:
`dist/react/datos-origen-xg.js`. Los textos «Con estos filtros» se arman en el navegador
(`web/react/src/origenXgLectura.js`) sobre esa misma tabla.

**Qué se cuenta.** Los tiros de Understat (`shots_all_seasons.csv`) agrupados por `situation`, con las mismas
reglas que el resto de las vistas de Equipos (`xg_equipos.py`): sin penales (`Penalty`) y sin autogoles
(`Own Goal`, con xG 0 y que no son un tiro del equipo). Por eso la suma del xG de los cuatro segmentos de un
equipo-temporada es, exacta, su `xg_fav` por su número de partidos: `test_origen_xg.py` lo comprueba contra
`xg_equipos.agregar` con los datos reales.

**A favor y en contra.** «A favor» son los tiros que hace el equipo (`team`). «En contra» son los tiros que
le hacen (`rival`): se reutiliza `xg_equipos._con_rival`, que cruza los nombres de Understat con los de FBref
con `nombres.club_visible`, deduce el rival de los 4 partidos en que Understat lo deja vacío y se detiene si
un club no tiene pareja. Lo que un equipo hace a favor, otro lo recibe en contra: en cada liga y temporada, el
xG de un segmento a favor de todos los equipos suma lo mismo que en contra.

**Partidos.** Los que Understat trae del equipo (como tirador o como rival), los mismos de `xg_equipos`: para
6 equipo-temporada difieren en uno de los `ov_Playing Time_MP` de FBref.
"""

import numpy as np
import pandas as pd

import react_views
import shot_map
import xg_equipos
from nombres import club_visible
from preguntas import PREGUNTAS
from site_utils import PROCESSED_DIR, ChartPage, temporadas_en_curso
from viz_theme import FUENTE_UNDERSTAT, LEAGUE_COLORS, LEAGUE_COLORS_DARK, LEAGUE_ORDER

SECTION = "Equipos"
SLUG = "origen-xg"
TITULO = "¿Cómo generan peligro?"

AUTOGOL = "Own Goal"

# Los segmentos en el orden en que se apilan, de izquierda a derecha: los tres de balón parado pegados al
# origen (así sus largos se comparan entre equipos) y la jugada abierta, que es la mayor parte, al final.
# (id, `situation` de Understat). Las etiquetas salen de `shot_map.TIPOS`, las del filtro de tipo de tiro.
SEGMENTOS = [("corner", "From Corner"), ("libre", "Direct Freekick"), ("otro", "Set Piece"),
             ("abierta", "Open Play")]
IDS = [s for s, _ in SEGMENTOS]
BALON_PARADO = [s for s in IDS if s != "abierta"]
_ETIQUETA = {k: e for k, e, *_ in shot_map.TIPOS}
ETIQUETAS = {s: _ETIQUETA[u] for s, u in SEGMENTOS}

# Colores de los segmentos (claro, oscuro). La jugada abierta es el fondo neutro (la vista le pone el gris del
# sitio); los tres de balón parado son tres pasos de claridad del slate del logo (un solo matiz, ninguno de liga): en un
# gráfico donde el color de otras vistas es la liga, un azul, un magenta y un ocre se leían como Serie A, Premier y La Liga.
# El orden de la leyenda es el de los segmentos, del más oscuro al más claro (al revés en el modo oscuro).
COLORES = {
    "claro": {"corner": "#2c4c54", "libre": "#4f7e8b", "otro": "#85a9b4"},
    "oscuro": {"corner": "#a5c4ce", "libre": "#6e9ba9", "otro": "#4a7684"},
}

MIN_PARES = 30     # un par de temporadas con menos equipos en común no entra en la repetición


def _clave():
    return ["temporada", "liga"]


# --- el cálculo -------------------------------------------------------------------------------------

def por_segmento(tiros, equipos):
    """Una fila por equipo-temporada (en el orden de `equipos`) con `temporada`, `liga`, `equipo` (el nombre
    como se muestra), `partidos` y, por cada segmento `s`, `xf_s` y `tf_s` (xG y tiros a favor) y `xc_s` y
    `tc_s` (en contra). Son totales de la temporada, no por partido. Si Understat trae una `situation` que no
    es una de las cuatro ni el penal, se detiene en vez de dejar tiros fuera."""
    t, e = xg_equipos._con_rival(tiros, equipos)
    conocidas = {u for _, u in SEGMENTOS} | {xg_equipos.PENAL}
    raras = set(t["situation"].dropna()) - conocidas
    if raras or t["situation"].isna().any():
        raise ValueError(f"xG por segmento: situaciones de tiro que no se saben clasificar: {sorted(raras)}.")
    partidos = xg_equipos._partidos_con_tiros(t)
    ids = {u: s for s, u in SEGMENTOS}
    sp = t[(t["situation"] != xg_equipos.PENAL) & (t["result"] != AUTOGOL)].copy()
    sp["s"] = sp["situation"].map(ids)

    def totales(columna_equipo, pre_xg, pre_tiros):
        g = sp.groupby(_clave() + [columna_equipo, "s"])["xg"].agg(["sum", "size"]).rename_axis(
            _clave() + ["equipo", "s"])
        xg = g["sum"].unstack("s").reindex(columns=IDS).fillna(0.0)
        n = g["size"].unstack("s").reindex(columns=IDS).fillna(0).astype(int)
        return (xg.add_prefix(pre_xg), n.add_prefix(pre_tiros))

    fav = totales("equipo", "xf_", "tf_")
    con = totales("rival_v", "xc_", "tc_")
    out = e[["temporada", "liga", "equipo"]].reset_index(drop=True)
    out["partidos"] = [int(partidos[(a, b, c)]) for a, b, c in zip(out["temporada"], out["liga"], out["equipo"])]
    out = out.join(pd.concat(fav + con, axis=1), on=_clave() + ["equipo"])
    cols = [f"{p}_{s}" for p in ("xf", "tf", "xc", "tc") for s in IDS]
    fuera = out[cols].isna().all(axis=1)
    if fuera.any():
        raise ValueError("xG por segmento: hay equipos sin ningún tiro.")
    out[cols] = out[cols].fillna(0)
    for c in cols:
        if c.startswith("t"):
            out[c] = out[c].astype(int)
    return out


def total(tabla, lado):
    """xG total sin penales de cada fila, a favor (`lado='f'`) o en contra (`'c'`): la suma de los 4 segmentos."""
    return tabla[[f"x{lado}_{s}" for s in IDS]].sum(axis=1)


def participacion(tabla, lado):
    """El reparto del xG de cada fila entre los cuatro segmentos: una columna por segmento, suma 1 por fila."""
    x = tabla[[f"x{lado}_{s}" for s in IDS]].set_axis(IDS, axis=1)
    return x.div(x.sum(axis=1), axis=0)


def peso_balon_parado(tabla, lado):
    """La parte del xG que viene de balón parado (córner + tiro libre directo + otro): es el número que ordena
    la vista por defecto y el de «Con estos filtros»."""
    return participacion(tabla, lado)[BALON_PARADO].sum(axis=1)


def repeticion(tabla, en_curso=()):
    """Cuánto se repite de una temporada cerrada a la siguiente (mismo criterio que «Goles vs. xG»: la
    correlación de Pearson, por cada par de temporadas cerradas seguidas, entre los equipos que están en las
    dos, cruzados por nombre de club). Devuelve, por medida, `(menor, mayor, menos equipos, más equipos)` y la
    correlación de todos los pares juntos con su n."""
    cerradas = tabla[~tabla["temporada"].isin(set(en_curso))].copy()
    cerradas["bp_f"] = peso_balon_parado(cerradas, "f")
    cerradas["bp_c"] = peso_balon_parado(cerradas, "c")
    cerradas["xg_f"] = total(cerradas, "f") / cerradas["partidos"]
    ts = sorted(cerradas["temporada"].unique())

    def medir(col):
        rs, ns, xs, ys = [], [], [], []
        for a, b in zip(ts, ts[1:]):
            m = (cerradas[cerradas["temporada"] == a].merge(
                cerradas[cerradas["temporada"] == b], on="equipo", suffixes=("_a", "_b")))
            if len(m) >= MIN_PARES:
                rs.append(float(m[f"{col}_a"].corr(m[f"{col}_b"])))
                ns.append(len(m))
                xs += list(m[f"{col}_a"]); ys += list(m[f"{col}_b"])
        if not rs:
            return None
        return {"min": min(rs), "max": max(rs), "n_min": min(ns), "n_max": max(ns),
                "juntos": float(np.corrcoef(xs, ys)[0, 1]), "n": len(xs)}

    return {k: medir(k) for k in ("bp_f", "bp_c", "xg_f")}


def hechos(tiros, tabla, equipos, en_curso):
    """Las cifras que citan los textos fijos, todas de los datos. `tiros` son los tiros crudos con el rival ya
    cruzado (`xg_equipos._con_rival`), de las temporadas cerradas."""
    cerr = tiros[~tiros["temporada"].isin(set(en_curso))]
    sin_penal = cerr[(cerr["situation"] != xg_equipos.PENAL) & (cerr["result"] != AUTOGOL)]
    xg_todo = float(cerr["xg"].sum())
    penales = float(cerr.loc[cerr["situation"] == xg_equipos.PENAL, "xg"].sum())
    por_sit = sin_penal.assign(gol=(sin_penal["result"] == "Goal")).groupby("situation").agg(
        xg=("xg", "sum"), goles=("gol", "sum"))
    razon = {s: float(por_sit.loc[u, "goles"] / por_sit.loc[u, "xg"]) for s, u in SEGMENTOS}
    xg_sit = {s: float(por_sit.loc[u, "xg"] / por_sit["xg"].sum()) for s, u in SEGMENTOS}
    gol_sit = {s: float(por_sit.loc[u, "goles"] / por_sit["goles"].sum()) for s, u in SEGMENTOS}
    c = tabla[~tabla["temporada"].isin(set(en_curso))]
    n_tiros_bp = c[[f"tf_{s}" for s in BALON_PARADO]].sum(axis=1)
    mp = equipos[["temporada", "liga", "Squad", xg_equipos.COL_PARTIDOS]].assign(
        equipo=equipos["Squad"].map(club_visible)).set_index(
        ["temporada", "liga", "equipo"])[xg_equipos.COL_PARTIDOS]
    llave = list(zip(tabla["temporada"], tabla["liga"], tabla["equipo"]))
    difieren = int((tabla["partidos"].to_numpy() != mp.loc[llave].to_numpy()).sum())
    return {
        "penales_pct": 100 * penales / xg_todo,
        "goles_xg": float(por_sit["goles"].sum() / por_sit["xg"].sum()),
        "razon": razon, "xg_pct": {s: 100 * v for s, v in xg_sit.items()},
        "gol_pct": {s: 100 * v for s, v in gol_sit.items()},
        "bp_xg_pct": 100 * sum(xg_sit[s] for s in BALON_PARADO),
        "bp_con_penales_pct": 100 * (sum(xg_sit[s] for s in BALON_PARADO) * (xg_todo - penales) + penales)
                              / xg_todo,
        "bp_gol_pct": 100 * sum(gol_sit[s] for s in BALON_PARADO),
        "bp_tiros_mediana": float(n_tiros_bp.median()),
        "bp_xg_mediana": float(c[[f"xf_{s}" for s in BALON_PARADO]].sum(axis=1).median()),
        "difieren": difieren,
        "n_cerradas": int(len(c)),
    }


def calcular(tiros_crudos, equipos, en_curso=None):
    """Todo el cálculo de la vista a partir de las tablas crudas (los tests lo llaman con datos sintéticos)."""
    en_curso = set(en_curso if en_curso is not None else temporadas_en_curso())
    sin_rival = int(tiros_crudos.loc[tiros_crudos["rival"].isna(), "game_id"].nunique())
    tabla = por_segmento(tiros_crudos, equipos)
    t, _ = xg_equipos._con_rival(tiros_crudos, equipos)
    h = hechos(t, tabla, equipos, en_curso)
    h["sin_rival"] = sin_rival
    return {"tabla": tabla, "en_curso": en_curso, "hechos": h, "repeticion": repeticion(tabla, en_curso),
            "temporadas": sorted(tabla["temporada"].unique())}


# --- los textos fijos ---------------------------------------------------------------------------------

def _p(x, dec=0):
    return f"{x:.{dec}f}%"


def _n(n):
    return f"{int(n):,}"


def _entre(p):
    equipos = f"{p['n_min']}" if p["n_min"] == p["n_max"] else f"{p['n_min']} a {p['n_max']}"
    return f"entre {p['min']:.2f} y {p['max']:.2f} ({equipos} equipos por par de temporadas)"


def _se_repite(p):
    """Las mismas bandas que «Goles vs. xG» (`insights._se_repite`), sobre el valor más alto de los pares."""
    hi = max(abs(p["min"]), abs(p["max"]))
    if hi < 0.3:
        return "Casi nada se repite."
    if hi < 0.6:
        return "Se repite en parte."
    return "Se repite bastante."


def textos(r):
    """(qué más mirar, por qué así): los textos fijos de la vista. Cada cifra sale de los datos calculados."""
    h, rep, ts = r["hechos"], r["repeticion"], r["temporadas"]
    cerradas = [t for t in ts if t not in r["en_curso"]]
    seg = ETIQUETAS
    que_mirar = (
        "Muestra cómo genera peligro cada equipo, según de dónde sale su xG. Cada barra reparte el xG según "
        "cómo nació la ocasión: jugada abierta en gris y, en colores, córner, tiro libre directo y otro balón "
        "parado.\n"
        "Con «% del xG» ves de qué vía depende cada equipo y con «xG por partido», cuánto produce por ella. "
        "«A favor» son los tiros que hace el equipo y «En contra», los que recibe.")


    por_que = (
        f"**Los segmentos.** Salen de la jugada con que Understat etiqueta cada tiro: **{seg['abierta']}** (juego en "
        f"movimiento), **{seg['corner']}** (saque de esquina), **{seg['libre']}** (remate directo de una falta) y "
        f"**{seg['otro']}** (faltas y saques al área que no acaban en tiro libre directo).\n\n"
        f"**Qué queda fuera.** Los penales ({_p(h['penales_pct'], 1)} del xG de Understat en las {len(cerradas)} temporadas "
        f"cerradas) y los autogoles. El balón parado que ves es **{_p(h['bp_xg_pct'], 1)}** del xG sin penales "
        f"({_p(h['xg_pct']['corner'], 1)} de córner, {_p(h['xg_pct']['libre'], 1)} de tiro libre directo y "
        f"{_p(h['xg_pct']['otro'], 1)} de otro balón parado); contando los penales, subiría a "
        f"{_p(h['bp_con_penales_pct'], 1)}.\n\n"
        f"**Límites.** El xG de Understat suma más de lo que entra: los equipos metieron el {_p(100 * h['goles_xg'])} de su "
        f"xG sin penales, y solo el {_p(100 * h['razon']['otro'])} en otro balón parado, contra el "
        f"{_p(100 * h['razon']['abierta'])} en jugada abierta. Por eso el reparto del xG no es el de los goles: el balón "
        f"parado es {_p(h['bp_xg_pct'], 1)} del xG y {_p(h['bp_gol_pct'], 1)} de los goles. El «por partido» divide entre "
        f"los partidos que Understat trae del equipo.\n\n"
        f"Una temporada de balón parado es **poca muestra**: un equipo típico hace {_n(round(h['bp_tiros_mediana']))} tiros "
        f"de balón parado y suma {h['bp_xg_mediana']:.1f} de xG. Y cambia bastante de un año al siguiente: la parte del xG "
        f"a favor que sale de balón parado correlaciona entre {rep['bp_f']['min']:.2f} y {rep['bp_f']['max']:.2f} (en "
        f"contra, entre {rep['bp_c']['min']:.2f} y {rep['bp_c']['max']:.2f}), contra {rep['xg_f']['min']:.2f} a "
        f"{rep['xg_f']['max']:.2f} del xG total. {_se_repite(rep['bp_f'])} Una barra de una sola temporada dice cómo fue "
        f"ese año y solo en parte cómo es el equipo.")
    return que_mirar, por_que


# --- la vista -----------------------------------------------------------------------------------------

def payload(r):
    """Lo que viaja al navegador: una fila por equipo-temporada, en columnas. Los xG van con tres decimales
    (el máximo es del orden de 100, y el redondeo no mueve ninguna cifra que se muestre con 1 o 2)."""
    d = r["tabla"]
    ligas = list(LEAGUE_ORDER)
    temporadas = list(r["temporadas"])
    nombres, j = react_views._diccionario(d["equipo"])
    c = {"pj": [int(v) for v in d["partidos"]]}
    for p in ("xf", "xc"):
        for s in IDS:
            c[f"{p}_{s}"] = [round(float(v), 3) for v in d[f"{p}_{s}"]]
    for p in ("tf", "tc"):
        for s in IDS:
            c[f"{p}_{s}"] = [int(v) for v in d[f"{p}_{s}"]]
    return {"entidad": SLUG, "n": int(len(d)), "temporadas": temporadas, "ligas": ligas, "nombres": nombres,
            "f": {"j": j, "l": react_views._codigos(d["liga"].astype(str), ligas),
                  "t": react_views._codigos(d["temporada"], temporadas)},
            "c": c, "enCurso": {t: n for t, n in temporadas_en_curso().items() if t in temporadas}}


def _cargar():
    tiros = xg_equipos.cargar_tiros(PROCESSED_DIR / "shots_all_seasons.csv")
    equipos = pd.read_csv(PROCESSED_DIR / "teams_all_seasons.csv")
    return tiros, equipos


def chart_origen_xg() -> ChartPage:
    tiros, equipos = _cargar()
    r = calcular(tiros, equipos)
    react_views.registrar_payload(SLUG, payload(r))
    que_mirar, _ = textos(r)
    bajada = "Cuánto del xG de cada equipo sale de jugada abierta, de córner y de otros balones parados."
    assert len(bajada) <= 108, f"{SLUG}: la bajada mide {len(bajada)} caracteres"
    cfg = {
        "id": SLUG, "titulo": TITULO, "bajada": bajada, "pregunta": PREGUNTAS[SLUG], "tabla": SLUG,
        "queMirar": que_mirar, "fuente": FUENTE_UNDERSTAT,
        "segmentos": [{"id": s, "etiqueta": ETIQUETAS[s], "balonParado": s in BALON_PARADO} for s in IDS],
        "colores": {"claro": {**COLORES["claro"]}, "oscuro": {**COLORES["oscuro"]}},
        "ligasColores": {"claro": {l: LEAGUE_COLORS[l] for l in LEAGUE_ORDER},
                         "oscuro": {l: LEAGUE_COLORS_DARK[l] for l in LEAGUE_ORDER}},
    }
    return ChartPage(slug=SLUG, section=SECTION, title=TITULO, subtitle=bajada,
                     body_html=react_views.montar_html("origen_xg", SLUG, cfg, alto_min=520), kind="bar")
