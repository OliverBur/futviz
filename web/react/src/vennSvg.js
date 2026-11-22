// El dibujo del Venn como texto SVG. Es una cadena y no JSX porque la misma función sirve a dos cosas: la pantalla
// (`VennVista.jsx` la inserta con innerHTML y atiende el cursor por delegación) y la imagen que se descarga, que tiene
// que ser un SVG autocontenido. Todo el estilo va en atributos (nada depende de la hoja de estilos del sitio).
import { CEN, R, centroide, apellido, corto, iniciales } from "./vennCalculo.js";
import { conAlfa } from "./colores.js";

export const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

// Tinta del texto sobre la ficha de cada liga (Bundesliga, Serie A, Ligue 1, La Liga, Premier League): blanca sobre las
// tres oscuras, oscura sobre el ámbar y el rosa.
const TINTA = ["#ffffff", "#ffffff", "#ffffff", "#241a00", "#3a0f22"];

// Dos jugadores con el mismo apellido en la misma vista se distinguen con la inicial del nombre.
function etiquetas(fichas, equipo) {
  if (equipo) return fichas.map((f) => (f.it ? f.it.r[0] : ""));   // un equipo va con su nombre entero
  const cuenta = {};
  for (const f of fichas) if (f.it) { const a = apellido(f.it.r[0]); cuenta[a] = (cuenta[a] || 0) + 1; }
  return fichas.map((f) => {
    if (!f.it) return "";
    const a = apellido(f.it.r[0]);
    const inicial = f.it.r[0].trim()[0];
    return cuenta[a] > 1 ? `${inicial}. ${a}` : a;
  });
}

// `ctx`: { fichas, pills, reg, tk, ligas (colores por liga), circ (colores de círculo), fuente, hover, buscado, compacto }
export function construirSvg(ctx) {
  const { fichas, pills, reg, tk, ligas, circ, hover, buscado, equipo } = ctx;
  const nombres = etiquetas(fichas, equipo);
  const tinta = tk["text-body"];
  const aro = tk.surface;

  const circulos = CEN.map(([x, y], j) =>
    `<circle cx="${x}" cy="${y}" r="${R}" fill="${conAlfa(circ[j], 0.1)}" stroke="${circ[j]}" stroke-width="2.5"/>`).join("");

  // una región que quedó vacía lo dice, en vez de dejar un hueco que parece un error
  const vacias = [3, 5, 6, 7].filter((m) => !reg[m].length).map((m) => {
    const c = centroide(m);
    if (!c) return "";
    return m === 7
      ? `<text x="${c[0]}" y="${c[1]}" text-anchor="middle" font-size="20" font-weight="700" fill="${tk.muted}">Nadie</text>`
        + `<text x="${c[0]}" y="${c[1] + 20}" text-anchor="middle" font-size="12.5" fill="${tk.muted}">cumple los tres</text>`
      : `<text x="${c[0]}" y="${c[1]}" text-anchor="middle" font-size="13" fill="${tk.muted}">Nadie</text>`;
  }).join("");

  const chips = fichas.map((f, i) => {
    const { lv } = f;
    const sel = hover === i;
    if (f.mas) {
      return `<g data-i="${i}" transform="translate(${f.x},${f.y})">`
        + `<circle r="${lv.r}" fill="${conAlfa(tk.muted, 0.18)}" stroke="${tk.muted}" stroke-width="${sel ? 2.5 : 1.5}" stroke-dasharray="3 2"/>`
        + `<text y="${lv.r * 0.22}" text-anchor="middle" font-size="${lv.r * 0.62}" font-weight="700" fill="${tinta}" pointer-events="none">+${f.mas}</text>`
        + (lv.f ? `<text y="${lv.r + lv.f + 1}" text-anchor="middle" font-size="${lv.f}" font-weight="600" fill="${tinta}" pointer-events="none">más</text>` : "")
        + `</g>`;
    }
    const r = f.it.r;
    const hl = buscado && r[0] === buscado;
    const trazo = hl || sel ? tk.primary : aro;
    const ancho = hl ? 4 : sel ? 3 : 2;
    const ini = lv.f ? `<text y="${lv.r * 0.22}" text-anchor="middle" font-size="${lv.r * 0.62}" font-weight="700" fill="${TINTA[r[2]]}" pointer-events="none">${esc(iniciales(r[0], equipo))}</text>` : "";
    const nom = lv.f
      ? `<text y="${lv.r + lv.f + 1}" text-anchor="middle" font-size="${lv.f}" font-weight="600" fill="${tinta}" stroke="${aro}" stroke-width="3" stroke-linejoin="round" paint-order="stroke" pointer-events="none">${esc(corto(nombres[i], lv.max))}</text>`
      : "";
    return `<g data-i="${i}" transform="translate(${f.x},${f.y})"><circle r="${lv.r}" fill="${ligas[r[2]]}" stroke="${trazo}" stroke-width="${ancho}"/>${ini}${nom}</g>`;
  }).join("");

  // Cada círculo lleva solo su nombre: el corte ya está en el control y la medida, en «Qué mide cada círculo».
  const pastillas = pills.map((p) => {
    const k = p.k;
    return `<g><rect x="${p.x - p.w / 2}" y="${p.y - 19 * k}" width="${p.w}" height="${38 * k}" rx="${14 * k}" fill="${aro}" stroke="${circ[p.j]}" stroke-width="${2.5 * (k > 1 ? 1.4 : 1)}"/>`
      + `<text x="${p.x}" y="${p.y + 5.5 * k}" text-anchor="middle" font-size="${16 * k}" font-weight="700" fill="${tk.primary}">${esc(p.nombre)}</text></g>`;
  }).join("");

  return circulos + vacias + chips + pastillas;
}

export const VIEWBOX = "0 22 900 888";
export const VIEWBOX_COMPACTO = "0 0 900 940";   // las pastillas del celular son más grandes y piden aire
