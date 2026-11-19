"""Test de la tabla de tiros por temporada (`shot_map.tabla_temporada`), la que alimenta el mapa de un jugador o un equipo.

    python -m unittest web/tests/test_tiros_entidad.py      (desde la raíz del repo)

Lo que no puede fallar: que un jugador sea un `player_id` y no un nombre (hay 26 nombres repetidos entre jugadores
distintos), que un tiro sin rival (Understat deja 95 así) no rompa la tabla, que los nombres salgan como se dicen y
que las columnas sean enteros en las unidades que la vista espera (decímetros, milésimas de xG).
"""

import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "code"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "charts"))

import shot_map as sm  # noqa: E402
from nombres import club_visible  # noqa: E402


def _tiros():
    # (temporada, liga, team, rival, player, player_id, xg, situation, body_part, gol, ancho, fondo)
    filas = [
        ("2025-26", "Premier League", "Arsenal", "Chelsea", "Gabriel", 1, 0.10, "Open Play", "Head", True, 34.0, 6.0),
        ("2025-26", "Premier League", "Arsenal", "Chelsea", "Gabriel", 1, 0.05, "From Corner", "Head", False, 30.0, 8.0),
        ("2025-26", "Premier League", "Arsenal", None, "Gabriel", 1, 0.40, "Open Play", "Right Foot", True, 36.0, 11.0),
        ("2025-26", "La Liga", "Atletico Madrid", "Barcelona", "Gabriel", 2, 0.07, "Open Play", "Left Foot", False, 20.0, 18.0),
        ("2025-26", "La Liga", "Barcelona", "Atletico Madrid", "Raphinha", 3, 0.30, "Direct Freekick", "Right Foot", False, 40.0, 20.0),
        ("2024-25", "La Liga", "Barcelona", "Atletico Madrid", "Raphinha", 3, 0.20, "Open Play", "Left Foot", True, 33.0, 9.0),
    ]
    cols = ["temporada", "liga", "team", "rival", "player", "player_id", "xg", "situation", "body_part", "gol", "ancho", "fondo"]
    return pd.DataFrame(filas, columns=cols)


def _nombre(t, n):
    return {"Gabriel": "Gabriel Magalhães"}.get(n, n)


class TablaTemporada(unittest.TestCase):
    def setUp(self):
        self.p = sm.tabla_temporada(_tiros(), "2025-26", _nombre, club_visible)

    def test_solo_los_tiros_de_la_temporada(self):
        self.assertEqual(self.p["n"], 5)
        self.assertTrue(all(len(v) == 5 for v in self.p["c"].values()))

    def test_un_jugador_es_un_id_aunque_el_nombre_se_repita(self):
        self.assertEqual(len(self.p["jug"]), 3)                       # los dos «Gabriel» y Raphinha
        self.assertEqual(self.p["jug"].count("Gabriel Magalhães"), 2)
        self.assertEqual(sorted(set(self.p["c"]["j"])), [0, 1, 2])
        # el primero (id 1) hizo 3 tiros con el Arsenal; el segundo (id 2), 1 con el Atlético
        self.assertEqual(self.p["c"]["j"].count(0), 3)
        self.assertEqual(self.p["jugClubes"][0], "Arsenal")
        self.assertEqual(self.p["jugClubes"][1], "Atlético Madrid")

    def test_el_tiro_sin_rival_va_con_menos_uno_y_los_demas_conservan_el_suyo(self):
        v = self.p["c"]["v"]
        self.assertEqual(v.count(-1), 1)
        self.assertEqual([self.p["eq"][i] for i in v if i >= 0].count("Chelsea"), 2)

    def test_los_clubes_salen_como_se_dicen_y_tienen_liga(self):
        self.assertIn("Atlético Madrid", self.p["eq"])
        self.assertNotIn("Atletico Madrid", self.p["eq"])
        liga = {n: self.p["ligas"][i] for n, i in zip(self.p["eq"], self.p["eqLiga"]) if i >= 0}
        self.assertEqual(liga["Arsenal"], "Premier League")
        self.assertEqual(liga["Barcelona"], "La Liga")

    def test_unidades_enteras(self):
        c = self.p["c"]
        self.assertEqual(c["x"][0], 340)          # 34.0 m -> decímetros
        self.assertEqual(c["y"][0], 60)
        self.assertEqual(c["xg"][2], 400)         # 0.40 -> milésimas
        self.assertEqual(c["g"], [1, 0, 1, 0, 0])
        for col in c.values():
            self.assertTrue(all(isinstance(v, int) for v in col))

    def test_jugada_y_parte_usan_los_mismos_indices_que_la_tabla_agregada(self):
        c = self.p["c"]
        self.assertEqual(sm.JUGADAS[c["s"][1]], "From Corner")
        self.assertEqual(sm.PARTES[c["b"][1]], "Head")
        self.assertEqual(sm.JUGADAS[c["s"][4]], "Direct Freekick")


if __name__ == "__main__":
    unittest.main()
