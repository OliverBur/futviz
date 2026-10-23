"""El modelo de xG y todo lo que se mide a su alrededor, calculado una sola vez.

`ml_xg.py` arma el artículo; este módulo hace el trabajo caro: cargar los tiros, entrenar los
modelos de la escalera, la curva de aprendizaje y el envejecimiento, y dejar listas las tablas que
usan las gráficas. Entrenar todo tarda unos 15-20 minutos, así que el resultado se guarda en
`data/processed/xg_v2.json` y solo se recalcula si cambian los datos de entrada o este archivo
(o con `XG_REHACER=1`).

Qué se mide, y contra qué (todo sobre 2025-26, que ningún modelo ve al entrenar):

  * la **escalera**: a un modelo de geometría se le van sumando grupos de variables, cada uno con
    su diferencia de log-loss frente al paso anterior y su intervalo (bootstrap por partido);
  * las **variables de contexto** (marcador, local, nivel de los equipos, puesto del tirador), con
    una regresión logística sobre el logit del modelo final: dice si hay señal y cuánta;
  * la **curva de aprendizaje** y el **envejecimiento**, con las temporadas históricas;
  * la **calibración** y el **sesgo** frente a Understat, por grupos y por equipo;
  * el **modelo publicado**: los mismos parámetros, reentrenado con 2021-25 y probado una sola vez en
    2025-26. Es el de las rejillas de "lo que aprendió" y el de la comparación final con Understat;
  * la **importancia** de las variables por permutación agrupada y por SHAP (no por ganancia media
    por corte, que premia a las variables usadas en pocos cortes grandes).

Los hiperparámetros salen de `data/processed/xg_params.json`, que escribe `code/xg_tuning.py` (Optuna
con validación temporal; no corre en el build). Sin ese archivo se usan los de antes (`PARAMS_BASE`).

Todas las variables usan solo el tiro y lo que pasó ANTES en su partido: `web/tests/test_xg_causal.py`
borra los tiros posteriores y comprueba que no cambian. La versión anterior marcaba como "rebote" a
cualquier tiro con otro del mismo equipo en el mismo minuto, también si el otro venía DESPUÉS: el
primero de esos grupos casi nunca es gol (si entra, la jugada se corta), así que el modelo se
enteraba del resultado por el tiro siguiente.
"""

import hashlib
import json
import os
import time
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

from site_utils import DATA_DIR

VERSION = 2
CERRADAS = ["2021-22", "2022-23", "2023-24", "2024-25", "2025-26"]
HISTORICAS = ["2014-15", "2015-16", "2016-17", "2017-18", "2018-19", "2019-20", "2020-21"]
TRAIN, VALID, TEST = CERRADAS[:3], CERRADAS[3], CERRADAS[4]
LARGO, ANCHO, PORTERIA = 105.0, 68.0, 7.32
ANGULO_MINIMO = np.radians(2)
SEMILLAS = [42, 7]
ARBOLES_MAX, PARADA = 6000, 60      # tope de árboles y early stopping: los mismos que en el tuning
FACTOR_PUBLICADO = 1.25             # el modelo publicado entrena con una temporada más: 25% más árboles

CACHE = DATA_DIR / "processed" / "xg_v2.json"
PARAMS_JSON = DATA_DIR / "processed" / "xg_params.json"

# Los hiperparámetros de antes del tuning. Se siguen usando donde no deben influir los de Optuna: la
# prueba hacia atrás (`xg_temporadas.py`: el tuning validó en 2023-24 y 2024-25, que ahí son prueba),
# la comparación de algoritmos (`xg_comparacion.py`: LightGBM no se ajustó) y el envejecimiento.
PARAMS_BASE = dict(learning_rate=0.05, max_depth=5, min_child_weight=20, subsample=0.8,
                   colsample_bytree=0.8, reg_lambda=1.0)
FIJOS = dict(eval_metric="logloss", n_jobs=4)


def _leer_params():
    """Los hiperparámetros de `xg_params.json` (los escribe `code/xg_tuning.py`), o los de antes."""
    if PARAMS_JSON.exists():
        return json.loads(PARAMS_JSON.read_text(encoding="utf-8"))["params"], "tuning"
    return dict(PARAMS_BASE), "base"


PARAMS, ORIGEN_PARAMS = _leer_params()

# Nombre del equipo en Understat -> en fbref (el `Squad` de elo.csv), solo donde no coinciden.
US_A_FBREF = {
    "AC Milan": "Milan", "Alaves": "Alavés", "Almeria": "Almería", "Arminia Bielefeld": "Arminia",
    "Atletico Madrid": "Atlético Madrid", "Bayer Leverkusen": "Leverkusen",
    "Borussia Dortmund": "Dortmund", "Borussia M.Gladbach": "Gladbach", "Cadiz": "Cádiz",
    "Darmstadt": "Darmstadt 98", "Eintracht Frankfurt": "Frankfurt", "FC Cologne": "Köln",
    "FC Heidenheim": "Heidenheim", "Greuther Fuerth": "Greuther Fürth", "Hertha Berlin": "Hertha BSC",
    "Ipswich": "Ipswich Town", "Leeds": "Leeds United", "Leganes": "Leganés",
    "Leicester": "Leicester City", "Luton": "Luton Town", "Manchester United": "Manchester Utd",
    "Newcastle United": "Newcastle", "Norwich": "Norwich City", "Nottingham Forest": "Nottingham",
    "Paris Saint Germain": "PSG", "Parma Calcio 1913": "Parma", "RasenBallsport Leipzig": "RB Leipzig",
    "Real Oviedo": "Oviedo", "Real Valladolid": "Valladolid", "Saint-Etienne": "Saint-Étienne",
    "St. Pauli": "St Pauli", "Verona": "Hellas Verona", "VfB Stuttgart": "Stuttgart",
    "Wolverhampton Wanderers": "Wolves",
}

# Las acciones previas que se quedan como categoría propia; el resto (menos de 500 tiros en las
# cinco temporadas) se junta en "Otra". Fijo, para que todos los modelos vean las mismas columnas.
ACCIONES = ["Pass", "Cross", "Ninguna", "Aerial", "Rebound", "Chipped", "TakeOn", "Standard",
            "BallRecovery", "BallTouch", "HeadPass", "Throughball", "LayOff", "Dispossessed"]
SITUACIONES = ["Open Play", "From Corner", "Set Piece", "Direct Freekick"]
PARTES = ["Right Foot", "Left Foot", "Head", "Other"]

