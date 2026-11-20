// Las cuentas y el texto «Con estos filtros» de la vista «De dónde sale el xG». Se arman en el navegador sobre la
// tabla que mandó el build (`web/charts/origen_xg.py`): cada cifra sale de ella. No toca el DOM, así que se puede
// probar con node.
import { fmt, media, miles } from "./stats.js";

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
    return [
      `**${temporada} va en curso (${jornadas} jornadas).** Con tan pocos partidos por equipo el balón parado casi no tiene muestra ` +
      `(unos pocos córners cambian el porcentaje de un equipo), así que aquí no se compara a los equipos. En ${ambito}, ` +
      `el balón parado es en promedio ${fmt(prom, 0)}% del xG a favor de los ${n} equipos. Para sacar conclusiones, mejor una temporada cerrada.`,
    ];
  }
  const alto = extremo(filas, (i) => pesoBP(D, i, "f"), true);
  const bajo = extremo(filas, (i) => pesoBP(D, i, "f"), false);
  const concede = extremo(filas, (i) => bpPorPartido(D, i, "c"), true);
  const promConcede = media(filas.map((i) => bpPorPartido(D, i, "c")));
  const p = [
    `**A favor.** En ${ambito}, ${temporada}, el equipo que más depende del balón parado es ${nombre(D, alto)}: ` +
    `${fmt(pesoBP(D, alto, "f"), 0)}% de su xG (${fmt(bpPorPartido(D, alto, "f"), 2)} por partido). El que menos, ${nombre(D, bajo)}: ` +
    `${fmt(pesoBP(D, bajo, "f"), 0)}% (${fmt(bpPorPartido(D, bajo, "f"), 2)} por partido). El promedio de los ${n} equipos es ${fmt(prom, 0)}%.`,
    `**En contra.** El que más xG de balón parado concede por partido es ${nombre(D, concede)}: ` +
    `${fmt(bpPorPartido(D, concede, "c"), 2)} (${fmt(pesoBP(D, concede, "c"), 0)}% de todo el xG que le hacen), contra ` +
    `${fmt(promConcede, 2)} en promedio.`,
  ];
  if (fijada >= 0) {
    p.push(`**${nombre(D, fijada)}.** ${fmt(pesoBP(D, fijada, "f"), 0)}% de su xG a favor sale del balón parado ` +
      `(${fmt(bpPorPartido(D, fijada, "f"), 2)} por partido, ${miles(suma(BALON_PARADO, (id) => tirosSeg(D, fijada, "f", id)))} tiros) ` +
      `y ${fmt(pesoBP(D, fijada, "c"), 0)}% del que concede.`);
  }
  p.push("**La regla.** El peso de balón parado es córner + tiro libre directo + otro balón parado, entre el xG total sin penales. " +
    "El equipo con más y con menos se escoge por ese peso a favor; el que más concede, por el xG de balón parado en contra por partido. " +
    "El promedio es la media simple de los equipos, sin ponderar. Una sola temporada es poca muestra: no leas la diferencia entre dos equipos cercanos.");
  return p;
}
