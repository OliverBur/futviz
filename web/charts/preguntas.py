"""Una pregunta por vista del análisis exploratorio, en el lenguaje de la portada.

Es la única fuente: la portada (`landing.PREGUNTAS`), la tarjeta de cada gráfica (el renglón sobre el título) y el
buscador leen de aquí. Si una vista cambia de nombre o se quita, hay que tocar este archivo y nada más.
"""

PREGUNTAS = {
    # Jugadores
    "xg-vs-goles-90": "¿Quién genera más ocasiones y quién las convierte?",
    "perfil-ofensivo": "¿Quién remata y quién crea?",
    "mapa-tiros": "¿Desde dónde se tira en las 5 ligas?",
    "xa-vs-asistencias-90": "¿Quién da más asistencias de las que debería?",
    "pases-clave-vs-asistencias": "¿Quién crea ocasiones que sus compañeros desperdician?",
    "construir-vs-producir": "¿Quién construye, quién termina y quién lo hace todo?",
    "corte-vs-cobertura": "¿Quién va al choque y quién lee el juego?",
    "edad": "¿A qué edad se juega más y a cuál se rinde mejor?",
    "crea-tu-grafico-jugadores": "¿Cómo se relacionan dos variables que tú elijas?",
    # Equipos
    "eficiencia-definicion": "¿Qué equipo aprovecha mejor sus ocasiones?",
    "creacion": "¿Qué equipo domina las ocasiones?",
    "defensa": "¿Quién defiende mejor y cómo?",
    "puntos-vs-xg": "¿Los puntos reflejan el juego o la suerte?",
    "nivel-por-liga-equipos": "¿Qué tan parejos son los equipos de cada liga?",
    "crea-tu-grafico-equipos": "¿Cómo se relacionan dos variables que tú elijas?",
}
