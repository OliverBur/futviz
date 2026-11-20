# Plan: siete gráficas nuevas para Equipos

Decidido con el usuario el 2026-11-19 (todas aprobadas; se hacen por lotes). Hoy Equipos tiene seis vistas, todas dispersiones con una cifra por equipo y temporada (`web/charts/teams.py`). Estas siete usan lo que ya tenemos y casi no se aprovecha: el resultado y el xG de **cada partido**, los **tiros** con minuto y tipo de jugada, las **alineaciones** y el **ELO**.

## Datos (verificado el 2026-11-19)

| Fuente | Qué trae | Ojo |
|---|---|---|
| `data/<t>/partidos.csv` | `temporada, liga, game_id, fecha, local, visita, goles_l, goles_v, xg_l, xg_v` (1,826 / 1,826 / 1,752 / 1,752 / 1,752 partidos y 2026-27 en curso) | el xG del partido probablemente incluye penales: comprobarlo antes de mezclarlo con el xG «sin penales» del resto del sitio |
| `data/<t>/shots.csv` | un tiro por fila: `team, rival, minute, situation, body_part, result, xg, location_x/y, player, game_id` | `rival` vacío en 4 partidos (`web/charts/xg_equipos.py` ya los resuelve); penales y autogoles se tratan como en el resto del sitio |
| `data/<t>/alineaciones.csv` | un jugador por partido: `time` (minutos), `xG, xA, key_passes, goals, position, roster_in/out` | **no existe para 2026-27**: esa temporada no tiene esta vista |
| `data/processed/teams_all_seasons.csv` | FBref (posesión, tiros, faltas…) + `elo_pre/medio/fin` | 2026-27 sin ELO. Equipos: `Squad` en nombre de FBref; los tiros traen el de Understat; se cruzan con `nombres.club_visible` |
| `web/charts/xg_equipos.py` | xG a favor y en contra por partido, sin penales, ya por equipo-temporada | léelo antes de calcular nada de equipos: ya resuelve los cruces de nombres y los huecos (6 equipo-temporada con un partido de más o de menos en Understat) |

No tenemos presión (PPDA), pases ni posiciones de jugadores en el campo. No proponer nada que dependa de eso.

## Convenciones del proyecto (obligatorias)

- Español de México con tuteo (nunca voseo). Sin lenguaje de marketing. Sin barra de metadatos bajo el título ni «N min de lectura».
- Cada vista: **pregunta** (la línea verde, en `web/charts/preguntas.py`), **título**, **bajada de ≤108 caracteres** (cabe en una línea en escritorio), «Qué más mirar», «Por qué así» (desplegable con el método y los límites) y un texto «Con estos filtros». **Toda cifra en un texto sale del código o de los datos**, nunca escrita a mano. Los textos dinámicos pueden vivir solo en JS (como `edadLectura.js`): no hace falta gemelo en Python.
- Una vista con tabla propia manda su payload con `react_views.registrar_payload` y lo pide bajo demanda con `datos.cargarDatos` (ejemplos: `MapaTiros.jsx`, `EdadVista.jsx`, `web/charts/edad.py`). Mantén el payload chico (agrega en Python, en el build, determinista; semilla fija si hay azar). Todo debe funcionar abierto con doble clic (`file://`).
- Una vista nueva se registra con un tipo en `web/react/src/main.jsx` (`VISTAS`), una tupla en `PESTANAS` y la llamada en `build()` de `web/charts/teams.py`, y una pregunta en `preguntas.py`. El menú final lo reordena el integrador.
- Diseño: mismo lenguaje que el resto (SVG propio o MUI X Charts, tokens de `theme.jsx`, rejilla suave, hover con los números), **claro y oscuro**, y a **390 px** sin desborde horizontal. SVG con `role="img"` y `aria-label` descriptivo.
- Las cifras de los textos «Por qué así» deben mencionar los límites reales de la medición (por ejemplo, que el xG de Understat suma más de lo que entra).
- La temporada que va en curso (2026-27, 6 a 9 partidos por equipo) se marca como tal y los textos no concluyen nada de ella.

## Las siete vistas

