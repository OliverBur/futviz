// Textos dinámicos de la caja de lectura ("En lo que estás viendo"): puerto a JS de las funciones
// vivas de `code/insights.py`. Mismas reglas, mismos umbrales y los mismos desempates (el primer
// máximo, el rango promedio entre empatados), porque el texto del navegador tiene que decir lo
// mismo que decía el que armaba Python. `web/react/test/paridad.mjs` lo comprueba contra Python.
//
// Cada generador recibe la tabla `T`, las FILAS que se ven (ya recortadas a temporada, ligas,
// filtros y población de la vista) y cómo se nombra el ámbito ("las 5 ligas", "Serie A"), y
// devuelve `{ fija, salta }`: la frase de estructura fija y el dato que salta (o null).
import {
  ajusteLineal, corr, cuantil, fmt, idxmax, idxmin, media, mediana, miles, rangoPct,
} from "./stats.js";

const col = (T, c, filas) => filas.map((r) => T.c[c][r]);
const quien = (T, r) => T.nombre(r);
const mayus = (t) => t[0].toUpperCase() + t.slice(1);   // no `capitalize`: "xG" saldría "xg"
const fmt1 = (v) => fmt(v, 1);

// La frase fija de las vistas de dos tasas: quién lidera cada eje, o quién lidera los dos.
function lideres(T, filas, colA, colB, fmtA, fmtB, queA, queB) {
  const a = filas[idxmax(col(T, colA, filas))], b = filas[idxmax(col(T, colB, filas))];
  if (quien(T, a) === quien(T, b)) {
    return `**${quien(T, a)}** (${T.equipo(a)}) lidera los dos ejes: ${queA} (${fmtA(T.c[colA][a])}) y ${queB} (${fmtB(T.c[colB][a])}).`;
  }
  return `${mayus(queA)}: **${quien(T, a)}** (${T.equipo(a)}, ${fmtA(T.c[colA][a])}). `
    + `${mayus(queB)}: **${quien(T, b)}** (${T.equipo(b)}, ${fmtB(T.c[colB][b])}).`;
}

// ---- Jugadores -------------------------------------------------------------------------

export function golesXg(T, filas, ambito) {
  const goles = col(T, "goals", filas), xg = col(T, "xG", filas);
  const top = filas[idxmax(goles)];
  const fija = `En ${ambito}, el máximo goleador es **${quien(T, top)}** (${T.equipo(top)}) con ${Math.trunc(T.c.goals[top])} goles sobre ${fmt1(T.c.xG[top])} de xG.`;
  if (filas.length < 5) return { fija, salta: null };
  const dif = goles.map((g, i) => g - xg[i]);
  const salta = `El que más superó su xG es **${quien(T, filas[idxmax(dif)])}** (+${fmt1(Math.max(...dif))} goles) y el que más se quedó corto, **${quien(T, filas[idxmin(dif)])}** (${fmt1(Math.min(...dif))}). Antes de sacar conclusiones: una diferencia así se repite poco de una temporada a la siguiente.`;
  return { fija, salta };
}

export function asistXa(T, filas, ambito) {
  const a = col(T, "a", filas), xa = col(T, "xA", filas);
  const top = filas[idxmax(a)], creador = filas[idxmax(xa)];
  const fija = `En ${ambito} el que más asistió es **${quien(T, top)}** (${T.equipo(top)}) con ${Math.trunc(T.c.a[top])}, y el que más ocasiones generó es **${quien(T, creador)}** (${fmt1(T.c.xA[creador])} de xA).`;
  if (filas.length < 5) return { fija, salta: null };
  const dif = a.map((v, i) => v - xa[i]);
  const salta = `**${quien(T, filas[idxmax(dif)])}** es el que más se pasa de su xA (+${fmt1(Math.max(...dif))} asistencias), pero eso habla tanto de él como de los que remataron sus pases.`;
  return { fija, salta };
}

