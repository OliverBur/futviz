// El texto "Con estos filtros" de la vista Edad. Se arma en el navegador sobre la tabla que mandó el build
// (`web/charts/edad.py`): cada cifra sale de ella, y las frases que afirman algo (pico firme, caída clara) lo
// hacen con una regla explícita sobre los intervalos, no a ojo. No toca el DOM, así que se puede probar con node.

import { miles } from "./stats.js";

const TOL_MESETA = 3;     // puntos de % de minutos: "cerca del máximo" en el panel de minutos
const PICO_FIRME = 3;      // años: si el 80% de las réplicas del bootstrap cae en un rango así de angosto, el pico es firme
const r0 = (x) => Math.round(x);

function edadesCerca(e, med) {
  const m = Math.max(...med), i = med.indexOf(m);
  let lo = i, hi = i;
  while (lo > 0 && med[lo - 1] >= m - TOL_MESETA) lo--;
  while (hi < med.length - 1 && med[hi + 1] >= m - TOL_MESETA) hi++;
  return { max: m, edad: e[i], de: e[lo], a: e[hi] };
}

export function lecturaMinutos(D, pos, etiqueta) {
  const m = D.minutos[pos];
  if (!m || !m.e.length) return `No hay edades con ${D.minJugadores} jugador-temporadas o más para ${etiqueta.toLowerCase()}.`;
  const tramos = m.grupos.map((g) => `${g.de}-${g.a}: ${r0(g.med)}%`).join(", ");
  const jov = m.grupos[0], mayor = m.grupos.find((g) => g.de === 25);
  let t = `**Minutos.** Mediana del % de los minutos de su club por tramo de edad: ${tramos}.`;
  if (jov && mayor) {
    t += ` De ${jov.de} a ${jov.a} años, ${r0(jov.mas50)}% de los jugador-temporadas pasa de la mitad de los minutos (de ${mayor.de} a ${mayor.a}, ${r0(mayor.mas50)}%).`;
  }
  const c = edadesCerca(m.e, m.med);
  t += c.de === c.a
    ? ` La mediana más alta es ${r0(c.max)}% a los ${c.edad} años.`
    : ` La mediana más alta es ${r0(c.max)}% a los ${c.edad} años, y de los ${c.de} a los ${c.a} se queda a menos de ${TOL_MESETA} puntos de ese valor.`;
  return t;
}

function frasePos(D, pos) {
  const r = D.rendimiento[pos];
  if (!r) return `No hay suficientes jugadores con ${D.minutosCambio} minutos o más en dos temporadas seguidas para estimar la curva.`;
  const { e, curva, lo, hi } = r;
  const n = e.length - 1, i = e.indexOf(r.pico);
  const rango = (k) => `${r0(lo[k])} a ${r0(hi[k])}`;
  const sobre = r0(r.picoValor - 100);
  const partes = [];
  const pruebas = `(${miles(r.pares_total)} pares de ${miles(r.jugadores)} jugadores, ${e[0]} a ${e[n]} años)`;
  if (i === 0) {
    partes.push(`La curva baja desde el primer tramo con datos (${e[0]} años): a los ${e[n]} está en ${r0(curva[n])} (franja ${rango(n)}) contra 100 a los ${r.ancla}. No hay un pico dentro del rango: el máximo cae en su borde, a los ${e[0]}.`);
    if (pos === "Defensa") partes.push("Eso es actividad defensiva y no calidad, así que una baja no significa que defiendan peor.");
  } else if (i === n) {
    partes.push(`La curva sigue subiendo hasta los ${e[n]} años, donde termina el rango con datos (${r0(curva[n])}, franja ${rango(n)}): no se ve dónde dejaría de subir.`);
  } else {
    const firme = r.picoP90 - r.picoP10 <= PICO_FIRME;
    partes.push(`Sube de ${r0(curva[0])} a los ${e[0]} años hasta un máximo de ${r0(r.picoValor)} a los ${r.pico} (${sobre >= 0 ? "+" : ""}${sobre}% frente a los ${r.ancla}).`);
    partes.push(firme
      ? `El máximo es firme: en el 80% de las réplicas cae entre los ${r.picoP10} y los ${r.picoP90}.`
      : `El máximo no es firme: en el 80% de las réplicas cae entre los ${r.picoP10} y los ${r.picoP90}, así que los datos no fijan un pico claro.`);
    partes.push(hi[n] < r.picoValor
      ? `A los ${e[n]} años la curva está en ${r0(curva[n])} (franja ${rango(n)}), por debajo del máximo de forma clara.`
      : `A los ${e[n]} años está en ${r0(curva[n])} (franja ${rango(n)}): no se distingue de forma clara una caída respecto del máximo.`);
  }
  return `${partes.join(" ")} ${pruebas}`;
}

// Devuelve los párrafos del texto, en orden.
export function lecturaEdad(D, pos, etiqueta, posiciones) {
  const salida = [lecturaMinutos(D, pos, etiqueta)];
  if (pos === "Portero") {
    salida.push("**Rendimiento.** No se calcula para porteros: ni npxG + xA ni las acciones defensivas describen lo que hacen.");
  } else if (pos === "campo") {
    for (const p of posiciones) if (p !== "campo" && p !== "Portero") salida.push(`**Rendimiento, ${p.toLowerCase()}.** ${frasePos(D, p)}`);
  } else {
    salida.push(`**Rendimiento.** ${frasePos(D, pos)}`);
  }
  return salida;
}
