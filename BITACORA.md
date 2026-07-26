# Top 5 Ligas — Ciencia de datos deportiva

## Por qué hice este proyecto

Este directorio es para proyectos de ciencia de datos deportiva, específicamente en fútbol. Tengo varios CSVs en `data/` que conseguí gratis de fbref, así que no traen estadísticas avanzadas (nada de xG, progresivos, etc.), pero sí traen muy buena información con la que se pueden hacer buenos análisis.

Lo empecé como una forma de meterme en el mundo de la ciencia de datos deportiva juntando dos cosas: mi conocimiento de ciencia de datos y mi pasión por el fútbol. La idea es partir de data pública y sencilla, sacarle todo el jugo posible, e ir subiendo en complejidad — desde un EDA general hasta análisis más específicos y avanzados más adelante.

Para la parte visual no quería quedarme en gráficos por defecto de matplotlib: quería meterle algo de identidad y producción a las gráficas aunque siguiera usando Python/matplotlib en vez de saltar directo a JS/D3.

## Estado actual del proyecto

### Datos (`data/`)

5 CSVs de fbref, todos a nivel de **equipo** (no partido, no jugador), temporada 2025-26:

- `leagues_overall.csv` — goles, asistencias, posesión, tarjetas
- `leagues_shoot.csv` — tiros, tiros a puerta, conversión
- `leagues_playtime.csv` — minutos, titularidades, rotación, PPM
- `leagues_misc.csv` — faltas, tackles, intercepciones, tarjetas
- `leagues_gk.csv` — portería: saves, clean sheets, penaltis

Sin columna de liga explícita, pero los archivos vienen concatenados en bloques ordenados: Bundesliga (18), Serie A (20), Ligue 1 (18), La Liga (20), Premier League (20) = 96 equipos. Se verificó que el orden de `Squad` es idéntico en los 5 archivos, así que la columna `liga` se asigna por rango de filas.

### Identidad visual (`code/viz_theme.py`)

Tema reutilizable para todos los notebooks del proyecto:

- **Colores fijos por liga**: Bundesliga rojo, Serie A azul, Ligue 1 verde oscuro, La Liga amarillo, Premier League magenta — siempre el mismo color para la misma liga en todos los gráficos.
- Rampa secuencial (azul) para magnitud, par divergente (azul↔rojo) para sobre/bajo rendimiento.
- Tema de matplotlib: fondo claro, sin bordes arriba/derecha, grid tenue, tipografía Segoe UI.
- Reglas: identidad nunca solo por color (labels directos en los puntos destacados), leyenda cuando hay ≥2 series.
- **Tema Plotly** (`apply_plotly_theme()`, `league_dropdown()`): mismo look que matplotlib (superficie, tinta, grid, Segoe UI) para los gráficos interactivos — ver sección "Plotly" más abajo.

### EDA general (`code/eda.ipynb`)

Un solo notebook (se consolidó `analisis1.ipynb` + `eda.ipynb` en uno solo — ya no existe `analisis1.ipynb`). Se ejecuta con `nbclient` después de cada cambio para que las salidas queden incrustadas y el notebook se pueda ver sin volver a correrlo (los gráficos Plotly quedan embebidos como HTML autocontenido, ver sección "Plotly" más abajo).

Estructura actual, 3 bloques (las secciones "Sobre/bajo rendimiento" y "Rotación de plantilla" que existieron en versiones anteriores se sacaron por decisión del usuario — no aportaban insight suficiente):

1. **Estilos de juego y diferencias por liga**
   - Perfil de liga (radar por liga, 8 métricas escaladas `value/max` — ver "Radar de perfil de liga" abajo)
   - Perfil de liga, sobrepuesto (mismo radar, 5 ligas juntas + tabla de separación por eje)
   - Eficiencia de definición (SoT% vs. G/SoT, interactivo con barra lateral)
2. **Porteros**
   - Ranking de porterías (índice `Save% − GA90`, sin CS% — ver sección "Índice de porterías" abajo)
   - Portería vs. resultado del equipo (CS% vs. puntos por partido, interactivo)
   - Exigencia vs. rendimiento (SoTA vs. Save%, interactivo)
3. **Identidad de cada liga** (propiedades de la liga como sistema, no de un equipo puntual — box plot + puntos por equipo, con hover)
   - Paridad competitiva (dispersión de puntos por partido dentro de cada liga)
   - Edad de plantilla
   - Disciplina: tarjetas amarillas

Preguntas específicas que surgieron en el camino (por qué destacó tanto el Lens, análisis táctico más a fondo con `overall`, etc.) quedaron **fuera de este EDA a propósito** — son para notebooks específicos más adelante.

### Radar de perfil de liga — decisiones de método (registro de decisión)

El radar del perfil de liga pasó por varias iteraciones de normalización antes de fijar el método y las métricas. Se documenta acá para no volver a discutir lo mismo.

#### Por qué `value/max` (y no las otras normalizaciones)

Todas las alternativas normalizan cada eje contra el spread de las 5 medias de liga, lo que **fabrica diferencias donde no las hay**. `value/max` (dividir cada media por el máximo de las 5) es el único donde el 0 del eje es el 0 real de la métrica y la separación refleja la **proporción real** entre ligas.

| Método | Qué hace | Problema | Veredicto |
|---|---|---|---|
| min-max `(x−min)/(max−min)` | ancla peor liga a 0, mejor a 1 | 170 vs 180 tiros se ven como polos opuestos aunque sean casi iguales | ❌ |
| min-max + padding 15% | igual pero mapea a 0.15–0.85 | mismo problema de fondo, solo mueve los extremos | ❌ |
| percentil 5/95 de equipos | normaliza contra los 96 equipos | aplasta las 5 formas al centro (poca diferenciación) | ❌ |
| z-score (5 medias) + sigmoide | estandariza las 5 medias, acota con `1/(1+e^(-z/k))` | estandarizar 5 números por su propio desvío **siempre** da spread completo → inventa diferencias; mide rank/significancia, no magnitud | ❌ |
| **`value/max`** | cada media / máximo de las 5 | ninguno para este objetivo: 0 real, magnitud proporcional | ✅ **champion** |

