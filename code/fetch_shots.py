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

Por qué acá NO se usa `soccerdata` (a diferencia de como se usó hasta la
temporada 2025-26): el 26-09-2026 se detectó que understat.com movió los datos
de sus páginas de liga y de partido de JSON embebido en el HTML a llamadas AJAX
propias — ver `fetch_understat.py` para el detalle completo. `soccerdata.
Understat.read_shot_events()` solo sabe leer el formato viejo, así que quedó
inútil para bajar partidos nuevos (no solo los de 2026-27). Acá se pide
directo:

    GET  getLeagueData/<liga>/<temporada>   lista de partidos jugados (`dates`,
                                             con `isResult`) + `teams` (id<->nombre)
    GET  getMatchData/<id_partido>          `shots.h` / `shots.a`, un dict por tiro

Sin Cloudflare ni sesión especial de por medio — un `requests.get()` sencillo
alcanza para las dos, igual que ya se comprobó para `getPlayersStats`.

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
import requests

warnings.filterwarnings("ignore")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

SEASONS = ["2021-22", "2022-23", "2023-24", "2024-25", "2025-26", "2026-27"]

API = "https://understat.com"
DELAY_SECONDS = 0.3  # entre partidos; son ~50-380 pedidos por liga-temporada
REINTENTOS = 4

# liga -> código de Understat en la URL
LEAGUES = {
    "Bundesliga": "Bundesliga",
    "Serie A": "Serie_A",
    "Ligue 1": "Ligue_1",
    "La Liga": "La_liga",
    "Premier League": "EPL",
}

COLUMNS = [
    "temporada", "liga", "game_id", "date", "team", "rival",
    "player", "assist_player", "minute", "situation", "body_part", "result",
    "xg", "location_x", "location_y", "shot_id", "player_id", "team_id",
]

# JSON de Understat -> mismos rótulos que ya usan los notebooks y el resto del
# sitio (el patch de `Head`/`OtherBodyPart` que hacía falta contra soccerdata
# 1.9.0 ya está incorporado acá directo, no hace falta parchear nada).
RESULTS = {
    "Goal": "Goal", "OwnGoal": "Own Goal", "BlockedShot": "Blocked Shot",
    "SavedShot": "Saved Shot", "MissedShots": "Missed Shot", "ShotOnPost": "Shot On Post",
}
SITUATIONS = {
    "OpenPlay": "Open Play", "FromCorner": "From Corner",
    "SetPiece": "Set Piece", "DirectFreekick": "Direct Freekick", "Penalty": "Penalty",
}
BODY_PARTS = {"RightFoot": "Right Foot", "LeftFoot": "Left Foot", "OtherBodyPart": "Other", "Head": "Head"}

# Partidos que no se pudieron leer, acumulados durante la corrida.
PARTIDOS_SALTADOS = []


def season_code(season):
    """'2024-25' -> '2024', el año de arranque que espera Understat."""
    return season.split("-")[0]


# Sin esto, understat.com devuelve 404 — el endpoint solo responde a
# requests que se parezcan a las que dispara su propio JS (ver `Referer` y
# `X-Requested-With` en `main/getPlayersStats/`, comprobado en `fetch_understat.py`).
HEADERS = {"User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest",
           "Referer": "https://understat.com/"}


def pedir(url, **kwargs):
    """GET con reintentos — los timeouts contra understat son frecuentes y
    transitorios, sobre todo pidiendo cientos de partidos seguidos."""
    for intento in range(1, REINTENTOS + 1):
        try:
            r = requests.get(url, headers=HEADERS, timeout=30, **kwargs)
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError) as e:
            if intento == REINTENTOS:
                raise
            time.sleep(DELAY_SECONDS * 4 * intento)


def partidos_jugados(liga_code, temporada_code):
    """(dict id->nombre de equipo, [ids de partido ya jugados]) de una
    liga-temporada."""
    data = pedir(f"{API}/getLeagueData/{liga_code}/{temporada_code}")
    equipos = {int(t["id"]): t["title"] for t in data.get("teams", {}).values()}
    ids = [d["id"] for d in data.get("dates", []) if d.get("isResult")]
    return equipos, ids


