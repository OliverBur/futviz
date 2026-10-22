# Backlog de FutViz

Propuestas de mejora para no perderlas. Nada de esto está hecho todavía; se toma de aquí cuando toque.
Cada punto dice qué es, por qué vale la pena, qué datos hay y qué faltaría. El esfuerzo es aproximado:
**bajo** (un rato, un archivo), **medio** (un par de sesiones), **alto** (una página o un dato nuevo).

---

## 1. Ficha de jugador — prioridad alta

**Qué es.** Una página por jugador, a la que llega el buscador. Hoy el buscador solo puede abrir una
gráfica general con el jugador fijado. La ficha sería el lugar donde se ve todo lo de una persona.

**Qué mostraría** (todo con datos que ya existen):

| Bloque | Contenido | De dónde sale |
|---|---|---|
| Encabezado | Nombre, equipo y liga actuales, posición, edad, temporadas en los datos | Tabla de jugadores (Understat), `born`, `posicion` |
| Temporada por temporada | Minutos, goles, xG, asistencias, xA, tiros y pases clave, en una tabla con una línea por temporada | Tabla de jugadores |
| Contra su posición | En qué percentil está en cada métrica frente a los de su misma posición y temporada (barras horizontales de 0 a 100) | Tabla de jugadores |
| Goles contra xG | Una línea por temporada: goles y xG, con la diferencia marcada | Tabla de jugadores |
| Sus tiros | Mini mapa de tiros con el xG de cada uno, goles marcados | Tiros por jugador (ver el punto 3) |
| Dónde aparece | Enlaces a las gráficas del análisis exploratorio con el jugador ya fijado | Lo mismo que hoy usa el buscador |

**Cómo encajaría.**
- **Una sola página** `jugador.html#<id-o-nombre>` en lugar de una página por jugador: son unos 4,000.
- **Datos:** la página lee la tabla de jugadores que ya viaja al sitio (`datos-jugadores.js`), así que no habría que generar archivos nuevos salvo los tiros.
- **Buscador:** pasaría a abrir la ficha como acción principal, con "Ver en…" para las gráficas.

**Cuidados.**
- **Homónimos:** sin un id de jugador, dos jugadores con el mismo nombre se mezclarían (ver el punto 5).
- **Percentiles:** solo tienen sentido con un mínimo de minutos, el mismo que ya usan las gráficas.
- **Temporada en curso:** si es la última, hay que decir que es parcial.

**Esfuerzo:** alto (página nueva con 4 o 5 gráficas), pero sin datos nuevos salvo el mapa de tiros.

## 2. Ficha de equipo — prioridad media

Lo mismo para un club:
- Su ataque, creación y defensa contra el promedio de su liga.
- Cómo cambió por temporada.
- Su lugar en "Nivel por liga".
- Sus jugadores con más minutos, con enlace a cada ficha.

Datos: la tabla de equipos (FBref) y la de jugadores. **Esfuerzo:** alto.

## 3. Mapa de tiros por jugador y por equipo — prioridad alta

**Por qué.** "¿Desde dónde tira Haaland?" es de las primeras cosas que alguien busca, y hoy el mapa de tiros no filtra por persona: sus datos viajan sumados por celda de la cancha.

**Qué haría falta.**
- **Datos:** una tabla de tiros por jugador (posición, xG, resultado), que se pida solo al elegir a alguien. Un archivo por equipo y temporada mantiene cada descarga chica.
- **Vista:** `MapaTiros.jsx` aceptaría `jugador` o `equipo` en la URL y mostraría los puntos encima del mapa de calor de la liga.
- **Buscador:** agregaría "Ver sus tiros".

**Esfuerzo:** medio. Es la pieza que luego reutiliza la ficha de jugador.

## 4. Más alcance para el buscador

| Mejora | Qué hace falta | Esfuerzo |
|---|---|---|
| Resaltar un club en "Nivel por liga" | `fijar` en `CajasVista.jsx` para marcar su punto en la caja de su liga. Así los equipos también pueden llevar ahí. | Bajo |
| Gráfica de porteros | Hoy no hay. Paradas, goles evitados contra lo esperado (con el xG propio) y salidas. Los porteros dejarían de caer en gráficas de jugadores de campo. | Medio |
| Comparar dos jugadores | Que "Haaland vs Mbappé" abra una dispersión con los dos fijados (`fijar` ya acepta varios). | Bajo |
| Buscar por tema | Sinónimos que lleven a gráficas: "goleadores", "asistencias", "defensa", "posesión". | Bajo |
| Jugadores del histórico | Los tiros llegan hasta 2014-15, pero las gráficas empiezan en 2021-22. Esos jugadores podrían llevar al explorador de tiros del artículo, si se le dan filtros en la URL. | Medio |

## 5. Datos

- **Id de jugador.** Guardar el id de Understat en la consolidación y usarlo en el índice, en `fijar` (`fijar=id:8260`) y en la ficha. Resuelve los homónimos, que hoy se mezclan en una sola entrada. **Esfuerzo:** medio.
- **Índice del buscador cuando crezca.** Hoy pesa 56.8 KB gzip de 150. Cada temporada nueva suma unos 9 KB y cada liga unos 12 KB. Si se acerca al límite (el build y el test lo avisan): partirlo por tipo o por inicial y pedir solo lo necesario.

## 6. Pendientes que fueron saliendo

| Pendiente | Detalle |
|---|---|
| Explorador de tiros del artículo sin filtros en la URL | El hash del lector de ML es `#articulo/seccion`; temporada, liga, equipo o jugador no se pueden compartir. |
| Filtros de la URL con la vista ya abierta | Pegar un enlace con filtros en una pestaña donde esa vista ya está montada no los aplica (se leen solo al montar). Recargar sí. |
| Zoom de las gráficas | No se guarda en la URL. |
| Logo oscuro | El slate `#3F6B78` da 2.70:1 sobre la superficie oscura, bajo el 3:1 de un gráfico. Fue decisión de diseño; si se ve apagado, `#4F8392` (3.76:1) es el siguiente paso. |
| Fuentes con doble clic (`file://`) | El navegador bloquea las fuentes locales y el texto cae en la del sistema. Solo afecta a abrir el sitio sin servidor. |
| Fixtures de las pruebas de React | `web/react/test/fixtures` tiene el gris viejo del par divergente; se regeneran con `gen_paridad.py`. |
| Artículo "Valores de jugadores" | Anunciado como "Próximamente" en el lector de ML y en la portada. |
