"""Consolida los CSV crudos de todas las temporadas en dos tablas únicas.

Entrada  — `data/<temporada>/` con los archivos tal cual se bajan:
             leagues_{overall,shoot,playtime,misc,gk}.csv  (fbref, equipos)
             {premier,laliga,seriea,bundes,ligue1}-players.csv  (Understat, jugadores)

Salida   — `data/processed/`:
             teams_all_seasons.{csv,xlsx}    una fila por equipo y temporada,
                                             las 5 tablas de fbref unidas a lo ancho
             players_all_seasons.{csv,xlsx}  una fila por jugador, liga y temporada

Las temporadas que todavía no estén descargadas se saltan con un aviso, así que
el script se puede correr hoy con una sola temporada y otra vez cuando estén las
cinco. Uso:  python consolidate_data.py
"""

import html
import unicodedata
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OUT_DIR = DATA_DIR / "processed"

SEASONS = ["2021-22", "2022-23", "2023-24", "2024-25", "2025-26"]

# fbref concatena las 5 ligas en este orden, sin columna que las identifique
LEAGUE_ORDER = ["Bundesliga", "Serie A", "Ligue 1", "La Liga", "Premier League"]

TEAM_FILES = {
    "ov": "leagues_overall.csv",
    "sh": "leagues_shoot.csv",
    "pt": "leagues_playtime.csv",
    "ms": "leagues_misc.csv",
    "gk": "leagues_gk.csv",
}

# Las mismas 5 tablas pero en versión "vs equipo": lo que los rivales le hacen a
# cada equipo (`vs_ms_Performance_Crs` = centros que le tiran en contra). Son
# opcionales — solo existen en las temporadas bajadas con `fetch_fbref.py`, no
# en las exportadas a mano — así que si faltan la temporada se procesa igual.
VS_FILES = {
    "vs_ov": "leagues_overall_vs.csv",
    "vs_sh": "leagues_shoot_vs.csv",
    "vs_pt": "leagues_playtime_vs.csv",
    "vs_ms": "leagues_misc_vs.csv",
    "vs_gk": "leagues_gk_vs.csv",
}

PLAYER_FILES = {
    "bundes-players.csv": "Bundesliga",
    "seriea-players.csv": "Serie A",
    "ligue1-players.csv": "Ligue 1",
    "laliga-players.csv": "La Liga",
    "premier-players.csv": "Premier League",
}

# Cuántos equipos tiene cada liga en cada temporada. Solo se usa como
# verificación cruzada de la detección automática: si los dos métodos no
# coinciden, el script para en vez de escribir una liga equivocada.
# Ligue 1 se redujo de 20 a 18 equipos en 2023-24; el resto no cambió.
EXPECTED_SIZES = {
    "2021-22": [18, 20, 20, 20, 20],
    "2022-23": [18, 20, 20, 20, 20],
    "2023-24": [18, 20, 18, 20, 20],
    "2024-25": [18, 20, 18, 20, 20],
    "2025-26": [18, 20, 18, 20, 20],
}


def _sort_key(name):
    """Clave de orden insensible a acentos: 'Cádiz' tiene que caer entre
    'Betis' y 'Celta', no después de 'Villarreal' (que es donde lo manda
    comparar por codepoint, porque 'á' vale más que cualquier letra ASCII)."""
    decomposed = unicodedata.normalize("NFKD", str(name))
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()


def split_league_blocks(squads, season):
    """Devuelve la columna `liga` para un archivo de fbref.

    El archivo son las 5 tablas de liga pegadas una debajo de otra, y cada una
    viene ordenada alfabéticamente — así que un cambio de liga es exactamente
    donde el orden alfabético se rompe. Es preferible a hardcodear los tamaños
    porque estos cambian entre temporadas (Ligue 1 pasó de 20 a 18 equipos).
    """
    squads = [str(s) for s in squads]
    cuts = [0] + [i for i in range(1, len(squads)) if _sort_key(squads[i]) < _sort_key(squads[i - 1])]

    if len(cuts) != len(LEAGUE_ORDER):
        raise ValueError(
            f"{season}: se detectaron {len(cuts)} bloques de liga en vez de 5 "
            f"(cortes en las filas {cuts}, empezando por {[squads[c] for c in cuts]}). "
            "El archivo puede no estar en el orden Bundesliga → Serie A → Ligue 1 → "
            "La Liga → Premier League, o alguna liga no venir ordenada alfabéticamente."
        )

    sizes = [b - a for a, b in zip(cuts, cuts[1:] + [len(squads)])]
    expected = EXPECTED_SIZES.get(season)
    if expected and sizes != expected:
        raise ValueError(
            f"{season}: los bloques detectados {sizes} no coinciden con los esperados "
            f"{expected}. Revisa el archivo, o corrige EXPECTED_SIZES si el dato "
            "esperado es el que está mal."
        )

    return [liga for liga, n in zip(LEAGUE_ORDER, sizes) for _ in range(n)]


def flatten_columns(raw):
    """Aplana el header de dos filas de fbref: ('Per 90 Minutes', 'Gls') pasa a
    'Per 90 Minutes_Gls', y los grupos vacíos ('Unnamed: 0_level_0', 'Squad')
    quedan solo con la métrica."""
    cols = []
    for top, bot in raw.columns:
        top = "" if str(top).startswith("Unnamed") else str(top).strip()
        bot = str(bot).strip()
        cols.append(f"{top}_{bot}" if top else bot)
    raw.columns = cols
    return raw


