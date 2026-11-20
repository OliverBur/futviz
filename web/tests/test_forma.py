"""Tests de la vista «Forma durante la temporada» (`web/charts/forma.py`).

    python -m unittest web/tests/test_forma.py      (desde la raíz del repo)

Dos partes. Las pruebas sintéticas comprueban la ventana móvil con valores conocidos, el orden por fecha, local y visita,
el resultado G/E/P, el xG sin penales, los partidos sin tiros o con tiros de un solo equipo y el cruce con FBref. Las de
datos reales necesitan `data/` y se saltan si no está: que cada equipo-temporada tenga las jornadas que jugó y que los goles
sumen lo que la tabla de FBref más los autogoles.
"""

import math
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(RAIZ / "web"), str(RAIZ / "web" / "charts"), str(RAIZ / "code")]

import forma  # noqa: E402

PROCESADOS = RAIZ / "data" / "processed"


def _partido(game, fecha, local, visita, gl, gv, temporada="2025-26", liga="Premier League"):
    return dict(temporada=temporada, liga=liga, game_id=game, fecha=f"{fecha} 15:00:00", local=local, visita=visita,
                goles_l=gl, goles_v=gv)


def _tiro(game, team, xg, situation="Open Play", result="Missed Shot", temporada="2025-26"):
    return dict(temporada=temporada, liga="Premier League", game_id=game, team=team, xg=xg, situation=situation, result=result)


# Ocho partidos entre Club A y Club B, un domingo tras otro. Los dueños de casa alternan (A, B, A, B...).
FECHAS = [f"2026-01-{d:02d}" for d in (4, 11, 18, 25)] + [f"2026-02-{d:02d}" for d in (1, 8, 15, 22)]
GOLES = [(2, 0), (1, 1), (0, 3), (2, 2), (3, 1), (0, 0), (1, 2), (4, 0)]          # (goles del local, goles de la visita)
XG_A = [1.5, 0.5, 0.2, 1.0, 2.0, 0.5, 0.8, 3.0]
XG_B = [0.5, 0.5, 1.2, 1.0, 0.5, 0.5, 1.8, 0.4]


def _sintetico():
    """(partidos, tiros) de los ocho partidos. Cada tiro es UNO por equipo y partido, más un penal que NO debe contar."""
    partidos, tiros = [], []
    for i, (f, (gl, gv)) in enumerate(zip(FECHAS, GOLES)):
        local, visita = ("Club A", "Club B") if i % 2 == 0 else ("Club B", "Club A")
        partidos.append(_partido(100 + i, f, local, visita, gl, gv))
        xl, xv = (XG_A[i], XG_B[i]) if i % 2 == 0 else (XG_B[i], XG_A[i])
        tiros += [_tiro(100 + i, local, xl), _tiro(100 + i, visita, xv),
                  _tiro(100 + i, local, 0.78, situation="Penalty", result="Goal")]
    return pd.DataFrame(partidos), pd.DataFrame(tiros)


def _fila(pe, equipo):
    return pe[pe["equipo"] == equipo].reset_index(drop=True)


class Ventana(unittest.TestCase):
    def test_promedio_movil_con_valores_conocidos(self):
        self.assertEqual(forma.ventana_movil([1, 2, 3, 4, 5, 6, 7], 3), [None, None, 2.0, 3.0, 4.0, 5.0, 6.0])

    def test_las_primeras_n_menos_1_no_tienen_ventana(self):
        v = forma.ventana_movil(list(range(10)), 6)
        self.assertEqual(v[:5], [None] * 5)
        self.assertEqual(v[5], 2.5)                  # (0+1+2+3+4+5) / 6

    def test_menos_valores_que_la_ventana_no_da_nada(self):
        self.assertEqual(forma.ventana_movil([1.0, 2.0], 6), [None, None])

    def test_un_valor_sin_dato_borra_las_ventanas_que_lo_contienen(self):
        v = forma.ventana_movil([1, 2, None, 4, 5, 6, 7], 3)
        self.assertEqual(v, [None, None, None, None, None, 5.0, 6.0])      # 3 a 5 llevan el hueco
        v = forma.ventana_movil([1, 2, float("nan"), 4, 5], 3)
        self.assertEqual(v, [None, None, None, None, None])

    def test_el_resultado(self):
        self.assertEqual([forma.resultado(2, 0), forma.resultado(1, 1), forma.resultado(0, 3)], ["G", "E", "P"])


