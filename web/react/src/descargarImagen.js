// Descargar una gráfica como imagen (PNG), igual en todas las vistas: título, una línea de contexto (los filtros que están
// puestos), la gráfica, y un pie con el logo de FutViz a la izquierda y la fuente a la derecha. Muy poco texto a propósito:
// solo lo que hace falta para entender y ubicar la imagen. Lo usan las vistas con el ícono de `BotonDescarga.jsx`.
//
// Dos formas de dar la gráfica:
// * `capturar(contenedor)`: copia lo que HAY EN PANTALLA dentro de un contenedor (uno o varios <svg>, canvas y los textos
//   marcados con `data-img-texto`). Cada elemento lleva sus estilos ya calculados (colores, trazos, tipografía), porque un
//   SVG que se dibuja como imagen no ve la hoja de estilos del sitio: así sirve igual para gráficas de MUI X Charts que para
//   las de SVG propio, y respeta los colores y filtros del momento y el modo claro u oscuro.
// * `{ interior, viewBox }`: SVG ya armado como texto (el Venn y el mapa de tiros lo tienen a mano).
//
// El logo viaja en `react/datos-marca.js` (data URI, ver `react_views.registrar_marca`): pedirlo con fetch falla en una página
// abierta desde el disco. Sin él, la imagen lleva el texto «FutViz».
import { cargarDatos } from "./datos.js";

const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const ANCHO = 1200, MARGEN = 60, ANCHO_GRAFICA = ANCHO - 2 * MARGEN, ESCALA = 2;

// Lo que cambia cómo se ve un elemento de SVG: se copia de su estilo calculado.
const PROPIEDADES = ["fill", "fill-opacity", "stroke", "stroke-width", "stroke-opacity", "stroke-dasharray", "stroke-linecap",
  "stroke-linejoin", "opacity", "font-family", "font-size", "font-weight", "font-style", "text-anchor", "dominant-baseline",
  "paint-order", "letter-spacing", "visibility", "display", "shape-rendering"];

// Un <svg> de la pantalla como texto, con los estilos calculados puestos en cada elemento. `limpiar(original, copia)` puede
// cambiar la copia (la pantalla no se toca) o devolver "quitar" para que el elemento no salga en la imagen.
function interiorDe(svg, limpiar) {
  const clon = svg.cloneNode(true);
  const originales = [svg, ...svg.querySelectorAll("*")];
  const copias = [clon, ...clon.querySelectorAll("*")];
  const quitar = [];
  originales.forEach((el, i) => {
    const cs = getComputedStyle(el);
    const destino = copias[i];
    for (const p of PROPIEDADES) destino.style.setProperty(p, cs.getPropertyValue(p));
    destino.style.removeProperty("pointer-events");
    if (limpiar && limpiar(el, destino) === "quitar") quitar.push(destino);
    destino.removeAttribute("class");
  });
  quitar.forEach((e) => e.remove());
  return clon.innerHTML;
}

// Lo que hay en pantalla dentro de `contenedor`, en el mismo orden y lugar: sus <svg> de nivel superior (los iconos chicos no
// cuentan), sus <canvas> y sus textos `[data-img-texto]`. Devuelve `{ interior, viewBox }` listo para `descargarPng`.
export function capturar(contenedor, { limpiar } = {}) {
  const base = contenedor.getBoundingClientRect();
  const lugar = (el) => { const r = el.getBoundingClientRect(); return [r.left - base.left, r.top - base.top, r.width, r.height]; };
  const partes = [];
  contenedor.querySelectorAll("svg").forEach((svg) => {
    if (svg.parentElement.closest("svg")) return;
    const [x, y, w, h] = lugar(svg);
    if (w < 120 || h < 60) return;
    partes.push({ y, texto: `<g transform="translate(${x},${y})">${interiorDe(svg, limpiar)}</g>` });
  });
  contenedor.querySelectorAll("canvas").forEach((c) => {
    const [x, y, w, h] = lugar(c);
    partes.push({ y, texto: `<image href="${c.toDataURL("image/png")}" x="${x}" y="${y}" width="${w}" height="${h}"/>` });
  });
  contenedor.querySelectorAll("[data-img-texto]").forEach((el) => {
    const [x, y, , h] = lugar(el);
    const cs = getComputedStyle(el);
    partes.push({ y, texto: `<text x="${x}" y="${y + h * 0.75}" font-size="${cs.fontSize}" font-weight="${cs.fontWeight}" fill="${cs.color}">${esc(el.textContent.trim())}</text>` });
  });
  partes.sort((a, b) => a.y - b.y);
  return { interior: partes.map((p) => p.texto).join(""), viewBox: [0, 0, base.width, base.height] };
}

