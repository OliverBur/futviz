"""Descarga las tablas de equipo de fbref y las deja en `data/<temporada>/`
con el mismo formato que los CSV exportados a mano, para que
`consolidate_data.py` funcione sin cambios.

Por qué vía `soccerdata` y no `requests`: fbref está detrás de Cloudflare Bot
Management y devuelve 403 a urllib, a curl y hasta a un Chromium headless
("Just a moment..."). `soccerdata` resuelve el reto, cachea el HTML y espacia
las peticiones. Acá se usa solo como *fetcher*: el parseo de las tablas es
propio, porque su lector de equipos cubre las mismas 5 tablas de siempre y no
las versiones "vs equipo".

Qué baja, por liga y temporada — las 10 tablas de plantilla que fbref todavía
publica gratis, en versión propia (`for`) y recibida (`against`):

    standard · shooting · playing_time · misc · keeper

Las tablas avanzadas (Passing, Pass Types, Possession, Defensive Actions, Goal
and Shot Creation, Advanced Goalkeeping) y el xG **ya no están** en las páginas
de temporada de fbref; para xG hay que ir a Understat.

Uso:
    python fetch_fbref.py                 # todas las temporadas que falten
    python fetch_fbref.py 2023-24 2022-23 # solo esas
    python fetch_fbref.py --force 2024-25 # re-baja aunque ya existan los CSV
"""

import io
import re
import sys
import time
import warnings
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CACHE_DIR = DATA_DIR / ".fbref_html"

# Orden en que se concatenan las ligas dentro de cada CSV — es el mismo que
# asumen los notebooks y el que `consolidate_data.py` verifica al detectar los
# bloques, así que no se puede cambiar sin tocar los dos.
LEAGUES = [
    ("Bundesliga", 20, "Bundesliga"),
    ("Serie A", 11, "Serie-A"),
    ("Ligue 1", 13, "Ligue-1"),
    ("La Liga", 12, "La-Liga"),
    ("Premier League", 9, "Premier-League"),
]

# archivo de salida -> id de la tabla en el HTML de fbref
TABLES = {
    "leagues_overall": "stats_squads_standard_for",
    "leagues_shoot": "stats_squads_shooting_for",
    "leagues_playtime": "stats_squads_playing_time_for",
    "leagues_misc": "stats_squads_misc_for",
    "leagues_gk": "stats_squads_keeper_for",
    "leagues_overall_vs": "stats_squads_standard_against",
    "leagues_shoot_vs": "stats_squads_shooting_against",
    "leagues_playtime_vs": "stats_squads_playing_time_against",
    "leagues_misc_vs": "stats_squads_misc_against",
    "leagues_gk_vs": "stats_squads_keeper_against",
}

SEASONS = ["2021-22", "2022-23", "2023-24", "2024-25", "2025-26"]

DELAY_SECONDS = 4  # entre páginas nuevas; las cacheadas no esperan
_reader = None


def season_to_fbref(season):
    """'2024-25' -> '2024-2025', que es como fbref arma sus URLs."""
    inicio, fin = season.split("-")
    return f"{inicio}-{inicio[:2]}{fin}"


def get_reader():
    """Una sola instancia de soccerdata para toda la corrida: levantar el
    navegador es lo caro, y así se reusa la sesión que ya pasó Cloudflare."""
    global _reader
    if _reader is None:
        import soccerdata as sd

        _reader = sd.FBref(leagues="ENG-Premier League", seasons="2024-2025")
    return _reader


