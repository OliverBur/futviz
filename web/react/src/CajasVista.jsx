// "Nivel por liga": una caja por liga para la variable que se elija, con cada equipo como un punto.
//
// Mira dos cosas distintas: qué liga está más arriba (su nivel típico) y qué tan ancha es la caja (qué tan
// parejos son sus equipos). El eje Y de cada variable se fija con el rango de TODAS las temporadas y niveles:
// si se reescalara al filtrar, dos cajas del mismo alto significarían dispersiones distintas.
//
// MUI X Charts no trae un boxplot gratuito, así que se arma sobre el mismo `ScatterChart` de las demás
// vistas: la liga es una posición entera del eje X (1..5), cada equipo un punto con un desplazamiento
// horizontal pequeño y determinista (jitter), y una capa propia dibuja las cajas encima.
import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { ThemeProvider } from "@mui/material/styles";
import Box from "@mui/material/Box";
import MenuItem from "@mui/material/MenuItem";
import Paper from "@mui/material/Paper";
import TextField from "@mui/material/TextField";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import Typography from "@mui/material/Typography";
import { ScatterChart } from "@mui/x-charts/ScatterChart";
import { ChartsTooltipContainer, useItemTooltip } from "@mui/x-charts/ChartsTooltip";
import { useDrawingArea } from "@mui/x-charts/hooks";
import { useSitioTema } from "./theme.jsx";
import { useTabla } from "./datos.js";
import { EstilosGrafica } from "./Grafica.jsx";
import { Aviso, Cargando, Parrafos, Rotulo } from "./ui.jsx";
import { cuantil, mediana } from "./stats.js";

const FilaCtx = createContext(null);
const ANCHO_CAJA = 0.5;     // en unidades del eje (las ligas están a distancia 1)
const JITTER = 0.2;         // ± en esas mismas unidades

// Desplazamiento horizontal estable por equipo: el mismo punto cae siempre en el mismo sitio.
const jitterDe = (r) => {
  let h = (r * 2654435761) >>> 0;
  h ^= h >>> 15; h = Math.imul(h, 2246822519) >>> 0; h ^= h >>> 13;
  return ((h % 1000) / 1000 - 0.5) * 2 * JITTER;
};

// Cuartiles (interpolación lineal, como el método "linear" de Plotly) y bigotes: hasta el dato más lejano
// que no pase de 1,5 veces el rango intercuartílico.
function estadisticas(v) {
  if (v.length < 1) return null;
  const q1 = cuantil(v, 0.25), q3 = cuantil(v, 0.75), med = mediana(v), iqr = q3 - q1;
  const dentro = v.filter((x) => x >= q1 - 1.5 * iqr && x <= q3 + 1.5 * iqr);
  return { n: v.length, q1, q3, med, lo: Math.min(...dentro), hi: Math.max(...dentro) };
}

function CuerpoTooltip() {
  const item = useItemTooltip();
  const ctx = useContext(FilaCtx);
  const f = item && ctx ? ctx.info(item.value.id) : null;
  if (!f) return null;
  return (
    <Paper className="rx-tooltip" elevation={4} sx={{ p: 1.25, minWidth: 170, border: 1, borderColor: "divider" }}>
      <Typography sx={{ fontWeight: 700, fontSize: 13.5, lineHeight: 1.25 }}>{f.nombre}</Typography>
      <Box sx={{ display: "flex", alignItems: "center", gap: 0.75, mb: 0.75, color: "text.secondary", fontSize: 12 }}>
        <Box component="span" sx={{ width: 12, height: 3, borderRadius: 1, bgcolor: f.color, flex: "none" }} />
        {f.sub}
      </Box>
      <Box sx={{ display: "flex", justifyContent: "space-between", gap: 2, fontSize: 12.5 }}>
        <Box component="span" sx={{ color: "text.secondary" }}>{f.etiqueta}</Box>
        <Box component="span" sx={{ fontWeight: 700 }}>{f.valor}</Box>
      </Box>
    </Paper>
  );
}
function PuntoTooltip(props) {
  return <ChartsTooltipContainer {...props} trigger="item"><CuerpoTooltip /></ChartsTooltipContainer>;
}
const Marcador = ({ x, y, color, size, isHighlighted, isFaded, seriesId, dataIndex, ...resto }) => (
  <circle {...resto} className={`${resto.className || ""} rx-punto`} transform={`translate(${x},${y})`}
    r={isHighlighted ? size * 1.9 : size} fill={color} fillOpacity={0.8}
    style={{ stroke: isHighlighted ? "var(--color-primary)" : "var(--color-surface)", strokeWidth: isHighlighted ? 2 : 0.6 }} />
);

