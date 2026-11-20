"""«Trayectoria del club en ELO»: cómo ha cambiado la fuerza de un club, temporada a temporada.

Líneas con el ELO de hasta 6 clubes a la vez (selector de clubes, de medida y de liga), contra el promedio de
ELO de las 5 ligas en cada temporada. Lo dibuja `LineasSvg.jsx` (el mismo componente de «Forma»).

**Los datos.** `elo_pre`, `elo_medio` y `elo_fin` de `teams_all_seasons.csv`, que `consolidate_data.py` pega a cada
equipo-temporada desde `elo.csv` (clubelo, `fetch_elo.py`). Las tres se miden en fechas fijas, las mismas para las
cinco ligas (`fetch_elo.ventana`):

* `elo_pre`: el rating vigente el **15 de julio** del año en que arranca la temporada (antes de su primer partido y
  después de todo lo de la anterior).
* `elo_fin`: el rating vigente el **1 de junio** del año siguiente (después de la última fecha de las 5 ligas).
* `elo_medio`: el promedio del rating entre el **1 de agosto y el 1 de junio**, ponderado por días (cada
  rating pesa los días que estuvo vigente, no los partidos que lo movieron).

`elo_club` es el nombre del club en clubelo (texto): aquí no se usa. El club se llama como en el resto del sitio
(`nombres.club_visible`, sobre el `Squad` de FBref). 2026-27 no tiene ELO (clubelo aún no lo baja): la vista llega
hasta la última temporada que sí lo tiene y lo dice.

**Huecos.** Un club solo tiene fila en las temporadas en que jugó en las 5 ligas (96 o 98 equipo-temporadas por
temporada). Si ascendió o descendió, su línea se corta: el payload lleva `null` ahí y el dibujo no une los puntos.

**La referencia.** El promedio simple del ELO de todos los clubes de las 5 ligas en esa temporada y con esa medida.
El ELO es una escala única para Europa (los clubes de ligas distintas se enfrentan en torneos europeos), así que
una sola referencia sirve para clubes de cualquier liga. Cambia un poco de una temporada a otra porque cambian los
clubes que hay (los que ascienden y descienden, y las dos plazas que perdió la Ligue 1).

Todo el cálculo vive aquí (en el build, determinista). Al navegador viaja una fila por club (con los tres ELO de
cada temporada) en `dist/react/datos-trayectoria-elo.js`; el texto «Con estos filtros» se arma allá
(`trayectoriaEloLectura.js`) sobre esa misma tabla.
"""

import numpy as np
import pandas as pd

import react_views
from nombres import club_visible
from preguntas import PREGUNTAS
from site_utils import PROCESSED_DIR, ChartPage
from viz_theme import LEAGUE_ORDER

SECTION = "Equipos"
SLUG = "trayectoria-elo"
TITULO = "Trayectoria del club en ELO"
BAJADA = "El ELO de cada club en cada temporada, junto al promedio de las 5 ligas."
FUENTE = "clubelo"

MAX_CLUBES = 6
MEDIDA_INICIAL = "med"

# (id en el payload, columna de teams_all_seasons.csv, etiqueta del botón)
MEDIDAS = [("pre", "elo_pre", "Al arrancar"), ("med", "elo_medio", "Promedio"), ("fin", "elo_fin", "Al cerrar")]
COLUMNAS = [c for _, c, _ in MEDIDAS]

# Las fechas de `fetch_elo.ventana` (mes, día). `test_trayectoria_elo.py` comprueba que siguen iguales.
FECHA_PRE = (7, 15)
FECHA_MEDIO_DESDE = (8, 1)
FECHA_FIN = (6, 1)

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre"]

# Seis colores que se distinguen entre sí y de la referencia (gris), en claro y en oscuro. Cada club conserva el suyo
# mientras está seleccionado (los asigna el navegador). Los de claro pasan 3:1 contra la superficie blanca; los de
# oscuro contra la superficie oscura.
COLORES = {
    "claro": ["#1F6FB5", "#C2511B", "#1E8F6B", "#8E4EC6", "#A9770A", "#C0407E"],
    "oscuro": ["#5AA9E6", "#F08A4B", "#3FC79A", "#B88AE8", "#E0B43C", "#F06FA8"],
}