// Qué tan distintas son las cinco ligas entre sí, comparado con lo que se estiran por dentro.
function perfilEntreLigas(T, filas) {
  const frases = [];
  for (const c of ["xG90", "xA90"]) {
    const porLiga = new Map();
    for (const r of filas) {
      const v = T.c[c][r];
      if (v == null) continue;
      const l = T.liga(r);
      if (!porLiga.has(l)) porLiga.set(l, []);
      porLiga.get(l).push(v);
    }
    if (porLiga.size < 2) continue;
    const med = [...porLiga.values()].map(mediana);
    const lo = fmt(Math.min(...med)), hi = fmt(Math.max(...med));
    frases.push(lo === hi ? `las de ${c} son las cinco ${lo}` : `las de ${c} van de ${lo} a ${hi}`);
  }
  if (!frases.length) return "";
  return `Y los cinco colores se mezclan más de lo que parece — las medianas por liga: ${frases.join(" y ")}. La diferencia **entre** ligas es mucho más chica que la que hay **dentro** de cada una.`;
}

// El más "completo": la mejor suma de percentiles. Y cuántos superan el promedio en los dos ejes.
function completo(T, filas, cx, cy) {
  const x = col(T, cx, filas), y = col(T, cy, filas);
  const rx = rangoPct(x), ry = rangoPct(y);
  const r = filas[idxmax(rx.map((v, i) => v + ry[i]))];
  const mx = media(x), my = media(y);
  let nAmbos = 0;
  for (let i = 0; i < x.length; i++) if (x[i] > mx && y[i] > my) nAmbos++;
  return [r, nAmbos];
}

export function perfil(T, filas, ambito) {
  const rem = filas[idxmax(col(T, "xG90", filas))], cre = filas[idxmax(col(T, "xA90", filas))];
  const fija = `En ${ambito}, el perfil más rematador es **${quien(T, rem)}** (${fmt(T.c.xG90[rem])} xG90) y el más creador **${quien(T, cre)}** (${fmt(T.c.xA90[cre])} xA90).`;
  if (filas.length < 5) return { fija, salta: null };
  const [c, nAmbos] = completo(T, filas, "xG90", "xA90");
  let salta = `El perfil más completo es **${quien(T, c)}** (${fmt(T.c.xG90[c])} xG90 y ${fmt(T.c.xA90[c])} xA90). Solo ${nAmbos} de ${filas.length} jugadores superan el promedio en los dos ejes a la vez: hacer las dos cosas es raro.`;
  const entre = perfilEntreLigas(T, filas);
  if (entre) salta += " " + entre;
  return { fija, salta };
}

export function recuperar(T, filas, ambito) {
  const rec = col(T, "recoveries90", filas), fal = col(T, "fouls90", filas);
  const top = filas[idxmax(rec)];
  const fija = `En ${ambito}, el que más pelota recupera es **${quien(T, top)}** (${T.equipo(top)}) con ${fmt(T.c.recoveries90[top])} por 90', contra una media de ${fmt(media(rec))}.`;
  if (filas.length < 5) return { fija, salta: null };
  const rr = rangoPct(rec), rf = rangoPct(fal);
  const limpio = rr.map((v, i) => v - rf[i]);
  const e = filas[idxmax(limpio)], o = filas[idxmin(limpio)];
  const salta = `El que mejor combina las dos cosas es **${quien(T, e)}** (${T.equipo(e)}): ${fmt(T.c.recoveries90[e])} recuperaciones por 90' con solo ${fmt(T.c.fouls90[e])} faltas. En el extremo opuesto, **${quien(T, o)}** (${T.equipo(o)}) comete ${fmt(T.c.fouls90[o])} faltas por 90' y recupera ${fmt(T.c.recoveries90[o])}.`;
  return { fija, salta };
}

