// Las gráficas de los análisis largos de Machine Learning (`web/charts/ml_xg.py`), en React.
//
// A diferencia de las vistas del análisis exploratorio, estas no filtran una tabla de 10.000 filas: cada
// gráfica es el RESULTADO de un modelo y viaja ya calculada, en una tabla pequeña
// (`dist/react/datos-xg.js`, ver `react_views.registrar_payload`). El navegador solo la dibuja y le
// agrega lo que el papel no tenía: pasar el mouse, ocultar series, cambiar de modo oscuro sin
// recargar y, en el mapa de valor del tiro, elegir qué tiro se quiere ver.
//
// Tipos, casi todos en SVG propio sobre un mismo marco (`Marco`) y con el tema de MUI:
//   lineas     calibración, trayectoria del sesgo, curva de aprendizaje, cabeza contra pie
//   forest     escalera de variables y diferencias por temporada (Δ log-loss con su intervalo)
//   barras     tasas de gol, sesgo por grupo, importancia de las variables
//   puntos     modelos en una métrica a elegir (log-loss, AUC...) sobre un eje que no empieza en cero
//   ventanas   cómo se parte el tiempo en entrenar, validar y probar
//   dispersion un punto por equipo, con tendencia
//   superficie el mapa de valor del tiro sobre la cancha, con controles
//   mapa       lo mismo con datos: tiros, tasa de gol y xG de Understat por zona, y franjas de distancia y ángulo
//   apiladas   columnas por temporada con la liga como color
//   arbol      el árbol de decisión interactivo (`Arbol.jsx`)
//   explorador elegir un tiro de entre los de cinco temporadas (`Explorador.jsx`, canvas)
import { useEffect, useMemo, useRef, useState } from "react";
import { ThemeProvider } from "@mui/material/styles";
import Box from "@mui/material/Box";
import Paper from "@mui/material/Paper";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import Typography from "@mui/material/Typography";
import { useSitioTema } from "./theme.jsx";
import { cargarDatos } from "./datos.js";
import { Aviso, Cargando, Rotulo } from "./ui.jsx";
import { conAlfa } from "./colores.js";
import { ajusteLineal } from "./stats.js";
import { miles } from "./milesComa.js";
import Arbol from "./Arbol.jsx";
import Explorador from "./Explorador.jsx";

// --- utilidades ---------------------------------------------------------------------------------

const FORMATO = {
  num0: (v) => String(Math.round(v)),
  num1: (v) => v.toFixed(1),
  num2: (v) => v.toFixed(2),
  num3: (v) => v.toFixed(3),
  num4: (v) => v.toFixed(4),
  pct0: (v) => `${Math.round(v)}%`,
  pct1: (v) => `${v.toFixed(1)}%`,
  signo1: (v) => `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(1)}%`,
  signo4: (v) => `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(4)}`,
  razon: (v) => `×${v.toFixed(2)}`,
  m: (v) => `${Math.round(v)} m`,
  miles: (v) => miles(Math.round(v)),
  log10: (v) => miles(Math.round(10 ** v)),     // el eje guarda log10 del valor
  grados: (v) => `${Math.round(v)}°`,
  fraccion: (v) => `${Math.round(v * 100)}%`,   // 0.12 -> 12%
};
const fm = (clave) => FORMATO[clave] || FORMATO.num2;

const lineal = (d0, d1, r0, r1) => {
  const k = (r1 - r0) / (d1 - d0 || 1);
  return (v) => r0 + (v - d0) * k;
};

// Marcas "bonitas" (1, 2, 5 × 10^k) entre min y max.
function marcas(min, max, n = 5) {
  const span = max - min;
  if (!(span > 0)) return [min];
  const bruto = span / n;
  const mag = 10 ** Math.floor(Math.log10(bruto));
  const f = bruto / mag;
  const paso = (f < 1.5 ? 1 : f < 3 ? 2 : f < 7 ? 5 : 10) * mag;
  const out = [];
  for (let v = Math.ceil(min / paso - 1e-9) * paso; v <= max + paso * 1e-6; v += paso) out.push(Number(v.toPrecision(10)));
  return out;
}

function useAncho() {
  const ref = useRef(null);
  const [ancho, setAncho] = useState(0);
  useEffect(() => {
    if (!ref.current) return undefined;
    const ro = new ResizeObserver(([e]) => setAncho(Math.round(e.contentRect.width)));
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);
  return [ref, ancho];
}

function useDatos(nombre) {
  const [est, setEst] = useState({ D: null, error: null });
  useEffect(() => {
    let vivo = true;
    cargarDatos(nombre)
      .then((D) => vivo && setEst({ D, error: null }))
      .catch((e) => vivo && setEst({ D: null, error: e }));
    return () => { vivo = false; };
  }, [nombre]);
  return est;
}

// Los colores con significado fijo en todo el artículo: azul = mi modelo, rojo = Understat.
function paletaDe(modo, tk) {
  const osc = modo === "dark";
  return {
    propio: osc ? "#6da7ec" : "#256abf",
    understat: osc ? "#f27b7a" : "#d93a39",
    neutro: tk.muted,
    acento: osc ? "#6fdb3b" : "#2e7a06",
    aviso: osc ? "#e0a93b" : "#b7791f",
  };
}
const color = (c, pal) => pal[c] || c;

// El tema del texto y de la grilla sale de los tokens del sitio, no de los de MUI.
const estiloTexto = (tk) => ({ fill: tk.muted, fontSize: 11.5 });

function Cabecera({ cfg }) {
  return (
    <>
      <Typography component="h3" sx={{ fontSize: 17, fontWeight: 700, color: "primary.main", lineHeight: 1.25, m: 0 }}>
        {cfg.titulo}
      </Typography>
      {cfg.subtitulo && (
        <Typography sx={{ fontSize: 13, color: "text.secondary", mb: 1.25 }}>{cfg.subtitulo}</Typography>
      )}
    </>
  );
}

function Pie({ cfg, extra }) {
  return (
    <Box sx={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", gap: 1, mt: 0.75 }}>
      <Typography sx={{ fontSize: 12, color: "text.secondary" }}>{extra || cfg.ayuda || ""}</Typography>
      <Typography sx={{ fontSize: 12, color: "text.secondary" }}>Datos: {cfg.fuente}</Typography>
    </Box>
  );
}

// Un tooltip pegado al puntero, dentro del contenedor, que se voltea para no salirse por la derecha.
function Tip({ tip, ancho, children }) {
  if (!tip) return null;
  const ladoIzq = tip.px > ancho * 0.58;
  return (
    <Paper elevation={4} className="rx-tooltip"
      sx={{ position: "absolute", top: Math.max(0, tip.py - 12), pointerEvents: "none", zIndex: 5, p: 1.1,
        minWidth: 150, maxWidth: 260, border: 1, borderColor: "divider", fontSize: 12.5,
        ...(ladoIzq ? { right: ancho - tip.px + 14 } : { left: tip.px + 14 }) }}>
      {children}
    </Paper>
  );
}

const Fila = ({ c, nombre, valor, fuerte }) => (
  <Box sx={{ display: "flex", alignItems: "center", gap: 0.75, justifyContent: "space-between" }}>
    <Box component="span" sx={{ display: "flex", alignItems: "center", gap: 0.75, color: "text.secondary" }}>
      {c && <Box component="span" sx={{ width: 10, height: 10, borderRadius: "50%", bgcolor: c, flex: "none" }} />}
      {nombre}
    </Box>
    <Box component="span" sx={{ fontWeight: fuerte ? 800 : 700 }}>{valor}</Box>
  </Box>
);

// --- marco: ejes, grilla y puntero ---------------------------------------------------------------
// `render({ px, py, w, h, hover })` devuelve `{ nodos, tip }`: lo que se dibuja dentro del área y, si hay
// algo bajo el puntero, el contenido del tooltip. El marco es el dueño del puntero.
function Marco({ alto = 380, margen, x, y, tk, aria, render }) {
  const [ref, ancho] = useAncho();
  const [hover, setHover] = useState(null);
  const angosto = ancho > 0 && ancho < 520;
  const m = { t: 12, r: angosto ? 10 : 18, b: x.etiqueta ? 52 : 34, l: angosto ? 48 : 60, ...margen };
  const w = Math.max(10, ancho - m.l - m.r), h = alto - m.t - m.b;
  const px = lineal(x.dom[0], x.dom[1], 0, w);
  const py = lineal(y.dom[0], y.dom[1], h, 0);
  const xs = x.marcas || marcas(x.dom[0], x.dom[1], Math.max(3, Math.round(w / 95)));
  const ys = y.marcas || marcas(y.dom[0], y.dom[1], Math.max(3, Math.round(h / 58)));
  const fx = x.valor || fm(x.formato), fy = y.valor || fm(y.formato);
  const svgRef = useRef(null);
  const mover = (e) => {
    const r = svgRef.current.getBoundingClientRect();
    setHover({ cx: e.clientX - r.left - m.l, cy: e.clientY - r.top - m.t,
      px: e.clientX - r.left, py: e.clientY - r.top });
  };
  const t = estiloTexto(tk);
  const out = ancho > 0 ? render({ px, py, w, h, hover }) : { nodos: null, tip: null };
  return (
    <Box ref={ref} className="rx-chart" sx={{ position: "relative", width: "100%", userSelect: "none" }}>
      {ancho > 0 && (
        <svg ref={svgRef} width={ancho} height={alto} role="img" aria-label={aria}
          style={{ display: "block", touchAction: "pan-y" }}
          onPointerMove={mover} onPointerDown={mover} onPointerLeave={() => setHover(null)}>
          <g transform={`translate(${m.l},${m.t})`}>
            {ys.map((v) => (
              <g key={`y${v}`}>
                <line x1={0} x2={w} y1={py(v)} y2={py(v)} stroke={tk.border} strokeOpacity={0.8} />
                <text x={-8} y={py(v)} dy="0.32em" textAnchor="end" {...t}>{fy(v)}</text>
              </g>
            ))}
            {xs.map((v, i) => (
              <g key={`x${v}`}>
                <line x1={px(v)} x2={px(v)} y1={h} y2={h + 5} stroke={tk.border} />
                <text x={px(v)} y={h + 19} textAnchor="middle" {...t}>{fx(v, i)}</text>
              </g>
            ))}
            <line x1={0} x2={w} y1={h} y2={h} stroke={tk.border} />
            {out.nodos}
          </g>
          {x.etiqueta && (
            <text x={m.l + w / 2} y={alto - 10} textAnchor="middle" fontSize={12.5} fontWeight={600} fill={tk["text-body"]}>
              {x.etiqueta}
            </text>
          )}
          {y.etiqueta && (
            <text transform={`translate(13 ${m.t + h / 2}) rotate(-90)`} textAnchor="middle" fontSize={12.5}
              fontWeight={600} fill={tk["text-body"]}>{y.etiqueta}</text>
          )}
        </svg>
      )}
      {hover && out.tip && <Tip tip={{ px: hover.px, py: hover.py }} ancho={ancho}>{out.tip}</Tip>}
    </Box>
  );
}

// Leyenda de series: chips que ocultan/muestran. Una serie oculta no cuenta para los ejes.
function Leyenda({ series, ocultas, onToggle, pal, fija }) {
  if (series.length < 2) return null;
  return (
    <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.75, mb: 1 }} role="group" aria-label="Series">
      {series.map((s) => {
        const apagada = !!ocultas[s.id];
        return (
          <Box key={s.id} component={fija ? "span" : "button"} type={fija ? undefined : "button"}
            onClick={fija ? undefined : () => onToggle(s.id)} aria-pressed={fija ? undefined : !apagada}
            sx={{ display: "inline-flex", alignItems: "center", gap: 0.75, px: 1.1, py: 0.45, borderRadius: 999,
              border: 1, borderColor: "divider", bgcolor: "background.paper", color: "text.primary",
              font: "600 12.5px Inter, system-ui", cursor: fija ? "default" : "pointer", opacity: apagada ? 0.45 : 1,
              "&:hover": fija ? {} : { borderColor: "text.secondary" },
              "&:focus-visible": { outline: "2px solid var(--color-interactive)", outlineOffset: 1 } }}>
            <Box component="span" sx={{ width: 16, height: 3, borderRadius: 1, bgcolor: color(s.color, pal),
              ...(s.trazo === "punteado" ? { background: `repeating-linear-gradient(90deg, ${color(s.color, pal)} 0 4px, transparent 4px 7px)` } : {}) }} />
            {s.nombre}
          </Box>
        );
      })}
    </Box>
  );
}

