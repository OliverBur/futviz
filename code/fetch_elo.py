"""Descarga el ELO de clubelo.com para los equipos de las 5 temporadas y lo
deja en `data/<temporada>/elo.csv`, para que `consolidate_data.py` lo pegue a
`teams_all_seasons.csv` igual que las tablas `vs` de fbref.

Por qué clubelo y no otra fuente: publica una API abierta y gratis
(http://api.clubelo.com), con **historia diaria completa** por club desde los
años 40. Eso es lo que hace falta acá: no queremos "el ELO de hoy" sino el que
tenía cada club en cada una de las 5 temporadas. Es el rating Elo de fútbol de
club más usado (mismo linaje que eloratings.net para selecciones), calculado
solo con resultados, y por lo tanto **independiente de fbref y de Understat**:
mide nivel de equipo sin usar ninguna de las estadísticas que ya tenemos, así
que no es circular usarlo para segmentar los gráficos.

Dos endpoints, los dos devuelven CSV:

    http://api.clubelo.com/<AAAA-MM-DD>   ranking de TODOS los clubes ese día
    http://api.clubelo.com/<Club>         historia completa de un club

Acá se usa el segundo: una petición por club (~130 en total, cacheadas en
`data/.clubelo/`) trae todos los intervalos `[From, To]` con su rating, que es
lo único que permite calcular bien un promedio de temporada. El primero se usa
solo en `--verificar`, para comprobar contra el ranking del día que los nombres
cruzaron con los clubes correctos.

Nombres: fbref y clubelo escriben distinto casi la mitad de los clubes
('Bayern Munich' vs 'Bayern', 'Nottingham' vs 'Forest'). El puente es `ALIAS`
—escrito a mano, es la única parte que hay que tocar cuando ascienda un club
nuevo— más una normalización de acentos para los que solo difieren en eso
('Alavés' -> 'Alaves'). La URL del club es su nombre de clubelo sin espacios,
pero **conservando los guiones**: 'Paris SG' -> ParisSG, 'Saint-Etienne' ->
Saint-Etienne (SaintEtienne devuelve vacío).

Uso:
    python fetch_elo.py                  # todas las temporadas que estén bajadas
    python fetch_elo.py 2024-25 2025-26  # solo esas
    python fetch_elo.py --force          # ignora el caché y vuelve a pedir todo
    python fetch_elo.py --verificar      # además, cruza contra el ranking diario
"""

import io
import sys
import time
import unicodedata
from datetime import date
from pathlib import Path

import pandas as pd
import requests

from consolidate_data import (
    DATA_DIR, LEAGUE_ORDER, SEASONS, flatten_columns, split_league_blocks,
)

CACHE_DIR = DATA_DIR / ".clubelo"
API = "http://api.clubelo.com"
DELAY_SECONDS = 1.5  # entre peticiones nuevas; las cacheadas no esperan
TIMEOUT = 60         # clubelo tarda ~8 s por club y a veces bastante más
REINTENTOS = 4

OUT_FILE = "elo.csv"
SOURCE_FILE = "leagues_overall.csv"  # de dónde salen los equipos de la temporada

# El país que clubelo le pone a los clubes de cada una de nuestras ligas. Sirve
# para verificar que el nombre cruzó con el club correcto y no con un homónimo
# de otro país (hay varios 'Valencia', 'Nacional', 'Racing'... en la base).
COUNTRY = {
    "Bundesliga": "GER", "Serie A": "ITA", "Ligue 1": "FRA",
    "La Liga": "ESP", "Premier League": "ENG",
}
# Alemania aparece como RFA en la historia vieja; irrelevante para 2021+, pero
# el chequeo mira toda la ventana de la temporada y no cuesta nada aceptarlo.
COUNTRY_ALT = {"GER": {"FRG", "GDR"}}

# fbref -> clubelo, solo donde no alcanza con quitar acentos. Cada línea es un
# club que en algún momento de las 5 temporadas jugó en primera.
ALIAS = {
    # Bundesliga
    "Arminia": "Bielefeld",
    "Bayern Munich": "Bayern",
    "Darmstadt 98": "Darmstadt",
    "Greuther Fürth": "Fuerth",
    "Hamburger SV": "Hamburg",
    "Hertha BSC": "Hertha",
    "Holstein Kiel": "Holstein",
    "Köln": "Koeln",
    "Mainz 05": "Mainz",
    "Schalke 04": "Schalke",
    "Werder Bremen": "Werder",
    # Serie A
    "Hellas Verona": "Verona",
    # Ligue 1
    "Clermont Foot": "Clermont",
    "PSG": "Paris SG",
    "Saint-Étienne": "Saint-Etienne",
    # La Liga
    "Athletic Club": "Bilbao",
    "Atlético Madrid": "Atletico",
    "Celta Vigo": "Celta",
    "Real Betis": "Betis",
    "Real Sociedad": "Sociedad",
    # Premier League
    "Ipswich Town": "Ipswich",
    "Leeds United": "Leeds",
    "Leicester City": "Leicester",
    "Luton Town": "Luton",
    "Manchester City": "Man City",
    "Manchester Utd": "Man United",
    "Norwich City": "Norwich",
    "Nottingham": "Forest",
}


