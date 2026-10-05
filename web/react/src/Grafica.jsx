// El scatter. Composición, de atrás hacia adelante:
//   1. fondo (<svg> aparte): con referencia "diagonal", el sombreado azul/rojo a cada lado de
//      y = x. Va DETRÁS de los puntos —el ScatterChart de MUI no tiene una ranura de "fondo"—
//      y por eso es un <svg> hermano, con el mismo área de dibujo que el del chart.
//   2. ScatterChart (puntos, ejes, grilla, tooltip, highlight de MUI).
//   3. dentro del <svg> del chart, encima: la referencia (la diagonal, o las líneas punteadas
//      en el promedio de cada eje con un rótulo por cuadrante), las etiquetas directas y la capa
//      invisible del zoom.
import { createContext, useContext, useEffect, useId, useMemo, useRef, useState } from "react";
import Box from "@mui/material/Box";
import Paper from "@mui/material/Paper";
import Typography from "@mui/material/Typography";
import GlobalStyles from "@mui/material/GlobalStyles";
import { ScatterChart } from "@mui/x-charts/ScatterChart";
import { ChartsTooltipContainer, useItemTooltip } from "@mui/x-charts/ChartsTooltip";
import { ZoomLayer } from "./ZoomLayer.jsx";
import { conAlfa } from "./colores.js";

// El tooltip y los rótulos necesitan datos de la fila que el chart no conoce: llegan por contexto.
export const FilaCtx = createContext(null);

const signo = (d, dec = 1) => (d >= 0 ? "+" : "−") + Math.abs(d).toFixed(dec);

// --- marcador -----------------------------------------------------------------
// Anillo de superficie de 0.6px (separa los que se pisan) y, al resaltarse, más grande
// y con borde de tinta. Los estilos van en `style` y no como atributos: `var(...)`
// no vale en un atributo de presentación SVG.
//
// **Animación de entrada.** La nube se "despliega" desde el origen (xG = 0, goles = 0) hasta
// su lugar y aparece, ~0.5 s, con un pequeño desfase por liga. Se anima la CAPA de cada serie
// (5 elementos) y no cada punto: animar los ~1.900 <circle> uno por uno (con `transform`,
// con solo `opacity`, con o sin `transform-box`) multiplicaba por 4-5 los fotogramas lentos
// al cambiar de temporada; una capa entera se repinta de una vez. Solo corre en la ventana
// que abre el montaje de los datos (`.rx-anim`, ver `Grafica`): al hacer zoom o pan, animar
// los puntos que entran al área visible sería ruido.
const ANIM_MS = 520;

// Los jugadores FIJADOS (varios a la vez) llegan por contexto y no por el highlight de MUI, que
// solo resalta un punto: con varios fijados, MUI se queda con el resaltado del mouse (un punto) y
// aquí se pinta lo demás — los fijados grandes y con borde, el resto atenuado. `ids` traduce
// (serie, índice) a la fila de datos.
export const PinCtx = createContext({ pines: new Set(), ids: {} });

function PuntoMarker({ x, y, color, size, isHighlighted, isFaded,
  seriesId, dataIndex, ...resto }) {
  const { pines, ids } = useContext(PinCtx);
  const fijado = pines.size > 0 && pines.has(ids[seriesId]?.[dataIndex]);
  const apagado = pines.size > 0 && !fijado;
  const grande = isHighlighted || fijado;
  return (
    <circle
      {...resto}
      className={`${resto.className || ""} rx-punto`}
      transform={`translate(${x},${y})`}
      r={grande ? size * 1.9 : size}
      fill={color}
      fillOpacity={apagado && !isHighlighted ? 0.14 : fijado ? 1 : 0.85}
      style={{
        stroke: grande ? "var(--color-primary)" : "var(--color-surface)",
        strokeWidth: grande ? 2 : 0.6,
        strokeOpacity: apagado && !isHighlighted ? 0.14 : 1,
        cursor: resto.onClick ? "pointer" : "inherit",
      }}
    />
  );
}

