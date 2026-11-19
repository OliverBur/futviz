// La agregación del mapa de tiros, sin React (se prueba en Node contra Python: `test/paridad.mjs`).
// La tabla (`shot_map.tabla_agregada`) trae los tiros ya sumados por (temporada, jugada, parte del
// cuerpo, celda de 2×2 m); aquí se suma lo que pida el filtro.
import { fmt, miles } from "./stats.js";

export const SUMAS = ["n", "g", "sd", "na", "ga", "nc", "ni"];

// `ti`: índice de temporada o null (todas). `tipo`: la opción del filtro (`{col, valor}`) o null (todos).
// Devuelve `{ n, g }` por celda (arreglos de nx*ny) y las sumas totales de `SUMAS`.
export function agregar(T, ti, tipo) {
  const F = T.f;
  const ncel = T.nx * T.ny;
  const n = new Float64Array(ncel), g = new Float64Array(ncel);
  const tot = Object.fromEntries(SUMAS.map((k) => [k, 0]));
  let col = null, idx = -1;
  if (tipo && tipo.col === "situation") { col = F.s; idx = T.jugadas.indexOf(tipo.valor); }
  else if (tipo && tipo.col === "body_part") { col = F.b; idx = T.partes.indexOf(tipo.valor); }
  for (let i = 0; i < F.t.length; i++) {
    if (ti !== null && F.t[i] !== ti) continue;
    if (col && col[i] !== idx) continue;
    n[F.celda[i]] += F.n[i]; g[F.celda[i]] += F.g[i];
    for (const k of SUMAS) tot[k] += F[k][i];
  }
  return { n, g, tot };
}

// ---- Los tiros de un jugador o de un equipo ----------------------------------------------------------------
// Vienen de otra tabla, la de la temporada (`shot_map.tabla_temporada`, `datos-tiros-<t>.js`): un tiro por fila.
// Es la misma población que la agregada (sin penales ni autogoles, a menos de 36 m de la línea de fondo), así
// que los promedios de las 5 ligas de `agregar` son la vara de comparación.

// Índices de fila de `D.c` de la selección. `modo`: "jugador" (`id` es el índice en `D.jug`) o "equipo" (`id` en
// `D.eq`; `contra` pide los tiros que le hicieron en vez de los que hizo). `tipo`: la opción del filtro o null.
export function filasDe(T, D, { modo, id, contra, tipo }) {
  const c = D.c;
  const de = modo === "jugador" ? c.j : contra ? c.v : c.e;
  let col = null, idx = -1;
  if (tipo && tipo.col === "situation") { col = c.s; idx = T.jugadas.indexOf(tipo.valor); }
  else if (tipo && tipo.col === "body_part") { col = c.b; idx = T.partes.indexOf(tipo.valor); }
  const filas = [];
  for (let i = 0; i < de.length; i++) {
    if (de[i] !== id) continue;
    if (col && col[i] !== idx) continue;
    filas.push(i);
  }
  return filas;
}

// Las mismas sumas que `agregar` (`SUMAS`), más el xG, de las filas elegidas. Posición en decímetros.
export function sumar(T, D, filas) {
  const c = D.c, medio = T.ancho / 2;
  const t = { n: 0, g: 0, xg: 0, sd: 0, na: 0, ga: 0, nc: 0, ni: 0 };
  for (const i of filas) {
    const x = c.x[i] / 10, y = c.y[i] / 10, lado = Math.abs(x - medio);
    t.n += 1; t.g += c.g[i]; t.xg += c.xg[i] / 1000; t.sd += Math.hypot(y, x - medio);
    if (y <= 16.5 && lado <= 20.16) { t.na += 1; t.ga += c.g[i]; }
    if (y <= 5.5 && lado <= 9.16) t.nc += 1;
    if (x < medio) t.ni += 1;
  }
  return t;
}

// Lo que dice la caja de lectura de un jugador o un equipo. Sin gemelo en Python: solo existe en esta vista, así
// que no entra en la prueba de paridad. `s` son sus sumas; `base`, las de todos los tiros de esa temporada y tipo.
export function lecturaEntidad({ nombre, clubes, modo, contra, temporada, frase, s, base }) {
  if (!s.n) {
    const de = modo === "equipo" && contra ? `contra ${nombre}` : `de ${nombre}`;
    return { fija: `No hay tiros ${frase}${de} en ${temporada}.`, salta: null };
  }
  const goles = `${miles(s.g)} ${s.g === 1 ? "gol" : "goles"} contra ${fmt(s.xg, 1)} de xG`;
  let fija;
  if (modo === "jugador") {
    fija = `**${nombre}** (${clubes}) hizo ${miles(s.n)} remates ${frase}en ${temporada}, sin penales: ${goles}.`;
  } else if (contra) {
    fija = `Los rivales de **${nombre}** remataron ${miles(s.n)} veces ${frase}contra su portería en ${temporada}, sin penales: ${goles}.`;
  } else {
    fija = `**${nombre}** remató ${miles(s.n)} veces ${frase}en ${temporada}, sin penales: ${goles}.`;
  }
  if (s.n < 5) return { fija, salta: null };
  const area = (100 * s.na) / s.n, areaBase = (100 * base.na) / base.n;
  const dist = s.sd / s.n, distBase = base.sd / base.n;
  let salta = `El **${fmt(area, 0)}%** salió desde dentro del área (el promedio de las 5 ligas es ${fmt(areaBase, 0)}%) y el remate medio se hizo a ${fmt(dist, 1)} m de la portería (${fmt(distBase, 1)} m en las 5 ligas).`;
  if (s.n < 20) salta += ` Con solo ${s.n} remates, un tiro más o menos mueve mucho estos porcentajes.`;
  return { fija, salta };
}
