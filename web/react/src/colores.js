// Color de los puntos. Dos codificaciones, y ninguna usa colores nuevos:
//  - "liga": identidad (categórica). Los 5 colores salen de `LEAGUE_COLORS` /
//    `LEAGUE_COLORS_DARK` de viz_theme.py, ya validados contra daltonismo y contraste.
//  - "rendimiento": polaridad (divergente) de goles − xG con el par `DIVERGING` del
//    sitio (azul = más de lo esperado, rojo = menos) y un gris neutro en el cero.
//    Lo que busca es lo contrario a "liga": que lo normal (cerca de la diagonal)
//    retroceda y solo se destaque lo raro.

const aRgb = (hex) => {
  const h = hex.replace("#", "");
  const n = parseInt(h.length === 3 ? h.replace(/./g, "$&$&") : h, 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
};

export const conAlfa = (hex, a) => {
  const [r, g, b] = aRgb(hex);
  return `rgba(${r},${g},${b},${a})`;
};

const mezclar = (a, b, t) => {
  const [r1, g1, b1] = aRgb(a);
  const [r2, g2, b2] = aRgb(b);
  const c = (x, y) => Math.round(x + (y - x) * t).toString(16).padStart(2, "0");
  return `#${c(r1, r2)}${c(g1, g2)}${c(b1, b2)}`;      // hex, para poder atenuarlo luego con conAlfa
};

// A partir de cuántos goles de diferencia el color deja de intensificarse. La
// mayoría de los jugadores está dentro de ±2; los extremos llegan a ±9, y sin tope
// todo lo demás quedaría casi gris.
export const TOPE_DIF = 4;

export function colorRendimiento(dif, divergente) {
  const t = Math.min(1, Math.abs(dif) / TOPE_DIF);
  return mezclar(divergente.mid, dif >= 0 ? divergente.pos : divergente.neg, t);
}

// El par divergente en cada modo. En claro es `DIVERGING` tal cual. En oscuro el
// azul y el rojo ya pasan 3:1 contra la superficie (#1B2426), pero el gris del
// cero no puede ser el claro (#cfcecb): sobre fondo oscuro sería lo MÁS brillante
// del gráfico, justo lo que debe retroceder.
export const divergente = (modo, base) =>
  modo === "dark" ? { ...base, mid: "#5f6e72" } : base;