// --- tooltip ------------------------------------------------------------------
// `filas.info(r)` devuelve `{ nombre, sub, colorLiga, filas: [[etiqueta, valor], ...] }`: lo que
// muestra depende de la vista (los ejes que tenga), no del gráfico.
function CuerpoTooltip() {
  const item = useItemTooltip();
  const filas = useContext(FilaCtx);
  const f = item && filas ? filas.info(item.value.id) : null;
  if (!f) return null;
  return (
    <Paper className="rx-tooltip" elevation={4} sx={{ p: 1.25, minWidth: 190, border: 1, borderColor: "divider" }}>
      <Typography sx={{ fontWeight: 700, fontSize: 13.5, lineHeight: 1.25 }}>{f.nombre}</Typography>
      <Box sx={{ display: "flex", alignItems: "center", gap: 0.75, mb: 0.75, color: "text.secondary", fontSize: 12 }}>
        <Box component="span" sx={{ width: 12, height: 3, borderRadius: 1, bgcolor: f.colorLiga, flex: "none" }} />
        {f.sub}
      </Box>
      {f.filas.map(([k, v]) => (
        <Box key={k} sx={{ display: "flex", justifyContent: "space-between", gap: 2, fontSize: 12.5 }}>
          <Box component="span" sx={{ color: "text.secondary" }}>{k}</Box>
          <Box component="span" sx={{ fontWeight: 700 }}>{v}</Box>
        </Box>
      ))}
    </Paper>
  );
}
function PuntoTooltip(props) {
  return (
    <ChartsTooltipContainer {...props} trigger="item">
      <CuerpoTooltip />
    </ChartsTooltipContainer>
  );
}

// --- capas dentro del <svg> -----------------------------------------------------
function CapaSuperior({ area, referencia, etiquetas, rotulosCuadrante, tk }) {
  const id = "rx-clip-" + useId().replace(/:/g, "");
  if (!area.width) return null;
  return (
    <g pointerEvents="none">
      <clipPath id={id}><rect x={area.left} y={area.top} width={area.width} height={area.height} /></clipPath>
      {referencia.diagonal && (
        <line {...referencia.diagonal} clipPath={`url(#${id})`} stroke={tk.muted} strokeOpacity={0.7}
          strokeWidth={1.4} strokeDasharray="5 4" />
      )}
      {referencia.promedios && (
        <g clipPath={`url(#${id})`} stroke={tk.muted} strokeOpacity={0.75} strokeWidth={1} strokeDasharray="4 4">
          <line x1={referencia.promedios.vx} x2={referencia.promedios.vx} y1={area.top} y2={area.top + area.height} />
          <line y1={referencia.promedios.hy} y2={referencia.promedios.hy} x1={area.left} x2={area.left + area.width} />
        </g>
      )}
      {rotulosCuadrante.map((q) => (
        <text key={q.clave} x={q.x} y={q.y} textAnchor={q.ancla} fontSize={10.5} fill={tk.muted}
          stroke={tk.surface} strokeWidth={3} paintOrder="stroke" strokeLinejoin="round">{q.texto}</text>
      ))}
      {etiquetas.map((e) => (
        // `rx-etiquetas`: mientras corre la entrada, las etiquetas esperan a que lleguen sus puntos.
        <g key={e.r} className="rx-etiquetas">
          {e.fijado && <circle cx={e.px} cy={e.py} r={9} fill="none" stroke={tk.primary} strokeWidth={2} />}
          <text x={e.tx} y={e.ty} dy="0.32em" textAnchor={e.ancla}
            fontSize={11.5} fontWeight={e.fijado ? 700 : 500} fill={tk["text-body"]}
            stroke={tk.surface} strokeWidth={3.5} paintOrder="stroke" strokeLinejoin="round">
            {/* El número es el de la lista Top 5: así se liga cada nombre del gráfico con su fila. */}
            {e.rango && <tspan fontWeight={700} fill={tk.muted}>{e.rango}  </tspan>}
            {e.texto}
          </text>
        </g>
      ))}
    </g>
  );
}