# La escalera: (id, nombre, bloques de variables, monotonía, grupo). Cada paso suma al anterior.
GEO = ["geo"]
ESCALERA = [
    ("geo", "Geometría: distancia, ángulo y posición", GEO, False, "base"),
    ("cuerpo", "+ parte del cuerpo y situación", GEO + ["contexto"], False, "base"),
    ("jugada", "+ si fue asistido y si hubo un tiro antes en ese minuto", GEO + ["contexto", "jugada"], False, "base"),
    ("accion", "+ la acción previa al tiro", GEO + ["contexto", "jugada", "accion"], False, "base"),
    ("mono", "+ restricciones de monotonía", GEO + ["contexto", "jugada", "accion"], True, "base"),
    ("estado", "+ marcador y minuto", GEO + ["contexto", "jugada", "accion", "estado"], True, "contexto"),
    ("local", "+ local o visitante", GEO + ["contexto", "jugada", "accion", "estado", "local"], True, "contexto"),
    ("rol", "+ puesto del tirador", GEO + ["contexto", "jugada", "accion", "estado", "local", "rol"], True, "contexto"),
    ("nivel", "+ nivel de los dos equipos (ELO)",
     GEO + ["contexto", "jugada", "accion", "estado", "local", "rol", "nivel"], True, "contexto"),
]
FINAL = "mono"          # el paso de la escalera que se queda como modelo
BASE_ANTERIOR = "jugada"  # "el modelo de hoy" del primer artículo: la referencia de comparación
BLOQUES_FINAL = next(bl for pid, _, bl, _, _ in ESCALERA if pid == FINAL)

# Las variables tal como las entiende alguien que mira el partido: para el SHAP del artículo.
ORIGINALES = [(c, lambda x, c=c: x == c) for c in ("dist", "angulo", "dist_y", "location_x", "location_y",
                                                  "asistido", "rebote_previo")] + [
    ("accion", lambda c: c.startswith("accion_")), ("cuerpo", lambda c: c.startswith("body_part_")),
    ("situacion", lambda c: c.startswith("situation_"))]

# Grupos para la importancia por permutación: se permutan juntas las columnas de un mismo grupo.
GRUPOS_IMPORTANCIA = [
    ("geo", "Geometría", lambda c: c in ("dist", "angulo", "dist_y", "location_x", "location_y")),
    ("accion", "Acción previa", lambda c: c.startswith("accion_")),
    ("rebote_previo", "Rebote previo", lambda c: c == "rebote_previo"),
    ("cuerpo", "Parte del cuerpo", lambda c: c.startswith("body_part_")),
    ("situacion", "Situación", lambda c: c.startswith("situation_")),
    ("asistido", "Asistido", lambda c: c == "asistido"),
]


def _sin_acentos(s):
    return "".join(c for c in unicodedata.normalize("NFKD", str(s)) if not unicodedata.combining(c))


# ------------------------------------------------------------------------------------------------
# datos
# ------------------------------------------------------------------------------------------------

def _temporada_completa(t):
    ruta = DATA_DIR / t / "shots.csv"
    if not ruta.exists() or not (DATA_DIR / t / "partidos.csv").exists():
        return False
    return pd.read_csv(ruta, encoding="utf-8-sig", usecols=["liga"])["liga"].nunique() == 5


def temporadas_disponibles():
    """Las cerradas (obligatorias) y las históricas que estén completas."""
    faltan = [t for t in CERRADAS if not _temporada_completa(t)]
    if faltan:
        raise SystemExit(f"xG: faltan shots.csv/partidos.csv completos de {faltan}. "
                         "Corre `python code/fetch_shots.py --partidos` y `--last-action`.")
    return CERRADAS, [t for t in HISTORICAS if _temporada_completa(t)]


def _firma(temporadas, extra=""):
    h = hashlib.sha1()
    h.update(f"{VERSION}{extra}".encode())
    h.update(Path(__file__).read_bytes())
    if PARAMS_JSON.exists():
        h.update(PARAMS_JSON.read_bytes())
    for t in temporadas:
        for nombre in ("shots.csv", "partidos.csv"):
            st = (DATA_DIR / t / nombre).stat()
            h.update(f"{t}{nombre}{st.st_size}".encode())
    return h.hexdigest()[:16]


def _cargar(temporadas):
    partes = []
    for t in temporadas:
        s = pd.read_csv(DATA_DIR / t / "shots.csv", encoding="utf-8-sig")
        p = pd.read_csv(DATA_DIR / t / "partidos.csv", encoding="utf-8-sig")[["game_id", "local", "visita"]]
        s = s.merge(p, on="game_id", how="left")
        if s["local"].isna().any():
            raise SystemExit(f"xG: {t} tiene partidos sin fila en partidos.csv.")
        partes.append(s)
    s = pd.concat(partes, ignore_index=True)
    s["es_local"] = (s.team == s["local"]).astype(int)
    # el equipo que concedió el tiro: 95 tiros de 4 partidos en que el otro equipo no remató
    s["rival"] = s["rival"].fillna(pd.Series(np.where(s.es_local == 1, s.visita, s["local"]), index=s.index))
    s["fecha"] = pd.to_datetime(s["date"])
    return s


def _marcador(s):
    """Goles de ventaja de quien tira, contando solo los goles de minutos ANTERIORES: dentro de un
    mismo minuto el orden de los tiros no es fiable (`shot_id` sigue el tiempo en el 87% de los
    partidos). El autogol lo anota Understat con el equipo del que lo mete y cuenta para el rival
    (verificado contra el marcador final en 720 partidos con autogol)."""
    v = np.where(s.result == "Goal", np.where(s.es_local == 1, 1, -1),
                 np.where(s.result == "Own Goal", np.where(s.es_local == 1, -1, 1), 0))
    t = pd.DataFrame({"game_id": s.game_id, "minute": s.minute, "v": v})
    pm = t.groupby(["game_id", "minute"])["v"].sum().reset_index().sort_values(["game_id", "minute"])
    pm["antes"] = pm.groupby("game_id")["v"].cumsum() - pm["v"]
    antes = s[["game_id", "minute"]].merge(pm[["game_id", "minute", "antes"]], on=["game_id", "minute"], how="left")["antes"]
    return np.where(s.es_local == 1, antes.values, -antes.values)


def _rebote_previo(s):
    """1 si el mismo equipo ya había rematado en ese partido y en ese minuto: un tiro ANTERIOR, con el
    orden de `shot_id`. Es la versión causal del viejo `rebote`, que también contaba los tiros
    posteriores. Limitación: `shot_id` sigue el tiempo en el 87% de los partidos, así que en el resto
    algún tiro puede quedar marcado (o sin marcar) por un orden equivocado dentro del minuto."""
    orden = s.sort_values("shot_id", kind="stable").groupby(["game_id", "team", "minute"]).cumcount()
    return (orden.reindex(s.index) > 0).astype(int)


