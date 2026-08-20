"""Mapa de calor de los tiros — dónde se remata en las 5 grandes ligas.

Este gráfico vive en un módulo propio en vez de duplicarse entre
`web/charts/players.py` y `code/eda_players.ipynb`, que es como se manejan los
demás gráficos de jugadores. La razón es el tamaño de lo que habría que
duplicar: no son veinte líneas de `go.Scatter` sino el binning de 220.720
tiros, el dibujo de la cancha y las 48 combinaciones de temporada × tipo que se
precalculan para que el filtro funcione sin servidor. Dos copias de eso se
separan seguro.

Sistema de coordenadas
----------------------
Understat da `location_x`/`location_y` normalizados 0-1, con `x=1` en la
portería rival. Acá se pasan a dos columnas en metros pensadas para dibujar el
mapa **mirando hacia la portería**:

- `fondo` = distancia a la línea de fondo (0 = línea de gol, arriba del mapa)
- `ancho` = posición a lo ancho, con la **izquierda del ataque a la izquierda**
  del mapa, que es lo que ve alguien parado detrás del equipo que ataca

El segundo invierte `location_y` porque en Understat `y < 0.5` es la banda
derecha del ataque. Se verificó con extremos de posición inequívoca: Salah
(0.41), Saka (0.40), Mahrez (0.40) y Yamal (0.38) juegan por la derecha y sus
tiros caen por debajo de 0.5; Leão (0.58), Nico Williams (0.56) y Coman (0.52)
juegan por la izquierda y caen por encima.
"""

import numpy as np
import pandas as pd

import insights as ins
from viz_theme import FUENTE_UNDERSTAT, INK, SEQUENTIAL_BLUE, select_chart_html

# Dimensiones de cancha, las mismas que asume el resto del proyecto (ver
# `web/charts/ml_xg.py`). El punto de penalti se dibuja donde lo pone Understat
# (0.885 -> 12.1 m) y no a los 11 m del reglamento: el mapa tiene que coincidir
# con los datos que muestra, no con la cancha ideal.
LARGO, ANCHO, PORTERIA = 105.0, 68.0, 7.32
PENAL = (1 - 0.885) * LARGO

# Región dibujada y resolución: los últimos 36 m de cancha en celdas de 2×2 m.
# 36 m deja fuera el 0.5% de los tiros (los de más lejos, tan repartidos que
# solo agregan cancha vacía) y da un mapa más ancho que alto, que es la forma
# que le sirve al contenedor del sitio.
PROFUNDIDAD, CELDA = 36.0, 2.0
NX, NY = int(ANCHO / CELDA), int(PROFUNDIDAD / CELDA)

# Metros de aire por encima de la línea de fondo, para que la portería y el
# borde del área chica no queden cortados contra el borde del gráfico.
AIRE = 1.5

TODAS = "todas"
TODOS = "todos"

# Qué opción del filtro es cada cosa: (valor, etiqueta del desplegable, grupo,
# columna y valor de Understat que la definen, y cómo se nombra dentro de una
# oración). El grupo `None` es la opción suelta de arriba.
TIPOS = [
    (TODOS, "Todos los tiros", None, None, None, ""),
    ("Open Play", "Jugada abierta", "Jugada", "situation", "Open Play", "de jugada abierta "),
    ("From Corner", "Córner", "Jugada", "situation", "From Corner", "de córner "),
    ("Direct Freekick", "Tiro libre directo", "Jugada", "situation", "Direct Freekick",
     "de falta directa "),   # en la oración, para no escribir "tiros de tiro libre"
    ("Set Piece", "Otro balón parado", "Jugada", "situation", "Set Piece",
     "de otro balón parado "),
    ("Head", "Cabezazo", "Parte del cuerpo", "body_part", "Head", "de cabeza "),
    ("Right Foot", "Pie derecho", "Parte del cuerpo", "body_part", "Right Foot",
     "con el pie derecho "),
    ("Left Foot", "Pie izquierdo", "Parte del cuerpo", "body_part", "Left Foot",
     "con el pie izquierdo "),
]

# Lo único que el desplegable no explica solo: qué cae dentro de la etiqueta
# más vaga de las ocho. Que las opciones se cruzan entre sí (un cabezazo puede
# venir de un córner) se cuenta en la caja de lectura, no acá: es una nota sobre
# cómo leer el mapa, no sobre qué hace el control.
HINT = ("\"Otro balón parado\" son las faltas y saques puestos al área que "
        "no acaban en tiro libre directo.")

# Bordes de las celdas. `ancho` crece hacia la derecha del mapa y `fondo` hacia
# el fondo de la cancha; el eje vertical se invierte después, al dibujar.
BORDES_ANCHO = np.linspace(0, ANCHO, NX + 1)
BORDES_FONDO = np.linspace(0, PROFUNDIDAD, NY + 1)
CENTROS_ANCHO = (BORDES_ANCHO[:-1] + BORDES_ANCHO[1:]) / 2
CENTROS_FONDO = (BORDES_FONDO[:-1] + BORDES_FONDO[1:]) / 2


