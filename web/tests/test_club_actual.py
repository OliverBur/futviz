"""Test del club de los jugadores con varios clubes en Understat (`consolidate_data.club_actual_al_final`).

    python -m unittest web/tests/test_club_actual.py      (desde la raíz del repo)

En 2026-27 Understat trajo a casi todo el PSG como 'Paris Saint Germain,Rennes' y el sitio tomaba el último:
Kvaratskhelia salía en el Rennes y como club underground. Ahora va al final el club del tiro más reciente.
"""

import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "code"))

import consolidate_data as cd  # noqa: E402


class ClubActual(unittest.TestCase):
    def _reordenar(self, jugadores, tiros):
        with tempfile.TemporaryDirectory() as d:
            pd.DataFrame(tiros, columns=["liga", "player", "team", "date", "minute"]).to_csv(
                Path(d) / "shots.csv", index=False, encoding="utf-8-sig")
            p = pd.DataFrame(jugadores, columns=["liga", "player", "team"])
            return list(cd.club_actual_al_final(p, Path(d))["team"])

    def test_el_club_del_ultimo_tiro_va_al_final(self):
        equipos = self._reordenar(
            [("Ligue 1", "Khvicha Kvaratskhelia", "Paris Saint Germain,Rennes"),
             ("Premier League", "Jack Grealish", "Everton,Manchester City"),
             ("Ligue 1", "Esteban Lepaul", "Paris Saint Germain,Rennes")],
            [("Ligue 1", "Khvicha Kvaratskhelia", "Paris Saint Germain", "2026-10-10 18:45:00", 60),
             ("Premier League", "Jack Grealish", "Manchester City", "2026-08-20 15:00:00", 10),
             ("Premier League", "Jack Grealish", "Everton", "2026-09-20 15:00:00", 30),
             ("Ligue 1", "Esteban Lepaul", "Rennes", "2026-10-01 20:00:00", 5)])
        self.assertEqual(equipos, ["Rennes,Paris Saint Germain", "Manchester City,Everton",
                                   "Paris Saint Germain,Rennes"])

    def test_sin_tiros_o_un_solo_club_no_cambia(self):
        equipos = self._reordenar(
            [("Serie A", "Sin Tiros", "Como,Fiorentina"), ("Serie A", "Uno Solo", "Napoli")],
            [("Serie A", "Uno Solo", "Napoli", "2026-09-01 18:00:00", 12)])
        self.assertEqual(equipos, ["Como,Fiorentina", "Napoli"])

    def test_tiro_con_un_club_que_no_esta_en_la_lista(self):
        equipos = self._reordenar([("La Liga", "Raro", "Betis,Sevilla")],
                                  [("La Liga", "Raro", "Cádiz", "2026-09-01 18:00:00", 3)])
        self.assertEqual(equipos, ["Betis,Sevilla"])


if __name__ == "__main__":
    unittest.main()