**Evidencia decisiva** — spread (separación en el eje) que genera cada método vs. la diferencia *real* entre ligas (eta² = fracción de la varianza total que explica la liga; alto = diferencia real grande):

| Métrica | eta² (diferencia real) | spread `value/max` | spread `z(5)+sigmoide` |
|---|---|---|---|
| Faltas | **0.324** (la más real) | 0.18 | 0.78 |
| CS% | 0.139 | 0.34 | 0.86 |
| Tiros | **0.024** (casi nula) | 0.07 | 0.79 |
| Centros | **0.020** (casi nula) | 0.06 | 0.86 |

Con `value/max` el spread sigue a eta² (grande donde hay diferencia real, chico donde no). Con z-score el spread es ~0.8 en **todos** los ejes por igual: Centros (sin diferencia real) sale con *más* spread que Faltas (la diferencia más real que existe) → drama constante e inventado. Bonus: `value/max` es exactamente lo que se pidió desde el principio (180/170/90 → 1.0/0.94/0.5).

Caso extremo — Posesión: diferencia real entre ligas = **0.0 pts %** (todas ~50%, porque la posesión suma 100% por partido y el promedio de liga es mecánicamente 50). `value/max` la muestra plana (correcto); z-score le inventaba spread 0.87.

#### Métricas del radar (qué quitamos y qué explica cada una)

Criterio de selección: **eta²** (señal real vs. ruido entre equipos) + **rango relativo** (para que se vea en `value/max`) + **correlación** (para no meter ejes redundantes que dupliquen otro).

**Quitadas:**

| Métrica | eta² | Por qué fuera |
|---|---|---|
| Posesión | ~0 | promedio de liga mecánicamente ~50% para todas → eje muerto en cualquier método |
| Tiros/90 | 0.024 | las 5 ligas tiran casi lo mismo (12.3–13.25); no discrimina |
| Centros/90 | 0.020 | casi idénticas (17–18); no discrimina |

También se evaluaron y **descartaron por redundancia** (duplicaban un eje ya presente): Asistencias (corr +0.98 con Goles), Goles recibidos/GA90 (corr −0.84 con CS%).

**Set final (7 ejes) y qué mide cada uno:**

| Eje | Columna | Qué explica de la liga | eta² |
|---|---|---|---|
| Goles | `ov_Per 90 Minutes_Gls` | producción goleadora (goles/90) | 0.085 |
| G/Sh | `sh_Standard_G/Sh` | definición: qué tan clínica es (goles por tiro) | 0.116 |
| CS% | `gk_Performance_CS%` | solidez defensiva por resultado (% porterías a cero) | 0.139 |
| Tackles | `p90_TklW` | actividad defensiva: entradas ganadas (duelo) | 0.138 |
| Intercep. | `p90_Int` | estilo defensivo de lectura: robar leyendo el pase (complementa Tackles, corr 0.49) | 0.196 |
| Offsides | `p90_Off` | dimensión táctica: línea alta / trampas de offside (independiente de todo, corr 0.15) | 0.149 |
| Faltas | `p90_Fls` | físico / disciplina: cuánto interrumpe a faltas | 0.324 |

Cubre ataque (Goles, G/Sh), defensa (CS%, Tackles, Intercep.), táctica (Offsides) y físico (Faltas). Offsides e Intercepciones fueron los reemplazos de Tiros/Centros: alta señal y baja redundancia.

### Plotly — gráficos interactivos (scatters de equipo por equipo)

Los 4 scatters que muestran un punto por equipo (Eficiencia de definición, Verticalidad, Portería vs. resultado, Puntos vs. diferencia de gol) se migraron de matplotlib a **Plotly** para poder identificar qué equipo es cada punto (hover) y filtrar por liga. El radar y los gráficos de barras se quedaron en matplotlib — no se benefician de hover/filtro de la misma forma y no hacía falta tocarlos.

- **`code/viz_theme.py`**: se agregó `apply_plotly_theme()` (template de Plotly con los mismos colores/tipografía que matplotlib) y `league_dropdown(extra_traces=0)` (helper que arma el menú desplegable de filtro por liga, reutilizado en los 4 gráficos — asume una traza por liga en el orden de `LEAGUE_ORDER`; `extra_traces` es para trazas que deben quedar siempre visibles, como la línea de tendencia).
- **Renderer**: `pio.renderers.default = 'notebook_connected'` — cada gráfico queda embebido en el `.ipynb` como `text/html` autocontenido (carga Plotly.js una vez desde CDN). Se verificó explícitamente con `nbclient` que esto genera output `text/html` (no `application/vnd.plotly.v1+json`, que necesita un renderer específico del visor) para que el notebook se pueda ver en Jupyter/VS Code sin volver a ejecutar — mismo criterio de diseño que ya tenía `eda.ipynb` con las imágenes de matplotlib. Requiere internet la primera vez que se abre (CDN).
- **Bug real encontrado y corregido en el gráfico de Puntos vs. diferencia de gol**: al mismo tiempo que se codifica el residuo como color continuo (colorscale divergente) y se arma una traza por liga (para el filtro), Plotly generaba una leyenda categórica con colores que no eran los de las ligas (tomados del colorscale), superpuesta al colorbar — ilegible. Fix: `showlegend=False` en las trazas de liga (la identidad de liga se resuelve por hover y por el filtro, no por color — el color ahí es el residuo) y colorbar único en la última traza con `cmin`/`cmax` fijos e iguales en las 5 trazas para que la escala sea comparable entre ligas.
- Instalado `plotly` y `kaleido` (este último solo para exportar PNG y poder revisar el layout de los prototipos antes de aplicarlos — no es una dependencia del notebook en sí).
- Prototipado todo en scratchpad (`plotly_proto.py`), verificado a PNG con kaleido, y recién después aplicado a `eda.ipynb` + ejecutado con `nbclient`.

