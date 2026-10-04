"""Descarga las tablas de jugador de fbref y las deja, unidas a lo ancho, en
`data/<temporada>/fbref-players.csv`.

Para qué, al principio: Understat no publica edad ni fecha de nacimiento, así
que el año de nacimiento (`born`) tiene que venir de fbref. Esa era la única
columna que el script existía para traer.

Y desde el 2026-09-01, también lo único defensivo que hay a nivel jugador:
entradas ganadas, intercepciones y faltas, de la tabla `misc` (ver
`EXTRA_TABLAS` para qué sobrevive de fbref y qué no). Understat es
shot-event-driven y no publica ninguna acción defensiva, así que sin esto la
sección de Jugadores del sitio era 100% de ataque.

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

SEASONS = ["2021-22", "2022-23", "2023-24", "2024-25", "2025-26", "2026-27"]

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

# Las tablas de jugador que se bajan. La clave es el slug de la página en la
# URL de fbref; el valor, (id de la tabla dentro del HTML, prefijo de sus
# columnas en el CSV).
#
# `stats` es la de identidad —de ahí salen `player`, `born` y `pos`— y por eso
# no lleva prefijo ni pasa por el camino genérico. Las demás aportan solo
# métricas y se prefijan: hay nombres que se repiten entre tablas (`CrdY` está
# en `stats` y en `misc`), y sin prefijo una pisaría a la otra. Es la misma
# convención que ya usan las tablas de equipo (`ov_`, `sh_`, `ms_`…) en
# `consolidate_data.load_teams_season`.
#
# Por qué solo `misc`, y por qué NO está `defense` (2026-09-01): fbref borró
# las estadísticas avanzadas de todo el sitio, y de forma retroactiva. Se
# verificó sobre las 26 páginas ya cacheadas —las 5 ligas × 5 temporadas— que
# la tabla `standard` no trae ninguna columna de xG, npxG, xAG ni progresivos
# ni siquiera en 2021-22; es el mismo hecho que ya obligaba a sacar el xG de
# Understat. La página `/defense/` sufrió lo mismo: llega con el header entero
# pero las celdas vacías (clase `iz`, que es como fbref pinta un cero). En la
# Premier 2024-25, de sus 574 jugadores hay 0 con dato en entradas totales,
# entradas por tercio, regates enfrentados, bloqueos, despejes y errores —y la
# tabla de EQUIPOS de esa misma página dice que el Arsenal hizo 348 entradas
# ganadas y 0 entradas en 38 partidos, que no es un dato bajo sino un dato que
# no existe. Lo único que sobrevive ahí es `TklW` e `Int`, que `misc` ya trae.
#
# `misc` sí llega completa en lo básico: faltas cometidas y recibidas, centros,
# fueras de juego, tarjetas, entradas ganadas e intercepciones. Sus columnas
# avanzadas (duelos aéreos, recuperaciones) también desaparecieron del header,
# y `PKwon`/`PKcon` vienen vacías, así que no se usan.
EXTRA_TABLAS = {
    "misc": ("stats_misc", "msc_"),
}

# Columnas que traen TODAS las tablas de fbref y que ya vienen de `stats`:
# repetirlas por tabla sería el mismo dato cinco veces. `Player` y `Squad` se
# usan como clave del merge y se descartan después.
COMUNES = {"Rk", "Player", "Nation", "Pos", "Age", "Born", "Squad", "90s", "Matches"}


def season_to_fbref(season):
    """'2024-25' -> '2024-2025', que es como fbref arma sus URLs."""
    inicio, fin = season.split("-")
    return f"{inicio}-{inicio[:2]}{fin}"


def page_url(liga, season, tabla="stats"):
    cid, slug = LEAGUES[liga]
    fb = season_to_fbref(season)
    return f"https://fbref.com/en/comps/{cid}/{fb}/{tabla}/{fb}-{slug}-Stats"


def _cache_file(liga, season, tabla="stats"):
    _, slug = LEAGUES[liga]
    # La tabla de identidad conserva el nombre viejo (`_players`) para no
    # invalidar lo que ya está bajado; las nuevas van con el suyo.
    sufijo = "players" if tabla == "stats" else tabla
    return CACHE_DIR / f"{season}_{slug}_{sufijo}.html"


def paginable(texto, table_id=TABLE_ID):
    """¿Esto es de verdad la página que se pidió? El fallo típico no es un
    error de red sino una página que no es la buscada (un iframe de
    publicidad), y esa diferencia no la delata ningún código HTTP."""
    return texto is not None and len(texto) > 500_000 and table_id in texto


def fetch_page(liga, season, intentos=INTENTOS, tabla="stats"):
    """HTML de la página de jugadores, cacheado en disco. None si no se pudo.

    Las temporadas cerradas no cambian, así que una vez bajada y validada no se
    vuelve a pedir nunca."""
    import fetch_fbref  # reusa el navegador que ya pasó Cloudflare

    table_id = TABLE_ID if tabla == "stats" else EXTRA_TABLAS[tabla][0]
    cached = _cache_file(liga, season, tabla)
    if cached.exists():
        texto = cached.read_text(encoding="utf-8", errors="replace")
        if paginable(texto, table_id):
            return texto
        print(f"      caché inservible ({cached.stat().st_size // 1024} KB), se descarta")
        cached.unlink()

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    url = page_url(liga, season, tabla)
    for intento in range(1, intentos + 1):
        try:
            with fetch_fbref.get_reader().get(url, filepath=cached, max_age=3650) as fh:
                texto = fh.read()
            if isinstance(texto, bytes):
                texto = texto.decode("utf-8", errors="replace")
            motivo = f"no trae la tabla ({len(texto) // 1024} KB)"
        except Exception as exc:
            texto, motivo = None, f"{type(exc).__name__}: {str(exc)[:60]}"

        if paginable(texto, table_id):
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


def parse_extra(texto, tabla, contexto):
    """Una de las tablas de métricas (`defense`, `misc`) con sus columnas ya
    prefijadas y las comunes fuera.

    Devuelve `Player` y `Squad` sin renombrar: son la clave con la que se pega
    a la tabla de identidad, y se descartan ahí.

    El header de dos filas se aplana a `Grupo_Métrica` —`Tackles_Def 3rd`— con
    la misma regla que `consolidate_data.flatten_columns` usa para las tablas
    de equipo, así que el nombre final (`def_Tackles_Def 3rd`) se lee igual que
    los `ms_Performance_Int` que ya existen."""
    table_id, prefijo = EXTRA_TABLAS[tabla]
    plain = texto.replace("<!--", "").replace("-->", "")
    match = re.search(rf'<table[^>]*id="{table_id}".*?</table>', plain, re.S)
    if match is None:
        raise ValueError(f"{contexto}: no se encontró la tabla '{table_id}'")

    df = pd.read_html(io.StringIO(match.group(0)), header=[0, 1])[0]
    df.columns = [bot if str(top).startswith("Unnamed") else f"{top}_{bot}"
                  for top, bot in df.columns]
    df = df[df["Player"].astype(str) != "Player"].copy()

    metricas = [c for c in df.columns if c not in COMUNES]
    df = df[["Player", "Squad"] + metricas]
    # Todo lo que no es la clave es numérico. `errors="coerce"` porque fbref
    # deja la celda vacía —no un 0— cuando un jugador no registró la acción, y
    # un porcentaje sin intentos sale como cadena vacía.
    for c in metricas:
        df[c] = pd.to_numeric(df[c].astype(str).str.replace(",", ""), errors="coerce")
    return df.rename(columns={c: f"{prefijo}{c}" for c in metricas}).reset_index(drop=True)


def merge_extra(base, extra, contexto):
    """Pega una tabla de métricas a la de identidad por (jugador, club).

    La clave es el par y no solo el nombre porque fbref parte en dos filas a
    quien cambió de club dentro de la misma liga, y las dos filas tienen que
    quedarse con sus propios números. Filas que no peguen se avisan en vez de
    desaparecer en silencio: todas las tablas de una liga-temporada listan a la
    misma gente, así que un descuadre es señal de que algo se bajó mal."""
    antes = len(base)
    out = base.merge(extra, left_on=["player", "team"], right_on=["Player", "Squad"],
                      how="left").drop(columns=["Player", "Squad"])
    if len(out) != antes:
        raise ValueError(f"{contexto}: el merge duplicó filas ({antes} -> {len(out)}), "
                          f"hay (jugador, club) repetidos en la tabla")
    metrica = next((c for c in extra.columns if c not in ("Player", "Squad")), None)
    if metrica is not None:
        huerfanas = int(out[metrica].isna().sum()) - int(extra[metrica].isna().sum())
        if huerfanas > 20:
            print(f"      aviso: {huerfanas} jugadores sin cruce en '{contexto}'")
    return out


def ligas_en_csv(path):
    """Qué ligas ya tiene un CSV escrito **con todas las tablas** — para
    completar lo que faltó en una corrida anterior en vez de empezar de cero.

    Mira también las columnas y no solo las ligas: un CSV escrito antes de que
    existiera `EXTRA_TABLAS` tiene las 5 ligas pero ninguna columna `msc_`, y
    darlo por completo dejaría la temporada sin bajar para siempre."""
    if not path.exists():
        return set()
    try:
        df = pd.read_csv(path, encoding="utf-8-sig")
    except Exception:
        return set()
    for _, prefijo in EXTRA_TABLAS.values():
        if not any(c.startswith(prefijo) for c in df.columns):
            return set()
    return set(df["liga"].dropna().unique())


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
        # Lo que ya está parseado en el CSV es exactamente lo que devolvería
        # bajar la página de nuevo: se reusa en vez de re-pedirla. Importa
        # porque agregar una tabla nueva marca la temporada como incompleta, y
        # sin esto una columna extra costaría re-bajar también las 25 páginas
        # `stats` que ya estaban resueltas.
        previo = pd.read_csv(path, encoding="utf-8-sig") if path.exists() else None
        nuevos = []
        for liga in faltan:
            print(f"    {liga:15s} ...", flush=True)
            contexto = f"{season} {liga}"
            fila = None
            if previo is not None and not force:
                ya = previo[previo["liga"] == liga]
                if len(ya) and ya[COLUMN_ORDER].notna().any().any():
                    fila = ya[COLUMN_ORDER].reset_index(drop=True)
                    print(f"      identidad del CSV ({len(fila)} jugadores)")
            if fila is None:
                texto = fetch_page(liga, season, intentos)
                if texto is None:
                    print(f"      SIN DATOS tras {intentos} intentos")
                    continue
                try:
                    fila = parse_players(texto, liga, contexto)
                except Exception as exc:
                    print(f"      no se pudo parsear: {exc}")
                    continue

            # Las tablas extra son opcionales fila a fila: si una no baja, la
            # liga entra igual con lo que sí se consiguió en vez de perderse.
            # Lo que no se puede es escribirla a medias — el CSV se re-lee para
            # decidir qué falta, y una liga sin `msc_` la marcaría incompleta.
            completa = True
            for tabla in EXTRA_TABLAS:
                extra_html = fetch_page(liga, season, intentos, tabla)
                if extra_html is None:
                    print(f"      SIN '{tabla}' tras {intentos} intentos")
                    completa = False
                    break
                try:
                    fila = merge_extra(fila, parse_extra(extra_html, tabla, contexto),
                                        f"{contexto} · {tabla}")
                except Exception as exc:
                    print(f"      no se pudo parsear '{tabla}': {exc}")
                    completa = False
                    break
            if not completa:
                continue

            nuevos.append(fila)
            print(f"      OK ({len(fila)} jugadores, {len(fila.columns)} columnas)")

        if not nuevos:
            print(f"  {season}: no se pudo bajar ninguna liga")
            incompletas.append(season)
            continue

        # Lo ya escrito se conserva: cada corrida suma las ligas que consiguió.
        # Las que sí se rehicieron mandan, porque traen más columnas.
        hechas = set(pd.concat(nuevos)["liga"].unique())
        quedan = ([previo[~previo["liga"].isin(hechas)]]
                   if previo is not None and not force else [])
        out = (pd.concat(quedan + nuevos, ignore_index=True)
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