def _preparar(s):
    """De los tiros crudos de uno o más partidos (con `es_local`) a la tabla del modelo, sin las
    variables de temporada (ELO, puesto). Todo lo que se calcula aquí usa solo el tiro y los tiros
    anteriores de su partido; `web/tests/test_xg_causal.py` lo comprueba borrando los posteriores."""
    s = s.copy()
    s["marcador"] = _marcador(s)
    s["gol"] = (s.result == "Goal").astype(int)
    pen = s[s.situation == "Penalty"]
    penales = {"n": int(len(pen)), "conversion": float(pen.gol.mean()) if len(pen) else float("nan"),
               "xg_understat": float(pen.xg.mean()) if len(pen) else float("nan")}
    s = s[(s.result != "Own Goal") & (s.situation != "Penalty")].copy()

    px, py = s.location_x * LARGO, s.location_y * ANCHO
    s["dist"] = np.hypot(LARGO - px, ANCHO / 2 - py)
    a = np.hypot(LARGO - px, ANCHO / 2 + PORTERIA / 2 - py)
    b = np.hypot(LARGO - px, ANCHO / 2 - PORTERIA / 2 - py)
    s["angulo"] = np.arccos(np.clip((a ** 2 + b ** 2 - PORTERIA ** 2) / (2 * a * b), -1, 1))
    s["dist_y"] = (s.location_y - 0.5).abs() * ANCHO
    s["asistido"] = s.assist_player.notna().astype(int)
    s["rebote_previo"] = _rebote_previo(s)
    # La definición vieja, que también contaba los tiros POSTERIORES. NO es variable del modelo: solo
    # sirve para medir, en el recuadro de corrección del artículo, cuánto pesaba la fuga.
    s["rebote_con_fuga"] = (s.groupby(["game_id", "team", "minute"])["shot_id"].transform("size") > 1).astype(int)
    olimpicos ={"n": int((s.angulo < ANGULO_MINIMO).sum()),
                 "goles": int(s.loc[s.angulo < ANGULO_MINIMO, "gol"].sum())}
    s = s[s.angulo >= ANGULO_MINIMO].drop_duplicates("shot_id").reset_index(drop=True)
    s["accion"] = s.last_action.where(s.last_action.isin(ACCIONES), "Otra")
    return s, penales, olimpicos


def _elo(s, temporadas):
    """ELO de cada club el día del partido (el vigente antes de jugarlo), el propio y el del rival."""
    club = {}
    for t in temporadas:
        elo = pd.read_csv(DATA_DIR / t / "elo.csv", encoding="utf-8-sig")
        por_squad = dict(zip(elo.Squad, elo.elo_club))
        en_us = set(s.loc[s.temporada == t, "team"]) | set(s.loc[s.temporada == t, "rival"])
        pares = {u: US_A_FBREF.get(u, u) for u in en_us}
        if set(pares.values()) != set(por_squad):
            raise SystemExit(f"xG: los equipos de Understat y de elo.csv no coinciden en {t}: "
                             f"{sorted(set(pares.values()) ^ set(por_squad))}")
        for u, sq in pares.items():
            club[(t, u)] = por_squad[sq]
    hist = {}
    for n in set(club.values()):
        h = pd.read_csv(DATA_DIR / ".clubelo" / f"{n.replace(' ', '_')}.csv")
        h["From"] = pd.to_datetime(h["From"])
        hist[n] = h.sort_values("From").reset_index(drop=True)

    def de(col):
        out = np.full(len(s), np.nan)
        claves = pd.Series(list(zip(s.temporada, s[col])), index=s.index)
        for k, idx in claves.groupby(claves).groups.items():
            h = hist[club[k]]
            pos = np.clip(np.searchsorted(h["From"].values, s.loc[idx, "fecha"].values, side="right") - 1,
                          0, len(h) - 1)
            out[s.index.get_indexer(idx)] = h["Elo"].values[pos]
        return out
    return de("team"), de("rival")


def _armar(temporadas_cerradas, historicas):
    """La tabla de tiros (sin penales, sin autogoles, sin los de menos de 2° de portería visible) con
    todas las variables. Las de nivel y puesto solo existen en las temporadas cerradas."""
    todas = list(temporadas_cerradas) + list(historicas)
    s = _cargar(todas)
    n_total = len(s)
    s, penales, olimpicos = _preparar(s)

    # ELO: el vigente el día del partido (clubelo lo cambia desde el día siguiente). Puesto: el de fbref
    # en la temporada, que resume toda la temporada (también partidos posteriores al tiro), aunque no
    # dice nada del resultado de ese tiro.
    cer = s.temporada.isin(temporadas_cerradas)
    s["elo_equipo"], s["elo_rival"] = np.nan, np.nan
    e1, e2 = _elo(s[cer].reset_index(drop=True), temporadas_cerradas)
    s.loc[cer, "elo_equipo"], s.loc[cer, "elo_rival"] = e1, e2
    jug = pd.read_csv(DATA_DIR / "processed" / "players_all_seasons.csv", encoding="utf-8-sig",
                      usecols=["temporada", "player", "posicion"]).drop_duplicates(["temporada", "player"], keep=False)
    s = s.merge(jug, on=["temporada", "player"], how="left")
    s["posicion"] = s["posicion"].fillna("Desconocido")
    s["dif_elo"] = s.elo_equipo - s.elo_rival
    return s, {"penales": penales, "olimpicos": olimpicos, "n_total": int(n_total)}


def _bloques(s):
    def dum(col, cats, pref):
        return pd.DataFrame({f"{pref}_{c}": (s[col] == c).astype(float) for c in cats})
    return {
        "geo": s[["dist", "angulo", "dist_y", "location_x", "location_y"]].astype(float),
        "contexto": pd.concat([dum("situation", SITUACIONES, "situation"), dum("body_part", PARTES, "body_part")], axis=1),
        "jugada": s[["asistido", "rebote_previo"]].astype(float),
        "accion": dum("accion", ACCIONES + ["Otra"], "accion"),
        "estado": pd.DataFrame({"minute": s.minute.astype(float), "marcador": s.marcador.astype(float)}),
        "local": s[["es_local"]].astype(float),
        "rol": dum("posicion", ["Delantero", "Medio", "Defensa", "Portero", "Desconocido"], "rol"),
        "nivel": s[["elo_equipo", "elo_rival", "dif_elo"]].astype(float),
    }


def _matriz(B, bloques):
    return pd.concat([B[b] for b in bloques], axis=1)


# ------------------------------------------------------------------------------------------------
# modelos y métricas
# ------------------------------------------------------------------------------------------------

def _ajustar(X, y, tr, va, semilla, monotono=False, arboles=None, params=None):
    """XGBoost con early stopping en `va`, o con `arboles` fijos. `params` por omisión: los del tuning."""
    from xgboost import XGBClassifier
    kw = dict(PARAMS if params is None else params, **FIJOS, random_state=semilla)
    if monotono:
        kw["monotone_constraints"] = tuple(-1 if c == "dist" else 1 if c == "angulo" else 0 for c in X.columns)
    if arboles:
        return XGBClassifier(n_estimators=arboles, **kw).fit(X[tr], y[tr], verbose=False)
    m = XGBClassifier(n_estimators=ARBOLES_MAX, early_stopping_rounds=PARADA, **kw)
    return m.fit(X[tr], y[tr], eval_set=[(X[va], y[va])], verbose=False)


