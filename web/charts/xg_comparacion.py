"""XGBoost contra LightGBM (y su mezcla), y un árbol de decisión para ver cómo se construye uno.

Cálculo aparte de `xg_modelo.py` y con su propio caché (`data/processed/xg_comparacion.json`):
entrena los dos modelos con las mismas variables, el mismo corte y las mismas semillas que el
modelo final del artículo, y arma el árbol que se dibuja en la página.

Qué sale de aquí:
  * métricas de los tres modelos en 2025-26 y sus diferencias con intervalo (bootstrap por partido);
  * el log-loss al ir sumando árboles (entrenamiento y prueba), que enseña cómo funciona el boosting;
  * el sesgo por grupos de tiros de cada uno;
  * UN árbol de decisión de profundidad 7 con las cuentas de cada nodo (entrenamiento y prueba),
    suficiente para que el navegador simule cualquier límite de profundidad u hojas y cualquiera de
    las dos formas de crecer (por niveles, como XGBoost, o por la mejor hoja, como LightGBM).
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
CACHE = xm.DATA_DIR / "processed" / "xg_comparacion.json"
BASES = ["geo", "contexto", "jugada", "accion"]      # las variables del modelo final
MODELOS = [("xgb", "XGBoost"), ("lgbm", "LightGBM"), ("mezcla", "Mezcla de los dos")]

# El árbol de la página: variables que se leen solas (nada de coordenadas crudas)
ARBOL_PROFUNDIDAD = 7
ARBOL_MIN_HOJA = 250
ACCION_ES = {"Pass": "Pase", "Cross": "Centro", "Ninguna": "Sin acción previa", "Aerial": "Balón aéreo",
             "Rebound": "Rebote", "Chipped": "Pase por alto", "TakeOn": "Regate", "Standard": "Balón detenido",
             "BallRecovery": "Recuperación", "BallTouch": "Control", "HeadPass": "Pase de cabeza",
             "Throughball": "Pase filtrado", "LayOff": "Descarga", "Dispossessed": "Pérdida del rival"}


def _firma():
    h = hashlib.sha1()
    h.update(f"{VERSION}".encode())
    h.update(Path(__file__).read_bytes())
    h.update(Path(xm.__file__).read_bytes())
    for t in xm.CERRADAS:
        for n in ("shots.csv", "partidos.csv"):
            h.update(f"{t}{n}{(xm.DATA_DIR / t / n).stat().st_size}".encode())
    return h.hexdigest()[:16]


def _lgbm(X, y, tr, va, semilla, mono):
    import lightgbm as lgb
    m = lgb.LGBMClassifier(n_estimators=3000, learning_rate=0.05, num_leaves=31, min_child_samples=20,
                           subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0,
                           monotone_constraints=mono, random_state=semilla, n_jobs=4, verbose=-1)
    m.fit(X[tr], y[tr], eval_set=[(X[va], y[va])], eval_metric="binary_logloss",
          callbacks=[lgb.early_stopping(50, verbose=False)])
    return m


def _grupos(st, cols):
    out = []
    nombres = {
        "situation": ("Situación", {"Open Play": "Jugada abierta", "From Corner": "Córner",
                                    "Set Piece": "Balón parado", "Direct Freekick": "Tiro libre directo"}),
        "body_part": ("Parte del cuerpo", {"Right Foot": "Pie derecho", "Left Foot": "Pie izquierdo",
                                           "Head": "Cabeza", "Other": "Otra"}),
        "liga": ("Liga", {}),
    }
    for col, (etq, ren) in nombres.items():
        agg = {c: (c, "sum") for c in cols}
        g = st.groupby(col, observed=True).agg(n=("gol", "size"), goles=("gol", "sum"), **agg)
        g = g[g.n >= 100].sort_values("n", ascending=False)
        out.append({"id": col, "etiqueta": etq, "filas": [
            {"nombre": ren.get(str(i), str(i)), "n": int(r.n),
             "valores": {c.replace("p_", ""): float((r[c] / r.goles - 1) * 100) for c in cols}}
            for i, r in g.iterrows()]})
    return out


def _arbol(s, tr, te):
    """Un árbol de decisión de profundidad 7 con las cuentas de entrenamiento y de prueba de cada nodo."""
    from sklearn.tree import DecisionTreeClassifier
    F = {"dist": s.dist, "angulo": np.degrees(s.angulo), "dist_y": s.dist_y,
         "asistido": s.asistido, "rebote": s.rebote,
         "cabeza": (s.body_part == "Head").astype(int), "pie_der": (s.body_part == "Right Foot").astype(int),
         "pie_izq": (s.body_part == "Left Foot").astype(int),
         "corner": (s.situation == "From Corner").astype(int), "abp": (s.situation == "Set Piece").astype(int),
         "tiro_libre": (s.situation == "Direct Freekick").astype(int)}
    for a in xm.ACCIONES:
        F[f"acc_{a}"] = (s.accion == a).astype(int)
    F = pd.DataFrame(F)
    etiquetas = {"dist": ("Distancia", "m"), "angulo": ("Ángulo", "°"), "dist_y": ("Dist. al centro", "m"),
                 "asistido": ("Asistido", None), "rebote": ("Rebote", None), "cabeza": ("De cabeza", None),
                 "pie_der": ("Pie derecho", None), "pie_izq": ("Pie izquierdo", None),
                 "corner": ("Córner", None), "abp": ("Balón parado", None), "tiro_libre": ("Tiro libre directo", None)}
    for a in xm.ACCIONES:
        etiquetas[f"acc_{a}"] = (f"Tras: {ACCION_ES.get(a, a).lower()}", None)

    ytr = s.gol.values[tr]
    arbol = DecisionTreeClassifier(criterion="log_loss", max_depth=ARBOL_PROFUNDIDAD,
                                   min_samples_leaf=ARBOL_MIN_HOJA, random_state=0)
    arbol.fit(F[tr], ytr)
    T = arbol.tree_

    def cuentas(mask):
        dp = arbol.decision_path(F[mask])
        n = np.asarray(dp.sum(axis=0)).ravel()
        pos = np.asarray(dp.T @ s.gol.values[mask]).ravel()
        return n.astype(int), pos.astype(int)
    n_tr, p_tr = cuentas(tr)
    n_te, p_te = cuentas(te)
    prof = np.zeros(T.node_count, dtype=int)
    for i in range(T.node_count):
        for h in (T.children_left[i], T.children_right[i]):
            if h >= 0:
                prof[h] = prof[i] + 1
    nodos = []
    for i in range(T.node_count):
        f = int(T.feature[i])
        if T.children_left[i] < 0:
            nodos.append([-1, 0, -1, -1, int(prof[i]), int(n_tr[i]), int(p_tr[i]), int(n_te[i]), int(p_te[i])])
            continue
        binaria = set(np.unique(F.iloc[:, f])) <= {0, 1}
        # "sí" = el lado donde la pregunta se cumple: en una binaria es el 1 (derecha), en una numérica el <=
        si, no = (int(T.children_right[i]), int(T.children_left[i])) if binaria \
            else (int(T.children_left[i]), int(T.children_right[i]))
        nodos.append([f, round(float(T.threshold[i]), 2), si, no, int(prof[i]), int(n_tr[i]), int(p_tr[i]),
                      int(n_te[i]), int(p_te[i])])
    return {"features": [{"id": c, "etiqueta": etiquetas[c][0], "unidad": etiquetas[c][1],
                          "tipo": "bin" if c not in ("dist", "angulo", "dist_y") else "num"} for c in F.columns],
            "nodos": nodos, "n_train": int(tr.sum()), "n_test": int(te.sum()),
            "profundidad": ARBOL_PROFUNDIDAD, "min_hoja": ARBOL_MIN_HOJA}


def _calcular(log=print):
    t0 = time.time()
    s, _ = xm._armar(xm.CERRADAS, [])
    B = xm._bloques(s)
    X = xm._matriz(B, BASES)
    y = s.gol.values
    tr = s.temporada.isin(xm.TRAIN).values
    va = (s.temporada == xm.VALID).values
    te = (s.temporada == xm.TEST).values
    yte = y[te]
    mono = [(-1 if c == "dist" else 1 if c == "angulo" else 0) for c in X.columns]
    boot = xm._Bootstrap(s.game_id.values[te])

    R = {"n": {"train": int(tr.sum()), "test": int(te.sum())}}
    modelos, probs, tiempos, arboles = {}, {"xgb": [], "lgbm": []}, {}, {}
    for sem in xm.SEMILLAS:
        t = time.time()
        mx = xm._ajustar(X, y, tr, va, sem, True)
        tx = time.time() - t
        t = time.time()
        ml = _lgbm(X, y, tr, va, sem, mono)
        tl = time.time() - t
        probs["xgb"].append(mx.predict_proba(X[te])[:, 1])
        probs["lgbm"].append(ml.predict_proba(X[te])[:, 1])
        if sem == xm.SEMILLAS[0]:
            modelos = {"xgb": mx, "lgbm": ml}
            tiempos = {"xgb": tx, "lgbm": tl}
            arboles = {"xgb": int(mx.best_iteration), "lgbm": int(ml.best_iteration_)}
        log(f"    semilla {sem}: xgb {tx:.0f}s lgbm {tl:.0f}s  [{time.time()-t0:.0f}s]")
    P = {k: np.mean(v, axis=0) for k, v in probs.items()}
    P["mezcla"] = 0.5 * P["xgb"] + 0.5 * P["lgbm"]
    und = s.xg.values[te]

    met = []
    for k, nombre in MODELOS:
        m = xm._metricas(yte, P[k])
        d, lo, hi = (None, None, None) if k == "xgb" else boot.dif(P[k], P["xgb"], yte)
        du, ulo, uhi = boot.dif(P[k], und, yte)
        met.append({"id": k, "nombre": nombre, **m, "d_xgb": d, "d_xgb_lo": lo, "d_xgb_hi": hi,
                    "d_und": du, "d_und_lo": ulo, "d_und_hi": uhi,
                    "arboles": arboles.get(k), "seg": tiempos.get(k)})
    R["metricas"] = met
    d, lo, hi = boot.dif(und, P["xgb"], yte)
    R["understat_vs_xgb"] = {"d": d, "lo": lo, "hi": hi, **xm._metricas(yte, und)}
    R["correlacion"] = {"xgb_lgbm": float(np.corrcoef(P["xgb"], P["lgbm"])[0, 1])}

    # sesgo por grupos
    st = s[te].reset_index(drop=True)
    for k in ("xgb", "lgbm", "mezcla"):
        st[f"p_{k}"] = P[k]
    st["p_understat"] = und
    R["grupos"] = _grupos(st, ["p_xgb", "p_lgbm", "p_mezcla", "p_understat"])

    # el boosting visto desde dentro: log-loss al ir sumando árboles
    rng = np.random.default_rng(0)
    idx = rng.choice(np.flatnonzero(tr), size=30000, replace=False)
    Xte, Xtr = X[te], X.iloc[idx]
    ytr_s = y[idx]
    curvas = {}
    for k, m in modelos.items():
        n = arboles[k]
        ks = sorted(set(int(round(v)) for v in np.geomspace(1, n, 18)))
        pts = []
        for j in ks:
            if k == "xgb":
                pt = m.predict_proba(Xte, iteration_range=(0, j))[:, 1]
                pr = m.predict_proba(Xtr, iteration_range=(0, j))[:, 1]
            else:
                pt = m.predict_proba(Xte, num_iteration=j)[:, 1]
                pr = m.predict_proba(Xtr, num_iteration=j)[:, 1]
            pts.append({"k": j, "prueba": float(xm._perdida(yte, pt).mean()),
                        "entrenamiento": float(xm._perdida(ytr_s, pr).mean())})
        curvas[k] = pts
    R["curvas"] = curvas

    # un árbol solo
    log("    árbol de decisión...")
    R["arbol"] = _arbol(s, tr, te)
    R["tiempo_s"] = float(time.time() - t0)
    return R


def resultados(log=print):
    firma = _firma()
    if CACHE.exists() and os.environ.get("XG_REHACER") != "1":
        c = json.loads(CACHE.read_text(encoding="utf-8"))
        if c.get("firma") == firma or os.environ.get("XG_SOLO_CACHE") == "1":
            log(f"  xG comparación: resultados en caché (firma {c.get('firma')})")
            return c["resultados"]
    log("  xG comparación: entrenando XGBoost y LightGBM (unos 5 min)...")
    R = _calcular(log)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps({"firma": firma, "resultados": R}, ensure_ascii=False), encoding="utf-8")
    return R
