---
name: FutViz
description: "Gráficas del fútbol de las 5 grandes ligas que se leen como una pregunta contestada: una cancha limpia con un solo dato resaltado."
colors:
  primary: "#2C4C54"
  neutral-bg: "#F2F6F8"
  neutral-surface: "#FFFFFF"
  neutral-border: "#DAE3E8"
  text-body: "#1A2E33"
  muted: "#57707A"
  brand-green: "#399906"
  interactive-green: "#2E7A06"
  section-jugadores: "#46765A"
  section-equipos: "#5B58A3"
  liga-bundesliga: "#E34948"
  liga-serie-a: "#2A78D6"
  liga-ligue-1: "#2E413A"
  liga-la-liga: "#EDA100"
  liga-premier-league: "#E87BA4"
  diverging-neutral: "#C7CFD3"
typography:
  display:
    fontFamily: "Inter, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    fontSize: "32px"
    fontWeight: 800
    lineHeight: 1.1
    letterSpacing: "-0.025em"
  headline:
    fontFamily: "Inter, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    fontSize: "17px"
    fontWeight: 700
    lineHeight: 1.25
  title:
    fontFamily: "Inter, system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 600
    lineHeight: 1.35
  body:
    fontFamily: "Inter, system-ui, sans-serif"
    fontSize: "14.5px"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "Inter, system-ui, sans-serif"
    fontSize: "10.5px"
    fontWeight: 700
    letterSpacing: "0.07em"
rounded:
  sm: "8px"
  md: "11px"
  lg: "14px"
  pill: "99px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
components:
  entity-toggle:
    backgroundColor: "{colors.neutral-surface}"
    textColor: "{colors.muted}"
    typography: "{typography.title}"
    rounded: "{rounded.md}"
    padding: "3px"
  entity-toggle-selected:
    backgroundColor: "{colors.section-jugadores}"
    textColor: "{colors.neutral-surface}"
    rounded: "{rounded.sm}"
    padding: "9px 12px"
  view-item:
    backgroundColor: "transparent"
    textColor: "{colors.text-body}"
    typography: "{typography.body}"
    rounded: "{rounded.sm}"
    padding: "8px 12px"
  chart-card:
    backgroundColor: "{colors.neutral-bg}"
    textColor: "{colors.text-body}"
    rounded: "{rounded.lg}"
    padding: "20px"
---

# Design System: FutViz

## Overview

**Creative North Star: "La cancha limpia"**

FutViz se ve como una cancha recién marcada: mucho espacio, líneas finas, y el dato que importa sobre un fondo tranquilo. Cada vista contesta una pregunta de aficionado y todo lo que no ayuda a leerla se quita. El color nunca decora: el color de una liga es siempre el mismo, el color de una sección (Jugadores o Equipos) dice dónde estás, y el resto es gris azulado.

La marca vive en tres lugares y no más: el logo (con su letra, Sansita), el verde del logo, y el papel de puntitos detrás del encabezado. Todo lo demás es Inter, plano y legible: bordes de un pixel en lugar de sombras, tintes suaves en lugar de rellenos fuertes. Funciona igual en claro y en oscuro, y también como imagen descargada para redes.

El sitio rechaza cuatro cosas, confirmadas por su autor: parecer una **casa de apuestas** (neón, números enormes, urgencia), un **trabajo de la universidad** (tablas grises, títulos formales, todo igual de importante), **demasiado colorido** (muchos colores compitiendo) y **adornos sin función** (degradados, sombras de botón, efectos que no ayudan a leer).

**Key Characteristics:**
- Fondo azul-gris frío, superficies blancas, tinta verde-azulada oscura.
- Un color por liga y un color por sección (apagado); nada más lleva color propio.
- Un solo resaltado a la vez: lo que el lector elige va a todo color, lo demás se apaga.
- Plano por defecto: la profundidad se hace con borde y tinte, no con sombra.
- Español de México, de tú, sin tecnicismos; las palabras técnicas se explican en una línea.

## Colors

La paleta es un slate frío con un verde de marca, cinco colores de liga fijos y dos colores apagados que solo marcan la sección (salvia para Jugadores, índigo para Equipos). Todo pasa contraste AA sobre el fondo claro y sobre el oscuro.