// --- líneas -------------------------------------------------------------------------------------
// G: { x: {etiqueta, formato, dom?, categorias?}, y: {...}, series: [{id, nombre, color, puntos: [[x, y, lo?, hi?, n?]],
//      banda?: bool, marcador?: bool, trazo?}], referencias: [{tipo: "diagonal"|"h", valor?, etiqueta}] }
function Lineas({ cfg, D, tk, pal }) {
  const G = D[cfg.dato];
  const [ocultas, setOcultas] = useState({});
  const [ref, ancho] = useAncho();
  const series = G.series.filter((s) => !ocultas[s.id]);
  const cat = G.x.categorias;

  const xs = series.flatMap((s) => s.puntos.map((p) => p[0]));
  const ys = series.flatMap((s) => s.puntos.flatMap((p) => [p[1], ...(p[2] != null ? [p[2], p[3]] : [])]));
  const hs = (G.referencias || []).filter((r) => r.tipo === "h").map((r) => r.valor);
  const lo = Math.min(...ys, ...hs), hi = Math.max(...ys, ...hs);
  const pad = (hi - lo) * 0.08 || 0.05;
  const xlo = Math.min(...xs), xhi = Math.max(...xs);
  const xdom = G.x.dom || (cat ? [-0.4, cat.length - 0.6] : [xlo - (xhi - xlo) * 0.03, xhi + (xhi - xlo) * 0.03]);
  const ydom = G.y.dom || [lo - pad, hi + pad];
  const angosto = ancho > 0 && ancho < 520;
  const xeje = cat
    ? { ...G.x, dom: xdom, marcas: cat.map((_, i) => i).filter((i) => !angosto || i % 2 === 0),
        valor: (v) => cat[Math.round(v)]?.replace(/^20/, "") ?? "" }
    : { ...G.x, dom: xdom };

  const render = ({ px, py, w, h, hover }) => {
    // El punto más cercano al puntero: con x categórica, la misma temporada en todas las series; con x
    // continua, el más cercano de cada serie que quede a menos de 70 px.
    let activos = null;
    if (hover) {
      const cand = series.map((s) => {
        let mejor = 0, dmin = Infinity;
        s.puntos.forEach((p, i) => { const d = Math.abs(px(p[0]) - hover.cx); if (d < dmin) { dmin = d; mejor = i; } });
        return { s, p: s.puntos[mejor], d: dmin };
      });
      const dm = Math.min(...cand.map((c) => c.d));
      if (dm <= 70) {
        const x0 = cand.find((c) => c.d === dm).p[0];
        activos = cand.filter((c) => (cat ? c.p[0] === x0 : c.d <= dm + 70));
      }
    }
    const nodos = (
      <>
        {(G.referencias || []).map((r, i) => {
          if (r.tipo === "diagonal") {
            const a = Math.max(xdom[0], ydom[0]), b = Math.min(xdom[1], ydom[1]);
            return <line key={i} x1={px(a)} y1={py(a)} x2={px(b)} y2={py(b)} stroke={tk.muted} strokeWidth={1.4}
              strokeDasharray="5 4" strokeOpacity={0.8} />;
          }
          if (r.tipo === "h") {
            return (
              <g key={i}>
                <line x1={0} x2={w} y1={py(r.valor)} y2={py(r.valor)} stroke={tk.muted} strokeWidth={1.2}
                  strokeDasharray="5 4" strokeOpacity={0.85} />
                {r.etiqueta && (
                  <text x={w - 4} y={py(r.valor) - 5} textAnchor="end" fontSize={11} fill={tk.muted}
                    stroke={tk.surface} strokeWidth={3} paintOrder="stroke">{r.etiqueta}</text>
                )}
              </g>
            );
          }
          return null;
        })}
        {series.map((s) => {
          const c = color(s.color, pal);
          const pts = s.puntos;
          const ruta = pts.map((p, i) => `${i ? "L" : "M"}${px(p[0])},${py(p[1])}`).join("");
          const hayBanda = s.banda && pts.every((p) => p[2] != null);
          const poligono = hayBanda
            ? pts.map((p) => `${px(p[0])},${py(p[3])}`).join(" ") + " " +
              [...pts].reverse().map((p) => `${px(p[0])},${py(p[2])}`).join(" ")
            : null;
          return (
            <g key={s.id}>
              {hayBanda && <polygon points={poligono} fill={conAlfa(c, 0.16)} stroke="none" />}
              <path d={ruta} fill="none" stroke={c} strokeWidth={s.grosor || 2.6} strokeLinejoin="round"
                strokeDasharray={s.trazo === "punteado" ? "6 5" : undefined} />
              {s.marcador !== false && pts.map((p, i) => (
                <circle key={i} cx={px(p[0])} cy={py(p[1])} r={4.2} fill={c} stroke={tk.surface} strokeWidth={1.5} />
              ))}
            </g>
          );
        })}
        {activos && (
          <g pointerEvents="none">
            <line x1={px(activos[0].p[0])} x2={px(activos[0].p[0])} y1={0} y2={h} stroke={tk.muted} strokeOpacity={0.5} />
            {activos.map(({ s, p }) => (
              <circle key={s.id} cx={px(p[0])} cy={py(p[1])} r={7} fill="none" stroke={color(s.color, pal)} strokeWidth={2.4} />
            ))}
          </g>
        )}
      </>
    );
    const tip = activos && (
      <>
        <Typography sx={{ fontWeight: 700, fontSize: 12.5, mb: 0.5 }}>
          {cat ? cat[Math.round(activos[0].p[0])] : `${G.x.etiqueta_corta || G.x.etiqueta || "x"}: ${fm(G.x.formato)(activos[0].p[0])}`}
        </Typography>
        {activos.map(({ s, p }) => (
          <Fila key={s.id} c={color(s.color, pal)} nombre={s.nombre}
            valor={`${fm(G.y.formato)(p[1])}${p[4] != null ? ` · ${miles(p[4])} ${G.unidad_n || "tiros"}` : ""}`} />
        ))}
        {G.nota_tip && <Typography sx={{ fontSize: 11.5, color: "text.secondary", mt: 0.5 }}>{G.nota_tip}</Typography>}
      </>
    );
    return { nodos, tip };
  };

  return (
    <Box ref={ref}>
      <Cabecera cfg={cfg} />
      <Leyenda series={G.series} ocultas={ocultas} pal={pal}
        onToggle={(id) => setOcultas((o) => ({ ...o, [id]: !o[id] }))} />
      <Marco alto={cfg.alto || (angosto ? 320 : 400)} x={xeje} y={{ ...G.y, dom: ydom }} tk={tk} aria={cfg.alt} render={render} />
      <Pie cfg={cfg} />
    </Box>
  );
}

