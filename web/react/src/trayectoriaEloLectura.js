// El texto «Con estos filtros» de la vista «Trayectoria del club en ELO». Se arma en el navegador sobre la tabla que mandó el
// build (`web/charts/trayectoria_elo.py`): cada cifra sale de ella. No toca el DOM, así que se puede probar con node.
//
// Los ELO se redondean al entero ANTES de restar: así el cambio que se escribe es justo la resta de los dos números que se ven.
import { mediana, miles } from "./stats.js";

export const elo = (v) => miles(Math.round(v));
export const sg = (d) => (d > 0 ? `+${miles(d)}` : d < 0 ? `−${miles(-d)}` : "0");

// Los valores de un club con una medida, redondeados (null donde no jugó en las 5 ligas), uno por temporada.
export const valoresClub = (c, medida) => c[medida].map((v) => (v == null ? null : Math.round(v)));

// Los cambios de una temporada a la SIGUIENTE (solo entre temporadas seguidas con dato: un hueco no se une).
export function cambiosClub(c, medida) {
  const v = valoresClub(c, medida), out = [];
  for (let i = 1; i < v.length; i++) if (v[i] != null && v[i - 1] != null) out.push({ i, de: v[i - 1], a: v[i], d: v[i] - v[i - 1] });
  return out;
}

// Todos los cambios de todos los clubes de las 5 ligas (el telón de fondo contra el que se mide el de los elegidos).
export const cambiosTodos = (D, medida) => D.clubes.flatMap((c) => cambiosClub(c, medida).map((x) => x.d));

const masGrande = (v, f) => v.reduce((m, x) => (f(x) > f(m) ? x : m));

// Devuelve los párrafos del texto, en orden.
//   D: la tabla de la vista; elegidos: nombres de club; medida: "pre" | "med" | "fin"; etiqueta: cómo se llama la medida.
export function lecturaElo(D, elegidos, medida, etiqueta) {
  const T = D.temporadas;
  const por = new Map(D.clubes.map((c) => [c.n, c]));
  const sel = elegidos.map((n) => por.get(n)).filter(Boolean);
  if (!sel.length) return ["Elige al menos un club para ver su trayectoria."];

  const out = [];
  const camb = sel.flatMap((c) => cambiosClub(c, medida).map((x) => ({ ...x, club: c.n })));
  const cuando = (x) => `de ${elo(x.de)} (${T[x.i - 1]}) a ${elo(x.a)} (${T[x.i]})`;
  if (!camb.length) {
    out.push(sel.length === 1
      ? `**${sel[0].n}** no tiene dos temporadas seguidas en las 5 ligas dentro de ${T[0]} a ${T[T.length - 1]}: no hay un cambio entre temporadas que medir.`
      : `Ninguno de los clubes elegidos tiene dos temporadas seguidas en las 5 ligas dentro de ${T[0]} a ${T[T.length - 1]}: no hay un cambio entre temporadas que medir.`);
  } else {
    const sube = masGrande(camb, (x) => x.d), baja = masGrande(camb, (x) => -x.d);
    const quien = sel.length === 1 ? "" : " entre los clubes elegidos";
    const partes = [];
    partes.push(sube.d > 0
      ? `**la mayor subida** de una temporada a la siguiente${quien} es la de **${sube.club}**: ${cuando(sube)}, ${sg(sube.d)} puntos.`
      : `Ninguno${sel.length === 1 ? "" : " de los clubes elegidos"} subió de una temporada a la siguiente.`);
    partes.push(baja.d < 0
      ? `**La mayor caída** es la de **${baja.club}**: ${cuando(baja)}, ${sg(baja.d)} puntos.`
      : `Ninguno bajó.`);
    out.push(`Con el ELO «${etiqueta.toLowerCase()}»: ${partes.join(" ")}`);

    const todos = cambiosTodos(D, medida);
    const m = Math.max(sube.d > 0 ? sube.d : 0, baja.d < 0 ? -baja.d : 0);
    if (m > 0) {
      const k = todos.filter((d) => Math.abs(d) >= m).length;
      out.push(`Para dimensionarlo: en las 5 ligas un club cambia ${elo(mediana(todos.map(Math.abs)))} puntos de una temporada a la siguiente `
        + `(mediana, sin signo), y solo ${miles(k)} de los ${miles(todos.length)} cambios llegan a ${miles(m)} puntos o más.`);
    }
  }

  const u = T.length - 1;
  const ref = Math.round(D.ref[medida][u]);
  const con = sel.map((c) => ({ n: c.n, v: valoresClub(c, medida)[u] })).filter((x) => x.v != null).sort((a, b) => b.v - a.v);
  const sin = sel.filter((c) => valoresClub(c, medida)[u] == null).map((c) => c.n);
  if (con.length) {
    out.push(`En ${T[u]} el promedio de las 5 ligas es ${elo(ref)}. Distancia al promedio de los clubes elegidos: `
      + `${con.map((x) => `${x.n} ${elo(x.v)} (${sg(x.v - ref)})`).join(", ")}.`
      + (sin.length ? ` ${sin.join(" y ")} no jugó${sin.length > 1 ? "n" : ""} esa temporada en las 5 ligas.` : ""));
  } else {
    out.push(`${sin.join(" y ")} no jugó${sin.length > 1 ? "n" : ""} en ${T[u]} en las 5 ligas: no hay ELO suyo en esa temporada.`);
  }
  return out;
}
