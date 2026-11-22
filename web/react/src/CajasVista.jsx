// "Distribución por liga": un enjambre de equipos por liga para la variable que se elija, con una raya en la mediana y una
// banda en la mitad central.
//
// Mira dos cosas distintas: qué liga está más arriba (su nivel típico) y qué tan ancha es la banda (qué tan parejos son sus
// equipos). El eje Y de cada variable se fija con el rango de TODAS las temporadas y niveles: si se reescalara al filtrar,
// dos bandas del mismo alto significarían dispersiones distintas.
//
// Se arma sobre el mismo `ScatterChart` de las demás vistas: la liga es una posición entera del eje X (1..5) y cada equipo un
// punto. Los puntos NO llevan azar: cada uno se acomoda en el lugar libre más cercano al centro de su liga (un enjambre,
// calculado en pixeles sobre el área de dibujo), así que cada equipo tiene un lugar fijo y ninguno se sale de su columna.
// Una capa propia dibuja la banda y la mediana. Nada se resalta solo: quien mira elige equipos con el buscador o con un clic.
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { entre, leerParams, usePublicarParams } from "./urlEstado.js";
import { ThemeProvider } from "@mui/material/styles";
import Autocomplete from "@mui/material/Autocomplete";
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
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
import { BotonDescarga } from "./BotonDescarga.jsx";
import { capturar, descargarPng, limpiarDispersion, nombreArchivo } from "./descargarImagen.js";
import { Aviso, Cargando, ComoLeer, Encabezado, Parrafos, Rotulo, sinAcentos } from "./ui.jsx";
import { cuantil, mediana } from "./stats.js";

const FilaCtx = createContext(null);
const PinCtx = createContext({ ids: {}, fijos: new Set() });
const X0 = 0.45, X1 = 5.55;     // el eje X: las ligas están a distancia 1
const MITAD_BANDA = 0.36;       // media anchura de la banda, en unidades del eje
const RADIO = 4.4;              // el del punto, en pixeles (el enjambre los separa por esto)
const MAX_FIJOS = 10;           // equipos resaltados a la vez

// El enjambre de una liga: cada punto, de abajo hacia arriba, toma el lugar libre más cercano al centro (alternando izquierda y
// derecha). Sin azar: los mismos datos dan siempre la misma figura. `ys` son las alturas en pixeles; devuelve el
// desplazamiento horizontal en pixeles de cada uno, en el mismo orden.
function enjambre(ys) {
  const orden = ys.map((_, i) => i).sort((a, b) => ys[b] - ys[a]);
  const puestos = [], dx = new Array(ys.length).fill(0);
  for (const i of orden) {
    for (let k = 0; ; k++) {
      const x = (k % 2 ? 1 : -1) * Math.ceil(k / 2) * RADIO * 1.05;
      if (puestos.every((p) => Math.hypot(p.x - x, p.y - ys[i]) >= RADIO * 2 - 0.5)) { puestos.push({ x, y: ys[i] }); dx[i] = x; break; }
    }
  }
  return dx;
}

