// Edad: dos paneles que comparten el eje de la edad (17 a 38 años).
//
//  1. Minutos por edad: mediana y rango típico (percentil 25 a 75) del % de los minutos de su club que jugó cada
//     jugador-temporada, con barras que cuentan cuántos hay en cada edad.
//  2. Rendimiento por edad, por el método del cambio de un año al siguiente: la curva relativa al nivel a los 22 años
//     (= 100) con su intervalo de bootstrap. Delantero y Medio comparten métrica; Defensa tiene la suya; Portero no entra.
//
// Todo el cálculo está hecho en el build (`web/charts/edad.py`): aquí solo se dibuja lo que viaja en `datos-edad.js`.
// SVG propio, en el mismo lenguaje que el resto de las gráficas (rejilla suave, ejes en gris, números en el hover).
import { useEffect, useMemo, useRef, useState } from "react";
import { ThemeProvider } from "@mui/material/styles";
import Box from "@mui/material/Box";
import Paper from "@mui/material/Paper";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import Typography from "@mui/material/Typography";
import { entre, leerParams, usePublicarParams } from "./urlEstado.js";
import { useSitioTema } from "./theme.jsx";
import { cargarDatos } from "./datos.js";
import { Aviso, Cargando, Encabezado, Md, Parrafos, Rotulo } from "./ui.jsx";
import { conAlfa } from "./colores.js";
import { lecturaEdad } from "./edadLectura.js";
import { miles } from "./stats.js";

const MG = { l: 46, r: 12, t: 10 };       // márgenes de los dos SVG (los mismos: el eje X se alinea)
const ALTO1 = 200, ALTO_BARRAS = 36, ALTO2 = 240, ALTO_EJE = 24;
const r0 = (x) => Math.round(x);

// Edades consecutivas -> tramos [i, j] de índices: una edad sin dato (menos de 30) corta la línea en vez de unirla.
function tramos(edades) {
  const out = [];
  let ini = 0;
  for (let i = 1; i <= edades.length; i++) {
    if (i === edades.length || edades[i] !== edades[i - 1] + 1) { out.push([ini, i - 1]); ini = i; }
  }
  return out;
}