def _perdida(y, p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def _metricas(y, p):
    from sklearn.metrics import brier_score_loss, roc_auc_score
    return {"ll": float(_perdida(y, p).mean()), "brier": float(brier_score_loss(y, p)),
            "auc": float(roc_auc_score(y, p)), "sesgo": float((p.sum() / y.sum() - 1) * 100)}


class _Bootstrap:
    """Intervalos de diferencias de log-loss re-muestreando PARTIDOS (los tiros de un mismo partido
    no son independientes)."""

    def __init__(self, juegos, repeticiones=3000, semilla=0):
        self.u, self.inv = np.unique(juegos, return_inverse=True)
        self.n = np.bincount(self.inv)
        rng = np.random.default_rng(semilla)
        self.idx = rng.integers(0, len(self.u), size=(repeticiones, len(self.u)))
        self.den = self.n[self.idx].sum(axis=1)

    def media(self, perdida):
        s = np.bincount(self.inv, weights=perdida)
        return s[self.idx].sum(axis=1) / self.den

    def dif(self, p_a, p_b, y):
        d = self.media(_perdida(y, p_a)) - self.media(_perdida(y, p_b))
        return float(d.mean()), float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))


# ------------------------------------------------------------------------------------------------
# el cálculo completo
# ------------------------------------------------------------------------------------------------

def _calcular(log=print):
    t0 = time.time()
    cerradas, historicas = temporadas_disponibles()
    log(f"  xG: cargando tiros ({len(cerradas)} cerradas + {len(historicas)} históricas)...")
    s, meta = _armar(cerradas, historicas)
    B = _bloques(s)
    y = s.gol.values
    tr = s.temporada.isin(TRAIN).values
    va = (s.temporada == VALID).values
    te = (s.temporada == TEST).values
    yte = y[te]
    boot = _Bootstrap(s.game_id.values[te])
    R = {"meta": meta, "temporadas": {"cerradas": cerradas, "historicas": historicas},
         "n": {"tiros": int(len(s)), "cerradas": int(s.temporada.isin(cerradas).sum()),
               "train": int(tr.sum()), "valid": int(va.sum()), "test": int(te.sum()),
               "goles_test": int(yte.sum())}}

    # --- 1) la escalera --------------------------------------------------------------------------
    log("  xG: escalera de variables...")
    probs, filas = {}, []
    modelos, todos = {}, {}
    for i, (pid, nombre, bl, mono, grupo) in enumerate(ESCALERA):
        X = _matriz(B, bl)
        ps, ms, arbs = [], [], []
        for sem in SEMILLAS:
            m = _ajustar(X, y, tr, va, sem, mono)
            ps.append(m.predict_proba(X[te])[:, 1])
            ms.append(m)
            arbs.append(m.best_iteration)
        p = np.mean(ps, axis=0)
        probs[pid] = p
        modelos[pid] = (ms[0], list(X.columns))
        todos[pid] = ms
        met = _metricas(yte, p)
        met["sd_ll"] = float(np.std([_perdida(yte, q).mean() for q in ps], ddof=1))
        met["arboles"] = float(np.mean(arbs))
        filas.append({"id": pid, "nombre": nombre, "grupo": grupo, **met})
        log(f"    {pid:7s} ll={met['ll']:.5f} auc={met['auc']:.4f} sesgo={met['sesgo']:+.1f}%  [{time.time()-t0:.0f}s]")
    und = s.xg.values[te]
    for i, f in enumerate(filas):
        if i == 0:
            f.update({"d_ll": None, "d_lo": None, "d_hi": None})
        else:
            f["d_ll"], f["d_lo"], f["d_hi"] = boot.dif(probs[f["id"]], probs[filas[i - 1]["id"]], yte)
    R["escalera"] = filas
    R["understat"] = _metricas(yte, und)
    from sklearn.linear_model import LogisticRegression
    lr = LogisticRegression(max_iter=1000).fit(s.loc[tr, ["dist", "angulo"]], y[tr])
    R["baselines"] = [
        {"nombre": "Tasa global de gol", **_metricas(yte, np.full(len(yte), y[tr].mean()))},
        {"nombre": "Logística con distancia y ángulo", **_metricas(yte, lr.predict_proba(s.loc[te, ["dist", "angulo"]])[:, 1])},
    ]
    cer = s[s.temporada.isin(CERRADAS)]
    ga = cer.groupby("accion").agg(tiros=("gol", "size"), tasa=("gol", "mean"), dist=("dist", "mean"),
                                   xg=("xg", "mean")).sort_values("tiros", ascending=False)
    R["acciones"] = [{"accion": str(a), "tiros": int(r.tiros), "tasa": float(r.tasa), "dist": float(r.dist),
                      "xg_understat": float(r.xg)} for a, r in ga.iterrows()]
    cc = cer.groupby("body_part").agg(tiros=("gol", "size"), tasa=("gol", "mean"), dist=("dist", "mean"))
    R["cuerpo"] = {str(k): {"tiros": int(r.tiros), "tasa": float(r.tasa), "dist": float(r.dist)} for k, r in cc.iterrows()}
    d, lo, hi = boot.dif(probs[FINAL], und, yte)
    R["final_vs_understat"] = {"d_ll": d, "d_lo": lo, "d_hi": hi}
    d, lo, hi = boot.dif(probs[FINAL], probs[BASE_ANTERIOR], yte)
    R["final_vs_anterior"] = {"d_ll": d, "d_lo": lo, "d_hi": hi}
    R["correlacion_understat"] = {"final": float(np.corrcoef(probs[FINAL], und)[0, 1]),
                                  "anterior": float(np.corrcoef(probs[BASE_ANTERIOR], und)[0, 1])}
    p_final = probs[FINAL]
    m_final, cols_final = modelos[FINAL]
    X_fin = _matriz(B, BLOQUES_FINAL)

    # --- 1b) el modelo final con los parámetros de antes del tuning (mismo corte, mismas semillas) ----
    log("  xG: modelo final con los parámetros sin ajustar...")
    p_base = np.mean([_ajustar(X_fin, y, tr, va, sem, True, params=PARAMS_BASE).predict_proba(X_fin[te])[:, 1]
                      for sem in SEMILLAS], axis=0)
    d, lo, hi = boot.dif(p_final, p_base, yte)
    du, dlo, dhi = boot.dif(p_base, und, yte)
    R["ajuste"] = {"origen": ORIGEN_PARAMS, "params": PARAMS, "params_base": PARAMS_BASE,
                   "tuning": ({k: v for k, v in json.loads(PARAMS_JSON.read_text(encoding="utf-8")).items()
                               if k != "params"} if PARAMS_JSON.exists() else None),
                   "sin_ajustar": _metricas(yte, p_base), "d_ll": d, "d_lo": lo, "d_hi": hi,
                   "sin_ajustar_vs_understat": {"d_ll": du, "d_lo": dlo, "d_hi": dhi}}
    log(f"    sin ajustar ll={R['ajuste']['sin_ajustar']['ll']:.5f}; ajustado - sin ajustar {d:+.5f} [{lo:+.5f}, {hi:+.5f}]")

    # --- 1d) la versión publicada antes, con la fuga, para el recuadro de corrección ------------------
    # Mismas columnas y parámetros de antes; solo cambia rebote_previo por la definición que miraba
    # también los tiros posteriores.
    log("  xG: la versión anterior, con la fuga...")
    X_fuga = X_fin.copy()
    X_fuga["rebote_previo"] = s["rebote_con_fuga"].astype(float).values
    p_fuga = np.mean([_ajustar(X_fuga, y, tr, va, sem, True, params=PARAMS_BASE).predict_proba(X_fuga[te])[:, 1]
                      for sem in SEMILLAS], axis=0)
    d, lo, hi = boot.dif(p_fuga, und, yte)
    ds, slo, shi = boot.dif(p_base, p_fuga, yte)
    R["fuga"] = {**_metricas(yte, p_fuga), "vs_understat": {"d_ll": d, "d_lo": lo, "d_hi": hi},
                 "sin_fuga_vs_fuga": {"d_ll": ds, "d_lo": slo, "d_hi": shi}, "lugares": _lugares(s)}
    log(f"    con fuga ll={R['fuga']['ll']:.5f}; - Understat {d:+.5f} [{lo:+.5f}, {hi:+.5f}]")

    # --- 1c) el modelo publicado: mismos parámetros, entrenado con 2021-25 ---------------------------
    # Sin temporada para early stopping: usa el FACTOR_PUBLICADO de los árboles que eligió la
    # validación (más datos aguantan más árboles). Se prueba UNA vez en 2025-26, que sigue sin verse.
    # Ojo: la diferencia con el modelo de evaluación mezcla "más datos" con "más árboles".
    log("  xG: modelo publicado (entrena 2021-25)...")
    tr_pub = s.temporada.isin(TRAIN + [VALID]).values
    pubs, arb_pub = [], []
    for m_, sem in zip(todos[FINAL], SEMILLAS):
        n_arb = int(round(FACTOR_PUBLICADO * (m_.best_iteration + 1)))
        pubs.append(_ajustar(X_fin, y, tr_pub, None, sem, True, arboles=n_arb))
        arb_pub.append(n_arb)
    ps_pub = [m_.predict_proba(X_fin[te])[:, 1] for m_ in pubs]
    p_pub = np.mean(ps_pub, axis=0)
    pub = _metricas(yte, p_pub)
    pub["sd_ll"] = float(np.std([_perdida(yte, q).mean() for q in ps_pub], ddof=1))
    d, lo, hi = boot.dif(p_pub, p_final, yte)
    du, dlo, dhi = boot.dif(p_pub, und, yte)
    R["publicado"] = {**pub, "arboles": arb_pub, "factor": FACTOR_PUBLICADO, "entrena": TRAIN + [VALID],
                      "tiros": int(tr_pub.sum()),
                      "vs_evaluacion": {"d_ll": d, "d_lo": lo, "d_hi": hi},
                      "vs_understat": {"d_ll": du, "d_lo": dlo, "d_hi": dhi},
                      "correlacion_understat": float(np.corrcoef(p_pub, und)[0, 1])}
    log(f"    publicado ll={pub['ll']:.5f} sesgo={pub['sesgo']:+.1f}%; - evaluación {d:+.5f} [{lo:+.5f}, {hi:+.5f}]; "
        f"- Understat {du:+.5f} [{dlo:+.5f}, {dhi:+.5f}]")
    m_pub = pubs[0]
    R["subgrupos"] = _subgrupos(s[te].reset_index(drop=True), yte, {"publicado": p_pub, "evaluacion": p_final}, und)

    # --- 2) ¿hay señal en el contexto? (logística con offset sobre el modelo final) -----------------
    # Con el modelo de evaluación: la logística se ajusta en 2024-25, que el publicado ya vio.
    log("  xG: prueba de residuo...")
    R["residuo"] = _residuo(s, B, m_final, cols_final, y, tr, va, te, boot)

    # --- 3) calibración -------------------------------------------------------------------------
    R["calibracion"] = _calibracion(yte, p_final, und, probs[BASE_ANTERIOR])
    R["calibracion"]["publicado"] = _calibracion(yte, p_pub, und, p_pub)["final"]
    R["calibracion_lineal"] = {k: _calibracion_lineal(yte, p) for k, p in
                               (("evaluacion", p_final), ("publicado", p_pub), ("understat", und))}

    # --- 4) por tramo del xG de Understat, por grupos y por equipo ----------------------------------
    st = s[te].reset_index(drop=True)
    st["p_final"], st["p_und"], st["p_ant"] = p_final, und, probs[BASE_ANTERIOR]
    R["tramos"] = _tramos(s, y)
    R["grupos"] = _grupos(st)
    R["equipos"] = _equipos(st)

    # --- 5) las temporadas históricas: curva de aprendizaje, envejecimiento y trayectoria -------------
    R["historico"] = _historico(s, B, y, va, te, boot, probs[FINAL], log, t0)

    # --- 6) lo que aprendió el modelo publicado, y de qué se agarra --------------------------------
    log("  xG: rejillas e importancia...")
    R["aprendio"] = _aprendio(s, m_pub, cols_final)
    Xte = X_fin[te]
    R["importancia"] = {"publicado": _importancia(m_pub, Xte, yte),
                        "evaluacion": _importancia(m_final, Xte, yte)}
    R["tiempo_s"] = float(time.time() - t0)
    return R