export function disputar(T, filas, ambito) {
  const ent = filas[idxmax(col(T, "tkl_w90", filas))], lec = filas[idxmax(col(T, "interceptions90", filas))];
  const fija = `En ${ambito}, el que más entradas gana es **${quien(T, ent)}** (${fmt(T.c.tkl_w90[ent])} por 90') y el que más intercepta, **${quien(T, lec)}** (${fmt(T.c.interceptions90[lec])} por 90').`;
  if (filas.length < 5) return { fija, salta: null };
  const [c, nAmbos] = completo(T, filas, "tkl_w90", "interceptions90");
  const salta = `El más completo de los dos lados es **${quien(T, c)}** (${T.equipo(c)}), con ${fmt(T.c.tkl_w90[c])} entradas y ${fmt(T.c.interceptions90[c])} intercepciones por 90'. ${nAmbos} de ${filas.length} jugadores superan el promedio en los dos ejes.`;
  return { fija, salta };
}

export function dosFases(T, filas, ambito) {
  const arriba = filas[idxmax(col(T, "xga90", filas))], atras = filas[idxmax(col(T, "recoveries90", filas))];
  const fija = `En ${ambito}, el que más produce arriba es **${quien(T, arriba)}** (${fmt(T.c.xga90[arriba])} de xG+xA por 90') y el que más recupera atrás, **${quien(T, atras)}** (${fmt(T.c.recoveries90[atras])} por 90').`;
  if (filas.length < 5) return { fija, salta: null };
  const [c, nAmbos] = completo(T, filas, "xga90", "recoveries90");
  const puesto = T.posicion(c);          // "" si el jugador no cruzó por nombre con fbref
  const nombre = `${quien(T, c)}** (${T.equipo(c)}${puesto ? `, ${puesto.toLowerCase()})` : ")"}`;
  const salta = `El que mejor pesa en las dos es **${nombre}: ${fmt(T.c.xga90[c])} de producción y ${fmt(T.c.recoveries90[c])} recuperaciones por 90'. Solo ${nAmbos} de ${filas.length} jugadores superan el promedio en los dos ejes a la vez — el cuadrante de arriba a la derecha es el más vacío del gráfico, y por eso el interesante.`;
  return { fija, salta };
}

export function pasesClave(T, filas, ambito) {
  const fija = `En ${ambito}: ` + lideres(T, filas, "kp90", "xA90", fmt1, fmt, "más pases clave por 90'", "más xA por 90'");
  if (filas.length < 5) return { fija, salta: null };
  const kp = col(T, "kp90", filas), med = mediana(kp);
  const frec = filas.filter((r) => T.c.kp90[r] >= med && T.c.kp90[r] > 0);
  if (frec.length < 3) return { fija, salta: null };
  const porPase = frec.map((r) => T.c.xA90[r] / T.c.kp90[r]);
  const mejor = frec[idxmax(porPase)];
  const salta = `Entre los que dan pases clave seguido, el que más peligro saca de cada uno es **${quien(T, mejor)}**: ${fmt(Math.max(...porPase))} de xA por pase clave, contra ${fmt(media(porPase))} del grupo.`;
  return { fija, salta };
}

export function construir(T, filas, ambito) {
  const fija = `En ${ambito}: ` + lideres(T, filas, "xgbuild90", "xga90", fmt, fmt,
    "más construcción por 90'", "más producción directa (xG + xA) por 90'");
  if (filas.length < 5) return { fija, salta: null };
  const med = mediana(col(T, "xga90", filas));
  const poco = filas.filter((r) => T.c.xga90[r] <= med);
  const c = poco[idxmax(poco.map((r) => T.c.xgbuild90[r]))];
  const salta = `El constructor más puro es **${quien(T, c)}**: ${fmt(T.c.xgbuild90[c])} de xG de construcción por 90' y solo ${fmt(T.c.xga90[c])} de producción directa — está en la mayoría de las jugadas peligrosas de su equipo sin que el tiro o el último pase sean suyos.`;
  return { fija, salta };
}

