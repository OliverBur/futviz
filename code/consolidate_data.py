"""Consolida los CSV crudos de todas las temporadas en dos tablas únicas.

Entrada  — `data/<temporada>/` con los archivos tal cual se bajan:
             leagues_{overall,shoot,playtime,misc,gk}.csv  (fbref, equipos)
             {premier,laliga,seriea,bundes,ligue1}-players.csv  (Understat, jugadores)
             fbref-players.csv  (fbref, jugadores) — opcional, aporta el año de
                                nacimiento, la posición principal y lo único
                                defensivo que existe a nivel jugador (entradas
                                ganadas, intercepciones, faltas), nada de lo
                                cual publica Understat
             elo.csv            (clubelo, equipos) — opcional, el rating Elo de
                                cada club en esa temporada (`fetch_elo.py`)

Salida   — `data/processed/`:
             teams_all_seasons.{csv,xlsx}    una fila por equipo y temporada,
                                             las 5 tablas de fbref unidas a lo
                                             ancho, más `elo_*` si estaba elo.csv
             players_all_seasons.{csv,xlsx}  una fila por jugador, liga y temporada,
                                             con `born`, `sub21`, `posicion` y las
                                             columnas defensivas (ver `MISC_COLS`)
                                             si estaba fbref-players.csv

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

SEASONS = ["2021-22", "2022-23", "2023-24", "2024-25", "2025-26", "2026-27"]

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

# Lo que se conserva de la tabla `misc` de fbref y cómo se llama en la tabla
# consolidada. Es **todo lo defensivo que fbref sigue publicando** a nivel
# jugador: las acciones avanzadas (entradas por tercio, regates enfrentados,
# bloqueos, despejes, duelos aéreos, recuperaciones) desaparecieron del sitio
# —ver `EXTRA_TABLAS` en `fetch_fbref_players.py`, donde está la verificación—
# y Understat, que es shot-event-driven, no publica ninguna.
#
# Las tarjetas no entran aunque `misc` las traiga: Understat ya las da, y dos
# columnas para el mismo hecho es justo lo que este proyecto evita.
MISC_COLS = {
    "msc_Performance_TklW": "tkl_w",
    "msc_Performance_Int": "interceptions",
    "msc_Performance_Fls": "fouls",
    "msc_Performance_Fld": "fouled",
    "msc_Performance_Crs": "crosses",
    "msc_Performance_Off": "offsides",
}

# Tabla de ELO de clubelo (`fetch_elo.py`). Opcional como las `vs`: si no está,
# `teams_all_seasons.csv` sale sin las columnas `elo_*` y todo lo demás igual.
ELO_FILE = "elo.csv"
ELO_COLS = ["elo_club", "elo_pre", "elo_medio", "elo_fin"]

# Corte entre clubes "top" y "underground", que alimenta el filtro de nivel de
# las gráficas de Equipos y de Jugadores. Vive acá y no en `web/charts/` para
# que el umbral esté en UN solo lugar: las dos secciones tienen que clasificar
# igual, si no un mismo club sería top en una gráfica y underground en la de al
# lado.
#
# Las tres decisiones detrás del número (la versión larga está en la bitácora,
# entrada del 2026-08-30):
#
#   · `elo_pre` y no `elo_medio`/`elo_fin` porque cuanto más tarde se mide el
#     ELO, más contiene los resultados de esa misma temporada (r con los puntos
#     0.70 / 0.82 / 0.87). El caso que decide es el Leverkusen 2023-24: llega
#     con 1748 y hace la temporada invicta. Con `elo_medio` (1852) quedaría
#     clasificado como club top y desaparecería del filtro underground, que es
#     exactamente la historia que el filtro existe para mostrar.
#   · Umbral ABSOLUTO y no un percentil por liga: la escala ELO ya es
#     comparable entre ligas, así que cortarla en un valor fijo es lo honesto.
#     Un percentil por liga fabricaría cuatro "grandes" en Ligue 1 los hubiera
#     o no — el mismo defecto por el que se descartó el z-score en el radar.
#     El precio, aceptado a sabiendas: el grupo top es ~40% Premier League y
#     Ligue 1 aporta solo al PSG.
#   · 1800 y no otro número: cae en el percentil 80 global (un 20/80 redondo),
#     deja ~20 equipos en el grupo top y ~77 en el underground, y es el umbral
#     más alto con el que **ninguna** de las 25 combinaciones liga×temporada
#     queda vacía (a partir de 1850 sí las hay).
#
# La clasificación es POR TEMPORADA, no fija por club: 9 clubes son top en las
# cinco, 23 cambian de lado y 98 no lo son nunca. Que el Newcastle sea
# underground en 2021-22 y top en 2024-25 no es un defecto: es lo que pasó.
ELO_TOP = 1800
NIVEL_COL = "elo_pre"
NIVEL_TOP = "Clubes top"
NIVEL_UNDER = "Clubes underground"
NIVELES = (NIVEL_TOP, NIVEL_UNDER)


def nivel_de(elo):
    """La etiqueta de nivel de un ELO, o nulo si no hay dato — un club sin ELO
    no es ni top ni underground, igual que un jugador sin edad no es sub-21."""
    if pd.isna(elo):
        return pd.NA
    return NIVEL_TOP if elo >= ELO_TOP else NIVEL_UNDER

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
    "2026-27": [18, 20, 18, 20, 20],
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


def attach_elo(teams, season_dir, season):
    """Le pega a los equipos sus columnas `elo_*`, si `elo.csv` está.

    El cruce es por `Squad` y no por nombre normalizado como el de jugadores:
    `fetch_elo.py` parte del mismo `leagues_overall.csv` que este archivo, así
    que los nombres son idénticos por construcción. Que falte alguno sería un
    error de verdad —el CSV se generó con otra temporada de fbref— y por eso
    revienta en vez de dejar nulos en silencio.
    """
    f = season_dir / ELO_FILE
    if not f.exists():
        return teams, None

    elo = pd.read_csv(f)
    faltan = set(teams["Squad"]) - set(elo["Squad"])
    if faltan:
        raise ValueError(
            f"{season}: {ELO_FILE} no trae ELO de {sorted(faltan)}. "
            f"Vuelve a correr `python fetch_elo.py {season}`."
        )
    teams = teams.merge(elo[["Squad"] + ELO_COLS], on="Squad", how="left")
    teams["nivel"] = [nivel_de(e) for e in teams[NIVEL_COL]]
    return teams, elo


def puente_understat_fbref(players, season_dir, season):
    """Cómo se llama en fbref cada equipo de Understat, deducido de los datos.

    Understat y fbref escriben los clubes distinto ('Borussia M.Gladbach' vs.
    'Gladbach', 'Wolverhampton Wanderers' vs. 'Wolves'), así que hace falta un
    puente. En vez de escribirlo a mano —una tercera tabla de alias que
    mantener cada vez que asciende alguien— se **deduce**: los jugadores ya
    cruzan por nombre con fbref (ver `attach_fbref`) y la tabla de fbref trae el
    club, así que para cada equipo de Understat el club fbref que más se repite
    entre sus jugadores cruzados es su equivalente.

    Verificado sobre las 5 temporadas: los 25 conjuntos liga-temporada salen
    biyectivos y completos, sin un solo alias escrito a mano.

    Devuelve `(mapa, avisos)`. Los avisos son los casos en que la mayoría no
    llega al 80% —señal de que el cruce por nombre falló para ese equipo— y se
    imprimen en vez de romper, porque un puente imperfecto deja sin `nivel` a un
    equipo pero no invalida el resto de la consolidación.
    """
    path = season_dir / FBREF_PLAYER_FILE
    if not path.exists():
        return {}, []

    fb = pd.read_csv(path, encoding="utf-8-sig")
    # El club donde más jugó, para quien cambió a mitad de temporada: es la
    # misma fila que elige `attach_fbref` y por el mismo motivo.
    fb = fb.sort_values("min", ascending=False).copy()
    fb["key"] = [_key(l, n) for l, n in zip(fb["liga"], fb["player"])]
    club_de = dict(zip(fb.drop_duplicates("key")["key"],
                        fb.drop_duplicates("key")["team"]))

    d = players.copy()
    d["key"] = [_key(l, n) for l, n in zip(d["liga"], d["player"])]
    d["fb_team"] = d["key"].map(club_de)
    d = d[d["fb_team"].notna()]

    mapa, avisos = {}, []
    for (liga, us_team), g in d.groupby(["liga", ultimo_club_col(d)]):
        cuenta = Counter(g["fb_team"])
        ganador, n = cuenta.most_common(1)[0]
        confianza = n / sum(cuenta.values())
        mapa[(liga, us_team)] = ganador
        if confianza < 0.80:
            avisos.append(f"{season} {liga}: '{us_team}' -> '{ganador}' con solo "
                          f"{confianza:.0%} de acuerdo ({dict(cuenta)})")
    return mapa, avisos


def ultimo_club_col(d):
    """El último club del campo `team` de Understat, como Serie.

    `load_players_season` deja `team` tal cual viene ('Bournemouth,Manchester
    City' para quien se fue en enero) porque quedarse con uno es decisión de
    análisis. Acá se toma el último, que es **la misma decisión que toma
    `web/charts/players.py` para mostrarlo**: si el hover dice "Manchester
    City", el filtro de nivel tiene que clasificarlo por Manchester City y no
    por el club que dejó."""
    return d["team"].str.split(",").str[-1].str.strip()


def attach_elo_players(players, teams, season_dir, season):
    """Le pega a cada jugador el `nivel` del club en el que jugó esa temporada.

    Devuelve `(df, avisos)`. Sin ELO en `teams` —o sin `fbref-players.csv`, que
    es de donde sale el puente— la columna queda entera en nulo y el filtro
    simplemente no se dibuja en el sitio."""
    players = players.copy()
    if teams is None or "nivel" not in teams.columns:
        players["nivel"] = pd.NA
        return players, []

    mapa, avisos = puente_understat_fbref(players, season_dir, season)
    nivel_de_club = {(l, s): n for l, s, n in
                     zip(teams["liga"], teams["Squad"], teams["nivel"])}

    def nivel(liga, us_team):
        squad = mapa.get((liga, us_team))
        return pd.NA if squad is None else nivel_de_club.get((liga, squad), pd.NA)

    players["nivel"] = [nivel(l, t) for l, t
                        in zip(players["liga"], ultimo_club_col(players))]
    return players, avisos


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

    Devuelve la **clave** de la fila de fbref que le toca a cada jugador, no
    los datos en sí: de esa clave cuelgan `born`, `pos` y las columnas
    defensivas, y resolver el cruce una vez para traer todo junto es lo que
    evita repetir este trabajo por cada columna nueva. La unicidad se sigue
    evaluando sobre `born` porque es el dato que distingue a dos personas —
    dos filas del mismo jugador (cambió de club dentro de la liga) comparten
    `born` pero pueden traer distinto `pos`."""
    clave = players["fb_key"].copy()
    faltan = players.index[clave.isna()]
    if not len(faltan):
        return clave

    # candidatos agrupados por liga: cruzar entre ligas no tendría sentido y
    # además multiplicaría las coincidencias espurias
    por_liga = {}
    for fila in fb.itertuples(index=False):
        por_liga.setdefault(fila.liga, []).append((set(fila.tokens), fila.born, fila.key))

    propuestas = {}
    for i in faltan:
        tokens = set(norm_name(players.at[i, "player"]))
        if not tokens:
            continue
        candidatos = [
            (frozenset(cand), b, k)
            for cand, b, k in por_liga.get(players.at[i, "liga"], [])
            if tokens <= cand or cand <= tokens
        ]
        # varios candidatos con el MISMO born no son ambiguos para lo que
        # importa acá (es el mismo jugador escrito de dos formas)
        if len({b for _, b, _ in candidatos}) == 1:
            propuestas[i] = candidatos[0]

    # que dos jugadores distintos reclamen la misma fila de fbref significa que
    # el nombre corto no alcanza para distinguirlos: se descartan los dos
    veces = Counter(cand for cand, _, _ in propuestas.values())
    for i, (cand, _, k) in propuestas.items():
        if veces[cand] == 1:
            clave.at[i] = k
    return clave


def edad_en_temporada(born, season):
    """Edad cumplida al arrancar la temporada, a partir del AÑO de nacimiento.

    Se usa el año y no la fecha exacta porque es lo que publica fbref, y porque
    es el mismo criterio de las categorías sub-N de UEFA: la elegibilidad va por
    año de nacimiento, no por cumpleaños. Para 2024-25 'sub-21' es entonces todo
    el que nació en 2004 o después."""
    return int(str(season)[:4]) - born


def attach_fbref(players, season_dir, season):
    """Agrega `born`, `sub21`, `posicion`, `nation` y las columnas defensivas
    cruzando por nombre con la tabla de fbref. Todas salen del mismo cruce:
    Understat no publica ni la edad, ni una posición que diga cuál es la
    principal (ver `posicion_understat`), ni nacionalidad, ni una sola acción
    defensiva.

    `nation` es el código de país de 3 letras tal cual lo trae fbref (`ARG`,
    `BRA`...) — se descartaba hasta ahora porque nada la usaba; la ficha de
    jugador es la primera consumidora.

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
        players["nation"] = pd.NA
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
    fb = fb[~fb["key"].isin(ambiguos)].copy()

    # Los CONTEOS se suman antes de colapsar, y no se toman de la fila que
    # sobrevive: fbref parte en dos a quien cambió de club dentro de la liga,
    # así que quedarse con la del club donde más jugó le borraría media
    # temporada de faltas y de entradas. `born` y `pos` sí salen de esa fila —
    # son propiedades del jugador, no cuentas que sumar.
    #
    # `fb_min` son los minutos de fbref, y es el divisor que les corresponde a
    # estas tasas: los de Understat cuentan otra cosa (los suyos), y dividir
    # una cuenta de fbref por minutos de Understat mezcla dos fuentes en un
    # solo número.
    disponibles = {c: n for c, n in MISC_COLS.items() if c in fb.columns}
    sumas = (fb.groupby("key")[["min"] + list(disponibles)].sum(min_count=1)
               .rename(columns={**disponibles, "min": "fb_min"}))

    fb = fb.sort_values("min", ascending=False).drop_duplicates("key").copy()
    fb["tokens"] = [norm_name(n) for n in fb["player"]]

    players["key"] = [_key(l, n) for l, n in zip(players["liga"], players["player"])]
    # Primera pasada: el nombre normalizado coincide exacto. La segunda
    # (`_por_subconjunto`) rellena lo que quede, y las dos devuelven lo mismo:
    # la clave de la fila de fbref, de la que después cuelga todo.
    players["fb_key"] = players["key"].where(players["key"].isin(set(fb["key"])))
    players["fb_key"] = _por_subconjunto(players, fb)

    por_clave = fb.set_index("key")
    players["born"] = por_clave["born"].reindex(players["fb_key"]).to_numpy()
    fb_pos = por_clave["pos"].reindex(players["fb_key"]).to_numpy()
    players["nation"] = (por_clave["nation"].reindex(players["fb_key"]).to_numpy()
                          if "nation" in por_clave.columns else pd.NA)

    sin_match = players.loc[players["born"].isna(), ["player", "team", "liga", "min"]]
    edad = edad_en_temporada(players["born"], season)
    players["sub21"] = (edad <= 20).where(players["born"].notna())
    players["born"] = players["born"].astype("Int64")
    players["posicion"] = [posicion_fbref(f) or posicion_understat(u)
                            for f, u in zip(fb_pos, players["position"])]

    # Las defensivas van al final, ya con sus tasas por 90'. Quien no cruzó por
    # nombre las tiene todas nulas, que es la misma regla que ya lo deja sin
    # edad y sin posición de fbref.
    defensivas = sumas.reindex(players["fb_key"]).reset_index(drop=True)
    # Un 0 en los minutos de fbref daría tasas infinitas. Pasa con quien
    # figura en la tabla sin haber jugado; queda sin tasa, que es lo correcto.
    noventas = (defensivas.pop("fb_min") / 90).replace(0, pd.NA)
    for col in defensivas.columns:
        players[col] = defensivas[col].to_numpy()
        players[f"{col}90"] = (defensivas[col] / noventas).to_numpy()
    # Recuperaciones: las dos formas de quitar la pelota, sumadas. Va como
    # columna propia y no calculada en cada gráfico porque es el eje de una de
    # ellas y una variable de "Crea tu gráfico".
    if {"tkl_w", "interceptions"} <= set(defensivas.columns):
        players["recoveries"] = players["tkl_w"] + players["interceptions"]
        players["recoveries90"] = players["tkl_w90"] + players["interceptions90"]
    return players.drop(columns=["key", "fb_key"]), sin_match


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
    t = None  # los equipos de la temporada en curso: los jugadores los usan
              # para saber el nivel del club en el que jugaron

    for season in SEASONS:
        season_dir = DATA_DIR / season
        t = None
        presentes = [f for f in list(TEAM_FILES.values()) + list(PLAYER_FILES)
                     if (season_dir / f).exists()]
        if not presentes:
            faltantes.append(season)
            continue

        print(f"{season}:")
        if all((season_dir / f).exists() for f in TEAM_FILES.values()):
            t = load_teams_season(season_dir, season)
            t, elo = attach_elo(t, season_dir, season)
            teams.append(t)
            con_vs = sum((season_dir / f).exists() for f in VS_FILES.values())
            print(f"  equipos   {len(t):4d}  " +
                  " · ".join(f"{k} {v}" for k, v in t['liga'].value_counts()[LEAGUE_ORDER].items()) +
                  (f"  (+{con_vs} tablas vs)" if con_vs else "  (sin tablas vs)"))
            if elo is None:
                print("    sin elo.csv: no hay columnas elo_*")
            else:
                print(f"    ELO {t['elo_medio'].notna().sum()}/{len(t)}"
                      f" · rango {t['elo_medio'].min():.0f}–{t['elo_medio'].max():.0f}"
                      f" · top {(t['nivel'] == NIVEL_TOP).sum()}"
                      f" / underground {(t['nivel'] == NIVEL_UNDER).sum()}")
        else:
            print("  equipos   faltan archivos leagues_*.csv, se salta")

        if all((season_dir / f).exists() for f in PLAYER_FILES):
            p = load_players_season(season_dir, season)
            p, sin_match = attach_fbref(p, season_dir, season)
            p, avisos_elo = attach_elo_players(p, t, season_dir, season)
            players.append(p)
            for a in avisos_elo:
                print(f"    ojo, puente Understat→fbref: {a}")
            con_pos = int(p["posicion"].notna().sum())
            print(f"  jugadores {len(p):4d}", end="")
            if sin_match is None:
                print("  (sin fbref-players.csv: no hay edades)"
                      f" · posición {con_pos}/{len(p)} ({con_pos / len(p):.1%},"
                      f" solo el respaldo de Understat)")
            else:
                con_born = len(p) - len(sin_match)
                sub21 = int((p["sub21"] == True).sum())
                con_nivel = int(p["nivel"].notna().sum())
                print(f"  · edad {con_born}/{len(p)} ({con_born / len(p):.1%})"
                      f" · sub-21 {sub21}"
                      f" · posición {con_pos}/{len(p)} ({con_pos / len(p):.1%})"
                      f" · nivel de club {con_nivel}/{len(p)} ({con_nivel / len(p):.1%})")
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
