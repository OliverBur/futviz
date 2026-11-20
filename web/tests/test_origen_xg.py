"""Test de «De dónde sale el xG» (`web/charts/origen_xg.py`).

    python -m unittest web/tests/test_origen_xg.py      (desde la raíz del repo)

Dos partes. Las pruebas sintéticas comprueban las reglas: los cuatro segmentos suman el xG total, los penales y
los autogoles quedan fuera, «en contra» cuenta por el rival, el rival vacío se deduce, los nombres de Understat y
de FBref se cruzan, los porcentajes suman 100 y la repetición entre temporadas se calcula sobre las cerradas. Las
de datos reales necesitan `data/processed/` y se saltan si no está: que la suma de los segmentos sea el `xg_fav`
de `xg_equipos.py` en las 580 filas, que el balón parado esté donde se sabe y que la vista se arme.
"""

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(RAIZ / "web"), str(RAIZ / "web" / "charts"), str(RAIZ / "code")]

import origen_xg as ox  # noqa: E402
import xg_equipos as xe  # noqa: E402

PROCESADOS = RAIZ / "data" / "processed"


def _tiro(game, fecha, team, rival, xg, situation="Open Play", result="Missed Shot", temporada="2025-26",
          liga="Premier League"):
    return dict(temporada=temporada, liga=liga, game_id=game, date=f"{fecha} 15:00:00", team=team, rival=rival,
                xg=xg, situation=situation, result=result)


def _equipos(filas, temporada="2025-26"):
    """filas: (Squad de FBref, partidos) de una misma liga y temporada."""
    return pd.DataFrame([dict(temporada=temporada, liga="Premier League", Squad=s, **{xe.COL_PARTIDOS: mp})
                         for s, mp in filas])


def _partido():
    """Un partido Arsenal-Wolves (Understat escribe «Wolverhampton Wanderers») con un tiro de cada tipo."""
    return pd.DataFrame([
        _tiro(1, "2026-01-01", "Arsenal", "Wolverhampton Wanderers", 0.10),
        _tiro(1, "2026-01-01", "Arsenal", "Wolverhampton Wanderers", 0.20, situation="From Corner"),
        _tiro(1, "2026-01-01", "Arsenal", "Wolverhampton Wanderers", 0.05, situation="Direct Freekick"),
        _tiro(1, "2026-01-01", "Arsenal", "Wolverhampton Wanderers", 0.03, situation="Set Piece"),
        _tiro(1, "2026-01-01", "Arsenal", "Wolverhampton Wanderers", 0.78, situation="Penalty", result="Goal"),
        _tiro(1, "2026-01-01", "Wolverhampton Wanderers", "Arsenal", 0.40, situation="From Corner", result="Goal"),
        _tiro(1, "2026-01-01", "Wolverhampton Wanderers", "Arsenal", 0.07),
        _tiro(1, "2026-01-01", "Wolverhampton Wanderers", "Arsenal", 0.0, result="Own Goal"),
    ])