// La leyenda de colores: una fila de puntos con su nombre ([{ color, texto }]).
function leyendaSvg(items, x0, y, tk) {
  let x = x0;
  return items.map((it) => {
    const g = `<circle cx="${x + 5}" cy="${y - 5}" r="5" fill="${it.color}"/><text x="${x + 16}" y="${y}" font-size="14" fill="${tk.muted}">${esc(it.texto)}</text>`;
    x += 16 + it.texto.length * 7.4 + 20;
    return g;
  }).join("");
}

// La imagen no necesita todo lo que ayuda en pantalla, así que sale más limpia:
// * sin rejilla vertical, sin marcas ni línea de los ejes, rejilla horizontal apenas visible y la mitad de los números de cada eje;
// * sin la línea vertical del corte de élite y con solo dos rótulos de cuadrante (arriba a la izquierda y abajo a la derecha: los
//   que cuentan algo);
// * con `apagado`, el montón de puntos de fondo conserva el color de su liga pero muy apagado (casi transparente) y los rotulados
//   (Top 5, fijados) salen grandes y a todo color.
export const limpiarDispersion = (tk, { apagado = false, oscuro = false } = {}) => (el, copia) => {
  const c = el.getAttribute("class") || "";
  if (c.includes("MuiChartsGrid-verticalLine") || c.includes("MuiChartsAxis-line") || /(^|\s)MuiChartsAxis-tick(\s|$)/.test(c)) return "quitar";
  if (c.includes("MuiChartsGrid-horizontalLine")) { copia.style.setProperty("stroke-opacity", "0.35"); return undefined; }
  if (c.includes("MuiChartsAxis-tickLabel")) {
    const todas = [...el.closest(".MuiChartsAxis-root").querySelectorAll(".MuiChartsAxis-tickLabel")];
    return todas.length > 5 && todas.indexOf(el) % 2 === 1 ? "quitar" : undefined;
  }
  if (el.getAttribute("data-img") === "corte") return "quitar";
  const cuadrante = el.getAttribute("data-cuadrante");
  if (cuadrante && cuadrante !== "tl" && cuadrante !== "br") return "quitar";
  if (c.includes("rx-punto")) {
    const r = parseFloat(el.getAttribute("r"));
    const base = parseFloat(copia.style.getPropertyValue("fill-opacity"));
    if (r > 5 || base < 0.2) return undefined;                 // un fijado o resaltado, o uno apagado por los fijados: se queda como está
    const hayRotulados = !!el.closest("svg").querySelector("[data-rotulado]");
    if (el.hasAttribute("data-rotulado")) { copia.setAttribute("r", 6); copia.style.setProperty("fill-opacity", "1"); copia.style.setProperty("stroke-width", "1.6"); return undefined; }
    copia.setAttribute("r", 3.2);
    copia.style.setProperty("stroke-width", "0");
    copia.style.setProperty("fill-opacity", apagado && hayRotulados ? (oscuro ? "0.4" : "0.24") : hayRotulados ? "0.38" : "0.62");
  }
  return undefined;
};

