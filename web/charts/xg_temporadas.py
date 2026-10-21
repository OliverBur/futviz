"""El modelo de xG probado en varias temporadas, no solo en la última.

`xg_modelo.py` mide todo sobre 2025-26. Aquí se repite el mismo experimento hacia atrás en el
tiempo ("walk-forward"): para cada temporada T con al menos cuatro temporadas anteriores, el
modelo entrena con las tres previas a la anterior, usa la anterior para decidir cuántos árboles
y predice T, que nunca vio. Es exactamente el corte del modelo final (entrena 2021-24, valida
2024-25, prueba 2025-26) corrido una ventana hacia atrás cada vez.

Sale de aquí:
  * por temporada: log-loss, AUC y sesgo del modelo y de Understat, y su diferencia con intervalo
    (bootstrap por partido);
  * la diferencia conjunta de todas las temporadas, con su intervalo;
  * la probabilidad de gol de cada tiro cuando NINGÚN modelo lo había visto
    (`data/processed/xg_temporadas_prob.csv.gz`): es la que usa el explorador de tiros.

Caché propio (`data/processed/xg_temporadas.json`): tarda ~15 min y no debe repetirse porque cambie
el texto del artículo. Solo se invalida si cambian los datos, este archivo o `xg_modelo.py`.
"""

import hashlib
import json
import os
import time
from pathlib import Path

import numpy as np
import pandas as pd

import xg_modelo as xm

VERSION = 1
CACHE = xm.DATA_DIR / "processed" / "xg_temporadas.json"
PREDICCIONES = xm.DATA_DIR / "processed" / "xg_temporadas_prob.csv.gz"
BASES = ["geo", "contexto", "jugada", "accion"]      # las variables del modelo final
ENTRENAN = 3                                          # temporadas de entrenamiento; la siguiente valida


def _firma(temporadas):
    h = hashlib.sha1()
    h.update(f"{VERSION}".encode())
    h.update(Path(__file__).read_bytes())
    h.update(Path(xm.__file__).read_bytes())
    for t in temporadas:
        for n in ("shots.csv", "partidos.csv"):
            h.update(f"{t}{n}{(xm.DATA_DIR / t / n).stat().st_size}".encode())
    return h.hexdigest()[:16]


def _calcular(log=print):
    t0 = time.time()
    cerradas, historicas = xm.temporadas_disponibles()
    s, _ = xm._armar(cerradas, historicas)
    temps = sorted(s.temporada.unique())
    B = xm._bloques(s)
    X = xm._matriz(B, BASES)
    y = s.gol.values
    und = s.xg.values
    p_todo = np.full(len(s), np.nan)
    filas = []
    for i in range(ENTRENAN + 1, len(temps)):
        T = temps[i]
        valida = temps[i - 1]
        entrena = temps[i - 1 - ENTRENAN:i - 1]
        tr = s.temporada.isin(entrena).values
        va = (s.temporada == valida).values
        te = (s.temporada == T).values
        ps, arbs = [], []
        for sem in xm.SEMILLAS:
            m = xm._ajustar(X, y, tr, va, sem, True)
            ps.append(m.predict_proba(X[te])[:, 1])
            arbs.append(m.best_iteration)
        p = np.mean(ps, axis=0)
        p_todo[te] = p
        yt = y[te]
        boot = xm._Bootstrap(s.game_id.values[te], repeticiones=2000)
        d, lo, hi = boot.dif(p, und[te], yt)
        mio, de_und = xm._metricas(yt, p), xm._metricas(yt, und[te])
        base = float(xm._perdida(yt, np.full(len(yt), y[tr].mean())).mean())
        filas.append({"temporada": T, "entrena": f"{entrena[0]} a {entrena[-1]}", "valida": valida,
                      "tiros": int(te.sum()), "goles": int(yt.sum()), "arboles": float(np.mean(arbs)),
                      "propio": mio, "understat": de_und, "base_ll": base, "d_ll": d, "d_lo": lo, "d_hi": hi,
                      "d_auc": mio["auc"] - de_und["auc"]})
        log(f"    {T}: mío {mio['ll']:.4f}  Understat {de_und['ll']:.4f}  dif {d:+.4f}  "
            f"sesgo {mio['sesgo']:+.1f}% / {de_und['sesgo']:+.1f}%  [{time.time() - t0:.0f}s]")

    ok = ~np.isnan(p_todo)
    boot = xm._Bootstrap(s.game_id.values[ok], repeticiones=2000)
    d, lo, hi = boot.dif(p_todo[ok], und[ok], y[ok])
    conjunto = {"tiros": int(ok.sum()), "d_ll": d, "d_lo": lo, "d_hi": hi,
                "propio": xm._metricas(y[ok], p_todo[ok]), "understat": xm._metricas(y[ok], und[ok]),
                "gana": int(sum(f["d_hi"] < 0 for f in filas)), "empata": int(sum(f["d_lo"] <= 0 <= f["d_hi"] for f in filas)),
                "pierde": int(sum(f["d_lo"] > 0 for f in filas))}
    salida = pd.DataFrame({"shot_id": s.shot_id.values[ok], "temporada": s.temporada.values[ok],
                           "p": np.round(p_todo[ok], 5)})
    PREDICCIONES.parent.mkdir(parents=True, exist_ok=True)
    salida.to_csv(PREDICCIONES, index=False, compression="gzip")
    return {"temporadas": filas, "conjunto": conjunto, "entrenan": ENTRENAN, "tiempo_s": float(time.time() - t0)}


def resultados(log=print):
    cerradas, historicas = xm.temporadas_disponibles()
    firma = _firma(cerradas + historicas)
    if CACHE.exists() and PREDICCIONES.exists() and os.environ.get("XG_REHACER") != "1":
        c = json.loads(CACHE.read_text(encoding="utf-8"))
        if c.get("firma") == firma or os.environ.get("XG_SOLO_CACHE") == "1":
            log(f"  xG temporadas: resultados en caché (firma {c.get('firma')})")
            return c["resultados"]
    log("  xG temporadas: probando el modelo en cada temporada (unos 15 min)...")
    R = _calcular(log)
    CACHE.write_text(json.dumps({"firma": firma, "resultados": R}, ensure_ascii=False), encoding="utf-8")
    return R


def predicciones():
    """shot_id -> probabilidad de gol de mi modelo, solo de las temporadas probadas fuera de muestra."""
    return pd.read_csv(PREDICCIONES)


if __name__ == "__main__":
    resultados()