// --- forest: un valor con su intervalo por fila ---------------------------------------------------
// G: { eje: {etiqueta, ref, formato, dom, mejor: "izq"|"der"}, filas: [{nombre, nota?, valor, lo, hi, texto, grupo?}],
//      columnas: [titulo...] }
function Forest({ cfg, D, tk, pal }) {
  const G = D[cfg.dato];
  const [ref, ancho] = useAncho();
  const [sel, setSel] = useState(null);
  const filas = G.filas;
  const [d0, d1] = G.eje.dom;
  const w = Math.max(60, ancho);
  const px = lineal(d0, d1, 6, w - 6);
  const marcasX = marcas(d0, d1, Math.max(3, Math.round(w / 90)));
  const fx = fm(G.eje.formato);
  const alto = 44;
  const cPos = pal.propio, cNeg = pal.understat;
  return (
    <Box>
      <Cabecera cfg={cfg} />
      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "minmax(110px, 1fr) minmax(0, 1.3fr) auto", sm: "minmax(190px, 1fr) minmax(0, 1.7fr) auto" },
        columnGap: 1.5, alignItems: "center" }}>
        <Box />
        <Box ref={ref} sx={{ height: 26, position: "relative" }}>
          {ancho > 0 && (
            <svg width={w} height={26} aria-hidden="true" style={{ display: "block" }}>
              {marcasX.map((v) => (
                <text key={v} x={px(v)} y={18} textAnchor="middle" {...estiloTexto(tk)}>{fx(v)}</text>
              ))}
            </svg>
          )}
        </Box>
        <Box sx={{ fontSize: 11, fontWeight: 700, color: "text.secondary", textAlign: "right", textTransform: "uppercase", letterSpacing: ".05em" }}>
          {G.columna}
        </Box>
        {filas.map((f, i) => {
          const activo = sel === i;
          const mejora = G.eje.mejor === "izq" ? f.valor < G.eje.ref : f.valor > G.eje.ref;
          const cruza = f.lo <= G.eje.ref && f.hi >= G.eje.ref;   // el intervalo incluye "sin efecto"
          const c = cruza ? tk.muted : mejora ? cPos : cNeg;
          return (
            <Box key={i} sx={{ display: "contents" }}
              onMouseEnter={() => setSel(i)} onMouseLeave={() => setSel(null)}>
              <Box sx={{ py: 0.75, pr: 1, borderTop: 1, borderColor: "divider", bgcolor: activo ? "action.hover" : "transparent",
                fontSize: 13, lineHeight: 1.3, fontWeight: f.destacado ? 700 : 500 }}>
                {f.nombre}
                {f.nota && <Box component="span" sx={{ display: "block", fontSize: 11.5, color: "text.secondary", fontWeight: 400 }}>{f.nota}</Box>}
              </Box>
              <Box sx={{ borderTop: 1, borderColor: "divider", bgcolor: activo ? "action.hover" : "transparent", height: alto }}>
                {ancho > 0 && (
                  <svg width={w} height={alto} role="img" aria-label={`${f.nombre}: ${f.texto}`} style={{ display: "block" }}>
                    {marcasX.map((v) => (
                      <line key={v} x1={px(v)} x2={px(v)} y1={0} y2={alto} stroke={tk.border} strokeOpacity={0.6} />
                    ))}
                    <line x1={px(G.eje.ref)} x2={px(G.eje.ref)} y1={0} y2={alto} stroke={tk.muted} strokeWidth={1.4}
                      strokeDasharray="4 3" />
                    {G.eje.referencias?.map((r) => (
                      <line key={r.etiqueta} x1={px(r.valor)} x2={px(r.valor)} y1={0} y2={alto} stroke={pal.understat}
                        strokeWidth={1.4} strokeDasharray="2 3" />
                    ))}
                    <line x1={px(f.lo)} x2={px(f.hi)} y1={alto / 2} y2={alto / 2} stroke={c} strokeWidth={2.4} strokeLinecap="round" />
                    <line x1={px(f.lo)} x2={px(f.lo)} y1={alto / 2 - 5} y2={alto / 2 + 5} stroke={c} strokeWidth={2} />
                    <line x1={px(f.hi)} x2={px(f.hi)} y1={alto / 2 - 5} y2={alto / 2 + 5} stroke={c} strokeWidth={2} />
                    <circle cx={px(f.valor)} cy={alto / 2} r={activo ? 7 : 5.5} fill={c} stroke={tk.surface} strokeWidth={1.5} />
                  </svg>
                )}
              </Box>
              <Box sx={{ borderTop: 1, borderColor: "divider", bgcolor: activo ? "action.hover" : "transparent", height: alto,
                display: "flex", alignItems: "center", justifyContent: "flex-end", fontSize: 12.5, fontWeight: 700,
                whiteSpace: "nowrap", pl: 0.5 }}>
                {f.texto}
              </Box>
            </Box>
          );
        })}
      </Box>
      {G.eje.etiqueta && (
        <Typography sx={{ fontSize: 12.5, fontWeight: 600, textAlign: "center", mt: 0.75 }}>{G.eje.etiqueta}</Typography>
      )}
      {G.eje.referencias?.length > 0 && (
        <Typography sx={{ fontSize: 11.5, color: "text.secondary", mt: 0.25, textAlign: "center" }}>
          <Box component="span" sx={{ color: pal.understat, fontWeight: 700 }}>┆</Box> {G.eje.referencias.map((r) => r.etiqueta).join(" · ")}
        </Typography>
      )}
      <Pie cfg={cfg} />
    </Box>
  );
}

// --- barras ---------------------------------------------------------------------------------------
// G: { agrupaciones: [{id, etiqueta, filas: [{nombre, n?, valores: {serie: v}}]}], series: [{id, nombre, color}],
//      eje: {formato, dom?, etiqueta}, ref? }
function Barras({ cfg, D, tk, pal }) {
  const G = D[cfg.dato];
  const [agr, setAgr] = useState(G.agrupaciones[0].id);
  const [ref, ancho] = useAncho();
  const [sel, setSel] = useState(null);
  const grupo = G.agrupaciones.find((a) => a.id === agr) || G.agrupaciones[0];
  const todos = G.agrupaciones.flatMap((a) => a.filas.flatMap((f) => Object.values(f.valores)));
  const lo = Math.min(0, ...todos), hi = Math.max(0, ...todos);
  // una agrupación puede traer su propio dominio (las que no comparten escala con las demás)
  const dom = grupo.dom || G.eje.dom || [lo < 0 ? lo - (hi - lo) * 0.14 : lo, hi + (hi - lo) * 0.1];   // espacio para el rótulo de un valor negativo
  const w = Math.max(80, ancho);
  const px = lineal(dom[0], dom[1], 4, w - 4);
  const marcasX = marcas(dom[0], dom[1], Math.max(3, Math.round(w / 90)));
  const fx = fm(G.eje.formato);
  const grosor = 14, sep = 4;
  const altoFila = G.series.length * grosor + (G.series.length - 1) * sep + 18;
  return (
    <Box>
      <Cabecera cfg={cfg} />
      {G.agrupaciones.length > 1 && (
        <Box sx={{ mb: 1.25 }}>
          <Rotulo>{G.rotulo || "Agrupar por"}</Rotulo>
          <ToggleButtonGroup exclusive size="small" value={agr} aria-label="Agrupar por"
            onChange={(_e, v) => v && setAgr(v)} sx={{ flexWrap: "wrap" }}>
            {G.agrupaciones.map((a) => <ToggleButton key={a.id} value={a.id}>{a.etiqueta}</ToggleButton>)}
          </ToggleButtonGroup>
        </Box>
      )}
      {G.series.length > 1 && (
        <Leyenda series={G.series} ocultas={{}} onToggle={() => {}} pal={pal} fija />
      )}
      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "minmax(96px, 0.9fr) minmax(0, 1.6fr)", sm: "minmax(150px, 0.8fr) minmax(0, 2fr)" }, columnGap: 1.5 }}>
        <Box />
        <Box ref={ref} sx={{ height: 24 }}>
          {ancho > 0 && (
            <svg width={w} height={24} aria-hidden="true" style={{ display: "block" }}>
              {marcasX.map((v) => <text key={v} x={px(v)} y={16} textAnchor="middle" {...estiloTexto(tk)}>{fx(v)}</text>)}
            </svg>
          )}
        </Box>
        {grupo.filas.map((f, i) => {
          const activo = sel === i;
          return (
            <Box key={`${agr}-${i}`} sx={{ display: "contents" }} onMouseEnter={() => setSel(i)} onMouseLeave={() => setSel(null)}>
              <Box sx={{ py: 0.5, pr: 1, borderTop: 1, borderColor: "divider", display: "flex", flexDirection: "column", justifyContent: "center",
                bgcolor: activo ? "action.hover" : "transparent", fontSize: 13, lineHeight: 1.25 }}>
                <span>{f.nombre}</span>
                {f.n != null && <Box component="span" sx={{ fontSize: 11.5, color: "text.secondary" }}>{miles(f.n)} {G.unidad || "tiros"}</Box>}
              </Box>
              <Box sx={{ borderTop: 1, borderColor: "divider", bgcolor: activo ? "action.hover" : "transparent", height: altoFila }}>
                {ancho > 0 && (
                  <svg width={w} height={altoFila} role="img" aria-label={`${f.nombre}: ${G.series.map((s) => `${s.nombre} ${fm(G.eje.formato)(f.valores[s.id])}`).join(", ")}`}
                    style={{ display: "block" }}>
                    {marcasX.map((v) => <line key={v} x1={px(v)} x2={px(v)} y1={0} y2={altoFila} stroke={tk.border} strokeOpacity={0.6} />)}
                    <line x1={px(0)} x2={px(0)} y1={0} y2={altoFila} stroke={tk.muted} strokeWidth={1.4} />
                    {G.series.map((s, k) => {
                      const v = f.valores[s.id];
                      if (v == null) return null;
                      const y0 = 9 + k * (grosor + sep);
                      const x0 = px(Math.min(0, v)), x1 = px(Math.max(0, v));
                      return (
                        <g key={s.id}>
                          <rect x={x0} y={y0} width={Math.max(1, x1 - x0)} height={grosor} rx={2} fill={color(s.color, pal)} />
                          <text x={v >= 0 ? x1 + 5 : x0 - 5} y={y0 + grosor / 2} dy="0.34em" textAnchor={v >= 0 ? "start" : "end"}
                            fontSize={11.5} fontWeight={700} fill={tk["text-body"]}>{fx(v)}</text>
                        </g>
                      );
                    })}
                  </svg>
                )}
              </Box>
            </Box>
          );
        })}
      </Box>
      {G.eje.etiqueta && <Typography sx={{ fontSize: 12.5, fontWeight: 600, textAlign: "center", mt: 0.75 }}>{G.eje.etiqueta}</Typography>}
      <Pie cfg={cfg} />
    </Box>
  );
}

