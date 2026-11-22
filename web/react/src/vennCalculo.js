// El cálculo y el acomodo del Venn de «Jugador completo» (`VennVista.jsx`). Sin React: funciones puras.
//
// La regla de membresía es la misma que `percentiles` y `regiones` en `web/charts/venn.py` (hay una prueba que las
// compara): el percentil de un valor se calcula dentro de su población (posición y temporada) y los empates comparten
// el promedio de sus lugares, `p = (rango_promedio - 0.5) / n`; está en el círculo quien tiene `p >= 1 - corte`.

export const R = 280;
export const CEN = [[450, 340], [300, 600], [600, 600]];
export const W = 900;
export const H = 930;

export function pcts(vals) {
  const n = vals.length, idx = vals.map((_, k) => k).sort((a, b) => vals[a] - vals[b]), out = new Array(n);
  for (let i = 0; i < n;) {
    let j = i;
    while (j + 1 < n && vals[idx[j + 1]] === vals[idx[i]]) j++;
    const p = ((i + j) / 2 + 0.5) / n;
    for (let k = i; k <= j; k++) out[idx[k]] = p;
    i = j + 1;
  }
  return out;
}

function pearson(a, b) {
  const n = a.length;
  let ma = 0, mb = 0;
  for (let i = 0; i < n; i++) { ma += a[i]; mb += b[i]; }
  ma /= n; mb /= n;
  let sab = 0, saa = 0, sbb = 0;
  for (let i = 0; i < n; i++) { sab += (a[i] - ma) * (b[i] - mb); saa += (a[i] - ma) ** 2; sbb += (b[i] - mb) ** 2; }
  return sab / Math.sqrt(saa * sbb);
}

// `venn` es una entrada de `cfg.venns`; `corte` va en % (15 = el 15% de arriba). Devuelve la población, los percentiles de
// cada círculo, las 7 regiones (índice = máscara, bit j = círculo j), los cortes en valor y la correlación entre criterios.
export function calcular(D, venn, temp, corte) {
  const q = corte / 100;
  const pos = D.posiciones.indexOf(venn.pos);
  const col = (s) => D.prefijo + D.medidas.indexOf(s.col);
  const pop = D.temporadas[temp].jug.filter((r) => r[3] === pos);
  // `inv`: menos es mejor (xG en contra): el percentil sale del signo cambiado y el corte en valor es un máximo.
  const P3 = venn.sets.map((s) => pcts(pop.map((r) => (s.inv ? -r[col(s)] : r[col(s)]))));
  const reg = [null, [], [], [], [], [], [], []];
  const cut = venn.sets.map((s) => (s.inv ? -Infinity : Infinity));
  const miembros = [];
  pop.forEach((r, k) => {
    let m = 0, suma = 0, nb = 0;
    venn.sets.forEach((s, j) => {
      if (P3[j][k] >= 1 - q) { m |= 1 << j; suma += P3[j][k]; nb++; if (s.inv ? r[col(s)] > cut[j] : r[col(s)] < cut[j]) cut[j] = r[col(s)]; }
    });
    if (m) { const it = { r, k, m, score: suma / nb, p: P3.map((c) => c[k]) }; reg[m].push(it); miembros.push(it); }
  });
  for (let m = 1; m < 8; m++) reg[m].sort((a, b) => b.score - a.score);
  const corr = [[0, 1], [0, 2], [1, 2]].map(([a, b]) => ({ a, b, r: pearson(P3[a], P3[b]) }));
  return { venn, pop, P3, reg, cut, miembros, corr, q, col };
}

// ---- acomodo de las fichas dentro de cada región ----------------------------------------------------
// De mayor a menor: cada región usa el nivel más grande en que caben todos sus jugadores. Una región con uno o dos
// jugadores se ve grande; una con decenas, chica. En pantalla angosta los nombres no se leen (el diagrama se encoge
// a la mitad o menos), así que ahí las fichas van sin nombre y son más grandes que su escala natural.
const NIVELES = [
  { r: 42, f: 15, dx: 150, dy: 120, max: 14 },
  { r: 26, f: 13, dx: 108, dy: 84, max: 13 },
  { r: 17, f: 11.5, dx: 74, dy: 58, max: 12 },
  { r: 13.5, f: 10.5, dx: 64, dy: 50, max: 10 },
];
const NIVELES_COMPACTOS = [
  { r: 34, f: 0, dx: 96, dy: 84, max: 0 },
  { r: 24, f: 0, dx: 62, dy: 56, max: 0 },
  { r: 18, f: 0, dx: 46, dy: 42, max: 0 },
  { r: 14, f: 0, dx: 36, dy: 33, max: 0 },
];
const MARGEN = 6;

function enRegion(x, y, mask, m) {
  for (let i = 0; i < 3; i++) {
    const d = Math.hypot(x - CEN[i][0], y - CEN[i][1]);
    if (mask & (1 << i)) { if (d > R - m) return false; } else if (d < R + m) return false;
  }
  return true;
}

