"""El análisis del modelo de xG para el sitio, contado como un proyecto de ML.

El orden es el de un proyecto: datos (qué hay y cómo se bajó), exploración, propuesta de modelo,
cómo funciona un árbol, resultados, qué hace Understat, la prueba en varias temporadas y un
explorador de tiros. Casi todo es una gráfica; el texto solo ata una con otra.

Los modelos y las mediciones los hacen `xg_modelo.py`, `xg_comparacion.py` y `xg_temporadas.py`
(cacheados en disco), y los conteos de la exploración `xg_eda.py`. Todas las cifras del texto salen de
esos resultados: si cambian los datos o el modelo, la prosa se mueve sola (y las frases que dependen de
que algo "mejore" o "empeore" se escriben según lo que salió, no según lo que se esperaba).

Las gráficas son vistas de React (`web/react/src/Articulo.jsx`): cada una lee su parte de una tabla
pequeña, `dist/react/datos-xg.js`, que se registra aquí (`_payload`). El explorador pide además una
tabla por temporada (`xg_explorador.py`).

Prototipado en `code/ml_xg_model.ipynb`; el artículo creció de ahí con la escalera de variables, la
acción previa al tiro, las temporadas históricas y la prueba hacia atrás en el tiempo.
"""

import json
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import react_views  # noqa: E402
import xg_comparacion as xc  # noqa: E402
import xg_eda  # noqa: E402
import xg_explorador  # noqa: E402
import xg_modelo as xm  # noqa: E402
import xg_temporadas as xt  # noqa: E402
from ml_comun import SECTION, _callout, _heading, _prose, _stat, _table  # noqa: E402
from site_utils import ArticlePage  # noqa: E402
from viz_theme import LEAGUE_COLORS, LEAGUE_COLORS_DARK, SEQUENTIAL_BLUE  # noqa: E402

FUENTE = "Understat"
# Escrito por el autor: se deja tal cual.
SUBTITULO = "La idea es trasladar todos los datos (que tengo) alrededor de un tiro para construir un modelo que genere la estadística de goles esperados."
LIGAS = ["Premier League", "La Liga", "Serie A", "Bundesliga", "Ligue 1"]

ACCION_ES = {
    "Pass": "Pase", "Cross": "Centro", "Ninguna": "Sin acción previa", "Aerial": "Balón aéreo",
    "Rebound": "Rebote", "Chipped": "Pase por alto", "TakeOn": "Regate", "Standard": "Balón detenido",
    "BallRecovery": "Recuperación", "BallTouch": "Control", "HeadPass": "Pase de cabeza",
    "Throughball": "Pase filtrado", "LayOff": "Descarga", "Dispossessed": "Pérdida del rival",
    "Otra": "Otra",
}
PARTE_ES = {"Right Foot": "Pie derecho", "Left Foot": "Pie izquierdo", "Head": "Cabeza", "Other": "Otra parte"}
SITUACION_ES = {"Open Play": "Jugada abierta", "From Corner": "Córner", "Set Piece": "Balón parado",
                "Direct Freekick": "Tiro libre directo", "Penalty": "Penal"}
RESULTADO_ES = ["Gol", "Atajado", "Fuera", "Bloqueado", "Poste"]


def _n(x):
    """225442 -> '225,442': coma para los miles, como en México; el punto es el decimal."""
    return f"{int(round(x)):,}"


def _signo(x, dec=4):
    x = round(x, dec)
    return f"{abs(x):.{dec}f}" if x == 0 else f"{x:+.{dec}f}"


def _nombre_variable(c):
    for pref, tabla, rotulo in (("accion_", ACCION_ES, "Acción previa: "), ("body_part_", PARTE_ES, ""),
                                ("situation_", SITUACION_ES, "")):
        if c.startswith(pref):
            return rotulo + tabla.get(c[len(pref):], c[len(pref):])
    return {"dist": "Distancia a la portería", "angulo": "Ángulo de tiro", "dist_y": "Distancia al centro",
            "location_x": "Posición (profundidad)", "location_y": "Posición (ancho)",
            "asistido": "Asistido", "rebote_previo": "Tiro antes en ese minuto"}.get(c, c)


def _ic(d):
    """'-0.0005 (intervalo de 95%: -0.0030 a +0.0021)' a partir de un dict con d_ll, d_lo y d_hi."""
    return f"{_signo(d['d_ll'])} (intervalo de 95%: {_signo(d['d_lo'])} a {_signo(d['d_hi'])})"


def _exceso(sesgo):
    """+16.8 -> 'un 17% más goles esperados de los que entraron'."""
    return f"un {abs(sesgo):.0f}% {'más' if sesgo >= 0 else 'menos'} goles esperados de los que entraron"


def _veredicto(d, mejor="es mejor", peor="es peor", igual="no se distingue"):
    """Lo que dice un intervalo de diferencia de log-loss: solo hay ganador si no toca el cero."""
    return mejor if d["d_hi"] < 0 else peor if d["d_lo"] > 0 else igual


# Las variables del gráfico SHAP, como las diría alguien que ve el partido.
NOMBRE_ORIGINAL = {"dist": "Distancia a la portería", "angulo": "Ángulo de tiro", "dist_y": "Distancia al centro",
                   "location_x": "Profundidad", "location_y": "Posición a lo ancho", "asistido": "Si fue asistido",
                   "rebote_previo": "Tiro antes en ese minuto", "accion": "Acción previa",
                   "cuerpo": "Parte del cuerpo", "situacion": "Situación (jugada, córner…)"}


def _corto(t):
    return t.replace("20", "", 1)


# ---------------------------------------------------------------------------------------------
# la tabla de las gráficas
# ---------------------------------------------------------------------------------------------

def _percentil(valores, q):
    v = np.array([x for x in valores if x is not None and x > 0], float)
    return float(np.percentile(v, q))


