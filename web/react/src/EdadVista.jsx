// Edad: los minutos por edad (17 a 38 años). Mediana y rango típico (percentil 25 a 75) del % de los minutos de su club que
// jugó cada jugador-temporada, con barras que cuentan cuántos hay en cada edad.
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

const MG = { l: 46, r: 12, t: 10 };       // márgenes del SVG
const ALTO1 = 220, ALTO_BARRAS = 36, ALTO_EJE = 24;
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
  const lectura = useMemo(() => lecturaEdad(D, pos, etiqueta), [D, pos, etiqueta]);

  const y1 = (v) => MG.t + ALTO1 * (1 - v / 100);
  const baseBarras = MG.t + ALTO1 + 12 + ALTO_BARRAS;
  const nmax = Math.max(1, ...M.n);
  const alto1 = baseBarras + ALTO_EJE;

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
    </Paper>
  );

  const resumen1 = M.e.length
    ? `Mediana del porcentaje de minutos jugados por edad, ${etiqueta.toLowerCase()}: de ${r0(M.med[0])}% a los ${M.e[0]} años a ${r0(M.med[M.e.length - 1])}% a los ${M.e[M.e.length - 1]}, con el máximo de ${r0(Math.max(...M.med))}% a los ${M.e[M.med.indexOf(Math.max(...M.med))]} años.`
    : "Sin edades con suficientes jugadores.";

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
            <Typography sx={{ fontSize: 11.5, color: "text.secondary" }}>
              Línea: mediana. Franja: del percentil 25 al 75.
              {M.ocultas.length > 0 && ` No se dibuja ${M.ocultas.length > 1 ? "las edades" : "la edad"} ${M.ocultas.join(", ")} (menos de ${D.minJugadores} jugador-temporadas).`}
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