def _dia(fecha):
    mes, dia = fecha
    return f"{dia} de {MESES[mes - 1]}"


# --- el cálculo ----------------------------------------------------------------------------------

def tabla_elo(equipos):
    """Una fila por club y temporada CON ELO: `temporada, liga, club, pre, med, fin`.

    `equipos` es `teams_all_seasons.csv` (o lo que traiga `temporada, liga, Squad, elo_pre, elo_medio, elo_fin`).
    Las temporadas sin ELO (todo vacío) no entran; una fila con solo parte del ELO es un error del dato."""
    e = equipos[["temporada", "liga", "Squad"] + COLUMNAS].copy()
    parcial = e[COLUMNAS].notna().any(axis=1) & e[COLUMNAS].isna().any(axis=1)
    if parcial.any():
        raise ValueError(f"Trayectoria ELO: filas con el ELO a medias: {e.loc[parcial, ['temporada', 'Squad']].values.tolist()}")
    e = e[e[COLUMNAS].notna().all(axis=1)].copy()
    e["club"] = e["Squad"].map(club_visible)
    dup = e.duplicated(["temporada", "club"], keep=False)
    if dup.any():
        raise ValueError(f"Trayectoria ELO: un club dos veces en una temporada: {e.loc[dup, ['temporada', 'club']].values.tolist()}")
    e = e.rename(columns={c: i for i, c, _ in MEDIDAS})
    return e[["temporada", "liga", "club", "pre", "med", "fin"]].sort_values(["temporada", "club"]).reset_index(drop=True)


def referencia(tabla, temporadas):
    """`{medida: [promedio por temporada]}` (promedio simple de todos los clubes de esa temporada) y los clubes por
    temporada. Una temporada sin clubes queda en `None`."""
    por = tabla.groupby("temporada")
    ref = {m: [None if t not in por.groups else float(por.get_group(t)[m].mean()) for t in temporadas]
           for m, _, _ in MEDIDAS}
    n = [0 if t not in por.groups else int(len(por.get_group(t))) for t in temporadas]
    return ref, n


def inicial(tabla, temporadas, medida=MEDIDA_INICIAL):
    """El club más fuerte de cada liga en la última temporada con ELO, con la medida con la que abre la vista, del
    más fuerte al menos fuerte. Abre la vista con algo que contar (las cinco ligas en la misma escala) sin
    escribir un nombre a mano."""
    u = tabla[tabla["temporada"] == temporadas[-1]]
    mejores = u.sort_values([medida, "club"], ascending=[False, True]).groupby("liga", sort=False).head(1)
    return list(mejores.sort_values([medida, "club"], ascending=[False, True])["club"])


def calcular(equipos):
    """Todo el cálculo de la vista (los tests lo llaman con datos sintéticos)."""
    tabla = tabla_elo(equipos)
    temporadas = sorted(tabla["temporada"].unique())
    sin_elo = sorted(set(equipos["temporada"]) - set(temporadas))
    ref, n = referencia(tabla, temporadas)
    return {"tabla": tabla, "temporadas": temporadas, "sin_elo": sin_elo, "ref": ref, "n": n,
            "iniciales": inicial(tabla, temporadas), "verano": diferencia_verano(tabla, temporadas)}


def diferencia_verano(tabla, temporadas):
    """`|elo_pre de una temporada − elo_fin de la anterior|` por club en temporadas seguidas: lo que se mueve el
    rating en el verano (del 1 de junio al 15 de julio). Devuelve `(mediana, máximo, pares)`."""
    pre = tabla.pivot(index="club", columns="temporada", values="pre")
    fin = tabla.pivot(index="club", columns="temporada", values="fin")
    d = []
    for a, b in zip(temporadas, temporadas[1:]):
        d += list((pre[b] - fin[a]).dropna().abs())
    if not d:
        return float("nan"), float("nan"), 0
    return float(np.median(d)), float(np.max(d)), len(d)


# --- el payload ----------------------------------------------------------------------------------

def _x(v):
    return None if v is None or (isinstance(v, float) and np.isnan(v)) else round(float(v), 1)