// Las cajas, dentro del <svg> del chart, encima de los puntos. El área de dibujo se lee con el hook de MUI.
function CapaCajas({ cajas, ligasX, dominioY, colores, tk, onArea }) {
  const area = useDrawingArea();
  useEffect(() => { onArea({ left: area.left, top: area.top, width: area.width, height: area.height }); },
    [area.left, area.top, area.width, area.height]);
  if (!area.width) return null;
  const px = (x) => area.left + ((x - 0.45) / (5.55 - 0.45)) * area.width;
  const py = (y) => area.top + (1 - (y - dominioY[0]) / (dominioY[1] - dominioY[0])) * area.height;
  const mitad = (ANCHO_CAJA / 2 / (5.55 - 0.45)) * area.width;
  return (
    <g>
      {cajas.map((c, i) => c && (
        <g key={ligasX[i]} stroke={colores[i]} strokeWidth={1.6} fill="none">
          <title>{`${ligasX[i]} · mediana ${c.med.toFixed(c.dec)} · caja ${c.q1.toFixed(c.dec)}–${c.q3.toFixed(c.dec)} · ${c.n} equipos`}</title>
          <line x1={px(i + 1)} x2={px(i + 1)} y1={py(c.hi)} y2={py(c.q3)} />
          <line x1={px(i + 1)} x2={px(i + 1)} y1={py(c.q1)} y2={py(c.lo)} />
          <line x1={px(i + 1) - mitad / 2} x2={px(i + 1) + mitad / 2} y1={py(c.hi)} y2={py(c.hi)} />
          <line x1={px(i + 1) - mitad / 2} x2={px(i + 1) + mitad / 2} y1={py(c.lo)} y2={py(c.lo)} />
          <rect x={px(i + 1) - mitad} y={py(c.q3)} width={mitad * 2} height={Math.max(1, py(c.q1) - py(c.q3))}
            fill={tk.surface} fillOpacity={0.35} rx={2} />
          <line x1={px(i + 1) - mitad} x2={px(i + 1) + mitad} y1={py(c.med)} y2={py(c.med)} strokeWidth={2.6} />
        </g>
      ))}
    </g>
  );
}

