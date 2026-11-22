// Tabla real vs. esperada: por liga y temporada, una fila por equipo (en el orden de la tabla real) con dos marcadores,
// los puntos reales y los esperados (xPts), unidos por una línea.
//
// Todo el cálculo está hecho en el build (`web/charts/tabla_esperada.py`): aquí solo se dibuja lo que viaja en
// `datos-tabla-esperada.js` y se arma el texto de la liga y temporada elegidas (`tablaEsperadaLectura.js`).
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
import { Aviso, ComoLeer, Cargando, Encabezado, Md, Parrafos, QueDice, Rotulo } from "./ui.jsx";
import { TOPE_DIF, colorRendimiento, conAlfa, divergente } from "./colores.js";
import { BotonDescarga } from "./BotonDescarga.jsx";
import { BarraFiltros, Campo, SelectTemporada, SelectUno } from "./Filtros.jsx";
import { capturar, descargarPng, nombreArchivo } from "./descargarImagen.js";
import { conSigno, d1, extremos, filasDe, lecturaTabla } from "./tablaEsperadaLectura.js";

const TOPE_PTS = 12;               // desde cuántos puntos de diferencia el color llega a su máximo
const HEAD = 26, EJE = 30;         // alto del encabezado de columnas y del eje de abajo
const R_MARCA = 5.5;

const menos = (s) => s.replace("-", "−");

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

const recorta = (s, max) => (s.length > max ? `${s.slice(0, Math.max(1, max - 1))}…` : s);

// Un color por el signo de la diferencia, con la escala divergente del sitio (azul = más de lo esperado, rojo =
// menos). `colorRendimiento` mide la diferencia en goles (tope `TOPE_DIF`); aquí son puntos, y se reescala para que
// 12 puntos sea el máximo. Hay un piso para que una diferencia chica no quede gris sobre el fondo: el signo se lee
// igual por el orden de los marcadores y por el texto.
function colorDe(dif, div) {
  const t = 0.3 + 0.7 * Math.min(1, Math.abs(dif) / TOPE_PTS);
  return colorRendimiento((dif >= 0 ? 1 : -1) * t * TOPE_DIF, div);
}

// Marcas del eje: cada 5, 10 o 20 puntos según el rango y el ancho disponible.
function marcas(lo, hi, pw) {
  const rango = hi - lo;
  const paso = rango <= 30 ? 5 : pw / (rango / 10) >= 30 ? 10 : 20;
  const a = Math.floor(lo / paso) * paso, b = Math.ceil(hi / paso) * paso;
  const out = [];
  for (let v = a; v <= b; v += paso) out.push(v);
  return out;
}

function Leyenda({ tk, div, enCurso }) {
  const azul = colorRendimiento(TOPE_DIF, div), rojo = colorRendimiento(-TOPE_DIF, div);
  const item = (marca, texto) => (
    <Box component="span" sx={{ display: "inline-flex", alignItems: "center", gap: 0.75, mr: 2, whiteSpace: "nowrap" }}>
      {marca}<span>{texto}</span>
    </Box>
  );
  const punto = (relleno, borde) => (
    <svg width={14} height={14} aria-hidden="true"><circle cx={7} cy={7} r={5} fill={relleno} stroke={borde} strokeWidth={2} /></svg>
  );
  const barra = (c) => <svg width={22} height={14} aria-hidden="true"><line x1={2} x2={20} y1={7} y2={7} stroke={c} strokeWidth={3.5} strokeLinecap="round" /></svg>;
  return (
    <Typography component="div" sx={{ fontSize: 12, color: "text.secondary", mb: 1, lineHeight: 1.9 }}>
      {item(punto(enCurso ? tk.muted : azul, enCurso ? tk.muted : azul), "Puntos reales")}
      {item(punto(tk.surface, tk.muted), "Puntos esperados (xPts)")}
      {enCurso
        ? item(barra(tk.muted), "En curso: sin color")
        : <>{item(barra(azul), "Más puntos de los esperados")}{item(barra(rojo), "Menos")}</>}
    </Typography>
  );
}