def load(path):
    """Los tiros de las 5 temporadas, listos para el mapa.

    Devuelve `(df, descartes)`: el DataFrame recortado a la región dibujada y
    los conteos de lo que se sacó, que los textos de lectura necesitan para
    poder explicarlo."""
    d = pd.read_csv(path, encoding="utf-8-sig")

    # Los autogoles se van por lo mismo que en el modelo de xG: Understat los
    # registra como un remate más, pero no son un intento de tiro del equipo
    # que aparece en la fila.
    d = d[d["result"] != "Own Goal"]
    penales = int((d["situation"] == "Penalty").sum())
    d = d[d["situation"] != "Penalty"].copy()

    d["fondo"] = (1 - d["location_x"]) * LARGO
    d["ancho"] = (1 - d["location_y"]) * ANCHO   # ver el docstring del módulo
    fuera = int((d["fondo"] > PROFUNDIDAD).sum())
    d = d[d["fondo"] <= PROFUNDIDAD].copy()

    d["gol"] = d["result"] == "Goal"
    d["dist"] = np.hypot(d["fondo"], d["ancho"] - ANCHO / 2)
    d["izquierda"] = d["ancho"] < ANCHO / 2
    lateral = (d["ancho"] - ANCHO / 2).abs()
    d["en_area"] = (d["fondo"] <= 16.5) & (lateral <= 20.16)
    d["en_area_chica"] = (d["fondo"] <= 5.5) & (lateral <= 9.16)
    return d.reset_index(drop=True), {"penales": penales, "fuera": fuera}


def _subconjunto(df, temporada, tipo):
    """Los tiros de una combinación del filtro."""
    d = df if temporada == TODAS else df[df["temporada"] == temporada]
    col, valor = next((c, v) for k, _, _, c, v, _ in TIPOS if k == tipo)
    return d if col is None else d[d[col] == valor]


def _celdas(sub):
    """(porcentaje por celda, `customdata` con tiros, goles y conversión).

    El color es el porcentaje de la selección y no el número de tiros para que
    dos filtros de tamaños muy distintos —163.799 tiros de jugada abierta contra
    6.864 de falta directa— se puedan comparar mirando la forma del mapa. La
    conversión va en el hover porque es la otra mitad de la historia: hay zonas
    desde las que se remata mucho y se mete poco, y el color solo cuenta la
    primera."""
    def grid(d):
        return np.histogram2d(d["fondo"], d["ancho"],
                               bins=[BORDES_FONDO, BORDES_ANCHO])[0]

    n = grid(sub)
    g = grid(sub[sub["gol"]])
    z = 100 * n / n.sum() if n.sum() else n
    conv = np.divide(100 * g, n, out=np.zeros_like(g), where=n > 0)
    custom = np.dstack([n, g, conv.round()]).astype(int)
    return z.round(4).tolist(), custom.tolist()


def _etiqueta_temporada(temporada, seasons):
    return f"las {len(seasons)} temporadas" if temporada == TODAS else temporada


def _subtitulo(temporada, tipo, n, seasons):
    etiqueta = next(e for k, e, _, _, _, _ in TIPOS if k == tipo)
    ambito = f"{seasons[0]} a {seasons[-1]}" if temporada == TODAS else temporada
    return f"{etiqueta} · {ambito} · {ins.miles(n)} remates, sin penaltis"