export function centros(T, filas, ambito) {
  const fija = `En ${ambito}: ` + lideres(T, filas, "crosses90", "xA90", fmt1, fmt,
    "quien más centra por 90'", "quien más xA por 90'");
  if (filas.length < 5) return { fija, salta: null };
  const corte = cuantil(col(T, "crosses90", filas), 0.75);
  const muchos = filas.filter((r) => T.c.crosses90[r] >= corte);
  if (!muchos.length) return { fija, salta: null };
  const p = muchos[idxmin(muchos.map((r) => T.c.xA90[r]))];
  const salta = `Entre los que más centran, el que menos peligro genera es **${quien(T, p)}**: ${fmt1(T.c.crosses90[p])} centros por 90' y ${fmt(T.c.xA90[p])} de xA — volumen que casi no se convierte en ocasión.`;
  return { fija, salta };
}

// ---- Equipos ---------------------------------------------------------------------------

const X_DEF = "sh_Standard_SoT%", Y_DEF = "sh_Standard_G/SoT";
const POSESION = "ov_Poss", ASIST_90 = "ov_Per 90 Minutes_Ast";
const SOTA_90 = "p90_SoTA", GA_90 = "gk_Performance_GA90";

export function definicion(T, filas, ambito) {
  const y = col(T, Y_DEF, filas);
  const mejor = filas[idxmax(y)];
  const fija = `En ${ambito}, **${quien(T, mejor)}** es el que más gol saca por tiro a puerta (${fmt(T.c[Y_DEF][mejor])} G/SoT) contra una media de ${fmt(media(y))}.`;
  if (filas.length < 4) return { fija, salta: null };
  // El mayor desajuste entre lo bien que llega y lo bien que define, por percentil dentro del ámbito.
  const rx = rangoPct(col(T, X_DEF, filas)), ry = rangoPct(y);
  const brecha = rx.map((v, i) => v - ry[i]);
  const iAlto = idxmax(brecha), iBajo = idxmin(brecha);
  let salta;
  if (Math.abs(brecha[iAlto]) >= Math.abs(brecha[iBajo])) {
    const e = filas[iAlto];
    salta = `El desajuste más grande es el de **${quien(T, e)}**: está entre los que más tiros a puerta consiguen (${fmt1(T.c[X_DEF][e])}%) pero de los que menos los aprovechan (${fmt(T.c[Y_DEF][e])} G/SoT).`;
  } else {
    const e = filas[iBajo];
    salta = `El caso opuesto lo tiene **${quien(T, e)}**: llega poco a puerta (${fmt1(T.c[X_DEF][e])}%) y aun así es de los más letales cuando llega (${fmt(T.c[Y_DEF][e])} G/SoT).`;
  }
  return { fija, salta };
}

export function creacion(T, filas, ambito) {
  const pos = filas[idxmax(col(T, POSESION, filas))], ast = filas[idxmax(col(T, ASIST_90, filas))];
  const fija = `En ${ambito}, **${quien(T, pos)}** es el que más balón tiene (${fmt1(T.c[POSESION][pos])}%) y **${quien(T, ast)}** el que más asistencias da por 90' (${fmt(T.c[ASIST_90][ast])}).`;
  if (filas.length < 4) return { fija, salta: null };
  const rp = rangoPct(col(T, POSESION, filas)), ra = rangoPct(col(T, ASIST_90, filas));
  const brecha = rp.map((v, i) => v - ra[i]);
  const iAlto = idxmax(brecha), iBajo = idxmin(brecha);
  let salta;
  if (Math.abs(brecha[iAlto]) >= Math.abs(brecha[iBajo])) {
    const e = filas[iAlto];
    salta = `El caso de posesión que no crea es **${quien(T, e)}**: de los que más balón tienen (${fmt1(T.c[POSESION][e])}%) y de los que menos asistencias dan (${fmt(T.c[ASIST_90][e])} por 90').`;
  } else {
    const e = filas[iBajo];
    salta = `El más directo es **${quien(T, e)}**: tiene poco el balón (${fmt1(T.c[POSESION][e])}%) y aun así da ${fmt(T.c[ASIST_90][e])} asistencias por 90', de lo más alto.`;
  }
  return { fija, salta };
}