**Ronda de fixes (mismo día, tras probar en un kernel real):**

1. **Gráfico "achatado"/dependiente del ancho de ventana**: sin `width` explícito, Plotly estira la figura al ancho del contenedor (se ve elongado en monitores anchos y cambia de forma al achicar la ventana). Fix: `PLOTLY_SCATTER_SIZE = dict(width=900, height=620)` en `viz_theme.py`, pasado a los 4 gráficos (`**PLOTLY_SCATTER_SIZE`, o explícito en el de residuo que necesita más ancho por el colorbar).
2. **Filtro de liga "apenas visible" abajo**: bug real en `league_dropdown()` — estaba en `y=-0.16, yanchor='top'`, o sea que la parte de ARRIBA de la caja quedaba en y=-0.16 (coordenadas de papel van de 0 a 1), así que la caja entera vivía fuera del canvas visible. Fix: `y=0.02, yanchor='bottom'` — la caja queda anclada por abajo, dentro de [0,1].
3. **Etiquetas de Bayern Munich/Dortmund no respetaban el filtro de liga**: las anotaciones de Plotly son de layout, no están atadas a la visibilidad de las trazas, así que al filtrar a otra liga las etiquetas se quedaban pegadas igual. Se sacaron esas dos etiquetas fijas — ya no hacen falta porque el buscador de club (punto 4) cubre ese caso mejor, sin el bug.
4. **Buscador de club** (pedido nuevo): `club_search_dropdown()` en `viz_theme.py` — dropdown alfabético con los 96 clubes (arriba a la derecha) que agranda el punto elegido y lo etiqueta con flecha. No es un campo de texto con autocompletado (Plotly no lo soporta nativo sin Dash/JS aparte), es un desplegable buscable con el teclado. Se aplicó a los 4 gráficos.
   - Detalle no obvio: el botón del buscador reemplaza `layout.annotations` por completo, así que sin cuidado borraría las anotaciones fijas del gráfico (etiquetas de cuadrante en Eficiencia, "tendencia lineal" en Puntos vs. diferencia de gol). Se agregó el parámetro `base_annotations` para que cada botón del buscador las preserve y solo agregue la del club elegido encima.
   - Limitación conocida y aceptada: el filtro de liga y el buscador de club son dos menús independientes que both tocan `annotations`/`marker.size` — usar uno después del otro puede resetear el efecto visual del otro (ej. buscar un club y después cambiar de liga borra el resaltado). Es una limitación de los dropdowns estáticos de Plotly (no hay estado compartido entre controles sin Dash/JS a medida); no se resolvió por quedar fuera de alcance para un notebook.
   - Efecto colateral en el gráfico de residuo: la línea de "tendencia lineal" terminaba en la esquina superior derecha, justo donde vive el buscador — la etiqueta quedaba tapada. Se movió al inicio de la línea (esquina inferior izquierda, vacía en ese gráfico).

**Segunda ronda (mismo día, tras ver la captura real en uso): se descartó el enfoque de `updatemenus` de Plotly por completo.**

El usuario probó el buscador de club (punto 4 arriba) y pidió dos cosas que el dropdown de Plotly no puede dar: (1) que los controles queden a la derecha del gráfico, no superpuestos — al abrir el desplegable, la lista de opciones se dibujaba encima del gráfico; y (2) autocompletado de verdad (escribir "j" y que aparezca "Juventus"), no una lista de 96 opciones para scrollear. Plotly no tiene un control de texto con autocompletado nativo (eso requeriría Dash o JS a medida).

**Solución: se reemplazaron `league_dropdown()`/`club_search_dropdown()` por `render_with_sidebar()`** en `viz_theme.py` — en vez de controles de Plotly (`updatemenus`), arma una barra lateral con HTML/CSS genuino (flexbox: gráfico a la izquierda, controles en una columna aparte a la derecha, nunca superpuestos) y JS puro:
- **Buscador de club**: `<input list="...">` + `<datalist>` — autocompletado nativo del navegador (HTML5, sin librerías). Escribir "j" filtra a "Juventus" en el desplegable nativo.
- **Filtro de liga**: `<select>` nativo.
- Ambos controles llaman `Plotly.restyle`/`Plotly.relayout` sobre el `div` del gráfico ya renderizado (identificado con un `div_id` único por gráfico vía `uuid`) — JS puro, sin depender de un kernel de Python vivo, así que el notebook se sigue viendo interactivo sin volver a ejecutar.
- Se arma con `fig.to_html(full_html=False, include_plotlyjs='cdn', div_id=...)` + `IPython.display.HTML(...)`, ya no con `fig.show()` — por eso se sacó `pio.renderers.default = 'notebook_connected'` de la celda de imports (ya no hace falta, no se usa `fig.show()` para estos 4 gráficos).
- **Verificación real, no solo con kaleido** (kaleido no renderiza el HTML/JS custom de la barra lateral, solo la figura Plotly): se instaló `playwright` + Chromium headless, se extrajo el HTML de cada celda ya ejecutada, y se comprobó en un navegador de verdad que (a) el buscador filtra correctamente a "Juventus" al tipear "j", (b) seleccionar un club agranda y etiqueta el punto sin borrar las anotaciones fijas, (c) el filtro de liga oculta las demás trazas y ambos controles combinan bien, (d) en el gráfico de residuo el colorbar y la barra lateral no se pisan. `playwright`/Chromium se instalaron solo para esta verificación, no son dependencia del notebook.

### Sección 2 (Porteros) — revisión y fix del índice compuesto

