"""Actualización semanal de la temporada en curso: baja los partidos nuevos,
consolida, regenera el sitio y (con `--publicar`) lo sube a GitHub, donde Vercel
lo despliega solo al llegar a `master`.

Es lo que corre el Programador de tareas de Windows cada lunes por la noche (ver
`programar_tarea.ps1`), pero se puede lanzar a mano en cualquier momento.

Qué hace, en orden — cada paso es un proceso aparte, y si uno falla se corta
todo ANTES de tocar el sitio publicado:

    1. Understat jugadores   fetch_understat.py --force        (5 peticiones)
    2. Understat tiros       fetch_shots.py --actualizar       (solo partidos nuevos)
    3. fbref equipos         fetch_fbref.py --refrescar        (5 páginas, Chrome)
    4. fbref jugadores       fetch_fbref_players.py --refrescar (10 páginas, Chrome)
    5. Validación            ninguna fuente puede tener MENOS partidos que antes
    6. consolidate_data.py   y   web/build.py
    7. --publicar: commit de data/<temporada> + web/dist, y push

Por qué no es un solo `git add -A`: el sitio se construye con el código que haya
en el árbol de trabajo. Si a esa hora hubiera código a medio editar, se
publicaría. Por eso `--publicar` EXIGE árbol limpio, rama `master` y nada sin
subir, y solo commitea esas dos rutas.

Uso:
    python actualizar.py                    # baja + consolida + construye, sin tocar git
    python actualizar.py --publicar         # además commit + push (lo que hace la tarea)
    python actualizar.py --temporada 2026-27
    python actualizar.py --sin-descarga     # solo consolida y construye con lo que hay

Código de salida: 0 si terminó bien (o si no había nada nuevo), 1 si algo falló.
El log de cada corrida queda en `logs/` (no se versiona).
"""

import argparse
import os
import subprocess
import sys
import threading
import time
import traceback
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from consolidate_data import LEAGUE_ORDER, SEASONS, flatten_columns, split_league_blocks

CODE_DIR = Path(__file__).resolve().parent
REPO_DIR = CODE_DIR.parent
DATA_DIR = REPO_DIR / "data"
WEB_DIR = REPO_DIR / "web"
LOG_DIR = REPO_DIR / "logs"
RAMA = "master"
LOGS_A_CONSERVAR = 20

# El build omite el logo y el favicon sin avisar si faltan estos archivos (no se
# versionan), y entonces el sitio se publicaría sin ellos.
IMG_NECESARIAS = ["futviz.png", "futviz-logo-only.png"]

_log = None


class Fallo(Exception):
    """Algo salió mal y no se debe publicar. El mensaje es para leerlo en el log."""


def decir(texto=""):
    print(texto, flush=True)
    if _log is not None:
        _log.write(texto + "\n")
        _log.flush()


def temporada_en_curso(hoy=None):
    """La temporada que está corriendo: de julio en adelante es la que arranca
    ese año, antes de julio es la que arrancó el año anterior."""
    hoy = hoy or date.today()
    inicio = hoy.year if hoy.month >= 7 else hoy.year - 1
    return f"{inicio}-{str(inicio + 1)[2:]}"


# --- procesos -------------------------------------------------------------

def correr(nombre, cmd, cwd, limite_min):
    """Corre un paso mostrando su salida en vivo y en el log. Un paso colgado
    (Chrome sin respuesta) se mata a los `limite_min`, con todo su árbol de
    procesos: sin eso quedaría un chromedriver huérfano por cada vez."""
    decir(f"\n=== {nombre} ===  ({' '.join(str(c) for c in cmd)})")
    t0 = time.time()
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.Popen(
        cmd, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", bufsize=1,
    )
    vencido = threading.Event()

    def _matar():
        vencido.set()
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)

    reloj = threading.Timer(limite_min * 60, _matar)
    reloj.start()
    try:
        for linea in proc.stdout:
            decir("  " + linea.rstrip())
        proc.wait()
    finally:
        reloj.cancel()

    if vencido.is_set():
        raise Fallo(f"{nombre}: pasó de {limite_min} min y se canceló")
    if proc.returncode != 0:
        raise Fallo(f"{nombre} terminó con código {proc.returncode}")
    decir(f"--- {nombre}: OK en {time.time() - t0:.0f}s")