def _subgrupos(st, y, modelos, und):
    """Robustez: log-loss y sesgo de cada modelo contra Understat dentro de cada liga, situación y parte
    del cuerpo de 2025-26, con el intervalo de la diferencia (bootstrap por partido dentro del grupo)."""
    out = []
    for col in ("liga", "situation", "body_part"):
        for val, idx in st.groupby(col).groups.items():
            k = st.index.isin(idx)
            if k.sum() < 500:
                continue
            bt = _Bootstrap(st.game_id.values[k], repeticiones=1000)
            fila = {"col": col, "valor": str(val), "tiros": int(k.sum()), "goles": int(y[k].sum()),
                    "understat": _metricas(y[k], und[k])}
            for nombre, p in modelos.items():
                d, lo, hi = bt.dif(p[k], und[k], y[k])
                fila[nombre] = {**_metricas(y[k], p[k]), "d_ll": d, "d_lo": lo, "d_hi": hi}
            out.append(fila)
    return out


def _lugares(s):
    """Tasa de gol según el lugar del tiro entre los del mismo equipo en el mismo partido y minuto (por
    `shot_id`), en las temporadas cerradas: muestra por qué el `rebote` viejo era una fuga."""
    c = s[s.temporada.isin(CERRADAS)]
    clave = ["game_id", "team", "minute"]
    pos = c.sort_values("shot_id", kind="stable").groupby(clave).cumcount().reindex(c.index)
    n = c.groupby(clave)["shot_id"].transform("size")
    lugar = np.where(n == 1, "solo", np.where(pos == 0, "primero", np.where(pos == n - 1, "ultimo", "intermedio")))
    g = c.groupby(lugar).gol.agg(["size", "sum", "mean"])
    return [{"id": k, "tiros": int(g.loc[k, "size"]), "goles": int(g.loc[k, "sum"]), "tasa": float(g.loc[k, "mean"])}
            for k in ("solo", "primero", "intermedio", "ultimo") if k in g.index]


