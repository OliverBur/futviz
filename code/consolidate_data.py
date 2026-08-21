"""Consolida los CSV crudos de todas las temporadas en dos tablas únicas.

Entrada  — `data/<temporada>/` con los archivos tal cual se bajan:
             leagues_{overall,shoot,playtime,misc,gk}.csv  (fbref, equipos)
             {premier,laliga,seriea,bundes,ligue1}-players.csv  (Understat, jugadores)
             fbref-players.csv  (fbref, jugadores) — opcional, aporta el año de
                                nacimiento y la posición principal, que
                                Understat no publica

Salida   — `data/processed/`:
             teams_all_seasons.{csv,xlsx}    una fila por equipo y temporada,
                                             las 5 tablas de fbref unidas a lo ancho
             players_all_seasons.{csv,xlsx}  una fila por jugador, liga y temporada,
                                             con `born`, `sub21` y `posicion` si estaba
                                             fbref-players.csv

Las temporadas que todavía no estén descargadas se saltan con un aviso, así que
el script se puede correr hoy con una sola temporada y otra vez cuando estén las
cinco. Uso:  python consolidate_data.py
"""

import html
import re
import unicodedata
from collections import Counter
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

# Tabla de jugador de fbref (`fetch_fbref_players.py`). Es opcional, igual que
# las tablas `vs`: si no está, `born`/`sub21` quedan vacíos, `posicion` se
# queda con lo poco que se puede deducir de Understat, y todo lo demás funciona
# igual.
FBREF_PLAYER_FILE = "fbref-players.csv"

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


# Letras que NFKD no descompone, porque no son una base + acento sino signos
# propios del alfabeto. Sin esto 'Ødegaard' nunca cruza con 'Odegaard', que es
# como lo escribe Understat — y con ellas se cae casi la mitad de los que no
# cruzaban: escandinavos, polacos y balcánicos.
# Se sigue la convención de Understat, que es la fuente con la que hay que
# coincidir: la 'đ' serbocroata la escribe 'dj' ('Đorđe' -> 'Djordje'), mientras
# que la 'ð' islandesa —otro carácter, aunque se parezcan— es simplemente 'd'.
TRANSLITERA = str.maketrans({
    "ø": "o", "ł": "l", "đ": "dj", "ð": "d", "ı": "i", "ħ": "h", "ŧ": "t",
    "þ": "th", "ß": "ss", "æ": "ae", "œ": "oe",
})


def norm_name(name):
    """Los tokens del nombre, comparables entre Understat y fbref: sin acentos,
    sin puntuación y en minúsculas, así 'Gündoğan' y 'Gundogan' dan lo mismo.

    Devuelve la lista de tokens y no un string porque el cruce necesita
    compararlos como conjunto: las dos fuentes no coinciden en cuántos
    apellidos ponen ('Ezri Konsa' vs 'Ezri Konsa Ngoyo')."""
    decomposed = unicodedata.normalize("NFKD", str(name))
    sin_acentos = "".join(c for c in decomposed if not unicodedata.combining(c))
    plano = sin_acentos.casefold().translate(TRANSLITERA)
    # El apóstrofo se borra en vez de separar: fbref escribe "N'Dicka" y
    # Understat "Ndicka", y espaciarlo daría ['n','dicka'] contra ['ndicka'],
    # que no son ni iguales ni uno subconjunto del otro. El guion sí separa
    # ("André-Frank" -> "andre frank"), que es como lo parte la otra fuente.
    return re.sub(r"[^a-z ]", " ", plano.replace("'", "").replace("’", "")).split()


def _key(liga, name):
    """El cruce es por liga + nombre, no por equipo: Understat y fbref escriben
    los clubes distinto ('Wolverhampton Wanderers' vs 'Wolves') y además
    Understat pega los dos clubes de quien se transfirió a mitad de temporada.
    Dentro de una liga-temporada el nombre solo ya es suficientemente único."""
    return f"{liga}|{' '.join(norm_name(name))}"


# --------------------------------------------------------------------------
# Posición
# --------------------------------------------------------------------------
#
# Una sola categoría gruesa por jugador, no la lista de puestos: lo que se
# quiere poder preguntar es "defensas / medios / delanteros", y dentro de cada
# uno entran todas sus variantes (central y lateral, pivote y enganche, extremo
# y punta). Ninguna de las dos fuentes publica algo más fino que eso de forma
# utilizable, así que tampoco se pierde nada por agrupar.
POSICIONES = ("Portero", "Defensa", "Medio", "Delantero")
FBREF_A_POSICION = {"GK": "Portero", "DF": "Defensa", "MF": "Medio", "FW": "Delantero"}
UNDERSTAT_A_POSICION = {"GK": "Portero", "D": "Defensa", "M": "Medio", "F": "Delantero"}


