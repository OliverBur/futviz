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
            "asistido": "Asistido", "rebote": "Rebote"}.get(c, c)


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
    modelos = [("Misma probabilidad para todos", glob, "neutro", False),
               ("Logística: distancia y ángulo", logi, "neutro", False),
               ("XGBoost · mi modelo", fin, "propio", True),
               ("LightGBM", M["lgbm"], "neutro", False),
               ("Mezcla de XGBoost y LightGBM", M["mezcla"], "neutro", False)]
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
    imp = R["importancia"][:12]
    P["importancia"] = {
        "agrupaciones": [{"id": "gain", "etiqueta": "Ganancia", "filas": [
            {"nombre": _nombre_variable(i["variable"]), "valores": {"gan": i["ganancia"]}} for i in imp]}],
        "series": [{"id": "gan", "nombre": "Ganancia media por corte", "color": "propio"}],
        "eje": {"etiqueta": "Ganancia media por corte", "formato": "num1",
                "dom": [0, max(i["ganancia"] for i in imp) * 1.15]}}

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
           "subtitulo": f"{_n(n_total)} tiros de las cinco últimas temporadas, con lo que dijo cada modelo",
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
        "<p>Aquí construyo el xG desde cero con la metodología de un proyecto de ML con el fin de aprender el detrás de este numero que tan popular se ha vuelto."
        "</p>"))

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
         ["Minuto", "82", "No fue de utilidad"],
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
        f"{_n(E['n'])} tiros de las cinco ligas, {E['temporadas'][0]} a {E['temporadas'][-1]} · elige qué mirar y pasa el "
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
        f"<p>La tarea es clasificar la probabilidad que un tiro sea gol dado su contexto. "
        f"La metodología se basa en un modelo <strong>XGBoost</strong> (árboles de decisión que se corrigen entre sí) con 3 puntos importantes:</p>"
        + _lista([
            "<strong>Split temporal:</strong> entreno con tres temporadas, decido con la siguiente y pruebo en una más. ",
            "<strong>Intervalos por partido:</strong> cada tiro es un dato, pero los tiros de un mismo partido no se mezclan entre entrenamiento y prueba. ",
            "<strong>Validación cruzada:</strong> entreno y decido con todas las combinaciones posibles de tres temporadas, y promedia los resultados. ",])))
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
        f"<p>En esta animación interactiva puedes ver cómo se construye un árbol de decisión para el xG, partiendo de una primer pregunta y creciendo dependiendo de la configuración de profundidad y el número de hojas.<p>Cada hoja tiene su propia tasa de gol, que es la predicción del xG para los tiros que llegan a esa hoja.</p>"))
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
        f"hasta llegar a cientos de árboles chicos con un log-loss de {mx['ll']:.4f}"))
    p.append(_grafica(
        "xg-boosting", "lineas", "boosting", "Árbol por árbol",
        "Log-loss al ir sumando árboles · punteado: entrenamiento; sólido: 2025-26 · "
        f"LightGBM termina con {_n(ml['arboles'])} árboles en {ml['seg']:.0f} s; XGBoost, con {_n(mx['arboles'])} "
        f"en {mx['seg']:.0f} s", "Log-loss de XGBoost y LightGBM según el número de árboles", alto=360))

    # ================================================================ 6. resultados
    p.append(h("Resultados", "resultados"))
    p.append(_prose(
        "<p>Para comparar modelos uso el <strong>log-loss</strong>: mide qué tan buenas son las probabilidades, no solo "
        "si el modelo acertó. Castiga más cuanto más seguro estaba de algo que no pasó (decir «0.9 de xG» y fallar "
        f"penaliza mucho). Menos es mejor, y un log-loss de {base_ll:.4f} es el baseline cuando el modelo le da a todos los tiros la misma "
        "probabilidad.</p>"
        f"<p>En {xm.TEST}, con {_n(n_test)} tiros que el modelo no vio, XGBoost obtuvo un <strong>log-loss de {fin['ll']:.4f}</strong>. "
        "Así queda frente a modelos más simples y a otros algoritmos:</p>"))
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
        f"diferencia: {algo_txt}. Por eso me quedo con XGBoost.</p>"))

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
                                                                 ("asistencia o rebote", "jugada"),
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
        "<p>Para ver qué aprendió, medí el xG que el modelo da a un tiro desde cada punto de la cancha. Elige el tipo "
        "de remate (situación, parte del cuerpo y acción previa) y el mapa cambia:"
        "</p>"))
    p.append(_grafica(
        "xg-superficie", "superficie", "superficie", "Qué aprendió el modelo",
        "xG de un remate desde cada punto de la cancha, según qué tipo de remate sea · la cancha mira "
        "hacia la portería", "Mapa interactivo del xG por zona de la cancha", alto_min=560,
        ayuda="Las zonas sin color no tienen tiros suficientes para opinar."))
    if None not in (z_pie, z_fil, z_cab):
        p.append(_prose(
            "<p>Prueba, por ejemplo, un tiro de frente desde 11 m (el punto penal): el modelo da "
            f"{z_pie:.2f} de xG si es con el pie tras un pase, {z_fil:.2f} si viene de un pase filtrado y "
            f"{z_cab:.2f} si es de cabeza tras un centro.</p>"))

    top = [f"«{_nombre_variable(i['variable'])}»" for i in R["importancia"][:3]]
    p.append(_prose(
        "<p>Otra forma de ver lo que aprendió es de qué variables se agarra. La importancia mide cuánto mejora el "
        "modelo, en promedio, cada vez que usa esa variable para separar un grupo de tiros.</p>"))
    p.append(_grafica(
        "xg-importancia", "barras", "importancia", "De qué se agarra el modelo",
        "Ganancia media por corte de las doce variables más usadas", "Importancia de las variables del modelo",
        alto_min=420))
    p.append(_prose(
        f"<p>Las que más pesan son {top[0]}, {top[1]} y {top[2]}."
        "</p>"))

    # ================================================================ 7. varias temporadas
    p.append(h("¿Y en otras temporadas?", "temporadas"))
    p.append(_prose(
        f"<p>Todo lo anterior fue en {xm.TEST}. Para saber si no fue casualidad, repetí el experimento en {len(ts)} "
        "temporadas, una por cada fila del diagrama de la propuesta de modelo. En cada una comparo contra lo mismo: "
        "predecir siempre la tasa de gol histórica.</p>"))
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
        f"<p>Los {_n(n_explorador)} tiros de las cinco últimas temporadas, cada uno con el xG de un modelo "
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
        title="Constuyendo un modelo de xG",
        subtitle=SUBTITULO,
        deck=SUBTITULO,   # `deck` es obligatorio y el texto de arriba de la página es el que escribió el autor
        body_html="".join(p),
        meta=[("Datos", f"+{_n(R['n']['cerradas'])} tiros · top 5 ligas · 10 temporadas"),
              ("Métodos", "XGBoost · LightGBM · bootstrap por partido")],
        fuente=f"{FUENTE} · temporadas {tray[0]['temporada']} a {tray[-1]['temporada']}",
        react=True,
    )


def build(assets_dir=None) -> list:
    return [build_xg_article()]