El usuario pidió opinión sobre los dos gráficos de porteros y si se aprovechaba toda `leagues_gk.csv`. Se encontró un problema real en el índice compuesto del ranking de porterías: `Save% + CS% − GA90` no triangula 3 señales independientes — **CS% y GA90 correlacionan −0.84** (casi la misma señal, ambas dependen directamente de goles recibidos), así que el índice pesaba esa señal casi el doble. Fix: se sacó CS% del índice, quedó `Save% − GA90` (dos señales genuinamente distintas: tasa de atajadas vs. goles recibidos por partido).

Se detectó además que `SoTA` (tiros a puerta enfrentados) no se usaba en ningún gráfico, pese a ser la columna que permite separar la exigencia real del arquero de la calidad de la defensa del equipo (GA90/CS% están confundidas con eso: un arquero detrás de una gran defensa tiene buenos números sin atajar mejor — confirmado con corr(SoTA, GA90)=0.73, corr(SoTA, CS%)=−0.66). Se agregó un tercer gráfico de la sección: **SoTA vs. Save%** (mismo criterio que Eficiencia de definición — separar volumen/exigencia de tasa de acierto en vez de mezclarlos). Se verificó primero que las dos métricas son casi independientes (corr=−0.12) antes de armar el gráfico, para no repetir el error de la nube 1-D. Penales (`Penalty Kicks_*`) se dejaron afuera a propósito: muestra chica por equipo (0–12 penales en toda la temporada), un Save% de penales sobre esa base es ruido, no señal.

### Corrección de tono: el usuario es de México, no Argentina

Se venía usando voseo rioplatense ("vos", "querés", "escribí", "pasá el mouse") en el código (`viz_theme.py`, `eda.ipynb`) sin que nadie lo pidiera — el usuario avisó que le sonaba raro. Se corrigió a tuteo neutro en todo el proyecto (`pasa el mouse`, `escribe un club`, etc.). Ver también memoria de feedback guardada sobre esto para no repetirlo en futuras sesiones.

### EDA de jugadores (`code/eda_players.ipynb`)

Segundo EDA del proyecto, a partir de datos de Understat (no fbref): un CSV por liga con columnas ofensivas de **jugador** (`goals`, `a`, `xG`, `xA`, `xG90`, `xA90`, `apps`, `min`). El EDA original de equipos se renombró a `code/eda_teams.ipynb` para distinguirlo de este.

- **Carga**: 5 CSVs (`data/{bundes,seriea,ligue1,laliga,premier}-players.csv`, separador `;`), columna `liga` asignada por archivo (a diferencia de equipos, acá no hace falta inferir por rango de filas).
- **Limpiezas de datos reales encontradas**: nombres con entidades HTML sin decodificar (ej. `M&#039;Bala Nzola` → `html.unescape`); jugadores transferidos a mitad de temporada con `team` como `"Angers,Rennes"` (dos equipos concatenados) → se queda con el **último** equipo (decisión del usuario).
- **Filtro de minutos mínimos**: ≥900 min (confirmado por el usuario, ya lo había visto en otros análisis) — sin esto `xG90`/`xA90` de jugadores con pocos minutos es ruido puro. De 2775 jugadores a 1583 tras el filtro.
- **3 scatters interactivos** (Plotly + `render_with_sidebar`, buscador de jugador + filtro de liga, igual patrón que equipos):
  1. Goles vs. xG (línea y=x, sobre/bajo-rendimiento de definición)
  2. Asistencias vs. xA (mismo concepto para creación)
  3. xG90 vs. xA90 (perfil ofensivo: killer puro / creador puro / todocampo, líneas de referencia en el promedio de cada eje)
- **2 boxplots** (`league_box_figure`, sin barra lateral): xG90 y xA90 por liga, para comparar nivel ofensivo entre las 5 ligas a nivel jugador (no solo equipo).
- **Generalización de `viz_theme.py`** para reusar con jugadores en vez de solo equipos: `render_with_sidebar()` y `league_box_figure()` ahora aceptan `name_col` (antes hardcodeado a `"Squad"`) y `render_with_sidebar()` además `search_label` para el texto del buscador ("jugador" vs. "club").
- **Bug real encontrado y corregido en `render_with_sidebar`**: la lógica JS del filtro de liga y del buscador asume que las trazas "extra" (`extra_traces`, ej. una línea de referencia) van **después** de las trazas de liga en la figura — si se agregan antes (como se hizo al prototipar los scatters de Goles/Asistencias, con la línea y=x agregada primero), los índices de traza quedan desalineados: el filtro de liga esconde/muestra la liga equivocada y el resaltado de búsqueda aplica el array de tamaños de una liga a la traza de otra (verificado con Playwright inspeccionando `data[i].marker.size` en el navegador — longitudes de array no coincidían con el tamaño real de esa liga). Fix aplicado en el notebook (no en `viz_theme.py`): agregar siempre las trazas de liga primero y la(s) traza(s) extra al final. Documentado como comentario en las celdas del notebook para no repetir el error.
- Verificado con `nbclient` (ejecución completa) + Playwright (búsqueda de jugador, filtro de liga, inspección de `marker.size` por consola) antes de dar por terminado, mismo criterio que el EDA de equipos.

### Sitio estático para deploy en Vercel (`web/`)

El usuario quiere publicar todos los gráficos (equipos + jugadores, interactivos y estáticos) en Vercel. Como Vercel sirve archivos estáticos y los notebooks no son deployables, se creó una carpeta `web/` separada que **reusa** el código de los notebooks pero lo porta a scripts `.py` que generan HTML de verdad. Los notebooks (`code/*.ipynb`) siguen siendo el laboratorio donde se prototipa cada gráfico; una vez que un gráfico queda listo ahí, su código se porta a mano a `web/charts/`.

**Estructura:**

