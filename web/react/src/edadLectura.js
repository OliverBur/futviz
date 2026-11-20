// El texto "Con estos filtros" de la vista Edad. Se arma en el navegador sobre la tabla que mandó el build
// (`web/charts/edad.py`): cada cifra sale de ella. No toca el DOM, así que se puede probar con node.

const TOL_MESETA = 3;     // puntos de % de minutos: "cerca del máximo"
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

// Devuelve los párrafos del texto, en orden.
export function lecturaEdad(D, pos, etiqueta) {
  return [lecturaMinutos(D, pos, etiqueta)];
}
