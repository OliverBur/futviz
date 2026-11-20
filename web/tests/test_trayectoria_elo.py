"""Tests de la vista «Trayectoria del club en ELO» (`web/charts/trayectoria_elo.py`).

    python -m unittest web/tests/test_trayectoria_elo.py      (desde la raíz del repo)

Dos partes. Las pruebas sintéticas comprueban el cruce de nombres, los huecos de los clubes que suben o bajan, las
temporadas sin ELO, el promedio de referencia, el orden de las temporadas, la selección inicial y el payload. Las de datos
reales necesitan `data/processed/` y se saltan si no está: que cada temporada traiga sus clubes, que los grandes salgan
con ELO alto y que un descenso se vea como hueco.
"""

import json
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(RAIZ / "web"), str(RAIZ / "web" / "charts"), str(RAIZ / "code")]

import trayectoria_elo as te  # noqa: E402

PROCESADOS = RAIZ / "data" / "processed"
NAN = np.nan


def _fila(temporada, squad, liga, pre, medio, fin):
    return dict(temporada=temporada, liga=liga, Squad=squad, elo_pre=pre, elo_medio=medio, elo_fin=fin)


def _equipos():
    """Cuatro temporadas (la última sin ELO) y cuatro clubes:

    * «Manchester Utd» (FBref) está siempre, en la Premier. El nombre visible es «Manchester United».
    * «Burnley» baja en 2022-23 y vuelve en 2023-24: hueco en el medio.
    * «Paris SG» es el nombre de FBref de una temporada; en las demás es «PSG». Los dos se muestran «PSG».
    * «Bayern Munich» está siempre, en la Bundesliga, y es el más fuerte de todos.
    Las filas llegan desordenadas a propósito."""
    f = [
        _fila("2023-24", "Manchester Utd", "Premier League", 1800, 1820, 1840),
        _fila("2021-22", "Burnley", "Premier League", 1600, 1610, 1620),
        _fila("2022-23", "Manchester Utd", "Premier League", 1700, 1720, 1740),
        _fila("2021-22", "Manchester Utd", "Premier League", 1750, 1760, 1770),
        _fila("2023-24", "Burnley", "Premier League", 1650, 1660, 1670),
        _fila("2021-22", "PSG", "Ligue 1", 1900, 1910, 1920),
        _fila("2022-23", "PSG", "Ligue 1", 1930, 1940, 1950),
        _fila("2023-24", "Paris SG", "Ligue 1", 1960, 1970, 1980),
        _fila("2021-22", "Bayern Munich", "Bundesliga", 1950, 1960, 1970),
        _fila("2022-23", "Bayern Munich", "Bundesliga", 1990, 2000, 2010),
        _fila("2023-24", "Bayern Munich", "Bundesliga", 2000, 2020, 2040),
        _fila("2024-25", "Manchester Utd", "Premier League", NAN, NAN, NAN),
        _fila("2024-25", "Bayern Munich", "Bundesliga", NAN, NAN, NAN),
    ]
    return pd.DataFrame(f)


