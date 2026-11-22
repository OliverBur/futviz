// «De dónde sale el xG»: una barra apilada por equipo con el reparto de su xG entre córner, tiro libre directo, otro
// balón parado y jugada abierta, a favor o en contra, en % del xG o en xG por partido.
//
// El cálculo (xG por segmento, sin penales) está hecho en el build (`web/charts/origen_xg.py`); aquí se dibuja lo que
// viaja en `datos-origen-xg.js` y se arma el texto «Con estos filtros» (`origenXgLectura.js`). SVG propio, en el mismo
// lenguaje que el resto de las gráficas (rejilla suave, ejes en gris, números en el hover).
import { useEffect, useMemo, useRef, useState } from "react";
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
import { entre, leerParams, usePublicarParams } from "./urlEstado.js";
import { useSitioTema } from "./theme.jsx";
import { cargarDatos } from "./datos.js";
import { Aviso, ComoLeer, Cargando, Encabezado, Md, Parrafos, QueDice, Rotulo, sinAcentos } from "./ui.jsx";
import { conAlfa } from "./colores.js";
import { fmt, miles } from "./stats.js";
import { BotonDescarga } from "./BotonDescarga.jsx";
import { capturar, descargarPng, nombreArchivo } from "./descargarImagen.js";
import {
  APILADO, BALON_PARADO, lecturaOrigen, pesoBP, tirosSeg, tirosTotal, valorOrden, valorSeg, xgTotal,
} from "./origenXgLectura.js";

const TODAS = -1;                    // "Las 5 ligas"
const MG_SUP = 36, MG_INF = 26;      // el eje de arriba y el de abajo (el de abajo solo con muchas filas)
const FILAS_IMAGEN = 10;             // con las 5 ligas juntas, la imagen lleva solo las primeras filas (96 barras no se leen)
const FILAS_ALTAS = 24;              // con más filas que estas, la barra es más baja y el eje se repite abajo

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

// El máximo del xG total por partido de TODAS las filas de temporadas cerradas (la en curso puede pasarse: ahí la escala crece), a favor y en contra: la escala del modo «xG por partido» no
// cambia al cambiar de temporada, de liga ni de lado, y las barras se pueden comparar entre vistas.
function techoXg(D) {
  let m = 0;
  for (let i = 0; i < D.n; i++) if (!D.enCurso || !D.enCurso[D.temporadas[D.f.t[i]]]) for (const lado of ["f", "c"]) m = Math.max(m, xgTotal(D, i, lado) / D.c.pj[i]);
  return Math.ceil(m * 2) / 2;
}

