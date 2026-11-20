// LineasSvg: dibujo reutilizable de series de líneas en SVG propio, en el mismo lenguaje que el resto de las gráficas
// (rejilla suave, ejes en gris, números en el hover, claro y oscuro, sin desborde a 390 px). No sabe nada de fútbol:
// no asume un solo equipo ni «jornadas». Lo usa «Forma durante la temporada» y lo reutilizará la trayectoria de ELO.
//
// Uso:
//   <LineasSvg
//     tk={t}                                  // tokens del tema: `useSitioTema().t` (muted, border, surface, primary)
//     ariaLabel="Texto que resume lo que dibuja"
//     series={[{ id, color, ancho = 2, opacidad = 1, punteada = false, radio = 0,
//                puntos: [{ x, y }] }]}         // y null/NaN corta la línea (un hueco); `radio` > 0 dibuja un punto en cada dato
//     x={{ dominio: [1, 38], paso, formato, categorias }}
//     y={{ dominio: [min, max], marcas: [..], formato }}
//     referencias={[{ y: 0, color, ancho, etiqueta }]}                // líneas horizontales (el cero, un promedio)
//     marcas={[{ x, fila = 0, forma = "circulo", color, hueco = false }]}   // marcas sobre el eje X, en filas
//     filasMarcas={[{ color }]}                                       // una por fila: la pista sobre la que van las marcas
//     tooltip={(x, puntos) => <nodo />}                               // contenido del hover para el x más cercano
//   />
//
// - Eje X numérico: `dominio` [mín, máx] y las marcas en múltiplos «redondos» (`paso` fuerza el salto). Si el eje es
//   de categorías (años, temporadas), pasa `categorias: ["2021-22", ...]`: los valores de x son los índices 0..n-1 y se
//   rotula con el texto de cada una (se omiten rótulos para que no se encimen). `formato(v)` da el rótulo en el eje.
// - Eje Y: `dominio` opcional (si no, se ajusta a los datos, a las referencias y a las marcas con un margen); las marcas
//   salen en números redondos; `formato(v)` rotula.
// - Hover y toque: la columna del valor de x más cercano a la posición del puntero (entre todos los x de las series y de
//   las marcas). `tooltip(x, puntos)` recibe ese x y `puntos`, una lista `{ serie, y }` con el valor de cada serie ahí
//   (y puede ser null). Devuelve el contenido (JSX) o null; el contenedor, la posición y el recorte son de este componente.
// - Pasa `series` y `marcas` con useMemo: al cambiar su identidad el hover se borra (no vale con otros datos).
// - Marcas: `forma` es "circulo" | "cuadrado" | "rombo" | "triangulo". `hueco` las dibuja vacías (solo contorno).
import { useEffect, useMemo, useRef, useState } from "react";
import Box from "@mui/material/Box";
import Paper from "@mui/material/Paper";

const MG = { l: 46, r: 14, t: 10 };      // márgenes del SVG
const FILA = 17, SEPARACION = 9, ALTO_EJE = 26;
const PASOS = [1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000];

const ok = (v) => v != null && Number.isFinite(v);

// Un número redondo (1, 2, 5 por una potencia de 10) igual o mayor a `x`.
function redondo(x) {
  const e = Math.pow(10, Math.floor(Math.log10(x)));
  const f = x / e;
  return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * e;
}

function marcasRedondas(lo, hi, cuantas) {
  const paso = redondo((hi - lo) / cuantas);
  const out = [];
  for (let v = Math.ceil(lo / paso - 1e-9) * paso; v <= hi + 1e-9; v += paso) out.push(Math.round(v / paso) * paso);
  return out;
}

function dominioY(series, referencias, marcas, dado) {
  if (dado) return dado;
  const v = [];
  series.forEach((s) => s.puntos.forEach((p) => { if (ok(p.y)) v.push(p.y); }));
  referencias.forEach((r) => v.push(r.y));
  (marcas || []).forEach((m) => v.push(m));
  if (!v.length) return [0, 1];
  let lo = Math.min(...v), hi = Math.max(...v);
  if (lo === hi) { lo -= 1; hi += 1; }
  const pad = (hi - lo) * 0.08;
  const paso = redondo((hi - lo) / 4);
  return [Math.floor((lo - pad) / paso) * paso, Math.ceil((hi + pad) / paso) * paso];
}

// Una serie se parte en tramos continuos cuando falta un valor.
function tramos(puntos) {
  const out = [];
  let cur = [];
  puntos.forEach((p) => {
    if (ok(p.y) && ok(p.x)) cur.push(p);
    else if (cur.length) { out.push(cur); cur = []; }
  });
  if (cur.length) out.push(cur);
  return out;
}

function useAncho(ref) {
  const [w, setW] = useState(0);
  useEffect(() => {
    const el = ref.current;
    const medir = () => setW(el.clientWidth);
    const ro = new ResizeObserver(medir);
    ro.observe(el);
    medir();
    return () => ro.disconnect();
  }, [ref]);
  return w;
}