```
web/
  site_utils.py     # ChartPage, plantillas de página + índice, embed de PNG de matplotlib
  charts/
    teams.py         # carga+limpieza de los 5 CSVs de equipo + 9 funciones chart_*() -> ChartPage
    players.py        # carga+limpieza de los 5 CSVs de jugador + 5 funciones chart_*() -> ChartPage
  build.py            # limpia dist/, llama build() de ambos módulos, escribe cada página + index.html
  dist/                # salida generada (gitignored) — esto es lo que apunta Vercel
vercel.json            # outputDirectory: web/dist
.gitignore              # web/dist/, __pycache__/, .ipynb_checkpoints/
```

- **Refactor en `code/viz_theme.py`** (sin cambiar el comportamiento en los notebooks): `render_with_sidebar()` y `render_plot()` ahora son wrappers finos de dos funciones nuevas que devuelven el HTML como **string** en vez de mostrarlo directo — `sidebar_chart_html()` y `plot_html()`. Así el mismo código sirve para `display(HTML(...))` en un notebook y para escribir a un archivo `.html` en el sitio, sin duplicar la lógica de JS/Plotly.
- **14 gráficos portados** (9 de `eda_teams.ipynb` + 5 de `eda_players.ipynb`): los 3 estáticos de matplotlib (2 radares + ranking de porterías) se exportan a PNG (`web/dist/charts/assets/*.png`) y se embeben con `<img>`; los 11 interactivos de Plotly (con y sin barra lateral) se embeben igual que en los notebooks, standalone (`include_plotlyjs="cdn"`).
- **Landing page** (`index.html`) con tarjetas agrupadas por sección (Equipos / Jugadores), cada una linkeando a `charts/<slug>.html`. Cada página de gráfico tiene un link "← Volver" al índice.
- `web/build.py` es idempotente (borra y regenera `dist/` entero cada vez) — se corre con `python build.py` desde `web/`.
- Verificado end-to-end con Playwright sobre el `dist/` generado (no solo con `kaleido`): el índice, una página matplotlib (radar) y una página Plotly con barra lateral (Goles vs. xG) — buscador de jugador, resaltado y línea de referencia funcionando igual que en el notebook.
### Repo en GitHub y deploy a Vercel

- El proyecto se llama **futviz** (nombre elegido por el usuario entre 3 opciones — corto, es el nombre que ya venía usando informalmente para la carpeta raíz `futviz_pl`, sirve como marca para todo lo que siga en ciencia de datos deportiva, no solo este EDA).
- Se instaló **GitHub CLI** (`gh`, vía `winget`) porque no había ni `gh` ni `vercel` CLI ni Node/npm en la máquina. Login interactivo por dispositivo (`gh auth login --web`, código de un solo uso en el navegador) — cuenta `OliverBur`.
- Se creó el repo **https://github.com/OliverBur/futviz** (público) con `gh repo create --source=. --push`, con el primer commit (código + notebooks + `web/`).
- `.claude/settings.json` y `.claude/settings.local.json` se sacaron del `git add -A` inicial (quedaron staged por accidente) y se agregó `.claude/` al `.gitignore` — es config local de permisos de Claude Code, no algo del proyecto.
- **Detalle importante para el deploy**: `web/dist/` (el sitio generado) inicialmente estaba en `.gitignore`. Se decidió sacarlo del gitignore y **commitear el HTML ya generado**, en vez de pedirle a Vercel que corra `python web/build.py` en su propio build — evita depender de que el entorno de build de Vercel tenga Python/matplotlib/plotly disponibles y configurados. Contrapartida: hay que acordarse de correr `python web/build.py` + commitear `web/dist/` de nuevo cada vez que cambie algún gráfico (no es automático).
- **Deploy a Vercel en sí queda pendiente** (no se hizo en esta sesión — no se instaló Node/Vercel CLI porque el usuario eligió la vía de GitHub CLI en vez de esa opción). Próximo paso: conectar el repo desde el dashboard de Vercel (Add New Project → Import `OliverBur/futviz` → framework "Other", sin build command, root directory = raíz del repo — `vercel.json` ya apunta `outputDirectory` a `web/dist`).

### Sitio responsivo (mobile / tablet / desktop)

A pedido del usuario, se hizo responsiva toda la página (`web/`), gráficos incluidos — hasta acá solo se había probado en desktop. Cambios en `code/viz_theme.py` (afectan por igual a los notebooks y al sitio, ya que ambos comparten las mismas funciones):

- **Gráficos Plotly** (`sidebar_chart_html`, `plot_html`): antes tenían ancho/alto fijos en px (`fig.update_layout(width=..., height=...)`), lo que los hacía desbordar en pantallas angostas. Ahora `autosize=True` + `config={"responsive": True}` + el div se envuelve en un contenedor con `aspect-ratio` fija (`width/height` del tamaño "de diseño") y `width:100%` hasta un `max-width` — el gráfico se achica/agranda con el contenedor sin deformarse, sin necesidad de JS de resize manual (Plotly.js con `responsive:true` ya usa `ResizeObserver` internamente).
- **Barra lateral** (`sidebar_chart_html`): el layout pasó de `display:flex` fijo a `flex-wrap:wrap` — en pantallas angostas (<~600px de contenido) la barra lateral cae debajo del gráfico en vez de comprimirlo.
- **Leyenda de Plotly en mobile**: con el gráfico angosto, la leyenda vertical a la derecha (default) se comía ~40% del ancho. Se agregó JS (`updateLegendLayout()`, en resize + al cargar) que mide el ancho real del div del gráfico y cambia la leyenda a horizontal abajo cuando ese ancho es <420px (con margen inferior extra para que no se pise con el título del eje X) — verificado que ya no hay superposición.
- **Imágenes estáticas de matplotlib** (radares, ranking de porterías): en vez de dejarlas encoger con `max-width:100%` hasta volverse ilegibles en mobile (el radar tiene 5 subplots), se les puso `min-width:600px` + un contenedor `.chart-scroll` con `overflow-x:auto` — en mobile el texto se mantiene legible y el usuario scrollea horizontal para ver el resto, en vez de perder detalle. Confirmado con Playwright que el contenedor es scrolleable y que la página en sí (`document.documentElement`) no tiene overflow horizontal en ningún breakpoint.
- **Plantillas de página** (`web/site_utils.py`): media queries a 640px para reducir paddings/tamaños de fuente del header e `index.html` (grid ya era responsivo con `auto-fill`, se ajustó el `minmax` a `min(260px, 100%)` para no desbordar en viewports <260px).
- Verificado con Playwright en 3 breakpoints (375px mobile, 768px tablet, 1440px desktop) sobre `web/dist` ya generado: índice, un scatter con barra lateral, un boxplot y el radar — sin overflow horizontal de página en ningún caso, controles y leyenda usables en mobile.
- Como el cambio vive en `viz_theme.py`, aplica también a los notebooks (`eda_teams.ipynb`/`eda_players.ipynb`) — se re-ejecutaron ambos con `nbclient` para regenerar las salidas embebidas con el nuevo comportamiento responsivo.