// --- dispersión: un punto por equipo ---------------------------------------------------------------
// G: { x: {...}, y: {...}, grupos: [{id, nombre, color, colorOscuro}], puntos: [{n, g, x, y}], tendencia: bool }
function Dispersion({ cfg, D, tk, pal, modo }) {
  const G = D[cfg.dato];
  const [ocultos, setOcultos] = useState({});
  const [ref, ancho] = useAncho();
  const vis = G.puntos.filter((p) => !ocultos[p.g]);
  const xs = G.puntos.map((p) => p.x), ys = G.puntos.map((p) => p.y);
  const ex = (Math.max(...xs) - Math.min(...xs)) * 0.05, ey = (Math.max(...ys) - Math.min(...ys)) * 0.08;
  const xdom = G.x.dom || [Math.min(...xs) - ex, Math.max(...xs) + ex];
  const ydom = G.y.dom || [Math.min(...ys) - ey, Math.max(...ys) + ey];
  const colorG = (g) => { const k = G.grupos[g]; return modo === "dark" && k.colorOscuro ? k.colorOscuro : k.color; };
  const recta = G.tendencia && vis.length > 2 ? ajusteLineal(vis.map((p) => p.x), vis.map((p) => p.y)) : null;
  const angosto = ancho > 0 && ancho < 520;

  const render = ({ px, py, w, hover }) => {
    let cercano = null;
    if (hover) {
      let dmin = 18 * 18;
      vis.forEach((p) => { const d = (px(p.x) - hover.cx) ** 2 + (py(p.y) - hover.cy) ** 2; if (d < dmin) { dmin = d; cercano = p; } });
    }
    const nodos = (
      <>
        {(G.referencias || []).map((r, i) => r.tipo === "h" && (
          <g key={i}>
            <line x1={0} x2={w} y1={py(r.valor)} y2={py(r.valor)} stroke={tk.muted} strokeDasharray="5 4" strokeOpacity={0.8} />
            {r.etiqueta && <text x={w - 4} y={py(r.valor) - 5} textAnchor="end" fontSize={11} fill={tk.muted}
              stroke={tk.surface} strokeWidth={3} paintOrder="stroke">{r.etiqueta}</text>}
          </g>
        ))}
        {recta && (
          <line x1={px(xdom[0])} y1={py(recta[0] * xdom[0] + recta[1])} x2={px(xdom[1])} y2={py(recta[0] * xdom[1] + recta[1])}
            stroke={tk["text-body"]} strokeWidth={1.8} strokeOpacity={0.7} strokeDasharray="7 4" />
        )}
        {vis.map((p, i) => (
          <circle key={i} cx={px(p.x)} cy={py(p.y)} r={p === cercano ? 8 : 5.2} fill={colorG(p.g)} fillOpacity={0.82}
            stroke={p === cercano ? tk.primary : tk.surface} strokeWidth={p === cercano ? 2 : 0.8} />
        ))}
      </>
    );
    const tip = cercano && (
      <>
        <Typography sx={{ fontWeight: 700, fontSize: 13, lineHeight: 1.25 }}>{cercano.n}</Typography>
        <Box sx={{ display: "flex", alignItems: "center", gap: 0.75, mb: 0.5, color: "text.secondary", fontSize: 12 }}>
          <Box component="span" sx={{ width: 12, height: 3, borderRadius: 1, bgcolor: colorG(cercano.g) }} />
          {G.grupos[cercano.g].nombre}
        </Box>
        <Fila nombre={G.x.etiqueta_corta || G.x.etiqueta} valor={fm(G.x.formato)(cercano.x)} />
        <Fila nombre={G.y.etiqueta_corta || G.y.etiqueta} valor={fm(G.y.formato)(cercano.y)} />
      </>
    );
    return { nodos, tip };
  };

  return (
    <Box ref={ref}>
      <Cabecera cfg={cfg} />
      <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.75, mb: 1 }} role="group" aria-label="Ligas">
        {G.grupos.map((g, i) => (
          <Box key={g.id} component="button" type="button" aria-pressed={!ocultos[i]}
            onClick={() => setOcultos((o) => ({ ...o, [i]: !o[i] }))}
            sx={{ display: "inline-flex", alignItems: "center", gap: 0.75, px: 1.1, py: 0.45, borderRadius: 999, border: 1,
              borderColor: "divider", bgcolor: "background.paper", color: "text.primary", font: "600 12.5px Inter, system-ui",
              cursor: "pointer", opacity: ocultos[i] ? 0.45 : 1 }}>
            <Box component="span" sx={{ width: 10, height: 10, borderRadius: "50%", bgcolor: colorG(i) }} />
            {g.nombre}
          </Box>
        ))}
      </Box>
      <Marco alto={cfg.alto || (angosto ? 340 : 420)} x={{ ...G.x, dom: xdom }} y={{ ...G.y, dom: ydom }} tk={tk}
        aria={cfg.alt} render={render} />
      <Pie cfg={cfg} extra={recta ? `Línea punteada: tendencia lineal (${G.tendencia_texto || "mínimos cuadrados"}).` : cfg.ayuda} />
    </Box>
  );
}