def payload(r):
    """Lo que viaja al navegador. `clubes`: una fila por club, `{n: nombre, l: índice en `ligas` (el de su última
    temporada con ELO), pre, med, fin: un valor por temporada o null donde no jugó en las 5 ligas}`. `ref`: el
    promedio de las 5 ligas por temporada, con cada medida. `n`: cuántos clubes hay por temporada."""
    tabla, temporadas = r["tabla"], r["temporadas"]
    idx = {t: i for i, t in enumerate(temporadas)}
    ligas = list(LEAGUE_ORDER)
    clubes = []
    for club, g in tabla.groupby("club", sort=True):
        fila = {"n": club, "l": ligas.index(g.sort_values("temporada")["liga"].iloc[-1])}
        for m, _, _ in MEDIDAS:
            v = [None] * len(temporadas)
            for t, x in zip(g["temporada"], g[m]):
                v[idx[t]] = _x(x)
            fila[m] = v
        clubes.append(fila)
    return {"entidad": SLUG, "temporadas": temporadas, "sinElo": r["sin_elo"], "ligas": ligas, "clubes": clubes,
            "ref": {m: [_x(v) for v in r["ref"][m]] for m, _, _ in MEDIDAS}, "n": r["n"],
            "iniciales": r["iniciales"], "medida": MEDIDA_INICIAL, "maxClubes": MAX_CLUBES}


# --- los textos fijos ----------------------------------------------------------------------------

def _elo(v):
    return f"{round(v):,}"


def ayudas_medidas():
    """La frase corta de cada medida (bajo el selector), con las fechas de `FECHA_*`."""
    return {
        "pre": f"El rating del {_dia(FECHA_PRE)} del año en que empieza la temporada, antes de su primer partido.",
        "med": (f"El rating promedio entre el {_dia(FECHA_MEDIO_DESDE)} y el {_dia(FECHA_FIN)} del año siguiente, "
                f"ponderado por días."),
        "fin": f"El rating del {_dia(FECHA_FIN)} del año siguiente, tras la última fecha de las 5 ligas.",
    }