// Coloca las etiquetas que le pasan: son las de la lista Top 5 (con su número) o, si hay un
// jugador fijado, solo la suya. QUÉ rotular ya no se decide aquí: así lo rotulado y la lista
// no pueden contradecirse (antes la gráfica rotulaba a los que más se alejaban de la diagonal
// y la lista ordenaba por xG o por goles: coincidían 0 de 7 en varias temporadas).
//
// Aquí solo se decide DÓNDE: derecha, izquierda, arriba o abajo del punto, la primera que no
// pise a otra etiqueta ni a los rótulos de esquina ni se salga del recuadro. Si ninguna
// cabe se dibuja igual a la derecha: una etiqueta de la lista que no aparezca sería
// peor que una que se roza con otra.
function colocarEtiquetas({ rotulos, area, view, obstaculos }) {
  if (!area.width || !rotulos.length) return [];
  const px = (x) => area.left + ((x - view.x0) / (view.x1 - view.x0)) * area.width;
  const py = (y) => area.top + (1 - (y - view.y0) / (view.y1 - view.y0)) * area.height;
  const dentro = (f) => f.x >= view.x0 && f.x <= view.x1 && f.y >= view.y0 && f.y <= view.y1;
  // Los rótulos de la gráfica (esquinas de sobre/bajo rendimiento, cuadrantes) también ocupan
  // lugar: las etiquetas de los jugadores los esquivan.
  const cajas = [...obstaculos];
  const salida = [];
  const choca = (a) => cajas.some((b) => a.x0 < b.x1 && a.x1 > b.x0 && a.y0 < b.y1 && a.y1 > b.y0);

  const solape = (a, b) => Math.max(0, Math.min(a.x1, b.x1) - Math.max(a.x0, b.x0)) *
    Math.max(0, Math.min(a.y1, b.y1) - Math.max(a.y0, b.y0));
  const cabe = (c) => c.x0 >= area.left && c.x1 <= area.left + area.width &&
    c.y0 >= area.top && c.y1 <= area.top + area.height;

  for (const f of rotulos) {
    if (!dentro(f)) continue;
    const cx = px(f.x), cy = py(f.y);
    const w = (f.texto.length + (f.rango ? 3 : 0)) * 6.3 + 8, h = 16;
    // Ocho posiciones alrededor del punto, de la más legible (a la derecha) a las diagonales.
    const caja = (x0, y0) => ({ x0, x1: x0 + w, y0, y1: y0 + h });
    const opciones = [
      caja(cx + 9, cy - h / 2),            // derecha
      caja(cx - 9 - w, cy - h / 2),        // izquierda
      caja(cx - w / 2, cy - 11 - h),       // arriba
      caja(cx - w / 2, cy + 11),           // abajo
      caja(cx + 7, cy - 8 - h),            // arriba a la derecha
      caja(cx + 7, cy + 8),                // abajo a la derecha
      caja(cx - 7 - w, cy - 8 - h),        // arriba a la izquierda
      caja(cx - 7 - w, cy + 8),            // abajo a la izquierda
    ];
    // La primera que cabe y no pisa a nadie; si no hay, la que menos pisa (una etiqueta de la
    // lista que no aparezca sería peor que una que se roza con otra).
    let elegida = opciones.find((c) => cabe(c) && !choca(c));
    let ancla = null;
    if (!elegida) {
      // Ninguna cabe sin pisar a nadie. En un gráfico angosto (móvil) un nombre largo no cabe ni a un
      // lado ni al otro del punto: cada opción se corre hacia dentro del recuadro, centrada, y se
      // elige la que menos pisa a otras etiquetas y al punto mismo.
      const pto = { x0: cx - 8, x1: cx + 8, y0: cy - 8, y1: cy + 8 };
      const dentroDelArea = (c) => {
        const x0 = Math.min(Math.max(c.x0, area.left), Math.max(area.left, area.left + area.width - w));
        const y0 = Math.min(Math.max(c.y0, area.top), area.top + area.height - h);
        return { x0, x1: x0 + w, y0, y1: y0 + h };
      };
      const costo = (c) => cajas.reduce((s, b) => s + solape(c, b), 0) + 3 * solape(c, pto);
      // Además de las 8 posiciones, versiones desplazadas hacia arriba y hacia abajo (como en un
      // gráfico angosto no hay a dónde correrse de lado, se apila).
      const apiladas = opciones.flatMap((c) => [0, 17, -17, 34, -34].map((dy) => ({ ...c, y0: c.y0 + dy, y1: c.y1 + dy })));
      elegida = apiladas.map(dentroDelArea).reduce((mejor, c) => (costo(c) < costo(mejor) ? c : mejor));
      ancla = "middle";
    }
    cajas.push(elegida);
    // Ancla del texto según de qué lado del punto cae la caja (centrada si se tuvo que correr).
    ancla = ancla || (elegida.x0 >= cx ? "start" : elegida.x1 <= cx ? "end" : "middle");
    const tx = ancla === "start" ? elegida.x0 + 2 : ancla === "end" ? elegida.x1 - 2 : (elegida.x0 + elegida.x1) / 2;
    salida.push({ r: f.r, texto: f.texto, rango: f.rango, fijado: f.fijado, px: cx, py: cy,
      tx, ty: (elegida.y0 + elegida.y1) / 2, ancla });
  }
  return salida;
}