// --- superficie: el mapa de valor del tiro --------------------------------------------------------
// La cancha mira HACIA LA PORTERÍA, igual que el mapa de calor de tiros del análisis exploratorio:
// la línea de fondo es el borde de arriba. Cada combinación de controles es una rejilla ya calculada.
function Superficie({ cfg, D, tk, modo }) {
  const S = D[cfg.dato];
  const [sit, setSit] = useState(S.situaciones[0].id);
  const [parte, setParte] = useState(S.partes[0].id);
  const [accion, setAccion] = useState(S.acciones[0].id);
  const [cel, setCel] = useState(null);
  const svgRef = useRef(null);
  const situacion = S.situaciones.find((s) => s.id === sit);
  const usaAccion = !!situacion.usaAccion;
  const clave = `${sit}|${parte}|${usaAccion ? accion : "-"}`;
  const rej = S.rejillas[clave];

  const rampa = useMemo(() => (modo === "dark" ? [...S.rampa].reverse() : S.rampa), [S, modo]);
  const hex = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
  const colorRampa = (t) => {
    const x = Math.min(1, Math.max(0, t)) * (rampa.length - 1);
    const i = Math.min(rampa.length - 2, Math.floor(x)), f = x - i;
    const a = hex(rampa[i]), b = hex(rampa[i + 1]);
    return `rgb(${a.map((v, k) => Math.round(v + (b[k] - v) * f)).join(",")})`;
  };

  const { nx, ny, largo, ancho: A } = S;
  // columnas = distancia a la línea de fondo (de lejos a cerca), filas = ancho de la cancha
  const dCol = (c) => (1 - (S.xmin + (S.xmax - S.xmin) * (c / (nx - 1)))) * largo;
  const wFila = (r) => (S.ymin + (S.ymax - S.ymin) * (r / (ny - 1))) * A;
  const celdaAlto = ((S.xmax - S.xmin) / (nx - 1)) * largo, celdaAncho = ((S.ymax - S.ymin) / (ny - 1)) * A;
  const prof = dCol(0) + celdaAlto / 2;
  const medio = A / 2, penal = 11;
  const tope = Math.asin(Math.sqrt(9.15 ** 2 - (16.5 - penal) ** 2) / 9.15);
  const arco = Array.from({ length: 61 }, (_, i) => {
    const a = -tope + (2 * tope * i) / 60;
    return `${medio + 9.15 * Math.sin(a)},${penal + 9.15 * Math.cos(a)}`;
  }).join(" ");
  const trazo = { fill: "none", vectorEffect: "non-scaling-stroke" };
  const vb = { x: -1, y: -3.2, w: A + 2, h: prof + 3.2 + 1 };

  const alMover = (e) => {
    const svg = svgRef.current;
    const pt = svg.createSVGPoint();
    pt.x = e.clientX; pt.y = e.clientY;
    const mt = svg.getScreenCTM();
    if (!mt || !rej) return;
    const p = pt.matrixTransform(mt.inverse());
    const r = Math.round((p.x / A - S.ymin) / (S.ymax - S.ymin) * (ny - 1));
    const d0 = dCol(0), dN = dCol(nx - 1);
    const c = Math.round(((d0 - p.y) / (d0 - dN)) * (nx - 1));
    setCel(r >= 0 && r < ny && c >= 0 && c < nx ? { r, c, px: e.clientX, py: e.clientY } : null);
  };

  const valores = rej || [];
  const vmax = S.vmax;
  let max = 0, imax = -1;
  valores.forEach((v, i) => { if (v != null && v > max) { max = v; imax = i; } });
  const lectura = imax >= 0
    ? `En esta combinación, lo más valioso del mapa es ${max.toFixed(2)} de xG, a ${Math.round(Math.hypot(dCol(imax % nx), wFila(Math.floor(imax / nx)) - medio))} m del centro de la portería.`
    : "Con estos controles no hay suficientes tiros en ninguna zona para sostener una predicción.";
  const sobre = cel && rej ? rej[cel.r * nx + cel.c] : null;

  return (
    <Box>
      <Cabecera cfg={cfg} />
      <Box sx={{ display: "grid", gap: 3, gridTemplateColumns: { xs: "minmax(0,1fr)", md: "minmax(0,1fr) 250px" }, alignItems: "start" }}>
        <Box sx={{ minWidth: 0 }}>
          <Box className="rx-chart" sx={{ display: "flex", flexDirection: { xs: "column", sm: "row" }, gap: 2, position: "relative" }}>
            <Box sx={{ flex: 1, minWidth: 0, maxWidth: 640 }}>
              <svg ref={svgRef} role="img" aria-label={cfg.alt} viewBox={`${vb.x} ${vb.y} ${vb.w} ${vb.h}`}
                style={{ width: "100%", height: "auto", display: "block", touchAction: "pan-y" }}
                onPointerMove={alMover} onPointerDown={alMover} onPointerLeave={() => setCel(null)}>
                <rect x={0} y={0} width={A} height={prof} fill={conAlfa(rampa[0], 0.22)} />
                {valores.map((v, i) => {
                  if (v == null) return null;
                  const r = Math.floor(i / nx), c = i % nx;
                  return <rect key={i} data-celda="1" x={wFila(r) - celdaAncho / 2} y={dCol(c) - celdaAlto / 2}
                    width={celdaAncho} height={celdaAlto} fill={colorRampa(v / vmax)} shapeRendering="crispEdges" />;
                })}
                {cel && (
                  <rect x={wFila(cel.r) - celdaAncho / 2} y={dCol(cel.c) - celdaAlto / 2} width={celdaAncho} height={celdaAlto}
                    fill="none" stroke={tk.primary} strokeWidth={2} vectorEffect="non-scaling-stroke" />
                )}
                {[0, 1].map((capa) => {
                  const e = capa === 0 ? { stroke: "rgba(11,11,11,.45)", strokeWidth: 3.4 } : { stroke: "rgba(252,252,251,.92)", strokeWidth: 1.5 };
                  return (
                    <g key={capa} {...trazo} {...e} pointerEvents="none">
                      <rect x={medio - 20.16} y={0} width={40.32} height={16.5} {...trazo} {...e} />
                      <rect x={medio - 9.16} y={0} width={18.32} height={5.5} {...trazo} {...e} />
                      <polyline points={arco} {...trazo} {...e} />
                      <circle cx={medio} cy={penal} r={0.4} fill={e.stroke} stroke="none" />
                    </g>
                  );
                })}
                <rect x={medio - 3.66} y={-1.2} width={7.32} height={1.2} fill="none" stroke={tk.muted} strokeWidth={1.6}
                  vectorEffect="non-scaling-stroke" />
              </svg>
              {cel && (
                <Paper elevation={4} className="rx-tooltip"
                  sx={{ position: "fixed", left: cel.px + 14, top: cel.py + 14, p: 1.1, pointerEvents: "none", zIndex: 1500,
                    border: 1, borderColor: "divider", fontSize: 12.5 }}>
                  <Box sx={{ color: "text.secondary", mb: 0.25 }}>
                    a {Math.round(Math.hypot(dCol(cel.c), wFila(cel.r) - medio))} m de la portería
                  </Box>
                  <Box>{sobre == null ? <span>sin tiros suficientes para opinar</span> : <><strong>xG {sobre.toFixed(2)}</strong></>}</Box>
                </Paper>
              )}
            </Box>
            <Box sx={{ width: { xs: "100%", sm: 56 }, flex: "none", display: "flex", flexDirection: "column", alignItems: "flex-start" }}>
              <Typography sx={{ fontSize: 11.5, fontWeight: 600, color: "text.secondary", mb: 0.5 }}>xG</Typography>
              <Box sx={{ display: "flex", flexDirection: { xs: "column", sm: "row" }, gap: 0.75, flex: 1, width: "100%", minHeight: { sm: 150 }, maxHeight: { sm: 260 } }}>
                <Box sx={{ width: { xs: "100%", sm: 12 }, height: { xs: 10, sm: "auto" }, borderRadius: 1, border: 1, borderColor: "divider",
                  background: `linear-gradient(to top, ${rampa.map((c, i) => `${c} ${(i / (rampa.length - 1)) * 100}%`).join(", ")})` }} />
                <Box sx={{ display: "flex", flexDirection: { xs: "row-reverse", sm: "column" }, justifyContent: "space-between", fontSize: 11.5, color: "text.secondary" }}>
                  <span>{vmax.toFixed(2)}</span><span>0</span>
                </Box>
              </Box>
            </Box>
          </Box>
          <Typography sx={{ fontSize: 12.5, mt: 1, fontWeight: 600 }} aria-live="polite">{lectura}</Typography>
          <Pie cfg={cfg} extra="Las zonas sin color no tienen tiros suficientes para que el modelo opine." />
        </Box>

        <Box sx={{ display: "flex", flexDirection: "column", gap: 2, order: { xs: -1, md: 0 } }}>
          <Box>
            <Rotulo>Situación</Rotulo>
            <ToggleButtonGroup exclusive size="small" fullWidth orientation="vertical" value={sit} aria-label="Situación"
              onChange={(_e, v) => v && setSit(v)}>
              {S.situaciones.map((s) => <ToggleButton key={s.id} value={s.id}>{s.etiqueta}</ToggleButton>)}
            </ToggleButtonGroup>
          </Box>
          <Box>
            <Rotulo>Parte del cuerpo</Rotulo>
            <ToggleButtonGroup exclusive size="small" fullWidth value={parte} aria-label="Parte del cuerpo"
              onChange={(_e, v) => v && setParte(v)} sx={{ flexWrap: "wrap" }}>
              {S.partes.map((p) => <ToggleButton key={p.id} value={p.id} sx={{ flex: "1 0 30%" }}>{p.etiqueta}</ToggleButton>)}
            </ToggleButtonGroup>
          </Box>
          <Box sx={{ opacity: usaAccion ? 1 : 0.45 }}>
            <Rotulo ayuda="Lo último que pasó antes del tiro, según Understat. Solo se puede elegir en jugada abierta: en córners y balón parado la acción previa es siempre la misma.">
              Acción previa
            </Rotulo>
            <ToggleButtonGroup exclusive size="small" fullWidth orientation="vertical" value={accion} aria-label="Acción previa"
              disabled={!usaAccion} onChange={(_e, v) => v && setAccion(v)}>
              {S.acciones.map((a) => <ToggleButton key={a.id} value={a.id}>{a.etiqueta}</ToggleButton>)}
            </ToggleButtonGroup>
          </Box>
        </Box>
      </Box>
    </Box>
  );
}