function Vista({ cfg, T, modo, tk }) {
  const [colVar, setColVar] = useState(cfg.variable);
  const [temporada, setTemporada] = useState(T.temporadas.length - 1);
  const [nivel, setNivel] = useState("todos");
  const [area, setArea] = useState({ left: 0, top: 0, width: 0, height: 0 });
  const [ancho, setAncho] = useState(0);
  const [caja, setCaja] = useState(null);
  useEffect(() => {
    if (!caja) return undefined;
    const ro = new ResizeObserver(([e]) => setAncho(Math.round(e.contentRect.width)));
    ro.observe(caja);
    return () => ro.disconnect();
  }, [caja]);

  const info = useMemo(() => Object.fromEntries(cfg.variables.map((v) => [v.col, v])), [cfg]);
  const v = info[colVar];
  const col = T.c[colVar];
  const colores = useMemo(() => T.ligas.map((l) => T.colores[modo === "dark" ? "oscuro" : "claro"][l]), [T, modo]);

  // El rango de cada variable: de TODAS las temporadas y niveles, con margen (más arriba que abajo: ahí
  // caben los bigotes y la caja sin pegarse al borde).
  const dominioY = useMemo(() => {
    let lo = Infinity, hi = -Infinity;
    for (const x of col) { if (x == null) continue; if (x < lo) lo = x; if (x > hi) hi = x; }
    const pad = (hi - lo) * 0.10;
    return [lo - pad * 0.5, hi + pad * 1.25];
  }, [col]);

  const nivelIdx = nivel === "todos" ? -1 : T.niveles.indexOf(nivel);
  const filas = useMemo(() => {
    const out = [];
    for (let r = 0; r < T.n; r++) {
      if (T.f.t[r] !== temporada || col[r] == null) continue;
      if (nivelIdx >= 0 && T.f.v[r] !== nivelIdx) continue;
      out.push(r);
    }
    return out;
  }, [T, col, temporada, nivelIdx]);

  const porLiga = useMemo(() => T.ligas.map((_, li) => filas.filter((r) => T.f.l[r] === li)), [T, filas]);
  const cajas = useMemo(() => porLiga.map((rs) => {
    const s = estadisticas(rs.map((r) => col[r]));
    return s && { ...s, dec: v.dec };
  }), [porLiga, col, v.dec]);
  const series = useMemo(() => T.ligas.map((liga, li) => ({
    id: liga, type: "scatter", label: liga, color: colores[li], markerSize: 4, highlightScope: { highlight: "item", fade: "none" },
    data: porLiga[li].map((r) => ({ x: li + 1 + jitterDe(r), y: col[r], id: r })),
  })), [T, colores, porLiga, col]);

  const ctx = useMemo(() => ({
    info: (r) => ({ nombre: T.nombre(r), sub: `${T.liga(r)} · ${tTemp(T, temporada)}`, color: colores[T.f.l[r]],
      etiqueta: v.label, valor: col[r].toFixed(v.dec) }),
  }), [T, colores, v, col, temporada]);

  const alto = Math.max(380, Math.min(560, Math.round(ancho * 0.58)));
  const tLabel = T.temporadas[temporada];
  // En pantalla angosta los cinco nombres no caben en una línea: se parten ("Premier / League / 20").
  const estrecho = ancho > 0 && ancho < 640;
  const etiquetaLiga = (x) => {
    const i = Math.round(x) - 1;
    if (Math.abs(x - Math.round(x)) > 1e-6 || !T.ligas[i]) return "";
    return estrecho ? `${T.ligas[i].replace(" ", "\n")}\n${porLiga[i].length}` : `${T.ligas[i]} · ${porLiga[i].length}`;
  };
  const claveDatos = `${colVar}|${temporada}|${nivel}`;

  return (
    <FilaCtx.Provider value={ctx}>
      <Box sx={{ display: "grid", gap: 3, gridTemplateColumns: { xs: "minmax(0,1fr)", md: "minmax(0,1fr) 270px" }, alignItems: "start" }}>
        <Box sx={{ minWidth: 0 }}>
          <Typography component="h2" sx={{ fontSize: 17, fontWeight: 700, color: "primary.main" }}>{cfg.titulo}</Typography>
          <Typography sx={{ fontSize: 13, color: "text.secondary", mb: 1.5 }}>
            {cfg.subtitulo.replace("{variable}", v.label).replace("{temporada}", tLabel)}
          </Typography>
          <Box ref={setCaja} className="rx-chart" sx={{
            position: "relative", width: "100%", userSelect: "none",
            "& .MuiChartsAxis-tickLabel": { fill: tk["text-body"], fontSize: 12, fontWeight: 600 },
            "& .MuiChartsAxis-label": { fill: tk["text-body"], fontSize: 12.5, fontWeight: 600 },
            "& .MuiChartsAxis-line, & .MuiChartsAxis-tick": { stroke: tk.border },
            "& .MuiChartsGrid-line": { stroke: tk.border, strokeOpacity: 0.7 },
          }}>
            <EstilosGrafica />
            {ancho > 0 && (
              <ScatterChart
                key={claveDatos}
                height={alto}
                series={series}
                xAxis={[{ id: "x", scaleType: "linear", min: 0.45, max: 5.55, tickInterval: [1, 2, 3, 4, 5],
                  valueFormatter: etiquetaLiga, height: estrecho ? 62 : 40,
                  // MUI esconde una marca si su texto roza a la vecina; con cinco ligas en ~290 px las
                  // etiquetas llegan justas, así que en pantalla angosta van más chicas y sin holgura mínima.
                  tickLabelMinGap: estrecho ? 0 : 4, tickLabelStyle: estrecho ? { fontSize: 10.5 } : undefined }]}
                yAxis={[{ id: "y", scaleType: "linear", min: dominioY[0], max: dominioY[1], label: v.label, width: 58,
                  valueFormatter: (y) => String(Number(y.toFixed(2))), tickNumber: 7 }]}
                margin={{ top: 10, right: estrecho ? 26 : 14, bottom: 6, left: 6 }}
                grid={{ horizontal: true }}
                hideLegend skipAnimation hitAreaRadius={14}
                slots={{ marker: Marcador, tooltip: PuntoTooltip }}>
                <CapaCajas cajas={cajas} ligasX={T.ligas} dominioY={dominioY} colores={colores} tk={tk} onArea={setArea} />
              </ScatterChart>
            )}
            {filas.length === 0 && ancho > 0 && (
              <Box role="status" sx={{ position: "absolute", left: 0, right: 0, top: "42%", textAlign: "center", color: "text.secondary", fontSize: 13.5 }}>
                Ningún equipo con estos filtros.
              </Box>
            )}
          </Box>
          <Box sx={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", gap: 1, mt: 0.75 }}>
            <Typography sx={{ fontSize: 12, color: "text.secondary" }}>
              La línea gruesa es la mediana · la caja, la mitad central de los equipos · cada punto, un equipo
            </Typography>
            <Typography sx={{ fontSize: 12, color: "text.secondary" }}>Datos: {cfg.fuente}</Typography>
          </Box>
        </Box>

        {/* Los controles: a la derecha en escritorio; ARRIBA del gráfico en móvil (son tres y se usan primero). */}
        <Box sx={{ display: "flex", flexDirection: "column", gap: 2.25, order: { xs: -1, md: 0 } }}>
          <Box>
            <Rotulo>Variable</Rotulo>
            <TextField select size="small" fullWidth value={colVar} onChange={(e) => setColVar(e.target.value)}
              slotProps={{ select: { MenuProps: { slotProps: { paper: { sx: { maxHeight: 420 } } } } } }}>
              {cfg.variables.map((x) => <MenuItem key={x.col} value={x.col} sx={{ fontSize: 13, whiteSpace: "normal" }}>{x.label}</MenuItem>)}
            </TextField>
          </Box>
          <Box>
            <Rotulo>Temporada</Rotulo>
            <ToggleButtonGroup exclusive size="small" fullWidth value={temporada} aria-label="Temporada"
              onChange={(_e, x) => x != null && setTemporada(x)}>
              {T.temporadas.map((t, i) => (
                <ToggleButton key={t} value={i} aria-label={t} sx={{ px: 0.5, fontSize: "11.5px !important" }}>{t.slice(2)}</ToggleButton>
              ))}
            </ToggleButtonGroup>
          </Box>
          {T.niveles && T.niveles.length > 0 && (
            <Box>
              <Rotulo ayuda={(T.ayudas || {}).nivel}>Nivel del club</Rotulo>
              <ToggleButtonGroup exclusive size="small" fullWidth value={nivel} aria-label="Nivel del club"
                onChange={(_e, x) => x && setNivel(x)}>
                <ToggleButton value="todos">Todos</ToggleButton>
                {T.niveles.map((n) => (
                  <ToggleButton key={n} value={n} sx={{ px: 0.5, fontSize: "11.5px !important" }}>
                    {n.replace("Clubes ", "").replace(/^./, (c) => c.toUpperCase())}
                  </ToggleButton>
                ))}
              </ToggleButtonGroup>
            </Box>
          )}
        </Box>
      </Box>

      <Box sx={{ mt: 3, maxWidth: 820 }}>
        <Rotulo>Qué mirar aquí</Rotulo>
        <Parrafos texto={cfg.queMirar} sx={{ color: "text.primary" }} />
      </Box>
    </FilaCtx.Provider>
  );
}

const tTemp = (T, i) => T.temporadas[i];

export default function CajasVista({ id }) {
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
