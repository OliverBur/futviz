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
  const goles = col(T, "np_goals", filas), xg = col(T, "np_xg", filas);
  const top = filas[idxmax(goles)];
  const fija = `En ${ambito}, el máximo goleador sin penales es **${quien(T, top)}** (${T.equipo(top)}) con ${Math.trunc(T.c.np_goals[top])} goles sobre ${fmt1(T.c.np_xg[top])} de xG.`;
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
  let nAmbos = 0, nx = 0, ny = 0;
  for (let i = 0; i < x.length; i++) {
    if (x[i] > mx) nx++;
    if (y[i] > my) ny++;
    if (x[i] > mx && y[i] > my) nAmbos++;
  }
  // los que saldrían arriba en los dos si un eje no tuviera que ver con el otro: con distribuciones
  // sesgadas, menos de la mitad supera el promedio de cada eje, así que "pocos" hay que medirlo contra esto
  return [r, nAmbos, Math.floor((nx * ny) / x.length + 0.5)];
}

// Cuántos superan el promedio en los dos ejes, comparado con lo que daría el azar.
function frasesAmbos(nAmbos, esperado, n) {
  const base = `${miles(nAmbos)} de ${miles(n)} jugadores superan el promedio en los dos ejes a la vez`;
  if (nAmbos > esperado * 1.15) return `${base}, más de los ${miles(esperado)} que saldrían si un eje no tuviera que ver con el otro: hacer una cosa suele ir con la otra.`;
  if (nAmbos < esperado * 0.85) return `Solo ${base}, menos de los ${miles(esperado)} que saldrían si un eje no tuviera que ver con el otro: hacer las dos cosas es raro.`;
  return `${base}, más o menos los ${miles(esperado)} que saldrían si un eje no tuviera que ver con el otro.`;
}

export function perfil(T, filas, ambito) {
  const rem = filas[idxmax(col(T, "xG90", filas))], cre = filas[idxmax(col(T, "xA90", filas))];
  const fija = `En ${ambito}, el perfil más rematador es **${quien(T, rem)}** (${fmt(T.c.xG90[rem])} xG90) y el más creador **${quien(T, cre)}** (${fmt(T.c.xA90[cre])} xA90).`;
  if (filas.length < 5) return { fija, salta: null };
  const [c, nAmbos, esperado] = completo(T, filas, "xG90", "xA90");
  let salta = `El perfil más completo es **${quien(T, c)}** (${fmt(T.c.xG90[c])} xG90 y ${fmt(T.c.xA90[c])} xA90). ${frasesAmbos(nAmbos, esperado, filas.length)}`;
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
  const [c, nAmbos, esperado] = completo(T, filas, "tkl_w90", "interceptions90");
  const salta = `El más completo de los dos lados es **${quien(T, c)}** (${T.equipo(c)}), con ${fmt(T.c.tkl_w90[c])} entradas y ${fmt(T.c.interceptions90[c])} intercepciones por 90'. ${frasesAmbos(nAmbos, esperado, filas.length)}`;
  return { fija, salta };
}

export function dosFases(T, filas, ambito) {
  const arriba = filas[idxmax(col(T, "xga90", filas))], atras = filas[idxmax(col(T, "recoveries90", filas))];
  const fija = `En ${ambito}, el que más produce arriba es **${quien(T, arriba)}** (${fmt(T.c.xga90[arriba])} de xG+xA por 90') y el que más recupera atrás, **${quien(T, atras)}** (${fmt(T.c.recoveries90[atras])} por 90').`;
  if (filas.length < 5) return { fija, salta: null };
  const [c, nAmbos, esperado] = completo(T, filas, "xga90", "recoveries90");
  const puesto = T.posicion(c);          // "" si el jugador no cruzó por nombre con fbref
  const nombre = `${quien(T, c)}** (${T.equipo(c)}${puesto ? `, ${puesto.toLowerCase()})` : ")"}`;
  const salta = `El que mejor pesa en las dos es **${nombre}: ${fmt(T.c.xga90[c])} de producción y ${fmt(T.c.recoveries90[c])} recuperaciones por 90'. ${frasesAmbos(nAmbos, esperado, filas.length)}`;
  return { fija, salta };
}

