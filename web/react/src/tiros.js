// La agregación del mapa de tiros, sin React (se prueba en Node contra Python: `test/paridad.mjs`).
// La tabla (`shot_map.tabla_agregada`) trae los tiros ya sumados por (temporada, jugada, parte del
// cuerpo, celda de 2×2 m); aquí se suma lo que pida el filtro.
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
