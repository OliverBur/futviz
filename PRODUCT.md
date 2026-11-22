# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- **El aficionado curioso (principal).** Alguien que ve fútbol y quiere entender quién rinde de verdad, quién tiene suerte y quién es muy bueno, sin saber de estadística. Llega con una pregunta de aficionado, no con una variable en la cabeza.
- **Quien juzga el trabajo de datos.** Reclutadores y gente del mundo de datos que abren el sitio como portafolio de ciencia de datos deportiva.
- **El propio autor.** FutViz también es su laboratorio para aprender y probar ideas; las vistas nuevas nacen de preguntas que él mismo quiere responder.

## Product Purpose

FutViz es un sitio de gráficas y modelos de fútbol de las cinco grandes ligas (Premier League, La Liga, Serie A, Bundesliga y Ligue 1). Existe para juntar el conocimiento de ciencia de datos del autor con su pasión por el fútbol: partir de datos públicos y sencillos, sacarles todo el jugo y subir en complejidad con el tiempo. Tiene éxito cuando alguien entiende algo del juego que antes no veía y puede compartirlo.

## Positioning

Cada gráfica responde una pregunta de aficionado («¿quién genera más ocasiones y quién las convierte?», «¿cómo generan peligro los equipos?»). No es un tablero de números: la vista abre con la pregunta, se lee sin tecnicismos y las palabras técnicas (xG, percentil) se explican en una línea. Otros sitios de estadísticas de fútbol ofrecen tablas y variables; FutViz ofrece respuestas.

## Operating Context

- Sitio estático en español que se construye con un script de Python (`web/build.py`) y vistas interactivas en React (bundle de Vite en `web/react/`). Lo servido sale de `web/dist/`, que se commitea; se despliega en Vercel desde el repositorio público `OliverBur/futviz`.
- Dos secciones: **Gráficas** (Jugadores y Equipos, cada una con sus vistas) y **Modelos** (artículos de machine learning, como el modelo de xG).
- Cada gráfica se puede descargar como imagen (con el logo y la fuente) para compartirla en redes.
- Las temporadas van de 2021-22 a la que está en curso; la en curso se marca como tal y usa cortes de minutos relativos.

## Capabilities and Constraints

- **Datos:** FBref (conteos, defensivos, edad), Understat (xG, xA, tiros), clubelo (ELO) y Transfermarkt. **No se redistribuyen**: sus términos no lo permiten. El sitio muestra gráficas y el código es público, pero los CSV no se versionan.
- **Cortes de minutos** para jugadores (900 en temporada cerrada; una fracción en la que va en curso) y posición como categoría gruesa (portero, defensa, medio, delantero): las fuentes no distinguen central de lateral.
- **Honestidad ante todo:** no se publica lo que los datos no sostienen. Las limitaciones (muestras chicas, temporada en curso, correlaciones que engañan) se dicen en la propia vista.
- Cada vista que muestra datos tiene que funcionar en modo claro y oscuro, incluida la imagen descargada.
- Decisiones de producto no resueltas: ninguna registrada.

## Brand Commitments

- **Nombre:** FutViz (elegido por el autor entre tres opciones; sirve de marca para todo lo que siga en ciencia de datos deportiva).
- **Logo:** wordmark «FutViz» con su ícono; archivos fuente `img/futviz.png` y `img/futviz-logo-only.png` (versión clara y oscura se generan en el build).
- **Voz:** español de México, de tú, cercano y claro, sin voseo rioplatense. «Underground» se queda como nombre del filtro de nivel del club.
- **Un color por liga, siempre el mismo**, en todas las gráficas y en el modo claro y en el oscuro.
- Nunca se pone una barra de metadatos («Datos / Modelo / Métodos / Lectura») bajo el título de un artículo, ni «N min de lectura».

## Evidence on Hand

- Datos reales de 5 ligas y 6 temporadas en `data/` (no versionados), con las vistas ya construidas en `web/dist/`.
- Un modelo de xG propio validado contra Understat tiro por tiro (artículo «Modelo xG»).
- Bitácora del proyecto en `BITACORA.md`, con las decisiones y sus razones.
- No hay testimonios, métricas de uso ni clientes: no se deben inventar.

## Product Principles

1. **Primero la pregunta.** Cada vista empieza con una pregunta de aficionado y todo lo demás (título, filtros, texto) sirve para contestarla.
2. **Honestidad antes que impacto.** Si los datos no sostienen una conclusión, se dice o no se publica.
3. **Se entiende sin saber estadística.** Una palabra técnica se explica en una línea; el texto es corto.
4. **Se comparte.** Cualquier gráfica tiene que poder salir como una imagen limpia, con sus filtros y sin ruido.
5. **Lo mismo significa lo mismo.** El color de una liga, el nombre de un filtro y el sentido de un control no cambian de una vista a otra.

## Accessibility & Inclusion

- Modo claro y oscuro en todo el sitio.
- El color nunca es la única señal: los puntos destacados llevan nombre y las leyendas dicen qué es cada color.
- Pensado también para celular: lo importante se lee y se toca en pantalla chica.
