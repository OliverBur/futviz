"""Invariancia al futuro de las variables del modelo de xG.

    python -m unittest web/tests/test_xg_causal.py      (desde la raíz del repo)

Si una variable de un tiro cambia al borrar los tiros que vinieron DESPUÉS en su partido, el modelo puede
enterarse del resultado por la jugada siguiente (es lo que pasaba con el viejo `rebote`). El test toma una
muestra de partidos de 2025-26, y para cada tiro k borra todo lo posterior —los tiros de minutos
siguientes y, dentro del mismo minuto, los de `shot_id` mayor— y vuelve a calcular las variables: las del
tiro k tienen que salir iguales. Cubre geometría, parte del cuerpo y situación, asistido, rebote previo,
acción previa, minuto y marcador, y local.

Lo que no cubre, porque no se calcula con los demás tiros: el ELO (el de clubelo vigente el día del
partido; cambia desde el día siguiente) y el puesto del tirador (el de fbref en la temporada: resume
toda la temporada, también partidos posteriores, pero no dice nada del resultado del tiro).

Hay además una prueba de que el test tiene dientes: la definición vieja de `rebote` tiene que fallarlo.
"""

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

WEB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WEB))
sys.path.insert(0, str(WEB / "charts"))

import xg_modelo as xm  # noqa: E402

TEMPORADA = "2025-26"
PARTIDOS = 40
COLUMNAS = ["dist", "angulo", "dist_y", "location_x", "location_y", "situation", "body_part",
            "asistido", "rebote_previo", "accion", "minute", "marcador", "es_local"]


def _rebote_viejo(s):
    """La definición de antes: otro tiro del mismo equipo en el mismo minuto, antes O DESPUÉS."""
    return (s.groupby(["game_id", "team", "minute"])["shot_id"].transform("size") > 1).astype(int)


def _hasta(partido, fila):
    """Los tiros del partido hasta `fila` inclusive: minutos anteriores y, en su minuto, `shot_id` menor o igual."""
    return partido[(partido.minute < fila.minute)
                   | ((partido.minute == fila.minute) & (partido.shot_id <= fila.shot_id))]


def _variables(crudo, extra=None):
    s, _, _ = xm._preparar(crudo)
    if extra:
        s["extra"] = extra(s)
    return s.set_index("shot_id")


def _cambios(crudo, columnas, extra=None):
    """Lista de (shot_id, columna, valor completo, valor truncado) que cambian al borrar el futuro."""
    completo = _variables(crudo, extra)
    out = []
    for _, partido in crudo.groupby("game_id"):
        for fila in partido.itertuples():
            if fila.shot_id not in completo.index:          # penal, autogol o fuera de ángulo
                continue
            trunc = _variables(_hasta(partido, fila), extra)
            a, b = completo.loc[fila.shot_id, columnas], trunc.loc[fila.shot_id, columnas]
            for c in columnas:
                va, vb = a[c], b[c]
                igual = (np.isclose(va, vb) if isinstance(va, (float, np.floating, int, np.integer)) else va == vb)
                if not igual:
                    out.append((fila.shot_id, c, va, vb))
    return out


class TestSintetico(unittest.TestCase):
    """Un partido inventado: no necesita los datos."""

    def setUp(self):
        base = dict(game_id=1, local="A", visita="B", location_x=0.9, location_y=0.5, situation="Open Play",
                    body_part="Right Foot", assist_player=None, last_action="Pass", xg=0.1, es_local=1)
        filas = [(10, "A", 20, "Missed Shot"), (11, "A", 20, "Saved Shot"), (12, "A", 20, "Goal"),
                 (13, "B", 20, "Missed Shot"), (14, "A", 35, "Goal"), (15, "B", 50, "Own Goal")]
        self.s = pd.DataFrame([dict(base, shot_id=i, team=t, minute=m, result=r, es_local=int(t == "A"))
                               for i, t, m, r in filas])

    def test_rebote_previo(self):
        s = _variables(self.s)
        self.assertEqual(s.loc[[10, 11, 12, 13, 14], "rebote_previo"].tolist(), [0, 1, 1, 0, 0])

    def test_marcador_solo_minutos_anteriores(self):
        s = _variables(self.s)
        # el gol del 20' no cuenta para los tiros de ese mismo minuto, sí para el del 35'
        self.assertEqual(s.loc[[10, 12, 14], "marcador"].tolist(), [0, 0, 1])

    def test_invariancia(self):
        self.assertEqual(_cambios(self.s, COLUMNAS), [])

    def test_el_rebote_viejo_falla(self):
        cambios = _cambios(self.s, ["extra"], extra=_rebote_viejo)
        self.assertTrue(any(sid == 10 for sid, *_ in cambios))


class TestDatosReales(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (xm.DATA_DIR / TEMPORADA / "shots.csv").exists():
            raise unittest.SkipTest(f"Faltan los tiros de {TEMPORADA}.")
        s = xm._cargar([TEMPORADA])
        n = s.groupby(["game_id", "team", "minute"])["shot_id"].transform("size")
        # la mitad de la muestra, partidos con varios tiros del mismo equipo en un minuto (donde muerde)
        con = s.loc[n > 1, "game_id"].drop_duplicates().sample(PARTIDOS // 2, random_state=0)
        resto = s.loc[~s.game_id.isin(con), "game_id"].drop_duplicates().sample(PARTIDOS // 2, random_state=0)
        cls.s = s[s.game_id.isin(set(con) | set(resto))].reset_index(drop=True)

    def test_invariancia(self):
        cambios = _cambios(self.s, COLUMNAS)
        self.assertEqual(cambios, [], f"{len(cambios)} variables cambian al borrar el futuro: {cambios[:5]}")

    def test_el_rebote_viejo_falla(self):
        cambios = _cambios(self.s, ["extra"], extra=_rebote_viejo)
        self.assertGreater(len(cambios), 0)


if __name__ == "__main__":
    unittest.main()