def sin_acentos(s):
    """'Alavés' -> 'Alaves'. clubelo escribe todo en ASCII."""
    d = unicodedata.normalize("NFKD", str(s))
    return "".join(c for c in d if not unicodedata.combining(c))


def clubelo_name(squad):
    return ALIAS.get(squad, sin_acentos(squad))


def clubelo_url(name):
    """El nombre sin espacios. Los guiones SÍ se conservan: 'Saint-Etienne'
    funciona y 'SaintEtienne' devuelve una tabla vacía."""
    return f"{API}/{name.replace(' ', '')}"


# --- Ventana de cada temporada -------------------------------------------
#
# Fechas fijas en vez de "el primer y el último partido de cada club" a
# propósito: las ligas arrancan y terminan en semanas distintas y queremos que
# el ELO de una temporada signifique lo mismo para las cinco. Los ratings de
# clubelo solo cambian cuando hay partido, así que un día de parón sirve de
# marca.
#
#   PRE  15-jul  ya terminó todo lo de la temporada anterior (incluida la final
#                de Champions, fin de mayo) y todavía no empezó nada de la nueva
#                — ni la primera ronda de copa alemana, que es a principios de
#                agosto. Es el nivel con el que el club LLEGA a la temporada.
#   FIN   1-jun  después de la última fecha de las 5 ligas (mediados/fines de
#                mayo) y de la final de Champions.
#
# El promedio se toma sobre [1-ago, 1-jun]: arranca cuando arranca la primera
# liga y no en julio, para que el mes largo de parón —donde el rating es una
# constante— no le pese al promedio.
def ventana(season):
    y0 = int(season[:4])
    y1 = y0 + 1
    return date(y0, 7, 15), date(y0, 8, 1), date(y1, 6, 1)


def pedir(url):
    """GET con reintentos. clubelo es un servidor chico: responde en ~8 s y de
    vez en cuando corta la conexión o tarda de más si se le pide muy seguido.
    Sin reintentos, una corrida de 130 clubes se muere a la mitad."""
    for intento in range(1, REINTENTOS + 1):
        try:
            r = requests.get(url, timeout=TIMEOUT)
            r.raise_for_status()
            return r.text
        except requests.RequestException as e:
            if intento == REINTENTOS:
                raise
            espera = DELAY_SECONDS * 4 * intento
            print(f"    {url} falló ({type(e).__name__}), reintento "
                  f"{intento}/{REINTENTOS - 1} en {espera:.0f}s")
            time.sleep(espera)


