"""Tests de «Jugador completo» (`web/charts/venn.py`), con datos sintéticos.

    python -m unittest web/tests/test_venn.py      (desde la raíz del repo)

La regla de membresía (percentil dentro de la posición, empates con el promedio de sus lugares, `p >= 1 - corte`) la repite
`web/react/src/vennCalculo.js`; aquí se fija la de Python.
"""

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
for ruta in (RAIZ / "web", RAIZ / "web" / "charts", RAIZ / "code"):
    sys.path.insert(0, str(ruta))

import venn  # noqa: E402


class Regla(unittest.TestCase):
    def test_percentil_de_valores_distintos(self):
        self.assertTrue(np.allclose(venn.percentiles([10, 30, 20, 40]), [0.125, 0.625, 0.375, 0.875]))

    def test_los_empates_comparten_el_promedio_de_sus_lugares(self):
        p = venn.percentiles([1, 2, 2, 3])
        self.assertEqual(p[1], p[2])
        self.assertAlmostEqual(p[1], (2.5 - 0.5) / 4)

    def test_regiones_suman_a_los_que_pasan_algun_corte(self):
        rng = np.random.default_rng(0)
        v = [rng.normal(size=200) for _ in range(3)]
        r = venn.regiones(v, 0.15)
        self.assertEqual(sorted(r), list(range(1, 8)))
        # cada círculo tiene el 15% de la población (sin empates)
        for j in range(3):
            self.assertEqual(sum(n for m, n in r.items() if m >> j & 1), 30)

    def test_tres_criterios_identicos_dejan_todo_en_el_centro(self):
        x = list(range(100))
        r = venn.regiones([x, x, x], 0.2)
        self.assertEqual(r[7], 20)
        self.assertEqual(sum(r.values()), 20)


def _df():
    filas = []
    for i in range(12):
        filas.append({"temporada": "2025-26", "player": f"J{i}", "team": "Club", "liga": "La Liga", "posicion": "Defensa" if i < 10 else "Portero",
                      "min": 1000 if i != 3 else 100, "recoveries90": 2.0 + i, "np_xg": 0.1 * i, "xA": 0.9, "xgchain90": 0.3, "xgbuild90": 0.2, "npxg90": 0.05})
    filas[5]["recoveries90"] = np.nan
    return pd.DataFrame(filas)


class Tabla(unittest.TestCase):
    def test_corte_de_minutos_posicion_y_nulos(self):
        t = venn.tabla(_df(), {"2025-26": 900})["2025-26"]
        nombres = [f[0] for f in t["jug"]]
        self.assertNotIn("J3", nombres)     # menos minutos que el corte
        self.assertNotIn("J5", nombres)     # sin recuperaciones (no cruzó con FBref)
        self.assertNotIn("J10", nombres)    # portero
        self.assertEqual(len(nombres), 8)
        self.assertEqual(t["minimo"], 900)

    def test_el_orden_de_las_columnas_es_el_del_payload(self):
        fila = venn.tabla(_df(), {"2025-26": 900})["2025-26"]["jug"][0]
        self.assertEqual(len(fila), venn.PREFIJO + len(venn.MEDIDAS))
        self.assertEqual(fila[venn.PREFIJO], 2.0)    # rec = recoveries90

    def test_xg_sin_penales_mas_xa_y_xa_se_arman_con_los_totales(self):
        d = venn.preparar(_df(), {"2025-26": 900})
        fila = d[d["player"] == "J4"].iloc[0]
        noventas = 1000 / 90
        self.assertAlmostEqual(fila["npxga90"], (0.4 + 0.9) / noventas)
        self.assertAlmostEqual(fila["xa90_exacto"], 0.9 / noventas)


class Config(unittest.TestCase):
    def test_cada_circulo_apunta_a_una_medida_que_viaja(self):
        claves = {k for k, _ in venn.MEDIDAS}
        for v in venn.VENNS:
            self.assertEqual(len(v["sets"]), 3)
            self.assertIn(v["pos"], venn.POSICIONES)
            for s in v["sets"]:
                self.assertIn(s["col"], claves)


if __name__ == "__main__":
    unittest.main()