def fetch_page(liga, comp_id, slug, season):
    """HTML de la página de temporada de una liga, cacheado en disco.

    Las temporadas cerradas no cambian, así que una vez bajada la página no se
    vuelve a pedir nunca (`max_age` largo)."""
    fb_season = season_to_fbref(season)
    url = f"https://fbref.com/en/comps/{comp_id}/{fb_season}/{fb_season}-{slug}-Stats"
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cached = CACHE_DIR / f"{season}_{slug}.html"

    if cached.exists():
        print(f"    {liga:15s} (caché)")
        return cached.read_text(encoding="utf-8")

    print(f"    {liga:15s} descargando...", flush=True)
    reader = get_reader()
    with reader.get(url, filepath=cached, max_age=3650) as fh:
        html = fh.read()
    if isinstance(html, bytes):
        html = html.decode("utf-8", errors="replace")
    time.sleep(DELAY_SECONDS)
    return html


def extract_table(html, table_id, contexto):
    """Saca una tabla del HTML y la devuelve con el header de dos filas.

    fbref envuelve todas las tablas salvo la primera en comentarios HTML, así
    que hay que destaparlas antes de buscarlas — es la razón por la que un
    `pd.read_html` directo sobre la página solo encuentra una."""
    plain = html.replace("<!--", "").replace("-->", "")
    match = re.search(rf'<table[^>]*id="{table_id}".*?</table>', plain, re.S)
    if match is None:
        raise ValueError(f"{contexto}: no se encontró la tabla '{table_id}' en la página")

    df = pd.read_html(io.StringIO(match.group(0)), header=[0, 1])[0]

    # fbref intercala filas de header cada tantas filas en las tablas largas
    squad_col = df.columns[0]
    df = df[df[squad_col].astype(str) != "Squad"].reset_index(drop=True)

    # en las tablas "against" cada equipo viene como "vs Arsenal": se le quita
    # el prefijo para que cruce por nombre con las tablas propias
    df[squad_col] = df[squad_col].astype(str).str.removeprefix("vs ").str.strip()

    # el nivel superior de las columnas sin grupo viene como 'Unnamed: N_level_0';
    # se vacía para que el CSV salga con la celda en blanco, igual que el export
    # manual de fbref
    df.columns = pd.MultiIndex.from_tuples(
        [("" if str(top).startswith("Unnamed") else top, bot) for top, bot in df.columns]
    )
    return df


def build_season(season, force=False):
    """Escribe los 10 CSV de una temporada. Devuelve cuántos escribió."""
    out_dir = DATA_DIR / season
    out_dir.mkdir(parents=True, exist_ok=True)

    pendientes = [n for n in TABLES if force or not (out_dir / f"{n}.csv").exists()]
    if not pendientes:
        print(f"  ya están los 10 CSV, se salta (usa --force para rehacerlos)")
        return 0

    pages = {liga: fetch_page(liga, cid, slug, season) for liga, cid, slug in LEAGUES}

    escritos = 0
    for nombre in pendientes:
        table_id = TABLES[nombre]
        bloques = []
        for liga, _, _ in LEAGUES:
            df = extract_table(pages[liga], table_id, f"{season} {liga}")
            bloques.append(df)

        full = pd.concat(bloques, ignore_index=True)
        # todas las ligas tienen que traer las mismas columnas o el concat
        # habría rellenado con NaN sin avisar
        anchos = {len(b.columns) for b in bloques}
        if len(anchos) != 1:
            raise ValueError(f"{season} {nombre}: las ligas traen distinto nº de columnas: {anchos}")

        full.to_csv(out_dir / f"{nombre}.csv", index=False, encoding="utf-8")
        escritos += 1
        print(f"    {nombre + '.csv':24s} {full.shape[0]:3d} equipos x {full.shape[1]} columnas")

    return escritos


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    force = "--force" in sys.argv
    seasons = args or SEASONS

    desconocidas = [s for s in seasons if s not in SEASONS]
    if desconocidas:
        raise SystemExit(f"Temporada no reconocida: {desconocidas}. Válidas: {SEASONS}")

    total = 0
    for season in seasons:
        print(f"\n{season}  ({season_to_fbref(season)})")
        total += build_season(season, force=force)

    print(f"\n{total} CSV escritos. Siguiente paso: python consolidate_data.py")


if __name__ == "__main__":
    main()