class PartidosPorEquipo(unittest.TestCase):
    def setUp(self):
        self.partidos, self.tiros = _sintetico()
        self.pe = forma.partidos_por_equipo(self.partidos, self.tiros)

    def test_dos_filas_por_partido_y_ocho_por_equipo(self):
        self.assertEqual(len(self.pe), 16)
        self.assertEqual(len(_fila(self.pe, "Club A")), 8)

    def test_orden_por_fecha_aunque_lleguen_desordenados(self):
        barajado = self.partidos.sample(frac=1, random_state=3).reset_index(drop=True)
        pe = forma.partidos_por_equipo(barajado, self.tiros)
        a = _fila(pe, "Club A")
        self.assertEqual(list(a["game_id"]), [100 + i for i in range(8)])
        self.assertTrue(a["fecha"].is_monotonic_increasing)

    def test_dos_partidos_el_mismo_dia_se_ordenan_por_game_id(self):
        p = pd.DataFrame([_partido(2, "2026-01-04", "Club A", "Club B", 1, 0), _partido(1, "2026-01-04", "Club A", "Club C", 0, 1)])
        pe = forma.partidos_por_equipo(p, pd.DataFrame([_tiro(1, "Club A", 0.1), _tiro(2, "Club A", 0.1)]))
        self.assertEqual(list(_fila(pe, "Club A")["game_id"]), [1, 2])

    def test_local_y_visita(self):
        a = _fila(self.pe, "Club A")
        self.assertEqual(list(a["local"]), [1, 0, 1, 0, 1, 0, 1, 0])
        self.assertEqual(a.loc[1, "rival"], "Club B")
        # el partido 2 (índice 1) lo juega B de local: B 1-1 A
        self.assertEqual((a.loc[1, "gf"], a.loc[1, "gc"]), (1, 1))
        # el partido 3 (índice 2): A de local, 0-3
        self.assertEqual((a.loc[2, "gf"], a.loc[2, "gc"]), (0, 3))
        # el partido 8 (índice 7): B de local gana 4-0; A, de visita, 0 a favor y 4 en contra
        self.assertEqual((a.loc[7, "gf"], a.loc[7, "gc"]), (0, 4))
        # el partido 7 (índice 6): A de local pierde 1-2
        self.assertEqual((a.loc[6, "gf"], a.loc[6, "gc"]), (1, 2))

    def test_resultado_de_cada_partido(self):
        a = _fila(self.pe, "Club A")
        # A: 2-0 G, 1-1 E, 0-3 P, 2-2 E, 3-1 G, 0-0 E, 1-2 P, 0-4 P (de visita)
        self.assertEqual(list(a["res"]), ["G", "E", "P", "E", "G", "E", "P", "P"])
        b = _fila(self.pe, "Club B")
        self.assertEqual(list(b["res"]), ["P", "E", "G", "E", "P", "E", "G", "G"])

    def test_xg_sin_penales_y_lo_que_uno_crea_el_otro_lo_concede(self):
        a, b = _fila(self.pe, "Club A"), _fila(self.pe, "Club B")
        np.testing.assert_allclose(a["xf"], XG_A)                    # el penal de 0.78 no cuenta
        np.testing.assert_allclose(a["xc"], XG_B)
        np.testing.assert_allclose(a["xf"], b["xc"])
        np.testing.assert_allclose(a["xc"], b["xf"])

    def test_ventana_de_xg_y_de_goles_con_valores_conocidos(self):
        pe = forma.con_ventanas(self.pe)
        a = _fila(pe, "Club A")
        dx = np.array(XG_A) - np.array(XG_B)
        dg = np.array([2, 0, -3, 0, 2, 0, -1, -4])                    # goles a favor − en contra de A, partido a partido
        self.assertTrue(a["vx"].iloc[:5].isna().all())
        for i in range(5, 8):
            self.assertAlmostEqual(a.loc[i, "vx"], dx[i - 5:i + 1].mean())
            self.assertAlmostEqual(a.loc[i, "vg"], dg[i - 5:i + 1].mean())
        b = _fila(pe, "Club B")                                       # lo de B es el espejo
        self.assertAlmostEqual(b.loc[5, "vx"], -a.loc[5, "vx"])

    def test_partido_sin_ningun_tiro_queda_sin_xg_y_borra_sus_ventanas(self):
        tiros = self.tiros[self.tiros["game_id"] != 102]              # Understat no trae el partido 3
        pe = forma.con_ventanas(forma.partidos_por_equipo(self.partidos, tiros))
        a = _fila(pe, "Club A")
        self.assertTrue(math.isnan(a.loc[2, "xf"]) and math.isnan(a.loc[2, "xc"]))
        self.assertEqual(a.loc[2, "gf"], 0)                           # el marcador sí está
        self.assertTrue(a["vx"].iloc[5:8].isna().all())              # las tres ventanas contienen el partido 3
        self.assertFalse(a["vg"].iloc[5:8].isna().any())             # los goles no dependen de los tiros

    def test_partido_con_tiros_de_un_solo_equipo_deja_al_otro_en_cero(self):
        tiros = self.tiros[~((self.tiros["game_id"] == 103) & (self.tiros["team"] == "Club A"))]   # A no tiró en el 4
        pe = forma.partidos_por_equipo(self.partidos, tiros)
        a, b = _fila(pe, "Club A"), _fila(pe, "Club B")
        self.assertEqual(a.loc[3, "xf"], 0.0)
        self.assertEqual(b.loc[3, "xc"], 0.0)
        self.assertAlmostEqual(a.loc[3, "xc"], XG_B[3])

    def test_solo_las_temporadas_con_tiros(self):
        extra = pd.DataFrame([_partido(900, "2015-01-04", "Club A", "Club B", 1, 0, temporada="2014-15")])
        pe = forma.partidos_por_equipo(pd.concat([self.partidos, extra], ignore_index=True), self.tiros)
        self.assertEqual(set(pe["temporada"]), {"2025-26"})

    def test_el_nombre_pasa_por_club_visible(self):
        p = pd.DataFrame([_partido(1, "2026-01-04", "Wolverhampton Wanderers", "Club B", 1, 0)])
        pe = forma.partidos_por_equipo(p, pd.DataFrame([_tiro(1, "Wolverhampton Wanderers", 0.2)]))
        self.assertIn("Wolves", set(pe["equipo"]))


