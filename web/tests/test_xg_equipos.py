"""Test del xG de equipo por partido y sin penales (`web/charts/xg_equipos.py`).

    python -m unittest web/tests/test_xg_equipos.py      (desde la raíz del repo)

Dos partes. Las pruebas sintéticas comprueban las reglas (sin penales, sin autogoles, el cruce de nombres y
el rival que Understat deja vacío). Las de datos reales necesitan `data/processed/` y se saltan si no está:
que la suma del xG a favor de una liga y temporada sea igual a la del xG en contra, que los goles por
partido de cada liga estén donde se sabe, que un equipo grande tenga mucho más xG que uno chico y que cada
club de las 580 filas cruce con su tabla de FBref.
"""

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(RAIZ / "web"), str(RAIZ / "web" / "charts"), str(RAIZ / "code")]

import xg_equipos as xe  # noqa: E402

PROCESADOS = RAIZ / "data" / "processed"
COLS = ["xg_fav", "xg_con", "gol_fav", "gol_con", "xg_dif"]


def _tiro(game, fecha, team, rival, xg, situation="Open Play", result="Missed Shot", temporada="2025-26",
          liga="Premier League"):
    return dict(temporada=temporada, liga=liga, game_id=game, date=f"{fecha} 15:00:00", team=team, rival=rival,
                xg=xg, situation=situation, result=result)


def _equipos(filas):
    """filas: (Squad de FBref, partidos) de una misma liga y temporada."""
    return pd.DataFrame([dict(temporada="2025-26", liga="Premier League", Squad=s, **{xe.COL_PARTIDOS: mp})
                         for s, mp in filas])


class Sintetico(unittest.TestCase):
    def test_sin_penales_ni_autogoles_y_por_partido(self):
        tiros = pd.DataFrame([
            _tiro(1, "2026-01-01", "Arsenal", "Wolverhampton Wanderers", 0.30, result="Goal"),
            _tiro(1, "2026-01-01", "Arsenal", "Wolverhampton Wanderers", 0.10),
            _tiro(1, "2026-01-01", "Arsenal", "Wolverhampton Wanderers", 0.78, situation="Penalty", result="Goal"),
            _tiro(1, "2026-01-01", "Wolverhampton Wanderers", "Arsenal", 0.20, result="Goal"),
            _tiro(1, "2026-01-01", "Wolverhampton Wanderers", "Arsenal", 0.0, result="Own Goal"),
            _tiro(2, "2026-01-08", "Wolverhampton Wanderers", "Arsenal", 0.50),
            _tiro(2, "2026-01-08", "Arsenal", "Wolverhampton Wanderers", 0.40, result="Goal"),
        ])
        # "Wolves" (FBref) y "Wolverhampton Wanderers" (Understat) son el mismo club
        out = xe.agregar(tiros, _equipos([("Arsenal", 2), ("Wolves", 2)]))
        ars, wol = out.iloc[0], out.iloc[1]
        self.assertEqual(ars["xg_partidos"], 2)
        self.assertAlmostEqual(ars["xg_fav"], (0.30 + 0.10 + 0.40) / 2)       # sin el penal
        self.assertAlmostEqual(ars["xg_con"], (0.20 + 0.0 + 0.50) / 2)
        self.assertAlmostEqual(ars["gol_fav"], 2 / 2)                          # 2 goles de juego, sin el penal
        self.assertAlmostEqual(ars["gol_con"], 1 / 2)                          # sin el autogol
        self.assertAlmostEqual(wol["xg_fav"], ars["xg_con"])                   # lo que uno crea, el otro lo concede
        self.assertAlmostEqual(ars["xg_dif"], ars["xg_fav"] - ars["xg_con"])

    def test_club_sin_pareja_detiene(self):
        tiros = pd.DataFrame([_tiro(1, "2026-01-01", "Arsenal", "Chelsea", 0.1),
                              _tiro(1, "2026-01-01", "Chelsea", "Arsenal", 0.1)])
        with self.assertRaises(ValueError) as e:
            xe.agregar(tiros, _equipos([("Arsenal", 1), ("Fulham", 1)]))
        self.assertIn("Chelsea", str(e.exception))
        self.assertIn("Fulham", str(e.exception))

    def test_rival_vacio_se_deduce(self):
        # El partido 3 trae tiros solo de Arsenal. Chelsea no tiró y no figura como rival: le falta un partido
        # en los tiros respecto de sus 2 partidos, y no jugó otro ese día. Fulham jugó ese día en el partido 4.
        tiros = pd.DataFrame([
            _tiro(1, "2026-01-01", "Arsenal", "Fulham", 0.1), _tiro(1, "2026-01-01", "Fulham", "Arsenal", 0.1),
            _tiro(2, "2026-01-08", "Chelsea", "Brentford", 0.1), _tiro(2, "2026-01-08", "Brentford", "Chelsea", 0.1),
            _tiro(3, "2026-01-15", "Arsenal", None, 0.6),
            _tiro(4, "2026-01-15", "Fulham", "Brentford", 0.1), _tiro(4, "2026-01-15", "Brentford", "Fulham", 0.1),
        ])
        out = xe.agregar(tiros, _equipos([("Arsenal", 2), ("Chelsea", 2), ("Fulham", 2), ("Brentford", 2)]))
        chelsea = out.iloc[1]
        self.assertAlmostEqual(chelsea["xg_con"], (0.1 + 0.6) / 2)   # lo del partido 2 y el 0.6 del partido 3
        self.assertEqual(chelsea["xg_partidos"], 2)
        # con todo asignado, lo que se crea es lo que se concede en la liga
        total = lambda c: (out[c] * out["xg_partidos"]).sum()
        self.assertAlmostEqual(total("xg_fav"), total("xg_con"))

    def test_rival_vacio_ambiguo_detiene(self):
        # Ningún equipo con un partido de menos en los tiros: no hay a quién asignarlo
        tiros = pd.DataFrame([
            _tiro(1, "2026-01-01", "Arsenal", "Fulham", 0.1), _tiro(1, "2026-01-01", "Fulham", "Arsenal", 0.1),
            _tiro(2, "2026-01-08", "Arsenal", None, 0.6),
        ])
        with self.assertRaises(ValueError):
            xe.agregar(tiros, _equipos([("Arsenal", 2), ("Fulham", 1)]))


