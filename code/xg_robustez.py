"""Chequeos de robustez y de fuga del modelo de xG. NO corre en el build del sitio.

    python code/xg_robustez.py          # ~30-40 min; escribe data/processed/xg_robustez.json

Complementa lo que ya mide `web/charts/xg_modelo.py` (escalera con intervalos, dos semillas, subgrupos,
calibración) y el test `web/tests/test_xg_causal.py` (invariancia al futuro de las variables):

  1. **Cruces entre conjuntos**: ningún tiro ni partido está en dos de entrenamiento / validación / prueba.
  2. **Etiquetas barajadas**: el mismo modelo entrenado con los goles barajados tiene que quedar en el
     log-loss de predecir la tasa global. Si quedara mejor, habría información del resultado en las
     variables por otro lado.
  3. **Fuga residual del orden dentro del minuto**: `rebote_previo` usa el orden de `shot_id`; cuántos
     goles quedan antes de otro tiro del mismo equipo en su minuto (si el orden fuera perfecto, casi cero).
  4. **¿El tuning generaliza?** Parámetros de antes contra los del tuning en 2018-19, 2019-20 y 2020-21,
     que el tuning nunca vio (ni como entrenamiento ni como validación), con el mismo corte que
     `xg_temporadas.py` (entrena las tres anteriores a la de validación) y una semilla.
"""

import json
import sys
import time
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "web"))
sys.path.insert(0, str(RAIZ / "web" / "charts"))

import xg_modelo as xm  # noqa: E402

SALIDA = xm.DATA_DIR / "processed" / "xg_robustez.json"
FUERA_DEL_TUNING = ["2018-19", "2019-20", "2020-21"]


def main():
    t0 = time.time()
    R = {"params": xm.PARAMS, "origen_params": xm.ORIGEN_PARAMS}
    cerradas, historicas = xm.temporadas_disponibles()
    s, _ = xm._armar(cerradas, historicas)
    X = xm._matriz(xm._bloques(s), xm.BLOQUES_FINAL)
    y = s.gol.values
    T = s.temporada.values
    tr, va, te = np.isin(T, xm.TRAIN), T == xm.VALID, T == xm.TEST

    # 1) cruces
    conj = {"entrena": tr, "valida": va, "prueba": te}
    cruces = {}
    for a in conj:
        for b in conj:
            if a < b:
                cruces[f"{a}-{b}"] = {
                    "tiros": len(set(s.shot_id[conj[a]]) & set(s.shot_id[conj[b]])),
                    "partidos": len(set(s.game_id[conj[a]]) & set(s.game_id[conj[b]]))}
    R["cruces"] = cruces
    R["temporadas_en_datos"] = sorted(set(T))
    print("cruces:", cruces, flush=True)

    # 2) etiquetas barajadas (en entrenamiento y validación; la prueba conserva los goles reales)
    rng = np.random.default_rng(0)
    yb = y.copy()
    for k in (tr, va):
        yb[k] = rng.permutation(y[k])
    m = xm._ajustar(X, yb, tr, va, 42, True)
    p = m.predict_proba(X[te])[:, 1]
    base = float(xm._perdida(y[te], np.full(te.sum(), y[tr].mean())).mean())
    R["etiquetas_barajadas"] = {"ll": float(xm._perdida(y[te], p).mean()), "ll_tasa_global": base,
                                "arboles": int(m.best_iteration) + 1, "auc": xm._metricas(y[te], p)["auc"]}
    print("barajadas:", R["etiquetas_barajadas"], f"[{time.time() - t0:.0f}s]", flush=True)

    # 3) orden dentro del minuto
    c = s[np.isin(T, xm.CERRADAS)]
    clave = ["game_id", "team", "minute"]
    n = c.groupby(clave)["shot_id"].transform("size")
    pos = c.sort_values("shot_id", kind="stable").groupby(clave).cumcount().reindex(c.index)
    multi = n > 1
    goles_multi = int(c.gol[multi].sum())
    no_ultimo = int(c.gol[multi & (pos < n - 1)].sum())
    R["orden_minuto"] = {"goles_en_minutos_con_varios_tiros": goles_multi,
                         "goles_que_no_son_el_ultimo_tiro": no_ultimo,
                         "fraccion": no_ultimo / goles_multi if goles_multi else None}
    print("orden:", R["orden_minuto"], flush=True)

    # 4) tuning fuera de las temporadas que vio
    temps = sorted(set(T))
    filas = []
    for t in FUERA_DEL_TUNING:
        i = temps.index(t)
        trk, vak, tek = np.isin(T, temps[i - 4:i - 1]), T == temps[i - 1], T == t
        boot = xm._Bootstrap(s.game_id.values[tek], repeticiones=2000)
        pb = xm._ajustar(X, y, trk, vak, 42, True, params=xm.PARAMS_BASE).predict_proba(X[tek])[:, 1]
        mt = xm._ajustar(X, y, trk, vak, 42, True)
        pt = mt.predict_proba(X[tek])[:, 1]
        d, lo, hi = boot.dif(pt, pb, y[tek])
        filas.append({"temporada": t, "ll_base": float(xm._perdida(y[tek], pb).mean()),
                      "ll_tuning": float(xm._perdida(y[tek], pt).mean()), "arboles_tuning": int(mt.best_iteration) + 1,
                      "d_ll": d, "d_lo": lo, "d_hi": hi})
        print(f"  {t}: base {filas[-1]['ll_base']:.5f} tuning {filas[-1]['ll_tuning']:.5f} "
              f"dif {d:+.5f} [{lo:+.5f}, {hi:+.5f}]  [{time.time() - t0:.0f}s]", flush=True)
    R["tuning_fuera"] = filas
    R["tiempo_s"] = time.time() - t0
    SALIDA.write_text(json.dumps(R, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"escrito {SALIDA}", flush=True)


if __name__ == "__main__":
    main()