| # | Slug | Título | Pregunta | Qué dibuja | Datos |
|---|---|---|---|---|---|
| 1 | `tabla-esperada` | Tabla real vs. esperada | ¿Quién está en el lugar que merece? | Por liga y temporada, una fila por equipo: puntos reales y puntos esperados (xPts) unidos por una línea (mancuernas), ordenados por la tabla real, con la posición real y la esperada | `shots.csv` o `partidos.csv` |
| 2 | `forma` | Forma durante la temporada | ¿Viene mejorando o cayendo? | Selector de equipo y temporada: diferencia de xG por partido en ventana móvil de 6 partidos, con los resultados (G/E/P, local o visita) como marcas | `partidos.csv` |
| 3 | `origen-xg` | De dónde sale el xG | ¿Vive de los córners o construye jugando? | Barras apiladas por equipo: jugada abierta, córner, tiro libre directo, otro balón parado. A favor o en contra; en % o por partido; filtro de liga y temporada | `shots.csv` |
| 4 | `cantidad-calidad` | Cantidad vs. calidad de los tiros | ¿Dispara mucho o espera la ocasión clara? | Dispersión: tiros por partido contra xG por tiro | `shots.csv` |
| 5 | `local-visitante` | Local vs. visitante | ¿Quién depende de su estadio? | Dispersión con diagonal: diferencia de xG por partido en casa contra fuera | `partidos.csv` |
| 6 | ~~`dependencia`~~ | ~~Dependencia de la plantilla~~ | | **Descartada por el usuario el 2026-11-20** | |
| 7 | `trayectoria-elo` | Trayectoria del club en ELO | ¿Cómo ha cambiado la fuerza de este club? | Líneas con el ELO por temporada, con selector de clubes (reutiliza el componente de líneas de la vista 2) | `teams_all_seasons.csv` (sin 2026-27) |

**Método de la 1 (xPts):** puntos esperados de cada partido a partir de las probabilidades de ganar, empatar y perder que dan los xG de los tiros de ese partido (los goles de cada equipo como suma de Bernoullis con la probabilidad `xg` de cada tiro, independientes entre equipos). Hay que documentar qué se hace con penales y autogoles, comparar contra la alternativa de Poisson sobre el xG total del partido, y reportar: correlación entre puntos reales y esperados por liga-temporada, y cuánto de la diferencia (real − esperada) se repite de una temporada a la siguiente. Si casi no se repite, la vista lo dice.

Las vistas 4 y 5 son dispersiones normales (`ScatterVista`, con `referencias`, líneas de percentil y cuadrantes como las de jugadores): solo hay que calcular las columnas nuevas por equipo-temporada en el build, sin regenerar los CSV.

## Lotes

1. **Lote 1 (hecho, en la rama `integra-equipos`):** vistas 1, 2 y 3. La vista 2 dejó el dibujo de líneas como componente reutilizable (`web/react/src/LineasSvg.jsx`).
2. **Lote 2 (en marcha, 2026-11-20):** vistas 4 y 5 (un agente: columnas nuevas en el cálculo de equipos y dos configuraciones de dispersión) y vista 7 (otro agente, con `LineasSvg`). La vista 6 se descartó.
3. **Lote 3:** preguntas de la portada y el buscador, y verificación completa.

## Menú final propuesto de Equipos

- **Temporada:** Tabla real vs. esperada · Forma
- **Ocasiones:** Goles vs. xG del equipo · Ocasiones a favor y en contra · De dónde sale el xG · Cantidad vs. calidad de los tiros
- **Defensa:** Goles recibidos vs. xG en contra
- **Contexto:** Puntos vs. xG · Local vs. visitante · Trayectoria ELO · Distribución por liga
- **Crea tu gráfico**

## Reglas de integración

- **Los filtros van a la derecha** (columna de ~270 px a la derecha de la gráfica, como en las dispersiones y en `MapaTiros`); en pantalla angosta, arriba de la gráfica. Pedido del usuario el 2026-11-20 para todas las vistas nuevas de Equipos.

- Los agentes trabajan en worktrees y **no confirman `web/dist` ni `web/react/build`**; el integrador reconstruye el sitio una sola vez.
- No tocar `players.py`, `main.jsx` más allá de una línea, ni lo de jugadores. Otra sesión puede estar editando esos archivos.
- Cada vista: pruebas unitarias con datos sintéticos, verificación con Playwright (1440×900 y 390×844, claro y oscuro, sin desborde ni errores de consola) y un reporte con lo que **no** se pudo comprobar.