def posicion_fbref(pos):
    """fbref lista los puestos de más a menos jugado ('MF,FW' contra 'FW,MF'),
    así que el principal es el primero. Es la fuente preferida justamente por
    eso: es la única de las dos que dice cuál es el principal."""
    if pd.isna(pos):
        return None
    return FBREF_A_POSICION.get(str(pos).split(",")[0].strip())


def posicion_understat(position):
    """Respaldo para el ~5% que no cruza con fbref.

    El campo de Understat es el CONJUNTO de puestos en los que apareció, en
    orden alfabético ('D M S', nunca 'M D S'), así que el orden no dice nada y
    solo sirve cuando hay uno solo: un 'D M S' es un lateral o un carrilero, y
    adivinar cuál de los dos es peor que dejarlo sin posición. La 'S' es "entró
    desde el banco", no un puesto, y se ignora."""
    if pd.isna(position):
        return None
    puestos = {UNDERSTAT_A_POSICION[t] for t in str(position).split()
               if t in UNDERSTAT_A_POSICION}
    return puestos.pop() if len(puestos) == 1 else None


def _por_subconjunto(players, fb):
    """Segunda pasada del cruce, para los que el nombre exacto no resolvió.

    Las dos fuentes no coinciden en cuántas partes del nombre escriben:
    Understat pone 'Ezri Konsa Ngoyo' donde fbref pone 'Ezri Konsa', y al revés
    abrevia a 'Ederson' o 'Bremer' lo que fbref escribe completo. En los dos
    casos los tokens de uno son un subconjunto de los del otro, que es lo que se
    busca acá.

    Solo se acepta cuando la correspondencia es **única en los dos sentidos**:
    un solo candidato de fbref para ese jugador, y ese candidato no reclamado
    por ningún otro. 'Gabriel' contra los cuatro Gabriel del Arsenal es
    ambiguo, y ante la duda se prefiere dejarlo sin edad antes que asignarle la
    de otro.

    Trae `born` y `pos` de una sola pasada: son dos columnas de la MISMA fila de
    fbref, y resolver el cruce dos veces para llegar a ella sería hacer el
    doble de trabajo para el mismo resultado. La unicidad se sigue evaluando
    sobre `born` porque es el dato que distingue a dos personas — dos filas del
    mismo jugador (cambió de club dentro de la liga) comparten `born` pero
    pueden traer distinto `pos`."""
    born, pos = players["born"].copy(), players["fb_pos"].copy()
    faltan = players.index[players["born"].isna()]
    if not len(faltan):
        return born, pos

    # candidatos agrupados por liga: cruzar entre ligas no tendría sentido y
    # además multiplicaría las coincidencias espurias
    por_liga = {}
    for fila in fb.itertuples(index=False):
        por_liga.setdefault(fila.liga, []).append((set(fila.tokens), fila.born, fila.pos))

    propuestas = {}
    for i in faltan:
        tokens = set(norm_name(players.at[i, "player"]))
        if not tokens:
            continue
        candidatos = [
            (frozenset(cand), b, p)
            for cand, b, p in por_liga.get(players.at[i, "liga"], [])
            if tokens <= cand or cand <= tokens
        ]
        # varios candidatos con el MISMO born no son ambiguos para lo que
        # importa acá (es el mismo jugador escrito de dos formas)
        if len({b for _, b, _ in candidatos}) == 1:
            propuestas[i] = candidatos[0]

    # que dos jugadores distintos reclamen la misma fila de fbref significa que
    # el nombre corto no alcanza para distinguirlos: se descartan los dos
    veces = Counter(cand for cand, _, _ in propuestas.values())
    for i, (cand, b, p) in propuestas.items():
        if veces[cand] == 1:
            born.at[i] = b
            pos.at[i] = p
    return born, pos