@unittest.skipUnless((PROCESADOS / "shots_all_seasons.csv").exists() and (PROCESADOS / "teams_all_seasons.csv").exists(),
                     "Faltan los CSV de data/processed/")
class DatosReales(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tiros = xe.cargar_tiros(PROCESADOS / "shots_all_seasons.csv")
        cls.equipos = pd.read_csv(PROCESADOS / "teams_all_seasons.csv")
        cls.xg = xe.agregar(cls.tiros, cls.equipos)
        cls.d = pd.concat([cls.equipos[["temporada", "liga", "Squad", xe.COL_PARTIDOS, "pt_Team Success_PPM",
                                        "nivel", "elo_pre"]], cls.xg], axis=1)
        cls.cerradas = cls.d[cls.d["temporada"] != "2026-27"]

    def test_580_filas_sin_nulos(self):
        self.assertEqual(len(self.xg), len(self.equipos))
        self.assertEqual(len(self.xg), 580)
        self.assertEqual(int(self.xg[COLS + ["xg_partidos"]].isna().sum().sum()), 0)
        self.assertTrue((self.xg["xg_partidos"] > 0).all())

    def test_ningun_tiro_sin_rival(self):
        t, _ = xe._con_rival(self.tiros, self.equipos)
        self.assertEqual(int(t["rival_v"].isna().sum()), 0)

    def test_lo_que_se_crea_es_lo_que_se_concede(self):
        """En cada liga y temporada, la suma del xG a favor de todos los equipos es la del xG en contra (lo
        mismo con los goles): cada tiro lo tira uno y lo recibe otro."""
        d = self.d
        for c_fav, c_con in (("xg_fav", "xg_con"), ("gol_fav", "gol_con")):
            tot = d.assign(f=d[c_fav] * d["xg_partidos"], c=d[c_con] * d["xg_partidos"]) \
                .groupby(["temporada", "liga"])[["f", "c"]].sum()
            self.assertLess(float((tot["f"] - tot["c"]).abs().max()), 1e-9, c_fav)

    def test_goles_por_partido_por_liga(self):
        """Los goles por partido de cada liga (con penales y autogoles, como se cuentan en la tabla) están donde
        se sabe (2.4 a 3.3 en las temporadas cerradas; la Premier 2023-24 fue de 3.28) y cerca de los de FBref."""
        t = self.tiros.assign(gol=self.tiros["result"].isin(["Goal", "Own Goal"]).astype(int))
        g = t.groupby(["temporada", "liga"]).agg(goles=("gol", "sum"), partidos=("game_id", "nunique"))
        g["por_partido"] = g["goles"] / g["partidos"]
        cerradas = g[g.index.get_level_values("temporada") != "2026-27"]
        self.assertTrue(cerradas["por_partido"].between(2.3, 3.4).all(), cerradas["por_partido"].round(2).to_dict())
        self.assertAlmostEqual(g.loc[("2023-24", "Premier League"), "por_partido"], 3.28, places=2)
        fb = self.equipos.groupby(["temporada", "liga"]).agg(
            goles=("ov_Performance_Gls", "sum"), mp=(xe.COL_PARTIDOS, "sum"))
        razon = g["por_partido"] / (fb["goles"] / (fb["mp"] / 2))
        # FBref no cuenta los autogoles en los de cada jugador: Understat sale un ~3% arriba, siempre
        self.assertTrue(razon.between(0.99, 1.08).all(), razon.round(3).to_dict())

    def test_xg_por_partido_es_razonable(self):
        c = self.cerradas
        por_liga = c.groupby(["temporada", "liga"])["xg_fav"].mean()
        self.assertTrue(por_liga.between(1.0, 1.9).all(), por_liga.round(2).to_dict())   # el xG de un equipo, por partido
        # Understat suma más xG que goles sin penales, en todas las temporadas cerradas
        for temporada, g in c.groupby("temporada"):
            razon = (g["gol_fav"] * g["xg_partidos"]).sum() / (g["xg_fav"] * g["xg_partidos"]).sum()
            self.assertTrue(0.80 < razon < 1.0, (temporada, razon))

    def test_grandes_contra_chicos(self):
        """Manchester City, Barcelona y Bayern crean mucho más xG que la mediana de su liga, en temporadas
        cerradas, y su diferencia de xG es claramente positiva. El último de cada liga, al revés."""
        d = self.d
        for club in ("Manchester City", "Barcelona", "Bayern Munich"):
            for temporada in ("2021-22", "2023-24", "2025-26"):
                f = d[(d["Squad"] == club) & (d["temporada"] == temporada)]
                self.assertEqual(len(f), 1, (club, temporada))
                f = f.iloc[0]
                liga = d[(d["liga"] == f["liga"]) & (d["temporada"] == temporada)]
                self.assertGreater(f["xg_fav"], liga["xg_fav"].median() + 0.4, (club, temporada))
                self.assertGreater(f["xg_fav"], liga["xg_fav"].min() + 0.8, (club, temporada))
                self.assertGreater(f["xg_dif"], 0.5, (club, temporada))
        c = self.cerradas
        top, resto = c[c["nivel"] == "Clubes top"], c[c["nivel"] != "Clubes top"]
        self.assertGreater(top["xg_dif"].mean() - resto["xg_dif"].mean(), 0.6)
        # y los puntos siguen a la diferencia de xG
        self.assertGreater(c["xg_dif"].corr(c["pt_Team Success_PPM"]), 0.85)

    def test_partidos_de_understat_contra_los_de_fbref(self):
        """Los partidos que Understat trae de cada equipo coinciden con los de FBref, salvo unos pocos equipos
        (a Understat le falta o le sobra un partido). Se imprimen para que no pasen en silencio."""
        dif = self.d["xg_partidos"] - self.d[xe.COL_PARTIDOS]
        distintos = self.d[dif != 0]
        print("\n  Partidos distintos entre Understat y FBref:",
              [(r.temporada, r.Squad, int(r[xe.COL_PARTIDOS]), int(r.xg_partidos)) for _, r in distintos.iterrows()])
        self.assertLessEqual(len(distintos), 10)
        self.assertTrue((dif.abs() <= 1).all())

    def test_psg_de_2026_27_cruza(self):
        """FBref pasó de «PSG» a «Paris SG» en 2026-27: tiene que cruzar igual con «Paris Saint Germain»."""
        f = self.d[(self.d["temporada"] == "2026-27") & (self.d["liga"] == "Ligue 1") & (self.d["Squad"] == "Paris SG")]
        self.assertEqual(len(f), 1)
        self.assertGreater(f.iloc[0]["xg_partidos"], 0)
        self.assertEqual(f.iloc[0]["xg_partidos"], f.iloc[0][xe.COL_PARTIDOS])

    def test_load_data_de_las_vistas(self):
        import teams
        df = teams.load_data()
        self.assertEqual(len(df), 580)
        for c in COLS + ["xg_partidos"]:
            self.assertEqual(int(df[c].isna().sum()), 0, c)
        # el ELO, sin tocar el consolidado: solo falta en 2026-27
        self.assertEqual(int(df.loc[df["temporada"] != "2026-27", "elo_pre"].isna().sum()), 0)
        for col, _, _, _ in teams.VARIABLES:
            self.assertIn(col, df.columns, col)
        # los nombres ya son los que se muestran
        self.assertIn("PSG", set(df["Squad"]))


if __name__ == "__main__":
    unittest.main()
