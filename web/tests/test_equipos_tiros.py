"""Test de las columnas de tiros y de local/visitante por equipo (`web/charts/equipos_tiros.py`) y de las dos vistas que
las usan («Cantidad vs. calidad de los tiros» y «Local vs. visitante»).

    python -m unittest web/tests/test_equipos_tiros.py      (desde la raíz del repo)

Dos partes. Las pruebas sintéticas comprueban las reglas (sin penales ni autogoles, por partido, el cruce de nombres, el
partido sin tiros, el rival que Understat deja vacío y la sede sin partidos). Las de datos reales necesitan `data/` y se
saltan si no está: que cuadren con `xg_equipos`, que los equipos que se sabe estén donde se sabe y que los textos de las
dos vistas salgan de los datos.
"""

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(RAIZ / "web"), str(RAIZ / "web" / "charts"), str(RAIZ / "code")]

import equipos_tiros as et  # noqa: E402
import xg_equipos as xe  # noqa: E402

DATOS = RAIZ / "data"
PROCESADOS = DATOS / "processed"


def _tiro(game, fecha, team, rival, xg, situation="Open Play", result="Missed Shot", temporada="2025-26",
          liga="Premier League"):
    return dict(temporada=temporada, liga=liga, game_id=game, date=f"{fecha} 15:00:00", team=team, rival=rival,
                xg=xg, situation=situation, result=result)


def _equipos(filas):
    """filas: (Squad de FBref, partidos) de una misma liga y temporada."""
    return pd.DataFrame([dict(temporada="2025-26", liga="Premier League", Squad=s, **{xe.COL_PARTIDOS: mp})
                         for s, mp in filas])


def _partidos(filas):
    """filas: (game_id, fecha, local, visita) con los nombres de Understat."""
    return pd.DataFrame([dict(temporada="2025-26", liga="Premier League", game_id=g, fecha=f"{d} 15:00:00",
                              local=lo, visita=vi) for g, d, lo, vi in filas])


W = "Wolverhampton Wanderers"   # en FBref es "Wolves"


def _dos_equipos():
    """Arsenal y Wolves, dos partidos (uno en cada casa). Con un penal y un autogol que no deben contar."""
    tiros = pd.DataFrame([
        _tiro(1, "2026-01-01", "Arsenal", W, 0.30, result="Goal"),
        _tiro(1, "2026-01-01", "Arsenal", W, 0.10),
        _tiro(1, "2026-01-01", "Arsenal", W, 0.78, situation="Penalty", result="Goal"),
        _tiro(1, "2026-01-01", W, "Arsenal", 0.20, result="Goal"),
        _tiro(1, "2026-01-01", W, "Arsenal", 0.0, result="Own Goal"),
        _tiro(2, "2026-01-08", W, "Arsenal", 0.50),
        _tiro(2, "2026-01-08", "Arsenal", W, 0.40, result="Goal"),
    ])
    partidos = _partidos([(1, "2026-01-01", "Arsenal", W), (2, "2026-01-08", W, "Arsenal")])
    return tiros, _equipos([("Arsenal", 2), ("Wolves", 2)]), partidos


