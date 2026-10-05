// Mapa de calor de los tiros: desde dónde se remata en las 5 grandes ligas.
//
// El mapa mira HACIA LA PORTERÍA: la línea de fondo es el borde de arriba, los dos rectángulos son el área
// grande y el área chica, y la izquierda del mapa es la izquierda del ataque. Cada celda es un cuadrado de
// 2×2 m y el color NO cuenta tiros: reparte entre las celdas el 100% de los tiros de la selección, así la
// forma de un tipo de tiro se compara con la de otro aunque haya veinte veces más de uno que de otro.
//
// La tabla viaja agregada por celda (`shot_map.tabla_agregada`) y el navegador suma lo que pida el filtro:
// no recibe los 225.000 tiros. Mismos datos, geometría y textos que la versión de Plotly; el eje del mapa
// y la cancha están en METROS (el viewBox del SVG), y los trazos de las líneas no escalan.
import { useMemo, useRef, useState } from "react";
import { ThemeProvider, useTheme } from "@mui/material/styles";
import useMediaQuery from "@mui/material/useMediaQuery";
import Box from "@mui/material/Box";
import ListSubheader from "@mui/material/ListSubheader";
import MenuItem from "@mui/material/MenuItem";
import Paper from "@mui/material/Paper";
import TextField from "@mui/material/TextField";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import Typography from "@mui/material/Typography";
import { useSitioTema } from "./theme.jsx";
import { useTabla } from "./datos.js";
import { Aviso, Cargando, Md, Parrafos, Rotulo } from "./ui.jsx";
import { tiros } from "./insights.js";
import { agregar } from "./tiros.js";
import { miles } from "./stats.js";
import { conAlfa } from "./colores.js";

const TODAS = "todas", TODOS = "todos";

// Color por interpolación lineal entre las paradas de la rampa (0..1).
const hex = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
function colorRampa(rampa, t) {
  const x = Math.min(1, Math.max(0, t)) * (rampa.length - 1);
  const i = Math.min(rampa.length - 2, Math.floor(x)), f = x - i;
  const a = hex(rampa[i]), b = hex(rampa[i + 1]);
  return `rgb(${a.map((v, k) => Math.round(v + (b[k] - v) * f)).join(",")})`;
}

