"""Las vistas del sitio hechas en React + MUI X Charts.

Todo el "Análisis exploratorio" pasa por un build de Node: `web/react/` (Vite) compila TODAS las
vistas a un solo archivo, `web/react/build/futviz-react.js`, y `build.py` lo copia a `dist/react/`.
Como `dist/`, el bundle compilado se versiona: Vercel sigue sirviendo estáticos y no hace falta
Node para correr `python build.py`.

**Contrato con el bundle** (ver `web/react/src/main.jsx`). Una vista es un fragmento mínimo:

    <div data-rx="scatter" data-rx-id="goles-vs-xg"></div>
    <script>(window.futvizVistas=window.futvizVistas||{})["goles-vs-xg"]={...configuración...};</script>

El cascarón (`section_views.py`) carga el bundle una sola vez y, al insertar cada fragmento, le pide
que monte lo que encuentre. Los DATOS no viajan en el fragmento: viven en tablas compartidas,
`dist/react/datos-<nombre>.js`, una por entidad (`jugadores`, `equipos`, `tiros`), que el bundle pide
la primera vez que una vista las necesita y que reutilizan todas las de esa entidad. Antes cada
vista llevaba sus datos adentro (hasta 3 MB por vista, repetidos 11 veces); ahora es una sola tabla.
Son `.js` y no `.json` por la misma razón que los fragmentos: tiene que funcionar abierto con doble
clic (`file://`), donde `fetch` no sirve.

**Por qué columnas.** La tabla viaja en columnas (un arreglo por variable) con los nombres de
jugador y equipo en un diccionario, y los filtros, los promedios, los rankings y los textos
("en lo que estás viendo") los calcula el navegador sobre ella. Por eso el texto no puede
contradecir al gráfico ni en principio. `web/react/test/paridad.mjs` comprueba que el JS dice lo
mismo que `code/insights.py` sobre cientos de combinaciones.
"""

import json
import math
import shutil
from pathlib import Path

import pandas as pd

REACT_DIR = Path(__file__).parent / "react"
BUNDLE = REACT_DIR / "build" / "futviz-react.js"

# Decimales con los que viaja un número. Ocho: los textos se redondean a 1 o 2 decimales, y con menos
# el redondeo doble (al viajar y al mostrar) cambiaría alguna cifra respecto de la que da Python
# sobre el dato completo: una de cada ~400 con cuatro decimales, una de cada ~40.000 con seis (el
# test de paridad lo encontró: 0,2249999… viajaba como 0,225 y se mostraba 0,23 en vez de 0,22).
DECIMALES = 8

_TABLAS = {}   # nombre -> payload; `escribir_datos` las vuelca a dist/react/


def bundle_disponible() -> bool:
    return BUNDLE.exists()


def exigir_bundle():
    """El sitio ya no tiene vistas sin React: sin bundle no hay gráficas."""
    if not bundle_disponible():
        raise SystemExit(
            "Falta el bundle de React (web/react/build/futviz-react.js). Compílalo con "
            "`npm install && npm run build` dentro de web/react y vuelve a correr build.py.")


def copiar_bundle(dist_dir: Path) -> Path:
    """Copia el bundle compilado a `dist/react/`. `build.py` borra `dist/` entero en
    cada corrida, así que esto se llama después de recrearlo."""
    destino = dist_dir / "react" / BUNDLE.name
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(BUNDLE, destino)
    return destino


# --- tablas ------------------------------------------------------------------------------------

def _num(v, decimales=DECIMALES):
    """Un número listo para JSON: nulo si no hay dato, entero si lo es. `decimales=None` lo deja
    con su precisión completa (JSON y JS conservan la `double` tal cual)."""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    if pd.isna(v):
        return None
    v = float(v)
    if v.is_integer():
        return int(v)
    return v if decimales is None else round(v, decimales)


def _columna(serie, decimales=DECIMALES):
    return [_num(v, decimales) for v in serie]


def _codigos(serie, categorias):
    """Índice de cada valor en `categorias`; -1 si no está (posición o nivel desconocidos)."""
    indice = {c: i for i, c in enumerate(categorias)}
    return [indice.get(v, -1) for v in serie]


