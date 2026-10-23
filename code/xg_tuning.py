"""Búsqueda de hiperparámetros del modelo de xG con Optuna. NO corre en el build del sitio.

    python code/xg_tuning.py                  # 80 pruebas (retoma si se cortó)
    python code/xg_tuning.py --pruebas 120

Usa las mismas variables que el modelo final de `web/charts/xg_modelo.py` (geometría, parte del cuerpo y
situación, asistido, rebote previo y acción previa, con monotonía en distancia y ángulo) y dos folds
temporales expansivos; el objetivo es la media del log-loss de validación de los dos:

    fold A: entrena 2021-22 y 2022-23           -> valida 2023-24
    fold B: entrena 2021-22, 2022-23 y 2023-24  -> valida 2024-25

2025-26 no se toca: es la temporada de prueba del artículo y no debe elegir nada.

Cada prueba entrena con early stopping (60 rondas, tope de 6000 árboles). TPE con semilla 1 y 10
pruebas aleatorias al inicio; antes de esas van dos puntos fijos: los parámetros de antes del tuning y
el mejor hallazgo de la auditoría (32 pruebas, que topaban en 3000 árboles).

Las pruebas se guardan en `data/processed/xg_tuning.db` (si se corta, se retoma donde iba) y al final:
  * `data/processed/xg_params.json`: los mejores parámetros con fecha, número de pruebas y valor de
    validación. Es lo que lee `xg_modelo.py` (y su firma: cambiarlo invalida el caché del modelo);
  * `data/processed/xg_tuning_pruebas.csv`: todas las pruebas.
"""

import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "web"))
sys.path.insert(0, str(RAIZ / "web" / "charts"))

import xg_modelo as xm  # noqa: E402

BLOQUES = ["geo", "contexto", "jugada", "accion"]
FOLDS = [("A", ["2021-22", "2022-23"], "2023-24"),
         ("B", ["2021-22", "2022-23", "2023-24"], "2024-25")]
SEMILLA_XGB = 42
ESPACIO = {
    "learning_rate": (0.02, 0.12, "log"), "max_depth": (3, 8, "int"),
    "min_child_weight": (3, 150, "log"), "subsample": (0.5, 1.0, "lin"),
    "colsample_bytree": (0.4, 1.0, "lin"), "reg_lambda": (0.1, 50, "log"),
    "reg_alpha": (1e-3, 5, "log"), "gamma": (0, 2, "lin"),
}
INICIALES = [
    # los de antes del tuning (alpha y gamma en su mínimo, ~0)
    dict(xm.PARAMS_BASE, reg_alpha=1e-3, gamma=0.0),
    # el mejor de la auditoría (32 pruebas)
    dict(learning_rate=0.0412, max_depth=4, min_child_weight=3.29, subsample=0.85, colsample_bytree=0.51,
         reg_lambda=1.35, reg_alpha=1.78, gamma=0.39),
]
DB = xm.DATA_DIR / "processed" / "xg_tuning.db"
PRUEBAS_CSV = xm.DATA_DIR / "processed" / "xg_tuning_pruebas.csv"
ESTUDIO = "xg_rebote_previo_v1"