// Una ficha ocupa el círculo y el apellido de abajo: se prueba la caja entera, no solo el centro, para que el nombre no
// quede pisando el borde de un círculo ni una pastilla.
function cabe(x, y, mask, lv, bloq) {
  const hw = lv.dx * 0.46, arriba = lv.r, abajo = lv.r + lv.f + 3;
  for (const [px, py] of [[x - hw, y - arriba], [x + hw, y - arriba], [x - hw, y + abajo], [x + hw, y + abajo],
    [x, y - arriba], [x, y + abajo], [x - hw, y], [x + hw, y]]) {
    if (!enRegion(px, py, mask, MARGEN)) return false;
  }
  for (const b of bloq) if (x + hw > b.x0 && x - hw < b.x1 && y + abajo > b.y0 && y - arriba < b.y1) return false;
  return true;
}

const ORIGENES = [[0, 0], [0.5, 0], [0, 0.5], [0.5, 0.5], [0.25, 0.25], [0.75, 0.25], [0.25, 0.75], [0.75, 0.75]];
function candidatos(mask, lv, bloq) {
  let mejor = [];
  for (const [ox, oy] of ORIGENES) {
    const out = [];
    for (let row = 0, y = oy * lv.dy + 30; y < H; row++, y += lv.dy) {
      const off = (row % 2) * lv.dx / 2;
      for (let x = ox * lv.dx + off + 8; x < W; x += lv.dx) if (cabe(x, y, mask, lv, bloq)) out.push([x, y]);
    }
    if (out.length > mejor.length) mejor = out;
  }
  return mejor;
}

export function centroide(mask) {
  let sx = 0, sy = 0, n = 0;
  for (let y = 0; y < H; y += 6) for (let x = 0; x < W; x += 6) if (enRegion(x, y, mask, 0)) { sx += x; sy += y; n++; }
  return n ? [sx / n, sy / n] : null;
}

export function acomodar(reg, bloq, compacto) {
  const niveles = compacto ? NIVELES_COMPACTOS : NIVELES;
  const fichas = [];
  for (let mask = 1; mask < 8; mask++) {
    const lista = reg[mask], n = lista.length;
    if (!n) continue;
    let lv = null, pts = null;
    for (const L of niveles) { const c = candidatos(mask, L, bloq); if (c.length >= n) { lv = L; pts = c; break; } }
    let mostrar = n, mas = 0;
    if (!lv) {
      lv = niveles[niveles.length - 1]; pts = candidatos(mask, lv, bloq);
      mostrar = Math.max(0, pts.length - 1); mas = n - mostrar;
    }
    // las mejor rankeadas al centro de la región
    const cx = pts.reduce((s, p) => s + p[0], 0) / pts.length, cy = pts.reduce((s, p) => s + p[1], 0) / pts.length;
    pts.sort((a, b) => Math.hypot(a[0] - cx, a[1] - cy) - Math.hypot(b[0] - cx, b[1] - cy));
    const usados = pts.slice(0, mostrar + (mas ? 1 : 0));
    for (let i = 0; i < mostrar; i++) fichas.push({ it: lista[i], x: usados[i][0], y: usados[i][1], lv, mask });
    if (mas) fichas.push({ mas, mask, x: usados[mostrar][0], y: usados[mostrar][1], lv });
  }
  return fichas;
}

// ---- las pastillas con el nombre de cada círculo ----------------------------------------------------
export function pastillas(venn, cut, corte, k = 1) {
  return venn.sets.map((s, j) => {
    const dec = s.dec ?? 2;
    const linea = `top ${corte}% · ${s.inv ? "≤" : "≥"} ${(Math.abs(cut[j]) === Infinity ? 0 : cut[j]).toFixed(dec)}`;
    const w = (Math.max(s.nombre.length * 9, linea.length * 6.6) + 30) * k;
    const [x, y] = [CEN[j][0], j === 0 ? CEN[0][1] - R : CEN[j][1] + R];
    return { j, k, nombre: s.nombre, linea, w, x, y, bloq: { x0: x - w / 2 - 6, x1: x + w / 2 + 6, y0: y - 31 * k, y1: y + 31 * k } };
  });
}

// ---- texto -----------------------------------------------------------------------------------------
const PART = new Set(["van", "de", "da", "di", "dos", "das", "del", "der", "den", "ten", "ter", "le", "la", "el", "al", "von", "du", "do", "mac", "lo"]);
export function apellido(n) {
  const t = n.trim().split(/\s+/);
  if (t.length === 1) return t[0];
  let i = t.length - 1;
  while (i > 0 && PART.has(t[i - 1].toLowerCase())) i--;
  return t.slice(i).join(" ");
}
export const corto = (s, max) => (s.length > max ? s.slice(0, max - 1) + "…" : s);
export function iniciales(n, equipo = false) {
  const t = n.trim().split(/\s+/);
  // Un equipo: la letra de sus dos primeras palabras («Manchester City» → MC); «Mainz 05» y «Darmstadt 98» llevan solo la primera.
  if (equipo) { const p = t.filter((w) => /^\p{L}/u.test(w)); return (p.length > 1 ? p[0][0] + p[1][0] : p[0].slice(0, 2)).toUpperCase(); }
  return t.length === 1 ? t[0].slice(0, 2).toUpperCase() : (t[0][0] + apellido(n)[0]).toUpperCase();
}
export const regionTxt = (m, venn) => venn.sets.filter((_, j) => m & (1 << j)).map((s) => s.nombre).join(" + ");
export const cuantos = (m) => (m & 1) + ((m >> 1) & 1) + ((m >> 2) & 1);
