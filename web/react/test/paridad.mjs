// Paridad del texto dinámico: el JS (`src/insights.js`) contra la referencia de Python
// (`code/insights.py`), sobre las tablas reales que viajan al sitio.
//
//   python test/gen_paridad.py && node test/paridad.mjs
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { pathToFileURL } from "node:url";

const aqui = dirname(fileURLToPath(import.meta.url));
globalThis.window = globalThis;               // las tablas son scripts que cuelgan de window.futvizDatos
globalThis.futvizDatos = {};

const { prepararTabla } = await import("../src/datos.js");
const { GENERADORES } = await import("../src/insights.js");

const tablas = {};
for (const nombre of ["jugadores", "equipos"]) {
  await import(pathToFileURL(join(aqui, "fixtures", "react", `datos-${nombre}.js`)).href);
  tablas[nombre] = prepararTabla(globalThis.futvizDatos[nombre]);
}
const casos = JSON.parse(readFileSync(join(aqui, "fixtures", "paridad.json"), "utf8"));

// Las filas que ve cada caso: el mismo recorte que hace la vista (temporada, ligas, filtros y población).
function filas(T, c) {
  const t = T.temporadas.indexOf(c.temporada);
  const li = c.liga == null ? null : T.ligas.indexOf(c.liga);
  const pos = c.posiciones.map((p) => T.posiciones.indexOf(p));
  const niv = c.nivel == null ? -1 : T.niveles.indexOf(c.nivel);
  const out = [];
  for (let r = 0; r < T.n; r++) {
    if (T.f.t[r] !== t) continue;
    if (li != null && T.f.l[r] !== li) continue;
    if (pos.length && !pos.includes(T.f.p[r])) continue;
    if (niv >= 0 && T.f.v[r] !== niv) continue;
    if (c.sub21 && !T.f.u[r]) continue;
    if (c.requiere.some((col) => T.c[col][r] == null)) continue;
    out.push(r);
  }
  return out;
}

// El orden de las filas de Python es el de la tabla; en la población se conserva.
let ok = 0, mal = 0;
const porInsight = {};
const fallos = [];
for (const c of casos) {
  const T = tablas[c.entidad];
  const f = filas(T, c);
  const ambito = c.liga ?? "las 5 ligas";
  const vacio = c.entidad === "jugadores" ? "Ningún jugador cumple los filtros elegidos." : "Ningún equipo cumple los filtros elegidos.";
  const r = f.length ? GENERADORES[c.insight](T, f, ambito) : { fija: vacio, salta: null };
  const igual = r.fija === c.fija && (r.salta ?? null) === (c.salta ?? null);
  porInsight[c.insight] = porInsight[c.insight] || [0, 0];
  porInsight[c.insight][igual ? 0 : 1]++;
  if (igual) ok++; else { mal++; if (fallos.length < 12) fallos.push({ c, r }); }
}

// ---- mapa de tiros: la agregación en el navegador contra el texto de Python ------------------------------
const { tiros } = await import("../src/insights.js");
const { agregar } = await import("../src/tiros.js");
await import(pathToFileURL(join(aqui, "fixtures", "react", "datos-tiros.js")).href);
const TT = globalThis.futvizDatos.tiros;
const casosT = JSON.parse(readFileSync(join(aqui, "fixtures", "paridad-tiros.json"), "utf8"));
let okT = 0, malT = 0;
for (const c of casosT) {
  const ti = c.temporada === "todas" ? null : TT.temporadas.indexOf(c.temporada);
  const tipo = c.tipo === "todos" ? null : TT.tipos.find((t) => t.id === c.tipo);
  const sub = agregar(TT, ti, tipo).tot, base = agregar(TT, ti, null).tot;
  const r = tiros(sub, base, c.frase, c.ambito);
  const igual = r.fija === c.fija && (r.salta ?? null) === (c.salta ?? null);
  if (igual) okT++; else { malT++; if (fallos.length < 12) fallos.push({ c: { insight: "tiros", temporada: c.temporada, liga: null, posiciones: [], nivel: c.tipo, sub21: false, fija: c.fija, salta: c.salta }, r }); }
}
ok += okT; mal += malT;
porInsight.tiros = [okT, malT];

console.log(`paridad: ${ok} iguales, ${mal} distintos, de ${casos.length + casosT.length} casos`);
for (const [k, [a, b]] of Object.entries(porInsight)) console.log(`  ${k.padEnd(12)} ${a} ok / ${b} distintos`);
for (const { c, r } of fallos) {
  console.log(`\n--- ${c.insight} · ${c.temporada} · ${c.liga ?? "todas"} · pos=${c.posiciones.join("+") || "-"} · nivel=${c.nivel ?? "-"} · sub21=${c.sub21}`);
  console.log("PY fija :", c.fija); console.log("JS fija :", r.fija);
  console.log("PY salta:", c.salta); console.log("JS salta:", r.salta);
}
process.exit(mal ? 1 : 0);
