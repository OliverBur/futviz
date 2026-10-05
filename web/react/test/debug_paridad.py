"""Depura los casos de paridad que difieren: valores exactos de Python (repr completo)."""
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
WEB = AQUI.parents[1]
sys.path[:0] = [str(WEB), str(WEB / "charts")]
import site_utils  # noqa
import numpy as np
import players, teams

# 1) definicion 2022-23 Bundesliga top
df = teams.load_data()
d = df[(df.temporada == "2022-23") & (df.liga == "Bundesliga") & (df.nivel == "Clubes top")]
print("definicion filas:", len(d))
print(d[["Squad", "sh_Standard_G/SoT"]].to_string())
y = d["sh_Standard_G/SoT"]
print("mean repr:", repr(y.mean()), "| naive:", repr(sum(y) / len(y)), "| numpy sum:", repr(float(np.sum(y.values))))

# 2) construir 2021-22 La Liga: mediana de xga90 y Aurier
dj = players.load_data()
dd = dj[dj["xgbuild90"].notna() & dj["xga90"].notna()]
d2 = dd[(dd.temporada == "2021-22") & (dd.liga == "La Liga")]
med = d2["xga90"].median()
print("\nmediana xga90 (py):", repr(med), "n =", len(d2))
for nombre in ("Serge Aurier", "Sergio Busquets"):
    r = d2[d2.player == nombre].iloc[0]
    print(nombre, "xga90 =", repr(r["xga90"]), "| <= mediana:", r["xga90"] <= med, "| xgbuild90 =", repr(r["xgbuild90"]))
cerca = d2[(d2["xga90"] - med).abs() < 1e-5][["player", "xga90"]]
print("cercanos a la mediana:\n", cerca.to_string())