export function pasesClave(T, filas, ambito) {
  const fija = `En ${ambito}: ` + lideres(T, filas, "kp90", "xA90", fmt1, fmt, "más pases clave por 90'", "más xA por 90'");
  if (filas.length < 5) return { fija, salta: null };
  const kp = col(T, "kp90", filas), med = mediana(kp);
  // con menos de 10 pases clave en la temporada, el xA por pase es ruido (un central con 3 pases y un gol)
  const frec = filas.filter((r) => T.c.kp90[r] >= med && T.c.kp90[r] > 0 && T.c.key_passes[r] >= 10);
  if (frec.length < 3) return { fija, salta: null };
  const porPase = frec.map((r) => T.c.xA90[r] / T.c.kp90[r]);
  const mejor = frec[idxmax(porPase)];
  const salta = `Entre los que dan pases clave seguido (10 o más en la temporada), el que más peligro saca de cada uno es **${quien(T, mejor)}**: ${fmt(Math.max(...porPase))} de xA por pase clave, contra ${fmt(media(porPase))} del grupo.`;
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

// Las tres vistas "por 90'" de goles y asistencias. Mismo texto que `xg_goles_90`, `xa_asist_90` y `pases_asist`
// de `code/insights.py`. `ELITE_PCT` tiene que valer lo mismo que allá (y que `referencia.zonas.pct` de la gráfica).
export const ELITE_PCT = 0.7;
const LINEA_PERCENTIL = 70;   // Cover vs. Stopper: ver `LINEA_PERCENTIL` de insights.py

export function xgGoles90(T, filas, ambito) {
  const fija = `En ${ambito}: ` + lideres(T, filas, "npxg90", "npg90", fmt, fmt,
    "más xG por 90' sin penales", "más goles por 90' sin penales");
  if (filas.length < 5) return { fija, salta: null };
  const corte = cuantil(col(T, "npxg90", filas), ELITE_PCT);
  const elite = filas.filter((r) => T.c.npxg90[r] >= corte);
  const mas = elite.filter((r) => T.c.npg90[r] >= T.c.npxg90[r]);
  const menos = elite.filter((r) => T.c.npg90[r] < T.c.npxg90[r]);
  let salta = `El ${Math.round((1 - ELITE_PCT) * 100)}% con más xG por 90' son ${elite.length} jugadores (desde ${fmt(corte)}): ${mas.length} marcan al menos lo que generan y ${menos.length} marcan menos.`;
  if (menos.length) {
    const p = menos[idxmin(menos.map((r) => T.c.npg90[r] - T.c.npxg90[r]))];
    salta += ` El que más se queda corto es **${quien(T, p)}**: ${fmt(T.c.npg90[p])} goles contra ${fmt(T.c.npxg90[p])} de xG por 90'.`;
  }
  return { fija, salta };
}

export function xaAsist90(T, filas, ambito) {
  const fija = `En ${ambito}: ` + lideres(T, filas, "xA90", "a90", fmt, fmt,
    "más xA por 90'", "más asistencias por 90'");
  if (filas.length < 5) return { fija, salta: null };
  const dif = filas.map((r) => T.c.a90[r] - T.c.xA90[r]);
  const arriba = filas[idxmax(dif)], abajo = filas[idxmin(dif)];
  const salta = `**${quien(T, arriba)}** es el que más se pasa de su xA (${sg(Math.max(...dif))} asistencias por 90'), y a **${quien(T, abajo)}** es a quien más le desperdician (${sg(Math.min(...dif))}). En los dos casos habla tanto de ellos como de quienes remataron sus pases.`;
  return { fija, salta };
}

export function pasesAsist(T, filas, ambito) {
  const fija = `En ${ambito}: ` + lideres(T, filas, "kp90", "a90", fmt1, fmt, "más pases clave por 90'", "más asistencias por 90'");
  if (filas.length < 5) return { fija, salta: null };
  const corte = cuantil(col(T, "kp90", filas), 0.75);
  const muchos = filas.filter((r) => T.c.kp90[r] >= corte);
  if (!muchos.length) return { fija, salta: null };
  const p = muchos[idxmin(muchos.map((r) => T.c.a90[r]))];
  const salta = `Entre el 25% que más pases clave da, al que menos le convierten es **${quien(T, p)}**: ${fmt1(T.c.kp90[p])} pases clave por 90' y ${fmt(T.c.a90[p])} asistencias.`;
  return { fija, salta };
}

// Defensa: Corte vs. Cobertura. Mismo texto que `cover_stopper` de `code/insights.py`.
export function coverStopper(T, filas, ambito) {
  const f0 = (v) => fmt(v, 0);
  const fija = `En ${ambito}: ` + lideres(T, filas, "pct_stopper", "pct_cover", f0, f0, "más corte", "más cobertura");
  if (filas.length < 5) return { fija, salta: null };
  let a = 0, b = 0, c = 0;
  for (const r of filas) {
    const stop = T.c.pct_stopper[r] > LINEA_PERCENTIL, cov = T.c.pct_cover[r] > LINEA_PERCENTIL;
    if (stop && !cov) a++; else if (cov && !stop) b++; else if (stop && cov) c++;
  }
  const e = filas[idxmax(filas.map((r) => T.c.pct_stopper[r] + T.c.pct_cover[r]))];
  const salta = `De ${filas.length} defensas, ${a} se inclinan al corte, ${b} a la cobertura, ${c} a los dos y ${filas.length - a - b - c} a ninguno (las líneas están en el percentil ${LINEA_PERCENTIL}). El más completo es **${quien(T, e)}** (${T.equipo(e)}): ${f0(T.c.pct_stopper[e])} de corte y ${f0(T.c.pct_cover[e])} de cobertura.`;
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
  const salta = `Entre el 25% que más centra, el que menos peligro genera es **${quien(T, p)}**: ${fmt1(T.c.crosses90[p])} centros por 90' y ${fmt(T.c.xA90[p])} de xA — volumen que casi no se convierte en ocasión.`;
  return { fija, salta };
}

// ---- Equipos ---------------------------------------------------------------------------
// xG y goles de Understat por partido y sin penales (`web/charts/xg_equipos.py`). Mismo texto que las
// funciones del mismo nombre de `code/insights.py`.

const XG_FAV = "xg_fav", XG_CON = "xg_con", XG_DIF = "xg_dif";
const GOL_FAV = "gol_fav", GOL_CON = "gol_con";

// Con el signo a la vista en los positivos ("+0.45", "-0.12"), como `_sg` de Python.
const sg = (v, dec = 2) => (v >= 0 ? "+" : "") + fmt(v, dec);

export function definicion(T, filas, ambito) {
  const gf = col(T, GOL_FAV, filas), xf = col(T, XG_FAV, filas);
  const top = filas[idxmax(gf)];
  const fija = `En ${ambito}, **${quien(T, top)}** es el que más goles mete por partido (${fmt(T.c[GOL_FAV][top])}) con ${fmt(T.c[XG_FAV][top])} de xG.`;
  if (filas.length < 4) return { fija, salta: null };
  const dif = gf.map((g, i) => g - xf[i]);
  const arriba = filas[idxmax(dif)], abajo = filas[idxmin(dif)];
  const mx = Math.max(...dif), mn = Math.min(...dif);
  const mas = mx > 0
    ? `El que más superó su xG es **${quien(T, arriba)}** (${sg(mx)} goles por partido)`
    : `Ninguno superó su xG: el que más cerca quedó es **${quien(T, arriba)}** (${fmt(mx)} goles por partido)`;
  const menos = mn < 0
    ? `y el que más se quedó corto, **${quien(T, abajo)}** (${fmt(mn)}).`
    : `y todos lo superaron: el que menos, **${quien(T, abajo)}** (${sg(mn)}).`;
  return { fija, salta: `${mas} ${menos} Una diferencia así se repite poco de una temporada a la siguiente.` };
}

export function creacion(T, filas, ambito) {
  const crea = filas[idxmax(col(T, XG_FAV, filas))], cede = filas[idxmin(col(T, XG_CON, filas))];
  const fija = quien(T, crea) === quien(T, cede)
    ? `En ${ambito}, **${quien(T, crea)}** es el que más ocasiones crea y el que menos concede: ${fmt(T.c[XG_FAV][crea])} de xG a favor y ${fmt(T.c[XG_CON][crea])} en contra por partido.`
    : `En ${ambito}, **${quien(T, crea)}** es el que más ocasiones crea (${fmt(T.c[XG_FAV][crea])} de xG por partido) y **${quien(T, cede)}** el que menos concede (${fmt(T.c[XG_CON][cede])}).`;
  if (filas.length < 4) return { fija, salta: null };
  const dif = col(T, XG_DIF, filas);
  const mejor = filas[idxmax(dif)], peor = filas[idxmin(dif)];
  const salta = `El que más domina las ocasiones es **${quien(T, mejor)}**: crea ${fmt(T.c[XG_FAV][mejor])} y concede ${fmt(T.c[XG_CON][mejor])} por partido (${sg(Math.max(...dif))}). En el otro extremo, **${quien(T, peor)}** crea ${fmt(T.c[XG_FAV][peor])} y concede ${fmt(T.c[XG_CON][peor])} (${sg(Math.min(...dif))}).`;
  return { fija, salta };
}

export function defensa(T, filas, ambito) {
  const mg = filas[idxmin(col(T, GOL_CON, filas))], mx = filas[idxmin(col(T, XG_CON, filas))];
  const fija = quien(T, mg) === quien(T, mx)
    ? `En ${ambito}, **${quien(T, mg)}** es el que menos goles recibe (${fmt(T.c[GOL_CON][mg])} por partido) y también el que menos xG concede (${fmt(T.c[XG_CON][mg])}).`
    : `En ${ambito}, **${quien(T, mg)}** es el que menos goles recibe (${fmt(T.c[GOL_CON][mg])} por partido) y **${quien(T, mx)}** el que menos xG concede (${fmt(T.c[XG_CON][mx])}).`;
  if (filas.length < 4) return { fija, salta: null };
  const dif = col(T, GOL_CON, filas).map((g, i) => g - T.c[XG_CON][filas[i]]);
  const i = idxmax(dif.map(Math.abs));
  const e = filas[i], delta = dif[i];
  const sentido = delta > 0 ? "más" : "menos";
  const salta = `El que más se aleja de la diagonal es **${quien(T, e)}**: concede ${fmt(T.c[XG_CON][e])} de xG por partido y recibe ${fmt(T.c[GOL_CON][e])} goles, ${fmt(Math.abs(delta))} ${sentido} de lo que decían las ocasiones. Ahí cuentan juntos el portero, la defensa y la suerte.`;
  return { fija, salta };
}

// «Cantidad vs. calidad de los tiros» y «Local vs. visitante». SIN gemelo en `code/insights.py` ni prueba de paridad
// (como `lecturaEntidad` de `tiros.js`): el texto fijo de las dos vistas sí vive allá (`cantidad_calidad_por_que`,
// `local_visitante_por_que`) y lleva las cifras de los datos. Las líneas de la primera, en el percentil `LINEA_PCT` de lo
// que se ve en cada eje, son las mismas que dibuja `ScatterVista` (`referencia.cuantil`).
const LINEA_PCT = 0.8;   // el mismo valor que `LINEA_PCT` de insights.py
const TIROS_PP = "tiros_pp", XG_TIRO = "xg_tiro", XP_LOCAL = "xp_local_pp", XP_VISITA = "xp_visita_pp";

// "A, B y C" (los primeros `n` de la lista).
const lista = (v, n = 3) => {
  const p = v.slice(0, n);
  return p.length > 1 ? `${p.slice(0, -1).join(", ")} y ${p[p.length - 1]}` : p[0];
};

export function cantidadCalidad(T, filas, ambito) {
  const tiros = col(T, TIROS_PP, filas), xgt = col(T, XG_TIRO, filas);
  const a = filas[idxmax(tiros)], b = filas[idxmax(xgt)];
  const fija = quien(T, a) === quien(T, b)
    ? `En ${ambito}, **${quien(T, a)}** lidera los dos ejes: ${fmt1(T.c[TIROS_PP][a])} tiros por partido y ${fmt(T.c[XG_TIRO][a], 3)} de xG por tiro.`
    : `En ${ambito}, **${quien(T, a)}** es el que más tira (${fmt1(T.c[TIROS_PP][a])} tiros por partido) y **${quien(T, b)}** el que tira con más calidad (${fmt(T.c[XG_TIRO][b], 3)} de xG por tiro).`;
  if (filas.length < 5) return { fija, salta: null };
  const cx = cuantil(tiros, LINEA_PCT), cy = cuantil(xgt, LINEA_PCT);
  const muchos = filas.filter((r) => T.c[TIROS_PP][r] >= cx);
  const buenos = muchos.filter((r) => T.c[XG_TIRO][r] >= cy);
  const n = buenos.length;
  const nombres = [...buenos].sort((p, q) => T.c[TIROS_PP][q] - T.c[TIROS_PP][p]).map((r) => `**${quien(T, r)}**`);
  let salta = `Arriba a la derecha (más de ${fmt1(cx)} tiros y ${fmt(cy, 3)} de xG por tiro) `
    + (n === 0 ? "no queda ningún equipo."
      : n <= 3 ? `${n === 1 ? "queda 1 equipo" : `quedan ${n} equipos`}: ${lista(nombres)}.`
        : `quedan ${n} equipos; los que más tiran son ${lista(nombres)}.`);
  const p = muchos[idxmin(muchos.map((r) => T.c[XG_TIRO][r]))];
  salta += ` Entre los que más tiran, el que menos calidad por tiro tiene es **${quien(T, p)}**: ${fmt1(T.c[TIROS_PP][p])} tiros por partido y ${fmt(T.c[XG_TIRO][p], 3)} de xG por tiro.`;
  return { fija, salta };
}

export function localVisitante(T, filas, ambito) {
  const pl = col(T, XP_LOCAL, filas), pv = col(T, XP_VISITA, filas);
  const a = filas[idxmax(pl)], b = filas[idxmax(pv)];
  const fija = quien(T, a) === quien(T, b)
    ? `En ${ambito}, **${quien(T, a)}** lidera los dos ejes: ${fmt(T.c[XP_LOCAL][a], 2)} puntos esperados por partido de local y ${fmt(T.c[XP_VISITA][a], 2)} de visitante.`
    : `En ${ambito}, **${quien(T, a)}** es el que más puntos esperados suma de local (${fmt(T.c[XP_LOCAL][a], 2)} por partido) y **${quien(T, b)}** el de visitante (${fmt(T.c[XP_VISITA][b], 2)}).`;
  if (filas.length < 4) return { fija, salta: null };
  // Las líneas son el promedio de cada sede en TODAS las temporadas (las mismas que dibuja `ScatterVista`).
  const ml = media(T.c[XP_LOCAL].filter((v) => v != null)), mv = media(T.c[XP_VISITA].filter((v) => v != null));
  let tr = 0, tl = 0, br = 0, bl = 0;
  filas.forEach((r) => {
    const l = T.c[XP_LOCAL][r] >= ml, v = T.c[XP_VISITA][r] >= mv;
    if (l && v) tr++; else if (v) tl++; else if (l) br++; else bl++;
  });
  const dif = pl.map((l, i) => l - pv[i]);
  const e = filas[idxmax(dif)];
  const salta = `De ${filas.length} equipos, ${tr} están arriba del promedio de local y de visita, ${br} solo de local, ${tl} solo de visita y ${bl} abajo en los dos lados. El que más cambia de un estadio a otro es **${quien(T, e)}**: ${fmt(T.c[XP_LOCAL][e], 2)} puntos esperados por partido de local y ${fmt(T.c[XP_VISITA][e], 2)} de visitante. Eso casi no se repite de una temporada a la siguiente.`;
  return { fija, salta };
}

export const GENERADORES = {
  goles_xg: golesXg, asist_xa: asistXa, perfil, recuperar, disputar, dos_fases: dosFases,
  pases_clave: pasesClave, construir, centros, definicion, creacion, defensa,
  xg_goles_90: xgGoles90, xa_asist_90: xaAsist90, pases_asist: pasesAsist, cover_stopper: coverStopper,
  cantidad_calidad: cantidadCalidad, local_visitante: localVisitante,
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

// ---- Explorador: cuánto se parecen las dos variables elegidas ------------------------------------
// Por dentro es el r² (la parte de la variación de una que explica la otra); a quien mira se le dice «parecido».

export function banda(r) {
  const a = Math.abs(r);
  if (a < 0.3) return "casi nada, miden cosas distintas";
  if (a < 0.6) return "hay tendencia, pero queda mucho que una no explica de la otra";
  if (a < 0.85) return "saber una dice buena parte de la otra";
  return "son casi la misma información, así que ponerlas en ejes distintos no agrega nada";
}

// `{ fija, salta }` del explorador sobre los pares (x, y) que se ven. Con menos de 3 puntos o sin variación en un eje no
// hay parecido que medir y el texto lo dice.
export function lecturaExplorador(xs, ys, etX, etY, entidad) {
  const n = xs.length;
  const b = (t) => `**${t}**`;
  if (n < 3) {
    return { fija: `No hay puntos suficientes para saber cuánto se parecen ${b(etX)} y ${b(etY)} con estos filtros.`, salta: null };
  }
  const r = corr(xs, ys);
  if (Number.isNaN(r)) {
    return { fija: `Con estos filtros, ${b(etX)} o ${b(etY)} vale lo mismo en los ${n} ${entidad} que quedan: sin variación en uno de los dos ejes no hay parecido que medir.`, salta: null };
  }
  const sentido = r >= 0 ? "suben juntas" : "cuando una sube, la otra baja";
  return {
    fija: `${b(etX)} y ${b(etY)} se parecen en un **${fmt(r * r * 100, 0)}%**: ${banda(r)}; ${sentido} (${n} ${entidad}).`,
    salta: null,
  };
}