class Calculo(unittest.TestCase):
    def setUp(self):
        self.partidos, self.tiros = _sintetico()

    def test_ruido_por_partido(self):
        pe = forma.con_ventanas(forma.partidos_por_equipo(self.partidos, self.tiros))
        dx = np.array(XG_A) - np.array(XG_B)
        # dos grupos (A y B, espejo): suma de cuadrados de A y de B entre (16 observaciones − 2 grupos)
        esperado = math.sqrt(2 * ((dx - dx.mean()) ** 2).sum() / (16 - 2))
        self.assertAlmostEqual(forma.ruido_por_partido(pe, ["2025-26"]), esperado)

    def test_calcular_marca_la_temporada_en_curso_y_no_la_mide(self):
        otra = self.partidos.assign(temporada="2026-27", game_id=self.partidos["game_id"] + 1000)
        tiros_o = self.tiros.assign(temporada="2026-27", game_id=self.tiros["game_id"] + 1000)
        r = forma.calcular(pd.concat([self.partidos, otra]), pd.concat([self.tiros, tiros_o]), en_curso={"2026-27": 8})
        self.assertEqual(r["cerradas"], ["2025-26"])
        self.assertEqual(r["en_curso_n"], {"2026-27": 8})
        self.assertEqual(r["pj_min"], 8)
        self.assertEqual(r["autogoles"], 0)
        self.assertEqual(r["partidos_sin_tiros"], 0)

    def test_cuenta_los_partidos_sin_tiros_y_los_de_un_solo_equipo(self):
        tiros = self.tiros[(self.tiros["game_id"] != 102) & ~((self.tiros["game_id"] == 103) & (self.tiros["team"] == "Club A"))]
        r = forma.calcular(self.partidos, tiros, en_curso=[])
        self.assertEqual(r["partidos_sin_tiros"], 1)
        self.assertEqual(r["partidos_un_equipo"], 1)

    def test_comprobacion_con_fbref_encuentra_el_partido_de_mas_o_de_menos(self):
        pe = forma.partidos_por_equipo(self.partidos, self.tiros)
        # FBref: A con 8 partidos y un gol menos que el marcador (un autogol); B con 9 partidos
        goles_a = int(_fila(pe, "Club A")["gf"].sum())
        goles_b = int(_fila(pe, "Club B")["gf"].sum())
        equipos = pd.DataFrame([
            dict(temporada="2025-26", liga="Premier League", Squad="Club A", **{"ov_Playing Time_MP": 8, "ov_Performance_Gls": goles_a - 1}),
            dict(temporada="2025-26", liga="Premier League", Squad="Club B", **{"ov_Playing Time_MP": 9, "ov_Performance_Gls": goles_b}),
        ])
        descuadres, dif = forma.comprobar_con_fbref(pe, equipos)
        self.assertEqual(descuadres, [("2025-26", "Premier League", "Club B", 8, 9)])
        self.assertEqual(dif, 1)

    def test_equipo_que_falta_en_fbref_detiene_el_calculo(self):
        pe = forma.partidos_por_equipo(self.partidos, self.tiros)
        equipos = pd.DataFrame([dict(temporada="2025-26", liga="Premier League", Squad="Club A",
                                     **{"ov_Playing Time_MP": 8, "ov_Performance_Gls": 10})])
        with self.assertRaises(ValueError):
            forma.comprobar_con_fbref(pe, equipos)