class Sintetico(unittest.TestCase):
    def setUp(self):
        self.eq = _equipos()
        self.r = te.calcular(self.eq)
        self.p = te.payload(self.r)
        self.club = {c["n"]: c for c in self.p["clubes"]}

    def test_cruza_los_nombres_con_club_visible(self):
        self.assertEqual(sorted(self.club), ["Bayern Múnich", "Burnley", "Manchester United", "PSG"])

    def test_un_club_que_cambia_de_nombre_en_fbref_sigue_siendo_uno(self):
        # «PSG» (dos temporadas) y «Paris SG» (una) son la misma línea, con las tres temporadas seguidas.
        self.assertEqual(self.club["PSG"]["med"], [1910.0, 1940.0, 1970.0])

    def test_las_temporadas_van_en_orden_aunque_las_filas_no(self):
        self.assertEqual(self.p["temporadas"], ["2021-22", "2022-23", "2023-24"])
        self.assertEqual(self.club["Manchester United"]["pre"], [1750.0, 1700.0, 1800.0])

    def test_la_temporada_sin_elo_no_entra_y_se_avisa(self):
        self.assertEqual(self.p["sinElo"], ["2024-25"])
        self.assertNotIn("2024-25", self.p["temporadas"])
        self.assertTrue(all(len(c["med"]) == 3 for c in self.p["clubes"]))

    def test_el_club_que_baja_y_sube_deja_un_hueco_no_un_puente(self):
        b = self.club["Burnley"]
        self.assertEqual(b["pre"], [1600.0, None, 1650.0])
        self.assertEqual(b["med"], [1610.0, None, 1660.0])
        self.assertEqual(b["fin"], [1620.0, None, 1670.0])

    def test_la_referencia_es_el_promedio_simple_de_los_clubes_de_esa_temporada(self):
        # 2021-22: Man Utd 1760, Burnley 1610, PSG 1910, Bayern 1960. 2022-23: no hay Burnley.
        self.assertEqual(self.p["n"], [4, 3, 4])
        self.assertAlmostEqual(self.p["ref"]["med"][0], (1760 + 1610 + 1910 + 1960) / 4, places=1)
        self.assertAlmostEqual(self.p["ref"]["med"][1], (1720 + 1940 + 2000) / 3, places=1)
        self.assertAlmostEqual(self.p["ref"]["pre"][1], (1700 + 1930 + 1990) / 3, places=1)
        self.assertAlmostEqual(self.p["ref"]["fin"][2], (1840 + 1670 + 1980 + 2040) / 4, places=1)

    def test_la_liga_es_la_de_la_ultima_temporada_con_elo(self):
        ligas = self.p["ligas"]
        self.assertEqual(ligas[self.club["PSG"]["l"]], "Ligue 1")
        self.assertEqual(ligas[self.club["Burnley"]["l"]], "Premier League")
        e = self.eq.copy()
        e.loc[(e["Squad"] == "Burnley") & (e["temporada"] == "2023-24"), "liga"] = "Serie A"
        c = {x["n"]: x for x in te.payload(te.calcular(e))["clubes"]}
        self.assertEqual(ligas[c["Burnley"]["l"]], "Serie A")

    def test_la_seleccion_inicial_es_el_mas_fuerte_de_cada_liga_de_mayor_a_menor(self):
        # Última temporada con ELO: 2023-24, con «Promedio»: Bayern 2020, PSG 1970, Man Utd 1820.
        self.assertEqual(self.r["iniciales"], ["Bayern Múnich", "PSG", "Manchester United"])
        self.assertEqual(self.p["iniciales"], self.r["iniciales"])

    def test_un_elo_a_medias_es_un_error_del_dato(self):
        e = self.eq.copy()
        e.loc[0, "elo_fin"] = NAN
        with self.assertRaises(ValueError):
            te.calcular(e)

    def test_un_club_repetido_en_una_temporada_es_un_error(self):
        e = pd.concat([self.eq, self.eq.iloc[[0]]], ignore_index=True)
        with self.assertRaises(ValueError):
            te.calcular(e)

    def test_la_diferencia_de_verano_compara_el_cierre_con_el_arranque_siguiente(self):
        # Man Utd: fin 1770 -> pre 1700 (70); fin 1740 -> pre 1800 (60). PSG: 1920 -> 1930 (10); 1950 -> 1960 (10).
        # Bayern: 1970 -> 1990 (20); 2010 -> 2000 (10). Burnley no tiene temporadas seguidas.
        mediana, maximo, pares = self.r["verano"]
        self.assertEqual(pares, 6)
        self.assertEqual(maximo, 70)
        self.assertEqual(mediana, 15)

    def test_el_payload_viaja_a_json_sin_nulos_raros(self):
        s = json.dumps(self.p, allow_nan=False)
        self.assertNotIn("NaN", s)
        self.assertEqual(self.p["maxClubes"], te.MAX_CLUBES)
        self.assertEqual(self.p["medida"], te.MEDIDA_INICIAL)

    def test_los_valores_viajan_con_un_decimal(self):
        e = self.eq.copy()
        e.loc[(e["Squad"] == "Bayern Munich") & (e["temporada"] == "2021-22"), "elo_medio"] = 1999.96
        e.loc[(e["Squad"] == "Bayern Munich") & (e["temporada"] == "2022-23"), "elo_medio"] = 1999.94
        c = {x["n"]: x for x in te.payload(te.calcular(e))["clubes"]}
        self.assertEqual(c["Bayern Múnich"]["med"][:2], [2000.0, 1999.9])

    def test_los_textos_salen_de_los_datos(self):
        mirar, porque = te.textos(self.r)
        for t in (mirar, porque):
            self.assertNotIn("nan", t.lower().replace("banan", ""))
            self.assertNotIn("{", t)
        self.assertIn("La vista llega hasta 2023-24: 2024-25 no tiene ELO todavía", mirar)
        self.assertIn("**La línea punteada**", mirar)
        self.assertIn("15 de julio", porque)
        self.assertIn("1 de junio", porque)
        self.assertIn("1 de agosto", porque)

    def test_el_conteo_de_clubes_completos_del_texto(self):
        mirar, _ = te.textos(self.r)
        # Man Utd, PSG y Bayern están las 3 temporadas con ELO; Burnley no.
        self.assertIn("3 de los 4 clubes están en las 3", mirar)

    def test_la_bajada_cabe_en_una_linea(self):
        self.assertLessEqual(len(te.BAJADA), 108)

    def test_las_fechas_del_texto_son_las_de_fetch_elo(self):
        try:
            import fetch_elo
        except ImportError:
            self.skipTest("fetch_elo necesita `requests`")
        pre, desde, fin = fetch_elo.ventana("2025-26")
        self.assertEqual((pre.month, pre.day), te.FECHA_PRE)
        self.assertEqual((desde.month, desde.day), te.FECHA_MEDIO_DESDE)
        self.assertEqual((fin.month, fin.day), te.FECHA_FIN)

    def test_la_vista_esta_registrada(self):
        import teams
        from preguntas import PREGUNTAS
        self.assertIn(te.SLUG, PREGUNTAS)
        self.assertIn((te.SLUG, "Trayectoria ELO", "Contexto"), teams.PESTANAS)

    def test_los_colores_alcanzan_para_todos_los_clubes_y_son_distintos(self):
        for modo in ("claro", "oscuro"):
            c = te.COLORES[modo]
            self.assertGreaterEqual(len(c), te.MAX_CLUBES)
            self.assertEqual(len(set(c)), len(c))


