"""Descarga la tabla *standard* de jugador de fbref y la deja en
`data/<temporada>/fbref-players.csv`.

Para qué: Understat no publica edad ni fecha de nacimiento, así que el año de
nacimiento (`born`) tiene que venir de fbref. Es la única columna que este
script existe para traer; el resto se guarda porque ya viene en la misma tabla
y sirve para verificar el cruce.

Por qué `born` y no `age`: la `age` de fbref es la edad a una fecha de corte
suya, así que el mismo jugador cambia de valor según cuándo se scrapeó la
página. `born` es fijo, y "sub-21 en tal temporada" se deriva de él sin
ambigüedad — ver `edad_en_temporada()` en `consolidate_data.py`.

Por qué la URL se arma a mano y no se usa `FBref.read_player_season_stats()`:
ese método pide primero el índice de temporadas de la liga
(`/comps/11/history/Serie-A-Seasons`), y el de Serie A no baja nunca — con lo
cual esa liga entera quedaba inaccesible aunque sus páginas de temporada estén
perfectamente disponibles. La URL de la tabla es derivable del id de la
competición, así que se construye directo y el índice deja de ser un
prerrequisito. `soccerdata` se sigue usando como *fetcher* (es lo que resuelve
el reto de Cloudflare), igual que en `fetch_fbref.py`, del que se reutiliza el
navegador ya abierto.

Se valida el HTML antes de aceptarlo: cuando el navegador se cae, a veces
devuelve el contenido de un iframe de publicidad en vez de la página. Eso pesa
~200 KB, no contiene la tabla, y si se acepta queda cacheado e inutiliza esa
liga-temporada para siempre.

Uso:
    python fetch_fbref_players.py                 # todo lo que falte
    python fetch_fbref_players.py 2023-24         # solo esa temporada
    python fetch_fbref_players.py --force 2025-26 # re-baja aunque ya exista el CSV
    python fetch_fbref_players.py --intentos 6    # más reintentos por página
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

SEASONS = ["2021-22", "2022-23", "2023-24", "2024-25", "2025-26"]

# liga -> (id de competición en fbref, slug de la URL). Mismos ids que
# `fetch_fbref.py`; el orden del dict es el que se usa al recorrer.
LEAGUES = {
    "Bundesliga": (20, "Bundesliga"),
    "Serie A": (11, "Serie-A"),
    "Ligue 1": (13, "Ligue-1"),
    "La Liga": (12, "La-Liga"),
    "Premier League": (9, "Premier-League"),
}

COLUMN_ORDER = ["liga", "player", "team", "nation", "pos", "age", "born", "mp", "min"]

TABLE_ID = "stats_standard"
INTENTOS = 4
ESPERA = 6  # segundos entre reintentos


def season_to_fbref(season):
    """'2024-25' -> '2024-2025', que es como fbref arma sus URLs."""
    inicio, fin = season.split("-")
    return f"{inicio}-{inicio[:2]}{fin}"


def page_url(liga, season):
    cid, slug = LEAGUES[liga]
    fb = season_to_fbref(season)
    return f"https://fbref.com/en/comps/{cid}/{fb}/stats/{fb}-{slug}-Stats"


def _cache_file(liga, season):
    _, slug = LEAGUES[liga]
    return CACHE_DIR / f"{season}_{slug}_players.html"


def paginable(texto):
    """¿Esto es de verdad la página que se pidió? El fallo típico no es un
    error de red sino una página que no es la buscada (un iframe de
    publicidad), y esa diferencia no la delata ningún código HTTP."""
    return texto is not None and len(texto) > 500_000 and TABLE_ID in texto


def fetch_page(liga, season, intentos=INTENTOS):
    """HTML de la página de jugadores, cacheado en disco. None si no se pudo.

    Las temporadas cerradas no cambian, así que una vez bajada y validada no se
    vuelve a pedir nunca."""
    import fetch_fbref  # reusa el navegador que ya pasó Cloudflare

    cached = _cache_file(liga, season)
    if cached.exists():
        texto = cached.read_text(encoding="utf-8", errors="replace")
        if paginable(texto):
            return texto
        print(f"      caché inservible ({cached.stat().st_size // 1024} KB), se descarta")
        cached.unlink()

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    url = page_url(liga, season)
    for intento in range(1, intentos + 1):
        try:
            with fetch_fbref.get_reader().get(url, filepath=cached, max_age=3650) as fh:
                texto = fh.read()
            if isinstance(texto, bytes):
                texto = texto.decode("utf-8", errors="replace")
            motivo = f"no trae la tabla ({len(texto) // 1024} KB)"
        except Exception as exc:
            texto, motivo = None, f"{type(exc).__name__}: {str(exc)[:60]}"

        if paginable(texto):
            return texto

        # Sin esto el intento siguiente re-lee la basura del disco en vez de
        # volver a pedir la página.
        cached.unlink(missing_ok=True)
        print(f"      intento {intento}/{intentos} falló: {motivo}", flush=True)
        if intento < intentos:
            time.sleep(ESPERA)
    return None


def parse_players(texto, liga, contexto):
    """La tabla de jugadores, con las columnas que interesan.

    fbref envuelve todas las tablas menos la primera en comentarios HTML, así
    que hay que destaparlas antes de buscarlas — misma razón que en
    `fetch_fbref.extract_table`."""
    plain = texto.replace("<!--", "").replace("-->", "")
    match = re.search(rf'<table[^>]*id="{TABLE_ID}".*?</table>', plain, re.S)
    if match is None:
        raise ValueError(f"{contexto}: no se encontró la tabla '{TABLE_ID}'")

    df = pd.read_html(io.StringIO(match.group(0)), header=[0, 1])[0]
    df.columns = [bot if str(top).startswith("Unnamed") else f"{top}|{bot}"
                  for top, bot in df.columns]
    # fbref intercala filas de encabezado cada tantas filas en las tablas largas
    df = df[df["Player"].astype(str) != "Player"].copy()
    df = df.rename(columns={
        "Player": "player", "Squad": "team", "Nation": "nation", "Pos": "pos",
        "Age": "age", "Born": "born", "Playing Time|MP": "mp", "Playing Time|Min": "min",
    })
    df["liga"] = liga
    # 'it ITA' -> 'ITA': fbref antepone el código del ícono de la bandera
    df["nation"] = df["nation"].astype(str).str.split().str[-1].replace("nan", pd.NA)
    df["born"] = pd.to_numeric(df["born"], errors="coerce").astype("Int64")
    df["mp"] = pd.to_numeric(df["mp"], errors="coerce")
    df["min"] = pd.to_numeric(df["min"].astype(str).str.replace(",", ""), errors="coerce")
    return df[COLUMN_ORDER].reset_index(drop=True)


def ligas_en_csv(path):
    """Qué ligas ya tiene un CSV escrito — para completar lo que faltó en una
    corrida anterior en vez de empezar de cero."""
    if not path.exists():
        return set()
    try:
        return set(pd.read_csv(path, encoding="utf-8-sig")["liga"].dropna().unique())
    except Exception:
        return set()


def main():
    argv = sys.argv[1:]
    force = "--force" in argv
    intentos = INTENTOS
    if "--intentos" in argv:
        intentos = int(argv[argv.index("--intentos") + 1])
        argv.remove(str(intentos))
    seasons = [a for a in argv if not a.startswith("--")] or SEASONS

    desconocidas = [s for s in seasons if s not in SEASONS]
    if desconocidas:
        raise SystemExit(f"Temporada no reconocida: {desconocidas}. Válidas: {SEASONS}")

    todas = set(LEAGUES)
    incompletas = []

    for season in seasons:
        path = DATA_DIR / season / "fbref-players.csv"
        ya = set() if force else ligas_en_csv(path)
        faltan = [lg for lg in LEAGUES if lg not in ya]
        if not faltan:
            print(f"{season}: completa, se salta")
            continue

        print(f"{season}: faltan {len(faltan)} — {', '.join(faltan)}")
        nuevos = []
        for liga in faltan:
            print(f"    {liga:15s} ...", flush=True)
            texto = fetch_page(liga, season, intentos)
            if texto is None:
                print(f"      SIN DATOS tras {intentos} intentos")
                continue
            try:
                nuevos.append(parse_players(texto, liga, f"{season} {liga}"))
                print(f"      OK ({len(nuevos[-1])} jugadores)")
            except Exception as exc:
                print(f"      no se pudo parsear: {exc}")

        if not nuevos:
            print(f"  {season}: no se pudo bajar ninguna liga")
            incompletas.append(season)
            continue

        # Lo ya escrito se conserva: cada corrida suma las ligas que consiguió.
        previo = [pd.read_csv(path, encoding="utf-8-sig")] if (path.exists() and not force) else []
        out = (pd.concat(previo + nuevos, ignore_index=True)
               .sort_values(["liga", "team", "player"]).reset_index(drop=True))
        path.parent.mkdir(parents=True, exist_ok=True)
        out.to_csv(path, index=False, encoding="utf-8-sig")

        presentes = set(out["liga"].dropna().unique())
        sin_born = int(out["born"].isna().sum())
        print(f"  {season}: {len(out):5d} jugadores, {len(presentes)}/5 ligas" +
              (f", {sin_born} sin año de nacimiento" if sin_born else ""))
        if presentes != todas:
            print(f"    faltan todavía: {', '.join(sorted(todas - presentes))}")
            incompletas.append(season)

    if incompletas:
        print(f"\nIncompletas: {', '.join(incompletas)} — vuelve a correr el script "
              "para completarlas (lo ya bajado no se re-pide)")
    else:
        print("\nTodas las temporadas completas")


if __name__ == "__main__":
    main()