def git(*args, check=True):
    r = subprocess.run(["git", *args], cwd=REPO_DIR, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    if check and r.returncode != 0:
        raise Fallo(f"git {' '.join(args)}: {(r.stderr or r.stdout).strip()}")
    return r.stdout.strip()


# --- antes de empezar -----------------------------------------------------

def preparar_git():
    """El repo tiene que estar en un estado donde publicar sea seguro."""
    rama = git("rev-parse", "--abbrev-ref", "HEAD")
    if rama != RAMA:
        raise Fallo(f"estás en la rama '{rama}', no en '{RAMA}'. No se publica desde ahí")
    sucio = git("status", "--porcelain", "--untracked-files=no")
    if sucio:
        raise Fallo("hay cambios sin commitear; el sitio se construiría con ese código:\n"
                    + sucio)
    git("fetch", "origin")
    git("pull", "--ff-only", "origin", RAMA)
    por_subir = int(git("rev-list", "--count", f"origin/{RAMA}..HEAD"))
    if por_subir:
        raise Fallo(f"hay {por_subir} commit(s) locales sin subir; el push los publicaría "
                    "junto con los datos. Súbelos (o revísalos) y vuelve a correr")


def revisar_img():
    faltan = [f for f in IMG_NECESARIAS if not (REPO_DIR / "img" / f).exists()]
    if faltan:
        raise Fallo(f"faltan img/{', img/'.join(faltan)}: el build publicaría el sitio sin logo")


# --- validación de datos --------------------------------------------------

def foto(season):
    """Cuánto hay en cada fuente, por liga. Se saca antes y después de
    descargar para comprobar que nada retrocedió."""
    d = DATA_DIR / season
    out = {k: dict.fromkeys(LEAGUE_ORDER, 0)
           for k in ("tiros: partidos", "fbref equipos: partidos", "fbref jugadores: filas")}

    if (d / "shots.csv").exists():
        s = pd.read_csv(d / "shots.csv", encoding="utf-8-sig", usecols=["liga", "game_id"])
        out["tiros: partidos"].update(s.groupby("liga")["game_id"].nunique().to_dict())

    if (d / "leagues_overall.csv").exists():
        raw = flatten_columns(pd.read_csv(d / "leagues_overall.csv", header=[0, 1]))
        liga = split_league_blocks(raw["Squad"], season)
        # cada partido lo juegan dos equipos, y cada uno suma 1 a su MP
        mp = pd.to_numeric(raw["Playing Time_MP"], errors="coerce").groupby(liga).sum() // 2
        out["fbref equipos: partidos"].update(mp.astype(int).to_dict())

    if (d / "fbref-players.csv").exists():
        f = pd.read_csv(d / "fbref-players.csv", encoding="utf-8-sig", usecols=["liga"])
        out["fbref jugadores: filas"].update(f["liga"].value_counts().to_dict())
    return out


def comparar(antes, despues):
    """Falla si algo retrocedió (señal de una descarga rota, no de un partido
    menos) y cuenta los partidos nuevos."""
    retrocesos = [f"{k} · {liga}: {antes[k][liga]} → {despues[k][liga]}"
                  for k in antes for liga in LEAGUE_ORDER if despues[k][liga] < antes[k][liga]]
    if retrocesos:
        raise Fallo("los datos nuevos tienen MENOS que los anteriores:\n  " + "\n  ".join(retrocesos))

    decir("\nPartidos por liga (Understat · fbref)")
    for liga in LEAGUE_ORDER:
        u0, u1 = antes["tiros: partidos"][liga], despues["tiros: partidos"][liga]
        f0, f1 = antes["fbref equipos: partidos"][liga], despues["fbref equipos: partidos"][liga]
        aviso = f"   (fbref va {u1 - f1} detrás)" if u1 > f1 else ""
        decir(f"  {liga:15s} Understat {u0:3d} → {u1:3d}   fbref {f0:3d} → {f1:3d}{aviso}")
    return {liga: despues["tiros: partidos"][liga] - antes["tiros: partidos"][liga]
            for liga in LEAGUE_ORDER}


def verificar_dist():
    """El sitio nuevo no puede haber perdido ninguna página del publicado."""
    publicados = set(git("ls-files", "web/dist").splitlines())
    existentes = {p.relative_to(REPO_DIR).as_posix()
                  for p in (WEB_DIR / "dist").rglob("*") if p.is_file()}
    faltan = sorted(publicados - existentes)
    if faltan:
        raise Fallo(f"el sitio nuevo perdió {len(faltan)} archivo(s) del publicado, "
                    f"p. ej. {faltan[:3]}")


# --- publicar -------------------------------------------------------------

def publicar(season, nuevos):
    rutas = [f"data/{season}", "web/dist"]
    git("add", "-A", "--", *rutas)

    # el árbol estaba limpio al empezar: si hay otra cosa cambiada, algo del
    # build tocó archivos que no debía, y eso no se publica sin que alguien lo vea
    ajeno = [l for l in git("status", "--porcelain", "--untracked-files=no").splitlines()
             if not l[3:].strip('"').startswith(tuple(rutas))]
    if ajeno:
        raise Fallo("el proceso modificó archivos fuera de data/ y web/dist:\n  "
                    + "\n  ".join(ajeno))

    if not git("diff", "--cached", "--name-only", "--", *rutas):
        decir("\nNada que commitear: el sitio quedó igual.")
        return

    detalle = ", ".join(f"{liga} +{n}" for liga, n in nuevos.items() if n)
    total = sum(nuevos.values())
    mensaje = (f"Actualiza datos {season} ({date.today():%Y-%m-%d}): "
               f"{total} partidos nuevos" + (f" ({detalle})" if detalle else ""))
    # `-- rutas` commitea solo esas rutas aunque haya otra cosa en el índice
    git("commit", "-m", mensaje, "--", *rutas)
    ESTADO["commiteado"] = True
    decir(f"\nCommit: {mensaje}")

    for intento in (1, 2, 3):
        try:
            git("push", "origin", RAMA)
            decir("Push OK: Vercel despliega solo en unos minutos.")
            return
        except Fallo as e:
            decir(f"push falló (intento {intento}/3): {e}")
            if intento < 3:
                time.sleep(30 * intento)
    raise Fallo("no se pudo hacer push. El commit quedó local: súbelo con `git push`")


def revertir(season):
    """Deja data/ y web/dist como estaban en el último commit. Solo se llama al
    publicar, cuando el árbol empezó limpio, así que no pisa trabajo de nadie."""
    decir("\nRevirtiendo cambios a medias en data/ y web/dist...")
    git("restore", "--source=HEAD", "--staged", "--worktree", "--",
        f"data/{season}", "web/dist", check=False)
    git("clean", "-fdq", "--", "web/dist", check=False)


# --- flujo ----------------------------------------------------------------

ESTADO = {"arranco_limpio": False, "commiteado": False}


def ejecutar(season, publicar_cambios, descargar):
    if season not in SEASONS:
        raise Fallo(f"{season} no está en SEASONS. Agrégala en consolidate_data.py y en "
                    "los fetch_*.py (y su tamaño en EXPECTED_SIZES)")
    py = sys.executable

    if publicar_cambios:
        preparar_git()
        ESTADO["arranco_limpio"] = True
    revisar_img()

    antes = foto(season)
    if descargar:
        correr("Understat · jugadores", [py, "fetch_understat.py", "--force", season], CODE_DIR, 15)
        correr("Understat · tiros", [py, "fetch_shots.py", "--actualizar", season], CODE_DIR, 45)
        correr("fbref · equipos", [py, "fetch_fbref.py", "--refrescar", season], CODE_DIR, 60)
        correr("fbref · jugadores", [py, "fetch_fbref_players.py", "--refrescar", season], CODE_DIR, 150)

    nuevos = comparar(antes, foto(season))

    if not git("status", "--porcelain", "--", f"data/{season}"):
        decir("\nSin cambios en los datos: no hay nada que reconstruir.")
        return

    correr("Consolidar", [py, "consolidate_data.py"], CODE_DIR, 30)
    correr("Construir sitio", [py, "build.py"], WEB_DIR, 60)
    if publicar_cambios:
        verificar_dist()
        publicar(season, nuevos)
    else:
        decir("\nListo (sin --publicar: el sitio está en web/dist, nada se commiteó).")


def main():
    global _log
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--temporada", help="por defecto, la que está en curso")
    ap.add_argument("--publicar", action="store_true", help="commit + push al terminar")
    ap.add_argument("--sin-descarga", action="store_true",
                    help="no baja nada; consolida y construye con lo que hay")
    args = ap.parse_args()

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    LOG_DIR.mkdir(exist_ok=True)
    ruta_log = LOG_DIR / f"actualizar-{datetime.now():%Y-%m-%d_%H%M}.log"
    _log = open(ruta_log, "w", encoding="utf-8")
    for viejo in sorted(LOG_DIR.glob("actualizar-*.log"))[:-LOGS_A_CONSERVAR]:
        viejo.unlink(missing_ok=True)

    season = args.temporada or temporada_en_curso()
    decir(f"Actualización {season} · {datetime.now():%Y-%m-%d %H:%M} · "
          f"{'con' if args.publicar else 'sin'} publicar · log: {ruta_log.name}")
    try:
        ejecutar(season, args.publicar, not args.sin_descarga)
    except Fallo as e:
        decir(f"\nFALLÓ: {e}")
    except Exception:
        decir("\nFALLÓ con una excepción inesperada:\n" + traceback.format_exc())
    else:
        return 0

    # Solo se revierte si la corrida arrancó desde un árbol limpio: si la
    # revisión inicial fue justo lo que falló, los cambios de data/ o web/dist
    # son tuyos, no de este proceso.
    if args.publicar and ESTADO["arranco_limpio"] and not ESTADO["commiteado"]:
        revertir(season)
    return 1


if __name__ == "__main__":
    sys.exit(main())