function Vista({ cfg, D, modo, tk }) {
  const [P] = useState(() => leerParams(cfg.id));
  const [liga, setLiga] = useState(() => entre(P.get("liga"), D.ligas, cfg.ligaInicial));
  const [temporada, setTemporada] = useState(() => entre(P.get("t"), D.temporadas, cfg.temporadaInicial));
  usePublicarParams(cfg.id, {
    liga: liga === cfg.ligaInicial ? null : liga,
    t: temporada === cfg.temporadaInicial ? null : temporada,
  });
  const [hover, setHover] = useState(null);       // {i, px, py}
  const caja = useRef(null);
  const lienzo = useRef(null);      // solo el dibujo: es lo que se captura para la imagen
  const w = useAncho(caja);

  const div = useMemo(() => divergente(modo, D.divergente), [modo, D]);
  const enCurso = D.enCurso[temporada] != null;
  const filas = useMemo(() => filasDe(D, liga, temporada), [D, liga, temporada]);
  const lectura = useMemo(() => lecturaTabla(D, liga, temporada, filas), [D, liga, temporada, filas]);
  const ext = useMemo(() => extremos(filas, D.errorMedio), [filas, D]);

  const compacto = w < 560;
  const RH = compacto ? 30 : 28;
  const POS_W = compacto ? 22 : 28, NOM_W = compacto ? 92 : 150, DER_W = compacto ? 60 : 124, SEP = 8;
  const pl = POS_W + NOM_W + SEP, pr = w - DER_W - SEP;
  const pw = Math.max(60, pr - pl);

  const valores = filas.flatMap((r) => [r.pts, r.xp]);
  const lo = Math.min(...valores) - 2, hi = Math.max(...valores) + 2;
  const ticks = valores.length ? marcas(lo, hi, pw) : [0, 10];
  const x0 = ticks[0], x1 = ticks[ticks.length - 1];
  const x = (v) => pl + (pw * (v - x0)) / (x1 - x0);
  const cy = (i) => HEAD + RH * i + RH / 2;
  const alto = HEAD + RH * filas.length + EJE;

  const filaDe = (e) => {
    const r = e.currentTarget.getBoundingClientRect();
    const i = Math.floor((e.clientY - r.top - HEAD) / RH);
    return i < 0 || i >= filas.length ? null : i;
  };
  const mover = (e) => {
    const i = filaDe(e);
    setHover(i == null ? null : { i, px: e.clientX, py: e.clientY });
  };
  const salir = (e) => { if (e.pointerType === "mouse") setHover(null); };
  const manejadores = { onPointerMove: mover, onPointerDown: mover, onPointerLeave: salir, style: { display: "block", touchAction: "pan-y" } };

  const elegir = (set) => (_e, v) => { if (v) { set(v); setHover(null); } };

  const resumen = filas.length
    ? `${liga} ${temporada}: puntos reales y esperados de ${filas.length} equipos en el orden de la tabla.` +
      (enCurso ? " Temporada en curso, sin conclusiones."
        : ` Con más puntos de los esperados: ${ext.mas.map((r) => `${r.nombre} ${conSigno(r.dif)}`).join(", ") || "ninguno por mucho"}.` +
          ` Con menos: ${ext.menos.map((r) => `${r.nombre} ${conSigno(r.dif)}`).join(", ") || "ninguno por mucho"}.`)
    : "Sin datos.";

  // --- el tooltip ---
  const h = hover && filas[hover.i];
  const tip = h && (
    <Paper elevation={4} className="rx-tooltip" sx={{
      position: "fixed", left: Math.max(8, Math.min(hover.px + 14, window.innerWidth - 270)), top: hover.py + 14,
      p: 1.25, pointerEvents: "none", zIndex: 1500, border: 1, borderColor: "divider", fontSize: 12.5, width: 256,
    }}>
      <Box sx={{ fontWeight: 700, mb: 0.25 }}>{h.nombre}</Box>
      <Box sx={{ color: "text.secondary", fontSize: 11.5, mb: 0.5 }}>{liga} · {temporada}{enCurso ? " · en curso" : ""} · {h.pj} partidos</Box>
      <Box><strong>{h.pts} puntos</strong> · esperados {d1(h.xp)}{enCurso ? "" : ` · dif. ${conSigno(h.dif)}`}</Box>
      <Box>Lugar real {h.pr} · esperado {h.pe}{h.lugares === 0 ? "" : ` (${h.lugares > 0 ? "+" : "−"}${Math.abs(h.lugares)} ${Math.abs(h.lugares) === 1 ? "lugar" : "lugares"})`}</Box>
      <Box sx={{ color: "text.secondary" }}>Goles {h.gf} a favor, {h.gc} en contra</Box>
      <Box sx={{ color: "text.secondary" }}>xG {d1(h.xgf)} a favor, {d1(h.xgc)} en contra</Box>
      {enCurso && <Box sx={{ color: "text.secondary", mt: 0.5 }}>Temporada en curso: no se concluye nada.</Box>}
    </Paper>
  );

  const neutro = tk.muted;

  const descargar = () => descargarPng({
    ...capturar(lienzo.current),
    titulo: cfg.titulo, subtitulo: `${liga} · ${temporada}${enCurso ? " (en curso)" : ""}`,
    nota: `Punto lleno: puntos reales · punto vacío: puntos esperados (xPts)${enCurso ? " · en gris: temporada en curso" : ""}`,
    leyenda: enCurso ? null : [{ color: colorRendimiento(TOPE_DIF, div), texto: "Más puntos de los esperados" },
      { color: colorRendimiento(-TOPE_DIF, div), texto: "Menos" }],
    fuente: `Datos: ${cfg.fuente}`, tk, modo, archivo: nombreArchivo("tabla-real-vs-esperada", liga, temporada),
  });

  return (
    <>
      <Encabezado pregunta={cfg.pregunta} titulo={cfg.titulo} bajada={cfg.bajada} />

      <BarraFiltros>
        <Campo ancho={200}>
          <SelectUno etiqueta="Liga" valor={liga} opciones={D.ligas.map((l) => ({ valor: l, texto: l }))}
            onChange={(v) => { setLiga(v); setHover(null); }} />
        </Campo>
        <Campo ancho={140}>
          <SelectTemporada valor={temporada} temporadas={D.temporadas} onChange={(v) => { setTemporada(v); setHover(null); }} />
        </Campo>
      </BarraFiltros>

      <Box>
        <Box sx={{ minWidth: 0 }}>

          <Box ref={caja} sx={{ maxWidth: 1000, width: "100%", position: "relative" }}>
            <Typography component="h3" sx={{ fontSize: 13.5, fontWeight: 700, mb: 0.25 }}>
              {liga} · {temporada}{enCurso ? " (en curso)" : ""}{" "}
              <Box component="span" sx={{ fontWeight: 500, color: "text.secondary" }}>· en el orden de la tabla real</Box>
            </Typography>
            {enCurso && (
              <Typography sx={{ fontSize: 12.5, mb: 1, pl: 1.25, borderLeft: 3, borderColor: "warning.main" }}>
                Esta temporada va en curso: los equipos llevan de {Math.min(...filas.map((r) => r.pj))} a {Math.max(...filas.map((r) => r.pj))} partidos.
                Se dibuja en gris porque con tan pocos partidos la diferencia es casi toda azar.
              </Typography>
            )}
            <Leyenda tk={tk} div={div} enCurso={enCurso} />
            {w > 0 && filas.length > 0 && (
              <Box ref={lienzo}>
              <svg role="img" aria-label={resumen} width={w} height={alto} {...manejadores}>
                {/* encabezados de las columnas */}
                <g fontSize={10.5} fill={tk.muted} fontWeight={600}>
                  <text x={POS_W} y={HEAD - 9} textAnchor="end">Real</text>
                  <text x={w - DER_W} y={HEAD - 9}>{compacto ? "Esp. (±)" : "Esperado (± lugares)"}</text>
                </g>
                {/* rejilla vertical y eje de puntos */}
                <g fontSize={11} fill={tk.muted}>
                  {ticks.map((v) => (
                    <g key={v}>
                      <line x1={x(v)} x2={x(v)} y1={HEAD} y2={HEAD + RH * filas.length} stroke={tk.border} strokeOpacity={0.8} />
                      <text x={x(v)} y={HEAD + RH * filas.length + 16} textAnchor="middle">{v}</text>
                    </g>
                  ))}
                  <text x={pl + pw / 2} y={alto - 2} textAnchor="middle" fontSize={10.5}>Puntos</text>
                </g>
                {hover && <rect x={0} y={HEAD + RH * hover.i} width={w} height={RH} fill={conAlfa(tk.primary, 0.08)} pointerEvents="none" />}
                {filas.map((r, i) => {
                  const c = enCurso ? neutro : colorDe(r.dif, div);
                  const y = cy(i);
                  const dl = r.lugares;
                  return (
                    <g key={r.nombre}>
                      {i > 0 && <line x1={0} x2={w} y1={HEAD + RH * i} y2={HEAD + RH * i} stroke={tk.border} strokeOpacity={0.35} />}
                      <text x={POS_W} y={y + 4} textAnchor="end" fontSize={11.5} fontWeight={700} fill={tk["text-body"]}>{r.pr}</text>
                      <text x={POS_W + 6} y={y + 4} fontSize={compacto ? 11.5 : 12.5} fill={tk["text-body"]}>
                        {recorta(r.nombre, Math.floor(NOM_W / (compacto ? 6 : 6.6)))}
                      </text>
                      <line x1={x(r.xp)} x2={x(r.pts)} y1={y} y2={y} stroke={c} strokeWidth={4} strokeLinecap="round" strokeOpacity={enCurso ? 0.5 : 0.9} />
                      <circle cx={x(r.xp)} cy={y} r={R_MARCA} fill={tk.surface} stroke={tk.muted} strokeWidth={2} />
                      <circle cx={x(r.pts)} cy={y} r={hover && hover.i === i ? R_MARCA + 1.5 : R_MARCA} fill={c} stroke={tk.surface} strokeWidth={1.5} />
                      <text x={w - DER_W} y={y + 4} fontSize={compacto ? 11.5 : 12.5} fill={tk["text-body"]}>
                        {r.pe}
                        <tspan dx={6} fill={tk.muted} fontWeight={dl === 0 ? 400 : 700}>
                          {dl === 0 ? "=" : menos(`${dl > 0 ? "+" : "-"}${Math.abs(dl)}`)}
                        </tspan>
                      </text>
                    </g>
                  );
                })}
              </svg>
              </Box>
            )}
            {tip}
            <Typography sx={{ fontSize: 11.5, color: "text.secondary", mt: 0.5 }}>
              «+2» es estar dos lugares por encima del que le tocaría por xPts; «−2», dos por debajo.
            </Typography>
          </Box>

          <Box sx={{ mt: 0.5, display: "flex", alignItems: "center", justifyContent: "space-between", maxWidth: 1000 }}>
            <Typography sx={{ fontSize: 12, color: "text.secondary" }}>Datos: {cfg.fuente}</Typography>
            <BotonDescarga alDescargar={descargar} />
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

export default function TablaEsperadaVista({ id }) {
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
        : !estado.D ? <Cargando alto={640} />
          : <Vista cfg={cfg} D={estado.D} modo={modo} tk={t} />}
    </ThemeProvider>
  );
}