def _diccionario(serie):
    """(valores únicos, código de cada fila): los nombres repetidos viajan una sola vez."""
    codigos, unicos = pd.factorize(serie)
    return [str(u) for u in unicos], [int(c) for c in codigos]


def registrar_tabla(nombre, df, *, nombre_col, columnas, ligas, temporadas, equipo_col=None,
                    posiciones=None, niveles=None, sub21_col=None, extra=None, derivadas=None,
                    exactas=()):
    """Arma la tabla columnar de una entidad y la deja registrada para `escribir_datos`.

    `columnas` son las numéricas (las variables de los ejes y las que usan los textos); las que no
    estén en `df` se omiten, como hace el explorador con las variables opcionales de FBref.

    `derivadas` son columnas que NO viajan y el navegador recalcula con la misma operación que usó
    Python (`datos.prepararTabla`): `{"xga90": ["suma", "xG90", "xA90"], "kp90": ["por90", "key_passes"]}`.
    Existen por los empates: `xga90 <= mediana` con una mediana de exactamente 0.15 se decide por el
    ruido de coma flotante de `xG90 + xA90` (0.15000000000000002), y redondear la suma al viajar lo
    pierde. Calculada igual que en Python, da el mismo resultado bit a bit. `exactas` son las columnas
    que viajan con su precisión completa porque alimentan una derivada (sus operandos tienen que ser
    idénticos a los de Python)."""
    nombres, j = _diccionario(df[nombre_col])
    f = {"j": j,
         "l": _codigos(df["liga"].astype(str), ligas),
         "t": _codigos(df["temporada"], temporadas)}
    payload = {"entidad": nombre, "n": len(df), "temporadas": list(temporadas), "ligas": list(ligas),
               "nombres": nombres, "f": f}
    if equipo_col:
        payload["equipos"], f["e"] = _diccionario(df[equipo_col])
    if posiciones:
        payload["posiciones"] = list(posiciones)
        f["p"] = _codigos(df["posicion"], posiciones)
    if niveles:
        payload["niveles"] = list(niveles)
        f["v"] = _codigos(df["nivel"], niveles)
    if sub21_col and sub21_col in df.columns:
        f["u"] = [1 if v is True or v == 1 else 0 for v in df[sub21_col].fillna(False)]
    derivadas = derivadas or {}
    payload["c"] = {c: _columna(df[c], None if c in exactas else DECIMALES)
                    for c in columnas if c in df.columns and c not in derivadas}
    if derivadas:
        payload["derivadas"] = derivadas
    if extra:
        payload.update(extra)
    _TABLAS[nombre] = payload
    return payload


def registrar_payload(nombre, payload):
    """Registra una tabla ya armada (la del mapa de tiros, que no sale de un DataFrame de entidades)."""
    _TABLAS[nombre] = payload
    return payload


def escribir_datos(dist_dir: Path):
    """Vuelca cada tabla registrada a `dist/react/datos-<nombre>.js`. Devuelve las rutas."""
    salida = []
    for nombre, payload in _TABLAS.items():
        ruta = dist_dir / "react" / f"datos-{nombre}.js"
        ruta.parent.mkdir(parents=True, exist_ok=True)
        cuerpo = json.dumps(payload, separators=(",", ":"), allow_nan=False).replace("</", "<\\/")
        ruta.write_text(
            f"(window.futvizDatos=window.futvizDatos||{{}})[{json.dumps(nombre)}]={cuerpo};",
            encoding="utf-8")
        salida.append(ruta)
    return salida


# --- vistas ------------------------------------------------------------------------------------

def montar_html(tipo: str, vista_id: str, config: dict) -> str:
    """El fragmento de una vista: contenedor y configuración (ver el contrato arriba)."""
    cuerpo = json.dumps(config, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return (
        f'<div class="rx-mount" data-rx="{tipo}" data-rx-id="{vista_id}" style="min-height:520px"></div>'
        f'<script>(window.futvizVistas=window.futvizVistas||{{}})[{json.dumps(vista_id)}]={cuerpo};</script>'
    )
