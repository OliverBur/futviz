// La lógica de los cuadrantes y del zoom a un cuadrante (`src/zoom.js`).
//
//   node test/zonas.mjs
import assert from "node:assert/strict";
import { ajustarA, esBase, poligonoZona, vistaDeZona, zonaDe } from "../src/zoom.js";

// Dos líneas (vertical en 2, horizontal en 5): los cuatro cuadrantes, con los puntos sobre la línea del lado de arriba/derecha.
const rect = { tipo: "rect", cx: 2, cy: 5 };
assert.equal(zonaDe(rect, 3, 6), "tr");
assert.equal(zonaDe(rect, 3, 4), "br");
assert.equal(zonaDe(rect, 1, 6), "tl");
assert.equal(zonaDe(rect, 1, 4), "bl");
assert.equal(zonaDe(rect, 2, 5), "tr");

// La vertical en 0.5 y la diagonal y = x: arriba de la diagonal es "marcó más de lo esperado".
const diag = { tipo: "diag", cx: 0.5 };
assert.equal(zonaDe(diag, 0.8, 1.0), "tr");
assert.equal(zonaDe(diag, 0.8, 0.4), "br");
assert.equal(zonaDe(diag, 0.2, 0.3), "tl");
assert.equal(zonaDe(diag, 0.2, 0.1), "bl");

// Cada punto cae dentro del polígono de SU cuadrante (y de ningún otro), en las dos clases de líneas.
function dentro(poli, x, y) {
  let c = false;
  for (let i = 0, j = poli.length - 1; i < poli.length; j = i++) {
    const [xi, yi] = poli[i], [xj, yj] = poli[j];
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) c = !c;
  }
  return c;
}
for (const lineas of [rect, diag]) {
  for (const [x, y] of [[3, 6], [3, 0.1], [0.1, 6], [0.1, 0.05], [1.7, 1.2], [1.7, 2.4]]) {
    const z = zonaDe(lineas, x, y);
    for (const id of ["tr", "tl", "br", "bl"]) {
      assert.equal(dentro(poligonoZona(lineas, id, 100), x, y), id === z, `${lineas.tipo}: (${x}, ${y}) en ${id}, debía estar solo en ${z}`);
    }
  }
}

// La vista de un cuadrante se recorta JUSTO en las líneas (por los lados que son línea) y deja margen por los otros.
const base = { x0: 0, x1: 10, y0: 0, y1: 2 };
const pts = [{ x: 6, y: 1 }, { x: 8, y: 1.5 }];
const rect2 = { tipo: "rect", cx: 5, cy: 0.5 };
const v = vistaDeZona(pts, rect2, "tr", base, 0.1);
assert.equal(v.x0, 5); assert.equal(v.y0, 0.5);                         // el corte, justo en las líneas
assert.ok(v.x1 > 8 && v.y1 > 1.5, "margen por los lados que no son línea");
const bl = vistaDeZona([{ x: 1, y: 0.2 }, { x: 3, y: 0.4 }], rect2, "bl", base, 0.1);
assert.equal(bl.x1, 5); assert.equal(bl.y1, 0.5);                       // abajo a la izquierda: las líneas son el borde de arriba y de la derecha
assert.ok(bl.x0 < 1 && bl.y0 <= 0.2);                                   // margen por los lados que no son línea
// Con la diagonal solo la vertical es recta: el cuadrante de arriba a la derecha arranca en la esquina (cx, cx).
const dg = vistaDeZona([{ x: 0.8, y: 1.0 }, { x: 1.2, y: 1.4 }], { tipo: "diag", cx: 0.5 }, "tr", { x0: 0, x1: 2, y0: 0, y1: 2 }, 0.1);
assert.equal(dg.x0, 0.5); assert.ok(dg.y0 <= 0.5 + 1e-9);
// Nunca se sale de la base ni se acerca más de la cuenta, y sin puntos no cambia nada.
const u = vistaDeZona([{ x: 9.9, y: 1.95 }, { x: 10, y: 2 }], { tipo: "rect", cx: 9, cy: 1.9 }, "tr", base, 0.5);
assert.ok(u.x1 <= 10 && u.y1 <= 2 && u.x0 >= 0 && u.y0 >= 0);
assert.equal(vistaDeZona([], rect, "tr", base), base);
assert.ok(!esBase(v, base));
// `ajustarA` (la vista de arranque) sí conserva la proporción de la base.
const w = ajustarA(pts, base, 0);
assert.ok(Math.abs((w.y1 - w.y0) / (w.x1 - w.x0) - 0.2) < 1e-9, "ajustarA conserva la proporción de la base");
console.log("zonas.mjs: ok");