export function defensa(T, filas, ambito) {
  const mg = filas[idxmin(col(T, GA_90, filas))], mt = filas[idxmin(col(T, SOTA_90, filas))];
  const fija = `En ${ambito}, **${quien(T, mg)}** es el que menos goles encaja (${fmt(T.c[GA_90][mg])} por 90') y **${quien(T, mt)}** el que menos tiros a puerta recibe (${fmt(T.c[SOTA_90][mt])} por 90').`;
  if (filas.length < 4) return { fija, salta: null };
  const x = col(T, SOTA_90, filas), y = col(T, GA_90, filas);
  const [pendiente, base] = ajusteLineal(x, y);
  const resto = y.map((v, i) => v - (pendiente * x[i] + base));
  const i = idxmax(resto.map(Math.abs));
  const e = filas[i], delta = resto[i];
  const sentido = delta > 0 ? "más" : "menos";
  const salta = `Respecto de lo que sus tiros recibidos hacían esperar, el que más se desvía es **${quien(T, e)}**: recibe ${fmt(T.c[SOTA_90][e])} tiros a puerta por 90' y encaja ${fmt(T.c[GA_90][e])}, ${fmt(Math.abs(delta))} goles ${sentido} de lo normal para ese volumen.`;
  return { fija, salta };
}

export const GENERADORES = {
  goles_xg: golesXg, asist_xa: asistXa, perfil, recuperar, disputar, dos_fases: dosFases,
  pases_clave: pasesClave, construir, centros, definicion, creacion, defensa,
};

// ---- Mapa de calor de los tiros ---------------------------------------------------------------
// Trabaja sobre SUMAS (`{ n, g, sd, na, ga, nc, ni }`: tiros, goles, suma de distancias, dentro del
// área, goles dentro del área, dentro del área chica, desde la izquierda) y no sobre tiros sueltos:
// el navegador no recibe los 225.000 (ver `shot_map.tabla_agregada`). Mismas reglas que `ins.tiros`.
const NOTABLE_LADO = 1.5, NOTABLE_DIST = 3.0, NOTABLE_CONV = 1.5, NOTABLE_CHICA = 6.0;

// Verbo que corresponde a la dirección real del cambio (tenerlo fijo en la plantilla es la forma más
// fácil de escribir una frase que se contradice a sí misma).
const verbo = (nuevo, viejo, baja, sube, igual = "quedó igual", tol = 0.005) =>
  Math.abs(nuevo - viejo) < tol ? igual : (nuevo < viejo ? baja : sube);