## Próximos pasos

- [x] ~~Revisar los gráficos abiertos en un kernel real de Jupyter~~ — hecho, varias rondas (colores, solapamiento, ajustes finos)
- [x] ~~Decidir si se mantienen los dos notebooks o se consolida en uno solo~~ — hecho: solo queda `eda.ipynb`, `analisis1.ipynb` se eliminó
- [ ] Notebook específico: exploración táctica con `overall` (estilos de juego a fondo)
- [ ] Notebook específico: por qué destacó el Lens (o el caso que corresponda esa temporada)
- [ ] Evaluar conseguir data a nivel de partido o jugador si se quiere ir a algo más avanzado (rachas, home/away, xG real)
- [x] ~~Si se necesita interactividad más adelante, evaluar Plotly~~ — hecho: los 4 scatters de equipo por equipo son Plotly con hover + filtro por liga (ver sección arriba)

## Historial de sesiones

### 2026-07-25 (tarde) — sitio estático para Vercel
- El usuario pidió subir todos los gráficos a Vercel. Antes de picar código, se propuso una estructura (`web/` separado de `code/`, notebooks como laboratorio, scripts `.py` como fuente para el sitio) y se confirmaron 2 decisiones con el usuario: suben **todos** los gráficos (incluyendo los matplotlib estáticos, como PNG embebido) y el layout es **landing + una página por gráfico** (no todo en una sola página larga).
- Se construyó `web/` completo: refactor de `viz_theme.py` para separar generación de HTML (string) de la visualización en notebook, `web/charts/{teams,players}.py` con los 14 gráficos portados 1:1 desde los notebooks, `web/site_utils.py` con las plantillas de página/índice, `web/build.py` como orquestador, y `vercel.json`.
- Verificado con `nbclient`-equivalente manual (`python build.py`) + Playwright sobre el HTML generado, no solo visualmente: se confirmó que el buscador de jugador y el filtro de liga siguen funcionando igual que en los notebooks.
- Detalle completo en la sección de referencia "Sitio estático para deploy en Vercel" más arriba. El deploy real a Vercel (requiere `git init` — el repo no es git todavía — y credenciales/decisión del usuario) queda como próximo paso, no se hizo en esta sesión.

### 2026-07-25 (EDA de jugadores)
- El usuario consiguió datos de jugadores de Understat (5 CSVs, uno por liga) con columnas ofensivas: goles, asistencias, xG, xA, xG90, xA90. Renombró el EDA de equipos existente a `eda_teams.ipynb` para dejar `eda_players.ipynb` como notebook nuevo.
- Se propuso alcance (3 scatters de jugador + boxplots de liga) y el usuario confirmó rápido, incluyendo el filtro de 900 min ("justo te iba a decir eso... lo he visto en varios gráficos") y la decisión sobre jugadores con doble equipo (quedarse con el último).
- Se construyó `eda_players.ipynb` completo (carga + limpieza + filtro + 3 scatters + 2 boxplots), reusando y generalizando helpers de `viz_theme.py` (`name_col`, `search_label`) para que funcionen tanto con equipos como con jugadores.
- Se encontró y corrigió un bug real de orden de trazas en `render_with_sidebar` (ver sección de referencia arriba) durante la verificación con Playwright — no se detectó a simple vista en las capturas iniciales (la anotación de texto se veía "correcta" por coincidencia, ya que no depende del índice de traza), solo se confirmó inspeccionando `marker.size` por consola del navegador.

