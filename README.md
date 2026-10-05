<p align="center">
  <img src="web/dist/assets/logo.png" alt="FutViz" width="360">
</p>

<p align="center">
  Nació de juntar mi pasión por el <strong>fútbol</strong> con la <strong>ciencia de datos</strong>:
  partir de información pública y simple, y sacarle todo el jugo posible.
</p>

<p align="center">
  <a href="https://futviz-lake.vercel.app"><strong>Ver el sitio →</strong></a>
</p>

---

## Qué es

**FutViz** es un proyecto de ciencia de datos deportiva sobre las 5 grandes ligas europeas
de fútbol, temporada 2025/2026.
Arranca con un EDA (análisis exploratorio) a nivel de **equipo** y de **jugador**, con la idea
de ir subiendo en complejidad más adelante: desde exploración general hasta análisis más
específicos y la inclusión de **Machine Learning**.

Los datos son públicos y gratuitos ([fbref](https://fbref.com) para equipos, 
[Understat](https://understat.com) para jugadores), así que no traen estadísticas súper 
avanzadas, pero sí lo suficiente para sacar insights reales con buen tratamiento visual.


## Estructura del repo

```
data/           CSVs públicos de fbref (equipos) y Understat (jugadores)
code/           Notebooks del EDA (laboratorio) + viz_theme.py (identidad visual compartida)
web/
  charts/       Configuración de las vistas de "Análisis exploratorio" (jugadores y equipos) y
                gráficos de los artículos de ML (Plotly)
  build.py      Genera el sitio estático completo en web/dist/
  site_utils.py Plantillas de página (landing, secciones, gráficos individuales)
  react/        Las vistas de "Análisis exploratorio" en React + MUI X (gráficas, filtros, tabla).
                Se compila con Vite a react/build/
  react_views.py  Une Python con el bundle de React (tablas de datos + fragmentos + copia a dist/)
  section_views.py  Cascarón de la página con las vistas que cargan bajo demanda
  dist/         Sitio generado — se commitea tal cual para el deploy
img/            Logo y assets de marca fuente (no versionado — se procesa en cada build)
```

## Cómo correrlo

**Notebooks** (laboratorio de cada gráfico):

```bash
pip install pandas matplotlib plotly numpy pillow
jupyter notebook code/eda_teams.ipynb    # o code/eda_players.ipynb
```

**Sitio estático** (regenera `web/dist/` a partir de `web/charts/`):

```bash
cd web
python build.py
```

**Vistas en React** (solo si se toca `web/react/src/`; hace falta Node 20+). El bundle compilado
`web/react/build/` se versiona, así que `python build.py` no necesita Node:

```bash
cd web/react
npm install      # una vez
npm run build    # genera build/futviz-react.js
cd .. && python build.py
```

Los textos de lectura de cada vista ("En lo que estás viendo") se calculan en el navegador con una
copia en JS de `code/insights.py`. Para comprobar que ambas dan lo mismo (1.328 combinaciones de
temporada, liga, posición, nivel y sub-21):

```bash
cd web/react
python test/gen_paridad.py   # genera test/fixtures/ con la versión de Python
node test/paridad.mjs        # compara contra la de JS
```