def textos(r):
    """(qué más mirar, por qué así). Cada cifra sale de los datos o de las constantes de este módulo."""
    t = r["temporadas"]
    ultima = t[-1]
    ref_med = [v for v in r["ref"]["med"] if v is not None]
    n_min, n_max = min(r["n"]), max(r["n"])
    n_clubes = int(r["tabla"]["club"].nunique())
    n_filas = int(len(r["tabla"]))
    completos = int((r["tabla"].groupby("club").size() == len(t)).sum())
    mediana, maximo, pares = r["verano"]
    sin = ", ".join(r["sin_elo"])
    llega = (f"La vista llega hasta {ultima}: {sin} no tiene ELO todavía y no se dibuja." if sin
             else f"La vista llega hasta {ultima}.")
    que_mirar = (
        "**Qué mide el ELO.** Es un rating único por club: cada resultado lo mueve, hacia arriba si el club rindió más de "
        "lo que su rating esperaba y hacia abajo si rindió menos. Pesan la diferencia de goles y la fuerza del rival: "
        "ganarle a uno fuerte por mucho sube más que ganarle a uno débil por uno. Como los clubes de ligas distintas se "
        "enfrentan en torneos europeos, todos comparten una sola escala, y por eso la línea de un club de la Bundesliga y la "
        "de uno de la Serie A se leen en el mismo eje.\n\n"
        f"**La línea punteada** es el promedio de ELO de los {n_min} a {n_max} clubes que hay en las 5 ligas cada temporada "
        f"(con «Promedio» va de {_elo(min(ref_med))} a {_elo(max(ref_med))} en estas {len(t)} temporadas). Un club "
        "arriba de ella está por encima de lo normal en las 5 ligas; uno abajo, por debajo.\n\n"
        "**Qué no es.** El ELO sale de resultados, no de jugadores: no sabe quién juega, cuánto cuesta la plantilla ni cómo "
        "está de lesionados. Un club con una plantilla muy cara puede tener un ELO bajo si no gana, y uno con una "
        "plantilla barata puede tenerlo alto si gana. Tampoco es absoluto: es un rating relativo, y en cada partido lo que gana un club "
        "lo pierde su rival. Una subida dice que el club ganó más de lo que se esperaba de él, no que "
        "mejoró en una medida fija.\n\n"
        f"**Dónde se corta la línea.** Cada club solo aparece en las temporadas que jugó en las 5 ligas: {completos} de los "
        f"{n_clubes} clubes están en las {len(t)}; los demás tienen huecos, y ahí la línea se interrumpe en vez de unir "
        f"los puntos. {llega}")
    por_que = (
        "**De dónde sale.** Del ELO de clubelo.com, un rating de fútbol de clubes calculado solo con resultados e "
        "independiente de FBref y de Understat. fetch_elo.py baja la historia diaria de cada club y toma tres valores por "
        "temporada, en las mismas fechas para las cinco ligas. "
        f"**Al arrancar** es el rating vigente el {_dia(FECHA_PRE)} del año en que empieza la temporada (después de todo lo de "
        f"la anterior y antes de su primer partido). **Al cerrar** es el del {_dia(FECHA_FIN)} del año siguiente (después de la "
        f"última fecha de las 5 ligas). **Promedio** es el rating entre el {_dia(FECHA_MEDIO_DESDE)} y el {_dia(FECHA_FIN)}, "
        "ponderado por días: cada rating pesa lo que estuvo vigente, no cuántos partidos lo movieron. Se empieza en agosto y "
        "no en julio para que el mes de parón, con el rating quieto, no pese en el promedio.\n\n"
        "**Qué medida mirar.** La vista abre en «Promedio» porque da un solo número por temporada que resume todo el "
        "campeonato y no depende del día en que se mida. «Al cerrar» ya contiene los resultados de esa temporada completa; "
        "«Al arrancar» solo trae lo anterior. En el verano, entre el cierre de una temporada y el arranque de la siguiente, "
        f"el rating casi no se mueve: la diferencia entre los dos es de {mediana:.0f} puntos en la mediana y de {maximo:.0f} "
        f"como máximo ({pares} pares de temporadas seguidas). Por eso la línea de «Al arrancar» es casi la de «Al cerrar» "
        "corrida una temporada.\n\n"
        f"**La referencia.** Es el promedio simple de los clubes de las 5 ligas en cada temporada ({n_filas} equipo-temporadas "
        f"en total, entre {n_min} y {n_max} por temporada), con la misma medida que se dibuja. No es el promedio de la liga "
        "del club: como la escala es común, un solo referente permite comparar clubes de ligas distintas. Se mueve un poco "
        "porque cambian los clubes que hay: los que suben y bajan, y cuántos equipos tiene cada liga.\n\n"
        "**Límites.** Son pocos puntos por club, uno por temporada: la línea muestra qué pasó, no una tendencia que se pueda "
        "proyectar. La comparación entre ligas se apoya en los partidos europeos, que son pocos frente a los de cada liga, "
        "así que el nivel relativo de dos ligas es menos firme que el de dos clubes de la misma liga. Un club que sube o "
        "baja de categoría deja un hueco: clubelo sí tiene su rating en segunda división, pero esta vista solo muestra las "
        "temporadas en las 5 ligas. El nombre del club es el del resto del sitio; el nombre con que clubelo lo conoce "
        f"(elo_club) no se usa. {llega}")
    return que_mirar, por_que


# --- la vista ------------------------------------------------------------------------------------

def _cargar():
    cols = ["temporada", "liga", "Squad"] + COLUMNAS
    return pd.read_csv(PROCESSED_DIR / "teams_all_seasons.csv", usecols=cols, encoding="utf-8-sig")


def chart_trayectoria_elo() -> ChartPage:
    r = calcular(_cargar())
    react_views.registrar_payload(SLUG, payload(r))
    que_mirar, por_que = textos(r)
    assert len(BAJADA) <= 108, f"{SLUG}: la bajada mide {len(BAJADA)} caracteres"
    cfg = {
        "id": SLUG, "titulo": TITULO, "bajada": BAJADA, "pregunta": PREGUNTAS[SLUG], "tabla": SLUG,
        "queMirar": que_mirar, "porQue": por_que, "fuente": FUENTE,
        "medidas": [{"id": m, "etiqueta": e, "ayuda": ayudas_medidas()[m]} for m, _, e in MEDIDAS],
        "colores": COLORES,
    }
    return ChartPage(slug=SLUG, section=SECTION, title=TITULO, subtitle=BAJADA,
                     body_html=react_views.montar_html("trayectoria_elo", SLUG, cfg, alto_min=520), kind="line")