def historia(name, force=False):
    """Los intervalos `[From, To]` con rating de un club, cacheados en disco."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    f = CACHE_DIR / f"{name.replace(' ', '_')}.csv"
    if force or not f.exists():
        f.write_text(pedir(clubelo_url(name)), encoding="utf-8")
        time.sleep(DELAY_SECONDS)
    df = pd.read_csv(f)
    if df.empty:
        raise ValueError(f"clubelo no conoce a '{name}' ({clubelo_url(name)})")
    df["From"] = pd.to_datetime(df["From"]).dt.date
    df["To"] = pd.to_datetime(df["To"]).dt.date
    return df


def elo_en(hist, dia):
    """El rating vigente un día. `None` si ese día queda fuera de la historia."""
    fila = hist[(hist["From"] <= dia) & (hist["To"] >= dia)]
    return None if fila.empty else float(fila.iloc[0]["Elo"])


def elo_medio(hist, desde, hasta):
    """Promedio del rating en la ventana, ponderado por días.

    Ponderar por días y no por intervalos es lo correcto: clubelo abre un
    intervalo nuevo por cada partido, así que una semana con tres partidos
    generaría tres intervalos cortos que pesarían igual que uno de un mes de
    parón. Con este promedio, un club que arrancó flojo y terminó fuerte queda
    en el medio, que es lo que se quiere de un "nivel de la temporada"."""
    tramos = hist[(hist["To"] >= desde) & (hist["From"] <= hasta)].copy()
    if tramos.empty:
        return None, None
    ini = tramos["From"].clip(lower=desde)
    fin = tramos["To"].clip(upper=hasta)
    dias = pd.Series([(b - a).days + 1 for a, b in zip(ini, fin)], index=tramos.index)
    return float((tramos["Elo"] * dias).sum() / dias.sum()), tramos


def paises_en(tramos):
    return set(tramos["Country"].unique())


def equipos_de(season):
    """Los equipos de la temporada con su liga, leídos del CSV crudo de fbref."""
    raw = flatten_columns(pd.read_csv(DATA_DIR / season / SOURCE_FILE, header=[0, 1]))
    return pd.DataFrame({
        "Squad": raw["Squad"],
        "liga": split_league_blocks(raw["Squad"], season),
    })


def temporada(season, force=False):
    """La tabla de ELO de una temporada, o None si faltan datos de fbref."""
    src = DATA_DIR / season / SOURCE_FILE
    if not src.exists():
        return None

    pre_dia, medio_desde, fin_dia = ventana(season)
    filas, avisos = [], []

    for squad, liga in equipos_de(season).itertuples(index=False):
        name = clubelo_name(squad)
        hist = historia(name, force=force)
        medio, tramos = elo_medio(hist, medio_desde, fin_dia)

        # El club correcto juega esa temporada en el país de esa liga y en
        # primera. Si no, el nombre cruzó con un homónimo o con el club de otra
        # ciudad — es el error que hay que ver acá y no tres pasos después.
        esperado = COUNTRY[liga]
        paises = paises_en(tramos) if tramos is not None else set()
        if not paises & ({esperado} | COUNTRY_ALT.get(esperado, set())):
            avisos.append(f"{squad} -> {name}: clubelo lo pone en {sorted(paises)}, "
                          f"no en {esperado}")
        elif tramos is not None and 1 not in set(tramos["Level"]):
            avisos.append(f"{squad} -> {name}: clubelo no lo tiene en primera "
                          f"división en {season} (niveles {sorted(set(tramos['Level']))})")

        filas.append({
            "Squad": squad,
            "liga": liga,
            "elo_club": name,
            "elo_pre": elo_en(hist, pre_dia),
            "elo_medio": medio,
            "elo_fin": elo_en(hist, fin_dia),
        })

    df = pd.DataFrame(filas)
    df["temporada"] = season
    df = df[["temporada", "Squad", "liga", "elo_club", "elo_pre", "elo_medio", "elo_fin"]]
    return df, avisos


def verificar(season, df):
    """Cruza contra el ranking del día: los clubes que clubelo pone en primera
    de ese país a mitad de temporada tienen que ser EXACTAMENTE los que
    resolvimos. Es la comprobación fuerte del mapeo de nombres — no solo que
    cada nombre exista, sino que no falte ni sobre ninguno."""
    dia = f"{int(season[:4]) + 1}-03-01"
    snap = pd.read_csv(io.StringIO(pedir(f"{API}/{dia}")))
    time.sleep(DELAY_SECONDS)

    problemas = []
    for liga in LEAGUE_ORDER:
        nuestros = set(df[df["liga"] == liga]["elo_club"])
        suyos = set(snap[(snap["Country"] == COUNTRY[liga]) & (snap["Level"] == 1)]["Club"])
        if nuestros != suyos:
            problemas.append(f"  {liga}: nos sobran {sorted(nuestros - suyos) or '—'} · "
                             f"nos faltan {sorted(suyos - nuestros) or '—'}")
    print(f"  verificación contra el ranking del {dia}: " +
          ("OK, los 5 conjuntos coinciden" if not problemas else "\n" + "\n".join(problemas)))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    force = "--force" in sys.argv
    con_verificacion = "--verificar" in sys.argv
    seasons = args or SEASONS

    for season in seasons:
        resultado = temporada(season, force=force)
        if resultado is None:
            print(f"{season}: falta data/{season}/{SOURCE_FILE}, se salta")
            continue
        df, avisos = resultado

        out = DATA_DIR / season / OUT_FILE
        df.to_csv(out, index=False, encoding="utf-8-sig")
        faltan = int(df[["elo_pre", "elo_medio", "elo_fin"]].isna().any(axis=1).sum())
        print(f"{season}: {out.relative_to(DATA_DIR.parent)}  ({len(df)} equipos"
              + (f", {faltan} con algún ELO vacío" if faltan else "") + ")")
        for a in avisos:
            print(f"  ojo: {a}")
        if con_verificacion:
            verificar(season, df)


if __name__ == "__main__":
    main()