// --- puntos: un valor por fila, con selector de métrica ----------------------------------------------
// Para comparar modelos en métricas cuyo cero no significa nada (log-loss, AUC): una barra desde cero
// regalaría el 90% de su largo a una diferencia de milésimas. Un punto por modelo, sobre un eje que
// empieza donde empiezan los datos, y una línea punteada en la referencia.
// G: { agrupaciones: [{id, etiqueta, eje: {dom, formato, etiqueta}, ref?: {valor, etiqueta},
//      filas: [{nombre, nota?, valor, texto, tono?: "propio"|"understat"|"neutro", destacado?}]}] }
function Puntos({ cfg, D, tk, pal }) {
  const G = D[cfg.dato];
  const [agr, setAgr] = useState(G.agrupaciones[0].id);
  const [ref, ancho] = useAncho();
  const [sel, setSel] = useState(null);
  const g = G.agrupaciones.find((a) => a.id === agr) || G.agrupaciones[0];
  const [d0, d1] = g.eje.dom;
  const w = Math.max(60, ancho);
  const px = lineal(d0, d1, 10, w - 10);
  const marcasX = marcas(d0, d1, Math.max(3, Math.round(w / 90)));
  const fx = fm(g.eje.formato);
  const alto = 40;
  const tono = (t) => (t === "propio" ? pal.propio : t === "understat" ? pal.understat : tk.muted);
  return (
    <Box>
      <Cabecera cfg={cfg} />
      {G.agrupaciones.length > 1 && (
        <Box sx={{ mb: 1.25 }}>
          <Rotulo>{G.rotulo || "Métrica"}</Rotulo>
          <ToggleButtonGroup exclusive size="small" value={agr} aria-label="Métrica"
            onChange={(_e, v) => v && setAgr(v)} sx={{ flexWrap: "wrap" }}>
            {G.agrupaciones.map((a) => <ToggleButton key={a.id} value={a.id}>{a.etiqueta}</ToggleButton>)}
          </ToggleButtonGroup>
        </Box>
      )}
      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "minmax(110px, 1fr) minmax(0, 1.3fr) auto", sm: "minmax(190px, 1fr) minmax(0, 1.7fr) auto" },
        columnGap: 1.5, alignItems: "center" }}>
        <Box />
        <Box ref={ref} sx={{ height: 24 }}>
          {ancho > 0 && (
            <svg width={w} height={24} aria-hidden="true" style={{ display: "block" }}>
              {marcasX.map((v) => <text key={v} x={px(v)} y={16} textAnchor="middle" {...estiloTexto(tk)}>{fx(v)}</text>)}
            </svg>
          )}
        </Box>
        <Box />
        {g.filas.map((f, i) => {
          const activo = sel === i;
          return (
            <Box key={`${agr}-${i}`} sx={{ display: "contents" }} onMouseEnter={() => setSel(i)} onMouseLeave={() => setSel(null)}>
              <Box sx={{ py: 0.5, pr: 1, borderTop: 1, borderColor: "divider", bgcolor: activo ? "action.hover" : "transparent",
                fontSize: 13, lineHeight: 1.3, fontWeight: f.destacado ? 700 : 500, height: alto, display: "flex",
                flexDirection: "column", justifyContent: "center" }}>
                <span>{f.nombre}</span>
                {f.nota && <Box component="span" sx={{ fontSize: 11.5, color: "text.secondary", fontWeight: 400 }}>{f.nota}</Box>}
              </Box>
              <Box sx={{ borderTop: 1, borderColor: "divider", bgcolor: activo ? "action.hover" : "transparent", height: alto }}>
                {ancho > 0 && (
                  <svg width={w} height={alto} role="img" aria-label={`${f.nombre}: ${f.texto}`} style={{ display: "block" }}>
                    {marcasX.map((v) => <line key={v} x1={px(v)} x2={px(v)} y1={0} y2={alto} stroke={tk.border} strokeOpacity={0.6} />)}
                    {g.ref && (
                      <line x1={px(g.ref.valor)} x2={px(g.ref.valor)} y1={0} y2={alto}
                        stroke={g.ref.tono === "understat" ? pal.understat : tk.muted} strokeWidth={1.4} strokeDasharray="3 3" />
                    )}
                    <line x1={10} x2={px(f.valor)} y1={alto / 2} y2={alto / 2} stroke={tono(f.tono)} strokeOpacity={0.35} strokeWidth={2} />
                    <circle cx={px(f.valor)} cy={alto / 2} r={activo || f.destacado ? 8 : 6.5} fill={tono(f.tono)} stroke={tk.surface} strokeWidth={1.5} />
                  </svg>
                )}
              </Box>
              <Box sx={{ borderTop: 1, borderColor: "divider", bgcolor: activo ? "action.hover" : "transparent", height: alto,
                display: "flex", alignItems: "center", justifyContent: "flex-end", fontSize: 13, fontWeight: 700, whiteSpace: "nowrap", pl: 0.5 }}>
                {f.texto}
              </Box>
            </Box>
          );
        })}
      </Box>
      <Typography sx={{ fontSize: 12.5, fontWeight: 600, textAlign: "center", mt: 0.75 }}>{g.eje.etiqueta}</Typography>
      {g.ref && (
        <Typography sx={{ fontSize: 11.5, color: "text.secondary", mt: 0.25, textAlign: "center" }}>
          <Box component="span" sx={{ color: g.ref.tono === "understat" ? pal.understat : "text.secondary", fontWeight: 700 }}>┆</Box> {g.ref.etiqueta}
        </Typography>
      )}
      <Pie cfg={cfg} />
    </Box>
  );
}

// --- ventanas: cómo se parte el tiempo para validar -----------------------------------------------------
// G: { temporadas: [...], filas: [{prueba: i, valida: i, entrena: [i...], final?: bool}] }
function Ventanas({ cfg, D, tk, pal }) {
  const G = D[cfg.dato];
  const [ref, ancho] = useAncho();
  const angosto = ancho > 0 && ancho < 520;
  const rotulo = angosto ? 82 : 150;
  const w = Math.max(200, ancho);
  const n = G.temporadas.length;
  const celda = (w - rotulo) / n;
  const alto = 26, cab = 22;
  const color_ = (rol) => (rol === "entrena" ? pal.propio : rol === "valida" ? pal.aviso : rol === "prueba" ? pal.acento : null);
  const series = [
    { id: "e", nombre: "Entrena", color: "propio" }, { id: "v", nombre: "Decide cuántos árboles", color: "aviso" },
    { id: "p", nombre: "Prueba (el modelo no la ve)", color: "acento" },
  ];
  return (
    <Box ref={ref}>
      <Cabecera cfg={cfg} />
      <Leyenda series={series} ocultas={{}} onToggle={() => {}} pal={pal} fija />
      {ancho > 0 && (
        <svg width={w} height={cab + G.filas.length * alto + 4} role="img" aria-label={cfg.alt} style={{ display: "block" }}>
          {G.temporadas.map((t, j) => (
            <text key={t} x={rotulo + j * celda + celda / 2} y={14} textAnchor="middle" {...estiloTexto(tk)}
              fontSize={angosto ? 9.5 : 11}>{angosto ? t.slice(2, 4) : t.replace(/^20/, "")}</text>
          ))}
          {G.filas.map((f, i) => {
            const y = cab + i * alto;
            return (
              <g key={f.prueba}>
                <text x={rotulo - 8} y={y + alto / 2} dy="0.34em" textAnchor="end" fontSize={12.5}
                  fontWeight={f.final ? 800 : 600} fill={tk["text-body"]}>
                  {angosto ? G.temporadas[f.prueba].replace(/^20/, "") : `Probar en ${G.temporadas[f.prueba]}`}
                </text>
                {G.temporadas.map((t, j) => {
                  const rol = j === f.prueba ? "prueba" : j === f.valida ? "valida" : f.entrena.includes(j) ? "entrena" : null;
                  const c = color_(rol);
                  return (
                    <rect key={t} x={rotulo + j * celda + 1.5} y={y + 2} width={Math.max(2, celda - 3)} height={alto - 4} rx={4}
                      fill={c || tk.border} fillOpacity={c ? 0.95 : 0.35}
                      stroke={f.final && c ? tk.primary : "none"} strokeWidth={f.final ? 1.5 : 0} />
                  );
                })}
              </g>
            );
          })}
        </svg>
      )}
      <Pie cfg={cfg} />
    </Box>
  );
}