class Payload(unittest.TestCase):
    def setUp(self):
        partidos, tiros = _sintetico()
        self.r = forma.calcular(partidos, tiros, en_curso=[])
        self.p = forma.payload(self.r, "Club A")
        self.a = self.p["t"]["2025-26"]["Club A"]

    def test_los_arrays_son_del_mismo_largo_y_van_en_orden_de_fecha(self):
        n = 8
        for k in ("r", "h", "gf", "gc", "xf", "xc", "d", "vx", "vg"):
            self.assertEqual(len(self.a[k]), n, k)
        self.assertEqual(self.a["d"], sorted(self.a["d"]))

    def test_el_rival_es_un_indice_de_nombres(self):
        self.assertEqual({self.p["nombres"][i] for i in self.a["r"]}, {"Club B"})
        self.assertEqual(self.a["h"], [1, 0, 1, 0, 1, 0, 1, 0])

    def test_las_ventanas_traen_nulos_al_principio(self):
        self.assertEqual(self.a["vx"][:5], [None] * 5)
        self.assertIsNotNone(self.a["vx"][5])
        dx = np.array(XG_A) - np.array(XG_B)
        self.assertAlmostEqual(self.a["vx"][5], dx[:6].mean(), places=3)

    def test_la_fecha_son_dias_desde_1970(self):
        self.assertEqual(self.a["d"][0], int((pd.Timestamp(FECHAS[0]) - pd.Timestamp("1970-01-01")).days))

    def test_el_payload_cabe_en_json_sin_nan(self):
        import json
        json.dumps(self.p, allow_nan=False)

    def test_los_textos_se_arman_sin_numeros_a_mano(self):
        que_mirar, por_que = forma.textos(self.r)
        self.assertIn(f"{forma.VENTANA} partidos", que_mirar)
        self.assertIn("Por qué xG sin penales", por_que)
        self.assertIn("2025-26", por_que)


@unittest.skipUnless((PROCESADOS / "shots_all_seasons.csv").exists() and (RAIZ / "data" / "2025-26" / "partidos.csv").exists(),
                     "faltan los datos de data/")
class DatosReales(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.partidos, cls.tiros, cls.equipos = forma._cargar()
        cls.r = forma.calcular(cls.partidos, cls.tiros, cls.equipos)

    def test_cada_equipo_temporada_tiene_las_jornadas_que_jugo_salvo_los_conocidos(self):
        # `partidos.csv` es de Understat; el conteo difiere del de FBref en uno en unos pocos equipo-temporadas
        self.assertLessEqual(len(self.r["descuadres"]), 6)
        for _t, _l, _e, aqui, fbref in self.r["descuadres"]:
            self.assertEqual(abs(aqui - fbref), 1)

    def test_los_goles_suman_lo_de_fbref_mas_los_autogoles(self):
        self.assertAlmostEqual(self.r["dif_goles"], self.r["autogoles"], delta=8)

    def test_un_solo_partido_sin_tiros_y_cuatro_de_un_solo_equipo(self):
        self.assertEqual(self.r["partidos_sin_tiros"], 1)
        self.assertEqual(self.r["partidos_un_equipo"], 4)

    def test_cada_partido_aparece_dos_veces_y_las_ventanas_son_de_6(self):
        pe = self.r["pe"]
        self.assertEqual(len(pe), 2 * self.r["n_partidos"])
        n = pe.groupby(["temporada", "equipo"]).size()
        cerradas = n[n.index.get_level_values("temporada").isin(self.r["cerradas"])]
        self.assertTrue(cerradas.between(34, 38).all())          # una temporada completa: 34 (18 equipos) o 38
        primeras = pe.groupby(["temporada", "equipo"]).head(forma.VENTANA - 1)
        self.assertTrue(primeras["vx"].isna().all())

    def test_el_xg_de_un_lado_es_el_del_otro_en_contra(self):
        pe = self.r["pe"]
        self.assertAlmostEqual(pe["xf"].sum(), pe["xc"].sum(), places=6)

    def test_las_liga_tienen_xg_por_partido_razonable(self):
        pe = self.r["pe"].dropna(subset=["xf"])
        self.assertTrue(1.0 < pe["xf"].mean() < 1.8)


if __name__ == "__main__":
    unittest.main()
