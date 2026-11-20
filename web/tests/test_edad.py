"""Tests de la vista «Edad» (`web/charts/edad.py`), con datos sintéticos.

    python -m unittest web/tests/test_edad.py      (desde la raíz del repo)

Comprueban la edad, los minutos disponibles (con jugadores de dos clubes), el corte de 30 jugador-temporadas, que los
porteros queden aparte y que la vista se arme con datos sintéticos.
"""

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
for ruta in (RAIZ / "web", RAIZ / "web" / "charts", RAIZ / "code"):
    sys.path.insert(0, str(ruta))

import edad  # noqa: E402


def _jugador(temporada, nombre, club, minutos, nacido, posicion="Medio", liga="La Liga", **extra):
    fila = {"temporada": temporada, "liga": liga, "player": nombre, "player_fbref": nombre, "team": club,
            "min": minutos, "np_xg": 1.0, "xA": 1.0, "born": nacido, "posicion": posicion,
            "tkl_w90": 1.0, "interceptions90": 1.0}
    fila.update(extra)
    return fila


PARTIDOS = {("2021-22", "La Liga", "Club A"): 38, ("2021-22", "La Liga", "Club B"): 20,
            ("2021-22", "Serie A", "Club C"): 38}


class EdadYMinutos(unittest.TestCase):
    def test_la_edad_es_anio_de_la_temporada_menos_anio_de_nacimiento(self):
        self.assertEqual(list(edad.edad_de(["2025-26", "2021-22"], [2000, 2003])), [25, 18])

    def test_la_edad_coincide_con_la_de_players(self):
        import players
        df = pd.DataFrame({"temporada": ["2024-25"], "born": [2001.0]})
        esperada = df["temporada"].str[:4].astype(int) - df["born"]   # la línea de `players.load_data`
        self.assertEqual(float(edad.edad_de(df["temporada"], df["born"])[0]), float(esperada[0]))

    def test_minutos_disponibles_de_un_club(self):
        self.assertEqual(edad.minutos_disponibles("2021-22", "La Liga", "Club A", PARTIDOS), 38 * 90)

    def test_dos_clubes_toman_el_de_mas_partidos(self):
        self.assertEqual(edad.minutos_disponibles("2021-22", "La Liga", "Club B,Club A", PARTIDOS), 38 * 90)
        self.assertEqual(edad.minutos_disponibles("2021-22", "La Liga", "Club A,Club B", PARTIDOS), 38 * 90)

    def test_un_club_que_no_cruza_es_nulo(self):
        self.assertTrue(np.isnan(edad.minutos_disponibles("2021-22", "La Liga", "Club Z", PARTIDOS)))
        # si uno de los dos cruza, se usa ese
        self.assertEqual(edad.minutos_disponibles("2021-22", "La Liga", "Club Z,Club B", PARTIDOS), 20 * 90)

    def test_jugador_temporadas_junta_dos_ligas_y_no_corta_por_minutos(self):
        p = pd.DataFrame([
            _jugador("2021-22", "Ana", "Club A", 1500, 2000),
            _jugador("2021-22", "Ana", "Club C", 800, 2000, liga="Serie A", np_xg=2.0, xA=0.5),  # mismo año, otra liga
            _jugador("2021-22", "Beto", "Club A", 20, 2003),                                   # 20 minutos: cuenta
            _jugador("2021-22", "Cris", "Club A", 3600, 1999, posicion="Portero"),            # pasa de 100%: se topa
            _jugador("2021-22", "Sin", "Club A", 900, np.nan),                                # sin nacimiento: fuera
        ])
        jt = edad.jugador_temporadas(p, PARTIDOS, ["2021-22"])
        self.assertEqual(sorted(jt["clave"]), ["Ana", "Beto", "Cris"])
        ana = jt[jt["clave"] == "Ana"].iloc[0]
        self.assertEqual(ana["min"], 2300)
        self.assertEqual(ana["disp"], 38 * 90)
        self.assertAlmostEqual(ana["pct"], 100 * 2300 / (38 * 90))
        self.assertEqual(ana["posicion"], "Medio")
        self.assertEqual(ana["edad"], 21)
        self.assertEqual(jt[jt["clave"] == "Beto"].iloc[0]["min"], 20)
        self.assertEqual(jt[jt["clave"] == "Cris"].iloc[0]["pct"], 100)
        self.assertEqual(jt.attrs["sin_nacimiento"], 1)

    def test_corte_de_30_jugador_temporadas(self):
        filas = [{"edad": 20, "pct": 10.0 + i, "posicion": "Medio"} for i in range(30)]
        filas += [{"edad": 21, "pct": 10.0 + i, "posicion": "Medio"} for i in range(29)]
        m = edad.minutos_por_edad(pd.DataFrame(filas), edad.CAMPO)
        self.assertEqual(m["e"], [20])
        self.assertEqual(m["n"], [30])
        self.assertEqual(m["ocultas"], [21])
        self.assertAlmostEqual(m["med"][0], 24.5)

    def test_campo_no_incluye_porteros(self):
        d = pd.DataFrame([{"edad": 25, "pct": 100.0, "posicion": "Portero"}] * 40
                         + [{"edad": 25, "pct": 10.0, "posicion": "Defensa"}] * 40
                         + [{"edad": 25, "pct": 20.0, "posicion": None}] * 40)
        self.assertEqual(edad.minutos_por_edad(d, edad.CAMPO)["n"], [80])
        self.assertEqual(edad.minutos_por_edad(d, "Portero")["med"], [100.0])


class VistaCompleta(unittest.TestCase):
    def test_calcular_y_textos_con_datos_sinteticos(self):
        rng = np.random.default_rng(3)
        filas, equipos = [], []
        temporadas = ["2021-22", "2022-23", "2023-24", "2026-27"]
        for t in temporadas:
            equipos.append({"temporada": t, "liga": "La Liga", "Squad": "Club A",
                            "ov_Playing Time_MP": 6 if t == "2026-27" else 38})
        for i in range(600):
            nacido = int(rng.integers(1988, 2006))
            for t in temporadas:
                filas.append(_jugador(t, f"J{i}", "Club A", int(rng.integers(100, 3300)), nacido,
                                      posicion=["Defensa", "Medio", "Delantero", "Portero"][i % 4]))
        r = edad.calcular(pd.DataFrame(filas), pd.DataFrame(equipos), en_curso=["2026-27"])
        self.assertEqual(r["temporadas"], ["2021-22", "2022-23", "2023-24"])      # la que va en curso no entra
        self.assertEqual(set(r["minutos"]), set(edad.POSICIONES_MINUTOS))
        que_mirar, por_que = edad.textos(r)
        self.assertIn("mediana", que_mirar)
        self.assertIn(str(edad.MIN_JUGADORES), por_que)
        self.assertNotIn("endimiento", que_mirar + por_que)       # el panel de rendimiento ya no existe
        carga = edad.payload(r)
        self.assertEqual(carga["edades"], [edad.EDAD_MIN, edad.EDAD_MAX])
        self.assertEqual(carga["minJugadores"], edad.MIN_JUGADORES)


if __name__ == "__main__":
    unittest.main()