// --- apiladas: columnas por temporada, con la liga como color ------------------------------------------------
// Tocar el nombre de una liga la quita o la devuelve; las columnas se acomodan con una transición, y entran
// creciendo la primera vez que la gráfica se ve en pantalla.
// G: { temporadas: [...], ligas: [{id, nombre, color, colorOscuro}], valores: {id: [n por temporada]} }
function Apiladas({ cfg, D, tk, pal, modo }) {
  const G = D[cfg.dato];
  const [ocultas, setOcultas] = useState({});
  const [listo, setListo] = useState(false);
  const [ref, ancho] = useAncho();
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof IntersectionObserver === "undefined") { setListo(true); return undefined; }
    const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) { setListo(true); io.disconnect(); } }, { threshold: 0.25 });
    io.observe(el);
    return () => io.disconnect();
  }, [ref]);
  const n = G.temporadas.length;
  const angosto = ancho > 0 && ancho < 520;
  const colorL = (l) => (modo === "dark" && l.colorOscuro ? l.colorOscuro : l.color);
  const visibles = G.ligas.filter((l) => !ocultas[l.id]);
  const totales = G.temporadas.map((_, i) => G.ligas.reduce((a, l) => a + G.valores[l.id][i], 0));
  const tope = Math.max(...totales) * 1.06;
  const series = G.ligas.map((l) => ({ id: l.id, nombre: l.nombre, color: colorL(l) }));
  const x = {
    dom: [0, n], marcas: G.temporadas.map((_, i) => i + 0.5).filter((_, i) => !angosto || i % 2 === 0),
    valor: (v) => (angosto ? G.temporadas[Math.floor(v)].slice(2) : G.temporadas[Math.floor(v)]),
  };
  const y = { dom: [0, tope], formato: "miles", etiqueta: "Tiros" };
  const render = ({ px, py, w, hover }) => {
    const slot = w / n, ancha = slot * 0.68;
    const i = hover ? Math.floor(hover.cx / slot) : -1;
    const nodos = G.temporadas.map((t, k) => {
      let acum = 0;
      return (
        <g key={t} opacity={i >= 0 && i !== k ? 0.55 : 1} style={{ transition: "opacity .2s" }}>
          {G.ligas.map((l) => {
            const v = ocultas[l.id] ? 0 : G.valores[l.id][k];
            const y0 = acum;
            acum += v;
            const alto = listo ? py(y0) - py(y0 + v) : 0;
            const yy = listo ? py(y0 + v) : py(0);
            return (
              <rect key={l.id} x={px(k + 0.5) - ancha / 2} width={ancha} y={yy} height={Math.max(0, alto)} fill={colorL(l)}
                style={{ y: yy, height: Math.max(0, alto), transition: "y .55s cubic-bezier(.2,.7,.2,1), height .55s cubic-bezier(.2,.7,.2,1)",
                  transitionDelay: listo ? `${k * 25}ms` : "0ms" }}
                stroke={tk.surface} strokeWidth={0.6} />
            );
          })}
        </g>
      );
    });
    const tip = i >= 0 && i < n && (
      <>
        <Typography sx={{ fontWeight: 700, fontSize: 12.5, mb: 0.5 }}>{G.temporadas[i]}</Typography>
        {[...visibles].reverse().map((l) => <Fila key={l.id} c={colorL(l)} nombre={l.nombre} valor={miles(G.valores[l.id][i])} />)}
        <Fila nombre="Total" valor={miles(visibles.reduce((a, l) => a + G.valores[l.id][i], 0))} fuerte />
      </>
    );
    return { nodos, tip };
  };
  return (
    <Box ref={ref}>
      <Cabecera cfg={cfg} />
      <Leyenda series={series} ocultas={ocultas} pal={pal}
        onToggle={(id) => setOcultas((o) => ({ ...o, [id]: !o[id] }))} />
      <Marco alto={cfg.alto || (angosto ? 320 : 380)} x={x} y={y} tk={tk} aria={cfg.alt} render={render} />
      <Pie cfg={cfg} extra={cfg.ayuda} />
    </Box>
  );
}

// --- mapa: la media cancha vista de varias maneras --------------------------------------------------------
// Tres lecturas por celda de lo mismo (tiros, tasa de gol, xG de Understat) y dos por zonas alrededor de la
// portería: círculos de distancia y curvas de ángulo (el lugar de los puntos desde donde la portería se ve
// con el mismo ángulo es un círculo que pasa por los dos postes), con la tasa de gol de cada zona para el pie
// y para la cabeza.
// S: { nx, ny, xmin, xmax, ymin, ymax, largo, ancho, metricas: {id: [...]}, bandas: {distancia: [...], angulo: [...]},
//      opciones: [{id, etiqueta, formato, tope, raiz?, unidad, tipo?: "bandas"}], rampa }
// banda: { desde, hasta, todos: {n, tasa}, pie: {n, tasa}, cabeza: {n, tasa} }
const POSTE = 7.32 / 2;
const profundidadAngulo = (grados) => (grados >= 180 ? 0 : POSTE / Math.tan((grados * Math.PI) / 360));