class Sintetico(unittest.TestCase):
    def test_tiros_por_partido_y_xg_por_tiro_sin_penales_ni_autogoles(self):
        out = et.agregar(*_dos_equipos())
        ars, wol = out.iloc[0], out.iloc[1]
        # Arsenal: 3 tiros (0.30, 0.10 y 0.40; el penal no cuenta) en 2 partidos
        self.assertAlmostEqual(ars["tiros_pp"], 3 / 2)
        self.assertAlmostEqual(ars["xg_tiro"], 0.80 / 3)
        # Wolves: 2 tiros (0.20 y 0.50; el autogol no es un tiro)
        self.assertAlmostEqual(wol["tiros_pp"], 2 / 2)
        self.assertAlmostEqual(wol["xg_tiro"], 0.70 / 2)

    def test_multiplicados_dan_el_xg_a_favor_por_partido(self):
        tiros, equipos, partidos = _dos_equipos()
        out, xg = et.agregar(tiros, equipos, partidos), xe.agregar(tiros, equipos)
        self.assertTrue(np.allclose(out["tiros_pp"] * out["xg_tiro"], xg["xg_fav"]))

    def test_local_y_visitante(self):
        out = et.agregar(*_dos_equipos())
        ars, wol = out.iloc[0], out.iloc[1]
        # Arsenal de local (partido 1): 0.40 a favor y 0.20 en contra; de visitante (partido 2): 0.40 y 0.50
        self.assertAlmostEqual(ars["xg_dif_local"], 0.40 - 0.20)
        self.assertAlmostEqual(ars["xg_dif_visita"], 0.40 - 0.50)
        self.assertAlmostEqual(wol["xg_dif_local"], 0.50 - 0.40)
        self.assertAlmostEqual(wol["xg_dif_visita"], 0.20 - 0.40)
        self.assertEqual((ars["partidos_local"], ars["partidos_visita"]), (1, 1))
        # lo que uno gana de local es lo que el otro pierde de visitante
        self.assertAlmostEqual(ars["xg_dif_local"], -wol["xg_dif_visita"])
        self.assertAlmostEqual(wol["xg_dif_local"], -ars["xg_dif_visita"])

    def test_el_promedio_de_las_dos_sedes_es_la_diferencia_de_xg(self):
        tiros, equipos, partidos = _dos_equipos()
        out, xg = et.agregar(tiros, equipos, partidos), xe.agregar(tiros, equipos)
        n = out["partidos_local"] + out["partidos_visita"]
        pond = (out["xg_dif_local"] * out["partidos_local"] + out["xg_dif_visita"] * out["partidos_visita"]) / n
        self.assertTrue(np.allclose(pond, xg["xg_dif"]))

    def test_cruce_de_nombres(self):
        # "Wolves" (FBref) y "Wolverhampton Wanderers" (Understat, en los tiros y en los partidos) son el mismo club
        out = et.agregar(*_dos_equipos())
        self.assertFalse(out[et.COLUMNAS].isna().any().any())

    def test_partidos_con_un_club_sin_pareja_detiene(self):
        tiros, equipos, _ = _dos_equipos()
        partidos = _partidos([(1, "2026-01-01", "Arsenal", "Chelsea"), (2, "2026-01-08", "Chelsea", "Arsenal")])
        with self.assertRaises(ValueError) as e:
            et.agregar(tiros, equipos, partidos)
        self.assertIn("Chelsea", str(e.exception))
        self.assertIn("Wolves", str(e.exception))

    def test_partido_sin_ningun_tiro_no_cuenta_ni_como_cero(self):
        # El partido 3 está en partidos.csv pero Understat no trae ni un tiro: no hay dato, no un 0
        tiros, _, partidos = _dos_equipos()
        partidos = pd.concat([partidos, _partidos([(3, "2026-01-15", "Arsenal", W)])], ignore_index=True)
        out = et.agregar(tiros, _equipos([("Arsenal", 3), ("Wolves", 3)]), partidos)
        ars = out.iloc[0]
        self.assertEqual(ars["partidos_local"], 1)                       # solo el partido 1
        self.assertAlmostEqual(ars["xg_dif_local"], 0.40 - 0.20)         # sin un 0 del partido 3 promediado
        self.assertAlmostEqual(ars["tiros_pp"], 3 / 2)                   # el partido 3 tampoco entra al denominador

    def test_rival_vacio_el_otro_equipo_queda_en_cero_en_ese_partido(self):
        # El partido 3 trae tiros solo de Arsenal (Chelsea no tiró) y sin rival. Mismo caso que en test_xg_equipos.
        tiros = pd.DataFrame([
            _tiro(1, "2026-01-01", "Arsenal", "Fulham", 0.1), _tiro(1, "2026-01-01", "Fulham", "Arsenal", 0.1),
            _tiro(2, "2026-01-08", "Chelsea", "Brentford", 0.1), _tiro(2, "2026-01-08", "Brentford", "Chelsea", 0.1),
            _tiro(3, "2026-01-15", "Arsenal", None, 0.6),
            _tiro(4, "2026-01-15", "Fulham", "Brentford", 0.1), _tiro(4, "2026-01-15", "Brentford", "Fulham", 0.1),
        ])
        equipos = _equipos([("Arsenal", 2), ("Chelsea", 2), ("Fulham", 2), ("Brentford", 2)])
        partidos = _partidos([(1, "2026-01-01", "Arsenal", "Fulham"), (2, "2026-01-08", "Chelsea", "Brentford"),
                              (3, "2026-01-15", "Arsenal", "Chelsea"), (4, "2026-01-15", "Fulham", "Brentford")])
        out = et.agregar(tiros, equipos, partidos)
        ars, che = out.iloc[0], out.iloc[1]
        self.assertAlmostEqual(ars["xg_dif_local"], ((0.1 - 0.1) + (0.6 - 0.0)) / 2)
        self.assertEqual(che["partidos_visita"], 1)
        self.assertAlmostEqual(che["xg_dif_visita"], 0.0 - 0.6)          # Chelsea no tiró y recibió 0.6
        self.assertEqual(che["tiros_pp"], 1 / 2)                          # un tiro en dos partidos
        xg = xe.agregar(tiros, equipos)
        self.assertTrue(np.allclose(out["tiros_pp"] * out["xg_tiro"], xg["xg_fav"]))

    def test_sede_sin_partidos_queda_sin_dato(self):
        # Wolves solo jugó de visitante (como una temporada en curso): su diferencia de local queda en NaN, no en 0
        tiros = pd.DataFrame([_tiro(1, "2026-01-01", "Arsenal", W, 0.30), _tiro(1, "2026-01-01", W, "Arsenal", 0.20)])
        out = et.agregar(tiros, _equipos([("Arsenal", 1), ("Wolves", 1)]), _partidos([(1, "2026-01-01", "Arsenal", W)]))
        ars, wol = out.iloc[0], out.iloc[1]
        self.assertTrue(np.isnan(wol["xg_dif_local"]))
        self.assertTrue(np.isnan(ars["xg_dif_visita"]))
        self.assertAlmostEqual(wol["xg_dif_visita"], 0.20 - 0.30)
        self.assertEqual(wol["partidos_local"] if not np.isnan(wol["partidos_local"]) else 0, 0)

    def test_equipo_sin_tiros_deja_xg_por_tiro_sin_dato(self):
        # Un equipo con solo un penal: cero tiros sin penales, así que su xG por tiro no existe (no es 0)
        tiros = pd.DataFrame([_tiro(1, "2026-01-01", "Arsenal", W, 0.30),
                              _tiro(1, "2026-01-01", W, "Arsenal", 0.78, situation="Penalty", result="Goal")])
        out = et.agregar(tiros, _equipos([("Arsenal", 1), ("Wolves", 1)]), _partidos([(1, "2026-01-01", "Arsenal", W)]))
        self.assertEqual(out.iloc[1]["tiros_pp"], 0.0)
        self.assertTrue(np.isnan(out.iloc[1]["xg_tiro"]))


