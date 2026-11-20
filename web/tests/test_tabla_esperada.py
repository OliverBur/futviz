"""Test de «Tabla real vs. esperada» (`web/charts/tabla_esperada.py`).

    python -m unittest web/tests/test_tabla_esperada.py      (desde la raíz del repo)

Dos partes. Las pruebas sintéticas comprueban el método con probabilidades que se calculan a mano (la
distribución de goles por tiros, el resultado de un partido, que el reparto de puntos suma bien), el orden de la
tabla, el cruce de nombres y los partidos que no cuadran. Las de datos reales necesitan `data/` y se saltan si no
está: correlación y error contra los puntos reales, que los campeones no queden lejos de su lugar, que la
suma de xPts se parezca a la de puntos y que la diferencia casi no se repita de un año al siguiente.
"""

import json
import re
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(RAIZ / "web"), str(RAIZ / "web" / "charts"), str(RAIZ / "code")]

import tabla_esperada as te  # noqa: E402

PROCESADOS = RAIZ / "data" / "processed"


def _partido(game, local, visita, gl, gv, xg_l=1.0, xg_v=1.0, temporada="2025-26", liga="Premier League"):
    return dict(game_id=game, temporada=temporada, liga=liga, local=local, visita=visita, goles_l=gl, goles_v=gv,
                xg_l=xg_l, xg_v=xg_v)


def _tiro(game, team, xg, result="Missed Shot", situation="Open Play"):
    return dict(game_id=game, team=team, xg=xg, result=result, situation=situation)


class Metodo(unittest.TestCase):
    def test_goles_por_tiros(self):
        np.testing.assert_allclose(te.pmf_goles([]), [1.0])
        np.testing.assert_allclose(te.pmf_goles([0.3]), [0.7, 0.3])
        np.testing.assert_allclose(te.pmf_goles([0.5, 0.5]), [0.25, 0.5, 0.25])
        # tres tiros distintos: la probabilidad de 0 goles es el producto de las que no entran
        p = te.pmf_goles([0.1, 0.2, 0.9])
        self.assertAlmostEqual(p[0], 0.9 * 0.8 * 0.1)
        self.assertAlmostEqual(p[3], 0.1 * 0.2 * 0.9)
        self.assertAlmostEqual(p.sum(), 1.0)
        # la media de goles es la suma del xG
        self.assertAlmostEqual(float(np.dot(np.arange(len(p)), p)), 0.1 + 0.2 + 0.9)

    def test_diez_ocasiones_chicas_no_son_una_grande(self):
        """Mismo xG total, distinta distribución: la de tiros no es la Poisson."""
        chicas = te.pmf_goles([0.09] * 10)
        una = te.pmf_goles([0.9])
        self.assertAlmostEqual(float(np.dot(np.arange(len(chicas)), chicas)), float(np.dot(np.arange(2), una)))
        self.assertGreater(chicas[1], una[1] - 0.9 + 0.1)        # varias chicas casi siempre dan algún gol
        self.assertAlmostEqual(una[0], 0.1)
        self.assertLess(chicas[0], 0.5)

    def test_poisson(self):
        p = te.pmf_poisson(1.5)
        self.assertAlmostEqual(p.sum(), 1.0)
        self.assertAlmostEqual(float(np.dot(np.arange(len(p)), p)), 1.5, places=6)
        self.assertAlmostEqual(p[0], np.exp(-1.5))
        # dos equipos iguales: ganar uno es ganar el otro
        w, d, l = te.probs_resultado(p, p)
        self.assertAlmostEqual(w, l)
        self.assertAlmostEqual(w + d + l, 1.0)

    def test_resultado_de_un_partido_con_probabilidades_conocidas(self):
        # local: 0 goles 0.7, 1 gol 0.3. visita: 0 goles 0.5, 1 gol 0.5.
        w, d, l = te.probs_resultado(te.pmf_goles([0.3]), te.pmf_goles([0.5]))
        self.assertAlmostEqual(w, 0.3 * 0.5)                     # 1-0
        self.assertAlmostEqual(d, 0.7 * 0.5 + 0.3 * 0.5)         # 0-0 y 1-1
        self.assertAlmostEqual(l, 0.7 * 0.5)                     # 0-1
        self.assertAlmostEqual(te.puntos_esperados(w, d), 3 * 0.15 + 0.5)
        self.assertAlmostEqual(te.puntos_esperados(l, d), 3 * 0.35 + 0.5)

    def test_cantidad_distinta_de_goles_por_lado(self):
        # un lado con más goles posibles que el otro (distinto largo de pmf)
        w, d, l = te.probs_resultado(te.pmf_goles([0.5, 0.5, 0.5]), te.pmf_goles([1.0]))
        self.assertAlmostEqual(w + d + l, 1.0)
        self.assertAlmostEqual(w, 0.5)                           # el local mete 2 o 3 goles
        self.assertAlmostEqual(d, 0.375)                         # el local mete exactamente 1
        self.assertAlmostEqual(l, 0.125)                         # la visita gana solo si el local no mete ninguno

    def test_el_reparto_suma_2_o_3_puntos(self):
        """En un partido los xPts de los dos equipos suman 2 + P(decisivo), y los puntos reales, 3 o 2."""
        for xl, xv in (([0.3, 0.1], [0.5]), ([0.9, 0.8, 0.7], [0.05] * 6), ([], [])):
            w, d, l = te.probs_resultado(te.pmf_goles(xl), te.pmf_goles(xv))
            suma = te.puntos_esperados(w, d) + te.puntos_esperados(l, d)
            self.assertAlmostEqual(suma, 3 * (w + l) + 2 * d)
            self.assertAlmostEqual(suma, 2 + (w + l))
        for a, b in ((2, 0), (0, 3), (1, 1), (0, 0)):
            self.assertEqual(te.puntos_de(a, b) + te.puntos_de(b, a), 2 if a == b else 3)