// Estilos globales de las gráficas (cursor de arrastre, transición del punto resaltado y animación de
// entrada). Los comparten `Grafica` y las cajas.
export function EstilosGrafica() {
  return (
    <GlobalStyles styles={{
      "html.rx-arrastrando .rx-tooltip": { display: "none" },
      "html.rx-arrastrando .rx-chart svg": { cursor: "grabbing" },
      '.rx-chart[data-zoom="1"] svg': { cursor: "grab" },
      // Solo el tamaño transiciona (crece al resaltarse). NO el color ni el atenuado: una transición
      // por punto con 1.900 puntos multiplicaba los fotogramas lentos al cambiar "Color por" (p95 de
      // 17 a 50 ms) y al pasar el mouse por un chip. Solo cambia de tamaño un punto a la vez.
      ".rx-punto": { transition: "r .12s ease" },
      // Entrada: cada capa de serie (una por liga) se despliega desde la esquina del origen.
      "@keyframes rx-despliega": { from: { opacity: 0, transform: "scale(0.3)" }, to: { opacity: 1, transform: "scale(1)" } },
      ".rx-anim [data-series]": {
        transformOrigin: "var(--rx-ox, 0px) var(--rx-oy, 0px)",
        animation: `rx-despliega ${ANIM_MS}ms cubic-bezier(.2,.8,.25,1) both`,
      },
      ".rx-anim [data-series]:nth-of-type(2)": { animationDelay: "50ms" },
      ".rx-anim [data-series]:nth-of-type(3)": { animationDelay: "100ms" },
      ".rx-anim [data-series]:nth-of-type(4)": { animationDelay: "150ms" },
      ".rx-anim [data-series]:nth-of-type(5)": { animationDelay: "200ms" },
      // Las etiquetas aparecen cuando la nube ya casi llegó (retraso ≈ duración + último desfase).
      "@keyframes rx-aparece": { from: { opacity: 0 }, to: { opacity: 1 } },
      ".rx-anim .rx-etiquetas": { animation: "rx-aparece 260ms ease-out 450ms both" },
      "@media (prefers-reduced-motion: reduce)": {
        ".rx-punto": { transition: "none" },
        ".rx-anim [data-series]": { animation: "none" },
        ".rx-anim .rx-etiquetas": { animation: "none" },
      },
    }} />
  );
}