// Marcas "bonitas" del eje Y.
function marcas(min, max, n = 5) {
  const crudo = (max - min) / Math.max(1, n - 1);
  const pot = 10 ** Math.floor(Math.log10(crudo));
  const paso = [1, 2, 2.5, 5, 10].map((k) => k * pot).find((p) => p >= crudo) || 10 * pot;
  const out = [];
  // de la marca por debajo del mínimo a la primera por encima del máximo: las marcas cubren todos los datos
  for (let v = Math.floor(min / paso) * paso; ; v += paso) {
    out.push(Math.round(v * 1e6) / 1e6);
    if (v >= max - paso * 1e-6) break;
  }
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

// Eje X compartido: marcas cada año y números cada `paso` años, según el ancho que haya por edad.
function EjeX({ geo, tk, y }) {
  const { a0, a1, cx, banda } = geo;
  const paso = banda >= 28 ? 1 : banda >= 16 ? 2 : 5;
  const etiquetas = [];
  for (let a = a0; a <= a1; a++) if (a % paso === 0) etiquetas.push(a);
  return (
    <g fontSize={11} fill={tk.muted}>
      {Array.from({ length: a1 - a0 + 1 }, (_, i) => a0 + i).map((a) => (
        <line key={a} x1={cx(a)} x2={cx(a)} y1={y} y2={y + 4} stroke={tk.muted} strokeOpacity={0.6} />
      ))}
      {etiquetas.map((a) => <text key={a} x={cx(a)} y={y + 17} textAnchor="middle">{a}</text>)}
    </g>
  );
}

function Rejilla({ geo, tk, y, marcasY, fmt }) {
  return (
    <g fontSize={11} fill={tk.muted}>
      {marcasY.map((v) => (
        <g key={v}>
          <line x1={geo.l} x2={geo.l + geo.pw} y1={y(v)} y2={y(v)} stroke={tk.border} strokeOpacity={0.8} />
          <text x={geo.l - 6} y={y(v) + 4} textAnchor="end">{fmt(v)}</text>
        </g>
      ))}
    </g>
  );
}

function Vista({ cfg, D, modo, tk }) {
  const [P] = useState(() => leerParams(cfg.id));
  const ids = cfg.posiciones.map((p) => p.id);
  const [pos, setPos] = useState(() => entre(P.get("pos"), ids, ids[0]));
  usePublicarParams(cfg.id, { pos: pos === ids[0] ? null : pos });
  const [hover, setHover] = useState(null);       // {a, px, py}
  const caja = useRef(null);
  const w = useAncho(caja);

  const etiqueta = cfg.posiciones.find((p) => p.id === pos).etiqueta;
  const [a0, a1] = D.edades;
  const nEd = a1 - a0 + 1;
  const pw = Math.max(80, w - MG.l - MG.r);
  const banda = pw / nEd;
  const geo = { a0, a1, pw, banda, l: MG.l, cx: (a) => MG.l + (a - a0 + 0.5) * banda };

  const M = D.minutos[pos];
  const posRend = pos === "campo" ? ["Defensa", "Medio", "Delantero"] : pos === "Portero" ? [] : [pos];
  const curvas = posRend.map((p) => ({ pos: p, r: D.rendimiento[p] })).filter((c) => c.r);
  const lectura = useMemo(() => lecturaEdad(D, pos, etiqueta, ["campo", "Defensa", "Medio", "Delantero"]), [D, pos, etiqueta]);
  const multiple = curvas.length > 1;
  const colorDe = (p) => (multiple ? D.coloresPos[p] : tk.primary);

  // --- panel 1 ---
  const y1 = (v) => MG.t + ALTO1 * (1 - v / 100);
  const baseBarras = MG.t + ALTO1 + 12 + ALTO_BARRAS;
  const nmax = Math.max(1, ...M.n);
  const alto1 = baseBarras + ALTO_EJE;

  // --- panel 2 ---
  const todos = curvas.flatMap((c) => [...c.r.lo, ...c.r.hi, 100]);
  const dom = todos.length ? [Math.min(...todos), Math.max(...todos)] : [90, 110];
  const margen = (dom[1] - dom[0]) * 0.06;
  const ticks2 = marcas(dom[0] - margen, dom[1] + margen, 5);
  const d2 = [ticks2[0], ticks2[ticks2.length - 1]];
  const y2 = (v) => MG.t + ALTO2 * (1 - (v - d2[0]) / (d2[1] - d2[0]));
  const alto2 = MG.t + ALTO2 + ALTO_EJE;

  const edadDe = (e) => {
    const r = e.currentTarget.getBoundingClientRect();
    const a = a0 + Math.floor((e.clientX - r.left - MG.l) / banda);
    return a < a0 || a > a1 ? null : a;
  };
  const mover = (e) => {
    const a = edadDe(e);
    setHover(a == null ? null : { a, px: e.clientX, py: e.clientY });
  };
  const salir = (e) => { if (e.pointerType === "mouse") setHover(null); };
  const manejadores = { onPointerMove: mover, onPointerDown: mover, onPointerLeave: salir, style: { display: "block", touchAction: "pan-y" } };

  const columna = (a, alto) => (
    <rect x={MG.l + (a - a0) * banda} y={MG.t} width={banda} height={alto} fill={conAlfa(tk.primary, 0.08)} pointerEvents="none" />
  );

  // --- el tooltip ---
  const idx = hover ? M.e.indexOf(hover.a) : -1;
  const tip = hover && (
    <Paper elevation={4} className="rx-tooltip" sx={{
      position: "fixed", left: Math.max(8, Math.min(hover.px + 14, window.innerWidth - 250)), top: hover.py + 14,
      p: 1.25, pointerEvents: "none", zIndex: 1500, border: 1, borderColor: "divider", fontSize: 12.5, width: 236,
    }}>
      <Box sx={{ fontWeight: 700, mb: 0.5 }}>{hover.a} años</Box>
      <Box sx={{ color: "text.secondary", fontSize: 11.5 }}>Minutos · {etiqueta.toLowerCase()}</Box>
      {idx >= 0 ? (
        <>
          <Box><strong>Mediana {r0(M.med[idx])}%</strong> de los minutos de su club</Box>
          <Box sx={{ color: "text.secondary" }}>Rango típico {r0(M.p25[idx])} a {r0(M.p75[idx])}% · {miles(M.n[idx])} jugador-temporadas</Box>
        </>
      ) : (
        <Box sx={{ color: "text.secondary" }}>Menos de {D.minJugadores} jugador-temporadas: no se dibuja.</Box>
      )}
      {curvas.length > 0 && <Box sx={{ color: "text.secondary", fontSize: 11.5, mt: 0.75 }}>Rendimiento · {curvas[0].r.metrica}{multiple ? " (cada posición con la suya)" : ""}</Box>}
      {curvas.map((c) => {
        const k = c.r.e.indexOf(hover.a);
        return (
          <Box key={c.pos}>
            {k < 0 ? <Box sx={{ color: "text.secondary" }}>{multiple ? `${c.pos}: ` : ""}sin curva a esta edad (pocos pares)</Box> : (
              <>
                <Box>{multiple && <strong>{c.pos}: </strong>}<strong>{c.r.curva[k].toFixed(1)}</strong> (franja {r0(c.r.lo[k])} a {r0(c.r.hi[k])})</Box>
                <Box sx={{ color: "text.secondary" }}>
                  {k === 0 ? "Punto de partida de la cadena" : `${miles(c.r.pares[k - 1])} pares de ${hover.a - 1} a ${hover.a}`}
                </Box>
              </>
            )}
          </Box>
        );
      })}
    </Paper>
  );

  const resumen1 = M.e.length
    ? `Mediana del porcentaje de minutos jugados por edad, ${etiqueta.toLowerCase()}: de ${r0(M.med[0])}% a los ${M.e[0]} años a ${r0(M.med[M.e.length - 1])}% a los ${M.e[M.e.length - 1]}, con el máximo de ${r0(Math.max(...M.med))}% a los ${M.e[M.med.indexOf(Math.max(...M.med))]} años.`
    : "Sin edades con suficientes jugadores.";
  const resumen2 = curvas.map((c) => {
    const k = c.r.e.indexOf(c.r.pico);
    return `${c.pos}: la curva llega a ${c.r.curva[k].toFixed(0)} a los ${c.r.pico} años, contra 100 a los ${c.r.ancla}.`;
  }).join(" ");

  return (
    <>
      <Encabezado pregunta={cfg.pregunta} titulo={cfg.titulo} bajada={cfg.bajada} />

      <Box sx={{ mb: 2, maxWidth: 760 }}>
        <Rotulo>Posición</Rotulo>
        <ToggleButtonGroup exclusive size="small" value={pos} aria-label="Posición" sx={{ flexWrap: "wrap" }}
          onChange={(_e, v) => { if (v) { setPos(v); setHover(null); } }}>
          {cfg.posiciones.map((p) => (
            <ToggleButton key={p.id} value={p.id} sx={{ flex: "1 1 auto" }}>{p.etiqueta}</ToggleButton>
          ))}
        </ToggleButtonGroup>
        {pos === "campo" && (
          <Typography sx={{ fontSize: 11.5, color: "text.secondary", mt: 0.5 }}>
            Defensa, Medio y Delantero. Los porteros se miran aparte: casi todos juegan el 100% de los minutos o casi nada.
          </Typography>
        )}
      </Box>

      <Box ref={caja} sx={{ maxWidth: 1000, width: "100%", position: "relative" }}>
        {w > 0 && (
          <>
            {/* panel 1: minutos */}
            <Typography component="h3" sx={{ fontSize: 13.5, fontWeight: 700, mb: 0.25 }}>
              Minutos jugados <Box component="span" sx={{ fontWeight: 500, color: "text.secondary" }}>· % de los minutos de su club</Box>
            </Typography>
            <svg role="img" aria-label={`${resumen1} Barras debajo: jugador-temporadas por edad.`} width={w} height={alto1} {...manejadores}>
              <Rejilla geo={geo} tk={tk} y={y1} marcasY={[0, 25, 50, 75, 100]} fmt={(v) => `${v}%`} />
              {hover && columna(hover.a, ALTO1 + 12 + ALTO_BARRAS)}
              {tramos(M.e).map(([i, j], k) => {
                const idxs = Array.from({ length: j - i + 1 }, (_, q) => i + q);
                const arriba = idxs.map((q) => `${geo.cx(M.e[q])},${y1(M.p75[q])}`);
                const abajo = idxs.map((q) => `${geo.cx(M.e[q])},${y1(M.p25[q])}`).reverse();
                const linea = idxs.map((q) => `${geo.cx(M.e[q])},${y1(M.med[q])}`).join(" ");
                return (
                  <g key={k}>
                    {idxs.length > 1 && <polygon points={[...arriba, ...abajo].join(" ")} fill={conAlfa(tk.primary, modo === "dark" ? 0.28 : 0.2)} />}
                    <polyline points={linea} fill="none" stroke={tk.primary} strokeWidth={2.2} strokeLinejoin="round" />
                  </g>
                );
              })}
              {M.e.map((a, q) => <circle key={a} cx={geo.cx(a)} cy={y1(M.med[q])} r={hover && hover.a === a ? 4.5 : 2.6} fill={tk.primary} stroke={tk.surface} strokeWidth={1} />)}
              {/* las barras de n: discretas, en el color del texto atenuado */}
              <g>
                <line x1={MG.l} x2={MG.l + pw} y1={baseBarras} y2={baseBarras} stroke={tk.border} />
                {M.e.map((a, q) => {
                  const h = Math.max(1.5, (ALTO_BARRAS - 12) * M.n[q] / nmax);
                  return <rect key={a} x={geo.cx(a) - banda * 0.34} y={baseBarras - h} width={banda * 0.68} height={h} fill={conAlfa(tk.muted, 0.55)} />;
                })}
                <text x={MG.l + 2} y={baseBarras - ALTO_BARRAS + 9} fontSize={10.5} fill={tk.muted}>Jugador-temporadas por edad (máximo {miles(nmax)})</text>
              </g>
              <EjeX geo={geo} tk={tk} y={baseBarras} />
            </svg>
            <Typography sx={{ fontSize: 11.5, color: "text.secondary", mb: 2.5 }}>
              Línea: mediana. Franja: del percentil 25 al 75.
              {M.ocultas.length > 0 && ` No se dibuja ${M.ocultas.length > 1 ? "las edades" : "la edad"} ${M.ocultas.join(", ")} (menos de ${D.minJugadores} jugador-temporadas).`}
            </Typography>

            {/* panel 2: rendimiento */}
            <Typography component="h3" sx={{ fontSize: 13.5, fontWeight: 700, mb: 0.25 }}>
              Rendimiento <Box component="span" sx={{ fontWeight: 500, color: "text.secondary" }}>
                · {curvas.length === 1 ? `${curvas[0].r.metrica}; ${D.ancla} años = 100` : curvas.length > 1 ? `cada posición con su métrica; ${D.ancla} años = 100` : "no se calcula"}
              </Box>
            </Typography>
            {multiple && (
              <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1.5, mb: 0.5, fontSize: 12 }}>
                {curvas.map((c) => (
                  <Box key={c.pos} sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
                    <Box sx={{ width: 14, height: 3, borderRadius: 1, bgcolor: colorDe(c.pos) }} />{c.pos}: {c.r.metrica}
                  </Box>
                ))}
              </Box>
            )}
            {curvas.length === 0 ? (
              <Box sx={{ border: 1, borderColor: "divider", borderRadius: 2, p: 2, minHeight: 120, display: "grid", placeItems: "center", textAlign: "center", color: "text.secondary", fontSize: 13.5 }}>
                {pos === "Portero"
                  ? "No hay curva de rendimiento para porteros: ni npxG + xA ni las acciones defensivas describen lo que hacen."
                  : "No hay suficientes jugadores con 900 minutos o más en dos temporadas seguidas para dibujar la curva."}
              </Box>
            ) : (
              <svg role="img" aria-label={`Curva de rendimiento por edad relativa a los ${D.ancla} años, con su intervalo. ${resumen2}`}
                width={w} height={alto2} {...manejadores}>
                <Rejilla geo={geo} tk={tk} y={y2} marcasY={ticks2} fmt={(v) => `${v}`} />
                {hover && columna(hover.a, ALTO2)}
                {/* la referencia: el nivel a los 22 años */}
                <line x1={MG.l} x2={MG.l + pw} y1={y2(100)} y2={y2(100)} stroke={tk.muted} strokeWidth={1.2} strokeDasharray="5 4" />
                <text x={MG.l + pw - 2} y={y2(100) - 5} textAnchor="end" fontSize={10.5} fill={tk.muted}
                  stroke={tk.surface} strokeWidth={3} paintOrder="stroke" strokeLinejoin="round">{D.ancla} años = 100</text>
                {curvas.map((c) => {
                  const { e, curva, lo, hi, pico } = c.r;
                  const col = colorDe(c.pos);
                  const k = e.indexOf(pico);
                  const arriba = e.map((a, q) => `${geo.cx(a)},${y2(hi[q])}`);
                  const abajo = e.map((a, q) => `${geo.cx(a)},${y2(lo[q])}`).reverse();
                  const px = geo.cx(pico), py = y2(curva[k]);
                  const ancla = px > MG.l + pw - 70 ? "end" : px < MG.l + 70 ? "start" : "middle";
                  return (
                    <g key={c.pos}>
                      <polygon points={[...arriba, ...abajo].join(" ")} fill={conAlfa(col, multiple ? 0.1 : modo === "dark" ? 0.28 : 0.2)} />
                      <polyline points={e.map((a, q) => `${geo.cx(a)},${y2(curva[q])}`).join(" ")} fill="none" stroke={col} strokeWidth={2.2} strokeLinejoin="round" />
                      {e.map((a, q) => <circle key={a} cx={geo.cx(a)} cy={y2(curva[q])} r={hover && hover.a === a ? 4.5 : 2.6} fill={col} stroke={tk.surface} strokeWidth={1} />)}
                      <circle cx={px} cy={py} r={6} fill="none" stroke={col} strokeWidth={1.8} />
                      {!multiple && (
                        <text x={px} y={py - 11} textAnchor={ancla} fontSize={11.5} fontWeight={600} fill={tk["text-body"]}
                          stroke={tk.surface} strokeWidth={3.5} paintOrder="stroke" strokeLinejoin="round">máximo a los {pico}</text>
                      )}
                    </g>
                  );
                })}
                <EjeX geo={geo} tk={tk} y={MG.t + ALTO2} />
              </svg>
            )}
            <Typography sx={{ fontSize: 11.5, color: "text.secondary", mt: 0.5 }}>
              {curvas.length > 0 && <>Línea: cambio encadenado del mismo jugador de un año al siguiente. Franja: intervalo del {(100 - D.nivelIc) / 2}% al {100 - (100 - D.nivelIc) / 2}%. Círculo: máximo de la curva. </>}
              {curvas.length > 0 && cfg.avisoSesgo}
            </Typography>
          </>
        )}
        {tip}
      </Box>

      <Box sx={{ mt: 1, display: "flex", justifyContent: "flex-end", maxWidth: 1000 }}>
        <Typography sx={{ fontSize: 12, color: "text.secondary" }}>Datos: {cfg.fuente}</Typography>
      </Box>

      <Box sx={{ mt: 2, maxWidth: 1040 }}>
        <Rotulo>Qué más mirar</Rotulo>
        <Parrafos texto={cfg.queMirar} sx={{ color: "text.primary" }} />
        <Box sx={{ mt: 2, pl: 2, borderLeft: 3, borderColor: "success.main" }}>
          <Typography sx={{ fontSize: 10.5, fontWeight: 700, letterSpacing: ".07em", textTransform: "uppercase", color: "success.main", mb: 0.75 }}>
            Con estos filtros · {etiqueta}
          </Typography>
          {lectura.map((t, i) => (
            <Typography key={i} sx={{ fontSize: 14, lineHeight: 1.6, mb: i < lectura.length - 1 ? 1 : 0 }}><Md texto={t} /></Typography>
          ))}
        </Box>
        <details style={{ marginTop: 16, borderTop: "1px solid var(--color-border)", paddingTop: 8 }}>
          <summary style={{ cursor: "pointer", font: "700 10.5px Inter, system-ui", letterSpacing: ".07em", textTransform: "uppercase", color: "var(--color-muted)", padding: "6px 0" }}>
            Por qué así
          </summary>
          <Parrafos texto={cfg.porQue} sx={{ fontSize: 13.5 }} />
        </details>
      </Box>
    </>
  );
}

export default function EdadVista({ id }) {
  const cfg = window.futvizVistas[id];
  const { theme, modo, t } = useSitioTema();
  const [estado, setEstado] = useState({ D: null, error: null });
  useEffect(() => {
    let vivo = true;
    cargarDatos(cfg.tabla).then((D) => vivo && setEstado({ D, error: null })).catch((error) => vivo && setEstado({ D: null, error }));
    return () => { vivo = false; };
  }, [cfg.tabla]);
  return (
    <ThemeProvider theme={theme}>
      {estado.error ? <Aviso>No se pudieron cargar los datos de esta vista.</Aviso>
        : !estado.D ? <Cargando />
          : <Vista cfg={cfg} D={estado.D} modo={modo} tk={t} />}
    </ThemeProvider>
  );
}
