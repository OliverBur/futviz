// Estadística mínima, calcada de lo que hace pandas/numpy en `code/insights.py`, para que el texto
// que se arma en el navegador diga lo mismo que decía el que armaba Python. Cada función trabaja
// sobre arreglos de números ya sin nulos (quien llama filtra), salvo `idxmax`/`idxmin`.

export const suma = (v) => { let s = 0; for (let i = 0; i < v.length; i++) s += v[i]; return s; };
export const media = (v) => suma(v) / v.length;

export function mediana(v) {
  const s = [...v].sort((a, b) => a - b);
  const n = s.length, m = n >> 1;
  return n % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

// pandas `quantile` (interpolación lineal): posición (n-1)*q entre los vecinos.
export function cuantil(v, q) {
  const s = [...v].sort((a, b) => a - b);
  const pos = (s.length - 1) * q, lo = Math.floor(pos), hi = Math.ceil(pos);
  return s[lo] + (s[hi] - s[lo]) * (pos - lo);
}

// `Series.rank(pct=True)`: rango promedio entre empatados, dividido por n.
export function rangoPct(v) {
  const n = v.length;
  const orden = v.map((x, i) => [x, i]).sort((a, b) => a[0] - b[0]);
  const rango = new Array(n);
  for (let i = 0; i < n;) {
    let j = i;
    while (j + 1 < n && orden[j + 1][0] === orden[i][0]) j++;
    const prom = (i + j) / 2 + 1;               // rango 1-based promedio del grupo
    for (let k = i; k <= j; k++) rango[orden[k][1]] = prom / n;
    i = j + 1;
  }
  return rango;
}

// Primer índice del máximo / mínimo (pandas devuelve la primera aparición); ignora no finitos.
export function idxmax(v) {
  let mejor = -1;
  for (let i = 0; i < v.length; i++) if (Number.isFinite(v[i]) && (mejor < 0 || v[i] > v[mejor])) mejor = i;
  return mejor;
}
export function idxmin(v) {
  let mejor = -1;
  for (let i = 0; i < v.length; i++) if (Number.isFinite(v[i]) && (mejor < 0 || v[i] < v[mejor])) mejor = i;
  return mejor;
}

// Correlación de Pearson. Devuelve NaN si algún eje no varía.
export function corr(x, y) {
  const n = x.length;
  const mx = media(x), my = media(y);
  let sxy = 0, sxx = 0, syy = 0;
  for (let i = 0; i < n; i++) {
    const dx = x[i] - mx, dy = y[i] - my;
    sxy += dx * dy; sxx += dx * dx; syy += dy * dy;
  }
  return sxx === 0 || syy === 0 ? NaN : sxy / Math.sqrt(sxx * syy);
}

// Desviación estándar de la población (como el z-score que usaban las etiquetas de "distancia al centro").
export function desvPob(v) {
  const m = media(v);
  let s = 0;
  for (let i = 0; i < v.length; i++) s += (v[i] - m) ** 2;
  return Math.sqrt(s / v.length);
}

// Recta de mínimos cuadrados y = pendiente*x + base (lo que hace `np.polyfit(x, y, 1)`).
export function ajusteLineal(x, y) {
  const mx = media(x), my = media(y);
  let sxy = 0, sxx = 0;
  for (let i = 0; i < x.length; i++) { sxy += (x[i] - mx) * (y[i] - my); sxx += (x[i] - mx) ** 2; }
  const pendiente = sxy / sxx;
  return [pendiente, my - pendiente * mx];
}

// Formato de Python (`f"{x:.{dec}f}"`). `toFixed` de JS trabaja sobre el valor EXACTO del número y
// coincide con Python salvo en los empates exactos (0.125 con 2 decimales): ahí JS redondea hacia
// arriba y Python al par. Un empate exacto solo lo es si el desarrollo decimal completo del número
// termina en 5 seguido de ceros; multiplicar por 10^dec y mirar si da .5 NO sirve, porque el
// producto se redondea y hace pasar por empate a 0.33499999999999996 (que Python redondea a 0.33).
export function fmt(x, dec = 2) {
  if (!Number.isFinite(x)) return String(x);
  const t = x.toFixed(dec + 40);              // el desarrollo decimal exacto de la double
  const corte = t.length - 40;
  if (t.slice(corte) === "5" + "0".repeat(39)) {
    const cabeza = t.slice(0, corte);          // con el signo y, si dec = 0, el punto final
    const ultimo = Number(cabeza.replace(/\D/g, "").slice(-1));
    if (ultimo % 2 === 0) return cabeza.replace(/\.$/, "");   // el par queda: se trunca
  }
  return x.toFixed(dec);
}
export const miles = (n) => String(Math.trunc(n)).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