def main():
    import optuna
    from xgboost import XGBClassifier

    ap = argparse.ArgumentParser()
    ap.add_argument("--pruebas", type=int, default=80, help="pruebas en total (contando las ya hechas)")
    ap.add_argument("--hilos", type=int, default=6)
    args = ap.parse_args()

    t0 = time.time()
    s, _ = xm._armar(xm.CERRADAS, [])
    X = xm._matriz(xm._bloques(s), BLOQUES)
    y = s.gol.values
    T = s.temporada.values
    if (T == xm.TEST).any():
        X, y, T = X[T != xm.TEST], y[T != xm.TEST], T[T != xm.TEST]   # 2025-26 fuera desde el principio
    mono = tuple(-1 if c == "dist" else 1 if c == "angulo" else 0 for c in X.columns)
    folds = [(nombre, np.isin(T, entrena), T == valida) for nombre, entrena, valida in FOLDS]
    print(f"{len(X)} tiros sin {xm.TEST}, {X.shape[1]} columnas; datos listos en {time.time() - t0:.0f}s", flush=True)

    def objetivo(trial):
        p = {}
        for k, (lo, hi, tipo) in ESPACIO.items():
            p[k] = (trial.suggest_int(k, lo, hi) if tipo == "int"
                    else trial.suggest_float(k, lo, hi, log=(tipo == "log")))
        vals = []
        for nombre, tr, va in folds:
            m = XGBClassifier(n_estimators=xm.ARBOLES_MAX, early_stopping_rounds=xm.PARADA,
                              random_state=SEMILLA_XGB, monotone_constraints=mono, eval_metric="logloss",
                              n_jobs=args.hilos, **p)
            m.fit(X[tr], y[tr], eval_set=[(X[va], y[va])], verbose=False)
            trial.set_user_attr(f"arboles_{nombre}", int(m.best_iteration) + 1)
            trial.set_user_attr(f"ll_{nombre}", float(m.best_score))
            vals.append(m.best_score)
        v = float(np.mean(vals))
        print(f"  prueba {trial.number:3d}: {v:.5f}  árboles {[trial.user_attrs[f'arboles_{n}'] for n, _, _ in folds]}"
              f"  [{time.time() - t0:.0f}s]", flush=True)
        return v

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    DB.parent.mkdir(parents=True, exist_ok=True)
    estudio = optuna.create_study(study_name=ESTUDIO, storage=f"sqlite:///{DB.as_posix()}", load_if_exists=True,
                                  direction="minimize",
                                  sampler=optuna.samplers.TPESampler(seed=1, n_startup_trials=10))
    hechas = [t for t in estudio.trials if t.state == optuna.trial.TrialState.COMPLETE]
    if not estudio.trials:
        for p in INICIALES:
            estudio.enqueue_trial(p)
    faltan = args.pruebas - len(hechas)
    print(f"pruebas hechas {len(hechas)}, faltan {max(faltan, 0)}", flush=True)
    if faltan > 0:
        estudio.optimize(objetivo, n_trials=faltan)

    completas = [t for t in estudio.trials if t.state == optuna.trial.TrialState.COMPLETE]
    mejor = estudio.best_trial
    inicial = completas[0]
    arboles = {n: mejor.user_attrs[f"arboles_{n}"] for n, _, _ in folds}
    if max(arboles.values()) >= xm.ARBOLES_MAX:
        print(f"OJO: la mejor prueba topó en {xm.ARBOLES_MAX} árboles", flush=True)
    salida = {
        "fecha": dt.date.today().isoformat(),
        "pruebas": len(completas),
        "valor_validacion": float(mejor.value),
        "valor_validacion_por_fold": {n: mejor.user_attrs[f"ll_{n}"] for n, _, _ in folds},
        "arboles_por_fold": arboles,
        "valor_parametros_anteriores": float(inicial.value),
        "folds": [{"id": n, "entrena": e, "valida": v} for n, e, v in FOLDS],
        "busqueda": {"sampler": "TPE", "semilla": 1, "pruebas_iniciales": 10, "tope_arboles": xm.ARBOLES_MAX,
                     "early_stopping": xm.PARADA, "semilla_xgboost": SEMILLA_XGB,
                     "espacio": {k: list(v) for k, v in ESPACIO.items()}},
        "params": {k: (int(v) if k == "max_depth" else float(v)) for k, v in mejor.params.items()},
    }
    xm.PARAMS_JSON.write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")
    estudio.trials_dataframe().to_csv(PRUEBAS_CSV, index=False)
    print(f"\n{len(completas)} pruebas en {time.time() - t0:.0f}s", flush=True)
    print(f"parámetros de antes: {inicial.value:.5f} · mejor (prueba {mejor.number}): {mejor.value:.5f}", flush=True)
    print(json.dumps(salida["params"], indent=2), flush=True)
    print(f"escrito {xm.PARAMS_JSON}", flush=True)


if __name__ == "__main__":
    main()