function Vista({ cfg, D, modo: tema, tk }) {
  const [P] = useState(() => leerParams(cfg.id));
  const ligas = D.ligas;
  const enCurso = D.enCurso || {};
  const cerradas = D.temporadas.map((t, i) => i).filter((i) => !enCurso[D.temporadas[i]]);
  const ultimaCerrada = cerradas.length ? cerradas[cerradas.length - 1] : D.temporadas.length - 1;
  const ligaIni = Math.max(0, ligas.indexOf("Premier League"));

  const [t, setT] = useState(() => { const i = D.temporadas.indexOf(P.get("t")); return i >= 0 ? i : D.temporadas.length - 1; });   // abre en la temporada actual
  const [liga, setLiga] = useState(() => {
    if (P.get("liga") === "todas") return TODAS;
    const i = ligas.indexOf(P.get("liga"));
    return i >= 0 ? i : ligaIni;
  });
  const [lado, setLado] = useState(() => entre(P.get("lado"), ["f", "c"], "f"));
  const [medida, setMedida] = useState(() => entre(P.get("medida"), ["pct", "xg"], "xg"));
  const ordenes = ["bp", ...APILADO];
  const [orden, setOrden] = useState(() => entre(P.get("orden"), ordenes, "abierta"));
  const [fijado, setFijado] = useState(() => { const j = D.nombres.indexOf(P.get("equipo")); return j >= 0 ? j : -1; });
  const [hover, setHover] = useState(null);       // {i, px, py}
  const caja = useRef(null);
  const svgRef = useRef(null);
  const w = useAncho(caja);
  const movil = w > 0 && w < 560;

  usePublicarParams(cfg.id, {
    t: D.temporadas[t], liga: liga === TODAS ? "todas" : (liga === ligaIni ? null : ligas[liga]),
    lado: lado === "f" ? null : lado, medida: medida === "pct" ? null : medida,
    orden: orden === "bp" ? null : orden, equipo: fijado >= 0 ? D.nombres[fijado] : null,
  });

  const tLabel = D.temporadas[t];
  const jornadas = enCurso[tLabel] || null;
  const etiquetaSeg = Object.fromEntries(cfg.segmentos.map((s) => [s.id, s.etiqueta]));
  const colorSeg = (id) => (id === "abierta"
    ? conAlfa(tk.muted, tema === "dark" ? 0.3 : 0.42)
    : cfg.colores[tema === "dark" ? "oscuro" : "claro"][id]);
  const colorLiga = (l) => cfg.ligasColores[tema === "dark" ? "oscuro" : "claro"][ligas[l]];
  const techo = useMemo(() => techoXg(D), [D]);

  // Las filas de la temporada (todas las ligas) y las que se ven.
  const deTemporada = useMemo(() => {
    const out = [];
    for (let i = 0; i < D.n; i++) if (D.f.t[i] === t) out.push(i);
    return out;
  }, [D, t]);
  const nombreFila = (i) => D.nombres[D.f.j[i]];
  const filas = useMemo(() => deTemporada.filter((i) => liga === TODAS || D.f.l[i] === liga), [deTemporada, liga, D]);
  const ordenadas = useMemo(() => [...filas].sort((a, b) => {
    const d = valorOrden(D, b, lado, orden, medida) - valorOrden(D, a, lado, orden, medida);
    return d || nombreFila(a).localeCompare(nombreFila(b), "es");
  }), [filas, D, lado, orden, medida]);
  const filaFijada = fijado >= 0 ? filas.find((i) => D.f.j[i] === fijado) ?? -1 : -1;
  const ambito = liga === TODAS ? "las 5 ligas" : ligas[liga];
  const lectura = useMemo(() => lecturaOrigen({
    D, filas, ambito, temporada: tLabel, jornadas, fijada: filaFijada,
  }), [D, filas, ambito, tLabel, jornadas, filaFijada]);

  // --- geometría ---
  const alta = ordenadas.length > FILAS_ALTAS;
  const hFila = alta ? 17 : (movil ? 24 : 26);
  const fuente = alta ? 11 : (movil ? 11.5 : 12.5);
  const wEt = movil ? 126 : 156;
  const wVal = movil ? 40 : 48;
  const pw = Math.max(80, w - wEt - wVal - 8);
  const maxVisible = ordenadas.reduce((m, i) => Math.max(m, xgTotal(D, i, lado) / D.c.pj[i]), 0);
  const tope = medida === "pct" ? 100 : Math.max(techo, Math.ceil(maxVisible * 2) / 2);
  const x = (v) => wEt + (pw * v) / tope;
  const alto = MG_SUP + ordenadas.length * hFila + (alta ? MG_INF : 8);
  const paso = medida === "pct" ? (movil ? 50 : 25) : (movil ? 1 : 0.5);
  const marcas = Array.from({ length: Math.floor(tope / paso + 1e-9) + 1 }, (_, k) => k * paso);
  const fmtMarca = (v) => (medida === "pct" ? `${v}%` : fmt(v, 1));
  const maxChars = Math.floor((wEt - 6) / (fuente * 0.54));
  const corto = (s) => (s.length > maxChars ? `${s.slice(0, maxChars - 1)}…` : s);

  const ladoTxt = lado === "f" ? "A favor" : "En contra";
  const ordenTxt = orden === "bp" ? "balón parado (los tres juntos)" : etiquetaSeg[orden].toLowerCase();
  const encabezadoOrden = orden === "bp" ? "Balón parado" : etiquetaSeg[orden];

  const filaDe = (e) => {
    const r = e.currentTarget.getBoundingClientRect();
    const k = Math.floor((e.clientY - r.top - MG_SUP) / hFila);
    return k < 0 || k >= ordenadas.length ? null : k;
  };
  const mover = (e) => {
    const k = filaDe(e);
    setHover(k == null ? null : { i: ordenadas[k], k, px: e.clientX, py: e.clientY });
  };
  const salir = (e) => { if (e.pointerType === "mouse") setHover(null); };

  // Al elegir un equipo del buscador: si no está en la liga que se ve, se pasa a la suya y se lleva a la vista.
  const elegir = (j) => {
    setFijado(j);
    if (j < 0) return;
    const f = deTemporada.find((i) => D.f.j[i] === j);
    if (f != null && liga !== TODAS && D.f.l[f] !== liga) setLiga(D.f.l[f]);
  };
  useEffect(() => {
    if (fijado < 0 || !alta || !svgRef.current) return;
    const k = ordenadas.findIndex((i) => D.f.j[i] === fijado);
    if (k < 0) return;
    const y = svgRef.current.getBoundingClientRect().top + MG_SUP + k * hFila;
    if (y < 80 || y > window.innerHeight - 80) window.scrollTo({ top: window.scrollY + y - window.innerHeight / 2, behavior: "smooth" });
  }, [fijado]);   // eslint-disable-line react-hooks/exhaustive-deps

  // --- el tooltip ---
  const tip = hover && (() => {
    const i = hover.i;
    const tot = xgTotal(D, i, lado), pj = D.c.pj[i];
    return (
      <Paper elevation={4} className="rx-tooltip" sx={{
        position: "fixed", left: Math.max(8, Math.min(hover.px + 14, window.innerWidth - 292)), top: Math.min(hover.py + 14, window.innerHeight - 250),
        p: 1.25, pointerEvents: "none", zIndex: 1500, border: 1, borderColor: "divider", fontSize: 12.5, width: 278,
      }}>
        <Box sx={{ fontWeight: 700 }}>{nombreFila(i)}</Box>
        <Box sx={{ color: "text.secondary", fontSize: 11.5, mb: 0.5 }}>
          {liga === TODAS ? `${ligas[D.f.l[i]]} · ` : ""}{ladoTxt} · {tLabel} · {pj} partidos
        </Box>
        {APILADO.map((id) => (
          <Box key={id} sx={{ display: "flex", gap: 0.75, alignItems: "baseline" }}>
            <Box component="span" sx={{ width: 9, height: 9, borderRadius: "2px", bgcolor: colorSeg(id), flex: "none", alignSelf: "center" }} />
            <Box sx={{ flex: 1 }}>
              <strong>{etiquetaSeg[id]}</strong>
              <Box sx={{ color: "text.secondary", fontSize: 11.5, mb: 0.25 }}>
                {fmt(valorSeg(D, i, lado, id, "xg"), 2)} xG por partido · {fmt(valorSeg(D, i, lado, id, "pct"), 1)}% · {miles(tirosSeg(D, i, lado, id))} tiros
              </Box>
            </Box>
          </Box>
        ))}
        <Box sx={{ mt: 0.5, pt: 0.5, borderTop: 1, borderColor: "divider" }}>
          <strong>Total {fmt(tot / pj, 2)} xG por partido</strong>
          <Box component="span" sx={{ color: "text.secondary" }}> · {miles(tirosTotal(D, i, lado))} tiros</Box>
          <Box sx={{ color: "text.secondary" }}>Balón parado: {fmt(pesoBP(D, i, lado), 1)}% del xG</Box>
        </Box>
      </Paper>
    );
  })();

  const resumen = ordenadas.length
    ? `Barras apiladas: de dónde sale el xG ${lado === "f" ? "a favor" : "en contra"} de ${ordenadas.length} equipos de ${ambito} en ${tLabel}, ` +
      `en ${medida === "pct" ? "porcentaje del xG" : "xG por partido"}, ordenados por ${ordenTxt}. Primero ${nombreFila(ordenadas[0])} con ` +
      `${fmt(valorOrden(D, ordenadas[0], lado, orden, medida), medida === "pct" ? 0 : 2)}${medida === "pct" ? "%" : ""}; ` +
      `último ${nombreFila(ordenadas[ordenadas.length - 1])} con ${fmt(valorOrden(D, ordenadas[ordenadas.length - 1], lado, orden, medida), medida === "pct" ? 0 : 2)}${medida === "pct" ? "%" : ""}.`
    : "Sin equipos con estos filtros.";

  const equiposBuscador = useMemo(() => [...new Set(deTemporada.map((i) => D.f.j[i]))]
    .sort((a, b) => D.nombres[a].localeCompare(D.nombres[b], "es")), [deTemporada, D]);
  const cuentaLiga = (l) => deTemporada.filter((i) => D.f.l[i] === l).length;
  const ordenarPorLeyenda = (id) => setOrden(orden === id ? "bp" : id);
  const muestra = `${ambito} · ${tLabel}${jornadas ? ` (en curso, ${jornadas} jornadas)` : ""} · ${ladoTxt.toLowerCase()} · sin penales`;

  // La imagen: las barras tal como están en pantalla. Con las 5 ligas juntas son 96 filas, así que solo salen las primeras 10.
  const recorta = liga === TODAS && ordenadas.length > FILAS_IMAGEN;
  const descargar = () => {
    const cap = capturar(caja.current, { limpiar: (el) => (recorta && Number(el.getAttribute("data-fila")) >= FILAS_IMAGEN ? "quitar" : undefined) });
    if (recorta) cap.viewBox = [0, 0, cap.viewBox[2], MG_SUP + FILAS_IMAGEN * hFila + 8];
    return descargarPng({
      ...cap,
      titulo: cfg.titulo,
      subtitulo: `${ambito} · ${tLabel}${jornadas ? " (en curso)" : ""} · ${ladoTxt.toLowerCase()} · sin penales`,
      nota: `${medida === "pct" ? "% del xG" : "xG por partido"}${recorta ? ` · los ${FILAS_IMAGEN} primeros` : ""}`,
      leyenda: APILADO.map((id) => ({ color: colorSeg(id), texto: etiquetaSeg[id] })),
      fuente: `Datos: ${cfg.fuente}`, tk, modo: tema,
      archivo: nombreArchivo("generan-peligro", ambito, tLabel, lado === "f" ? "a-favor" : "en-contra"),
    });
  };

  return (
    <>
      <Box sx={{ display: "grid", gap: 3, gridTemplateColumns: { xs: "minmax(0,1fr)", md: "minmax(0,1fr) 270px" }, alignItems: "start" }}>
        <Box sx={{ minWidth: 0 }}>
          <Encabezado pregunta={cfg.pregunta} titulo={cfg.titulo} bajada={cfg.bajada} muestra={muestra} />

          {fijado >= 0 && filaFijada < 0 && (
            <Typography sx={{ fontSize: 12.5, color: "text.secondary", mb: 1 }}>
              {D.nombres[fijado]} no tiene barra en {ambito} · {tLabel}.
            </Typography>
          )}

          {/* --- las barras --- */}
          <Box ref={caja} sx={{ maxWidth: 1000, width: "100%", position: "relative" }}>
            {w > 0 && (
              <svg ref={svgRef} role="img" aria-label={resumen} width={w} height={alto}
                onPointerMove={(e) => mover(e)} onPointerDown={(e) => mover(e)} onPointerLeave={salir}
                style={{ display: "block", touchAction: "pan-y" }}>
                {/* rejilla y eje (arriba, y abajo si son muchas filas) */}
                <g fontSize={11} fill={tk.muted}>
                  {marcas.map((v) => (
                    <g key={v}>
                      <line x1={x(v)} x2={x(v)} y1={MG_SUP - 6} y2={MG_SUP + ordenadas.length * hFila} stroke={tk.border} strokeOpacity={0.9} />
                      <text x={x(v)} y={MG_SUP - 10} textAnchor={v === tope ? "end" : v === 0 ? "start" : "middle"}>{fmtMarca(v)}</text>
                      {alta && <text x={x(v)} y={MG_SUP + ordenadas.length * hFila + 16} textAnchor={v === tope ? "end" : v === 0 ? "start" : "middle"}>{fmtMarca(v)}</text>}
                    </g>
                  ))}
                  <text x={w} y={11} textAnchor="end" fontWeight={700}>{encabezadoOrden}</text>
                </g>
                {ordenadas.map((i, k) => {
                  const y = MG_SUP + k * hFila;
                  const pinta = fijado >= 0 && D.f.j[i] === fijado;
                  const apagada = fijado >= 0 && !pinta;
                  const enHover = hover && hover.i === i;
                  let acum = 0;
                  return (
                    <g key={i} data-fila={k} opacity={apagada && !enHover ? 0.38 : 1}>
                      {(pinta || enHover) && <rect x={0} y={y} width={w} height={hFila} fill={conAlfa(tk.primary, pinta ? 0.13 : 0.07)} rx={3} />}
                      <text x={2} y={y + hFila / 2 + fuente * 0.35} fontSize={fuente} fill={tk["text-body"]}
                        fontWeight={pinta ? 700 : 500}>{corto(nombreFila(i))}</text>
                      {APILADO.map((id) => {
                        const v = valorSeg(D, i, lado, id, medida);
                        const x1 = x(acum);
                        acum += v;
                        return <rect key={id} x={x1} y={y + (alta ? 2 : 3)} width={Math.max(0, x(acum) - x1)} height={hFila - (alta ? 4 : 6)}
                          fill={colorSeg(id)} stroke={tk.surface} strokeWidth={1} />;
                      })}
                      <text x={w} y={y + hFila / 2 + 4} fontSize={fuente} textAnchor="end" fill={tk["text-body"]} fontWeight={pinta ? 700 : 500}>
                        {medida === "pct" ? `${fmt(valorOrden(D, i, lado, orden, medida), 0)}%` : fmt(valorOrden(D, i, lado, orden, medida), 2)}
                      </text>
                    </g>
                  );
                })}
              </svg>
            )}
            {tip}
          </Box>

          <Box sx={{ mt: 1, display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 1, maxWidth: 1000 }}>
            <Typography sx={{ fontSize: 12, color: "text.secondary" }}>
              Cada barra mide el xG sin penales de un equipo en una temporada{Object.keys(enCurso).length ? ". * Temporada en curso" : ""}.
            </Typography>
            <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
              <Typography sx={{ fontSize: 12, color: "text.secondary" }}>Datos: {cfg.fuente}</Typography>
              <BotonDescarga alDescargar={descargar} />
            </Box>
          </Box>

        </Box>
        <Box sx={{ display: "flex", flexDirection: "column", gap: 2.25, order: { xs: -1, md: 0 } }}>
          {/* --- controles --- */}
          <Box sx={{ display: "grid", gap: 2.25 }}>
            <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1.5, alignItems: "flex-end", justifyContent: "space-between" }}>
              <Box role="group" aria-label="Filtrar por liga" sx={{ display: "flex", flexWrap: "wrap", gap: 0.75 }}>
                {[TODAS, ...ligas.map((_, l) => l)].map((l) => {
                  const on = liga === l;
                  const color = l === TODAS ? tk.primary : colorLiga(l);
                  return (
                    <Chip key={l} size="small" clickable variant={on ? "filled" : "outlined"} aria-pressed={on}
                      onClick={() => { setLiga(l); setHover(null); }}
                      label={l === TODAS ? `Las 5 ligas · ${deTemporada.length}` : `${ligas[l]} · ${cuentaLiga(l)}`}
                      avatar={l === TODAS ? undefined : <Box component="span" sx={{ width: "10px !important", height: "10px !important",
                        borderRadius: "50%", bgcolor: color, ml: "8px !important" }} />}
                      sx={{ bgcolor: on ? conAlfa(color, 0.16) : "transparent", color: on ? "text.primary" : "text.secondary",
                        borderColor: on ? color : "divider" }} />
                  );
                })}
              </Box>
              {movil ? (
                <TextField select size="small" label="Temporada" value={t} onChange={(e) => { setT(Number(e.target.value)); setHover(null); }}
                  slotProps={{ select: { native: true }, htmlInput: { "aria-label": "Temporada" } }} sx={{ minWidth: 150 }}>
                  {D.temporadas.map((s, i) => <option key={s} value={i}>{s}{enCurso[s] ? " (en curso)" : ""}</option>)}
                </TextField>
              ) : (
                <Box>
                  <Rotulo>Temporada</Rotulo>
                  <ToggleButtonGroup exclusive size="small" value={t} aria-label="Temporada" sx={{ flexWrap: "wrap" }}
                    onChange={(_e, v) => { if (v != null) { setT(v); setHover(null); } }}>
                    {D.temporadas.map((s, i) => (
                      <ToggleButton key={s} value={i} aria-label={`${s}${enCurso[s] ? " (en curso)" : ""}`} sx={{ px: 1, flex: "1 0 30%", whiteSpace: "nowrap" }}>
                        {s.slice(2)}{enCurso[s] ? "*" : ""}
                      </ToggleButton>
                    ))}
                  </ToggleButtonGroup>
                </Box>
              )}
            </Box>

            <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1.5, alignItems: "flex-end" }}>
              <Box>
                <Rotulo>Tiros</Rotulo>
                <ToggleButtonGroup exclusive size="small" value={lado} aria-label="A favor o en contra"
                  onChange={(_e, v) => v && setLado(v)}>
                  <ToggleButton value="f">A favor</ToggleButton>
                  <ToggleButton value="c">En contra</ToggleButton>
                </ToggleButtonGroup>
              </Box>
              <Box>
                <Rotulo>Mostrar</Rotulo>
                <ToggleButtonGroup exclusive size="small" value={medida} aria-label="Porcentaje o xG por partido"
                  onChange={(_e, v) => v && setMedida(v)}>
                  <ToggleButton value="pct">% del xG</ToggleButton>
                  <ToggleButton value="xg">xG por partido</ToggleButton>
                </ToggleButtonGroup>
              </Box>
              <Box sx={{ minWidth: 190 }}>
                <Rotulo>Ordenar por</Rotulo>
                <TextField select size="small" fullWidth value={orden} onChange={(e) => setOrden(e.target.value)}
                  slotProps={{ htmlInput: { "aria-label": "Ordenar por" } }}>
                  <MenuItem value="bp" sx={{ fontSize: 13 }}>Balón parado (los tres)</MenuItem>
                  {APILADO.map((id) => <MenuItem key={id} value={id} sx={{ fontSize: 13 }}>{etiquetaSeg[id]}</MenuItem>)}
                </TextField>
              </Box>
              <Box sx={{ minWidth: 200, flex: "1 1 200px", maxWidth: 300 }}>
                <Rotulo>Resaltar un equipo</Rotulo>
                <Autocomplete size="small" options={equiposBuscador} value={fijado >= 0 && equiposBuscador.includes(fijado) ? fijado : null}
                  onChange={(_e, v) => elegir(v == null ? -1 : v)}
                  getOptionLabel={(j) => D.nombres[j]} isOptionEqualToValue={(a, b) => a === b}
                  filterOptions={(opciones, { inputValue }) => {
                    const q = sinAcentos(inputValue.trim());
                    return opciones.filter((j) => sinAcentos(D.nombres[j]).includes(q));
                  }}
                  noOptionsText="Ningún equipo con ese nombre"
                  renderInput={(p) => <TextField {...p} placeholder="Busca un equipo" slotProps={{ ...p.slotProps, htmlInput: { ...(p.slotProps && p.slotProps.htmlInput), "aria-label": "Resaltar un equipo" } }} />} />
              </Box>
            </Box>

            {/* leyenda: también es el control de orden */}
            <Box role="group" aria-label="Segmentos: clic para ordenar por uno" sx={{ display: "flex", flexWrap: "wrap", gap: 0.75, alignItems: "center" }}>
              {APILADO.map((id) => {
                const on = orden === id;
                return (
                  <Chip key={id} size="small" clickable aria-pressed={on} variant={on ? "filled" : "outlined"}
                    onClick={() => ordenarPorLeyenda(id)}
                    title={on ? "Ordenado por este segmento. Clic para volver a balón parado" : `Ordenar por ${etiquetaSeg[id].toLowerCase()}`}
                    label={etiquetaSeg[id]}
                    avatar={<Box component="span" sx={{ width: "11px !important", height: "11px !important", borderRadius: "3px",
                      bgcolor: colorSeg(id), ml: "8px !important" }} />}
                    sx={{ bgcolor: on ? conAlfa(tk.primary, 0.12) : "transparent", color: "text.primary", borderColor: on ? tk.primary : "divider" }} />
                );
              })}
            </Box>
          </Box>

        </Box>
      </Box>

      <Box sx={{ mt: 2, maxWidth: 1040 }}>
        <Rotulo>Cómo leer la gráfica</Rotulo>
        <ComoLeer texto={cfg.queMirar} />
        <QueDice texto={lectura[0]} />
      </Box>
    </>
  );
}

export default function OrigenXgVista({ id }) {
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
