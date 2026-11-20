// El texto «Con estos filtros» de la vista «Forma durante la temporada». Se arma en el navegador sobre los arrays que mandó
// el build (`web/charts/forma.py`): cada cifra sale de ellos. No toca el DOM, así que se puede probar con node.
import { fmt } from "./stats.js";

const MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
export const fechaCorta = (dias) => {
  const d = new Date(dias * 86400000);
  return `${d.getUTCDate()} ${MESES[d.getUTCMonth()]} ${d.getUTCFullYear()}`;
};
export const sg = (v, dec = 2) => (v >= 0 ? "+" : "") + fmt(v, dec);

const media = (v) => v.reduce((a, b) => a + b, 0) / v.length;

// La ventana que TERMINA en el partido i (0-based) abarca los partidos i-V+1 a i, en número de partido: i-V+2 a i+1.
function rango(g, i, V) {
  return { de: i - V + 2, a: i + 1, fechas: `${fechaCorta(g.d[i - V + 1])} a ${fechaCorta(g.d[i])}` };
}

function extremos(g, V) {
  let mejor = -1, peor = -1;
  g.vx.forEach((v, i) => {
    if (v == null) return;
    if (mejor < 0 || v > g.vx[mejor]) mejor = i;
    if (peor < 0 || v < g.vx[peor]) peor = i;
  });
  return { mejor, peor };
}

// Diferencia de xG por partido en los partidos [de, a) (0-based), solo con los que tienen xG. null si no hay ninguno.
function mediaTramo(g, de, a) {
  const v = [];
  for (let i = de; i < a; i++) if (g.xf[i] != null && g.xc[i] != null) v.push(g.xf[i] - g.xc[i]);
  return v.length ? media(v) : null;
}

// Devuelve los párrafos del texto para un equipo en una temporada, en orden.
//   D: la tabla de la vista (`ventana`, `tramo`, `kRuido`, `sigma`); g: los arrays del equipo-temporada; enCurso: ¿va en curso?
export function lecturaForma(D, g, equipo, enCurso) {
  const V = D.ventana, n = g.d.length;
  const dur = `**${equipo}** lleva ${n} partidos`;
  if (n < V) return [`${dur}: todavía no hay una ventana de ${V} partidos y no se dibuja la línea de forma.`];

  const { mejor, peor } = extremos(g, V);
  const out = [];
  if (mejor < 0) {
    out.push(`${dur}, pero Understat no trae los tiros de alguno de ellos y no hay ventana completa para medir.`);
  } else {
    const desc = (i) => {
      const r = rango(g, i, V);
      return `partidos ${r.de} a ${r.a} (${r.fechas}): ${sg(g.vx[i])} de xG por partido y ${sg(g.vg[i])} de goles`;
    };
    if (mejor === peor) {
      out.push(`${dur}, con una sola ventana de ${V} partidos: ${desc(mejor)}.`);
    } else {
      out.push(`${dur}. **Mejor racha de ${V} partidos:** ${desc(mejor)}. **Peor:** ${desc(peor)}.`);
    }
  }

  if (enCurso) {
    out.push(`Esta temporada va en curso: con ${n} partidos no se compara ningún tramo ni se concluye nada sobre su forma.`);
    return out;
  }
  const T = D.tramo;
  if (n < 2 * T) {
    out.push(`Con ${n} partidos no alcanzan dos tramos de ${T} sin cruzarse: no se compara el principio con el final.`);
    return out;
  }
  const primero = mediaTramo(g, 0, T), ultimo = mediaTramo(g, n - T, n);
  if (primero == null || ultimo == null) {
    out.push(`No se compara el principio con el final: a alguno de los dos tramos le faltan los tiros en Understat.`);
    return out;
  }
  const dif = ultimo - primero;
  const umbral = D.kRuido * D.sigma * Math.sqrt(2 / T);
  const tramos = `el último tramo (partidos ${n - T + 1} a ${n}) promedia ${sg(ultimo)} de xG por partido y el primero (1 a ${T}) ${sg(primero)}: una diferencia de ${sg(dif)}`;
  const regla = `La regla: solo se habla de mejora o de caída si la diferencia pasa de ${D.kRuido} veces el ruido esperado de comparar dos tramos de ${T} partidos (${D.kRuido} × ${fmt(D.sigma, 2)} × √(2/${T}) = ${fmt(umbral, 2)}).`;
  if (Math.abs(dif) > umbral) {
    out.push(`**Tendencia:** ${tramos}, más de lo que el azar explicaría. Terminó ${dif > 0 ? "mejor" : "peor"} de como empezó. ${regla}`);
  } else {
    out.push(`**Tendencia:** ${tramos}. Es menos de lo que el azar mueve entre dos tramos así: no se puede decir que mejorara ni que cayera. ${regla}`);
  }
  return out;
}