class Sintetico(unittest.TestCase):
    def setUp(self):
        self.tabla = ox.por_segmento(_partido(), _equipos([("Arsenal", 1), ("Wolves", 1)]))
        self.ars, self.wol = self.tabla.iloc[0], self.tabla.iloc[1]

    def test_cruza_los_nombres_y_deja_el_nombre_visible(self):
        self.assertEqual(list(self.tabla["equipo"]), ["Arsenal", "Wolves"])
        self.assertEqual(list(self.tabla["partidos"]), [1, 1])

    def test_cada_segmento_a_favor(self):
        self.assertAlmostEqual(self.ars["xf_abierta"], 0.10)
        self.assertAlmostEqual(self.ars["xf_corner"], 0.20)
        self.assertAlmostEqual(self.ars["xf_libre"], 0.05)
        self.assertAlmostEqual(self.ars["xf_otro"], 0.03)
        self.assertEqual([self.ars[f"tf_{s}"] for s in ox.IDS], [1, 1, 1, 1])

    def test_los_penales_no_cuentan_ni_en_xg_ni_en_tiros(self):
        self.assertAlmostEqual(ox.total(self.tabla, "f")[0], 0.10 + 0.20 + 0.05 + 0.03)
        self.assertEqual(sum(self.ars[f"tf_{s}"] for s in ox.IDS), 4)
        self.assertEqual(sum(self.ars[f"tc_{s}"] for s in ox.IDS), 2)   # los de Wolves: sin el autogol

    def test_el_autogol_no_es_un_tiro(self):
        self.assertEqual(sum(self.wol[f"tf_{s}"] for s in ox.IDS), 2)
        self.assertAlmostEqual(ox.total(self.tabla, "f")[1], 0.47)

    def test_en_contra_usa_el_rival(self):
        # el córner de Wolves (0.40) es xG EN CONTRA de Arsenal, y el de Arsenal (0.20), en contra de Wolves
        self.assertAlmostEqual(self.ars["xc_corner"], 0.40)
        self.assertAlmostEqual(self.ars["xc_abierta"], 0.07)
        self.assertAlmostEqual(self.wol["xc_corner"], 0.20)
        self.assertAlmostEqual(self.wol["xc_libre"], 0.05)
        self.assertEqual(self.ars["tc_corner"], 1)
        self.assertEqual(self.wol["tc_corner"], 1)

    def test_lo_que_uno_hace_el_otro_lo_recibe_en_cada_segmento(self):
        for s in ox.IDS:
            self.assertAlmostEqual(self.tabla[f"xf_{s}"].sum(), self.tabla[f"xc_{s}"].sum())
            self.assertEqual(self.tabla[f"tf_{s}"].sum(), self.tabla[f"tc_{s}"].sum())

    def test_los_segmentos_suman_lo_mismo_que_xg_equipos(self):
        base = xe.agregar(_partido(), _equipos([("Arsenal", 1), ("Wolves", 1)]))
        for lado, col in (("f", "xg_fav"), ("c", "xg_con")):
            np.testing.assert_allclose(ox.total(self.tabla, lado) / self.tabla["partidos"], base[col].to_numpy())

    def test_los_porcentajes_suman_100(self):
        for lado in ("f", "c"):
            p = ox.participacion(self.tabla, lado)
            np.testing.assert_allclose(p.sum(axis=1), 1.0)
            self.assertEqual(list(p.columns), ox.IDS)
        p = ox.participacion(self.tabla, "f")
        self.assertAlmostEqual(p.loc[0, "corner"], 0.20 / 0.38)

    def test_el_peso_de_balon_parado_es_la_suma_de_los_tres(self):
        self.assertAlmostEqual(ox.peso_balon_parado(self.tabla, "f")[0], (0.20 + 0.05 + 0.03) / 0.38)

    def test_situacion_desconocida_detiene(self):
        t = _partido()
        t.loc[0, "situation"] = "ThrowinSetPiece"
        with self.assertRaises(ValueError) as e:
            ox.por_segmento(t, _equipos([("Arsenal", 1), ("Wolves", 1)]))
        self.assertIn("ThrowinSetPiece", str(e.exception))

    def test_club_sin_pareja_detiene(self):
        with self.assertRaises(ValueError):
            ox.por_segmento(_partido(), _equipos([("Arsenal", 1), ("Fulham", 1)]))

    def test_partido_sin_rival_se_deduce(self):
        # El partido 3 trae tiros solo de Arsenal (un córner de 0.6). Chelsea no tiró y no figura como rival: le
        # falta un partido en los tiros y no jugó otro ese día, así que es el rival (ver `xg_equipos`).
        tiros = pd.DataFrame([
            _tiro(1, "2026-01-01", "Arsenal", "Fulham", 0.1), _tiro(1, "2026-01-01", "Fulham", "Arsenal", 0.1),
            _tiro(2, "2026-01-08", "Chelsea", "Brentford", 0.1), _tiro(2, "2026-01-08", "Brentford", "Chelsea", 0.1),
            _tiro(3, "2026-01-15", "Arsenal", None, 0.6, situation="From Corner"),
            _tiro(4, "2026-01-15", "Fulham", "Brentford", 0.1), _tiro(4, "2026-01-15", "Brentford", "Fulham", 0.1),
        ])
        t = ox.por_segmento(tiros, _equipos([("Arsenal", 2), ("Chelsea", 2), ("Fulham", 2), ("Brentford", 2)]))
        chelsea = t[t["equipo"] == "Chelsea"].iloc[0]
        self.assertAlmostEqual(chelsea["xc_corner"], 0.6)
        self.assertEqual(chelsea["tc_corner"], 1)
        self.assertEqual(chelsea["partidos"], 2)
        for s in ox.IDS:
            self.assertAlmostEqual(t[f"xf_{s}"].sum(), t[f"xc_{s}"].sum())

    def test_el_payload_es_una_fila_por_equipo_temporada(self):
        r = ox.calcular(_partido(), _equipos([("Arsenal", 1), ("Wolves", 1)]), en_curso=[])
        p = ox.payload(r)
        self.assertEqual(p["n"], 2)
        self.assertEqual(len(p["c"]["pj"]), 2)
        self.assertEqual(len(p["c"]["xf_corner"]), 2)
        self.assertEqual(p["nombres"][p["f"]["j"][0]], "Arsenal")
        self.assertEqual(p["ligas"][p["f"]["l"][0]], "Premier League")
        self.assertEqual(p["temporadas"][p["f"]["t"][0]], "2025-26")


