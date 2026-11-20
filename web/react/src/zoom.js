// Matemática del zoom y el pan, sin React. La vista es el rectángulo de datos que se
// ve: { x0, x1, y0, y1 }. Los dos ejes se acercan siempre al mismo ritmo: la
// diagonal y = x de esta gráfica tiene que seguir siendo una diagonal, y un zoom
// que estirara un solo eje la deformaría y haría mentir a "sobre/bajo-rendimiento".

export const ZOOM_MAX = 40; // cuántas veces se puede acercar respecto de la vista base

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

export const anchoDe = (v) => v.x1 - v.x0;
export const altoDe = (v) => v.y1 - v.y0;

export const esBase = (v, base) =>
  Math.abs(v.x0 - base.x0) < 1e-9 && Math.abs(v.x1 - base.x1) < 1e-9 &&
  Math.abs(v.y0 - base.y0) < 1e-9 && Math.abs(v.y1 - base.y1) < 1e-9;

// Mantiene la vista dentro de la base: no se puede arrastrar hasta el vacío.
export function encuadrar(v, base) {
  const w = Math.min(anchoDe(v), anchoDe(base));
  const h = Math.min(altoDe(v), altoDe(base));
  const x0 = clamp(v.x0, base.x0, base.x1 - w);
  const y0 = clamp(v.y0, base.y0, base.y1 - h);
  return { x0, x1: x0 + w, y0, y1: y0 + h };
}

// `factor` < 1 acerca y > 1 aleja. (fx, fy) es el punto que se queda quieto, como
// fracción del área de dibujo: fx desde la izquierda, fy desde ABAJO.
export function acercar(v, base, factor, fx = 0.5, fy = 0.5) {
  const nivel = anchoDe(v) / anchoDe(base);                      // 1 = vista base
  const f = clamp(nivel * factor, 1 / ZOOM_MAX, 1) / nivel;      // factor efectivo
  const ax = v.x0 + fx * anchoDe(v);
  const ay = v.y0 + fy * altoDe(v);
  return encuadrar({
    x0: ax - (ax - v.x0) * f, x1: ax + (v.x1 - ax) * f,
    y0: ay - (ay - v.y0) * f, y1: ay + (v.y1 - ay) * f,
  }, base);
}

// Desplaza la vista (dx, dy) píxeles dentro de un área de (ancho x alto) píxeles.
// Arrastrar a la derecha mueve los DATOS a la derecha, o sea la ventana a la izquierda.
export function desplazar(v, base, dx, dy, ancho, alto) {
  return encuadrar({
    x0: v.x0 - (dx / ancho) * anchoDe(v), x1: v.x1 - (dx / ancho) * anchoDe(v),
    y0: v.y0 + (dy / alto) * altoDe(v), y1: v.y1 + (dy / alto) * altoDe(v),
  }, base);
}

// Centra la vista en (x, y) conservando el nivel de zoom.
export function centrarEn(v, base, x, y) {
  const w = anchoDe(v), h = altoDe(v);
  return encuadrar({ x0: x - w / 2, x1: x + w / 2, y0: y - h / 2, y1: y + h / 2 }, base);
}

// Vista que abarca un conjunto de puntos con un margen, manteniendo la proporción
// de la base (así la diagonal no se deforma) y sin salirse de ella.
// `acercamientoMax` es lo más que se puede acercar respecto de la base: para la vista de arranque se usa
// uno chico, porque con dos o tres puntos "ajustar" los dejaría a 40 aumentos, que no es verlos mejor.
export function ajustarA(puntos, base, margen = 0.08, acercamientoMax = ZOOM_MAX) {
  if (!puntos.length) return base;
  let x1 = -Infinity, y1 = -Infinity;
  let x0 = Infinity, y0 = Infinity;
  for (const p of puntos) {
    if (p.x < x0) x0 = p.x; if (p.x > x1) x1 = p.x;
    if (p.y < y0) y0 = p.y; if (p.y > y1) y1 = p.y;
  }
  const razon = altoDe(base) / anchoDe(base);
  let w = Math.max(x1 - x0, (y1 - y0) / razon, anchoDe(base) / acercamientoMax) * (1 + margen * 2);
  w = Math.min(w, anchoDe(base));
  const h = w * razon;
  return encuadrar({
    x0: (x0 + x1) / 2 - w / 2, x1: (x0 + x1) / 2 + w / 2,
    y0: (y0 + y1) / 2 - h / 2, y1: (y0 + y1) / 2 + h / 2,
  }, base);
}