def load_teams_season(season_dir, season):
    """Las 5 tablas de fbref de una temporada, unidas a lo ancho por equipo.

    Cada tabla lleva su prefijo (`ov_`, `sh_`, `pt_`, `ms_`, `gk_`) igual que en
    los notebooks, así que columnas repetidas entre archivos (`# Pl`, `90s`,
    `Age`, `MP`...) conviven sin pisarse y el código existente sigue sirviendo.
    """
    disponibles = {**TEAM_FILES, **{t: f for t, f in VS_FILES.items() if (season_dir / f).exists()}}

    frames = {}
    for tag, fname in disponibles.items():
        raw = flatten_columns(pd.read_csv(season_dir / fname, header=[0, 1]))
        raw["liga"] = split_league_blocks(raw["Squad"], season)
        stat_cols = [c for c in raw.columns if c not in ("Squad", "liga")]
        frames[tag] = raw.rename(columns={c: f"{tag}_{c}" for c in stat_cols})

    df = frames["ov"]
    for tag in [t for t in disponibles if t != "ov"]:
        other = frames[tag]
        # la liga ya vino de `ov`; acá solo se comprueba que los otros archivos
        # traigan los mismos equipos en el mismo orden antes de descartarla
        if not other["Squad"].equals(df["Squad"]):
            faltan = set(df["Squad"]) ^ set(other["Squad"])
            raise ValueError(
                f"{season}: {disponibles[tag]} no trae los mismos equipos que "
                f"leagues_overall.csv (difieren: {sorted(faltan) or 'solo el orden'})"
            )
        df = df.merge(other.drop(columns=["liga"]), on="Squad", how="left")

    df = df.copy()  # desfragmenta tras los merges, si no `insert` avisa
    df.insert(0, "temporada", season)
    df.insert(2, "liga", df.pop("liga"))
    return df


def load_players_season(season_dir, season):
    """Los 5 CSV de Understat de una temporada, apilados con liga y temporada.

    Se corrigen las entidades HTML de los nombres (`O&#039;Reilly`), que es un
    defecto del export. NO se toca `team`: los jugadores que cambiaron de club
    traen los dos separados por coma ('Bournemouth,Manchester City') y quedarse
    con uno u otro es una decisión de análisis, no de consolidación.
    """
    dfs = []
    for fname, liga in PLAYER_FILES.items():
        d = pd.read_csv(season_dir / fname, sep=";", encoding="utf-8-sig")
        d["player"] = d["player"].apply(html.unescape)
        d.insert(0, "temporada", season)
        d.insert(1, "liga", liga)
        dfs.append(d)
    return pd.concat(dfs, ignore_index=True)


def load_shots_season(season_dir, season):
    """Los tiros de una temporada (`fetch_shots.py`). Ya vienen con `temporada`
    y `liga`, así que no hay nada que derivar acá."""
    return pd.read_csv(season_dir / "shots.csv", encoding="utf-8-sig")


def write(df, stem, excel=True):
    """Escribe CSV y Excel. El CSV es el que deberían leer los notebooks (no
    depende de openpyxl y se versiona bien en git); el Excel es para revisarlo
    a mano."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = OUT_DIR / f"{stem}.csv"
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"  {csv_path.relative_to(DATA_DIR.parent)}  ({len(df)} filas x {df.shape[1]} columnas)")
    if excel:
        xlsx_path = OUT_DIR / f"{stem}.xlsx"
        df.to_excel(xlsx_path, index=False, sheet_name=stem[:31])
        print(f"  {xlsx_path.relative_to(DATA_DIR.parent)}")


def main():
    teams, players, shots, faltantes = [], [], [], []

    for season in SEASONS:
        season_dir = DATA_DIR / season
        presentes = [f for f in list(TEAM_FILES.values()) + list(PLAYER_FILES)
                     if (season_dir / f).exists()]
        if not presentes:
            faltantes.append(season)
            continue

        print(f"{season}:")
        if all((season_dir / f).exists() for f in TEAM_FILES.values()):
            t = load_teams_season(season_dir, season)
            teams.append(t)
            con_vs = sum((season_dir / f).exists() for f in VS_FILES.values())
            print(f"  equipos   {len(t):4d}  " +
                  " · ".join(f"{k} {v}" for k, v in t['liga'].value_counts()[LEAGUE_ORDER].items()) +
                  (f"  (+{con_vs} tablas vs)" if con_vs else "  (sin tablas vs)"))
        else:
            print("  equipos   faltan archivos leagues_*.csv, se salta")

        if all((season_dir / f).exists() for f in PLAYER_FILES):
            p = load_players_season(season_dir, season)
            players.append(p)
            print(f"  jugadores {len(p):4d}")
        else:
            print("  jugadores faltan archivos *-players.csv, se salta")

        if (season_dir / "shots.csv").exists():
            s = load_shots_season(season_dir, season)
            shots.append(s)
            print(f"  tiros     {len(s):5d}")

    if faltantes:
        print(f"\nSin descargar todavía: {', '.join(faltantes)}")

    print("\nEscrito:")
    if teams:
        write(pd.concat(teams, ignore_index=True), "teams_all_seasons")
    if players:
        write(pd.concat(players, ignore_index=True), "players_all_seasons")
    if shots:
        # sin Excel: son ~250.000 tiros, un .xlsx de ese tamaño pesa decenas de
        # MB y tarda minutos en abrir, y no es una tabla que se mire a mano
        write(pd.concat(shots, ignore_index=True), "shots_all_seasons", excel=False)
    if not teams and not players:
        print("  nada — no se encontró ninguna temporada en data/")


if __name__ == "__main__":
    main()