function Vista({ cfg, T, modo, tk }) {
  const esAngosta = useMediaQuery(useTheme().breakpoints.down("sm"), { noSsr: true });
  const [temporada, setTemporada] = useState(TODAS);
  const [tipoId, setTipoId] = useState(TODOS);
  const [celdaSobre, setCeldaSobre] = useState(null);
  const svgRef = useRef(null);

  const ti = temporada === TODAS ? null : T.temporadas.indexOf(temporada);
  const tipo = T.tipos.find((t) => t.id === tipoId);
  const tipoAgg = tipoId === TODOS ? null : tipo;
  const sel = useMemo(() => agregar(T, ti, tipoAgg), [T, ti, tipoAgg]);
  const base = useMemo(() => agregar(T, ti, null).tot, [T, ti]);   // la misma temporada sin filtro de tipo

  // Oscuro: la rampa va de oscuro a claro (lo más alto es lo más brillante sobre la superficie oscura).
  const rampa = useMemo(() => (modo === "dark" ? [...T.rampa].reverse() : T.rampa), [T, modo]);
  const total = sel.tot.n;
  const z = (i) => (total ? (100 * sel.n[i]) / total : 0);
  const zmax = useMemo(() => { let m = 0; for (let i = 0; i < sel.n.length; i++) if (total && sel.n[i] / total * 100 > m) m = sel.n[i] / total * 100; return m; }, [sel, total]);

  const ambito = temporada === TODAS ? `las ${T.temporadas.length} temporadas` : temporada;
  const lectura = useMemo(() => tiros(sel.tot, base, tipo.frase || "", ambito), [sel, base, tipo, ambito]);
  const subtitulo = `${tipo.etiqueta} · ${temporada === TODAS ? `${T.temporadas[0]} a ${T.temporadas[T.temporadas.length - 1]}` : temporada} · ${miles(total)} remates, sin penaltis`;

  // --- geometría (metros) --------------------------------------------------------------------------
  const { nx, ny, celda: lado, ancho, profundidad, aire, penal, porteria } = T;
  const vb = { x: -1, y: -aire - 1.6, w: ancho + 2, h: profundidad + aire + 1.6 + 1 };
  const medio = ancho / 2;
  const tope = Math.asin(Math.sqrt(9.15 ** 2 - (16.5 - penal) ** 2) / 9.15);
  const arco = Array.from({ length: 61 }, (_, i) => {
    const a = -tope + (2 * tope * i) / 60;
    return `${medio + 9.15 * Math.sin(a)},${penal + 9.15 * Math.cos(a)}`;
  }).join(" ");
  const trazo = { fill: "none", vectorEffect: "non-scaling-stroke" };

  // Del puntero a la celda: el SVG convierte píxeles a metros con su propia matriz.
  const alMover = (e) => {
    const svg = svgRef.current;
    const pt = svg.createSVGPoint();
    pt.x = e.clientX; pt.y = e.clientY;
    const m = svg.getScreenCTM();
    if (!m) return;
    const p = pt.matrixTransform(m.inverse());
    const cx = Math.floor(p.x / lado), cy = Math.floor(p.y / lado);
    setCeldaSobre(cx >= 0 && cx < nx && cy >= 0 && cy < ny ? { cx, cy, px: e.clientX, py: e.clientY } : null);
  };
  const cel = celdaSobre ? celdaSobre.cy * nx + celdaSobre.cx : -1;

  return (
    <>
      <Box sx={{ display: "grid", gap: 3, gridTemplateColumns: { xs: "minmax(0,1fr)", md: "minmax(0,1fr) 270px" }, alignItems: "start" }}>
        <Box sx={{ minWidth: 0 }}>
          <Typography component="h2" sx={{ fontSize: 17, fontWeight: 700, color: "primary.main" }}>{cfg.titulo}</Typography>
          <Typography sx={{ fontSize: 13, color: "text.secondary", mb: 1.5 }}>{subtitulo}</Typography>

          <Box sx={{ display: "flex", flexDirection: { xs: "column", sm: "row" }, gap: 2, alignItems: "stretch" }}>
            <Box sx={{ flex: 1, minWidth: 0, maxWidth: 780, position: "relative" }}>
              <svg ref={svgRef} role="img" aria-label={`Mapa de calor de los tiros: ${subtitulo}`}
                viewBox={`${vb.x} ${vb.y} ${vb.w} ${vb.h}`} style={{ width: "100%", height: "auto", display: "block", touchAction: "pan-y" }}
                onPointerMove={alMover} onPointerLeave={() => setCeldaSobre(null)} onPointerDown={alMover}>
                {/* el campo: la región dibujada, apenas teñida con el primer tono de la rampa */}
                <rect x={0} y={0} width={ancho} height={profundidad} fill={conAlfa(rampa[0], 0.28)} />
                {Array.from({ length: nx * ny }, (_, i) => {
                  if (!sel.n[i]) return null;
                  const cx = i % nx, cy = Math.floor(i / nx);
                  return <rect key={i} x={cx * lado} y={cy * lado} width={lado} height={lado}
                    fill={colorRampa(rampa, zmax ? z(i) / zmax : 0)} />;
                })}
                {/* la celda bajo el puntero */}
                {celdaSobre && (
                  <rect x={celdaSobre.cx * lado} y={celdaSobre.cy * lado} width={lado} height={lado} fill="none"
                    stroke={tk.primary} strokeWidth={2} vectorEffect="non-scaling-stroke" />
                )}
                {/* la cancha: línea clara con un halo oscuro debajo, para que se lea sobre cualquier celda */}
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
                {/* la portería, detrás de la línea de fondo, fuera del mapa */}
                <rect x={medio - porteria / 2} y={-1.2} width={porteria} height={1.2} fill="none" stroke={tk.muted}
                  strokeWidth={1.6} vectorEffect="non-scaling-stroke" />
              </svg>
              {celdaSobre && (
                <Paper elevation={4} className="rx-tooltip" sx={{ position: "fixed", left: celdaSobre.px + 14, top: celdaSobre.py + 14,
                  p: 1.25, pointerEvents: "none", zIndex: 1500, border: 1, borderColor: "divider", fontSize: 12.5 }}>
                  <Box sx={{ color: "text.secondary", mb: 0.5 }}>A {Math.round((celdaSobre.cy + 0.5) * lado)} m de la línea de fondo</Box>
                  <Box><strong>{miles(sel.n[cel])}</strong> tiros ({z(cel).toFixed(2)}% del total)</Box>
                  <Box><strong>{miles(sel.g[cel])}</strong> goles ({sel.n[cel] ? Math.round((100 * sel.g[cel]) / sel.n[cel]) : 0}%)</Box>
                </Paper>
              )}
            </Box>

            {/* la barra de color: vertical a la derecha del mapa; en pantalla angosta, horizontal debajo,
                para que el mapa use todo el ancho */}
            <Box sx={{ width: { xs: "100%", sm: 64 }, flex: "none", display: "flex", flexDirection: "column", alignItems: "flex-start" }}>
              <Typography sx={{ fontSize: 11.5, fontWeight: 600, color: "text.secondary", mb: 0.5 }}>% de los tiros</Typography>
              <Box sx={{ display: "flex", flexDirection: { xs: "column", sm: "row" }, gap: 0.75, flex: 1, width: "100%",
                minHeight: { sm: 160 }, maxHeight: { sm: 280 } }}>
                <Box sx={{ width: { xs: "100%", sm: 12 }, height: { xs: 10, sm: "auto" }, borderRadius: 1, border: 1, borderColor: "divider",
                  background: `linear-gradient(to ${esAngosta ? "right" : "top"}, ${rampa.map((c, i) => `${c} ${(i / (rampa.length - 1)) * 100}%`).join(", ")})` }} />
                <Box sx={{ display: "flex", flexDirection: { xs: "row-reverse", sm: "column" }, justifyContent: "space-between",
                  fontSize: 11.5, color: "text.secondary" }}>
                  <span>{zmax.toFixed(1)}</span><span>0</span>
                </Box>
              </Box>
            </Box>
          </Box>

          <Box sx={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", gap: 1, mt: 0.75 }}>
            <Typography sx={{ fontSize: 12, color: "text.secondary" }}>Pasa el mouse por una celda para ver los números crudos.</Typography>
            <Typography sx={{ fontSize: 12, color: "text.secondary" }}>Datos: {cfg.fuente}</Typography>
          </Box>
        </Box>

        {/* Los controles: a la derecha en escritorio; ARRIBA del mapa en móvil (son pocos y se usan primero). */}
        <Box sx={{ display: "flex", flexDirection: "column", gap: 2.25, order: { xs: -1, md: 0 } }}>
          <Box>
            <Rotulo>Temporada</Rotulo>
            <ToggleButtonGroup exclusive size="small" fullWidth value={temporada} aria-label="Temporada"
              onChange={(_e, v) => v && setTemporada(v)} sx={{ flexWrap: "wrap" }}>
              <ToggleButton value={TODAS} sx={{ flexBasis: "100%", borderRadius: 1 }}>Todas las temporadas</ToggleButton>
              {T.temporadas.map((t) => (
                <ToggleButton key={t} value={t} aria-label={t} sx={{ px: 0.5, fontSize: "11.5px !important", flex: "1 0 16%" }}>{t.slice(2)}</ToggleButton>
              ))}
            </ToggleButtonGroup>
          </Box>
          <Box>
            <Rotulo>Tipo de tiro</Rotulo>
            <TextField select size="small" fullWidth value={tipoId} onChange={(e) => setTipoId(e.target.value)}>
              {[null, "Jugada", "Parte del cuerpo"].flatMap((g) => [
                ...(g ? [<ListSubheader key={`g-${g}`}>{g}</ListSubheader>] : []),
                ...T.tipos.filter((t) => (t.grupo || null) === g).map((t) => (
                  <MenuItem key={t.id} value={t.id} sx={{ fontSize: 13 }}>{t.etiqueta}</MenuItem>)),
              ])}
            </TextField>
            <Typography sx={{ fontSize: 11.5, color: "text.secondary", mt: 0.5 }}>{T.hint}</Typography>
          </Box>
        </Box>
      </Box>

      <Box sx={{ mt: 3, maxWidth: 820 }}>
        <Rotulo>Qué mirar aquí</Rotulo>
        <Parrafos texto={cfg.queMirar} sx={{ color: "text.primary" }} />
        <Box sx={{ mt: 2, pl: 2, borderLeft: 3, borderColor: "success.main" }}>
          <Typography sx={{ fontSize: 10.5, fontWeight: 700, letterSpacing: ".07em", textTransform: "uppercase", color: "success.main", mb: 0.75 }}>
            En lo que estás viendo · {temporada === TODAS ? "todas las temporadas" : temporada} · {tipo.etiqueta}
          </Typography>
          <Typography sx={{ fontSize: 14, lineHeight: 1.6, mb: lectura.salta ? 1 : 0 }}><Md texto={lectura.fija} /></Typography>
          {lectura.salta && <Typography sx={{ fontSize: 14, lineHeight: 1.6 }}><Md texto={lectura.salta} /></Typography>}
        </Box>
        <details style={{ marginTop: 16, borderTop: "1px solid var(--color-border)", paddingTop: 8 }}>
          <summary style={{ cursor: "pointer", font: "700 10.5px Inter, system-ui", letterSpacing: ".07em", textTransform: "uppercase", color: "var(--color-muted)", padding: "6px 0" }}>
            Por qué el mapa es así
          </summary>
          <Parrafos texto={cfg.porQue} sx={{ fontSize: 13.5 }} />
        </details>
      </Box>
    </>
  );
}

export default function MapaTiros({ id }) {
  const cfg = window.futvizVistas[id];
  const { theme, modo, t } = useSitioTema();
  const { T, error } = useTabla(cfg.tabla);
  return (
    <ThemeProvider theme={theme}>
      {error ? <Aviso>No se pudieron cargar los datos de esta vista.</Aviso>
        : !T ? <Cargando />
          : <Vista cfg={cfg} T={T} modo={modo} tk={t} />}
    </ThemeProvider>
  );
}
