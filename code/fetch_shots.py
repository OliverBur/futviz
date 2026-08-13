"""Descarga los eventos de tiro de Understat y los deja en
`data/<temporada>/shots.csv` — un renglón por tiro, con coordenadas.

Es lo más parecido a datos de evento que se puede conseguir gratis: WhoScored
tiene el stream completo pero se cuelga al scrapearlo (se probó headless y con
navegador visible; en 20 minutos no bajó ni un partido) y además serían ~8.750
páginas, una por partido.

Qué trae cada tiro:

    location_x / location_y   posición en la cancha, normalizada 0-1
    situation                 Open Play · From Corner · Set Piece · Direct Freekick
    body_part                 pie derecho / izquierdo / cabeza / otro
    result                    gol, atajado, fuera, bloqueado, al palo
    xg                        xG de ese tiro concreto
    minute, player, assist_player
    rival                     el equipo que CONCEDIÓ el tiro

`rival` se agrega acá porque es pura contabilidad (en cada partido hay dos
equipos, así que el que no tiró es el que concedió) y sin él no se puede armar
el perfil defensivo, que es la mitad interesante: dónde y de qué situación te
rematan.

Lo que NO se calcula acá, a propósito, porque son decisiones de análisis y no de
descarga: distancia a puerta (depende de qué dimensiones de cancha asumas) y
cualquier agregado por equipo.

Tarda ~5 min por liga-temporada (~2 h las 25). Va escribiendo temporada por
temporada, así que si se corta, lo ya bajado queda; y soccerdata cachea, o sea
que volver a correrlo no re-descarga nada.

Uso:
    python fetch_shots.py                 # todas las temporadas que falten
    python fetch_shots.py 2023-24         # solo esa
    python fetch_shots.py --force 2024-25 # rehace el CSV aunque ya exista
"""

import sys
import time
import warnings
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

SEASONS = ["2021-22", "2022-23", "2023-24", "2024-25", "2025-26"]

# liga en soccerdata -> nombre que usa el resto del proyecto
LEAGUES = {
    "GER-Bundesliga": "Bundesliga",
    "ITA-Serie A": "Serie A",
    "FRA-Ligue 1": "Ligue 1",
    "ESP-La Liga": "La Liga",
    "ENG-Premier League": "Premier League",
}

COLUMNS = [
    "temporada", "liga", "game_id", "date", "team", "rival",
    "player", "assist_player", "minute", "situation", "body_part", "result",
    "xg", "location_x", "location_y", "shot_id", "player_id", "team_id",
]


def season_to_understat(season):
    """'2024-25' -> '2024-2025'."""
    inicio, fin = season.split("-")
    return f"{inicio}-{inicio[:2]}{fin}"


def add_rival(df):
    """El equipo que concedió cada tiro.

    En cada partido hay exactamente dos equipos entre los tiros, así que el
    rival del que tiró es el otro. Si un partido quedara con un solo equipo
    (nadie remató en todo el partido, rarísimo), esos tiros conservan `rival`
    vacío en vez de desaparecer.
    """
    pares = df.groupby("game_id")["team"].unique()
    mapa = {g: {t[0]: t[1], t[1]: t[0]} for g, t in pares.items() if len(t) == 2}
    df["rival"] = [mapa.get(g, {}).get(t) for g, t in zip(df["game_id"], df["team"])]
    return df


INTENTOS = 3  # los timeouts contra understat son frecuentes y transitorios

# Partidos que Understat sirve malformados, acumulados durante la corrida.
PARTIDOS_SALTADOS = []


def parchear_mapeos():
    """Recupera cabezazos y penales, que soccerdata 1.9.0 tira a nulo.

    Sus diccionarios de traducción están incompletos frente a lo que sirve
    Understat: `SHOT_BODY_PARTS` no contempla `Head` y escribe `OtherBodyParts`
    donde la API manda `OtherBodyPart` (singular), y `SHOT_SITUATIONS` no
    contempla `Penalty`. Todo lo que no está en el diccionario se convierte en
    `pd.NA`, así que ~17% de los tiros perdían la parte del cuerpo y los penales
    perdían la situación — dos features de primer orden para un modelo de xG.
    """
    from soccerdata import understat as us_mod

    us_mod.SHOT_BODY_PARTS.update({"Head": "Head", "OtherBodyPart": "Other"})
    us_mod.SHOT_SITUATIONS.update({"Penalty": "Penalty"})


def parchear_soccerdata():
    """Evita que un partido malformado tumbe la liga-temporada entera.

    Para algunos partidos Understat devuelve el roster como lista vacía (`[]`)
    en vez de diccionario — es cómo PHP serializa un array asociativo vacío. El
    parser de soccerdata hace `rosters["h"].values()` sin comprobarlo y revienta
    con `AttributeError`, perdiendo las ~300 jornadas restantes por un partido.

    `_read_match` ya tiene un contrato para "este partido no se puede leer":
    devolver `None`, que el llamador saltea con `if data is None: continue`. El
    parche solo traduce la excepción a ese contrato, y anota cuál fue para que
    el hueco quede reportado y no silencioso.
    """
    from soccerdata.understat import Understat

    if getattr(Understat._read_match, "_parcheado", False):
        return
    original = Understat._read_match

    def _read_match(self, url, match_id, *args, **kwargs):
        try:
            return original(self, url, match_id, *args, **kwargs)
        except AttributeError:
            PARTIDOS_SALTADOS.append(match_id)
            return None

    _read_match._parcheado = True
    Understat._read_match = _read_match