// La vista de un cuadrante: cada eje por su cuenta (no hay por qué conservar la proporción de la base) y recortada JUSTO en
// las líneas punteadas del lado donde el cuadrante termina en una línea, así lo de los demás cuadrantes sale de la vista.
// Por los otros lados deja un margen sobre los puntos. `id`: "tr", "tl", "br" o "bl". Con las líneas "diag" (la vertical y la
// diagonal y = x) solo la vertical es un corte recto: el lado de la diagonal queda en los puntos. `encuadrar` lo mantiene
// dentro de la base.
export function vistaDeZona(puntos, lineas, id, base, margen = 0.06) {
  if (!puntos.length) return base;
  let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
  for (const p of puntos) {
    if (p.x < x0) x0 = p.x; if (p.x > x1) x1 = p.x;
    if (p.y < y0) y0 = p.y; if (p.y > y1) y1 = p.y;
  }
  const minW = anchoDe(base) / ZOOM_MAX, minH = altoDe(base) / ZOOM_MAX;
  const padX = Math.max(x1 - x0, minW) * margen, padY = Math.max(y1 - y0, minH) * margen;
  const derecha = id[1] === "r", arriba = id[0] === "t";
  // los lados que son una línea: exactos; los demás, con margen
  if (derecha) { x0 = lineas.cx; x1 += padX; } else { x1 = lineas.cx; x0 -= padX; }
  if (lineas.tipo === "rect") {
    if (arriba) { y0 = lineas.cy; y1 += padY; } else { y1 = lineas.cy; y0 -= padY; }
  } else {
    if (arriba) { y0 = derecha ? Math.min(y0, lineas.cx) : y0 - padY; y1 += padY; } else { y0 -= padY; y1 += padY; }
  }
  // un cuadrante con casi nadie no se acerca más de la cuenta
  if (x1 - x0 < minW) { const m = (x0 + x1) / 2; x0 = m - minW / 2; x1 = m + minW / 2; }
  if (y1 - y0 < minH) { const m = (y0 + y1) / 2; y0 = m - minH / 2; y1 = m + minH / 2; }
  return encuadrar({ x0, x1, y0, y1 }, base);
}

// El cuadrante de un punto respecto de las líneas de una vista: "tr", "tl", "br" o "bl" (arriba o abajo, derecha o izquierda).
// `lineas`: `{ tipo: "rect", cx, cy }` (dos líneas, una vertical en `cx` y otra horizontal en `cy`) o `{ tipo: "diag", cx }`
// (la vertical en `cx` y la diagonal y = x, para las gráficas de "marcó lo esperado").
export function zonaDe(lineas, x, y) {
  const derecha = x >= lineas.cx;
  const arriba = lineas.tipo === "diag" ? y >= x : y >= lineas.cy;
  return (arriba ? "t" : "b") + (derecha ? "r" : "l");
}

// El cuadrante como polígono en coordenadas de datos (`T`: más allá de cualquier zoom), para sombrearlo.
export function poligonoZona(lineas, id, T) {
  const { cx } = lineas;
  if (lineas.tipo === "diag") {
    return {
      tr: [[cx, cx], [T, T], [cx, T]],
      br: [[cx, -T], [T, -T], [T, T], [cx, cx]],
      tl: [[-T, -T], [cx, cx], [cx, T], [-T, T]],
      bl: [[-T, -T], [cx, cx], [cx, -T]],
    }[id];
  }
  const { cy } = lineas;
  return {
    tr: [[cx, cy], [T, cy], [T, T], [cx, T]],
    br: [[cx, -T], [T, -T], [T, cy], [cx, cy]],
    tl: [[-T, cy], [cx, cy], [cx, T], [-T, T]],
    bl: [[-T, -T], [cx, -T], [cx, cy], [-T, cy]],
  }[id];
}