// --- el componente ---------------------------------------------------------------
//
// `referencia` (de la configuración de la vista): `{ tipo: "diagonal", sobre, bajo }` dibuja y = x con
// su sombreado, o `{ tipo: "promedios", cuadrantes? }` dibuja líneas punteadas en `medias` ({x, y},
// el promedio de las temporadas juntas) y, si hay `cuadrantes`, un rótulo por cuadrante. Sin
// referencia (el explorador) no se dibuja nada.
export function Grafica({
  series, view, viewRef, base, onView, rotulos, destacado, onDestacar, onClicPunto,
  tk, pos, neg, hayZoom, pista, onPista, ejeX, ejeY, claveDatos, pines, idsPorSerie,
  referencia, medias, vacio, soloPositivoX, soloPositivoY,
}) {
  const pinCtx = useMemo(() => ({ pines, ids: idsPorSerie }), [pines, idsPorSerie]);
  const idFondo = "rx-clip-fondo-" + useId().replace(/:/g, "");   // único por instancia: hay varias vistas montadas a la vez
  const caja = useRef(null);
  const [ancho, setAncho] = useState(0);
  const [area, setArea] = useState({ left: 0, top: 0, width: 0, height: 0 });

  useEffect(() => {
    if (!caja.current) return undefined;
    const ro = new ResizeObserver(([e]) => setAncho(Math.round(e.contentRect.width)));
    ro.observe(caja.current);
    return () => ro.disconnect();
  }, []);
  const alto = Math.max(360, Math.min(640, Math.round(ancho * 0.74)));

  const px = (x) => area.left + ((x - view.x0) / (view.x1 - view.x0)) * area.width;
  const py = (y) => area.top + (1 - (y - view.y0) / (view.y1 - view.y0)) * area.height;
  const diag = referencia && referencia.tipo === "diagonal";
  const prom = referencia && referencia.tipo === "promedios" && medias;

  // --- la referencia, en píxeles (y las cajas que ocupan sus rótulos, para que las etiquetas las esquiven)
  const ref = { diagonal: null, promedios: null };
  const rotulosCuadrante = [];
  const obstaculos = [];
  if (area.width > 0) {
    if (diag) {
      const T = Math.max(base.x1, base.y1) * 3;           // más allá de cualquier zoom
      ref.diagonal = { x1: px(-T), y1: py(-T), x2: px(T), y2: py(T) };
      // Los rótulos de esquina solo valen mientras esa esquina siga a su lado de la diagonal: con
      // zoom profundo la de arriba a la izquierda puede quedar en zona roja.
      if (view.y1 > view.x0) obstaculos.push({ x0: area.left, x1: area.left + 140, y0: area.top, y1: area.top + 22 });
      if (view.y0 < view.x1) obstaculos.push({ x0: area.left + area.width - 128, x1: area.left + area.width,
        y0: area.top + area.height - 22, y1: area.top + area.height });
    }
    if (prom) {
      const vx = px(medias.x), hy = py(medias.y);
      ref.promedios = { vx, hy };
      const q = referencia.cuadrantes;
      if (q) {
        // Un rótulo por cuadrante, pegado a las líneas de promedio por arriba y por abajo del recuadro.
        // Solo los cuadrantes que se ven: si el promedio quedó fuera del zoom, el rótulo no aplica.
        const arriba = area.top + 13, abajo = area.top + area.height - 7;
        const hayArriba = hy > area.top + 18, hayAbajo = hy < area.top + area.height - 12;
        const hayDer = vx < area.left + area.width - 40, hayIzq = vx > area.left + 40;
        const poner = (clave, ok, x, y, ancla) => {
          if (!ok || !q[clave]) return;
          const w = q[clave].length * 5.7 + 6;
          // Pegado a la línea de promedio, pero sin salirse del recuadro (en pantalla angosta un rótulo largo
          // no cabe entre la línea y el borde): si no cabe, se corre hacia dentro.
          if (ancla === "start" && x + w > area.left + area.width - 2) { x = area.left + area.width - 2 - w; }
          if (ancla === "end" && x - w < area.left + 2) { x = area.left + 2 + w; }
          const x0 = ancla === "start" ? x : x - w;
          rotulosCuadrante.push({ clave, x, y, ancla, texto: q[clave] });
          obstaculos.push({ x0, x1: x0 + w, y0: y - 12, y1: y + 3 });
        };
        poner("tr", hayArriba && hayDer, vx + 6, arriba, "start");
        poner("tl", hayArriba && hayIzq, vx - 6, arriba, "end");
        poner("br", hayAbajo && hayDer, vx + 6, abajo, "start");
        poner("bl", hayAbajo && hayIzq, vx - 6, abajo, "end");
      }
    }
  }
  const etiquetas = useMemo(() => colocarEtiquetas({ rotulos, area, view, obstaculos }),
    // `obstaculos` se reconstruye en cada render; depende solo de estas cosas.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [rotulos, area, view, referencia, medias]);

  // La animación de entrada corre mientras `fin` (la última clave de datos cuya animación ya
  // terminó) sea distinta de la clave actual. Se deriva así, y no con un estado que un efecto
  // enciende, porque el efecto llegaría DESPUÉS del primer render de los puntos nuevos y estos
  // nacerían sin la clase.
  const [fin, setFin] = useState(null);
  const animando = fin !== claveDatos;
  useEffect(() => {
    const t = setTimeout(() => setFin(claveDatos), ANIM_MS + 400);
    return () => clearTimeout(t);
  }, [claveDatos]);

  // Los ejes llevan un margen por debajo del mínimo de los datos; si los datos no bajan de cero (un xG,
  // unos goles) una marca negativa no existe y no se rotula. Si la variable SÍ puede ser negativa (una
  // diferencia de goles) se rotula todo.
  const rotulo = (soloPositivo) => (v) => (soloPositivo && v < -1e-9 ? "" : String(Number(v.toFixed(2))));
  // Cuántos caracteres tendrán las marcas del eje vertical: los dígitos enteros del mayor valor y, si
  // la separación entre marcas es menor que 1, los decimales que hacen falta (0.35 → 4; 35 → 2).
  // El eje se ensancha con eso: con un ancho fijo, "0.45" se cortaba como "0.…".
  const marcasY = Math.max(4, Math.round(area.height / 55));
  const pasoY = 10 ** Math.floor(Math.log10((view.y1 - view.y0) / marcasY || 1));
  const decimalesY = pasoY >= 1 ? 0 : Math.min(2, Math.ceil(-Math.log10(pasoY)) + (((view.y1 - view.y0) / marcasY / pasoY) < 3 ? 1 : 0));
  const digitosY = Math.max(1, Math.floor(Math.log10(Math.max(Math.abs(view.y0), Math.abs(view.y1), 1))) + 1);
  const largoY = digitosY + (decimalesY ? decimalesY + 1 : 0);
  const anchoEjeY = 28 + 8 * Math.max(2, largoY) + 8;
  // Una marca cada ~75 px en X y ~55 en Y; MUI por defecto pone casi el doble y al acercar se llena de números.
  const ejes = useMemo(() => ({
    x: [{ id: "x", scaleType: "linear", min: view.x0, max: view.x1, label: ejeX, height: 46, valueFormatter: rotulo(soloPositivoX),
      tickNumber: Math.max(4, Math.round(area.width / 75)) }],
    y: [{ id: "y", scaleType: "linear", min: view.y0, max: view.y1, label: ejeY, width: anchoEjeY, valueFormatter: rotulo(soloPositivoY),
      tickNumber: marcasY }],
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }), [view, ejeX, ejeY, soloPositivoX, soloPositivoY, area.width, anchoEjeY, marcasY]);

  const clipFondo = idFondo;
  const T = Math.max(base.x1, base.y1) * 3;
  const lienzo = `M ${px(-T)},${py(-T)} L ${px(T)},${py(T)}`;
  return (
    <Box ref={caja} className={`rx-chart${animando ? " rx-anim" : ""}`} data-zoom={hayZoom ? 1 : 0}
      // La esquina de abajo a la izquierda del área de dibujo: de ahí se despliega la nube.
      style={{ "--rx-ox": `${area.left}px`, "--rx-oy": `${area.top + area.height}px` }}
      sx={{
        position: "relative", width: "100%", userSelect: "none",
        "& svg": { touchAction: hayZoom ? "none" : "pan-y" },
        "& .rx-chart-svg svg": { position: "relative", zIndex: 1 },
        // Ejes y grilla con los tokens del sitio, no los de MUI.
        "& .MuiChartsAxis-tickLabel": { fill: tk.muted, fontSize: 11.5 },
        "& .MuiChartsAxis-label": { fill: tk["text-body"], fontSize: 12.5, fontWeight: 600 },
        "& .MuiChartsAxis-line, & .MuiChartsAxis-tick": { stroke: tk.border },
        "& .MuiChartsGrid-line": { stroke: tk.border, strokeOpacity: 0.7, strokeDasharray: "0" },
      }}>
      <EstilosGrafica />
      {/* 1. Fondo: sombreado a cada lado de la diagonal (solo con referencia "diagonal") */}
      {diag && area.width > 0 && (
        <svg width="100%" height={alto} aria-hidden="true"
          style={{ position: "absolute", left: 0, top: 0, pointerEvents: "none" }}>
          <clipPath id={clipFondo}>
            <rect x={area.left} y={area.top} width={area.width} height={area.height} />
          </clipPath>
          <g clipPath={`url(#${clipFondo})`}>
            <path d={`${lienzo} L ${px(-T)},${py(T)} Z`} fill={conAlfa(pos, 0.08)} />
            <path d={`${lienzo} L ${px(T)},${py(-T)} Z`} fill={conAlfa(neg, 0.08)} />
          </g>
          {/* Los rótulos van en las esquinas, pero solo valen mientras esa esquina siga a su lado de la
              diagonal: con zoom profundo la de arriba a la izquierda puede quedar en zona roja. */}
          {view.y1 > view.x0 && (
            <text x={area.left + 8} y={area.top + 16} fontSize={11.5} fontWeight={600} fill={pos}>↑ {referencia.sobre}</text>
          )}
          {view.y0 < view.x1 && (
            <text x={area.left + area.width - 8} y={area.top + area.height - 8} fontSize={11.5} fontWeight={600}
              fill={neg} textAnchor="end">↓ {referencia.bajo}</text>
          )}
        </svg>
      )}

      {/* 2. El chart. Hasta que se mide el contenedor no hay con qué dibujar. */}
      {ancho > 0 && (
        // `key`: cuando cambia QUÉ puntos hay (filtros), el chart se vuelve a montar. MUI guarda
        // el highlight y el foco como (serie, índice) y procesa las series en un efecto: en el
        // render en que los datos cambian, un índice de la serie vieja se lee contra la nueva y
        // `descriptionGetter` revienta ("reading 'toFixed'"). Con la clave nueva su estado nace limpio.
        // El zoom y el pan NO la cambian: solo mueven los ejes.
        <PinCtx.Provider value={pinCtx}>
          <ScatterChart
            key={claveDatos}
            className="rx-chart-svg"
            height={alto}
            series={series}
            xAxis={ejes.x}
            yAxis={ejes.y}
            margin={{ top: 10, right: 14, bottom: 6, left: 6 }}
            grid={{ vertical: true, horizontal: true }}
            hideLegend
            skipAnimation
            hitAreaRadius={18}
            highlightedItem={destacado}
            onHighlightChange={onDestacar}
            onItemClick={onClicPunto}
            slots={{ marker: PuntoMarker, tooltip: PuntoTooltip }}
          >
            <CapaSuperior area={area} referencia={ref} etiquetas={etiquetas} rotulosCuadrante={rotulosCuadrante} tk={tk} />
            <ZoomLayer viewRef={viewRef} base={base} onView={onView} onArea={setArea} onPista={onPista} />
          </ScatterChart>
        </PinCtx.Provider>
      )}

      {vacio && ancho > 0 && (
        <Box role="status" sx={{ position: "absolute", left: 0, right: 0, top: "42%", textAlign: "center", zIndex: 2,
          color: "text.secondary", fontSize: 13.5, pointerEvents: "none" }}>
          {vacio}
        </Box>
      )}

      {pista && (
        <Box role="status" sx={{
          position: "absolute", left: "50%", bottom: 64, transform: "translateX(-50%)", zIndex: 2,
          px: 1.5, py: 0.75, borderRadius: 2, bgcolor: tk.primary, color: tk.bg, fontSize: 12.5,
          fontWeight: 600, pointerEvents: "none", boxShadow: 3,
        }}>
          Usa Ctrl + rueda para hacer zoom
        </Box>
      )}
    </Box>
  );
}