def edad_en_temporada(born, season):
    """Edad cumplida al arrancar la temporada, a partir del AÑO de nacimiento.

    Se usa el año y no la fecha exacta porque es lo que publica fbref, y porque
    es el mismo criterio de las categorías sub-N de UEFA: la elegibilidad va por
    año de nacimiento, no por cumpleaños. Para 2024-25 'sub-21' es entonces todo
    el que nació en 2004 o después."""
    return int(str(season)[:4]) - born


def attach_fbref(players, season_dir, season):
    """Agrega `born`, `sub21` y `posicion` cruzando por nombre con la tabla de
    fbref. Los tres salen del mismo cruce: Understat no publica ni la edad ni
    una posición que diga cuál es la principal (ver `posicion_understat`).

    Devuelve `(df, sin_match)`, donde `sin_match` son las filas de Understat que
    no encontraron par — se informan en pantalla para poder revisarlas, porque
    un cruce por nombre nunca pega al 100%. Los que no cruzan igual pueden
    terminar con posición: para eso está el respaldo de Understat."""
    players = players.copy()
    path = season_dir / FBREF_PLAYER_FILE
    if not path.exists():
        players["born"] = pd.NA
        players["sub21"] = pd.NA
        players["posicion"] = [posicion_understat(p) for p in players["position"]]
        return players, None

    fb = pd.read_csv(path, encoding="utf-8-sig")
    fb = fb[fb["born"].notna()].copy()
    fb["born"] = fb["born"].astype(int)
    fb["key"] = [_key(l, n) for l, n in zip(fb["liga"], fb["player"])]

    # Un jugador aparece dos veces si cambió de club dentro de la misma liga:
    # son filas distintas pero con el mismo `born`, así que colapsan sin ruido.
    # Lo ambiguo son dos jugadores DISTINTOS que normalizan al mismo nombre; ahí
    # no hay forma de saber cuál es cuál, y se descartan los dos antes que
    # asignarle a uno la edad del otro.
    nacimientos = fb.groupby("key")["born"].nunique()
    ambiguos = set(nacimientos[nacimientos > 1].index)
    # Ordenado por minutos, la fila que sobrevive al colapso es la del club
    # donde más jugó — indistinto para `born`, pero es la que corresponde para
    # `pos`: quien se fue en enero pudo jugar de otra cosa en el club nuevo.
    fb = (fb[~fb["key"].isin(ambiguos)]
            .sort_values("min", ascending=False).drop_duplicates("key").copy())
    fb["tokens"] = [norm_name(n) for n in fb["player"]]

    players["key"] = [_key(l, n) for l, n in zip(players["liga"], players["player"])]
    players = players.merge(fb[["key", "born", "pos"]].rename(columns={"pos": "fb_pos"}),
                             on="key", how="left")
    players["born"], players["fb_pos"] = _por_subconjunto(players, fb)

    sin_match = players.loc[players["born"].isna(), ["player", "team", "liga", "min"]]
    edad = edad_en_temporada(players["born"], season)
    players["sub21"] = (edad <= 20).where(players["born"].notna())
    players["born"] = players["born"].astype("Int64")
    players["posicion"] = [posicion_fbref(f) or posicion_understat(u)
                            for f, u in zip(players["fb_pos"], players["position"])]
    return players.drop(columns=["key", "fb_pos"]), sin_match


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
            p, sin_match = attach_fbref(p, season_dir, season)
            players.append(p)
            con_pos = int(p["posicion"].notna().sum())
            print(f"  jugadores {len(p):4d}", end="")
            if sin_match is None:
                print("  (sin fbref-players.csv: no hay edades)"
                      f" · posición {con_pos}/{len(p)} ({con_pos / len(p):.1%},"
                      f" solo el respaldo de Understat)")
            else:
                con_born = len(p) - len(sin_match)
                sub21 = int((p["sub21"] == True).sum())
                print(f"  · edad {con_born}/{len(p)} ({con_born / len(p):.1%})"
                      f" · sub-21 {sub21}"
                      f" · posición {con_pos}/{len(p)} ({con_pos / len(p):.1%})")
                # Los que no cruzaron se listan por minutos: un titular sin edad
                # importa mucho más que un suplente, y es el que hay que ir a
                # revisar a mano si el porcentaje baja.
                relevantes = sin_match[sin_match["min"] >= 900]
                if len(relevantes):
                    print(f"    sin edad con >=900 min ({len(relevantes)}): " +
                          ", ".join(relevantes.sort_values("min", ascending=False)
                                    ["player"].head(8)) +
                          (" ..." if len(relevantes) > 8 else ""))
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
