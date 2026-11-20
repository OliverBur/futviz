// Las filas de «Tabla real vs. esperada» y el texto «Con estos filtros». Se arman en el navegador sobre la tabla
// que mandó el build (`web/charts/tabla_esperada.py`): cada cifra sale de ella. No toca el DOM, así que se puede
// probar con node.
import { corr, suma } from "./stats.js";

export const MAX_NOMBRADOS = 3;          // cuántos equipos se nombran en cada sentido
export const CASI_NADA = 0.2;            // |r| menor que esto: «casi nada» se repite
export const BASTANTE = 0.4;             // |r| mayor que esto: «bastante» se repite

const menos = (s) => s.replace("-", "−");
export const d1 = (x) => menos(x.toFixed(1));
export const d2 = (x) => menos(x.toFixed(2));
export const conSigno = (x) => (x >= 0 ? "+" : "") + d1(x);
const miles = (n) => String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, ",");

// Los equipos de una liga y temporada, en el orden de la tabla real.
export function filasDe(D, liga, temporada) {
  const f = D.f, li = D.ligas.indexOf(liga), ti = D.temporadas.indexOf(temporada);
  const out = [];
  for (let i = 0; i < f.l.length; i++) {
    if (f.l[i] !== li || f.t[i] !== ti) continue;
    out.push({
      nombre: D.nombres[f.e[i]], pj: f.pj[i], pts: f.pts[i], xp: f.xp[i], gf: f.gf[i], gc: f.gc[i],
      xgf: f.xgf[i], xgc: f.xgc[i], pr: f.pr[i], pe: f.pe[i],
      dif: f.pts[i] - f.xp[i],            // más de cero: sumó más puntos de los que valían sus ocasiones
      lugares: f.pe[i] - f.pr[i],         // más de cero: está más arriba de donde lo pone xPts
    });
  }
  return out.sort((a, b) => a.pr - b.pr);
}

// Las cifras de una liga y temporada: correlación, error medio y cuánto suman los xPts contra los puntos.
export function resumen(filas) {
  const pts = filas.map((r) => r.pts), xp = filas.map((r) => r.xp);
  return {
    n: filas.length,
    r: corr(pts, xp),
    mae: suma(filas.map((r) => Math.abs(r.dif))) / filas.length,
    pts: suma(pts), xp: suma(xp),
  };
}

// Los que más se alejan en cada sentido: de mayor a menor diferencia, los `MAX_NOMBRADOS` primeros que pasan del
// error medio de las temporadas cerradas (`umbral`). Lo que queda por debajo es lo normal y no se nombra.
export function extremos(filas, umbral) {
  const ord = [...filas].sort((a, b) => b.dif - a.dif || a.pr - b.pr);
  return {
    mas: ord.filter((r) => r.dif >= umbral).slice(0, MAX_NOMBRADOS),
    menos: ord.filter((r) => r.dif <= -umbral).reverse().slice(0, MAX_NOMBRADOS),
  };
}

function cuanto(r) {
  const a = Math.abs(r);
  return a < CASI_NADA ? "casi nada" : a < BASTANTE ? "algo" : "bastante";
}

// Devuelve los párrafos del texto (con **negritas**), en orden. La temporada en curso no se concluye.
export function lecturaTabla(D, liga, temporada, filas) {
  const enCurso = D.enCurso && D.enCurso[temporada] != null;
  if (!filas.length) return [`No hay datos de ${liga} en ${temporada}.`];
  if (enCurso) {
    const pj = filas.map((r) => r.pj);
    return [
      `**${temporada} va en curso.** Los equipos de ${liga} llevan de ${Math.min(...pj)} a ${Math.max(...pj)} partidos. ` +
      `Con tan pocos partidos, la diferencia entre puntos y xPts es casi toda azar, así que aquí no se concluye nada de ella. ` +
      `Para leer quién rinde de más o de menos, elige una temporada cerrada.`,
    ];
  }
  const R = resumen(filas), u = D.errorMedio, P = D.persistencia;
  const { mas, menos: abajo } = extremos(filas, u);
  const lista = (xs) => xs.map((r) => `${r.nombre} (${conSigno(r.dif)})`).join(", ");
  const t = [];
  t.push(mas.length
    ? `**Sumaron más de lo que valían sus ocasiones:** ${lista(mas)}.`
    : `**Sumaron más de lo que valían sus ocasiones:** ninguno por más de ${d1(u)} puntos.`);
  t.push(abajo.length
    ? `**Sumaron menos:** ${lista(abajo)}.`
    : `**Sumaron menos:** ninguno por más de ${d1(u)} puntos.`);
  t.push(`Se nombran, como máximo ${MAX_NOMBRADOS} por lado, los equipos cuya diferencia pasa de ${d1(u)} puntos, que es lo que se alejan en promedio ` +
    `los puntos de los xPts en las temporadas cerradas: por debajo de eso, es lo normal.`);
  t.push(`En ${liga} ${temporada}, la correlación entre puntos y xPts es ${d2(R.r)} y el error medio es de ${d1(R.mae)} puntos. ` +
    `Los xPts suman ${miles(R.xp)} y los puntos reales ${miles(R.pts)}: en un empate se reparten 2 puntos y no 3, y el xG de ` +
    `Understat suma más de lo que entra.`);
  t.push(`**Cuánto se repite.** De una temporada cerrada a la siguiente, la correlación de (puntos − xPts) de un mismo club es ` +
    `${d2(P.r)} (${miles(P.n)} pares; intervalo aproximado de ${d2(P.lo)} a ${d2(P.hi)}): se repite ${cuanto(P.r)}. ` +
    (Math.abs(P.r) < CASI_NADA
      ? `Un club que sumó de más o de menos un año no suele hacerlo el siguiente: esta diferencia es sobre todo suerte del año y no sirve para adivinar cómo le irá.`
      : `Una parte de la diferencia se mantiene de un año a otro, pero la mayor parte cambia.`));
  return t;
}
