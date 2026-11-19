"""Los nombres como se dicen: «Kylian Mbappé», «Atlético Madrid», «Bayern Múnich».

Cada fuente escribe distinto. Understat quita los acentos de casi todos los clubes y a veces pone el nombre
completo («Kylian Mbappe-Lottin»); FBref los trae bien escritos, pero con abreviaturas propias («Manchester Utd»,
«Racing Sant»). Aquí se unifican para lo que se MUESTRA (menús, etiquetas, tablas, el buscador de la portada). Los
datos consolidados no se tocan: los cruces entre fuentes (`consolidate_data.py`) siguen usando los nombres de origen.

* **Jugadores**: el nombre de la fila de FBref con la que se cruzó (`player_fbref`, lo deja `consolidate_data.py`);
  quien no cruzó conserva el de Understat, salvo los alias de abajo.
* **Clubes**: un diccionario, porque son pocos y se equivocan de forma distinta cada uno.
"""

import pandas as pd

# Cómo se muestra cada club. Las llaves son los nombres de Understat y de FBref que no coinciden entre sí.
CLUBES = {
    # Understat
    "AC Milan": "Milan", "Alaves": "Alavés", "Almeria": "Almería", "Arminia Bielefeld": "Arminia",
    "Atletico Madrid": "Atlético Madrid", "Bayer Leverkusen": "Leverkusen", "Borussia Dortmund": "Dortmund",
    "Borussia M.Gladbach": "Gladbach", "Cadiz": "Cádiz", "Coventry": "Coventry City", "Darmstadt": "Darmstadt 98",
    "Deportivo La Coruna": "Deportivo La Coruña", "Eintracht Frankfurt": "Frankfurt", "FC Cologne": "Köln",
    "FC Heidenheim": "Heidenheim", "Greuther Fuerth": "Greuther Fürth", "Hertha Berlin": "Hertha BSC",
    "Hull": "Hull City", "Ipswich": "Ipswich Town", "Leeds": "Leeds United", "Leganes": "Leganés",
    "Leicester": "Leicester City", "Luton": "Luton Town", "Malaga": "Málaga", "Newcastle United": "Newcastle",
    "Norwich": "Norwich City", "Paderborn": "Paderborn 07", "Paris Saint Germain": "PSG",
    "Parma Calcio 1913": "Parma", "RasenBallsport Leipzig": "RB Leipzig", "Real Oviedo": "Oviedo",
    "Real Valladolid": "Valladolid", "Saint-Etienne": "Saint-Étienne", "St. Pauli": "St Pauli",
    "Verona": "Hellas Verona", "VfB Stuttgart": "Stuttgart", "Wolverhampton Wanderers": "Wolves",
    # los dos: el que se dice en español
    "Bayern Munich": "Bayern Múnich", "Manchester Utd": "Manchester United", "Nottingham": "Nottingham Forest",
    "Paris SG": "PSG", "Racing Sant": "Racing Santander", "Dep. A Coruña": "Deportivo La Coruña",
}

# Jugadores que no cruzaron con FBref y cuyo nombre en Understat no es como se les dice. Se llena mirando la
# lista de «sin cruce» con más minutos (ver la bitácora del 2026-11-18).
JUGADORES = {
    "Kylian Mbappe-Lottin": "Kylian Mbappé",
    "Dayotchanculle Upamecano": "Dayot Upamecano",
    "Kephren Thuram": "Khéphren Thuram",
    "Naif Aguerd": "Nayef Aguerd",
    "Kouadio Kone": "Manu Koné",
    "Yeremi Pino": "Yeremy Pino",
    "Mathis Cherki": "Rayan Cherki",
    "Andrew Robertson": "Andy Robertson",
    "Álex Balde": "Alejandro Balde",
}


def club_visible(nombre):
    """El club como se muestra. Respeta la coma de quien jugó en dos («Angers,Rennes»)."""
    if not isinstance(nombre, str):
        return nombre
    return ",".join(CLUBES.get(c.strip(), c.strip()) for c in nombre.split(","))


def aplicar_a_jugadores(df):
    """`df` con `player` y `team` listos para mostrar."""
    df = df.copy()
    if "player_fbref" in df.columns:
        bueno = df["player_fbref"].notna() & (df["player_fbref"].astype(str).str.strip() != "")
        df["player"] = df["player_fbref"].where(bueno, df["player"])
    df["player"] = df["player"].replace(JUGADORES)
    df["team"] = df["team"].map(club_visible)
    return df


def aplicar_a_equipos(df):
    """`df` con `Squad` listo para mostrar."""
    df = df.copy()
    df["Squad"] = df["Squad"].map(club_visible)
    return df