def _payload(R, C, T, E):
    P = {}
    esc = R["escalera"]
    ult = T["temporadas"][-1]

    def lim(filas, ref):
        lo = min([f["lo"] for f in filas] + [ref])
        hi = max([f["hi"] for f in filas] + [ref])
        pad = (hi - lo) * 0.12
        return [lo - pad, hi + pad]

    # ============================================================ datos y exploración
    tpt = E["tiros_por_temporada"]
    temps = E["temporadas"]
    P["tiros_temporada"] = {
        "temporadas": temps,
        "ligas": [{"id": lg, "nombre": lg, "color": LEAGUE_COLORS[lg], "colorOscuro": LEAGUE_COLORS_DARK[lg]} for lg in LIGAS],
        "valores": {lg: [tpt[t][lg] for t in temps] for lg in LIGAS}}

    m = E["mapa"]
    cuentas = m["metricas"]["tiros"]
    P["mapa"] = {
        **{k: m[k] for k in ("nx", "ny", "xmin", "xmax", "ymin", "ymax", "largo", "ancho")},
        "metricas": m["metricas"], "rampa": SEQUENTIAL_BLUE, "bandas": E["bandas"],
        "opciones": [
            {"id": "tiros", "etiqueta": "Dónde se tira", "formato": "miles", "unidad": "tiros por zona",
             "tope": _percentil(cuentas, 98), "raiz": True},
            {"id": "tasa", "etiqueta": "Qué tanto entra", "formato": "fraccion", "unidad": "tasa de gol",
             "tope": _percentil(m["metricas"]["tasa"], 98)},
            {"id": "xg_und", "etiqueta": "xG de Understat", "formato": "num2", "unidad": "xG medio",
             "tope": _percentil(m["metricas"]["xg_und"], 98)},
            {"id": "distancia", "etiqueta": "Por distancia", "formato": "fraccion", "unidad": "tasa de gol",
             "tipo": "bandas", "tope": max(b["todos"]["tasa"] for b in E["bandas"]["distancia"])},
            {"id": "angulo", "etiqueta": "Por ángulo", "formato": "fraccion", "unidad": "tasa de gol",
             "tipo": "bandas", "tope": max(b["todos"]["tasa"] for b in E["bandas"]["angulo"])},
        ]}

    tas = E["tasas"]

    def filas(reg, clave, nombres, con_dist=True):
        out = []
        for r in sorted(reg, key=lambda r: -r["tasa"]):
            nom = nombres.get(r[clave], r[clave])
            if con_dist:
                nom = f"{nom} · a {r['dist']:.0f} m de media"
            out.append({"nombre": nom, "n": int(r["n"]), "valores": {"tasa": float(r["tasa"])}})
        return out
    f_acc = filas(tas["accion"], "accion", ACCION_ES, con_dist=False)
    f_cue = filas(tas["cuerpo"], "body_part", PARTE_ES)
    f_sit = filas(tas["situacion"], "situation", SITUACION_ES)

    def tope(fs):
        return max(f["valores"]["tasa"] for f in fs) * 1.2
    P["tasas"] = {
        "rotulo": "Tasa de gol según",
        "agrupaciones": [
            {"id": "cuerpo", "etiqueta": "Parte del cuerpo", "dom": [0, tope(f_cue)], "filas": f_cue},
            {"id": "situacion", "etiqueta": "Situación", "dom": [0, tope(f_sit)], "filas": f_sit},
            {"id": "accion", "etiqueta": "Acción previa", "dom": [0, tope(f_acc)], "filas": f_acc},
        ],
        "series": [{"id": "tasa", "nombre": "Tasa de gol", "color": "propio"}],
        "eje": {"etiqueta": "Tasa de gol (%)", "formato": "pct1"}, "unidad": "tiros"}

    # ============================================================ el corte en el tiempo
    tt = E["temporadas"]
    P["ventanas"] = {
        "temporadas": tt,
        "filas": [{"prueba": tt.index(f["temporada"]), "valida": tt.index(f["valida"]),
                   "entrena": [tt.index(x) for x in tt[tt.index(f["temporada"]) - 1 - T["entrenan"]:tt.index(f["temporada"]) - 1]],
                   "final": f["temporada"] == xm.TEST} for f in T["temporadas"]]}

    # ============================================================ los modelos
    M = {k["id"]: k for k in C["metricas"]}
    E_ = {f["id"]: f for f in esc}
    fin = E_[xm.FINAL]
    glob, logi = R["baselines"]
    pub = R["publicado"]
    modelos = [("Misma probabilidad para todos", glob, "neutro", False),
               ("Logística: distancia y ángulo", logi, "neutro", False),
               ("XGBoost · sin ajustar", M["xgb"], "neutro", False),
               ("LightGBM · sin ajustar", M["lgbm"], "neutro", False),
               ("Mezcla de los dos · sin ajustar", M["mezcla"], "neutro", False),
               (f"XGBoost ajustado · evaluación (entrena {_corto(xm.TRAIN[0])} a {_corto(xm.TRAIN[-1])})", fin, "propio", True),
               (f"XGBoost ajustado · publicado (entrena {_corto(pub['entrena'][0])} a {_corto(pub['entrena'][-1])})",
                pub, "propio", False)]
    vals = [m_["ll"] for _, m_, _, _ in modelos]
    pad = (max(vals) - min(vals)) * 0.08
    P["modelos"] = {"agrupaciones": [{
        "id": "ll", "etiqueta": "Log-loss",
        "eje": {"dom": [min(vals) - pad, max(vals) + pad], "formato": "num3",
                "etiqueta": f"Log-loss en {xm.TEST} (menos es mejor)"},
        "filas": [{"nombre": n_, "valor": m_["ll"], "texto": f"{m_['ll']:.4f}", "tono": tono, "destacado": d}
                  for n_, m_, tono, d in modelos]}]}

    # --- escalera de variables: Δ log-loss de cada paso, con su intervalo
    f_esc = [{"nombre": f["nombre"].replace("restricciones de monotonía", "monotone constraints"),
              "nota": f"log-loss {f['ll']:.4f}", "valor": f["d_ll"], "lo": f["d_lo"], "hi": f["d_hi"],
              "texto": f"{f['d_ll']:+.4f}", "destacado": f["id"] == xm.FINAL} for f in esc[1:]]
    P["escalera"] = {
        "eje": {"etiqueta": "Cambio en el log-loss al sumar el grupo (a la izquierda, mejor) · línea: intervalo de 95%",
                "ref": 0, "mejor": "izq", "formato": "num3", "dom": lim(f_esc, 0)},
        "filas": f_esc, "columna": "Δ log-loss"}

    cv = C["curvas"]
    P["boosting"] = {
        "x": {"etiqueta": "Árboles sumados (escala logarítmica)", "etiqueta_corta": "árboles", "formato": "log10",
              "marcas": [float(np.log10(v)) for v in (1, 3, 10, 30, 100, 300, 1000)]},
        "y": {"etiqueta": "Log-loss (menos es mejor)", "formato": "num3"},
        "series": [
            {"id": "xgb_p", "nombre": "XGBoost · prueba (2025-26)", "color": "propio", "marcador": False,
             "puntos": [[float(np.log10(c["k"])), c["prueba"]] for c in cv["xgb"]]},
            {"id": "xgb_e", "nombre": "XGBoost · entrenamiento", "color": "propio", "marcador": False, "trazo": "punteado",
             "puntos": [[float(np.log10(c["k"])), c["entrenamiento"]] for c in cv["xgb"]]},
            {"id": "lgbm_p", "nombre": "LightGBM · prueba (2025-26)", "color": "aviso", "marcador": False,
             "puntos": [[float(np.log10(c["k"])), c["prueba"]] for c in cv["lgbm"]]},
            {"id": "lgbm_e", "nombre": "LightGBM · entrenamiento", "color": "aviso", "marcador": False, "trazo": "punteado",
             "puntos": [[float(np.log10(c["k"])), c["entrenamiento"]] for c in cv["lgbm"]]},
        ]}
    P["arbol"] = dict(C["arbol"], rampa=SEQUENTIAL_BLUE, ref=[
        {"id": "xgb", "nombre": "XGBoost completo", "ll": M["xgb"]["ll"], "auc": M["xgb"]["auc"], "arboles": M["xgb"]["arboles"]},
        {"id": "lgbm", "nombre": "LightGBM completo", "ll": M["lgbm"]["ll"], "auc": M["lgbm"]["auc"], "arboles": M["lgbm"]["arboles"]}])

    # --- lo que aprendió
    P["superficie"] = dict(R["aprendio"]["superficie"], rampa=SEQUENTIAL_BLUE)
    ori = R["importancia"]["publicado"]["originales"]
    P["shap"] = {
        "agrupaciones": [{"id": "shap", "etiqueta": "SHAP", "filas": [
            {"nombre": NOMBRE_ORIGINAL.get(v["id"], v["id"]), "valores": {"v": v["shap"]}} for v in ori]}],
        "series": [{"id": "v", "nombre": "Aporte medio", "color": "propio"}],
        "eje": {"etiqueta": "Cuánto mueve, en promedio, el xG de un tiro (SHAP medio, en log-odds)", "formato": "num2",
                "dom": [0, max(v["shap"] for v in ori) * 1.15]}}

    # ============================================================ varias temporadas
    ts = T["temporadas"]
    P["rendimiento"] = {
        "x": {"categorias": [f["temporada"] for f in ts], "etiqueta": None},
        "y": {"etiqueta": "Log-loss en la temporada de prueba", "formato": "num3"},
        "series": [
            {"id": "base", "nombre": "Misma probabilidad para todos", "color": "neutro",
             "puntos": [[k, f["base_ll"], None, None, f["tiros"]] for k, f in enumerate(ts)]},
            {"id": "propio", "nombre": "XGBoost · mi modelo", "color": "propio",
             "puntos": [[k, f["propio"]["ll"], None, None, f["tiros"]] for k, f in enumerate(ts)]},
        ],
        "unidad_n": "tiros de prueba"}
    return P