def _figura(z, custom, subtitulo):
    """El mapa con la temporada y el tipo que se muestran al abrir. Los demás
    estados se cambian con `restyle` sobre esta misma traza (ver `_frames`)."""
    import plotly.graph_objects as go

    fig = go.Figure(go.Heatmap(
        z=z, x=CENTROS_ANCHO, y=CENTROS_FONDO, customdata=custom,
        colorscale=SEQUENTIAL_BLUE, zsmooth=False,
        colorbar=dict(title=dict(text="% de los tiros", side="right"),
                      thickness=14, outlinewidth=0),
        hovertemplate="A %{y:.0f} m de la línea de fondo<br>"
                      "%{customdata[0]} tiros (%{z:.2f}% del total)<br>"
                      "%{customdata[1]} goles (%{customdata[2]}%)<extra></extra>"))

    # La cancha se dibuja con la tinta clara de la superficie, no con la del
    # texto: va ENCIMA del mapa de calor, así que tiene que leerse sobre el
    # azul, y ese azul es el mismo en tema claro y en oscuro.
    linea = dict(color=INK["surface"], width=1.6)
    for medio, fondo in [(20.16, 16.5), (9.16, 5.5)]:
        fig.add_shape(type="rect", x0=ANCHO / 2 - medio, x1=ANCHO / 2 + medio,
                      y0=0, y1=fondo, line=linea, opacity=0.75)
    fig.add_shape(type="circle", x0=ANCHO / 2 - 0.4, x1=ANCHO / 2 + 0.4,
                  y0=PENAL - 0.4, y1=PENAL + 0.4,
                  fillcolor=INK["surface"], line=dict(width=0), opacity=0.75)
    # La portería es lo único que se dibuja FUERA del mapa (detrás de la línea
    # de fondo, en la franja de aire), así que va en tinta media y no en la
    # clara de la superficie: ahí atrás el fondo es el de la página, y el de la
    # página cambia con el tema.
    fig.add_shape(type="rect", x0=ANCHO / 2 - PORTERIA / 2, x1=ANCHO / 2 + PORTERIA / 2,
                  y0=0, y1=-1.2, line=dict(color=INK["muted"], width=1.6))

    # El arco del área va como traza y no como shape: un `path` con arco SVG se
    # dibuja al revés cuando el eje está invertido, y acá lo está.
    tope = np.arcsin(np.sqrt(9.15 ** 2 - (16.5 - PENAL) ** 2) / 9.15)
    ang = np.linspace(-tope, tope, 60)
    fig.add_trace(go.Scatter(
        x=ANCHO / 2 + 9.15 * np.sin(ang), y=PENAL + 9.15 * np.cos(ang),
        mode="lines", line=dict(color=INK["surface"], width=1.6), opacity=0.75,
        hoverinfo="skip", showlegend=False))

    eje = dict(showgrid=False, zeroline=False, showticklabels=False, ticks="",
               showline=False, title=None, constrain="domain")
    fig.update_layout(
        title=dict(text="Mapa de calor de los tiros",
                   subtitle=dict(text=subtitulo)),
        # El eje vertical va invertido (la portería arriba) y con un margen de
        # AIRE metros por encima de la línea de fondo: sin él la línea de gol y
        # el borde del área chica caen justo en el borde del gráfico y se ven
        # cortados por la mitad. El eje horizontal se ancla a este para que la
        # cancha no se deforme al cambiar el ancho del contenedor.
        yaxis=dict(**eje, range=[PROFUNDIDAD, -AIRE]),
        xaxis=dict(**eje, range=[0, ANCHO], scaleanchor="y", scaleratio=1),
        margin=dict(t=95, r=90, b=20, l=20))
    return fig


def _frames(df, seasons):
    """Las 48 combinaciones precalculadas, más la entrada de la caja de lectura
    de cada una.

    Se calculan todas en el build porque el sitio es estático: en el navegador
    no hay pandas con qué rehacer un `histogram2d` de 220.720 filas. Es la misma
    decisión que en los scatter con filtro de liga, solo que acá el estado es
    una combinación de dos controles y no dos filtros independientes — de ahí
    `joint_updates` en vez de un `update` por control."""
    joint, textos, primera = {}, {}, None
    for temporada in [TODAS] + list(seasons):
        base = _subconjunto(df, temporada, TODOS)
        ambito = _etiqueta_temporada(temporada, seasons)
        for tipo, _, _, _, _, frase in TIPOS:
            sub = _subconjunto(df, temporada, tipo)
            z, custom = _celdas(sub)
            subtitulo = _subtitulo(temporada, tipo, len(sub), seasons)
            clave = f"{temporada}|{tipo}"
            # La traza 0 es el mapa; la 1 es el arco del área, que no cambia.
            joint[clave] = {
                "restyle": [{"update": {"z": [z], "customdata": [custom]}, "traces": [0]}],
                "relayout": {"title.subtitle.text": subtitulo},
            }
            textos[clave] = dict(zip(("fija", "salta"),
                                      ins.tiros(sub, base, frase, ambito)))
            if primera is None:
                primera = (z, custom, subtitulo)
    return joint, textos, primera


def shot_map_html(df, descartes, seasons, width=760, height=470):
    """El gráfico completo (figura + controles + caja de lectura) como HTML."""
    joint, textos, (z, custom, subtitulo) = _frames(df, seasons)
    controls = [
        {"id": "temporada", "label": "Temporada",
         "options": [TODAS] + list(seasons), "default": TODAS,
         "labels": {TODAS: "Todas las temporadas"}},
        {"id": "tipo", "label": "Tipo de tiro", "default": TODOS,
         "labels": {k: e for k, e, _, _, _, _ in TIPOS},
         "groups": [(grupo, [k for k, _, g, _, _, _ in TIPOS if g == grupo])
                     for grupo in [None, "Jugada", "Parte del cuerpo"]]},
    ]
    return select_chart_html(
        _figura(z, custom, subtitulo), controls, width=width, height=height,
        # En pantalla angosta se conserva la proporción del escritorio: acá la
        # caja del gráfico contiene una cancha, y hacerla más cuadrada no
        # agranda la cancha, solo deja franjas vacías (ver `_sidebar_css`).
        hint=HINT, joint_updates=joint, mobile_aspect=1.45, fuente=FUENTE_UNDERSTAT,
        insights={"que_mirar": ins.tiros_que_mirar(),
                   "por_que": ins.tiros_por_que(len(df), descartes["penales"],
                                                 descartes["fuera"]),
                   "dinamico": textos})


def render_shot_map(*args, **kwargs):
    """Muestra el mapa en un notebook."""
    from IPython.display import HTML, display
    display(HTML(shot_map_html(*args, **kwargs)))