def _residuo(s, B, m, cols, y, tr, va, te, boot):
    """Logística con el logit del modelo como offset, ajustada en 2024-25 y evaluada en 2025-26."""
    # el modelo final de la escalera entrenó solo con 2021-24 (early stopping en 2024-25)
    p = m.predict_proba(_matriz(B, ["geo", "contexto", "jugada", "accion"])[cols])[:, 1]
    lg = np.log(p / (1 - p))
    F = pd.DataFrame({
        "marcador": s.marcador.clip(-3, 3).astype(float),
        "minuto": s.minute / 90.0,
        "local": s.es_local.astype(float),
        "dif_elo": s.dif_elo / 100.0,
        "delantero": (s.posicion == "Delantero").astype(float),
        "defensa": (s.posicion == "Defensa").astype(float),
    })
    etiquetas = {
        "marcador": "Un gol más de ventaja en el marcador",
        "minuto": "Del minuto 0 al 90",
        "local": "Rematar de local",
        "dif_elo": "100 puntos de ELO más que el rival",
        "delantero": "El tirador es delantero (contra medio)",
        "defensa": "El tirador es defensa (contra medio)",
    }

    def glm(A, yy, off):
        b = np.zeros(A.shape[1])
        for _ in range(50):
            mu = 1 / (1 + np.exp(-(A @ b + off)))
            H = A.T @ (A * (mu * (1 - mu))[:, None])
            paso = np.linalg.solve(H, A.T @ (yy - mu))
            b += paso
            if np.abs(paso).max() < 1e-9:
                break
        mu = 1 / (1 + np.exp(-(A @ b + off)))
        cov = np.linalg.inv(A.T @ (A * (mu * (1 - mu))[:, None]))
        return b, np.sqrt(np.diag(cov))

    ok = ~F.dif_elo.isna().values
    va_, te_ = va & ok, te & ok

    def ajustar(cols_):
        A = np.column_stack([np.ones(va_.sum()), F.loc[va_, cols_].values])
        b, ee = glm(A, y[va_], lg[va_])
        B_ = np.column_stack([np.ones(te_.sum()), F.loc[te_, cols_].values])
        pt = 1 / (1 + np.exp(-(B_ @ b + lg[te_])))
        return b, ee, pt

    base_te = 1 / (1 + np.exp(-lg[te_]))
    yte = y[te_]
    bt = _Bootstrap(s.game_id.values[te_], repeticiones=2000)
    filas = []
    for c in F.columns:
        b, ee, pt = ajustar([c])
        d, lo, hi = bt.dif(pt, base_te, yte)
        filas.append({"id": c, "nombre": etiquetas[c], "razon": float(np.exp(b[1])),
                      "lo": float(np.exp(b[1] - 1.96 * ee[1])), "hi": float(np.exp(b[1] + 1.96 * ee[1])),
                      "z": float(b[1] / ee[1]), "d_ll": d, "d_lo": lo, "d_hi": hi})
    b, ee, pt = ajustar(list(F.columns))
    d, lo, hi = bt.dif(pt, base_te, yte)
    return {"variables": filas, "todas": {"d_ll": d, "d_lo": lo, "d_hi": hi},
            "ll_base": float(_perdida(yte, base_te).mean())}


def _calibracion(y, p_final, und, p_ant, k=12):
    def curva(p):
        c = pd.DataFrame({"p": p, "y": y})
        c["b"] = pd.qcut(c.p, k, labels=False, duplicates="drop")
        g = c.groupby("b").agg(n=("y", "size"), p=("p", "mean"), real=("y", "mean"))
        return [[float(r.p), float(r.real), None, None, int(r.n)] for r in g.itertuples()]
    return {"final": curva(p_final), "understat": curva(und), "anterior": curva(p_ant)}


def _calibracion_lineal(y, p):
    """Logística de y sobre el logit de p: pendiente 1 e intercepto 0 = bien calibrado. Pendiente < 1:
    el modelo es demasiado extremo (sobreajuste); intercepto < 0: predice de más en general."""
    from sklearn.linear_model import LogisticRegression
    q = np.clip(p, 1e-6, 1 - 1e-6)
    lg = np.log(q / (1 - q)).reshape(-1, 1)
    m = LogisticRegression(C=1e6, max_iter=1000).fit(lg, y)
    return {"pendiente": float(m.coef_[0, 0]), "intercepto": float(m.intercept_[0])}


def _tramos(s, y):
    """El exceso de goles esperados de Understat según su propio xG, sobre todas las temporadas
    cerradas (sin penales)."""
    c = s[s.temporada.isin(CERRADAS)]
    t = pd.cut(c.xg, [0, 0.03, 0.06, 0.10, 0.15, 0.25, 0.40, 1.0])
    g = c.groupby(t, observed=True).agg(tiros=("gol", "size"), predice=("xg", "mean"), entra=("gol", "mean"))
    g["exceso"] = (g.predice - g.entra) * g.tiros
    return [{"desde": float(iv.left), "hasta": float(iv.right), "tiros": int(r.tiros),
             "predice": float(r.predice), "entra": float(r.entra), "exceso": float(r.exceso)}
            for iv, r in g.iterrows()]


def _grupos(st):
    """Sesgo (xG sumado contra goles) de mi modelo y de Understat, por grupos de tiros."""
    st = st.copy()
    st["nivel"] = pd.qcut(st.elo_equipo, 4, labels=["Más flojos", "Segundo cuarto", "Tercer cuarto", "Élite"])
    nombres = {
        "situation": ("Situación", {"Open Play": "Jugada abierta", "From Corner": "Córner",
                                    "Set Piece": "Balón parado", "Direct Freekick": "Tiro libre directo"}),
        "body_part": ("Parte del cuerpo", {"Right Foot": "Pie derecho", "Left Foot": "Pie izquierdo",
                                           "Head": "Cabeza", "Other": "Otra"}),
        "liga": ("Liga", {}),
        "nivel": ("Nivel del equipo", {}),
    }   # (no se agrupa por el xG de un modelo para evaluar al otro: eso mide regresión a la media)
    out = []
    for col, (etq, ren) in nombres.items():
        g = st.groupby(col, observed=True).agg(n=("gol", "size"), goles=("gol", "sum"),
                                               final=("p_final", "sum"), und=("p_und", "sum"), ant=("p_ant", "sum"))
        g = g[g.n >= 100]
        filas = [{"nombre": ren.get(str(i), str(i)), "n": int(r.n), "goles": int(r.goles),
                  "valores": {"propio": float((r.final / r.goles - 1) * 100),
                              "understat": float((r.und / r.goles - 1) * 100)}} for i, r in g.iterrows()]
        if col in ("situation", "body_part", "liga"):
            filas.sort(key=lambda f: -f["n"])
        out.append({"id": col, "etiqueta": etq, "filas": filas})
    return out


