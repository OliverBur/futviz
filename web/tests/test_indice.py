"""Test del índice del buscador de la landing, sobre lo que quedó en `web/dist` (correr después de build.py).

    python -m unittest web/tests/test_indice.py      (desde la raíz del repo)

Comprueba que el índice no tenga duplicados, que cada destino de un jugador o equipo sea una vista real de su
entidad con una temporada en la que ese nombre tiene fila en la tabla que usa la gráfica, que los enlaces de
"Preguntas para empezar" apunten a vistas que existen, que la portada no pida el índice al cargar y que el
peso quede dentro del presupuesto.
"""

import gzip
import json
import re
import sys
import unittest
from pathlib import Path

WEB = Path(__file__).resolve().parents[1]
DIST = WEB / "dist"
sys.path.insert(0, str(WEB))


def _js_a_json(ruta, prefijo):
    texto = ruta.read_text(encoding="utf-8")
    assert texto.startswith(prefijo), f"{ruta.name} no empieza con {prefijo!r}"
    return json.loads(texto[len(prefijo):].rstrip().rstrip(";"))


def _tabla(nombre):
    texto = (DIST / "react" / f"datos-{nombre}.js").read_text(encoding="utf-8")
    return json.loads(texto[texto.index("]=") + 2:].rstrip().rstrip(";"))


class TestIndice(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ruta = DIST / "assets" / "search-index.js"
        if not cls.ruta.exists():
            raise unittest.SkipTest("Falta web/dist: corre `python build.py` antes del test.")
        cls.ix = _js_a_json(cls.ruta, "window.futvizIndice=")
        cls.html = (DIST / "index.html").read_text(encoding="utf-8")

    def test_sin_duplicados(self):
        for clave in ("j", "e"):
            nombres = [x[0] for x in self.ix[clave]]
            self.assertEqual(len(nombres), len(set(nombres)), f"nombres repetidos en '{clave}'")
        self.assertEqual(len({v[0] for v in self.ix["v"]}), len(self.ix["v"]), "vistas repetidas")

    def test_destinos_validos(self):
        """Cada destino: una vista de la entidad correcta y una temporada con fila de ese nombre."""
        temporadas, vistas = self.ix["t"], self.ix["v"]
        for clave, entidad, tabla, i_dest in (("j", "Jugadores", "jugadores", 4), ("e", "Equipos", "equipos", 2)):
            t = _tabla(tabla)
            filas = {}
            for r in range(t["n"]):
                filas.setdefault(t["nombres"][t["f"]["j"][r]], set()).add(t["temporadas"][t["f"]["t"][r]])
            for entrada in self.ix[clave]:
                nombre, destinos = entrada[0], entrada[i_dest]
                self.assertTrue(destinos, f"{nombre} no tiene ninguna gráfica")
                self.assertIn(nombre, filas, f"{nombre} no está en la tabla {tabla}")
                for v, ti in destinos:
                    self.assertEqual(vistas[v][3], entidad, f"{nombre} -> {vistas[v][0]} no es de {entidad}")
                    self.assertIn(temporadas[ti], filas[nombre], f"{nombre} no tiene fila en {temporadas[ti]}")

    def test_sugerencias(self):
        """Las sugerencias del campo vacío: jugadores que están en el índice, con sus goles reales en esa
        temporada, y vistas que existen."""
        s = self.ix["s"]
        nombres = {x[0] for x in self.ix["j"]}
        t = _tabla("jugadores")
        temporada = s["titulo"].rsplit(" ", 1)[-1]
        self.assertIn(temporada, t["temporadas"])
        ti = t["temporadas"].index(temporada)
        goles = {}
        for r in range(t["n"]):
            if t["f"]["t"][r] == ti and t["c"]["goals"][r] is not None:
                n = t["nombres"][t["f"]["j"][r]]
                goles[n] = max(goles.get(n, 0), t["c"]["goals"][r])
        self.assertTrue(s["j"])
        for nombre, g in s["j"]:
            self.assertIn(nombre, nombres)
            self.assertEqual(g, goles[nombre], f"{nombre}: goles distintos a los de la tabla")
        self.assertEqual(max(g for _, g in s["j"]), max(goles.values()), "falta el máximo goleador")
        for i in s["v"]:
            self.assertLess(i, len(self.ix["v"]))

    def test_enlaces_de_la_portada(self):
        slugs = {v[0] for v in self.ix["v"]}
        enlaces = re.findall(r'href="analisis-exploratorio\.html#([^"?]+)"', self.html)
        self.assertGreaterEqual(len(enlaces), 6)
        for slug in enlaces:
            self.assertIn(slug, slugs, f"la portada enlaza a una vista que no existe: {slug}")
        self.assertIn(f"Ver las {len(self.ix['v'])} gráficas", self.html)

    def test_el_indice_no_se_pide_al_cargar(self):
        self.assertNotIn("search-index.js", self.html)

    def test_presupuesto(self):
        from landing import PRESUPUESTO_INDICE_KB
        kb = len(gzip.compress(self.ruta.read_bytes(), 9)) / 1024
        self.assertLessEqual(kb, PRESUPUESTO_INDICE_KB, f"el índice pesa {kb:.1f} KB gzip")


if __name__ == "__main__":
    unittest.main()