function Marca({ cx, cy, forma, color, hueco, fondo, r = 4.4 }) {
  const rel = hueco ? { fill: fondo, stroke: color, strokeWidth: 1.7 } : { fill: color, stroke: fondo, strokeWidth: 0.8 };
  if (forma === "cuadrado") return <rect x={cx - r * 0.9} y={cy - r * 0.9} width={r * 1.8} height={r * 1.8} rx={0.8} {...rel} />;
  if (forma === "rombo") return <polygon points={`${cx},${cy - r * 1.2} ${cx + r * 1.2},${cy} ${cx},${cy + r * 1.2} ${cx - r * 1.2},${cy}`} {...rel} />;
  if (forma === "triangulo") return <polygon points={`${cx},${cy - r * 1.15} ${cx + r * 1.15},${cy + r * 0.9} ${cx - r * 1.15},${cy + r * 0.9}`} {...rel} />;
  return <circle cx={cx} cy={cy} r={r} {...rel} />;
}

export default function LineasSvg({ tk, ariaLabel, series, x, y = {}, referencias = [], marcas = [], filasMarcas = [],
  tooltip, alto = 260 }) {
  const caja = useRef(null);
  const w = useAncho(caja);
  const [hover, setHover] = useState(null);       // { x, px, py }

  useEffect(() => { setHover(null); }, [series, marcas]);   // un hover de antes no vale con otros datos

  const cats = x.categorias;
  const [d0, d1] = cats ? [0, Math.max(cats.length - 1, 1)] : x.dominio;
  const pw = Math.max(80, w - MG.l - MG.r);
  const px = (v) => MG.l + ((v - d0) / (d1 - d0 || 1)) * pw;
  const [y0, y1] = useMemo(() => dominioY(series, referencias, y.marcas, y.dominio), [series, referencias, y.marcas, y.dominio]);
  const marcasY = y.marcas || marcasRedondas(y0, y1, 5);
  const py = (v) => MG.t + alto * (1 - (v - y0) / (y1 - y0 || 1));
  const fmtY = y.formato || ((v) => String(v));
  const fmtX = x.formato || (cats ? (v) => cats[v] : (v) => String(v));

  const nFilas = filasMarcas.length || (marcas.length ? 1 : 0);
  const baseMarcas = MG.t + alto + SEPARACION;
  const baseEje = baseMarcas + nFilas * FILA + (nFilas ? 2 : 0);
  const altoTotal = baseEje + ALTO_EJE;

  // rótulos del eje X
  const ticksX = useMemo(() => {
    const porUnidad = pw / (d1 - d0 || 1);
    if (cats) {
      const ancho = Math.max(...cats.map((c) => String(c).length)) * 6.4 + 12;
      const paso = x.paso || Math.max(1, Math.ceil(ancho / porUnidad));
      const out = [];
      for (let i = 0; i < cats.length; i += paso) out.push(i);
      return out;
    }
    const paso = x.paso || PASOS.find((p) => p * porUnidad >= 30) || PASOS[PASOS.length - 1];
    const out = [];
    for (let v = Math.ceil(d0 / paso) * paso; v <= d1; v += paso) out.push(v);
    if (!x.paso && out.length && (out[0] - d0) * porUnidad >= 30) out.unshift(d0);
    return out;
  }, [cats, d0, d1, pw, x.paso]);

  // los x donde hay algo que mostrar en el hover
  const xs = useMemo(() => {
    const s = new Set();
    series.forEach((se) => se.puntos.forEach((p) => { if (ok(p.x)) s.add(p.x); }));
    marcas.forEach((m) => { if (ok(m.x)) s.add(m.x); });
    return [...s].sort((a, b) => a - b);
  }, [series, marcas]);

  const mover = (e) => {
    const r = e.currentTarget.getBoundingClientRect();
    const xp = e.clientX - r.left;
    if (!xs.length || xp < MG.l - 12 || xp > MG.l + pw + 12) { setHover(null); return; }
    let mejor = xs[0], dist = Infinity;
    for (const v of xs) { const d = Math.abs(px(v) - xp); if (d < dist) { dist = d; mejor = v; } }
    setHover({ x: mejor, px: e.clientX, py: e.clientY });
  };
  const salir = (e) => { if (e.pointerType === "mouse") setHover(null); };

  const puntosHover = hover && series.map((s) => {
    const p = s.puntos.find((q) => q.x === hover.x);
    return { serie: s, y: p && ok(p.y) ? p.y : null };
  });
  const contenido = hover && tooltip ? tooltip(hover.x, puntosHover) : null;
  const abajo = hover && hover.py > window.innerHeight * 0.55;

  return (
    <Box ref={caja} sx={{ width: "100%", position: "relative" }}>
      {w > 0 && (
        <svg role="img" aria-label={ariaLabel} width={w} height={altoTotal}
          onPointerMove={mover} onPointerDown={mover} onPointerLeave={salir}
          style={{ display: "block", touchAction: "pan-y" }}>
          <g fontSize={11} fill={tk.muted}>
            {marcasY.map((v) => (
              <g key={v}>
                <line x1={MG.l} x2={MG.l + pw} y1={py(v)} y2={py(v)} stroke={tk.border} strokeOpacity={0.8} />
                <text x={MG.l - 6} y={py(v) + 4} textAnchor="end">{fmtY(v)}</text>
              </g>
            ))}
          </g>
          {referencias.map((r, i) => (
            <g key={i}>
              <line x1={MG.l} x2={MG.l + pw} y1={py(r.y)} y2={py(r.y)} stroke={r.color || tk.muted} strokeWidth={r.ancho || 1.2} strokeOpacity={0.9} />
              {r.etiqueta && <text x={MG.l + pw - 2} y={py(r.y) - 4} fontSize={10.5} textAnchor="end" fill={tk.muted}>{r.etiqueta}</text>}
            </g>
          ))}
          {hover && <line x1={px(hover.x)} x2={px(hover.x)} y1={MG.t} y2={baseEje} stroke={tk.muted} strokeOpacity={0.5} strokeDasharray="3 3" />}

          {series.map((s) => (
            <g key={s.id}>
              {tramos(s.puntos).map((t, k) => (
                <polyline key={k} points={t.map((p) => `${px(p.x)},${py(p.y)}`).join(" ")} fill="none" stroke={s.color}
                  strokeWidth={s.ancho || 2} strokeOpacity={s.opacidad ?? 1} strokeDasharray={s.punteada ? "6 4" : undefined}
                  strokeLinejoin="round" strokeLinecap="round" />
              ))}
              {s.radio > 0 && s.puntos.filter((p) => ok(p.y) && ok(p.x)).map((p, k) => (
                <circle key={k} cx={px(p.x)} cy={py(p.y)} r={s.radio} fill={s.color} fillOpacity={s.opacidad ?? 1} />
              ))}
            </g>
          ))}
          {hover && puntosHover.filter((p) => p.y != null).map((p) => (
            <circle key={p.serie.id} cx={px(hover.x)} cy={py(p.y)} r={4.5} fill={p.serie.color} stroke={tk.surface} strokeWidth={1.5} />
          ))}

          {nFilas > 0 && (
            <g>
              {Array.from({ length: nFilas }, (_, f) => (
                <line key={f} x1={MG.l} x2={MG.l + pw} y1={baseMarcas + f * FILA + FILA / 2} y2={baseMarcas + f * FILA + FILA / 2}
                  stroke={(filasMarcas[f] && filasMarcas[f].color) || tk.border} strokeOpacity={0.45} strokeWidth={2} />
              ))}
              {marcas.map((m, i) => (
                <Marca key={i} cx={px(m.x)} cy={baseMarcas + (m.fila || 0) * FILA + FILA / 2} forma={m.forma} color={m.color}
                  hueco={m.hueco} fondo={tk.surface} r={hover && hover.x === m.x ? 5.6 : 4.4} />
              ))}
            </g>
          )}

          <g fontSize={11} fill={tk.muted}>
            <line x1={MG.l} x2={MG.l + pw} y1={baseEje} y2={baseEje} stroke={tk.border} />
            {ticksX.map((v) => (
              <g key={v}>
                <line x1={px(v)} x2={px(v)} y1={baseEje} y2={baseEje + 4} stroke={tk.muted} strokeOpacity={0.6} />
                <text x={px(v)} y={baseEje + 17} textAnchor="middle">{fmtX(v)}</text>
              </g>
            ))}
          </g>
        </svg>
      )}
      {contenido && (
        <Paper elevation={4} className="rx-tooltip" sx={{
          position: "fixed", left: Math.max(8, Math.min(hover.px + 14, window.innerWidth - 268)), top: hover.py + (abajo ? -14 : 14),
          transform: abajo ? "translateY(-100%)" : "none", p: 1.25, pointerEvents: "none", zIndex: 1500, border: 1,
          borderColor: "divider", fontSize: 12.5, width: 254,
        }}>
          {contenido}
        </Paper>
      )}
    </Box>
  );
}

// Un muestrario de una línea para las leyendas: trazo del color de la serie (con su opacidad y trazo punteado).
export function MuestraLinea({ color, opacidad = 1, punteada = false, ancho = 2.4 }) {
  return (
    <svg width={26} height={10} aria-hidden="true" style={{ flex: "none" }}>
      <line x1={1} x2={25} y1={5} y2={5} stroke={color} strokeWidth={ancho} strokeOpacity={opacidad}
        strokeDasharray={punteada ? "5 3" : undefined} strokeLinecap="round" />
    </svg>
  );
}
