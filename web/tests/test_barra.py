"""Test de la barra de arriba, la lupa del buscador y el encabezado compacto, sobre lo que quedó en `web/dist`
(correr después de build.py).

    python -m unittest web/tests/test_barra.py      (desde la raíz del repo)

Comprueba que los nombres cortos de la barra ("Gráficas", "Modelos") no cambien los títulos de las páginas, que la
lupa y su <dialog> estén en todas las páginas menos la portada (que ya tiene el campo grande) con la ruta correcta al
script y al índice, que ningún id del buscador se repita ni choque con otro de la página, y que el encabezado compacto
sea solo el del análisis exploratorio.
"""

import re
import unittest
from collections import Counter
from pathlib import Path

WEB = Path(__file__).resolve().parents[1]
DIST = WEB / "dist"

# (archivo, prefijo de la ruta de la página a la raíz del sitio)
PAGINAS = [("index.html", ""), ("analisis-exploratorio.html", ""), ("machine-learning.html", ""),
           ("analisis/modelo-xg.html", "../")]


def _html(archivo):
    return (DIST / archivo).read_text(encoding="utf-8")


class TestBarra(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (DIST / "index.html").exists():
            raise unittest.SkipTest("Falta web/dist: corre `python build.py` antes del test.")

    def test_nombres_cortos_con_nombre_completo_accesible(self):
        for archivo, prefijo in PAGINAS:
            barra = re.search(r'<nav class="sitebar-nav".*?</nav>', _html(archivo), re.S).group(0)
            self.assertIn('title="Análisis exploratorio: gráficas de jugadores y equipos"', barra, archivo)
            self.assertIn('aria-label="Análisis exploratorio: gráficas de jugadores y equipos"', barra, archivo)
            self.assertIn('title="Machine Learning: modelos y artículos"', barra, archivo)
            self.assertIn('aria-label="Machine Learning: modelos y artículos"', barra, archivo)
            self.assertRegex(barra, rf'href="{re.escape(prefijo)}analisis-exploratorio\.html"[^>]*>Gráficas</a>', archivo)
            self.assertRegex(barra, rf'href="{re.escape(prefijo)}machine-learning\.html"[^>]*>Modelos</a>', archivo)
            # el texto visible va contenido en el nombre accesible (WCAG 2.5.3)
            self.assertNotIn(">Análisis exploratorio</a>", barra)
            self.assertNotIn(">Machine Learning</a>", barra)

    def test_los_titulos_de_las_paginas_no_cambian(self):
        eda, ml, portada = (_html(a) for a in ("analisis-exploratorio.html", "machine-learning.html", "index.html"))
        self.assertIn("<title>Análisis exploratorio · FutViz</title>", eda)
        self.assertIn('<h1 class="page-title">Análisis exploratorio</h1>', eda)
        self.assertIn("<title>Machine Learning · FutViz</title>", ml)
        self.assertIn('<h1 class="page-title">Machine Learning</h1>', ml)
        self.assertIn('<span class="puerta-nombre">Análisis exploratorio →</span>', portada)
        self.assertIn('<span class="puerta-nombre">Machine Learning →</span>', portada)

    def test_lupa_y_dialogo(self):
        for archivo, prefijo in PAGINAS:
            html = _html(archivo)
            lupa = re.search(r'<button[^>]*id="buscador-abrir"[^>]*>', html).group(0)
            self.assertIn('aria-label="Buscar"', lupa, archivo)
            if archivo == "index.html":
                # la portada no lleva <dialog>: la lupa enfoca el campo grande
                self.assertNotIn("<dialog class", html)
                self.assertIn('aria-controls="buscador-q"', lupa)
                self.assertNotIn("aria-expanded", lupa)
                self.assertEqual(html.count('id="buscador"'), 1)
                continue
            self.assertIn('aria-controls="buscador-dialogo"', lupa, archivo)
            self.assertIn('aria-expanded="false"', lupa, archivo)
            self.assertEqual(html.count("<dialog class"), 1, archivo)
            self.assertIn(f'action="{prefijo}analisis-exploratorio.html" data-prefijo="{prefijo}"', html, archivo)
            self.assertIn(f'<script src="{prefijo}assets/buscador.js" defer></script>', html, archivo)

    def test_ids_sin_repetir(self):
        """Un id repetido haría que `getElementById` del buscador (o el `#anuncio` del lector de ML) tomara el equivocado."""
        for archivo, _ in PAGINAS:
            ids = Counter(re.findall(r'\sid="([^"]+)"', _html(archivo)))
            repetidos = {i: n for i, n in ids.items() if n > 1}
            self.assertEqual(repetidos, {}, archivo)
        self.assertEqual(Counter(re.findall(r'\sid="([^"]+)"', _html("machine-learning.html")))["anuncio"], 1)

    def test_encabezado_compacto_solo_en_graficas(self):
        eda, ml = _html("analisis-exploratorio.html"), _html("machine-learning.html")
        self.assertIn('<header class="page-header page-header--compacto">', eda)
        self.assertIn('<div class="lead">Compara jugadores y equipos de las 5 ligas. Toca un punto para ver quién es.</div>', eda)
        # la meta description conserva el texto completo
        self.assertIn('<meta name="description" content="Rendimiento, estilo y nivel de jugadores y equipos de las '
                      '5 grandes ligas, con filtros y un explorador para cruzar cualquier par de variables.">', eda)
        self.assertIn('<header class="page-header">', ml)   # el CSS de la variante va en todas; la clase, solo en la de gráficas
        self.assertIn('<div class="lead">Aplicación de modelos de Machine Learning para buscar patrones que no estén a simple vista.</div>', ml)


if __name__ == "__main__":
    unittest.main()