def _equipos(st):
    g = st.groupby(["liga", "team"]).agg(pj=("game_id", "nunique"), und=("p_und", "sum"), final=("p_final", "sum"),
                                         goles=("gol", "sum"), elo=("elo_equipo", "mean")).reset_index()
    return [{"n": r.team, "liga": r.liga, "x": float(r.und / r.pj), "y": float((r.und / r.final - 1) * 100),
             "goles": int(r.goles), "elo": float(r.elo)} for r in g.itertuples()]


def _historico(s, B, y, va, te, boot, p_final, log, t0):
    """Todo lo que usa temporadas de antes de 2021-22: la trayectoria del sesgo de Understat, la curva
    de aprendizaje y el envejecimiento. Solo con las variables que existen en esas temporadas."""
    bl = ["geo", "contexto", "jugada", "accion"]
    X = _matriz(B, bl)
    temps = sorted(s.temporada.unique())
    prev = [t for t in temps if t < VALID]
    cerr = [t for t in temps if t in CERRADAS]
    out = {"temporadas": temps}

    # trayectoria: el xG de Understat contra los goles, por temporada; y mi modelo (entrenado con 2021-24)
    tr = s.temporada.isin(TRAIN).values
    m = _ajustar(X, y, tr, va, SEMILLAS[0], True)
    pm = m.predict_proba(X)[:, 1]
    tray = []
    for t in temps:
        k = (s.temporada == t).values
        tray.append({"temporada": t, "tiros": int(k.sum()), "goles": int(y[k].sum()),
                     "understat": float((s.xg.values[k].sum() / y[k].sum() - 1) * 100),
                     "propio": float((pm[k].sum() / y[k].sum() - 1) * 100),
                     "entrenamiento": bool(t in TRAIN)})
    out["trayectoria"] = tray

    # curva de aprendizaje: las k temporadas más recientes anteriores a 2024-25
    curva = []
    yte = y[te]
    for k in range(1, len(prev) + 1):
        usar = prev[-k:]
        trk = s.temporada.isin(usar).values
        ps = [_ajustar(X, y, trk, va, sem, True).predict_proba(X[te])[:, 1] for sem in SEMILLAS]
        met = _metricas(yte, np.mean(ps, axis=0))
        met["sd"] = float(np.std([_perdida(yte, q).mean() for q in ps], ddof=1))
        curva.append({"k": k, "desde": usar[0], "tiros": int(trk.sum()), **met})
        log(f"    curva k={k} desde {usar[0]}: ll={met['ll']:.5f}  [{time.time()-t0:.0f}s]")
    out["curva"] = curva

    # envejecimiento: entrenar con UNA temporada y medir el sesgo en 2025-26. No hay temporada libre
    # para early stopping (la de 2024-25 se entrena aquí), así que van 600 árboles fijos, que se
    # eligieron para los parámetros de antes: con ellos se queda, para que el número tenga sentido.
    # (La curva de aprendizaje sí usa los del tuning: decide los árboles con early stopping.)
    viejo = []
    for t in [t for t in temps if t != TEST]:
        trk = (s.temporada == t).values
        ps = [_ajustar(X, y, trk, va, sem, True, arboles=600, params=PARAMS_BASE).predict_proba(X[te])[:, 1]
              for sem in SEMILLAS[:1]]
        met = _metricas(yte, ps[0])
        viejo.append({"temporada": t, "tiros": int(trk.sum()), **met})
    out["envejecimiento"] = viejo
    return out


def _aprendio(s, m, cols):
    """Rejillas de xG del modelo final sobre la cancha, una por combinación de situación, parte del
    cuerpo y acción previa, con las zonas sin tiros suficientes tapadas."""
    nx, ny = 40, 32
    xmin, xmax, ymin, ymax = 0.55, 0.995, 0.06, 0.94
    xs, ys = np.linspace(xmin, xmax, nx), np.linspace(ymin, ymax, ny)
    malla = pd.DataFrame([(a, b) for b in ys for a in xs], columns=["location_x", "location_y"])
    mx, my = malla.location_x * LARGO, malla.location_y * ANCHO
    malla["dist"] = np.hypot(LARGO - mx, ANCHO / 2 - my)
    pa = np.hypot(LARGO - mx, ANCHO / 2 + PORTERIA / 2 - my)
    pb = np.hypot(LARGO - mx, ANCHO / 2 - PORTERIA / 2 - my)
    malla["angulo"] = np.arccos(np.clip((pa ** 2 + pb ** 2 - PORTERIA ** 2) / (2 * pa * pb), -1, 1))
    malla["dist_y"] = (malla.location_y - 0.5).abs() * ANCHO

    sit = {"jugada": "Open Play", "corner": "From Corner", "abp": "Set Piece"}
    parte = {"pie_der": "Right Foot", "pie_izq": "Left Foot", "cabeza": "Head"}
    accion_fija = {"corner": "Pass", "abp": "Pass"}
    acciones = {"Pass": "Pase", "Cross": "Centro", "Throughball": "Pase filtrado", "Rebound": "Rebote",
                "TakeOn": "Regate", "Ninguna": "Sin acción previa"}
    asistida = {"Pass": 1, "Cross": 1, "Throughball": 1, "Rebound": 0, "TakeOn": 0, "Ninguna": 0}

    bx = np.r_[xs - (xs[1] - xs[0]) / 2, xs[-1] + (xs[1] - xs[0]) / 2]
    by = np.r_[ys - (ys[1] - ys[0]) / 2, ys[-1] + (ys[1] - ys[0]) / 2]
    def vecinos(sub):
        cnt, _, _ = np.histogram2d(sub.location_y, sub.location_x, bins=[by, bx])
        return sum(np.roll(np.roll(cnt, i, 0), j, 1) for i in (-1, 0, 1) for j in (-1, 0, 1))

    rej, vmax = {}, 0.0
    crudo, peso = {}, {}     # por tipo de remate: el xG sin tapar y cuántos tiros de ese tipo hay cerca
    for sid, sname in sit.items():
        for pid, pname in parte.items():
            sub = s[(s.situation == sname) & (s.body_part == pname)]
            veci = vecinos(sub)
            mask = veci >= 15
            for aid in (acciones if sid == "jugada" else [accion_fija[sid]]):
                X = malla.copy()
                for c in cols:
                    if c not in X:
                        X[c] = 0.0
                X["asistido"] = float(asistida.get(aid, 1))
                # tras un rebote casi siempre hubo un tiro antes en ese minuto (94% de los casos)
                X["rebote_previo"] = 1.0 if aid == "Rebound" else 0.0
                X[f"situation_{sname}"] = 1.0
                X[f"body_part_{pname}"] = 1.0
                X[f"accion_{aid}"] = 1.0
                z = m.predict_proba(X[cols])[:, 1].reshape(ny, nx)
                clave = f"{sid}|{pid}|{aid if sid == 'jugada' else '-'}"
                crudo[clave] = z
                peso[clave] = vecinos(sub[sub.accion == aid]) if sid == "jugada" else veci
                z = np.where(mask, z, np.nan)
                rej[clave] = [None if np.isnan(v) else round(float(v), 3) for v in z.ravel()]
                if np.isfinite(z).any():
                    vmax = max(vmax, float(np.nanpercentile(z, 99.5)))

    # Sin elegir situación, parte del cuerpo o acción ("*"): el promedio de los tipos de remate que
    # entran, pesado por cuántos tiros de cada tipo hubo en esa zona (cabezazos cerca de la portería,
    # remates de pie más lejos). En córner y balón parado la acción no se elige.
    def junta(claves):
        w = sum(peso[k] for k in claves)
        z = sum(crudo[k] * peso[k] for k in claves) / np.where(w > 0, w, 1)
        z = np.where(w >= 15, z, np.nan)
        return [None if np.isnan(v) else round(float(v), 3) for v in z.ravel()]
    def entra(k, sid, pid, aid):
        ks, kp, ka = k.split("|")
        return ((sid == "*" or ks == sid) and (pid == "*" or kp == pid)
                and (sid != "jugada" or aid == "*" or ka == aid))
    for sid in list(sit) + ["*"]:
        for pid in list(parte) + ["*"]:
            for aid in (list(acciones) + ["*"] if sid == "jugada" else ["-"]):
                if "*" in (sid, pid, aid):
                    rej[f"{sid}|{pid}|{aid}"] = junta([k for k in crudo if entra(k, sid, pid, aid)])

    # cabeza contra pie derecho, de frente, tras un centro, a distintas distancias
    def frontal(dist_m, pname):
        X = pd.DataFrame([{c: 0.0 for c in cols}])
        X["dist"], X["dist_y"] = dist_m, 0.0
        X["angulo"] = np.arccos(np.clip((2 * dist_m ** 2 - PORTERIA ** 2) / (2 * dist_m ** 2), -1, 1))
        X["location_x"], X["location_y"] = 1 - dist_m / LARGO, 0.5
        X["asistido"] = 1.0
        X["situation_Open Play"] = 1.0
        X[f"body_part_{pname}"] = 1.0
        X["accion_Cross"] = 1.0
        return float(m.predict_proba(X[cols])[0, 1])
    dist = list(range(4, 31))
    pie = [frontal(d, "Right Foot") for d in dist]
    cab = [frontal(d, "Head") for d in dist]
    return {"superficie": {"nx": nx, "ny": ny, "xmin": xmin, "xmax": xmax, "ymin": ymin, "ymax": ymax,
                           "largo": LARGO, "ancho": ANCHO, "vmax": round(vmax, 3),
                           "situaciones": [{"id": "jugada", "etiqueta": "Jugada abierta", "usaAccion": True},
                                           {"id": "corner", "etiqueta": "Córner"},
                                           {"id": "abp", "etiqueta": "Balón parado"}],
                           "partes": [{"id": "pie_der", "etiqueta": "Pie derecho"},
                                      {"id": "pie_izq", "etiqueta": "Pie izquierdo"},
                                      {"id": "cabeza", "etiqueta": "Cabeza"}],
                           "acciones": [{"id": k, "etiqueta": v} for k, v in acciones.items()],
                           "rejillas": rej},
            "cabeza": {"dist": dist, "pie": pie, "cabeza": cab}}