class Repeticion(unittest.TestCase):
    def _tabla(self, pesos):
        """Una tabla mínima: `pesos` {temporada: {equipo: (corner a favor, jugada abierta a favor)}}."""
        filas = []
        for t, equipos in pesos.items():
            for e, (corner, abierta) in equipos.items():
                f = dict(temporada=t, liga="Premier League", equipo=e, partidos=10)
                for p in ("xf", "xc"):
                    for s in ox.IDS:
                        f[f"{p}_{s}"] = 0.0
                f["xf_corner"], f["xf_abierta"], f["xc_corner"], f["xc_abierta"] = corner, abierta, corner, abierta
                filas.append(f)
        return pd.DataFrame(filas)

    def test_dos_temporadas_iguales_correlacionan_uno_y_la_en_curso_no_entra(self):
        clubes = {f"C{i}": (1 + i % 7, 10 + i % 5) for i in range(40)}
        # Con distinto reparto cada temporada de las cerradas no habría r = 1; con la en curso al revés sí
        tabla = self._tabla({"2024-25": clubes, "2025-26": clubes,
                             "2026-27": {c: (v[1], v[0]) for c, v in clubes.items()}})
        rep = ox.repeticion(tabla, en_curso=["2026-27"])
        self.assertAlmostEqual(rep["bp_f"]["min"], 1.0)
        self.assertEqual(rep["bp_f"]["n"], 40)
        self.assertEqual(rep["bp_f"]["n_min"], 40)
        # incluyendo la en curso baja
        self.assertLess(ox.repeticion(tabla)["bp_f"]["min"], 0.99)

    def test_un_par_con_pocos_equipos_en_comun_no_cuenta(self):
        tabla = self._tabla({"2024-25": {f"C{i}": (1 + i, 10) for i in range(10)},
                             "2025-26": {f"C{i}": (1 + i, 10) for i in range(10)}})
        self.assertIsNone(ox.repeticion(tabla)["bp_f"])

    def test_las_bandas_de_se_repite(self):
        p = lambda lo, hi: dict(min=lo, max=hi)
        self.assertEqual(ox._se_repite(p(0.1, 0.2)), "Casi nada se repite.")
        self.assertEqual(ox._se_repite(p(0.29, 0.43)), "Se repite en parte.")
        self.assertEqual(ox._se_repite(p(0.7, 0.8)), "Se repite bastante.")


@unittest.skipUnless((PROCESADOS / "shots_all_seasons.csv").exists() and (PROCESADOS / "teams_all_seasons.csv").exists(),
                     "Faltan los CSV de data/processed/")