function Mapa({ cfg, D, tk, pal, modo }) {
  const S = D[cfg.dato];
  const [met, setMet] = useState(S.opciones[0].id);
  const [cel, setCel] = useState(null);
  const [zona, setZona] = useState(null);
  const svgRef = useRef(null);
  const [ref, ancho] = useAncho();
  const op = S.opciones.find((o) => o.id === met);
  const esBandas = op.tipo === "bandas";
  const bandas = esBandas ? S.bandas[op.id] : null;
  const vals = esBandas ? null : S.metricas[met];
  const rampa = useMemo(() => (modo === "dark" ? [...S.rampa].reverse() : S.rampa), [S, modo]);
  const hex = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
  const colorRampa = (t) => {
    const x = Math.min(1, Math.max(0, t)) * (rampa.length - 1);
    const i = Math.min(rampa.length - 2, Math.floor(x)), f = x - i;
    const a = hex(rampa[i]), b = hex(rampa[i + 1]);
    return `rgb(${a.map((v, k) => Math.round(v + (b[k] - v) * f)).join(",")})`;
  };
  const { nx, ny, largo, ancho: A } = S;
  const dCol = (c) => (1 - (S.xmin + (S.xmax - S.xmin) * (c / (nx - 1)))) * largo;
  const wFila = (r) => (S.ymin + (S.ymax - S.ymin) * (r / (ny - 1))) * A;
  const celdaAlto = ((S.xmax - S.xmin) / (nx - 1)) * largo, celdaAncho = ((S.ymax - S.ymin) / (ny - 1)) * A;
  const prof = dCol(0) + celdaAlto / 2;
  const medio = A / 2, penal = 11;
  const tope = Math.asin(Math.sqrt(9.15 ** 2 - (16.5 - penal) ** 2) / 9.15);
  const arco = Array.from({ length: 61 }, (_, i) => {
    const a = -tope + (2 * tope * i) / 60;
    return `${medio + 9.15 * Math.sin(a)},${penal + 9.15 * Math.cos(a)}`;
  }).join(" ");
  const trazo = { fill: "none", vectorEffect: "non-scaling-stroke" };
  const vb = { x: -1, y: -3.2, w: A + 2, h: prof + 3.2 + 1 };
  const esc = ancho > 0 ? Math.min(ancho, 640) / vb.w : 9;       // píxeles por metro de cancha
  const fs = (ancho < 480 ? 10.5 : 11.5) / esc;                 // el texto se dibuja en metros: se pasa a píxeles
  const t_ = (v) => {
    const z = Math.min(1, v / op.tope);
    return op.raiz ? Math.sqrt(z) : z;
  };

  // la banda que contiene a un punto de la cancha (x, y en metros: y es la profundidad)
  const bandaDe = (px, py) => {
    if (!bandas || py < 0 || py > prof || px < 0 || px > A) return null;
    if (op.id === "distancia") {
      const d = Math.hypot(px - medio, py);
      return bandas.findIndex((b) => d >= b.desde && d < b.hasta);
    }
    const a = Math.hypot(px - medio + POSTE, py), b = Math.hypot(px - medio - POSTE, py);
    const ang = (Math.acos(Math.min(1, Math.max(-1, (a * a + b * b - 7.32 * 7.32) / (2 * a * b)))) * 180) / Math.PI;
    return bandas.findIndex((z) => ang >= z.desde && ang < z.hasta);
  };
  const alMover = (e) => {
    const svg = svgRef.current;
    const pt = svg.createSVGPoint();
    pt.x = e.clientX; pt.y = e.clientY;
    const mt = svg.getScreenCTM();
    if (!mt) return;
    const p = pt.matrixTransform(mt.inverse());
    if (esBandas) {
      const i = bandaDe(p.x, p.y);
      setZona(i != null && i >= 0 ? { i, px: e.clientX, py: e.clientY } : null);
      return;
    }
    const r = Math.round((p.x / A - S.ymin) / (S.ymax - S.ymin) * (ny - 1));
    const d0 = dCol(0), dN = dCol(nx - 1);
    const c = Math.round(((d0 - p.y) / (d0 - dN)) * (nx - 1));
    setCel(r >= 0 && r < ny && c >= 0 && c < nx ? { r, c, px: e.clientX, py: e.clientY } : null);
  };
  const salir = () => { setCel(null); setZona(null); };
  const sobre = cel ? cel.r * nx + cel.c : null;
  const fmt = fm(op.formato);
  const pct = (v) => `${(v * 100).toFixed(v < 0.1 ? 1 : 0)}%`;
  const tasaTxt = (g) => (g && g.n >= 40 ? pct(g.tasa) : "—");

  // el texto de una banda sobre el eje de la portería, en el centro de la zona
  const etiquetas = bandas && bandas.map((b, i) => {
    let a0, a1;
    if (op.id === "distancia") { a0 = b.desde; a1 = Math.min(b.hasta, prof); }
    else { a0 = profundidadAngulo(b.hasta); a1 = Math.min(profundidadAngulo(b.desde), prof); }
    const yc = (a0 + a1) / 2;
    const halo = { stroke: tk.surface, strokeWidth: fs * 0.32, paintOrder: "stroke", strokeLinejoin: "round", fontWeight: 700, fontSize: fs, textAnchor: "middle", pointerEvents: "none" };
    if (ancho < 480) return <text key={i} x={medio} y={yc} dy="0.34em" fill={tk["text-body"]} {...halo}>{tasaTxt(b.todos)}</text>;
    return (
      <g key={i}>
        <text x={medio} y={yc - fs * 0.62} dy="0.34em" fill={pal.propio} {...halo}>Pie {tasaTxt(b.pie)}</text>
        <text x={medio} y={yc + fs * 0.62} dy="0.34em" fill={pal.aviso} {...halo}>Cabeza {tasaTxt(b.cabeza)}</text>
      </g>
    );
  });

  const zonaDe = zona && bandas ? bandas[zona.i] : null;
  const rotuloZona = zonaDe && (op.id === "distancia"
    ? (zonaDe.hasta >= 60 ? `A más de ${zonaDe.desde} m de la portería` : `A ${zonaDe.desde} a ${zonaDe.hasta} m de la portería`)
    : (zonaDe.hasta >= 180 ? `Portería vista con más de ${zonaDe.desde}°` : `Portería vista con ${zonaDe.desde}° a ${zonaDe.hasta}°`));
  return (
    <Box>
      <Cabecera cfg={cfg} />
      <Box sx={{ mb: 1.25 }}>
        <ToggleButtonGroup exclusive size="small" value={met} aria-label="Qué mostrar"
          onChange={(_e, v) => v && setMet(v)} sx={{ flexWrap: "wrap" }}>
          {S.opciones.map((o) => <ToggleButton key={o.id} value={o.id}>{o.etiqueta}</ToggleButton>)}
        </ToggleButtonGroup>
      </Box>
      <Box className="rx-chart" sx={{ display: "flex", flexDirection: { xs: "column", sm: "row" }, gap: 2, position: "relative" }}>
        <Box ref={ref} sx={{ flex: 1, minWidth: 0, maxWidth: 640 }}>
          <svg ref={svgRef} role="img" aria-label={cfg.alt} viewBox={`${vb.x} ${vb.y} ${vb.w} ${vb.h}`}
            style={{ width: "100%", height: "auto", display: "block", touchAction: "pan-y" }}
            onPointerMove={alMover} onPointerDown={alMover} onPointerLeave={salir}>
            <defs>
              <clipPath id={`recorte-${cfg.titulo.length}`}><rect x={0} y={0} width={A} height={prof} /></clipPath>
            </defs>
            <rect x={0} y={0} width={A} height={prof} fill={conAlfa(rampa[0], 0.22)} />
            {!esBandas && vals.map((v, i) => {
              if (v == null || (met === "tiros" && v === 0)) return null;
              const r = Math.floor(i / nx), c = i % nx;
              return <rect key={i} data-celda="1" x={wFila(r) - celdaAncho / 2} y={dCol(c) - celdaAlto / 2}
                width={celdaAncho} height={celdaAlto} fill={colorRampa(t_(v))} shapeRendering="crispEdges"
                style={{ transition: "fill .45s" }} />;
            })}
            {esBandas && (
              <g clipPath={`url(#recorte-${cfg.titulo.length})`}>
                {op.id === "distancia"
                  ? [...bandas].reverse().map((b) => (
                    <circle key={b.desde} data-celda="1" cx={medio} cy={0} r={Math.min(b.hasta, 120)}
                      fill={colorRampa(b.todos.tasa / op.tope)} stroke={tk.surface} strokeOpacity={0.7} strokeWidth={1}
                      vectorEffect="non-scaling-stroke" style={{ transition: "fill .45s" }} />))
                  : bandas.map((b, i) => {
                    if (i === 0) return <rect key={b.desde} data-celda="1" x={0} y={0} width={A} height={prof} fill={colorRampa(b.todos.tasa / op.tope)} />;
                    const R = POSTE / Math.sin((b.desde * Math.PI) / 180);
                    return <circle key={b.desde} data-celda="1" cx={medio} cy={R * Math.cos((b.desde * Math.PI) / 180)} r={R}
                      fill={colorRampa(b.todos.tasa / op.tope)} stroke={tk.surface} strokeOpacity={0.7} strokeWidth={1}
                      vectorEffect="non-scaling-stroke" />;
                  })}
              </g>
            )}
            {cel && (
              <rect x={wFila(cel.r) - celdaAncho / 2} y={dCol(cel.c) - celdaAlto / 2} width={celdaAncho} height={celdaAlto}
                fill="none" stroke={tk.primary} strokeWidth={2} vectorEffect="non-scaling-stroke" />
            )}
            {[0, 1].map((capa) => {
              const e = capa === 0 ? { stroke: "rgba(11,11,11,.45)", strokeWidth: 3.4 } : { stroke: "rgba(252,252,251,.92)", strokeWidth: 1.5 };
              return (
                <g key={capa} {...trazo} {...e} pointerEvents="none">
                  <rect x={medio - 20.16} y={0} width={40.32} height={16.5} {...trazo} {...e} />
                  <rect x={medio - 9.16} y={0} width={18.32} height={5.5} {...trazo} {...e} />
                  <polyline points={arco} {...trazo} {...e} />
                  <circle cx={medio} cy={penal} r={0.4} fill={e.stroke} stroke="none" />
                </g>
              );
            })}
            <rect x={medio - 3.66} y={-1.2} width={7.32} height={1.2} fill="none" stroke={tk.muted} strokeWidth={1.6}
              vectorEffect="non-scaling-stroke" />
            {esBandas && etiquetas}
          </svg>
          {cel && (
            <Paper elevation={4} className="rx-tooltip"
              sx={{ position: "fixed", left: cel.px + 14, top: cel.py + 14, p: 1.1, pointerEvents: "none", zIndex: 1500,
                border: 1, borderColor: "divider", fontSize: 12.5 }}>
              <Box sx={{ color: "text.secondary", mb: 0.25 }}>
                a {Math.round(Math.hypot(dCol(cel.c), wFila(cel.r) - medio))} m de la portería
              </Box>
              <Box><strong>{miles(S.metricas.tiros[sobre])}</strong> tiros</Box>
              {S.metricas.tasa[sobre] != null && (
                <>
                  <Box><strong>{(S.metricas.tasa[sobre] * 100).toFixed(1)}%</strong> entran</Box>
                  <Box>xG de Understat: <strong>{S.metricas.xg_und[sobre].toFixed(2)}</strong></Box>
                </>
              )}
            </Paper>
          )}
          {zona && zonaDe && (
            <Paper elevation={4} className="rx-tooltip"
              sx={{ position: "fixed", left: zona.px + 14, top: zona.py + 14, p: 1.1, pointerEvents: "none", zIndex: 1500,
                border: 1, borderColor: "divider", fontSize: 12.5 }}>
              <Box sx={{ color: "text.secondary", mb: 0.25 }}>{rotuloZona}</Box>
              <Box><strong>{pct(zonaDe.todos.tasa)}</strong> de {miles(zonaDe.todos.n)} tiros</Box>
              <Box sx={{ color: pal.propio }}>Pie: <strong>{tasaTxt(zonaDe.pie)}</strong> · {miles(zonaDe.pie.n)} tiros</Box>
              <Box sx={{ color: pal.aviso }}>Cabeza: <strong>{tasaTxt(zonaDe.cabeza)}</strong> · {miles(zonaDe.cabeza.n)} tiros</Box>
            </Paper>
          )}
        </Box>
        <Box sx={{ width: { xs: "100%", sm: 64 }, flex: "none", display: "flex", flexDirection: "column", alignItems: "flex-start" }}>
          <Typography sx={{ fontSize: 11.5, fontWeight: 600, color: "text.secondary", mb: 0.5 }}>{op.unidad}</Typography>
          <Box sx={{ display: "flex", flexDirection: { xs: "column", sm: "row" }, gap: 0.75, flex: 1, width: "100%", minHeight: { sm: 150 }, maxHeight: { sm: 260 } }}>
            <Box sx={{ width: { xs: "100%", sm: 12 }, height: { xs: 10, sm: "auto" }, borderRadius: 1, border: 1, borderColor: "divider",
              background: `linear-gradient(to top, ${rampa.map((c, i) => `${c} ${(i / (rampa.length - 1)) * 100}%`).join(", ")})` }} />
            <Box sx={{ display: "flex", flexDirection: { xs: "row-reverse", sm: "column" }, justifyContent: "space-between", fontSize: 11.5, color: "text.secondary" }}>
              <span>{fmt(op.tope)}{op.raiz ? "+" : ""}</span><span>0</span>
            </Box>
          </Box>
        </Box>
      </Box>
      <Pie cfg={cfg} extra={cfg.ayuda} />
    </Box>
  );
}

// --- entrada -------------------------------------------------------------------------------------

const GRAFICAS = { lineas: Lineas, forest: Forest, barras: Barras, dispersion: Dispersion, superficie: Superficie,
  arbol: Arbol, puntos: Puntos, ventanas: Ventanas, mapa: Mapa, apiladas: Apiladas };

export default function ArticuloVista({ id }) {
  const cfg = window.futvizVistas[id];
  const { theme, modo, t } = useSitioTema();
  const { D, error } = useDatos(cfg.tabla || "xg");
  const G = GRAFICAS[cfg.grafica];
  const pal = useMemo(() => paletaDe(modo, t), [modo, t]);
  // el explorador pide una tabla por temporada, cuando el lector la elige
  if (cfg.grafica === "explorador") {
    return (
      <ThemeProvider theme={theme}>
        <Explorador cfg={cfg} tk={t} pal={pal} modo={modo} />
      </ThemeProvider>
    );
  }
  return (
    <ThemeProvider theme={theme}>
      {!G ? <Aviso>Tipo de gráfica desconocido: {cfg.grafica}</Aviso>
        : error ? <Aviso>No se pudieron cargar los datos de esta gráfica.</Aviso>
          : !D ? <Cargando alto={cfg.alto || 380} />
            : <G cfg={cfg} D={D} tk={t} pal={pal} modo={modo} />}
    </ThemeProvider>
  );
}
