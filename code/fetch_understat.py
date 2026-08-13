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

Uso:
    python fetch_understat.py                 # todas las temporadas que falten
    python fetch_understat.py 2023-24         # solo esa
    python fetch_understat.py --force 2025-26 # re-baja aunque ya exista el CSV
"""

import sys
import warnings
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

SEASONS = ["2021-22", "2022-23", "2023-24", "2024-25", "2025-26"]

# liga en soccerdata -> nombre del archivo, igual que el export manual
LEAGUE_FILES = {
    "GER-Bundesliga": "bundes-players.csv",
    "ITA-Serie A": "seriea-players.csv",
    "FRA-Ligue 1": "ligue1-players.csv",
    "ESP-La Liga": "laliga-players.csv",
    "ENG-Premier League": "premier-players.csv",
}

# soccerdata -> nombre en los CSV que ya usan los notebooks
RENAMES = {
    "matches": "apps",
    "minutes": "min",
    "assists": "a",
    "xg": "xG",
    "xa": "xA",
}

# orden de columnas: primero las del export manual, después las nuevas
COLUMN_ORDER = [
    "number", "player", "team", "apps", "min", "goals", "a", "xG", "xA", "xG90", "xA90",
    "position", "shots", "key_passes", "np_goals", "np_xg",
    "yellow_cards", "red_cards", "xg_chain", "xg_buildup",
]


def season_to_understat(season):
    """'2024-25' -> '2024-2025', el formato que espera soccerdata."""
    inicio, fin = season.split("-")
    return f"{inicio}-{inicio[:2]}{fin}"


def fetch(seasons):
    """Una sola llamada para todas las ligas y temporadas pedidas: soccerdata
    cachea por liga-temporada, así que re-correr no vuelve a pedir nada."""
    import soccerdata as sd

    us = sd.Understat(
        leagues=list(LEAGUE_FILES),
        seasons=[season_to_understat(s) for s in seasons],
    )
    return us.read_player_season_stats().reset_index()


def to_manual_format(df):
    """Deja el DataFrame con las columnas y el orden del export manual."""
    df = df.rename(columns=RENAMES).copy()

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
        if force or not all((DATA_DIR / s / f).exists() for f in LEAGUE_FILES.values())
    ]
    if not pendientes:
        print("Todas las temporadas pedidas ya tienen sus CSV (usa --force para rehacerlos)")
        return

    print(f"Descargando Understat: {', '.join(pendientes)}")
    raw = fetch(pendientes)
    print(f"  {len(raw)} filas de jugador-temporada en bruto")

    escritos = 0
    for season in pendientes:
        out_dir = DATA_DIR / season
        out_dir.mkdir(parents=True, exist_ok=True)
        codigo = season.split("-")[0][2:] + season.split("-")[1]  # '2024-25' -> '2425'

        sub_season = raw[raw["season"].astype(str) == codigo]
        if sub_season.empty:
            print(f"  {season}: sin datos (¿temporada fuera de la cobertura de Understat?)")
            continue

        print(f"  {season}:")
        for liga, fname in LEAGUE_FILES.items():
            sub = sub_season[sub_season["league"] == liga]
            if sub.empty:
                print(f"    {fname:22s} SIN DATOS")
                continue
            out = to_manual_format(sub)
            out.to_csv(out_dir / fname, sep=";", index=False, encoding="utf-8-sig")
            escritos += 1
            print(f"    {fname:22s} {len(out):4d} jugadores")

    print(f"\n{escritos} CSV escritos. Siguiente paso: python consolidate_data.py")


if __name__ == "__main__":
    main()