def _grafica(vista_id, tipo, dato, titulo, subtitulo, alt, alto=None, alto_min=420, pie="", ayuda=None):
    """Una figura del artículo: el montaje de React dentro de `figure`, con su pie."""
    cfg = {"grafica": tipo, "tabla": "xg", "dato": dato, "titulo": titulo, "subtitulo": subtitulo,
           "fuente": FUENTE, "alt": alt}
    if alto:
        cfg["alto"] = alto
    if ayuda:
        cfg["ayuda"] = ayuda
    cap = f"<figcaption>{pie}</figcaption>" if pie else ""
    return ('<figure class="wrap-wide"><div class="chart-scroll">'
            f'{react_views.montar_html("articulo", vista_id, cfg, alto_min)}</div>{cap}</figure>')


def _explorador(n_total):
    cfg = {"grafica": "explorador", "titulo": "Elige un tiro",
           "subtitulo": f"{_n(n_total)} tiros de las cinco últimas temporadas (penales incluidos), con lo que dijo cada modelo",
           "fuente": FUENTE, "alt": "Cancha con los tiros de la temporada y el detalle del tiro elegido",
           "temporadas": xm.CERRADAS, "ligas": LIGAS, "origen": [2021, 7, 1],
           "situaciones": [SITUACION_ES[s] for s in xg_explorador.SITUACIONES],
           "partes": [PARTE_ES[p] for p in xg_explorador.PARTES],
           "acciones": [ACCION_ES[a] for a in xg_explorador.ACCIONES],
           "resultados": RESULTADO_ES}
    return ('<figure class="wrap-wide"><div class="chart-scroll">'
            f'{react_views.montar_html("articulo", "xg-explorador", cfg, 780)}</div></figure>')


# ---------------------------------------------------------------------------------------------
# el artículo
# ---------------------------------------------------------------------------------------------

def _cargar_resultados():
    """Los resultados de los modelos. Con `XG_SOLO_CACHE=1` se usa el último caché sin comprobar que los
    datos no hayan cambiado: sirve para reconstruir el sitio sin disparar un recálculo de media hora."""
    if os.environ.get("XG_SOLO_CACHE") == "1" and xm.CACHE.exists():
        print("  xG: usando el último resultado en caché, sin comprobar la firma (XG_SOLO_CACHE=1)")
        R = json.loads(xm.CACHE.read_text(encoding="utf-8"))["resultados"]
    else:
        R = xm.resultados()
    return R, xc.resultados(), xt.resultados()


def _perdida(n, pos, p):
    p = min(1 - 1e-4, max(1e-4, p))
    return -(pos * np.log(p) + (n - pos) * np.log(1 - p))


def _lista(items):
    return "<ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>"