// Cuartiles (interpolación lineal, como el método "linear" de Plotly) y mediana.
function estadisticas(v) {
  if (v.length < 1) return null;
  return { n: v.length, q1: cuantil(v, 0.25), q3: cuantil(v, 0.75), med: mediana(v) };
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
// Con equipos resaltados, esos van grandes y a todo color y los demás se apagan; sin ninguno, todos iguales.
const Marcador = ({ x, y, color, size, isHighlighted, isFaded, seriesId, dataIndex, ...resto }) => {
  const { ids, fijos } = useContext(PinCtx);
  const fijo = fijos.size > 0 && fijos.has(ids[seriesId]?.[dataIndex]);
  const apagado = fijos.size > 0 && !fijo;
  const grande = isHighlighted || fijo;
  return (
    <circle {...resto} className={`${resto.className || ""} rx-punto`} transform={`translate(${x},${y})`}
      data-rotulado={fijo ? 1 : undefined}
      r={grande ? size * 1.9 : size} fill={color} fillOpacity={apagado && !isHighlighted ? 0.28 : fijo ? 1 : 0.8}
      style={{ stroke: grande ? "var(--color-primary)" : "var(--color-surface)", strokeWidth: grande ? 2 : 0.6, cursor: "pointer" }} />
  );
};

// La banda (mitad central) y la raya de la mediana, y el nombre de cada equipo resaltado, dentro del <svg> del chart. El área de
// dibujo se lee con el hook de MUI.
function CapaBandas({ cajas, ligasX, dominioY, colores, tk, onArea, etiquetas }) {
  const area = useDrawingArea();
  useEffect(() => { onArea({ left: area.left, top: area.top, width: area.width, height: area.height }); },
    [area.left, area.top, area.width, area.height]);
  if (!area.width) return null;
  const px = (x) => area.left + ((x - X0) / (X1 - X0)) * area.width;
  const py = (y) => area.top + (1 - (y - dominioY[0]) / (dominioY[1] - dominioY[0])) * area.height;
  const mitad = (MITAD_BANDA / (X1 - X0)) * area.width;
  return (
    <g pointerEvents="none">
      {cajas.map((c, i) => c && (
        <g key={ligasX[i]} stroke={colores[i]} fill="none">
          <rect x={px(i + 1) - mitad} y={py(c.q3)} width={mitad * 2} height={Math.max(1, py(c.q1) - py(c.q3))}
            fill={colores[i]} fillOpacity={0.1} stroke="none" />
          <line x1={px(i + 1) - mitad} x2={px(i + 1) + mitad} y1={py(c.med)} y2={py(c.med)} strokeWidth={2.4} />
        </g>
      ))}
      {etiquetas.map((e) => {
        const derecha = e.x < 4.4;   // en la última liga el nombre va a la izquierda del punto, para no salirse
        return (
          <text key={e.id} x={px(e.x) + (derecha ? 11 : -11)} y={py(e.y)} dy="0.32em" textAnchor={derecha ? "start" : "end"}
            fontSize={11.5} fontWeight={700} fill={tk["text-body"]} stroke={tk.surface} strokeWidth={3.5} paintOrder="stroke"
            strokeLinejoin="round">{e.texto}</text>
        );
      })}
    </g>
  );
}

function Vista({ cfg, T, modo, tk }) {
  // Los filtros de la URL (ver urlEstado.js): se leen una vez, al montarse.
  const [P] = useState(() => leerParams(cfg.id));
  const [colVar, setColVar] = useState(() => entre(P.get("var"), cfg.variables.map((v) => v.col), cfg.variable));
  const [temporada, setTemporada] = useState(() => {
    const i = T.temporadas.indexOf(P.get("t"));
    return i >= 0 ? i : T.temporadas.length - 1;
  });
  const [nivel, setNivel] = useState(() => entre(P.get("nivel"), T.niveles, "todos"));
  const [fijados, setFijados] = useState(() => P.getAll("fijar").map((n) => T.nombres.indexOf(n)).filter((j) => j >= 0).slice(-MAX_FIJOS));
  usePublicarParams(cfg.id, {
    var: colVar === cfg.variable ? null : colVar,
    t: T.temporadas[temporada],
    nivel: nivel === "todos" ? null : nivel,
    fijar: fijados.map((j) => T.nombres[j]),
  });
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
  // Las temporadas en las que la variable tiene dato (el ELO de la temporada en curso todavía no existe). Si la elegida
  // no está, se muestra la última que sí.
  const temporadasOk = useMemo(() => {
    const ts = new Set();
    for (let r = 0; r < T.n; r++) if (col[r] != null) ts.add(T.f.t[r]);
    return [...ts].sort((a, b) => a - b);
  }, [T, col]);
  const tEf = temporadasOk.includes(temporada) ? temporada : temporadasOk[temporadasOk.length - 1];
  const colores = useMemo(() => T.ligas.map((l) => T.colores[modo === "dark" ? "oscuro" : "claro"][l]), [T, modo]);

  // El rango de cada variable: de TODAS las temporadas y niveles, con margen (más arriba que abajo: ahí cabe el enjambre
  // sin pegarse al borde).
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
      if (T.f.t[r] !== tEf || col[r] == null) continue;
      if (nivelIdx >= 0 && T.f.v[r] !== nivelIdx) continue;
      out.push(r);
    }
    return out;
  }, [T, col, tEf, nivelIdx]);

  const porLiga = useMemo(() => T.ligas.map((_, li) => filas.filter((r) => T.f.l[r] === li)), [T, filas]);
  const cajas = useMemo(() => porLiga.map((rs) => {
    const s = estadisticas(rs.map((r) => col[r]));
    return s && { ...s, dec: v.dec };
  }), [porLiga, col, v.dec]);

  // El lugar de cada equipo: x en unidades del eje (la liga + el desplazamiento del enjambre), y el valor.
  const puestos = useMemo(() => {
    const unidad = area.width ? area.width / (X1 - X0) : 0;
    return porLiga.map((rs, li) => {
      const ys = rs.map((r) => (area.height ? area.height * (1 - (col[r] - dominioY[0]) / (dominioY[1] - dominioY[0])) : 0));
      const dx = unidad ? enjambre(ys) : ys.map(() => 0);
      return rs.map((r, k) => ({ r, x: li + 1 + (unidad ? dx[k] / unidad : 0), y: col[r] }));
    });
  }, [porLiga, col, dominioY, area.width, area.height]);
  const series = useMemo(() => T.ligas.map((liga, li) => ({
    id: liga, type: "scatter", label: liga, color: colores[li], markerSize: 4, highlightScope: { highlight: "item", fade: "none" },
    data: puestos[li].map((p) => ({ x: p.x, y: p.y, id: p.r })),
  })), [T, colores, puestos]);
  const idsPorSerie = useMemo(() => Object.fromEntries(T.ligas.map((liga, li) => [liga, porLiga[li]])), [T, porLiga]);

  // Los equipos resaltados que tienen punto en esta vista (uno puede no jugar esa temporada o caer fuera del filtro de nivel).
  const filaDeJug = useMemo(() => new Map(filas.map((r) => [T.f.j[r], r])), [T, filas]);
  const fijos = useMemo(() => new Set(fijados.map((j) => filaDeJug.get(j)).filter((r) => r != null)), [fijados, filaDeJug]);
  const pinCtx = useMemo(() => ({ ids: idsPorSerie, fijos }), [idsPorSerie, fijos]);
  const etiquetas = useMemo(() => puestos.flat().filter((p) => fijos.has(p.r)).map((p) => ({ id: p.r, x: p.x, y: p.y, texto: T.nombre(p.r) })), [puestos, fijos, T]);
  const opciones = useMemo(() => [...filaDeJug.keys()].sort((a, b) => T.nombres[a].localeCompare(T.nombres[b], "es")), [filaDeJug, T]);
  const onClicPunto = useCallback((_e, { seriesId, dataIndex }) => {
    const r = idsPorSerie[seriesId] ? idsPorSerie[seriesId][dataIndex] : null;
    if (r == null) return;
    const j = T.f.j[r];
    setFijados((p) => (p.includes(j) ? p.filter((x) => x !== j) : [...p, j].slice(-MAX_FIJOS)));
  }, [idsPorSerie, T]);

  const ctx = useMemo(() => ({
    info: (r) => ({ nombre: T.nombre(r), sub: `${T.liga(r)} · ${tTemp(T, tEf)}`, color: colores[T.f.l[r]],
      etiqueta: v.label, valor: col[r].toFixed(v.dec) }),
  }), [T, colores, v, col, tEf]);

  const alto = Math.max(380, Math.min(560, Math.round(ancho * 0.58)));
  const tLabel = T.temporadas[tEf];
  // En pantalla angosta los nombres de dos palabras se parten ("Premier / League").
  const estrecho = ancho > 0 && ancho < 640;
  const etiquetaLiga = (x) => {
    const i = Math.round(x) - 1;
    if (Math.abs(x - Math.round(x)) > 1e-6 || !T.ligas[i]) return "";
    return estrecho ? T.ligas[i].replace(" ", "\n") : T.ligas[i];
  };
  const claveDatos = `${colVar}|${tEf}|${nivel}`;
  const descargar = () => descargarPng({
    ...capturar(caja, { limpiar: limpiarDispersion(tk, { apagado: true, oscuro: modo === "dark" }) }),
    titulo: v.label, subtitulo: [T.enCurso && T.enCurso[tLabel] ? `${tLabel} (en curso)` : tLabel, nivel !== "todos" ? nivel : null].filter(Boolean).join(" · "),
    fuente: `Datos: ${cfg.fuente}`, tk, modo, archivo: nombreArchivo(cfg.id, v.label, tLabel),
  });

  return (
    <FilaCtx.Provider value={ctx}>
      <Box sx={{ display: "grid", gap: 3, gridTemplateColumns: { xs: "minmax(0,1fr)", md: "minmax(0,1fr) 270px" }, alignItems: "start" }}>
        <Box sx={{ minWidth: 0 }}>
          <Encabezado pregunta={cfg.pregunta} titulo={cfg.titulo} bajada={cfg.bajada}
            muestra={cfg.subtitulo.replace("{variable}", v.label).replace("{temporada}",
              T.enCurso && T.enCurso[tLabel] ? `${tLabel} (en curso, ${T.enCurso[tLabel]} jornadas)` : tLabel)} />
          <Box ref={setCaja} className="rx-chart" sx={{
            position: "relative", width: "100%", userSelect: "none",
            "& .MuiChartsAxis-tickLabel": { fill: tk["text-body"], fontSize: 12, fontWeight: 600 },
            "& .MuiChartsAxis-label": { fill: tk["text-body"], fontSize: 12.5, fontWeight: 600 },
            "& .MuiChartsAxis-line, & .MuiChartsAxis-tick": { stroke: tk.border },
            "& .MuiChartsGrid-line": { stroke: tk.border, strokeOpacity: 0.7 },
          }}>
            <EstilosGrafica />
            {ancho > 0 && (
              <PinCtx.Provider value={pinCtx}>
                <ScatterChart
                  key={claveDatos}
                  height={alto}
                  series={series}
                  xAxis={[{ id: "x", scaleType: "linear", min: X0, max: X1, tickInterval: [1, 2, 3, 4, 5],
                    valueFormatter: etiquetaLiga, height: estrecho ? 46 : 40,
                    // MUI esconde una marca si su texto roza a la vecina; con cinco ligas en ~290 px las
                    // etiquetas llegan justas, así que en pantalla angosta van más chicas y sin holgura mínima.
                    tickLabelMinGap: estrecho ? 0 : 4, tickLabelStyle: estrecho ? { fontSize: 10.5 } : undefined }]}
                  yAxis={[{ id: "y", scaleType: "linear", min: dominioY[0], max: dominioY[1], label: v.label, width: 58,
                    valueFormatter: (y) => String(Number(y.toFixed(2))), tickNumber: 7 }]}
                  margin={{ top: 10, right: estrecho ? 26 : 14, bottom: 6, left: 6 }}
                  grid={{ horizontal: true }}
                  hideLegend skipAnimation hitAreaRadius={14}
                  onItemClick={onClicPunto}
                  slots={{ marker: Marcador, tooltip: PuntoTooltip }}>
                  <CapaBandas cajas={cajas} ligasX={T.ligas} dominioY={dominioY} colores={colores} tk={tk} onArea={setArea} etiquetas={etiquetas} />
                </ScatterChart>
              </PinCtx.Provider>
            )}
            {filas.length === 0 && ancho > 0 && (
              <Box role="status" sx={{ position: "absolute", left: 0, right: 0, top: "42%", textAlign: "center", color: "text.secondary", fontSize: 13.5 }}>
                Ningún equipo con estos filtros.
              </Box>
            )}
          </Box>
          <Box sx={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", gap: 1, mt: 0.75 }}>
            <Typography sx={{ fontSize: 12, color: "text.secondary" }}>
              La raya es la mediana · la banda, la mitad central de los equipos · cada punto, un equipo · clic en un punto para resaltarlo
            </Typography>
            <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
              <Typography sx={{ fontSize: 12, color: "text.secondary" }}>Datos: {cfg.fuente}</Typography>
              <BotonDescarga alDescargar={descargar} />
            </Box>
          </Box>
        </Box>

        {/* Los controles: a la derecha en escritorio; ARRIBA del gráfico en móvil (son pocos y se usan primero). */}
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
            <ToggleButtonGroup exclusive size="small" fullWidth value={tEf} aria-label="Temporada"
              onChange={(_e, x) => x != null && setTemporada(x)}>
              {temporadasOk.map((i) => (
                <ToggleButton key={i} value={i} aria-label={T.temporadas[i]} sx={{ px: 0.5, fontSize: "11.5px !important" }}>{T.temporadas[i].slice(2)}</ToggleButton>
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
          <Box>
            <Rotulo>Resaltar equipos</Rotulo>
            <Autocomplete multiple size="small" options={opciones}
              filterOptions={(ops, { inputValue }) => {
                const q = sinAcentos(inputValue.trim());
                return ops.filter((j) => sinAcentos(T.nombres[j]).includes(q)).slice(0, 40);
              }}
              value={fijados}
              onChange={(_e, nuevo) => setFijados(nuevo.slice(-MAX_FIJOS))}
              getOptionLabel={(j) => T.nombres[j]}
              isOptionEqualToValue={(a, b) => a === b}
              disableCloseOnSelect filterSelectedOptions
              noOptionsText="Ningún equipo con esos filtros"
              renderValue={(valor, getItemProps) => valor.map((j, i) => {
                const { key, ...props } = getItemProps({ index: i });
                const sinPunto = !filaDeJug.has(j);
                return (
                  <Chip key={key} size="small" label={T.nombres[j]} {...props}
                    variant={sinPunto ? "outlined" : "filled"}
                    title={sinPunto ? `${T.nombres[j]} — no tiene punto en esta temporada o con estos filtros` : T.nombres[j]}
                    sx={{ fontSize: 11.5, opacity: sinPunto ? 0.6 : 1, borderStyle: sinPunto ? "dashed" : "solid" }} />
                );
              })}
              renderInput={(p) => <TextField {...p} placeholder={fijados.length ? "" : "Escribe un equipo…"} />} />
          </Box>
        </Box>
      </Box>

      <Box sx={{ mt: 3, maxWidth: 1040 }}>
        <Rotulo>Cómo leer la gráfica</Rotulo>
        <ComoLeer texto={cfg.queMirar} />
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