def tiros_de(game_id, equipos):
    """Los tiros de un partido, en el formato final. `None` si el partido
    viene malformado (sin `shots`, o sin los dos lados)."""
    data = pedir(f"{API}/getMatchData/{game_id}")
    shots = data.get("shots")
    if not shots or not shots.get("h") or not shots.get("a"):
        return None

    nombre_a_id = {v: k for k, v in equipos.items()}
    filas = []
    for lado in ("h", "a"):
        for s in shots[lado]:
            equipo = s["h_team"] if s["h_a"] == "h" else s["a_team"]
            filas.append({
                "game_id": int(game_id),
                "date": s["date"],
                "team": equipo,
                "player": s["player"],
                "assist_player": s.get("player_assisted") or None,
                "minute": int(s["minute"]),
                "situation": SITUATIONS.get(s["situation"], s["situation"]),
                "body_part": BODY_PARTS.get(s["shotType"], s["shotType"]),
                "result": RESULTS.get(s["result"], s["result"]),
                "xg": float(s["xG"]),
                "location_x": float(s["X"]),
                "location_y": float(s["Y"]),
                "shot_id": int(s["id"]),
                "player_id": int(s["player_id"]),
                "team_id": nombre_a_id.get(equipo),
            })
    return filas


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


def fetch_league_season(liga_code, temporada_code, liga):
    """Todos los tiros de una liga-temporada."""
    equipos, ids = partidos_jugados(liga_code, temporada_code)
    filas = []
    for game_id in ids:
        try:
            del_partido = tiros_de(game_id, equipos)
        except Exception:
            del_partido = None
        if del_partido is None:
            PARTIDOS_SALTADOS.append(game_id)
            continue
        filas.extend(del_partido)
        time.sleep(DELAY_SECONDS)
    return pd.DataFrame(filas)


def build_season(season, force=False):
    """Completa la temporada: baja solo las ligas que falten en el CSV.

    Es lo que permite arreglar una corrida en la que alguna liga se cayó por
    red — antes el script se saltaba la temporada entera con solo ver que el
    archivo existía, y dejaba el hueco ahí para siempre.
    """
    out_path = DATA_DIR / season / "shots.csv"
    temporada_code = season_code(season)

    previo = None
    if out_path.exists() and not force:
        previo = pd.read_csv(out_path, encoding="utf-8-sig")
        ya = set(previo["liga"])
        pendientes = {code: l for l, code in LEAGUES.items() if l not in ya}
        if not pendientes:
            print(f"  completa ({len(previo)} tiros, 5/5 ligas), se salta")
            return 0
        print(f"  incompleta: faltan {sorted(pendientes.values())}", flush=True)
    else:
        pendientes = {code: l for l, code in LEAGUES.items()}

    bloques = [previo] if previo is not None else []
    fallidas = []
    for liga_code, liga in pendientes.items():
        t0 = time.time()
        n_saltados_antes = len(PARTIDOS_SALTADOS)
        try:
            df = fetch_league_season(liga_code, temporada_code, liga)
        except Exception as exc:  # una liga caída no debe tumbar la corrida
            print(f"    {liga:15s} FALLÓ: {type(exc).__name__}: {exc}", flush=True)
            fallidas.append(liga)
            continue

        if df.empty:
            print(f"    {liga:15s} sin partidos jugados todavía", flush=True)
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

    print(f"\n{total} tiros bajados en esta corrida, en {(time.time()-t_inicio)/60:.1f} min.")
    if PARTIDOS_SALTADOS:
        print(f"Partidos omitidos (malformados): {PARTIDOS_SALTADOS}")

    # estado final de TODAS las temporadas, no solo las de esta corrida: un
    # hueco por un timeout es silencioso y envenena cualquier análisis después
    print("\nEstado:")
    incompletas = []
    for s in SEASONS:
        p = DATA_DIR / s / "shots.csv"
        if not p.exists():
            print(f"  {s}: sin descargar"); incompletas.append(s); continue
        d = pd.read_csv(p, encoding="utf-8-sig")
        faltan = sorted(set(LEAGUES) - set(d["liga"]))
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