class Partidos(unittest.TestCase):
    def setUp(self):
        self.partidos = pd.DataFrame([
            _partido(1, "Arsenal", "Chelsea", 1, 0, 1.5, 0.5),
            _partido(2, "Chelsea", "Arsenal", 1, 1, 0.9, 0.9),
            _partido(3, "Arsenal", "Fulham", 0, 0, 1.2, 0.4),    # sin tiros: queda fuera
            _partido(4, "Fulham", "Chelsea", 2, 0, 0.8, 0.3),    # los tiros traen 1 gol y el marcador 2
        ])
        self.tiros = pd.DataFrame([
            _tiro(1, "Arsenal", 0.3, "Goal"), _tiro(1, "Arsenal", 0.1), _tiro(1, "Chelsea", 0.2),
            _tiro(2, "Chelsea", 0.78, "Goal", "Penalty"), _tiro(2, "Arsenal", 0.0, "Own Goal"),
            _tiro(4, "Fulham", 0.4, "Goal"), _tiro(4, "Chelsea", 0.1),
        ])

    def test_clasifica_los_partidos(self):
        j = te.calcular_partidos(self.partidos, self.tiros)
        self.assertEqual(list(j["game_id"]), [1, 2, 4])
        self.assertEqual(list(j["metodo"]), ["tiros", "tiros", "partido"])
        self.assertEqual([r.game_id for r in j.attrs["sin_tiros"]], [3])
        self.assertEqual([r.game_id for r in j.attrs["con_poisson"]], [4])
        # los tres resultados suman 1 por los dos métodos
        np.testing.assert_allclose(j["bw"] + j["bd"] + j["bl"], 1.0)
        np.testing.assert_allclose(j["qw"] + j["qd"] + j["ql"], 1.0)

    def test_xg_de_cada_lado_y_penal_y_autogol(self):
        j = te.calcular_partidos(self.partidos, self.tiros).set_index("game_id")
        self.assertAlmostEqual(j.loc[1, "xg_l"], 0.4)            # lo de Arsenal: 0.3 + 0.1
        self.assertAlmostEqual(j.loc[1, "xg_v"], 0.2)
        # el penal entra con su xG; el autogol (xG 0) no suma esperados
        self.assertAlmostEqual(j.loc[2, "xg_l"], 0.78)           # Chelsea es local en el partido 2
        self.assertAlmostEqual(j.loc[2, "xg_v"], 0.0)
        # cuando los tiros no cuadran con el marcador se usa el xG del partido
        self.assertAlmostEqual(j.loc[4, "xg_l"], 0.8)
        self.assertAlmostEqual(j.loc[4, "xg_v"], 0.3)

    def test_probabilidades_de_un_partido_de_tiros(self):
        j = te.calcular_partidos(self.partidos, self.tiros).set_index("game_id")
        # partido 1: Arsenal con tiros 0.3 y 0.1, Chelsea con uno de 0.2
        pl, pv = te.pmf_goles([0.3, 0.1]), te.pmf_goles([0.2])
        w, d, l = te.probs_resultado(pl, pv)
        self.assertAlmostEqual(j.loc[1, "bw"], w)
        self.assertAlmostEqual(j.loc[1, "bd"], d)
        # Poisson sobre el mismo xG total (0.4 contra 0.2)
        qw, qd, ql = te.probs_resultado(te.pmf_poisson(0.4), te.pmf_poisson(0.2))
        self.assertAlmostEqual(j.loc[1, "qw"], qw)
        self.assertAlmostEqual(j.loc[1, "ql"], ql)
        self.assertNotAlmostEqual(j.loc[1, "bw"], j.loc[1, "qw"], places=3)

    def test_tabla_puntos_orden_y_posiciones(self):
        # liga de 4 equipos con resultados inventados y xG que mandan a otro orden
        partidos = pd.DataFrame([
            _partido(1, "A", "B", 1, 0), _partido(2, "C", "D", 1, 0),
            _partido(3, "B", "C", 3, 0), _partido(4, "D", "A", 0, 0),
        ])
        tiros = pd.DataFrame([
            _tiro(1, "A", 0.1), _tiro(1, "B", 0.9), _tiro(2, "C", 0.1), _tiro(2, "D", 0.8),
            _tiro(3, "B", 0.7, "Goal"), _tiro(3, "B", 0.7, "Goal"), _tiro(3, "B", 0.7, "Goal"), _tiro(3, "C", 0.05),
            _tiro(4, "D", 0.3), _tiro(4, "A", 0.3),
        ])
        # los tiros del partido 1 y 2 traen 0 goles y el marcador 1: no cuadran y van por Poisson
        j = te.calcular_partidos(partidos, tiros)
        t = te.tabla_equipos(j).set_index("equipo")
        # puntos: A 3+1, B 0+3, C 3+0, D 0+1
        self.assertEqual(t.loc["A", "pts"], 4)
        self.assertEqual(t.loc["B", "pts"], 3)
        self.assertEqual(t.loc["C", "pts"], 3)
        self.assertEqual(t.loc["D", "pts"], 1)
        # B y C empatan en puntos: gana B por diferencia de goles (+2 contra −2)
        self.assertEqual({e: int(t.loc[e, "pos_real"]) for e in "ABCD"}, {"A": 1, "B": 2, "C": 3, "D": 4})
        # las dos posiciones son permutaciones de 1..n
        self.assertEqual(sorted(t["pos_real"]), [1, 2, 3, 4])
        self.assertEqual(sorted(t["pos_esp"]), [1, 2, 3, 4])
        # goles y xG a favor y en contra
        self.assertEqual((t.loc["B", "gf"], t.loc["B", "gc"]), (3, 1))
        # B: el xG del partido 1 (no cuadra: 1.0 por defecto) y los tres tiros de 0.7 del partido 3
        self.assertAlmostEqual(t.loc["B", "xgf"], 1.0 + 3 * 0.7)
        self.assertAlmostEqual(t.loc["B", "xgc"], 1.0 + 0.05)
        # el reparto: los xPts de toda la liga suman 2 por partido más la probabilidad de que sea decisivo
        esperado = float(2 * len(j) + (j["bw"] + j["bl"]).sum())
        self.assertAlmostEqual(float(t["xp"].sum()), esperado)
        self.assertAlmostEqual(float(t["xp_poisson"].sum()), float(2 * len(j) + (j["qw"] + j["ql"]).sum()))
        # y los puntos reales suman 3 por partido decidido y 2 por empate
        self.assertEqual(int(t["pts"].sum()), 3 * 3 + 2 * 1)

    def test_el_equipo_sin_el_partido_figura_con_uno_menos(self):
        j = te.calcular_partidos(self.partidos, self.tiros)
        t = te.tabla_equipos(j).set_index("equipo")
        self.assertEqual(int(t.loc["Fulham", "pj"]), 1)          # el partido sin tiros no entra
        self.assertEqual(int(t.loc["Arsenal", "pj"]), 2)
        self.assertEqual(int(t.loc["Chelsea", "pj"]), 3)


