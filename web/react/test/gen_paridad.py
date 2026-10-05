"""Genera los casos del test de paridad (`paridad.mjs`): para cientos de combinaciones de temporada,
liga, posición, nivel y sub-21, el texto que produce `code/insights.py` (la referencia) y las tablas
reales que viajan al sitio (`dist/react/datos-*.js`). El test de Node comprueba que el JS portado
dice EXACTAMENTE lo mismo sobre esas tablas.

Uso (desde `web/react`):  python test/gen_paridad.py
"""
import itertools
import json
import random
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
WEB = AQUI.parents[1]
sys.path[:0] = [str(WEB), str(WEB / "charts")]

import site_utils  # noqa: E402,F401  (pone code/ en sys.path)
import insights as ins  # noqa: E402
import players  # noqa: E402
import react_views  # noqa: E402
import shot_map  # noqa: E402
import teams  # noqa: E402

SALIDA = AQUI / "fixtures"
LIGA_TODAS = ins.LIGA_TODAS

# (insight, generador de Python, columnas que definen la población de la vista)
JUGADORES = [
    ("goles_xg", ins.goles_xg, []), ("asist_xa", ins.asist_xa, []), ("perfil", ins.perfil, []),
    ("recuperar", ins.recuperar, ["recoveries90"]), ("disputar", ins.disputar, ["recoveries90"]),
    ("dos_fases", ins.dos_fases, ["recoveries90"]),
    ("pases_clave", ins.pases_clave, ["kp90", "xA90"]),
    ("construir", ins.construir, ["xgbuild90", "xga90"]),
    ("centros", ins.centros, ["crosses90", "xA90"]),
]
EQUIPOS = [("definicion", ins.definicion, []), ("creacion", ins.creacion, []), ("defensa", ins.defensa, [])]


def casos(df, seasons, ligas, insight, generador, requiere, entidad, rng, n_aleatorios):
    pob = df
    for c in requiere:
        pob = pob[pob[c].notna()]
    pob = pob.reset_index(drop=True)
    posiciones = players.posiciones_de(pob) if entidad == "jugadores" else []
    niveles = (players.niveles_de(pob) if entidad == "jugadores" else teams.niveles_de(pob))
    temporadas = [s for s in seasons if (pob["temporada"] == s).any()]

    def una(season, liga, pos, nivel, sub21):
        d = pob
        if pos:
            d = d[d["posicion"].isin(pos)]
        if nivel:
            d = d[d["nivel"] == nivel]
        if sub21:
            d = d[d["sub21"] == True]  # noqa: E712
        dd = d[d["temporada"] == season]
        if liga != LIGA_TODAS:
            dd = dd[dd["liga"] == liga]
        if dd.empty:
            fija, salta = ("Ningún jugador cumple los filtros elegidos." if entidad == "jugadores"
                           else "Ningún equipo cumple los filtros elegidos."), None
        else:
            fija, salta = generador(d, season, liga)
        return {"insight": insight, "entidad": entidad, "temporada": season,
                "liga": None if liga == LIGA_TODAS else liga, "posiciones": list(pos or []),
                "nivel": nivel, "sub21": bool(sub21), "requiere": requiere, "fija": fija, "salta": salta}

    sin_filtros = [una(s, l, None, None, False) for s in temporadas for l in [LIGA_TODAS, *ligas]]
    aleatorios = []
    for _ in range(n_aleatorios):
        pos = None
        if posiciones and rng.random() < 0.6:
            pos = rng.sample(posiciones, rng.randint(1, len(posiciones) - 1))
            pos = [p for p in posiciones if p in pos]
        nivel = rng.choice(niveles) if niveles and rng.random() < 0.5 else None
        sub21 = entidad == "jugadores" and rng.random() < 0.3
        aleatorios.append(una(rng.choice(temporadas), rng.choice([LIGA_TODAS, *ligas]), pos, nivel, sub21))
    return sin_filtros + aleatorios


def main():
    rng = random.Random(20261004)
    SALIDA.mkdir(exist_ok=True)

    dfj = players.load_data()
    seasons_j = players.seasons_of(dfj)
    players._registrar_tabla(dfj, seasons_j)

    dfe = teams.load_data()
    seasons_e = teams.seasons_of(dfe)
    teams._registrar_tabla(dfe, seasons_e)

    # Mapa de tiros: la tabla agregada y, por cada combinación temporada × tipo, el texto de Python.
    shots, descartes = shot_map.load(site_utils.PROCESSED_DIR / "shots_all_seasons.csv")
    seasons_t = sorted(shots["temporada"].unique())
    react_views.registrar_payload("tiros", shot_map.tabla_agregada(shots, descartes, seasons_t))

    react_views.escribir_datos(SALIDA)
    ligas = list(players.LEAGUE_ORDER)

    casos_tiros = []
    for temporada in [shot_map.TODAS] + list(seasons_t):
        base = shot_map._subconjunto(shots, temporada, shot_map.TODOS)
        ambito = shot_map._etiqueta_temporada(temporada, seasons_t)
        for tipo, _, _, _, _, frase in shot_map.TIPOS:
            sub = shot_map._subconjunto(shots, temporada, tipo)
            fija, salta = ins.tiros(sub, base, frase, ambito)
            casos_tiros.append({"temporada": temporada, "tipo": tipo, "frase": frase, "ambito": ambito,
                                "fija": fija, "salta": salta})
    (SALIDA / "paridad-tiros.json").write_text(json.dumps(casos_tiros, ensure_ascii=False), encoding="utf-8")
    print(f"{len(casos_tiros)} casos de tiros")

    todos = []
    for insight, gen, req in JUGADORES:
        todos += casos(dfj, seasons_j, ligas, insight, gen, req, "jugadores", rng, 70)
    for insight, gen, req in EQUIPOS:
        todos += casos(dfe, seasons_e, ligas, insight, gen, req, "equipos", rng, 70)

    (SALIDA / "paridad.json").write_text(json.dumps(todos, ensure_ascii=False), encoding="utf-8")
    print(f"{len(todos)} casos -> {SALIDA / 'paridad.json'}")
    for r in sorted(SALIDA.glob("react/datos-*.js")):
        print(f"  {r.name}: {r.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
