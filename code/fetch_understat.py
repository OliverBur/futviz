"""Descarga las estadísticas de jugador de Understat para todas las temporadas
y las deja en `data/<temporada>/{liga}-players.csv`, con el mismo nombre,
separador y columnas que los CSV exportados a mano — más las que la exportación
de la web no traía.

Entrada equivalente (export manual):  number;player;team;apps;min;goals;a;xG;xA;xG90;xA90
Salida de acá: esas mismas, y además

    position       posición según Understat ('F M S' = delantero/medio/suplente)
    shots          tiros
    key_passes     pases clave
    np_goals       goles sin penales
    np_xg          xG sin penales
    yellow_cards / red_cards
    xg_chain       xG de todas las posesiones en las que participó
    xg_buildup     ídem, pero sin contar tiro ni asistencia (participación pura)

Mantener los nombres viejos es a propósito: `eda_players.ipynb` y
`web/charts/players.py` siguen funcionando sin tocarlos, y las columnas nuevas
quedan disponibles para lo que venga.

Por qué acá NO se usa `soccerdata` (a diferencia del resto del proyecto): el
26-09-2026 se detectó que understat.com rediseñó sus páginas de liga —
`playersData`/`teamsData`/`datesData` ya no vienen embebidos como JSON en el
HTML (que es lo único que sabe leer `soccerdata.Understat`, y por eso
`read_player_season_stats()` empezó a devolver 0 filas para CUALQUIER
temporada, no solo la nueva). Los datos ahora se cargan por AJAX desde el
propio navegador: `POST main/getPlayersStats/` con `{league, season}`
devuelve el mismo JSON de siempre, sin Cloudflare ni ningún desafío de por
medio (una request de `requests` sin sesión ni headers especiales ya alcanza).
Así que acá se pide ese endpoint directo, igual de espíritu a como
`fetch_fbref.py` ya usaba `soccerdata` solo como *fetcher* y no como parser.

`season` en ese endpoint es el año de arranque solo ('2024' para 2024-25, no
'2024-2025') y `league` es el nombre tal cual lo escribe Understat en la URL
('La_liga', 'Serie_A', 'Ligue_1', 'Bundesliga', 'EPL' — ver `LEAGUES`).

Uso:
    python fetch_understat.py                 # todas las temporadas que falten
    python fetch_understat.py 2023-24         # solo esa
    python fetch_understat.py --force 2025-26 # re-baja aunque ya exista el CSV
"""

import sys
import time
import warnings
from pathlib import Path

import pandas as pd
import requests

warnings.filterwarnings("ignore")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

SEASONS = ["2021-22", "2022-23", "2023-24", "2024-25", "2025-26", "2026-27"]

API = "https://understat.com/main/getPlayersStats/"
DELAY_SECONDS = 1.5
REINTENTOS = 4

# liga -> (código de Understat en la URL/POST, nombre de archivo)
LEAGUES = {
    "Bundesliga": ("Bundesliga", "bundes-players.csv"),
    "Serie A": ("Serie_A", "seriea-players.csv"),
    "Ligue 1": ("Ligue_1", "ligue1-players.csv"),
    "La Liga": ("La_liga", "laliga-players.csv"),
    "Premier League": ("EPL", "premier-players.csv"),
}

# JSON de Understat -> nombre en los CSV que ya usan los notebooks
RENAMES = {
    "player_name": "player",
    "team_title": "team",
    "games": "apps",
    "time": "min",
    "assists": "a",
    "npg": "np_goals",
    "npxG": "np_xg",
    "xGChain": "xg_chain",
    "xGBuildup": "xg_buildup",
}

NUMERIC_COLS = [
    "apps", "min", "goals", "a", "xG", "xA", "shots", "key_passes",
    "np_goals", "np_xg", "yellow_cards", "red_cards", "xg_chain", "xg_buildup",
]

# orden de columnas: primero las del export manual, después las nuevas
COLUMN_ORDER = [
    "number", "player", "team", "apps", "min", "goals", "a", "xG", "xA", "xG90", "xA90",
    "position", "shots", "key_passes", "np_goals", "np_xg",
    "yellow_cards", "red_cards", "xg_chain", "xg_buildup",
]


def season_code(season):
    """'2024-25' -> '2024', el año de arranque que espera este endpoint."""
    return season.split("-")[0]


def pedir_liga(codigo_liga, codigo_temporada):
    """Los jugadores de una liga-temporada, o [] si Understat no tiene nada
    todavía (p. ej. una temporada que no arrancó)."""
    for intento in range(1, REINTENTOS + 1):
        try:
            r = requests.post(
                API, data={"league": codigo_liga, "season": codigo_temporada},
                timeout=30,
            )
            r.raise_for_status()
            data = r.json()
            return data.get("players", []) if data.get("success") else []
        except (requests.RequestException, ValueError) as e:
            if intento == REINTENTOS:
                raise
            espera = DELAY_SECONDS * 4 * intento
            print(f"    {codigo_liga}/{codigo_temporada} falló ({type(e).__name__}), "
                  f"reintento {intento}/{REINTENTOS - 1} en {espera:.0f}s")
            time.sleep(espera)


def to_manual_format(players):
    """Lista de dicts de la API -> DataFrame con las columnas y el orden del
    export manual."""
    df = pd.DataFrame(players).rename(columns=RENAMES)
    for col in NUMERIC_COLS:
        df[col] = pd.to_numeric(df[col])

    # xG90 / xA90 no vienen en la API: Understat los muestra calculados. Se
    # reproducen acá. Los jugadores con 0 minutos quedan en NaN, no en infinito.
    noventas = df["min"] / 90
    df["xG90"] = (df["xG"] / noventas).where(noventas > 0).round(2)
    df["xA90"] = (df["xA"] / noventas).where(noventas > 0).round(2)

    # `number` era el ranking de la tabla web; se regenera por minutos jugados
    # para que la columna siga existiendo y signifique algo
    df = df.sort_values("min", ascending=False).reset_index(drop=True)
    df["number"] = range(1, len(df) + 1)

    return df[COLUMN_ORDER]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    force = "--force" in sys.argv
    seasons = args or SEASONS

    desconocidas = [s for s in seasons if s not in SEASONS]
    if desconocidas:
        raise SystemExit(f"Temporada no reconocida: {desconocidas}. Válidas: {SEASONS}")

    pendientes = [
        s for s in seasons
        if force or not all((DATA_DIR / s / f).exists() for _, f in LEAGUES.values())
    ]
    if not pendientes:
        print("Todas las temporadas pedidas ya tienen sus CSV (usa --force para rehacerlos)")
        return

    print(f"Descargando Understat: {', '.join(pendientes)}")
    escritos = 0
    for season in pendientes:
        out_dir = DATA_DIR / season
        out_dir.mkdir(parents=True, exist_ok=True)
        codigo = season_code(season)

        print(f"  {season}:")
        for liga, (codigo_liga, fname) in LEAGUES.items():
            players = pedir_liga(codigo_liga, codigo)
            time.sleep(DELAY_SECONDS)
            if not players:
                print(f"    {fname:22s} SIN DATOS")
                continue
            out = to_manual_format(players)
            out.to_csv(out_dir / fname, sep=";", index=False, encoding="utf-8-sig")
            escritos += 1
            print(f"    {fname:22s} {len(out):4d} jugadores")

    print(f"\n{escritos} CSV escritos. Siguiente paso: python consolidate_data.py")


if __name__ == "__main__":
    main()