def fetch_league_season(liga_sd, season):
    """Una liga-temporada, reintentando ante fallos de red.

    soccerdata cachea partido por partido, así que un reintento no vuelve a
    pedir lo ya bajado: retoma donde se cortó.
    """
    import soccerdata as sd

    parchear_mapeos()
    parchear_soccerdata()
    for intento in range(1, INTENTOS + 1):
        try:
            us = sd.Understat(leagues=liga_sd, seasons=season_to_understat(season))
            return us.read_shot_events().reset_index()
        except Exception as exc:
            if intento == INTENTOS:
                raise
            print(f"      intento {intento}/{INTENTOS} falló ({type(exc).__name__}), "
                  f"reintentando...", flush=True)
            time.sleep(10 * intento)


def build_season(season, force=False):
    """Completa la temporada: baja solo las ligas que falten en el CSV.

    Es lo que permite arreglar una corrida en la que alguna liga se cayó por
    red — antes el script se saltaba la temporada entera con solo ver que el
    archivo existía, y dejaba el hueco ahí para siempre.
    """
    out_path = DATA_DIR / season / "shots.csv"

    previo = None
    if out_path.exists() and not force:
        previo = pd.read_csv(out_path, encoding="utf-8-sig")
        ya = set(previo["liga"])
        pendientes = {sd_: l for sd_, l in LEAGUES.items() if l not in ya}
        if not pendientes:
            print(f"  completa ({len(previo)} tiros, 5/5 ligas), se salta")
            return 0
        print(f"  incompleta: faltan {sorted(pendientes.values())}", flush=True)
    else:
        pendientes = dict(LEAGUES)

    bloques = [previo] if previo is not None else []
    fallidas = []
    for liga_sd, liga in pendientes.items():
        t0 = time.time()
        n_saltados_antes = len(PARTIDOS_SALTADOS)
        try:
            df = fetch_league_season(liga_sd, season)
        except Exception as exc:  # una liga caída no debe tumbar la corrida
            print(f"    {liga:15s} FALLÓ: {type(exc).__name__}: {exc}", flush=True)
            fallidas.append(liga)
            continue

        df["temporada"] = season
        df["liga"] = liga
        df = add_rival(df)
        sin_rival = int(df["rival"].isna().sum())
        bloques.append(df)
        nota = f"  ({sin_rival} sin rival)" if sin_rival else ""
        saltados = len(PARTIDOS_SALTADOS) - n_saltados_antes
        if saltados:
            nota += f"  [{saltados} partido(s) malformado(s) omitido(s)]"
        print(f"    {liga:15s} {len(df):6d} tiros en {time.time()-t0:4.0f}s{nota}", flush=True)

    if not bloques:
        print(f"  {season}: ninguna liga se pudo bajar")
        return 0

    full = pd.concat(bloques, ignore_index=True)
    faltantes = [c for c in COLUMNS if c not in full.columns]
    if faltantes:
        raise ValueError(f"{season}: faltan columnas esperadas: {faltantes}")

    full = full[COLUMNS].sort_values(["liga", "date", "game_id"]).reset_index(drop=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    full.to_csv(out_path, index=False, encoding="utf-8-sig")
    estado = f"{full['liga'].nunique()}/5 ligas" + (f" — SIGUEN FALTANDO {fallidas}" if fallidas else "")
    print(f"  -> {out_path.relative_to(DATA_DIR.parent)}  ({len(full)} tiros, {estado})")
    return len(full)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    force = "--force" in sys.argv
    seasons = args or SEASONS

    desconocidas = [s for s in seasons if s not in SEASONS]
    if desconocidas:
        raise SystemExit(f"Temporada no reconocida: {desconocidas}. Válidas: {SEASONS}")

    t_inicio = time.time()
    total = 0
    for season in seasons:
        print(f"\n{season}", flush=True)
        total += build_season(season, force=force)

    print(f"\n{total} tiros bajados en esta corrida, en {(time.time()-t_inicio)/60:.0f} min.")

    # estado final de TODAS las temporadas, no solo las de esta corrida: un
    # hueco por un timeout es silencioso y envenena cualquier análisis después
    print("\nEstado:")
    incompletas = []
    for s in SEASONS:
        p = DATA_DIR / s / "shots.csv"
        if not p.exists():
            print(f"  {s}: sin descargar"); incompletas.append(s); continue
        d = pd.read_csv(p, encoding="utf-8-sig")
        faltan = sorted(set(LEAGUES.values()) - set(d["liga"]))
        print(f"  {s}: {len(d):6d} tiros · {d['liga'].nunique()}/5 ligas"
              + (f"  FALTAN {faltan}" if faltan else ""))
        if faltan:
            incompletas.append(s)

    if incompletas:
        print(f"\nVuelve a correr para completar: python fetch_shots.py {' '.join(incompletas)}")
    else:
        print("\nTodo completo. Siguiente paso: python consolidate_data.py")


if __name__ == "__main__":
    main()
