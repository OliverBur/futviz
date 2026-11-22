// Las cuentas y el texto «Con estos filtros» de la vista «De dónde sale el xG». Se arman en el navegador sobre la
// tabla que mandó el build (`web/charts/origen_xg.py`): cada cifra sale de ella. No toca el DOM, así que se puede
// probar con node.
import { fmt, media } from "./stats.js";

export const BALON_PARADO = ["corner", "libre", "otro"];
export const APILADO = ["corner", "libre", "otro", "abierta"];   // el orden en que se apilan

const suma = (ids, f) => ids.reduce((s, id) => s + f(id), 0);

// `lado`: "f" (a favor) o "c" (en contra). xG de un segmento de la fila `i`, y su total (sin penales).
export const xgSeg = (D, i, lado, id) => D.c[`x${lado}_${id}`][i];
export const tirosSeg = (D, i, lado, id) => D.c[`t${lado}_${id}`][i];
export const xgTotal = (D, i, lado) => suma(APILADO, (id) => xgSeg(D, i, lado, id));
export const tirosTotal = (D, i, lado) => suma(APILADO, (id) => tirosSeg(D, i, lado, id));

// Lo que se dibuja de un segmento: el % del xG de la fila, o el xG por partido.
export const valorSeg = (D, i, lado, id, modo) => (modo === "pct"
  ? (100 * xgSeg(D, i, lado, id)) / xgTotal(D, i, lado)
  : xgSeg(D, i, lado, id) / D.c.pj[i]);

// Lo que ordena y lo que se rotula a la derecha: un segmento, o "bp", el balón parado entero.
export const valorOrden = (D, i, lado, orden, modo) => (orden === "bp"
  ? suma(BALON_PARADO, (id) => valorSeg(D, i, lado, id, modo))
  : valorSeg(D, i, lado, orden, modo));

// El peso de balón parado (córner + tiro libre directo + otro) en el xG de la fila, en % (el número de la regla).
export const pesoBP = (D, i, lado) => valorOrden(D, i, lado, "bp", "pct");
// El xG por partido de balón parado.
export const bpPorPartido = (D, i, lado) => valorOrden(D, i, lado, "bp", "xg");

function extremo(filas, f, mayor) {
  let mejor = -1;
  for (const i of filas) if (mejor < 0 || (mayor ? f(i) > f(mejor) : f(i) < f(mejor))) mejor = i;
  return mejor;
}

const nombre = (D, i) => D.nombres[D.f.j[i]];

// Los párrafos del texto, en orden. `filas` son las filas que se ven (la liga y la temporada elegidas); `ambito`
// es cómo se llama esa liga o "las 5 ligas"; `jornadas` es el número de jornadas si la temporada va en curso (y
// entonces no se concluye nada de ella); `fijada` es la fila del equipo resaltado, si está entre `filas`.
export function lecturaOrigen({ D, filas, ambito, temporada, jornadas, fijada = -1 }) {
  if (!filas.length) return ["No hay equipos con estos filtros."];
  const n = filas.length;
  const prom = media(filas.map((i) => pesoBP(D, i, "f")));
  if (jornadas) {
    return [`${ambito}, ${temporada} (en curso, ${jornadas} jornadas): con tan pocos partidos el balón parado casi no tiene muestra, ` +
      `así que no se comparan equipos.`];
  }
  if (fijada >= 0) {
    return [`${nombre(D, fijada)}: ${fmt(pesoBP(D, fijada, "f"), 0)}% de su xG sale del balón parado ` +
      `(${fmt(bpPorPartido(D, fijada, "f"), 2)} por partido) y ${fmt(pesoBP(D, fijada, "c"), 0)}% del que concede.`];
  }
  const alto = extremo(filas, (i) => pesoBP(D, i, "f"), true);
  const bajo = extremo(filas, (i) => pesoBP(D, i, "f"), false);
  return [`En ${ambito} ${temporada}, el balón parado pesa ${fmt(prom, 0)}% del xG en promedio: el que más depende es ` +
    `${nombre(D, alto)} (${fmt(pesoBP(D, alto, "f"), 0)}%) y el que menos, ${nombre(D, bajo)} (${fmt(pesoBP(D, bajo, "f"), 0)}%).`];
}