@unittest.skipUnless((PROCESADOS / "teams_all_seasons.csv").exists(), "faltan los datos procesados")
class DatosReales(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = te.calcular(te._cargar())
        cls.p = te.payload(cls.r)
        cls.club = {c["n"]: c for c in cls.p["clubes"]}

    def test_cinco_temporadas_con_ELO_y_2026_27_aparte(self):
        self.assertEqual(self.p["temporadas"], ["2021-22", "2022-23", "2023-24", "2024-25", "2025-26"])
        self.assertEqual(self.p["sinElo"], ["2026-27"])
        self.assertEqual(self.p["n"], [98, 98, 96, 96, 96])

    def test_no_hay_valores_vacios_donde_el_club_si_jugo(self):
        for c in self.p["clubes"]:
            for m in ("pre", "med", "fin"):
                self.assertEqual([v is None for v in c[m]], [v is None for v in c["med"]], c["n"])

    def test_los_grandes_salen_con_elo_alto_y_estable(self):
        for n in ("Manchester City", "Bayern Múnich", "Real Madrid"):
            med = self.club[n]["med"]
            self.assertTrue(all(v is not None and v > 1850 for v in med), (n, med))
            self.assertLess(max(med) - min(med), 160, n)
        for ref in self.p["ref"]["med"]:
            self.assertTrue(1650 < ref < 1750, ref)

    def test_un_colapso_conocido_se_ve(self):
        # El City llegó a 2024-25 con 2,050 y terminó en 1,960.
        c = self.club["Manchester City"]
        self.assertGreater(c["pre"][3] - c["fin"][3], 80)

    def test_un_club_que_desciende_y_vuelve_deja_hueco(self):
        b = self.club["Burnley"]
        self.assertIsNotNone(b["med"][0])
        self.assertIsNone(b["med"][1])
        self.assertIsNotNone(b["med"][2])

    def test_la_seleccion_inicial_tiene_un_club_por_liga(self):
        ligas = [self.p["ligas"][self.club[n]["l"]] for n in self.p["iniciales"]]
        self.assertEqual(sorted(ligas), sorted(self.p["ligas"]))

    def test_el_payload_es_chico(self):
        self.assertLess(len(json.dumps(self.p, separators=(",", ":"))), 30_000)

    def test_los_textos_se_arman_con_los_datos_reales(self):
        mirar, porque = te.textos(self.r)
        self.assertIn("96 a 98 clubes", mirar)
        self.assertIn("2026-27 no tiene ELO todavía", mirar)
        self.assertIn("331 pares", porque)


if __name__ == "__main__":
    unittest.main()