// `viewBox` es [x, y, ancho, alto]; `interior` el contenido del <svg>. Todo lo demás es texto plano: `linea` (opcional, una
// sola, la cifra clave), `nota` (opcional, para leer el color o el símbolo de la gráfica) y `fuente`.
export async function descargarPng({ interior, viewBox, titulo, subtitulo, linea, nota, leyenda, fuente, tk, modo, archivo }) {
  let marca = null;
  try { marca = await cargarDatos("marca"); } catch { /* sin logo: se escribe el nombre */ }
  const logo = marca && marca[modo === "dark" ? "oscuro" : "claro"];
  const proporcion = (marca && marca.proporcion) || 4;

  const alto = ANCHO_GRAFICA * viewBox[3] / viewBox[2];
  const arriba = (linea ? 196 : 160);
  const finGrafica = arriba + alto;
  const yLeyenda = finGrafica + 30;
  const yNota = finGrafica + (leyenda ? 62 : 36);
  const pie = finGrafica + (leyenda ? 28 : 0) + (nota ? 52 : 24) + 40;
  const TH = Math.round(pie + 56 + 36);
  const LH = 56, LW = LH * proporcion;

  const doc = `<svg xmlns="http://www.w3.org/2000/svg" width="${ANCHO}" height="${TH}" viewBox="0 0 ${ANCHO} ${TH}" font-family="Inter, 'Segoe UI', Arial, sans-serif">`
    + `<rect width="${ANCHO}" height="${TH}" fill="${tk.surface}"/>`
    + `<text x="${MARGEN}" y="92" font-size="50" font-weight="800" fill="${tk.primary}">${esc(titulo)}</text>`
    + (subtitulo ? `<text x="${MARGEN}" y="134" font-size="23" fill="${tk.muted}">${esc(subtitulo)}</text>` : "")
    + (linea ? `<text x="${MARGEN}" y="176" font-size="23" font-weight="600" fill="${tk["text-body"]}">${esc(linea)}</text>` : "")
    + `<svg x="${MARGEN}" y="${arriba}" width="${ANCHO_GRAFICA}" height="${alto}" viewBox="${viewBox.join(" ")}">${interior}</svg>`
    + (leyenda ? leyendaSvg(leyenda, MARGEN, yLeyenda, tk) : "")
    + (nota ? `<text x="${MARGEN}" y="${yNota}" font-size="18" fill="${tk.muted}">${esc(nota)}</text>` : "")
    + (logo ? `<image href="${logo}" x="${MARGEN}" y="${TH - 28 - LH}" width="${LW}" height="${LH}"/>`
      : `<text x="${MARGEN}" y="${TH - 40}" font-size="30" font-weight="800" fill="${tk.primary}">FutViz</text>`)
    + `<text x="${ANCHO - MARGEN}" y="${TH - 36}" text-anchor="end" font-size="10.5" fill="${tk.muted}">${esc(fuente)}</text></svg>`;

  const url = URL.createObjectURL(new Blob([doc], { type: "image/svg+xml;charset=utf-8" }));
  await new Promise((ok, fallo) => {
    const img = new Image();
    img.onload = () => {
      const c = document.createElement("canvas");
      c.width = ANCHO * ESCALA; c.height = TH * ESCALA;
      c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
      URL.revokeObjectURL(url);
      c.toBlob((b) => {
        const a = document.createElement("a");
        a.href = URL.createObjectURL(b);
        a.download = archivo;
        a.click();
        setTimeout(() => URL.revokeObjectURL(a.href), 1000);
        ok();
      }, "image/png");
    };
    img.onerror = () => { URL.revokeObjectURL(url); fallo(new Error("no se pudo dibujar la imagen")); };
    img.src = url;
  });
}

// Un nombre de archivo sin acentos ni signos: «futviz-xg-vs-goles-2026-27.png».
export const nombreArchivo = (...partes) =>
  "futviz-" + partes.filter(Boolean).join("-").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") + ".png";