### 2026-07-22
- Ajustamos la normalización del radar de perfil de liga: el usuario ya había cambiado de min/max de las 5 ligas a percentiles 5/95 de equipos individuales para evitar que la peor liga cayera a 0, pero eso aplastaba las 5 formas al centro (poca diferenciación visual, ej. posesión con rango de 0.002 entre ligas).
- Solución aplicada (intento 1): volver a normalizar contra el min/max de las 5 ligas, pero con padding del 15% (mapea a rango 0.15–0.85) para que el peor no llegue a 0 ni el mejor sature en 1. Confirmado con el usuario antes de aplicar.
- Se agregó un segundo gráfico: los mismos 6 ejes pero con las 5 ligas sobrepuestas en un solo radar (antes eran 5 subplots separados), para comparar directamente dónde se separa cada liga.
- **Cambio de fondo (mismo día, más tarde)**: el usuario objetó cualquier variante min-max — el problema no es el padding sino que anclar el mínimo del grupo a 0 siempre cuenta una historia distorsionada (ej. 170 vs 180 tiros son casi iguales en la realidad pero min-max los separa igual que si fueran 90 vs 180).
- Solución intento 2: escala proporcional al máximo (`value / max`, no `(value - min) / (max - min)`). El 0 del eje es el 0 real de la métrica, no la peor liga, así que las distancias en el radar reflejan la proporción real entre ligas.
- Desvío (sigmoide sobre z-score): se probó una variante con `z-score` de cada liga + sigmoide `1/(1+e^(-z/k))`. Se **descartó** tras analizarla con datos: estandarizar 5 medias por su propio desvío siempre da spread completo, así que inventaba diferencias donde no las hay (ej. Posesión, diferencia real 0.0 pts %, mostraba spread 0.87; Centros —sin diferencia real— salía con más spread que Faltas, la diferencia más real). El z-score mide rank/significancia, no magnitud, que es lo que el usuario quiere.
- **Decisión final del método: `value / max`.** Argumento decisivo: el spread que genera en cada eje **rastrea la diferencia real** entre ligas (0.06 donde no hay diferencia, 0.34 donde es grande), mientras que z-score y min-max meten ~0.8 de spread en todos los ejes por igual (drama falso). Es además lo que el usuario describió desde el principio (180/170/90 → 1.0/0.94/0.5).
- **Selección de métricas del radar** (medida con eta² = fracción de varianza que explica la liga vs. ruido entre equipos, + rango relativo para que se vea en value/max, + correlación para descartar redundantes): se sacaron Posesión (~50% fija para todas por construcción), Tiros y Centros (eta² ~0.02, casi idénticas entre ligas). Set final de 7 ejes: **Goles, G/Sh, CS%, Tackles (p90_TklW), Intercepciones (p90_Int), Offsides (p90_Off), Faltas**. Offsides e Intercepciones se eligieron por señal alta y baja redundancia (Offsides corr 0.15 con todo = dimensión táctica nueva; Intercep. complementa Tackles sin duplicarlo). Se descartaron por redundancia: Asistencias (corr +0.98 con Goles) y Goles recibidos/GA90 (corr −0.84 con CS%).
- Aplicado en `code/eda.ipynb`, celda del radar (`RADAR_METRICS`, `norm = league_avg / league_avg.max()`). Nota: durante la sesión el usuario dejó en la celda una variante manual (z-score sobre el error estándar de cada media + sigmoide k=1.5); se reemplazó por value/max según su confirmación explícita.
- Se ejecutó `eda.ipynb` completo con `nbclient` (se instaló `nbclient`/`nbformat` porque no estaban disponibles) para regenerar las imágenes incrustadas. Verificado visualmente: las 5 ligas ahora muestran formas distintas y honestas.
- Se documentó todo el razonamiento (comparación de métodos + selección de métricas, con tablas de eta²/spread) en una sección permanente de la bitácora: "Radar de perfil de liga — decisiones de método".
- **Mejora de estilo de los dos radares** (pulido tipográfico, sin cambiar datos ni paleta): el título se partió en título grande bold + subtítulo en itálica con el detalle metodológico (antes iba todo en el paréntesis del título); nota de fuente ("Datos: fbref · 2025-26") abajo; nombres de liga en VERSALITAS con su color; marcadores en los vértices; un anillo de referencia (subplots) / tres (sobrepuesto) para leer magnitud; leyenda del sobrepuesto en fila horizontal abajo. Se mantuvo la paleta por liga fija del proyecto (no se tocó por consistencia con el resto de gráficos). Prototipado en scratchpad y verificado a PNG antes de aplicar.
- **Tabla junto al radar sobrepuesto**: se agregó a la derecha (layout de 2 paneles con `gridspec`: radar polar + eje de tabla con `axis('off')`) una tabla que cuantifica el spread de cada eje. El usuario reincorporó Tiros al radar (vuelve a 8 ejes) **a propósito**: aunque casi no discrimina (era el eje que se había sacado por eta² bajo), le pareció un insight interesante mostrar que las 5 ligas convergen ahí mientras difieren en todo lo demás — se mantiene.
- **Revisión de estilo pedida explícitamente ("sé honesto y constructivo")**: se detectaron y corrigieron 3 problemas reales, no solo estéticos:
  1. La tabla original mostraba `mín/máx` crudo ordenado ascendente → la barra más larga (más peso visual) terminaba siendo la del eje **menos** interesante (Tiros, 0.93), y la más corta la del eje más interesante (CS%, 0.66). Se invirtió a **`1 − (mín/máx)` en %, ordenado descendente**: ahora la barra más larga y la fila de arriba son el eje que más separa a las ligas (CS% 34%), alineando peso visual con información. Tiros queda al fondo con 7%, visible como el insight que el usuario quería resaltar, sin dominar la tabla.
  2. El título del radar sobrepuesto repetía literalmente "Perfil de estilo por liga" (idéntico al radar de arriba) → se cambió a **"Dónde se separa cada liga"**, con el subtítulo complementando ("...con el detalle de separación por eje a la derecha") en vez de reafirmar lo mismo. Se agregó la nota de fuente ("Datos: fbref · temporada 2025-26") abajo a la derecha, igual que en el radar de 5 subplots — antes faltaba en este gráfico.
  3. (Mencionado pero no corregido, es inherente a la forma) con 5 ligas × 8 ejes superpuestos hay tramos donde 2 líneas de color parecido se pisan (ej. Serie A/Premier League) — no se tocó porque los 5 subplots de al lado ya resuelven ese problema de lectura individual.