@unittest.skipUnless((PROCESADOS / "shots_all_seasons.csv").exists() and (PROCESADOS / "teams_all_seasons.csv").exists()
                     and (DATOS / "2025-26" / "partidos.csv").exists(), "Faltan los CSV de data/")
class DatosReales(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tiros = xe.cargar_tiros(PROCESADOS / "shots_all_seasons.csv")
        cls.equipos = pd.read_csv(PROCESADOS / "teams_all_seasons.csv")
        partidos = et.cargar_partidos(DATOS, sorted(cls.equipos["temporada"].unique()))
        cls.xg = xe.agregar(cls.tiros, cls.equipos)
        cls.nuevo = et.agregar(cls.tiros, cls.equipos, partidos)
        cls.d = pd.concat([cls.equipos[["temporada", "liga", "Squad", xe.COL_PARTIDOS]], cls.xg, cls.nuevo], axis=1)
        cls.cerradas = cls.d[cls.d["temporada"] != "2026-27"]

    def test_580_filas_sin_nulos(self):
        self.assertEqual(len(self.nuevo), 580)
        self.assertEqual(int(self.nuevo[et.COLUMNAS + et.EXTRAS].isna().sum().sum()), 0)

    def test_cuadra_con_xg_equipos(self):
        d = self.d
        self.assertLess(float((d["tiros_pp"] * d["xg_tiro"] - d["xg_fav"]).abs().max()), 1e-9)
        n = d["partidos_local"] + d["partidos_visita"]
        self.assertTrue((n == d["xg_partidos"]).all())
        pond = (d["xg_dif_local"] * d["partidos_local"] + d["xg_dif_visita"] * d["partidos_visita"]) / n
        self.assertLess(float((pond - d["xg_dif"]).abs().max()), 1e-9)

    def test_lo_que_se_gana_de_local_se_pierde_de_visitante(self):
        """En cada liga y temporada, la suma de las diferencias de local (por partido jugado) es la de las de visitante con
        el signo cambiado: cada partido lo gana en xG uno de local y lo pierde el otro de visitante."""
        d = self.d
        loc = (d["xg_dif_local"] * d["partidos_local"]).groupby([d["temporada"], d["liga"]]).sum()
        vis = (d["xg_dif_visita"] * d["partidos_visita"]).groupby([d["temporada"], d["liga"]]).sum()
        self.assertLess(float((loc + vis).abs().max()), 1e-9)

    def test_quien_tira_mucho_y_quien_tira_bien(self):
        """Los que más tiran por partido en cada temporada cerrada son los de siempre, y los de más xG por tiro
        incluyen a equipos de élite (PSG, Barcelona, Bayern). El Bayern es de los tres que más tiran en las cinco."""
        c = self.cerradas
        grandes = {"Bayern Munich", "Liverpool", "Manchester City", "Real Madrid", "Barcelona", "PSG", "Inter",
                   "Napoli", "Arsenal"}
        for t, g in c.groupby("temporada"):
            top3 = set(g.nlargest(3, "tiros_pp")["Squad"])
            self.assertTrue(top3 <= grandes, (t, top3))
            self.assertIn("Bayern Munich", set(g.nlargest(3, "tiros_pp")["Squad"]), t)
        elite = set(c.groupby("temporada").apply(lambda g: list(g.nlargest(2, "xg_tiro")["Squad"])).sum())
        self.assertTrue({"PSG", "Barcelona", "Bayern Munich"} & elite, elite)
        # y el rango es el de un tiro: de 0.07 a 0.17 de xG, de 8 a 25 tiros por partido
        self.assertTrue(c["xg_tiro"].between(0.06, 0.18).all())
        self.assertTrue(c["tiros_pp"].between(8, 25).all())

    def test_jugar_en_casa_ayuda_a_casi_todos(self):
        c = self.cerradas
        self.assertAlmostEqual(c["xg_dif_local"].mean(), -c["xg_dif_visita"].mean(), places=2)
        self.assertGreater(c["xg_dif_local"].mean() - c["xg_dif_visita"].mean(), 0.4)
        self.assertGreater((c["xg_dif_local"] > c["xg_dif_visita"]).mean(), 0.85)
        self.assertGreater(c["xg_dif_local"].corr(c["xg_dif_visita"]), 0.6)   # buenos de local son buenos de visitante

    def test_el_efecto_estadio_casi_no_se_repite(self):
        """Lo que dice «Por qué estas variables» de Local vs. visitante: la diferencia local − visitante de un mismo equipo
        correlaciona poco entre dos temporadas cerradas seguidas (mucho menos que el volumen de tiros)."""
        import insights as ins
        d = self.d.copy()
        efecto = ins._persistencia_equipos(d, d["xg_dif_local"] - d["xg_dif_visita"])
        tiros = ins._persistencia_equipos(d, d["tiros_pp"])
        self.assertLess(max(abs(efecto[0]), abs(efecto[1])), 0.3)
        self.assertGreater(min(tiros[0], tiros[1]), 0.5)
        # y con los puntos esperados, que son los que dibuja la vista: lo que dice «Cómo leer» («casi no se repite»)
        import teams
        df = teams.load_data()
        xp = ins._persistencia_equipos(df, df["xp_local_pp"] - df["xp_visita_pp"])
        self.assertLess(max(abs(xp[0]), abs(xp[1])), 0.3)

    def test_load_data_y_las_dos_vistas(self):
        import teams
        df = teams.load_data()
        self.assertEqual(len(df), 580)
        columnas = {c for c, *_ in teams.VARIABLES}
        for c in et.COLUMNAS:
            self.assertIn(c, columnas)
            self.assertIn(c, teams.EXACTAS)
            self.assertEqual(int(df[c].isna().sum()), 0, c)
        for crear in (teams.chart_shots_quantity_quality, teams.chart_home_away):
            pag = crear(df)
            self.assertLessEqual(len(pag.subtitle), 108, pag.slug)       # la bajada cabe en una línea en escritorio
            self.assertIn(pag.slug, {s for s, *_ in teams.PESTANAS})
        for c in ("xp_local_pp", "xp_visita_pp", "pts_local_pp", "pts_visita_pp"):
            self.assertIn(c, columnas)
            self.assertEqual(int(df[c].isna().sum()), 0, c)
            self.assertTrue(df[c].between(0, 3).all(), c)       # puntos por partido: de 0 a 3
        grupos = {s: g for s, _, g in teams.PESTANAS}
        self.assertEqual(grupos["cantidad-calidad"], "Ocasiones")
        self.assertEqual(grupos["local-visitante"], "Contexto")

    def test_los_textos_salen_de_los_datos(self):
        import insights as ins
        import teams
        df = teams.load_data()
        c = ins._cerradas_eq(df)
        por_que = ins.cantidad_calidad_por_que(df)
        self.assertIn(f"{ins._fmt(c['tiros_pp'].corr(c['xg_tiro']))}", por_que)
        self.assertIn(f"{ins.miles(len(c))} equipos-temporada cerrados", por_que)
        self.assertIn("Understat suma más de lo que entra", por_que)
        self.assertIn("6 a 9 partidos", por_que)
        lv = ins.local_visitante_por_que(df)
        self.assertIn(ins._fmt(c["xp_local_pp"].corr(c["xp_visita_pp"])), lv)
        self.assertIn("Casi nada se repite", lv)
        self.assertIn("un accidente de la temporada", lv)
        self.assertIn("6 a 9 partidos", lv)
        self.assertIn("poca muestra", lv)
        for texto in (por_que, lv, ins.cantidad_calidad_que_mirar(), ins.local_visitante_que_mirar()):
            self.assertNotIn("jugadores", texto)
            self.assertNotIn("vos ", texto)


if __name__ == "__main__":
    unittest.main()