export function tiros(sub, base, frase, ambito) {
  if (!sub.n) return { fija: "No hay tiros de este tipo en la temporada elegida.", salta: null };
  const n = sub.n;
  const area = (100 * sub.na) / n, dist = sub.sd / n, conv = (100 * sub.g) / n;
  const fija = `De los ${miles(n)} tiros ${frase}de ${ambito}, el **${fmt(area, 0)}%** salió desde dentro del área. La distancia media a la portería fue de ${fmt(dist, 1)} m y acabó en gol el ${fmt(conv, 1)}%.`;

  const izq = (100 * sub.ni) / n, izqBase = (100 * base.ni) / base.n;
  const chica = (100 * sub.nc) / n, chicaBase = (100 * base.nc) / base.n;
  const distBase = base.sd / base.n, convBase = (100 * base.g) / base.n;
  // Los candidatos se normalizan por su umbral de notabilidad; gana el cociente más alto y, si
  // empatan, el de nombre mayor (Python compara las tuplas).
  const cand = [
    [Math.abs(izq - 50) / NOTABLE_LADO, "lado"], [Math.abs(dist - distBase) / NOTABLE_DIST, "dist"],
    [Math.abs(conv - convBase) / NOTABLE_CONV, "conv"], [Math.abs(chica - chicaBase) / NOTABLE_CHICA, "chica"],
  ].reduce((m, c) => (c[0] > m[0] || (c[0] === m[0] && c[1] > m[1]) ? c : m));
  const [peso, cual] = cand;

  let salta;
  if (peso < 1) {
    // Ninguna selección se separa del promedio: se cuenta la estructura del mapa, que siempre está.
    const fuera = n - sub.na;
    const convFuera = fuera ? (100 * (sub.g - sub.ga)) / fuera : NaN;
    const convDentro = sub.na ? (100 * sub.ga) / sub.na : NaN;
    salta = `El ${fmt(100 - area, 0)}% se remató desde fuera del área, y de esos entró solo el ${fmt(convFuera, 1)}% contra el ${fmt(convDentro, 1)}% de los de dentro.`;
  } else if (cual === "lado") {
    salta = `El **${fmt(izq, 0)}%** salió desde la mitad izquierda del ataque y el ${fmt(100 - izq, 0)}% desde la derecha, contra un reparto de ${fmt(izqBase, 0)}/${fmt(100 - izqBase, 0)} en el tiro medio de ${ambito}.`;
  } else if (cual === "dist") {
    salta = `Se remata desde mucho más **${verbo(dist, distBase, "cerca", "lejos")}** que el tiro medio de ${ambito}: ${fmt(dist, 1)} m contra ${fmt(distBase, 1)} m.`;
  } else if (cual === "chica") {
    salta = `El **${fmt(chica, 0)}%** salió desde el área chica, contra el ${fmt(chicaBase, 0)}% del tiro medio de ${ambito}.`;
  } else {
    salta = `Entra el **${fmt(conv, 1)}%** contra el ${fmt(convBase, 1)}% del tiro medio de ${ambito}, aun rematando desde ${verbo(dist, distBase, "más cerca", "más lejos", "la misma distancia")}.`;
  }
  return { fija, salta };
}

// ---- Explorador: el r² del par elegido ------------------------------------------------------

export function banda(r) {
  const a = Math.abs(r);
  if (a < 0.3) return "Casi no se pisan: cada una mide algo que la otra no capta, así que el gráfico está comparando dos cosas de verdad distintas.";
  if (a < 0.6) return "Se pisan a medias: hay tendencia, pero queda mucha variación que una no explica de la otra.";
  if (a < 0.85) return "Se pisan bastante: saber una ya dice buena parte de la otra.";
  return "Son casi la misma información: una se puede predecir desde la otra, y ponerlas en ejes distintos no agrega nada.";
}

// `{ fija, salta }` del explorador sobre los pares (x, y) que se ven. Devuelve 'pocos' / 'plano'
// como causa cuando no hay r que medir (dos cosas distintas que el aviso tiene que decir).
export function lecturaExplorador(xs, ys, etX, etY, entidad) {
  const n = xs.length;
  const b = (t) => `**${t}**`;
  if (n < 3) {
    return { fija: `No hay puntos suficientes para medir la relación entre ${b(etX)} y ${b(etY)} con estos filtros.`, salta: null };
  }
  const r = corr(xs, ys);
  if (Number.isNaN(r)) {
    return { fija: `Con estos filtros, ${b(etX)} o ${b(etY)} vale lo mismo en los ${n} ${entidad} que quedan: sin variación en uno de los dos ejes no hay relación que medir.`, salta: null };
  }
  const signo = r >= 0 ? "+" : "−";
  return {
    fija: `**r² = ${fmt(r * r * 100, 0)}%** entre ${b(etX)} y ${b(etY)} (r = ${signo}${Math.abs(r).toFixed(2)}), sobre ${n} ${entidad}.`,
    salta: `${banda(r)} El r² es la parte de la variación de una que queda explicada por la otra: **cuanto más chico, más distintas son**. ${r >= 0 ? "El signo es positivo: suben juntas." : "El signo es negativo: cuando una sube, la otra baja."}`,
  };
}