class Nombres(unittest.TestCase):
    def _tabla(self, nombres):
        return pd.DataFrame([dict(temporada="2025-26", liga="Premier League", equipo=n) for n in nombres])

    def _fbref(self, squads):
        return pd.DataFrame([dict(temporada="2025-26", liga="Premier League", Squad=s) for s in squads])

    def test_cruza_el_nombre_de_understat_con_el_de_fbref(self):
        # Wolverhampton Wanderers (Understat) y Wolves (FBref) son el mismo club tras `club_visible`
        tabla = self._tabla([te.club_visible("Wolverhampton Wanderers"), te.club_visible("Arsenal")])
        te.comprobar_nombres(tabla, self._fbref(["Wolves", "Arsenal"]))

    def test_un_club_sin_pareja_detiene(self):
        with self.assertRaises(ValueError) as e:
            te.comprobar_nombres(self._tabla(["Arsenal", "Chelsea"]), self._fbref(["Arsenal", "Fulham"]))
        self.assertIn("Chelsea", str(e.exception))
        self.assertIn("Fulham", str(e.exception))


class Persistencia(unittest.TestCase):
    def _tabla(self, residuos):
        """Cuatro temporadas cerradas de 20 equipos con el residuo (puntos − xPts) dado por `residuos(equipo, año)`."""
        filas = []
        for año in (2021, 2022, 2023, 2024):
            for e in range(20):
                xp = 50.0 + e
                filas.append(dict(temporada=f"{año}-{str(año + 1)[2:]}", liga="L", equipo=f"E{e}", pj=38,
                                  pts=xp + residuos(e, año), xp=xp, xp_poisson=xp))
        return pd.DataFrame(filas)

    def test_residuo_que_se_repite(self):
        cerradas = ["2021-22", "2022-23", "2023-24", "2024-25"]
        t = self._tabla(lambda e, a: (e % 7) - 3.0)
        r = te.persistencia(t, "xp", cerradas)
        self.assertAlmostEqual(r["r"], 1.0, places=6)
        self.assertEqual(r["n"], 60)
        self.assertEqual(r["transiciones"], 3)

    def test_residuo_que_no_se_repite(self):
        cerradas = ["2021-22", "2022-23", "2023-24", "2024-25"]
        rng = np.random.default_rng(7)
        ruido = {(e, a): rng.normal(0, 5) for e in range(20) for a in (2021, 2022, 2023, 2024)}
        r = te.persistencia(self._tabla(lambda e, a: ruido[(e, a)]), "xp", cerradas)
        self.assertLess(abs(r["r"]), 0.4)
        self.assertLess(r["lo"], r["r"])
        self.assertGreater(r["hi"], r["r"])

    def test_metricas_de_equipos(self):
        t = self._tabla(lambda e, a: 2.0 if e % 2 else -2.0)
        m = te.metricas_equipos(t, "xp", ["2021-22", "2022-23"])
        self.assertAlmostEqual(m["mae"], 2.0)
        self.assertGreater(m["corr_mediana"], 0.9)
        self.assertAlmostEqual(m["razon_media"], m["xp_total"] / m["pts_total"], places=6)


