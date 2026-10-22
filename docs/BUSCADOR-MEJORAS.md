# Buscador de la landing: qué hace hoy

## Qué hace hoy

El buscador del hero (`web/static/buscador.js`) encuentra **jugadores, equipos y gráficas** y lleva a la gráfica que los muestra:

- **Jugador:** abre una de las dispersiones del análisis exploratorio con su punto fijado (`#goles-vs-xg?t=2026-27&fijar=Erling+Haaland`). Cuál abre depende de su posición: un delantero va a Goles vs. xG, un medio a Perfil xG90 / xA90 y un defensa a Perfil defensivo. Debajo ofrece otras dos gráficas donde aparece. La temporada es la última en la que tiene punto en esa gráfica, para que nunca abra una vista donde no está.
- **Equipo:** abre Eficiencia de definición, Creación o Defensa con el club fijado.
- **Gráfica o lectura:** abre la vista o el artículo.
- **Campo vacío:** al enfocarlo sugiere los máximos goleadores de la temporada más reciente (con sus goles) y las primeras gráficas de "Preguntas para empezar".

El índice (`dist/assets/search-index.js`) lo arma `web/landing.py` en cada build con los mismos datos que usan las gráficas. Solo entran jugadores y equipos que tienen punto en alguna dispersión: hoy son 4,010 jugadores, 139 equipos, 16 gráficas y 1 lectura, y pesan **56.8 KB gzip** (el presupuesto es 150 KB). `web/tests/test_indice.py` comprueba que no haya duplicados, que cada destino sea real y que el peso no se pase.

## Lo que todavía no puede hacer

- **El mapa de tiros no filtra por jugador ni por equipo.** Sus datos viajan sumados por celda de la cancha (`datos-tiros.js`), no tiro por tiro. Por eso un jugador nunca lleva al mapa de tiros.
- **"Nivel por liga" (cajas) no resalta un club.** No acepta `fijar` en la URL, así que los equipos no llevan ahí.
- **No hay una gráfica de porteros.** Un portero cae en gráficas pensadas para jugadores de campo.
- **Los homónimos se mezclan.** Los datos no traen un id de jugador, así que dos jugadores con el mismo nombre son una sola entrada (igual que en `fijar`, que también busca por nombre).
- **Solo están las temporadas de las gráficas** (2021-22 en adelante). Los tiros llegan hasta 2014-15, pero esos jugadores no se pueden buscar.

## Qué sigue

Las propuestas para que el buscador sea más completo (mapa de tiros por jugador, ficha de jugador y de equipo, porteros, comparar, histórico, id de jugador) están en **[BACKLOG.md](BACKLOG.md)**.

## Si el índice crece

Hoy cada jugador cuesta unos 14 bytes gzip en el índice:

- **Temporada nueva:** suma unos 620 jugadores, es decir unos **9 KB**. Al ritmo actual faltan unas 10 temporadas para llegar a 150 KB.
- **Liga nueva:** suma unos **12 KB**.

Si se acerca al límite (el build y el test lo avisan):

1. **Partir el índice** en un archivo por tipo, o por inicial del apellido, y pedir solo el que haga falta.
2. **Quitar del índice a quien no juega desde hace varias temporadas**, aunque siga en las gráficas viejas.
