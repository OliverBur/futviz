// Miles con coma ("1,576"), como se escribe en México: el punto queda para los decimales. Solo lo usan
// los artículos de ML; el resto del sitio sigue con `miles` de stats.js.
export const miles = (n) => String(Math.trunc(n)).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
