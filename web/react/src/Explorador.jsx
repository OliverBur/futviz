// El explorador de tiros: elegir un tiro de entre los de las cinco últimas temporadas y verlo sobre la
// cancha con lo que dijo cada modelo y lo que pasó.
//
// Cada temporada viaja en su propia tabla (`dist/react/datos-xgtiros-<temporada>.js`, ver
// `web/charts/xg_explorador.py`) y se pide al elegirla: ~45.000 tiros en columnas de enteros. El xG
// "mío" de cada tiro sale de un modelo que NO había visto esa temporada (walk-forward, ver
// `xg_temporadas.py`), así que la comparación con Understat es justa tiro por tiro.
//
// La cancha es un <canvas>: con 45.000 puntos un SVG no se mueve. Los dos xG del tiro elegido se dibujan
// como círculos cuya área es proporcional al valor (azul: mío, rojo: Understat) alrededor del punto, y el
// resultado es el relleno del centro.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Autocomplete from "@mui/material/Autocomplete";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import MenuItem from "@mui/material/MenuItem";
import Paper from "@mui/material/Paper";
import Select from "@mui/material/Select";
import TextField from "@mui/material/TextField";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import Typography from "@mui/material/Typography";
import { cargarDatos } from "./datos.js";
import { Cargando, Rotulo } from "./ui.jsx";
import { conAlfa } from "./colores.js";
import { miles } from "./milesComa.js";

const LARGO = 105, ANCHO = 68, PORTERIA = 7.32;
const PROF = 46;                    // metros de profundidad que se dibujan
const MARGEN = 3.4;                 // metros de aire alrededor (arriba cabe la portería)