def _importancia(m, X, y, repeticiones=5):
    """De qué se agarra el modelo, medido en 2025-26:

      * por grupo, la **permutación agrupada**: cuánto empeora el log-loss al barajar juntas las
        columnas del grupo (media de `repeticiones` barajadas);
      * por variable (y por grupo), **SHAP** nativo de XGBoost: la media del valor absoluto de la
        contribución, en log-odds;
      * la **ganancia media por corte** de antes, solo para explicar por qué se dejó: premia a las
        variables que el modelo usa en pocos cortes grandes."""
    import xgboost as xgb
    X = X.reset_index(drop=True)
    cols = list(X.columns)
    base = float(_perdida(y, m.predict_proba(X)[:, 1]).mean())
    try:
        rango = (0, int(m.best_iteration) + 1)   # predict_proba corta en la mejor iteración; aquí igual
    except AttributeError:
        rango = (0, 0)                           # sin early stopping: todos los árboles
    bst = m.get_booster()
    contrib = bst.predict(xgb.DMatrix(X), pred_contribs=True, iteration_range=rango)[:, :-1]
    rng = np.random.default_rng(0)
    grupos = []
    for gid, nombre, es in GRUPOS_IMPORTANCIA:
        cs = [c for c in cols if es(c)]
        idx = [cols.index(c) for c in cs]
        d = []
        for _ in range(repeticiones):
            Xp = X.copy()
            Xp[cs] = X[cs].values[rng.permutation(len(X))]
            d.append(float(_perdida(y, m.predict_proba(Xp)[:, 1]).mean()) - base)
        grupos.append({"id": gid, "nombre": nombre, "columnas": len(cs), "d_ll": float(np.mean(d)),
                       "sd": float(np.std(d, ddof=1)), "shap": float(np.abs(contrib[:, idx].sum(axis=1)).mean())})
    grupos.sort(key=lambda g: -g["d_ll"])
    variables = sorted(({"variable": c, "shap": float(np.abs(contrib[:, i]).mean())} for i, c in enumerate(cols)),
                       key=lambda v: -v["shap"])
    gm, w, tg = (bst.get_score(importance_type=t) for t in ("gain", "weight", "total_gain"))
    ganancia = sorted(({"variable": k, "media": float(gm[k]), "cortes": int(w[k]), "total": float(tg[k])} for k in gm),
                      key=lambda v: -v["media"])
    # SHAP por variable ORIGINAL: las categóricas (acción previa, parte del cuerpo, situación) suman sus
    # columnas antes del valor absoluto, como una sola variable.
    originales = []
    for vid, es in ORIGINALES:
        idx = [i for i, c in enumerate(cols) if es(c)]
        originales.append({"id": vid, "shap": float(np.abs(contrib[:, idx].sum(axis=1)).mean())})
    originales.sort(key=lambda v: -v["shap"])
    return {"base_ll": base, "repeticiones": repeticiones, "grupos": grupos, "variables": variables,
            "originales": originales, "ganancia": ganancia}


def resultados(log=print):
    """Los resultados del modelo, de caché si los datos y el código no cambiaron."""
    cerradas, historicas = temporadas_disponibles()
    firma = _firma(cerradas + historicas, extra="" if (DATA_DIR / ".clubelo").exists() else "sin_clubelo")
    if CACHE.exists() and os.environ.get("XG_REHACER") != "1":
        c = json.loads(CACHE.read_text(encoding="utf-8"))
        if c.get("firma") == firma:
            log(f"  xG: resultados en caché ({CACHE.name}, firma {firma})")
            return c["resultados"]
    log("  xG: calculando los modelos (15-20 min la primera vez)...")
    R = _calcular(log)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps({"firma": firma, "resultados": R}, ensure_ascii=False), encoding="utf-8")
    return R