def _liga_sintetica():
    """Cuatro equipos, tres temporadas cerradas y una en curso con la mitad de los partidos: lo justo para correr
    `calcular` entera (validación y persistencia incluidas)."""
    rng = np.random.default_rng(3)
    equipos = ["Arsenal", "Chelsea", "Fulham", "Brentford"]
    partidos, tiros, g = [], [], 0
    for temporada, mitad in (("2022-23", False), ("2023-24", False), ("2024-25", False), ("2025-26", True)):
        pares = [(a, b) for a in equipos for b in equipos if a != b]
        for a, b in pares[: len(pares) // 2 if mitad else None]:
            g += 1
            gl, gv = int(rng.poisson(1.5)), int(rng.poisson(1.1))
            partidos.append(_partido(g, a, b, gl, gv, 1.4, 1.1, temporada=temporada))
            for equipo, n in ((a, gl), (b, gv)):
                for _ in range(n):
                    tiros.append(_tiro(g, equipo, 0.3, "Goal"))
                for _ in range(8):
                    tiros.append(_tiro(g, equipo, 0.1))
    fbref = pd.DataFrame([dict(temporada=t, liga="Premier League", Squad=e)
                          for t in ("2022-23", "2023-24", "2024-25", "2025-26") for e in equipos])
    return pd.DataFrame(partidos), pd.DataFrame(tiros), fbref


class Entera(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.partidos, cls.tiros, cls.fbref = _liga_sintetica()
        cls.r = te.calcular(cls.partidos, cls.tiros, cls.fbref, en_curso={"2025-26": 6})

    def test_marca_la_temporada_en_curso(self):
        self.assertEqual(self.r["en_curso"], {"2025-26": 6})
        self.assertEqual(self.r["cerradas"], ["2022-23", "2023-24", "2024-25"])
        # la validación solo cuenta las cerradas
        self.assertEqual(self.r["validacion"]["tiros"]["equipos"]["n_equipos"], 12)
        self.assertEqual(self.r["validacion"]["tiros"]["persistencia"]["n"], 8)

    def test_payload_en_columnas(self):
        p = te.payload(self.r)
        n = len(p["f"]["pts"])
        self.assertEqual(n, 16)
        for k, col in p["f"].items():
            self.assertEqual(len(col), n, k)
        self.assertEqual(p["ligas"], ["Premier League"])
        self.assertEqual(p["temporadas"], ["2022-23", "2023-24", "2024-25", "2025-26"])
        self.assertEqual(p["enCurso"], {"2025-26": 6})
        self.assertEqual(sorted(p["nombres"]), sorted(["Arsenal", "Chelsea", "Fulham", "Brentford"]))
        json.dumps(p, allow_nan=False)

    def test_los_textos_salen_de_los_datos(self):
        que, por = te.textos(self.r)
        self.assertIn("2025-26", por)
        self.assertIsNone(re.search(r"\bnan\b", por.lower()))
        self.assertNotIn("{", por)


@unittest.skipUnless((PROCESADOS / "shots_all_seasons.csv").exists() and (PROCESADOS / "teams_all_seasons.csv").exists()
                     and list((RAIZ / "data").glob("*/partidos.csv")), "Faltan los CSV de data/")
class DatosReales(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        partidos, tiros, fbref = te._cargar()
        cls.fbref = fbref
        cls.r = te.calcular(partidos, tiros, fbref)
        cls.t = cls.r["tabla"]
        cls.v = cls.r["validacion"]
        cls.cerradas = cls.t[cls.t["temporada"].isin(cls.r["cerradas"])]
        print("\n  Validación (temporadas cerradas):", json.dumps(
            {k: {kk: round(vv, 3) if isinstance(vv, float) else vv for kk, vv in cls.v[k]["equipos"].items()}
             for k in ("tiros", "poisson")}, ensure_ascii=False))
        print("  Persistencia:", {k: {kk: round(vv, 3) for kk, vv in cls.v[k]["persistencia"].items()} for k in ("tiros", "poisson")})
        print("  Partidos:", {k: cls.v["partidos"][k] for k in ("tiros", "poisson")})

    def test_580_equipos_temporada_con_su_liga(self):
        self.assertEqual(len(self.t), 580)
        self.assertEqual(self.r["en_curso"].keys(), {"2026-27"})
        self.assertEqual(int(self.t[te.COLUMNAS].isna().sum().sum()), 0)
        for (_, _), g in self.t.groupby(["temporada", "liga"]):
            self.assertEqual(sorted(g["pos_real"]), list(range(1, len(g) + 1)))
            self.assertEqual(sorted(g["pos_esp"]), list(range(1, len(g) + 1)))

    def test_los_puntos_son_los_de_fbref_salvo_unos_pocos_marcadores(self):
        """Los puntos de los marcadores de Understat coinciden con los de FBref (puntos por partido × partidos, redondeados) en
        todas las temporadas cerradas salvo en un puñado de equipos, por un punto casi siempre: el partido sin tiros (Bochum)
        y unos marcadores mal capturados en una de las dos fuentes. Se imprimen para que no pasen en silencio."""
        cuantos, maximo, n = self.r["discrepancias_fbref"]
        print("\n  Equipos-temporada cuyos puntos difieren de FBref:", cuantos, "de", n, "· diferencia máxima:", maximo)
        self.assertEqual(n, 484)
        self.assertLessEqual(cuantos, 8)
        self.assertLessEqual(maximo, 3)
        # a lo más un partido de diferencia entre los equipos de una misma liga y temporada (el que se quitó)
        for (_, _), g in self.cerradas.groupby(["temporada", "liga"]):
            self.assertLessEqual(int(g["pj"].max() - g["pj"].min()), 1)

    def test_correlacion_y_error_contra_los_puntos(self):
        e = self.v["tiros"]["equipos"]
        self.assertGreater(e["corr_min"], 0.8)
        self.assertGreater(e["corr_mediana"], 0.9)
        self.assertLess(e["mae"], 7.0)

    def test_la_suma_de_xpts_se_parece_a_la_de_puntos(self):
        """Los empates reparten 2 puntos y el xG predice menos empates de los que hay: los xPts suman un poco más."""
        e = self.v["tiros"]["equipos"]
        self.assertGreater(e["razon_min"], 0.98)
        self.assertLess(e["razon_max"], 1.05)
        p = self.v["partidos"]
        self.assertLess(p["tiros"]["empate"], p["real"]["empate"])

    def test_tiros_se_acercan_mas_que_poisson(self):
        self.assertLess(self.v["tiros"]["equipos"]["mae"], self.v["poisson"]["equipos"]["mae"])
        self.assertLess(self.v["partidos"]["tiros"]["rps"], self.v["partidos"]["poisson"]["rps"])

    def test_la_diferencia_casi_no_se_repite(self):
        p = self.v["tiros"]["persistencia"]
        self.assertEqual(p["transiciones"], 4)
        self.assertLess(abs(p["r"]), 0.2)
        self.assertGreater(p["r_xp_pts"], p["r_pts_pts"] - 0.01)    # los xPts de un año anticipan los puntos del siguiente tan bien como los puntos

    def test_los_campeones_no_estan_lejos_de_si_mismos(self):
        """El campeón de cada liga y temporada cerrada tiene xPts entre los tres primeros de su liga y no se aleja de ellos
        más que lo que se alejan los demás equipos."""
        c = self.cerradas
        camp = c[c["pos_real"] == 1]
        self.assertEqual(len(camp), 25)
        self.assertLessEqual(int(camp["pos_esp"].max()), 3)
        self.assertLess(float((camp["pts"] - camp["xp"]).abs().max()), 20)

    def test_sanidad_con_casos_conocidos(self):
        """Casos que se saben: Union Berlin 2022-23 (4.º con un xG de mitad de tabla), Real Madrid 2023-24 y Manchester
        United 2023-24 muy por encima de sus xPts; los últimos de cada liga, por debajo."""
        c = self.cerradas.assign(dif=lambda d: d["pts"] - d["xp"]).set_index(["temporada", "equipo"])
        self.assertGreater(c.loc[("2022-23", "Union Berlin"), "dif"], 12)
        self.assertGreater(c.loc[("2023-24", "Real Madrid"), "dif"], 12)
        self.assertGreater(c.loc[("2023-24", "Manchester United"), "dif"], 10)
        ultimos = self.cerradas[self.cerradas.groupby(["temporada", "liga"])["pos_real"].transform("max") == self.cerradas["pos_real"]]
        self.assertLess(float((ultimos["pts"] - ultimos["xp"]).mean()), 0)

    def test_payload_y_textos(self):
        p = te.payload(self.r)
        n = len(p["f"]["pts"])
        self.assertEqual(n, 580)
        for k, col in p["f"].items():
            self.assertEqual(len(col), n, k)
        self.assertEqual(p["ligas"], [l for l in te.LEAGUE_ORDER])
        self.assertLess(len(json.dumps(p)), 120_000)
        json.dumps(p, allow_nan=False)
        que, por = te.textos(self.r)
        for t in (que, por):
            self.assertIsNone(re.search(r"\bnan\b", t.lower()))
            self.assertNotIn("{", t)
        self.assertIn("2026-27", por)
        self.assertIn("Holstein Kiel", por)                        # el partido sin tiros sale del dato
        self.assertLessEqual(len(te.BAJADA), 108)


if __name__ == "__main__":
    unittest.main()