def _frase_tuning(aj):
    tu = aj.get("tuning")
    if not tu:
        return ""
    folds = " y ".join(f"entrenar hasta {f['entrena'][-1]} y validar en {f['valida']}" for f in tu["folds"])
    return (f"Sus hiperparámetros los elegí con Optuna ({tu['pruebas']} pruebas) y validación en el tiempo "
            f"({folds}), sin mirar {xm.TEST}. ")


def _frase_robustez():
    """Si se corrió `code/xg_robustez.py`: ¿la mejora del ajuste se repite en temporadas que el tuning no vio?"""
    ruta = xm.DATA_DIR / "processed" / "xg_robustez.json"
    if not ruta.exists():
        return ""
    rb = json.loads(ruta.read_text(encoding="utf-8"))
    if rb.get("params") != xm.PARAMS:      # resultado de otros parámetros: no vale
        return ""
    f = rb["tuning_fuera"]
    mejor = sum(x["d_hi"] < 0 for x in f)
    peor = sum(x["d_lo"] > 0 for x in f)
    igual = len(f) - mejor - peor
    if mejor == len(f):
        return f" Y se repite en {f[0]['temporada']} a {f[-1]['temporada']}, temporadas que el ajuste nunca vio."
    partes = [f"{n} {'temporada' if n == 1 else 'temporadas'} {etq}" for n, etq in
              ((mejor, "mejor"), (igual, "igual"), (peor, "peor")) if n]
    return (f" Ojo: en {f[0]['temporada']} a {f[-1]['temporada']}, temporadas que el ajuste nunca vio, la mejora no se "
            f"repite ({', '.join(partes)}): parece propia de los años con los que se eligió.")


def _frase_temporadas(aj):
    tu = aj.get("tuning")
    if not tu:
        return ""
    return (" Aquí el modelo va con los hiperparámetros sin ajustar: el ajuste se validó en "
            f"{' y '.join(f['valida'] for f in tu['folds'])}, que aquí también son temporadas de prueba.")


def _correccion(R):
    """El recuadro de corrección: qué estaba mal en la versión anterior y cuánto cambió, todo de los datos."""
    fu, aj = R["fuga"], R["ajuste"]
    lug = {l_["id"]: l_ for l_ in fu["lugares"]}
    pri, solo = lug["primero"], lug["solo"]

    def estado(d):
        return _veredicto(d, "mejor que Understat", "peor que Understat", "empate con Understat")
    return _callout("Corrección · octubre de 2026", (
        "<p>La versión anterior de este artículo usaba una variable, «rebote», que marcaba un tiro si el mismo equipo "
        "remataba otra vez en ese minuto, <em>antes o después</em>. El después era el problema: si un tiro entra, la "
        "jugada se corta, así que el primero de varios tiros en un minuto casi nunca es gol "
        f"({_n(pri['goles'])} de {_n(pri['tiros'])}, el {pri['tasa']:.1%}, contra el {solo['tasa']:.1%} de un tiro "
        "solo). El modelo se enteraba del resultado por el tiro que venía después.</p>"
        "<p>Ahora la variable solo mira los tiros anteriores (en el orden del identificador del tiro, que sigue al "
        "reloj en el 87% de los partidos). Con los mismos hiperparámetros, el log-loss en "
        f"{xm.TEST} pasa de {fu['ll']:.4f} a {aj['sin_ajustar']['ll']:.4f}, y frente a Understat de "
        f"{_ic(fu['vs_understat'])} ({estado(fu['vs_understat'])}) a {_ic(aj['sin_ajustar_vs_understat'])} "
        f"({estado(aj['sin_ajustar_vs_understat'])}). Además ajusté los hiperparámetros, entreno el modelo publicado "
        "con una temporada más y cambié la forma de medir qué variables importan; todo está en Resultados.</p>"),
        warn=True)


def _texto_importancia(R):
    imp = R["importancia"]["publicado"]
    g, ori = imp["grupos"], imp["originales"]
    top = [f"«{NOMBRE_ORIGINAL.get(v['id'], v['id']).lower()}»" for v in ori[:3]]
    geo = {"dist", "angulo", "dist_y", "location_x", "location_y"}
    txt = (f"<p>Lo que más pesa es {top[0]}, luego {top[1]} y {top[2]}"
           + (": dónde se tira manda. " if ori[0]["id"] in geo and ori[1]["id"] in geo else ". "))
    ultimos = [v for v in ori if v["shap"] < 0.05 * ori[0]["shap"]]
    if ultimos:
        txt += ("Casi no lo mueven " + " ni ".join(f"«{NOMBRE_ORIGINAL.get(v['id'], v['id']).lower()}»" for v in ultimos)
                + ".")
    txt += "</p>"

    def v(x):
        return f"{x:.3f}" if abs(x) >= 0.001 else f"{x:.4f}"
    gr = (f"{g[0]['nombre'].lower()} ({v(g[0]['d_ll'])})"
          + "".join(f", {x['nombre'].lower()} ({v(x['d_ll'])})" for x in g[1:-1])
          + f" y {g[-1]['nombre'].lower()} ({v(g[-1]['d_ll'])})")
    domina = g[0]["id"] == "geo" and g[0]["d_ll"] > sum(x["d_ll"] for x in g[1:])
    txt += ("<p>Lo confirma otra medida: barajar un grupo de variables entre los tiros y ver cuánto empeora el "
            f"log-loss: {gr}" + (". La geometría pesa más que todo lo demás junto.</p>" if domina else ".</p>"))

    # Por qué se dejó la ganancia media por corte: el cabezazo era el ejemplo (primero en la versión
    # anterior). Se compara su puesto por ganancia media con su puesto por SHAP en este modelo.
    rango_shap = [x["variable"] for x in imp["variables"]]
    rango_gan = [x["variable"] for x in imp["ganancia"]]
    cab_v = "body_part_Head"
    if cab_v in rango_shap and cab_v in rango_gan:
        k_gan, k_shap = rango_gan.index(cab_v) + 1, rango_shap.index(cab_v) + 1
        cortes = imp["ganancia"][k_gan - 1]["cortes"]
        txt += ("<p>Antes esta gráfica usaba la ganancia media por corte, que premia a las variables que el modelo "
                "usa en pocos cortes grandes. Con ella «Cabeza» salía primera; en este modelo es la "
                f"{k_gan}.ª ({_n(cortes)} cortes), pero por SHAP es la {k_shap}.ª.")
        cab = R["aprendio"]["cabeza"]
        if 10 in cab["dist"]:
            i = cab["dist"].index(10)
            txt += (" El efecto del cabezazo sí es real: de frente a 10 m tras un centro, el modelo le da "
                    f"{cab['cabeza'][i]:.2f} de xG contra {cab['pie'][i]:.2f} del pie derecho, el "
                    f"{cab['cabeza'][i] / cab['pie'][i]:.0%}. Lo que era un artefacto era su lugar en el ranking.")
        txt += "</p>"
    return txt