class DatosReales(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tiros, cls.equipos = ox._cargar()
        cls.r = ox.calcular(cls.tiros, cls.equipos, en_curso=["2026-27"])
        cls.t = cls.r["tabla"]
        cls.cerradas = cls.t[cls.t["temporada"] != "2026-27"]

    def test_580_filas_sin_nulos(self):
        self.assertEqual(len(self.t), 580)
        self.assertEqual(int(self.t.isna().sum().sum()), 0)
        self.assertTrue((self.t["partidos"] > 0).all())

    def test_los_segmentos_suman_el_xg_de_xg_equipos(self):
        base = xe.agregar(self.tiros, self.equipos)
        np.testing.assert_allclose(ox.total(self.t, "f").to_numpy(),
                                   (base["xg_fav"] * base["xg_partidos"]).to_numpy(), atol=1e-6)
        np.testing.assert_allclose(ox.total(self.t, "c").to_numpy(),
                                   (base["xg_con"] * base["xg_partidos"]).to_numpy(), atol=1e-6)
        np.testing.assert_array_equal(self.t["partidos"].to_numpy(), base["xg_partidos"].to_numpy())

    def test_los_tiros_a_favor_son_los_tiros_sin_penal_ni_autogol(self):
        sp = self.tiros[(self.tiros["situation"] != "Penalty") & (self.tiros["result"] != "Own Goal")]
        self.assertEqual(int(sum(self.t[f"tf_{s}"].sum() for s in ox.IDS)), len(sp))
        self.assertEqual(int(sum(self.t[f"tc_{s}"].sum() for s in ox.IDS)), len(sp))

    def test_en_cada_liga_y_temporada_lo_que_se_hace_se_recibe(self):
        for s in ox.IDS:
            g = self.t.groupby(["temporada", "liga"])[[f"xf_{s}", f"xc_{s}"]].sum()
            np.testing.assert_allclose(g[f"xf_{s}"], g[f"xc_{s}"], atol=1e-6)

    def test_el_balon_parado_ronda_lo_que_se_sabe(self):
        # Sin penales, entre un quinto y un cuarto del xG: no es el 25-30% que se oye porque ese número suele
        # incluir los penales. Un equipo cualquiera queda entre el 5% y el 55%.
        peso = ox.peso_balon_parado(self.cerradas, "f")
        self.assertTrue(0.18 < peso.mean() < 0.28, peso.mean())
        self.assertTrue(0.05 < peso.min() and peso.max() < 0.6, (peso.min(), peso.max()))
        self.assertTrue(0.18 < self.r["hechos"]["bp_xg_pct"] / 100 < 0.28)

    def test_los_porcentajes_suman_100_en_las_580_filas(self):
        for lado in ("f", "c"):
            np.testing.assert_allclose(ox.participacion(self.t, lado).sum(axis=1), 1.0)

    def test_la_repeticion_del_balon_parado_es_baja_y_menor_que_la_del_xg_total(self):
        rep = self.r["repeticion"]
        self.assertLess(rep["bp_f"]["max"], 0.6)
        self.assertLess(rep["bp_f"]["juntos"], rep["xg_f"]["juntos"])

    def test_la_vista_se_arma_y_el_payload_es_chico(self):
        import json
        pagina = ox.chart_origen_xg()
        self.assertEqual(pagina.slug, "origen-xg")
        self.assertLessEqual(len(pagina.subtitle), 108)
        self.assertLess(len(json.dumps(ox.payload(self.r), separators=(",", ":"))), 200_000)

    def test_los_textos_no_dejan_marcas_sin_llenar(self):
        que, por = ox.textos(self.r)
        for t in (que, por):
            self.assertNotIn("{", t)
            self.assertNotIn("nan", t.lower().replace("financ", ""))
        self.assertIn("poca muestra", por)
        self.assertIn("suma más de lo que entra", por)


if __name__ == "__main__":
    unittest.main()
