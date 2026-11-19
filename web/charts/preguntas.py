"""Una pregunta por vista del análisis exploratorio, en el lenguaje de la portada.

Es la única fuente: la portada (`landing.PREGUNTAS`), la tarjeta de cada gráfica (el renglón sobre el título) y el
buscador leen de aquí. Si una vista cambia de nombre o se quita, hay que tocar este archivo y nada más.
"""

PREGUNTAS = {
    # Jugadores
    "goles-vs-xg": "¿Quién marca más de lo que debería?",
    "perfil-ofensivo": "¿Quién remata y quién crea?",
    "mapa-tiros": "¿Desde dónde se tira en las 5 ligas?",
    "asistencias-vs-xa": "¿Quién da más asistencias de las que debería?",
    "pases-clave-vs-xa": "¿Quién genera más ocasiones para sus compañeros?",
    "construir-vs-producir": "¿Quién arma la jugada y quién la termina?",
    "recuperacion-vs-faltas": "¿Quién recupera más balones y a qué costo?",
    "perfil-defensivo": "¿Quién defiende yendo al choque y quién leyendo el pase?",
    "crea-tu-grafico-jugadores": "¿Cómo se relacionan dos variables que tú elijas?",
    # Equipos
    "eficiencia-definicion": "¿Qué equipo aprovecha mejor sus ocasiones?",
    "creacion": "¿Tener el balón se convierte en asistencias?",
    "defensa": "¿Quién defiende mejor y cómo?",
    "nivel-por-liga-equipos": "¿Qué tan parejos son los equipos de cada liga?",
    "crea-tu-grafico-equipos": "¿Cómo se relacionan dos variables que tú elijas?",
}
