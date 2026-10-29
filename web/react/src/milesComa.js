// Miles con coma ("1,576"), como se escribe en México: el punto queda para los decimales. Es lo mismo
// que `miles` de stats.js; se queda para no tocar los imports de los artículos de ML.
export const miles = (n) => String(Math.trunc(n)).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