### Primary
- **Slate Tinta** (#2C4C54): títulos, texto fuerte y el fondo de los botones activos neutros. En oscuro pasa a #D7E4E7 (la tinta se invierte).
- **Verde Cancha** (#399906): el verde del logo. Solo para elementos grandes o de marca (el ícono, puntos de los grupos); nunca para texto chico.
- **Verde Enlace** (#2E7A06): el verde accionable (enlaces, foco, sección Jugadores). Pasa 5.3:1 sobre blanco. En oscuro: #5CC22A.

### Secondary
- **Salvia Jugadores** (#46765A) e **Índigo Equipos** (#5B58A3): identifican la sección (el botón elegido y la vista elegida del menú, nada más). Apagados a propósito para no llenar la pantalla de color, y distintos de los colores de liga. En oscuro: #86BFA0 y #A5A1DE.

### Tertiary (los colores de liga)
- **Rojo Bundesliga** (#E34948), **Azul Serie A** (#2A78D6), **Verde Oscuro Ligue 1** (#2E413A), **Ámbar La Liga** (#EDA100), **Rosa Premier League** (#E87BA4). Son fijos: la misma liga lleva el mismo color en todas las gráficas. En oscuro cambian de luminosidad, no de matiz (Ligue 1 pasa a #0C7B60; la Bundesliga a #DD1D2D; La Liga a #C28412; la Premier a #CC7193).

### Neutral
- **Fondo Frío** (#F2F6F8): fondo de la página. En oscuro: #12181A.
- **Superficie** (#FFFFFF): tarjetas, menús, controles. En oscuro: #1B2426.
- **Borde Hielo** (#DAE3E8): todo borde y rejilla. En oscuro: #2C393C.
- **Texto Cuerpo** (#1A2E33) y **Gris Azulado** (#57707A): texto de lectura y texto de apoyo (4.8:1 sobre el fondo). En oscuro: #C7D3D6 y #8CA0A5.
- **Neutro Divergente** (#C7CFD3): el cero entre azul (sobre lo esperado) y rojo (bajo lo esperado).

### Named Rules
**The League Color Rule.** Un color de liga significa esa liga y nada más. Ninguna otra cosa del sitio (sección, tipo de jugada, categoría) usa rojo, azul, verde oscuro, ámbar o rosa de liga.
**The Section Color Rule.** Jugadores es salvia, Equipos es índigo. Ese color aparece solo en el botón elegido del selector de sección y en la vista elegida del menú; en ningún otro lugar.
**The One Highlight Rule.** En una gráfica, solo lo que el lector eligió lleva color pleno; el resto del montón se apaga (gris o su color casi transparente). El color pleno es una señal, no una decoración.

## Typography

**Display Font:** Inter (800, apretada)
**Body Font:** Inter (variable, 400 a 800)
**Brand Font:** Sansita (800), solo en el logo

**Character:** Inter hace todo el trabajo: neutra, firme y compacta; el título grande es la misma Inter en 800 con el espaciado apretado. Sansita, redondeada y con algo de cuaderno, solo aparece en la palabra «FutViz» del logo.

### Hierarchy
- **Display** (800, 32px / 26px en celular, 1.1, -0.025em): el título de la página («Explora los datos»).
- **Headline** (700, 17px, 1.25): el título de cada gráfica.
- **Title** (600, 13px): la pregunta que abre cada gráfica (en gris azulado) y los botones.
- **Body** (400, 14.5px, 1.5): la bajada y los textos de lectura; líneas de 65 a 75 caracteres como máximo.
- **Label** (700, 10.5px, +0.07em, mayúsculas): rótulos de los controles («TEMPORADA», «POSICIÓN»).

### Named Rules
**The Sansita Rule.** Sansita es solo la letra del logo. Ni títulos, ni controles, ni ejes, ni texto de lectura.
**The Plain Numbers Rule.** Los números de ejes, tablas y tooltips van en Inter con cifras tabulares; nunca en Sansita.

## Layout

Una columna a todo lo ancho en celular; desde 960px, un menú fijo de 250px a la izquierda y la gráfica con el ancho que queda (máximo 1880px, con 24px a cada lado). Dentro de la gráfica, el área de dibujo va a la izquierda y los controles en una columna de 270px a la derecha (arriba del dibujo en celular, porque se usan primero). El encabezado de la página es compacto a propósito: el eje X de la gráfica tiene que caber en pantalla. Los puntos de quiebre son 640px y 960px. El ritmo de espacios es de 4, 8, 16, 24 y 32px; más aire sobre un título que debajo.

## Elevation & Depth

El sitio es plano. Las superficies se separan por un borde de un pixel (#DAE3E8) y por el cambio entre el fondo frío y el blanco. Las sombras solo aparecen en lo que flota sobre la gráfica (los tooltips), con desplazamiento y desenfoque suaves; ningún control lleva sombra en reposo. El estado seleccionado se marca con un tinte del color de la sección (12%) y un borde fino, nunca con una barra a un lado ni con una sombra.

### Named Rules
**The Flat-By-Default Rule.** Un control o tarjeta en reposo no tiene sombra. Si necesita separarse, se le da borde o tinte.

## Shapes

Esquinas suaves y consistentes: 8px en elementos de menú y botones dentro de un grupo, 11px en el contenedor de un selector, 14px en la tarjeta de la gráfica y 99px en las etiquetas chicas (chips). Los puntos de las gráficas son círculos con un anillo del color de la superficie para que se separen entre sí. El fondo del encabezado lleva un patrón de puntitos (dos tonos, slate y verde, muy tenues) que evoca papel de apuntes y es la única textura del sitio.

## Components

### Selector de sección (Jugadores / Equipos)
- **Forma:** dos botones iguales dentro de un contenedor de 11px de radio, con borde.
- **Reposo:** texto y ícono (persona o escudo, trazo de 2px) en gris azulado sobre la superficie.
- **Seleccionado:** relleno del color de la sección (salvia o índigo) con texto blanco (negro azulado en oscuro).
- **Hover:** tinte del color al 10%. Foco: anillo de 2px del color de la sección.

### Menú de vistas
- **Estilo:** filas de texto sin caja, agrupadas por familia de preguntas (el rótulo del grupo en gris azulado).
- **Seleccionada:** tinte del color de la sección al 12%, texto del color y 700, y un borde de 1px al 35%. En celular se vuelve un selector desplegable.

### Etiquetas (chips)
- **Filtro de liga:** punto del color de la liga, texto con el número de equipos o jugadores; activo con un tinte suave de ese color.

### Tarjeta de gráfica
- **Forma:** 14px de radio, borde de 1px, fondo del color de la página; 20px de relleno (12px en celular).
- **Contenido:** la pregunta en gris azulado, el título, la bajada, la gráfica y, a la derecha, los controles.

### Botón de ícono (descargar, zoom)
- Solo el ícono, gris azulado, sin borde ni fondo en reposo; tooltip con su nombre. Va en la fila de controles o junto a «Datos: …», nunca encima del dibujo.

### Tooltip
- Superficie con borde, sombra suave, título en 700, valores alineados a la derecha. Es lo único con elevación.

### Imagen descargada
- Título en Inter 800, una línea de contexto con los filtros, la gráfica tal como está en pantalla (más limpia: sin rejilla vertical, sin marcas de eje, fondo apagado y lo elegido a color), logo abajo a la izquierda y la fuente chica abajo a la derecha. Sale en claro u oscuro según el tema.

## Do's and Don'ts

### Do:
- **Do** usar el mismo color para la misma liga en todas las gráficas, en claro y en oscuro.
- **Do** dejar el montón de puntos apagado y resaltar solo lo que el lector elige (nada se resalta solo).
- **Do** abrir cada vista con su pregunta y un título corto.
- **Do** explicar una palabra técnica en una línea y marcar las limitaciones del dato en la propia vista.
- **Do** validar cualquier color nuevo contra el fondo claro y el oscuro (contraste y distinción para daltónicos) antes de usarlo.

### Don't:
- **Don't** hacer que FutViz parezca una casa de apuestas: nada de neón, números gigantes, urgencia ni brillo.
- **Don't** hacer que parezca un trabajo de la universidad: nada de tablas grises, títulos formales ni jerarquías planas donde todo pesa igual.
- **Don't** usar más colores de los necesarios ni reutilizar un color de liga para otra cosa.
- **Don't** añadir adornos sin función: degradados, sombras en reposo, barras a un lado de una caja, texto con efecto.
- **Don't** usar Sansita fuera del logo, ni llenar la pantalla de colores de sección: el color de la sección vive solo en el botón y en la vista elegida.