def build_xg_article() -> ArticlePage:
    R, C, T = _cargar_resultados()
    E = xg_eda.calcular()
    X = xg_explorador.tablas()
    react_views.registrar_payload("xg", _payload(R, C, T, E))

    esc = {f["id"]: f for f in R["escalera"]}
    fin = esc[xm.FINAL]
    acc = esc["accion"]
    n_test = R["n"]["test"]
    pen, oli = R["meta"]["penales"], R["meta"]["olimpicos"]
    contexto = [esc[i] for i in ("estado", "local", "rol", "nivel")]
    ayudan = [f for f in contexto if f["d_hi"] < 0]
    tray = R["historico"]["trayectoria"]
    M = {m["id"]: m for m in C["metricas"]}
    mx, ml, mm = M["xgb"], M["lgbm"], M["mezcla"]
    base_ll, logi = R["baselines"][0]["ll"], R["baselines"][1]
    rej = R["aprendio"]["superficie"]["rejillas"]
    tasas = {k: {r[{"cuerpo": "body_part", "situacion": "situation", "accion": "accion"}[k]]: r for r in v}
             for k, v in E["tasas"].items()}
    ts = T["temporadas"]
    n_explorador = sum(v["n"] for v in X.values())

    contador = [0]

    def h(titulo, ancla):
        contador[0] += 1
        return _heading(f"{contador[0]:02d}", titulo, ancla)

    def sub(titulo):
        return _prose(f"<h3>{titulo}</h3>")

    p = []
    # ================================================================ 1. el problema
    p.append(h("¿Qué es un gol esperado?", "que_es"))
    p.append(_prose(
        "<p>El xG (goles esperados) es la probabilidad de que un tiro sea gol según el contexto en el que se da: "
        "distancia, ángulo, parte del cuerpo, tipo de jugada, entre otros. Sirve para medir la "
        "calidad de las ocasiones sin depender del marcador: permite ver si un equipo o un jugador rinde por encima o "
        "por debajo de lo esperado, y separar lo que fue juego de lo que fue suerte. Un xG, al final, no es más que "
        "eso: <strong>una probabilidad dada la situación en la que se tira</strong>.</p>"
        "<p>Aquí construyo el xG desde cero con la metodología de un proyecto de ML con el fin de aprender lo que hay detrás de este número que tan popular se ha vuelto."
        "</p>"))
    p.append(_correccion(R))

    # ================================================================ 2. los datos
    p.append(h("Los datos", "datos"))
    p.append(_prose(
        f"<p>El primer paso es la recolección de los datos a través de la API de Understat: todos los tiros desde la temporada {E['temporadas'][0]} a "
        f"{E['temporadas'][-1]} en las cinco ligas."
        f"<p><strong>{_n(E['raw']['filas'])} tiros</strong> en {_n(E['partidos'])} partidos.</p>"))
    p.append(_grafica("xg-tiros-temporada", "apiladas", "tiros_temporada", "Cuántos tiros hay",
                      "Por temporada, con la liga como color · toca el nombre de una liga para quitarla o ponerla · "
                      "sin penales, autogoles ni remates desde el banderín", "Tiros por temporada y por liga", alto_min=420))
    p.append(_table(
        ["Variables", "Ejemplo", "Qué hago con eso"],
        [["Posición en la cancha (x, y)", "0.86, 0.43", "Distancia y ángulo a la portería"],
         ["Parte del cuerpo", "Pie derecho", "Variable del modelo"],
         ["Situación", "Jugada abierta, balón parado", "Variable del modelo"],
         ["Asistente", "Martin Ødegaard", "De quién viene el pase"],
         ["Acción previa", "Pase filtrado", "Variable del modelo"],
         ["Minuto", "82", "Si el mismo equipo ya había tirado en ese minuto"],
         ["xG de Understat", "0.68", "Comparar con mi modelo"],
         ["Resultado", "Gol, atajado, bloqueado", "Lo que predigo: ¿gol o no?"]], wide=True))
    p.append(_prose(
        f"<p>Antes de modelar saqué los {_n(pen['n'])} penales (entran el {pen['conversion']:.0%} sin importar "
        f"quién los patee), los autogoles y {oli['n']} remates a menos de dos grados de portería visible: "
        "casi todos son goles olímpicos y Understat solo registra un córner si iba a "
        "puerta.</p>"))

    # ================================================================ 3. exploración
    p.append(h("Explorando los datos", "eda"))
    p.append(_prose(
        "<p>Antes de modelar, es importante mirar qué dicen los tiros por sí solos: desde dónde se dispara, qué tanto "
        "de eso termina en gol y cómo cambia según la distancia y el ángulo.</p>"))
    p.append(_grafica(
        "xg-mapa", "mapa", "mapa", "Los tiros sobre la cancha",
        f"{_n(E['n'])} tiros de las cinco ligas sin penales ni autogoles, {E['temporadas'][0]} a {E['temporadas'][-1]} · elige qué mirar y pasa el "
        "mouse sobre una zona", "Mapa de la media cancha con tiros, tasa de gol, xG medio de Understat y zonas de "
        "distancia y de ángulo", alto_min=520,
        ayuda="Las zonas con menos de 25 tiros no muestran tasa; las franjas, menos de 40."))
    cab, pie_d = tasas["cuerpo"]["Head"], tasas["cuerpo"]["Right Foot"]
    th, ps = tasas["accion"].get("Throughball"), tasas["accion"].get("Pass")
    p.append(_prose("<p>La distancia es la variable más obvia, pero, ¿qué más mueve la tasa de gol?</p>"))
    p.append(_grafica(
        "xg-tasas", "barras", "tasas", "Tasa de gol según otras cosas del tiro",
        "Elige cómo agrupar · el número de tiros va debajo de cada nombre", "Tasa de gol por categoría", alto_min=300))
    cab_menos = all(b["cabeza"]["tasa"] < b["pie"]["tasa"] for b in E["bandas"]["distancia"]
                    if b["cabeza"]["n"] >= 40 and b["pie"]["n"] >= 40)
    frase_cuerpo = (f"Un cabezazo convierte casi igual que un remate con el pie ({cab['tasa']:.1f}% contra "
                    f"{pie_d['tasa']:.1f}%) solo porque se da desde más cerca ({cab['dist']:.0f} m contra "
                    f"{pie_d['dist']:.0f} m)" + ("; en cada franja de distancia vale menos." if cab_menos else "."))
    frase_accion = (f" Y lo que pasó justo antes también cuenta: tras un pase filtrado entra el {th['tasa']:.0f}%; "
                    f"tras un pase normal, el {ps['tasa']:.0f}%." if th and ps else "")
    p.append(_prose(
        "<p>La distancia, y con ella el ángulo, es el factor más importante: cuanto más cerca se tira, más "
        "probabilidad de gol, tanto de pie como de cabeza. Por eso un equipo con xG alto suele ser uno que generó "
        f"ocasiones muy claras, cerca de la portería. <p>Pero medir qué tan cerca se tira no alcanza. {frase_cuerpo}"
        f"{frase_accion} <p>El modelo tendrá que combinar la geometría con la parte del cuerpo, la situación y la "
        "acción previa.</p>"))

    # ================================================================ 4. propuesta de modelo
    p.append(h("Propuesta de modelo", "modelo"))
    p.append(_prose(
        f"<p>La tarea es clasificar la probabilidad de que un tiro sea gol dado su contexto. "
        f"La metodología se basa en un modelo <strong>XGBoost</strong> (árboles de decisión que se corrigen entre sí) con 3 puntos importantes:</p>"
        + _lista([
            "<strong>Split temporal:</strong> entreno con tres temporadas, decido cuántos árboles con la siguiente y pruebo en una que el modelo nunca vio.",
            "<strong>Intervalos por partido:</strong> los tiros de un mismo partido no son independientes, así que para calcular los intervalos de confianza remuestreo partidos, no tiros.",
            "<strong>Validación hacia adelante:</strong> repito el experimento moviendo la ventana una temporada cada vez, siempre entrenando con el pasado y probando en el futuro (en la sección 7 se ve el resultado de cada una)."])))
    p.append(_grafica(
        "xg-ventanas", "ventanas", "ventanas", "Cómo parto el tiempo",
        "Cada fila es un experimento con su propio split temporal. ",
        alt="Diagrama de las ventanas de entrenamiento, validación y prueba por temporada"))

    # ================================================================ 5. cómo funciona un árbol
    p.append(h("Cómo funciona un modelo de árboles", "arboles"))
    A = C["arbol"]
    hojas_arbol = [n for n in A["nodos"] if n[0] < 0]
    ll_arbol = sum(_perdida(n[7], n[8], n[6] / n[5] if n[5] else 0.0) for n in hojas_arbol) / A["n_test"]
    p.append(_prose(
        f"<p>Un árbol de decisión es un modelo que toma decisiones basadas en preguntas de sí o no sobre las características del dato. Cada hoja representa una predicción final.</p>"
        f"<p>En esta animación interactiva puedes ver cómo se construye un árbol de decisión para el xG, partiendo de una primera pregunta y creciendo dependiendo de la configuración de profundidad y el número de hojas.<p>Cada hoja tiene su propia tasa de gol, que es la predicción del xG para los tiros que llegan a esa hoja.</p>"))
    p.append(_grafica(
        "xg-arbol", "arbol", "arbol", "Un árbol de decisión, abierto partición por partición",
        "Cada hoja es un xG: la tasa de gol de los tiros que llegan ahí", "Árbol de decisión interactivo del xG",
        alto_min=620))
    p.append(_prose(
        "<p>Para decidir si un tiro entra, las preguntas serían del tipo ¿está a menos de 12 m?, ¿fue de cabeza?, "
        "¿venía de un pase filtrado?: cada respuesta manda el tiro por una rama hasta una hoja. <p>Las "
        "preguntas se eligen para que los tiros de cada rama se parezcan lo más posible en lo que importa: si "
        "terminaron o no en gol. La probabilidad que recibe el tiro es la proporción de goles entre los tiros de "
        f"entrenamiento que cayeron en esa misma hoja. "
        f"<p>Al medir con muchos árboles, cada uno corrigiendo los errores de los anteriores, se obtiene un modelo más robusto y preciso "
        f"hasta llegar a cientos de árboles chicos con un log-loss de {mx['ll']:.4f}."))
    p.append(_grafica(
        "xg-boosting", "lineas", "boosting", "Árbol por árbol",
        "Log-loss al ir sumando árboles · punteado: entrenamiento; sólido: 2025-26 · "
        f"LightGBM termina con {_n(ml['arboles'])} árboles en {ml['seg']:.0f} s; XGBoost, con {_n(mx['arboles'])} "
        f"en {mx['seg']:.0f} s", "Log-loss de XGBoost y LightGBM según el número de árboles", alto=360))

    # ================================================================ 6. resultados
    aj, pub = R["ajuste"], R["publicado"]
    p.append(h("Resultados", "resultados"))
    p.append(_prose(
        "<p>Para comparar modelos uso el <strong>log-loss</strong>: mide qué tan buenas son las probabilidades, no solo "
        "si el modelo acertó. Castiga más cuanto más seguro estaba de algo que no pasó (decir «0.9 de xG» y fallar "
        f"penaliza mucho). Menos es mejor, y un log-loss de {base_ll:.4f} es el baseline cuando el modelo le da a todos los tiros la misma "
        "probabilidad.</p>"
        f"<p>En {xm.TEST}, con {_n(n_test)} tiros que el modelo no vio, XGBoost obtuvo un <strong>log-loss de {fin['ll']:.4f}</strong>. "
        f"{_frase_tuning(aj)}Así queda frente a modelos más simples y a otros algoritmos:</p>"))
    p.append(_grafica(
        "xg-modelos", "puntos", "modelos", "XGBoost frente a otros modelos",
        f"Log-loss en {xm.TEST} · cada punto es un modelo", "Log-loss de cada modelo en la temporada de prueba",
        alto_min=300))
    lg_peor, mz_peor = ml["d_xgb_lo"] > 0, mm["d_xgb_lo"] > 0
    lg_igual, mz_igual = ml["d_xgb_hi"] >= 0 >= ml["d_xgb_lo"], mm["d_xgb_hi"] >= 0 >= mm["d_xgb_lo"]
    if lg_peor and mz_peor:
        algo_txt = (f"LightGBM y la mezcla de los dos quedan un poco peor ({_signo(ml['d_xgb'])} y "
                    f"{_signo(mm['d_xgb'])} de log-loss)")
    elif lg_igual and mz_igual:
        algo_txt = (f"LightGBM y la mezcla de los dos no se distinguen de XGBoost ({_signo(ml['d_xgb'])} y "
                    f"{_signo(mm['d_xgb'])})")
    else:
        algo_txt = (f"LightGBM da {_signo(ml['d_xgb'])} y la mezcla de los dos, {_signo(mm['d_xgb'])} de log-loss "
                    "frente a XGBoost")
    p.append(_prose(
        f"<p>Con solo la distancia y el ángulo (una regresión logística) el log-loss baja de {base_ll:.4f} a "
        f"{logi['ll']:.4f}. Con todas las variables y XGBoost baja a {fin['ll']:.4f}. <p>Entre algoritmos casi no hay "
        f"diferencia: {algo_txt}, los tres con los hiperparámetros sin ajustar (LightGBM no pasó por el ajuste). "
        "Por eso me quedo con XGBoost." + (
            f" Ajustarlo cambia el log-loss en {_ic(aj)}: "
            f"{_veredicto(aj, 'una mejora pequeña pero distinta de cero', 'lo empeora', 'no se distingue de cero')}."
            + _frase_robustez() if aj['origen'] == 'tuning' else "") + "</p>"))
    pe = pub["vs_evaluacion"]
    p.append(_prose(
        f"<p>Hay dos versiones del modelo{' ajustado' if aj['origen'] == 'tuning' else ''}. La de <strong>evaluación</strong> entrena de {xm.TRAIN[0]} a "
        f"{xm.TRAIN[-1]} y usa {xm.VALID} para decidir cuántos árboles: es la de todas las comparaciones de esta "
        f"sección. La <strong>publicada</strong> entrena también con {xm.VALID} (sin temporada para decidir árboles, "
        f"usa {pub['factor']:.2f} veces los de la de evaluación) y es la del mapa y la importancia de abajo. La probé "
        f"una sola vez en {xm.TEST}, que tampoco vio: log-loss {pub['ll']:.4f}, {_ic(pe)} frente a la de evaluación "
        f"({_veredicto(pe, 'mejor', 'peor', 'sin diferencia clara')}). Esa diferencia mezcla dos cosas, más datos y "
        "más árboles, y no las separa.</p>"))
    pu, eu, tc = pub["vs_understat"], R["final_vs_understat"], T["conjunto"]
    p.append(_prose(
        f"<p>¿Y contra el xG de Understat, en los mismos tiros? La versión de evaluación queda en {_ic(eu)} de "
        f"log-loss ({_veredicto(eu, 'mejor', 'peor', 'empate')}) y la publicada en {_ic(pu)} "
        f"({_veredicto(pu, 'mejor', 'peor', 'empate')}). Pero una temporada es poco: en la prueba hacia atrás "
        f"de la sección 7 (sin ajustar), en las {len(ts)} temporadas juntas la diferencia es {_ic(tc)}, "
        f"{_veredicto(tc, 'a favor de mi modelo', 'a favor de Understat', 'sin ganador')} "
        f"(mi modelo gana {tc['gana']}, empata {tc['empata']} y pierde {tc['pierde']}). Donde sí hay una diferencia "
        f"clara es en el total: en {xm.TEST} Understat suma {_exceso(R['understat']['sesgo'])}; mi modelo publicado, "
        f"{_exceso(pub['sesgo'])}.</p>"))

    p.append(_prose(
        "<p>¿Qué variables ayudan? Las fui sumando por grupos y en cada paso medí cuánto cambia el log-loss: a la "
        "izquierda del cero, mejora. La línea alrededor de cada punto es un intervalo de 95%: si toca el cero, el "
        "cambio podría ser casualidad.</p>"))
    p.append(_grafica(
        "xg-escalera", "forest", "escalera", "Qué variables ayudan",
        "Cambio en el log-loss frente al paso anterior · en gris, lo que no se distingue de cero",
        "Escalera de variables: cambio en el log-loss al agregar cada grupo", alto_min=480))
    res_ctx = ("solo " + " y ".join(f"«{f['nombre'][2:]}»" for f in ayudan) + " mejora con intervalo que excluye "
               "el cero") if ayudan else "ninguno mejora con un intervalo que excluya el cero"
    mejoran = [f"{n_} ({_signo(esc[k]['d_ll'])})" for n_, k in (("cuerpo y situación", "cuerpo"),
                                                                 ("asistido y tiro previo en el minuto", "jugada"),
                                                                 ("la acción previa", "accion")) if esc[k]["d_hi"] < 0]
    p.append(_prose(
        f"<p>{(', '.join(mejoran[:-1]) + ' y ' + mejoran[-1] if len(mejoran) > 1 else ''.join(mejoran)).capitalize()} "
        f"mejoran el modelo. El contexto del partido (marcador, local, puesto del tirador, nivel del equipo) no "
        f"ayudó: {res_ctx}.</p>"))

    sup = R["aprendio"]["superficie"]

    def valor_penal(clave):
        """El xG del mapa a 11 m de la portería, de frente (el punto penal), o None si no hay tiros ahí."""
        if clave not in rej:
            return None
        nx, ny = sup["nx"], sup["ny"]
        cols = [(abs((1 - (sup["xmin"] + (sup["xmax"] - sup["xmin"]) * c / (nx - 1))) * sup["largo"] - 11), c)
                for c in range(nx)]
        c = min(cols)[1]
        return rej[clave][(ny // 2) * nx + c]
    z_pie, z_fil, z_cab = (valor_penal("jugada|pie_der|Pass"), valor_penal("jugada|pie_der|Throughball"),
                           valor_penal("jugada|cabeza|Cross"))
    p.append(_prose(
        "<p>Para ver qué aprendió, medí el xG que el modelo da a un tiro desde cada punto de la cancha. Sin elegir "
        "nada, el mapa junta todos los remates; elige una situación, una parte del cuerpo o una acción previa y el "
        "mapa se queda solo con esos:"
        "</p>"))
    p.append(_grafica(
        "xg-superficie", "superficie", "superficie", "Qué aprendió el modelo",
        "xG del modelo publicado para un remate desde cada punto de la cancha, según qué tipo de remate sea · "
        "la cancha mira hacia la portería", "Mapa interactivo del xG por zona de la cancha", alto_min=560,
        ayuda="Las zonas sin color no tienen tiros suficientes para opinar."))
    if None not in (z_pie, z_fil, z_cab):
        p.append(_prose(
            "<p>Prueba, por ejemplo, un tiro de frente desde 11 m (el punto penal): el modelo da "
            f"{z_pie:.2f} de xG si es con el pie tras un pase, {z_fil:.2f} si viene de un pase filtrado y "
            f"{z_cab:.2f} si es de cabeza tras un centro.</p>"))

    p.append(_prose(
        "<p>Otra forma de ver lo que aprendió es de qué variables se agarra. Para eso uso SHAP: reparte el xG "
        "de cada tiro entre sus variables y dice cuánto lo movió cada una, hacia arriba o hacia abajo. La barra "
        f"es el promedio de ese movimiento en los {_n(R['n']['test'])} tiros de {xm.TEST}: cuanto más larga, más "
        "depende el xG de esa variable.</p>"))
    p.append(_grafica(
        "xg-importancia", "barras", "shap", "De qué se agarra el modelo",
        "Aporte medio de cada variable al xG de un tiro · modelo publicado", "Importancia SHAP de las variables",
        alto_min=420, ayuda="Un aporte de 0.69 equivale a duplicar (o partir a la mitad) los momios del gol."))
    p.append(_prose(_texto_importancia(R)))

    # ================================================================ 7. varias temporadas
    p.append(h("¿Y en otras temporadas?", "temporadas"))
    p.append(_prose(
        f"<p>Todo lo anterior fue en {xm.TEST}. Para saber si no fue casualidad, repetí el experimento en {len(ts)} "
        "temporadas, una por cada fila del diagrama de la propuesta de modelo. En cada una comparo contra lo mismo: "
        f"predecir siempre la tasa de gol histórica.{_frase_temporadas(aj)}</p>"))
    p.append(_grafica(
        "xg-rendimiento", "lineas", "rendimiento", "Rendimiento temporada por temporada",
        "Log-loss en cada temporada de prueba (menos es mejor) · el modelo nunca vio esa temporada al entrenar",
        "Log-loss del modelo y de la tasa de gol histórica en cada temporada de prueba", alto=340))
    mejora = [f["base_ll"] - f["propio"]["ll"] for f in ts]
    if min(mejora) > 0:
        p.append(_prose(
            f"<p>Cada temporada tiene su dificultad, pero el XGB siempre rinde bien."
            "</p>"))
    else:
        p.append(_prose(
            f"<p>Cada temporada tiene su dificultad, y el XGB no siempre rinde mejor que la tasa histórica."
            "</p>"))

    # ================================================================ 8. el explorador
    p.append(h("Elige un tiro", "explorador"))
    p.append(_prose(
        f"<p>Los {_n(n_explorador)} tiros de las cinco últimas temporadas, penales incluidos, cada uno con el xG de un modelo "
        "que <strong>no había visto esa temporada</strong>. Elige uno y compáralo con Understat y con lo que "
        "pasó.</p>"))
    p.append(_explorador(n_explorador))

    # ================================================================ 9. cómo usar un xG
    p.append(h("Cómo usar un xG", "usar"))
    p.append(_prose(
        "<p>Ya vimos cómo se construye uno. Ahora, cómo usarlo sin que nos engañe:</p>" + _lista([
            "<strong>Mira la temporada, no el partido:</strong> un partido es muy poca muestra, y un golazo o un fallo "
            "increíble cambia toda la lectura. Con cientos de tiros el ruido se promedia y aparece lo importante, que "
            "es cómo genera ocasiones un equipo y cómo se las generan, no quién falló una jugada en concreto.",
            "<strong>Calidad, no cantidad:</strong> un tiro vale por dónde y cómo se remató. Dos remates que parecen "
            "parecidos pueden valer muy distinto por el contexto, y por eso un equipo con xG alto no es el que más "
            "tira, sino el que tiene mejores ocasiones.",
            "<strong>Es un modelo, no un hecho:</strong> un xG es una probabilidad, no un resultado. Que un tiro "
            "clarísimo se falle o que uno casi imposible entre no significa que el modelo se equivocó, así es la "
            "probabilidad: solo habla de lo que pasa a la larga. Úsalo para comparar y ver tendencias, no para decir "
            "qué iba a pasar en una jugada.",
            "<strong>El xG no lo ve todo:</strong> según las variables que tenga, a cada modelo se le escapan cosas, "
            "y ahí un aficionado todavía aporta (por lo menos por ahora)."])
        + "<p><strong>El xG es un apoyo, no un veredicto.</strong></p>"))

    return ArticlePage(
        slug="modelo-xg",
        section=SECTION,
        title="Construyendo un modelo de xG",
        subtitle=SUBTITULO,
        deck=SUBTITULO,   # `deck` es obligatorio y el texto de arriba de la página es el que escribió el autor
        body_html="".join(p),
        meta=[("Datos", f"{_n(E['raw']['filas'])} tiros · top 5 ligas · {len(E['temporadas'])} temporadas "
                        f"({E['temporadas'][0]} a {E['temporadas'][-1]})"),
              ("Modelo", f"entrenado y evaluado con {_n(R['n']['cerradas'])} tiros de {xm.CERRADAS[0]} a {xm.CERRADAS[-1]}"),
              ("Métodos", "XGBoost · LightGBM · Optuna · bootstrap por partido")],
        fuente=f"{FUENTE} · temporadas {tray[0]['temporada']} a {tray[-1]['temporada']}",
        react=True,
    )


def build(assets_dir=None) -> list:
    return [build_xg_article()]