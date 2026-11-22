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
  const c = edadesCerca(m.e, m.med);
  return c.de === c.a
    ? `${etiqueta}: la mediana más alta es ${r0(c.max)}% de los minutos de su club, a los ${c.edad} años.`
    : `${etiqueta}: la mediana más alta es ${r0(c.max)}% de los minutos de su club, a los ${c.edad} años; de los ${c.de} a los ` +
      `${c.a} se queda a menos de ${TOL_MESETA} puntos.`;
}

// Devuelve los párrafos del texto, en orden.
export function lecturaEdad(D, pos, etiqueta) {
  return [lecturaMinutos(D, pos, etiqueta)];
}