const FECHA = new Intl.DateTimeFormat("es", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
const fecha = (d0, d) => FECHA.format(new Date(Date.UTC(d0[0], d0[1] - 1, d0[2] + d)));
const num2 = (v) => v.toFixed(2);

// la geometría de un tiro a partir de sus coordenadas (las mismas fórmulas que el modelo)
function geometria(x, y) {
  const px = x * LARGO, py = y * ANCHO;
  const dist = Math.hypot(LARGO - px, ANCHO / 2 - py);
  const a = Math.hypot(LARGO - px, ANCHO / 2 + PORTERIA / 2 - py);
  const b = Math.hypot(LARGO - px, ANCHO / 2 - PORTERIA / 2 - py);
  const ang = Math.acos(Math.min(1, Math.max(-1, (a * a + b * b - PORTERIA * PORTERIA) / (2 * a * b))));
  return { dist, ang: (ang * 180) / Math.PI };
}

function useTemporada(nombre) {
  const [est, setEst] = useState({ nombre: null, D: null, error: null });
  useEffect(() => {
    let vivo = true;
    cargarDatos(nombre)
      .then((D) => vivo && setEst({ nombre, D, error: null }))
      .catch((e) => vivo && setEst({ nombre, D: null, error: e }));
    return () => { vivo = false; };
  }, [nombre]);
  return est.nombre === nombre ? est : { nombre, D: null, error: null };
}

export default function Explorador({ cfg, tk, pal, modo, alCargar }) {
  const [temp, setTemp] = useState(cfg.temporadas[cfg.temporadas.length - 1]);
  const [liga, setLiga] = useState(-1);
  // Se abre solo con los goles de las cinco ligas: dibujar los ~45.000 tiros de la temporada pesa y
  // no se lee. "Todos" y "Sin gol" quedan a un clic.
  const [res, setRes] = useState("gol");
  const [equipo, setEquipo] = useState(null);       // índice en D.eq
  const [jugador, setJugador] = useState(null);     // índice en D.jug
  const [sel, setSel] = useState(null);
  const [hover, setHover] = useState(null);
  const [tipPos, setTipPos] = useState(null);
  const { D, error } = useTemporada(`xgtiros-${temp}`);
  const canvasRef = useRef(null);
  const cajaRef = useRef(null);
  const [ancho, setAncho] = useState(0);

  useEffect(() => {
    if (!cajaRef.current) return undefined;
    const ro = new ResizeObserver(([e]) => setAncho(Math.round(e.contentRect.width)));
    ro.observe(cajaRef.current);
    return () => ro.disconnect();
  }, [D]);

  const c = D ? D.c : null;
  // al cambiar de temporada el índice elegido es de la tabla anterior hasta que corre el efecto de abajo
  const selOk = c && sel != null && sel < D.n ? sel : null;

  // los tiros que pasan los filtros
  const idx = useMemo(() => {
    if (!c) return new Int32Array(0);
    const out = new Int32Array(D.n);
    let k = 0;
    for (let i = 0; i < D.n; i += 1) {
      if (liga >= 0 && c.l[i] !== liga) continue;
      if (res === "gol" && c.r[i] !== 0) continue;
      if (res === "nogol" && c.r[i] === 0) continue;
      if (equipo != null && c.e[i] !== equipo) continue;
      if (jugador != null && c.j[i] !== jugador) continue;
      out[k] = i; k += 1;
    }
    return out.slice(0, k);
  }, [D, c, liga, res, equipo, jugador]);

  // El resumen cuenta TODOS los tiros del equipo, jugador o liga elegidos, sin el filtro de resultado: la
  // suma de xG solo de los goles (o solo de los fallos) no compara nada.
  const resumen = useMemo(() => {
    if (!c) return null;
    let n = 0, goles = 0, me = 0, us = 0;
    for (let i = 0; i < D.n; i += 1) {
      if (liga >= 0 && c.l[i] !== liga) continue;
      if (equipo != null && c.e[i] !== equipo) continue;
      if (jugador != null && c.j[i] !== jugador) continue;
      n += 1; goles += c.r[i] === 0 ? 1 : 0; me += c.me[i]; us += c.us[i];
    }
    return { n, goles, me: me / 1e4, us: us / 1e4, vistos: idx.length };
  }, [D, c, idx, liga, equipo, jugador]);

  // al cambiar de temporada, de entrada se muestra el gol más improbable
  useEffect(() => {
    if (!c) return;
    if (alCargar) alCargar();
    let mejor = null, v = Infinity;
    for (let i = 0; i < D.n; i += 1) {
      if (c.r[i] !== 0) continue;
      const p = c.me[i] + c.us[i];
      if (p < v) { v = p; mejor = i; }
    }
    setSel(mejor);
    setHover(null); setTipPos(null);
    setEquipo(null); setJugador(null); setLiga(-1); setRes("gol");
  }, [D]); // eslint-disable-line react-hooks/exhaustive-deps

  // Un filtro nuevo que deja fuera al tiro elegido: se pasa al de más discrepancia entre los que quedan
  useEffect(() => {
    if (!c || sel == null || sel >= D.n || idx.length === 0) return;
    const pasa = (!(liga >= 0) || c.l[sel] === liga)
      && !(res === "gol" && c.r[sel] !== 0) && !(res === "nogol" && c.r[sel] === 0)
      && (equipo == null || c.e[sel] === equipo) && (jugador == null || c.j[sel] === jugador);
    if (pasa) return;
    let mejor = idx[0], v = -1;
    for (const i of idx) {
      const d = Math.abs(c.me[i] - c.us[i]);
      if (d > v) { v = d; mejor = i; }
    }
    setSel(mejor);
  }, [idx]); // eslint-disable-line react-hooks/exhaustive-deps

  // --- el dibujo ---------------------------------------------------------------------------------
  const W = Math.max(280, Math.min(ancho, 880));
  const escala = W / (ANCHO + 2 * 1.5);
  const H = Math.round((PROF + MARGEN + 1.5) * escala);
  const aPx = useCallback((x, y) => [(y * ANCHO + 1.5) * escala, (((1 - x) * LARGO) + MARGEN) * escala], [escala]);

  useEffect(() => {
    const cv = canvasRef.current;
    if (!cv || !c || ancho === 0) return;
    const dpr = window.devicePixelRatio || 1;
    cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr);
    cv.style.width = `${W}px`; cv.style.height = `${H}px`;
    const g = cv.getContext("2d");
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, W, H);
    // la cancha
    const m = (v) => v * escala;
    const X0 = 1.5 * escala, Y0 = MARGEN * escala;
    g.fillStyle = conAlfa(pal.propio, modo === "dark" ? 0.07 : 0.05);
    g.fillRect(X0, Y0, m(ANCHO), m(PROF));
    g.strokeStyle = modo === "dark" ? "rgba(255,255,255,.55)" : "rgba(7,12,14,.45)";
    g.lineWidth = 1.4;
    g.strokeRect(X0, Y0, m(ANCHO), m(PROF) + 4);
    const medio = ANCHO / 2;
    g.strokeRect(X0 + m(medio - 20.16), Y0, m(40.32), m(16.5));
    g.strokeRect(X0 + m(medio - 9.16), Y0, m(18.32), m(5.5));
    g.beginPath();
    const tope = Math.asin(Math.sqrt(9.15 ** 2 - (16.5 - 11) ** 2) / 9.15);
    for (let i = 0; i <= 40; i += 1) {
      const a = -tope + (2 * tope * i) / 40;
      const px = X0 + m(medio + 9.15 * Math.sin(a)), py = Y0 + m(11 + 9.15 * Math.cos(a));
      if (i === 0) g.moveTo(px, py); else g.lineTo(px, py);
    }
    g.stroke();
    g.beginPath(); g.arc(X0 + m(medio), Y0 + m(11), 1.6, 0, 2 * Math.PI); g.fillStyle = g.strokeStyle; g.fill();
    g.lineWidth = 2.4;
    g.strokeRect(X0 + m(medio - PORTERIA / 2), Y0 - m(1.2), m(PORTERIA), m(1.2));
    // los tiros
    const n = idx.length;
    const alfa = n > 20000 ? 0.22 : n > 4000 ? 0.32 : 0.5;
    const rad = n > 20000 ? 1.7 : n > 4000 ? 2.1 : 2.8;
    const dibujar = (esGol) => {
      g.fillStyle = esGol ? conAlfa(pal.acento, Math.min(0.9, alfa + 0.35)) : conAlfa(tk.muted, alfa);
      g.beginPath();
      for (const i of idx) {
        if ((c.r[i] === 0) !== esGol) continue;
        const [px, py] = aPx(c.x[i] / 1000, c.y[i] / 1000);
        if (py > H) continue;
        g.moveTo(px + rad, py);
        g.arc(px, py, esGol ? rad + 0.7 : rad, 0, 2 * Math.PI);
      }
      g.fill();
    };
    dibujar(false);
    dibujar(true);
    // el tiro elegido: línea a la portería y los dos xG como áreas
    const marcar = (i, ligero) => {
      const [px, py] = aPx(c.x[i] / 1000, c.y[i] / 1000);
      if (ligero) {
        g.strokeStyle = tk.primary; g.lineWidth = 1.6; g.beginPath(); g.arc(px, py, 7, 0, 2 * Math.PI); g.stroke();
        return;
      }
      const [gx, gy] = [X0 + m(medio), Y0];
      g.setLineDash([5, 4]); g.strokeStyle = conAlfa(tk.muted, 0.8); g.lineWidth = 1.2;
      g.beginPath(); g.moveTo(px, py); g.lineTo(gx, gy); g.stroke(); g.setLineDash([]);
      const r = (p) => 5 + Math.sqrt(p) * 46;
      const mio = c.me[i] / 1e4, und = c.us[i] / 1e4;
      for (const [p, col] of [[und, pal.understat], [mio, pal.propio]]) {
        g.fillStyle = conAlfa(col, 0.16); g.strokeStyle = col; g.lineWidth = 2.2;
        g.beginPath(); g.arc(px, py, r(p), 0, 2 * Math.PI); g.fill(); g.stroke();
      }
      g.beginPath(); g.arc(px, py, 5.2, 0, 2 * Math.PI);
      g.fillStyle = c.r[i] === 0 ? pal.acento : tk.surface; g.fill();
      g.strokeStyle = c.r[i] === 0 ? tk.surface : tk["text-body"]; g.lineWidth = 1.8; g.stroke();
    };
    if (hover != null && hover !== selOk && hover < D.n) marcar(hover, true);
    if (selOk != null) marcar(selOk, false);
  }, [c, D, idx, selOk, hover, W, H, escala, ancho, tk, pal, modo, aPx]);

  // --- interacción -------------------------------------------------------------------------------
  const cercano = (e) => {
    const r = canvasRef.current.getBoundingClientRect();
    const mx = e.clientX - r.left, my = e.clientY - r.top;
    let mejor = null, dm = 15 * 15;
    for (const i of idx) {
      const [px, py] = aPx(c.x[i] / 1000, c.y[i] / 1000);
      const d = (px - mx) ** 2 + (py - my) ** 2;
      if (d < dm) { dm = d; mejor = i; }
    }
    return { i: mejor, px: e.clientX - r.left, py: e.clientY - r.top };
  };
  const alMover = (e) => {
    if (!c) return;
    const k = cercano(e);
    setHover(k.i);
    setTipPos(k.i != null ? { px: k.px, py: k.py } : null);
  };
  const alPulsar = (e) => {
    if (!c) return;
    const k = cercano(e);
    if (k.i != null) setSel(k.i);
  };

  const elegir = (criterio) => {
    if (!c || idx.length === 0) return;
    let mejor = null, v = -Infinity;
    if (criterio === "azar") { setSel(idx[Math.floor(Math.random() * idx.length)]); return; }
    for (const i of idx) {
      const me = c.me[i], us = c.us[i], gol = c.r[i] === 0;
      let p;
      if (criterio === "improbable") { if (!gol) continue; p = -(me + us); }
      else if (criterio === "desacuerdo") p = Math.abs(me - us);
      else if (criterio === "claro") { if (gol) continue; p = me + us; }
      else continue;
      if (p > v) { v = p; mejor = i; }
    }
    if (mejor != null) setSel(mejor);
  };

  const jugadoresOpc = useMemo(() => {
    if (!c) return [];
    const vistos = new Set();
    for (let i = 0; i < D.n; i += 1) vistos.add(c.j[i]);
    return [...vistos].sort((a, b) => D.jug[a].localeCompare(D.jug[b], "es"));
  }, [D, c]);
  const equiposOpc = useMemo(() => {
    if (!c) return [];
    const vistos = new Set();
    for (let i = 0; i < D.n; i += 1) vistos.add(c.e[i]);
    return [...vistos].sort((a, b) => D.eq[a].localeCompare(D.eq[b], "es"));
  }, [D, c]);

  // --- detalle del tiro elegido ------------------------------------------------------------------
  const det = useMemo(() => {
    if (!c || selOk == null) return null;
    const sel = selOk;
    const x = c.x[sel] / 1000, y = c.y[sel] / 1000;
    return {
      jugador: D.jug[c.j[sel]], asistio: c.q[sel] >= 0 ? D.jug[c.q[sel]] : null,
      equipo: D.eq[c.e[sel]], rival: D.eq[c.v[sel]], local: c.h[sel] === 1,
      fecha: fecha(cfg.origen, c.d[sel]), minuto: c.m[sel], liga: cfg.ligas[c.l[sel]],
      situacion: cfg.situaciones[c.s[sel]], parte: cfg.partes[c.p[sel]], accion: cfg.acciones[c.a[sel]],
      resultado: cfg.resultados[c.r[sel]], gol: c.r[sel] === 0,
      me: c.me[sel] / 1e4, us: c.us[sel] / 1e4, ...geometria(x, y),
    };
  }, [c, D, selOk, cfg]);

  const barra = (v, color) => (
    <Box sx={{ height: 10, borderRadius: 1, bgcolor: "action.hover", overflow: "hidden", flex: 1 }}>
      <Box sx={{ height: "100%", width: `${Math.min(100, v * 100)}%`, bgcolor: color, borderRadius: 1 }} />
    </Box>
  );
  const fila = (nombre, valor, v, color, fuerte) => (
    <Box sx={{ display: "grid", gridTemplateColumns: "92px 1fr 58px", alignItems: "center", gap: 1, py: 0.5 }}>
      <Typography sx={{ fontSize: 13, color: "text.secondary" }}>{nombre}</Typography>
      {barra(v, color)}
      <Typography sx={{ fontSize: 15, fontWeight: fuerte ? 800 : 700, textAlign: "right" }}>{valor}</Typography>
    </Box>
  );

  const tip = hover != null && tipPos && c ? (
    <Paper elevation={4} className="rx-tooltip"
      sx={{ position: "absolute", pointerEvents: "none", zIndex: 5, p: 1, border: 1, borderColor: "divider", fontSize: 12.5,
        top: Math.max(0, tipPos.py - 62), ...(tipPos.px > W * 0.6 ? { right: W - tipPos.px + 12 } : { left: tipPos.px + 12 }) }}>
      <Typography sx={{ fontWeight: 700, fontSize: 12.5 }}>{D.jug[c.j[hover]]} · {c.m[hover]}'</Typography>
      <Box sx={{ color: "text.secondary" }}>
        mío {num2(c.me[hover] / 1e4)} · Understat {num2(c.us[hover] / 1e4)} · {cfg.resultados[c.r[hover]].toLowerCase()}
      </Box>
    </Paper>
  ) : null;

  const dif = det ? det.us - det.me : 0;
  const frase = det && (Math.abs(dif) < 0.015
    ? "Los dos modelos dicen casi lo mismo."
    : dif > 0 ? `Understat le da ${num2(dif)} más que mi modelo.` : `Mi modelo le da ${num2(-dif)} más que Understat.`);

  return (
    <Box>
      <Typography component="h3" sx={{ fontSize: 17, fontWeight: 700, color: "primary.main", lineHeight: 1.25, m: 0 }}>
        {cfg.titulo}
      </Typography>
      {cfg.subtitulo && <Typography sx={{ fontSize: 13, color: "text.secondary", mb: 1.5 }}>{cfg.subtitulo}</Typography>}

      <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1.5, mb: 1.5, alignItems: "flex-end" }}>
        <Box>
          <Rotulo>Temporada</Rotulo>
          <ToggleButtonGroup exclusive size="small" value={temp} aria-label="Temporada"
            onChange={(_e, v) => v && setTemp(v)} sx={{ flexWrap: "wrap" }}>
            {cfg.temporadas.map((t) => <ToggleButton key={t} value={t}>{t}</ToggleButton>)}
          </ToggleButtonGroup>
        </Box>
        <Box>
          <Rotulo>Resultado</Rotulo>
          <ToggleButtonGroup exclusive size="small" value={res} aria-label="Resultado"
            onChange={(_e, v) => v && setRes(v)}>
            <ToggleButton value="todos">Todos</ToggleButton>
            <ToggleButton value="gol">Goles</ToggleButton>
            <ToggleButton value="nogol">Sin gol</ToggleButton>
          </ToggleButtonGroup>
        </Box>
        <Box sx={{ minWidth: 150 }}>
          <Rotulo>Liga</Rotulo>
          <Select size="small" fullWidth value={liga} onChange={(e) => setLiga(e.target.value)}
            inputProps={{ "aria-label": "Liga" }} sx={{ fontSize: 13 }}>
            <MenuItem value={-1}>Las cinco</MenuItem>
            {cfg.ligas.map((l, i) => <MenuItem key={l} value={i}>{l}</MenuItem>)}
          </Select>
        </Box>
      </Box>
      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" }, gap: 1.5, mb: 1.5 }}>
        <Autocomplete size="small" options={equiposOpc} value={equipo} onChange={(_e, v) => setEquipo(v)}
          getOptionLabel={(i) => (D ? D.eq[i] : "")} noOptionsText="Sin coincidencias"
          renderInput={(p) => <TextField {...p} label="Equipo" placeholder="Todos" />} />
        <Autocomplete size="small" options={jugadoresOpc} value={jugador} onChange={(_e, v) => setJugador(v)}
          getOptionLabel={(i) => (D ? D.jug[i] : "")} noOptionsText="Sin coincidencias"
          renderInput={(p) => <TextField {...p} label="Jugador" placeholder="Todos" />} />
      </Box>
      <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.75, mb: 2 }}>
        {[["azar", "Un tiro al azar"], ["improbable", "El gol más improbable"], ["desacuerdo", "Donde más discrepan"],
          ["claro", "La ocasión clara que no entró"]].map(([k, t]) => (
          <Button key={k} size="small" variant="outlined" onClick={() => elegir(k)} disabled={!resumen || resumen.n === 0}
            sx={{ textTransform: "none", fontWeight: 600, fontSize: 12.5, borderColor: "divider", color: "text.primary" }}>
            {t}
          </Button>
        ))}
      </Box>

      {error ? <Typography color="text.secondary">No se pudo cargar la temporada.</Typography>
        : !D ? <Cargando alto={420} />
          : (
            <Box sx={{ display: "grid", gap: 2.5, gridTemplateColumns: { xs: "minmax(0,1fr)", md: "minmax(0,1fr) 270px" }, alignItems: "start" }}>
              <Box ref={cajaRef} sx={{ position: "relative", minWidth: 0 }}>
                <canvas ref={canvasRef} role="img" aria-label={cfg.alt} className="rx-chart"
                  style={{ display: "block", cursor: hover != null ? "pointer" : "crosshair", touchAction: "pan-y" }}
                  onPointerMove={alMover} onPointerDown={(e) => { alMover(e); alPulsar(e); }}
                  onPointerLeave={() => { setHover(null); setTipPos(null); }} />
                {tip}
                {resumen && (
                  <Typography sx={{ fontSize: 12.5, color: "text.secondary", mt: 1 }} aria-live="polite">
                    {miles(resumen.n)} tiros · <strong>{miles(resumen.goles)}</strong> goles · mi modelo suma{" "}
                    <Box component="strong" sx={{ color: pal.propio }}>{miles(Math.round(resumen.me))}</Box>, Understat{" "}
                    <Box component="strong" sx={{ color: pal.understat }}>{miles(Math.round(resumen.us))}</Box>
                    {resumen.vistos !== resumen.n && <> · en la cancha, {miles(resumen.vistos)}</>}
                  </Typography>
                )}
              </Box>

              <Paper variant="outlined" sx={{ p: 1.75, borderRadius: 2, order: { xs: -1, md: 0 } }}>
                {det ? (
                  <>
                    <Typography sx={{ fontSize: 17, fontWeight: 800, lineHeight: 1.2 }}>{det.jugador}</Typography>
                    <Typography sx={{ fontSize: 13, color: "text.secondary", mb: 1 }}>
                      {det.equipo} · {det.local ? "de local ante" : "de visita en"} {det.rival}
                      <br />{det.liga} · {det.fecha} · minuto {det.minuto}
                    </Typography>
                    <Typography sx={{ fontSize: 13, mb: 0.25 }}>
                      {det.situacion} · {det.parte.toLowerCase()}{det.accion && det.accion !== "Sin acción previa" ? ` · tras ${det.accion.toLowerCase()}` : ""}
                    </Typography>
                    <Typography sx={{ fontSize: 13, color: "text.secondary", mb: 1.25 }}>
                      A {det.dist.toFixed(1)} m de la portería, {det.ang.toFixed(0)}° de ángulo
                      {det.asistio ? ` · asistió ${det.asistio}` : ""}
                    </Typography>
                    {fila("Mi modelo", num2(det.me), det.me, pal.propio)}
                    {fila("Understat", num2(det.us), det.us, pal.understat)}
                    {fila("Resultado", det.resultado, det.gol ? 1 : 0, det.gol ? pal.acento : tk.muted, true)}
                    <Typography sx={{ fontSize: 12.5, color: "text.secondary", mt: 1 }}>{frase}</Typography>
                  </>
                ) : <Typography sx={{ fontSize: 13, color: "text.secondary" }}>Toca un punto de la cancha.</Typography>}
              </Paper>
            </Box>
          )}
      <Box sx={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", gap: 1, mt: 1 }}>
        <Typography sx={{ fontSize: 12, color: "text.secondary" }}>
          Círculos del tiro elegido: área proporcional al xG · azul, mi modelo · rojo, Understat · centro verde, gol.
        </Typography>
        <Typography sx={{ fontSize: 12, color: "text.secondary" }}>Datos: {cfg.fuente}</Typography>
      </Box>
    </Box>
  );
}