- **Rediseño del scatter "Eficiencia ofensiva"** (`code/eda.ipynb`, celda `6d080b1c`), a pedido del usuario ("¿se puede mejorar?"). Hallazgo de fondo, no solo estético: el gráfico original graficaba **G/Sh vs. G/SoT**, pero esas dos métricas están relacionadas por construcción — `G/Sh = SoT% × G/SoT` (identidad verificada con los datos, diferencia máxima 0.006 de redondeo) — por eso la nube de puntos era casi 1-D (r=0.88, una diagonal), no un hallazgo real sino un artefacto de la fórmula.
- **Fix**: se cambió a **SoT% (precisión, % de tiros que van a puerta) vs. G/SoT (definición, goles por tiro a puerta)**, el par que sí mide dos habilidades independientes (r=0.28, casi sin relación). Con esto la nube tiene forma 2-D real y aparecen casos que antes quedaban ocultos por la colinealidad: Bayern Munich es un outlier de precisión (44% SoT%, el más alto por lejos) sin ser el más letal; Dortmund es al revés (0.39 G/SoT, la definición más alta) con precisión apenas sobre el promedio.
- Se agregaron líneas de referencia en la media de cada eje (creando 4 cuadrantes con etiqueta: "certeros y letales", "mucho a puerta poca pegada", etc.) y se aplicó el mismo tratamiento tipográfico título+subtítulo+fuente que ya tenían los radares, por consistencia.
- Prototipado en scratchpad con números de correlación calculados antes de decidir (no a ojo), verificado a PNG, y ejecutado con `nbclient` para regenerar la imagen incrustada.
- **Migración a Plotly de los 4 scatters de equipo por equipo** (Eficiencia de definición, Verticalidad, Portería vs. resultado, Puntos vs. diferencia de gol), a pedido del usuario: quería poder identificar qué equipo es cada "bolita" (hover) y filtrar por liga (dropdown abajo a la derecha). Esto era justo el próximo paso que ya estaba anotado en la bitácora ("evaluar Plotly como punto intermedio antes de JS/D3"). Detalle completo en la sección de referencia "Plotly — gráficos interactivos" más arriba (no repetido acá): tema Plotly nuevo en `viz_theme.py`, renderer `notebook_connected` verificado para que el notebook siga viéndose sin re-ejecutar, y un bug real de leyenda/colorbar superpuestos que se encontró y corrigió en el gráfico de residuo. El radar y las barras se quedaron en matplotlib (no se tocaron).
- Instalado `plotly` y `kaleido` en el entorno (no estaban).
- **Revisión general pedida explícitamente** ("revisa todo lo que llevamos, dime si ves algo mejorable"). 3 hallazgos, todos de documentación/limpieza, no del contenido de los gráficos en sí (esos ya habían pasado varias rondas de revisión):
  1. La sección "Estado actual del proyecto" de esta bitácora describía una estructura de 4 bloques que ya no existía (las secciones 3 y 4 se habían borrado, "Verticalidad" también, nombres/fórmulas de varios gráficos habían cambiado) y seguía mencionando `analisis1.ipynb`, que ya no existe en `code/` — se consolidó todo en `eda.ipynb`. Corregido para reflejar la estructura real (2 bloques → ahora 3, ver abajo).
  2. La celda de carga de datos calculaba `p90_Crs` y `p90_Fld` sin que ningún gráfico los usara ya (quedaron huérfanos tras sacar Verticalidad). Se sacaron del loop.
  3. El título del radar de 5 subplots usaba coordenadas `x` sueltas (0.42/0.35/0.88) pensadas para centrar sobre esa figura puntual — frágil ante cualquier cambio de ancho. Se alineó a la izquierda/derecha con las mismas fracciones fijas (0.015/0.985) que usa el resto de los gráficos del notebook.
- **Nueva sección "3. Identidad de cada liga"**, a partir de revisar qué columnas de los `leagues_*.csv` seguían sin usarse. 3 gráficos nuevos, todos con el mismo formato (box plot + puntos individuales por equipo, con hover — helper nuevo `league_box_figure()` en `viz_theme.py`, sin barra lateral porque las 5 ligas ya están una al lado de la otra) y verificados con eta²/CV antes de construir, no a ojo:
  - **Paridad competitiva** (`pt_Team Success_PPM`, columna que había quedado sin usar tras sacar el chart de residuo): coeficiente de variación de los 20 equipos por liga. Bundesliga la más desigual (38%), Premier League y La Liga las más parejas (31%) — coincide con el folklore futbolero (Bayern y el resto vs. Premier "parejísima") pero sale de los números, no de la percepción.
  - **Edad de plantilla** (`ov_Age`, sin usar hasta ahora): eta²=0.14. La Liga la más veterana, Ligue 1 la más joven — con un outlier real confirmado en los datos crudos (no un bug del gráfico): Strasbourg, edad promedio 21.5, la plantilla más joven de las 5 ligas por lejos (conocida por su estrategia de fichajes jóvenes bajo el grupo propietario BlueCo/Chelsea).
  - **Disciplina: tarjetas amarillas** (`p90_CrdY`, ya se calculaba pero no se graficaba): eta²=0.15. La Liga claramente por encima del resto (~2.2 vs. ~1.85–1.91).
  - Se agregó también `render_plot()` a `viz_theme.py` (misma lógica de `render_with_sidebar` — `fig.to_html` + `display(HTML(...))`, JS puro, sin depender de un kernel vivo — pero sin la barra lateral, para gráficos donde las 5 ligas ya se comparan directamente).
  - Verificado con `nbclient` + capturas vía Playwright antes de dar por terminado.

### 2026-07-21
- Definimos el alcance del proyecto y la idea de arrancar con un EDA general antes de notebooks específicos.
- Elegimos los 8 puntos de análisis del EDA entre varias opciones propuestas.
- Definimos la identidad visual (paleta por liga, tema matplotlib) — primera vez que el usuario define una identidad visual para gráficos.
- Se armó `viz_theme.py` y `analisis1.ipynb` completo (carga, limpieza, merge de los 5 CSVs + 9 gráficos), verificado que corre sin errores.
- Se generó `eda.ipynb` con las salidas ya renderizadas porque `analisis1.ipynb` no mostraba nada al no haberse ejecutado en un kernel real.
- Se creó esta bitácora.
