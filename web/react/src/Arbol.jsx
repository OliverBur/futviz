// Un árbol de decisión que el lector puede ir abriendo.
//
// El servidor (`web/charts/xg_comparacion.py`) entrena UN árbol de profundidad 7 con los tiros de
// entrenamiento y manda, de cada nodo, la partición que elige y cuántos tiros y goles le llegan
// (entrenamiento y prueba). Como la mejor partición de un nodo depende solo de los tiros que le
// llegan, cualquier árbol más chico es un recorte de ese: el navegador simula aquí los dos modos de
// crecer que usan los algoritmos —por niveles (XGBoost) y por la mejor hoja (LightGBM)— con
// cualquier tope de profundidad y de hojas, y recalcula el error con las cuentas de cada hoja.
import { useEffect, useMemo, useRef, useState } from "react";
import Box from "@mui/material/Box";
import IconButton from "@mui/material/IconButton";
import Paper from "@mui/material/Paper";
import Slider from "@mui/material/Slider";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import Typography from "@mui/material/Typography";
import PlayArrow from "@mui/icons-material/PlayArrow";
import Pause from "@mui/icons-material/Pause";
import Replay from "@mui/icons-material/Replay";
import { Rotulo } from "./ui.jsx";
import { conAlfa } from "./colores.js";
import { miles } from "./milesComa.js";

const COL_W = 200, CAJA_W = 176, FILA_H = 46, CAJA_H = 38;
const TASA_MAX = 0.6;           // la tasa de gol a la que el color llega al tope

function perdida(n, pos, p) {
  const q = Math.min(1 - 1e-4, Math.max(1e-4, p));
  return -(pos * Math.log(q) + (n - pos) * Math.log(1 - q));
}

const hex = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
function colorRampa(rampa, t) {
  const x = Math.min(1, Math.max(0, t)) * (rampa.length - 1);
  const i = Math.min(rampa.length - 2, Math.floor(x)), f = x - i;
  const a = hex(rampa[i]), b = hex(rampa[i + 1]);
  return a.map((v, k) => Math.round(v + (b[k] - v) * f));
}

// Las particiones, en el orden en que cada estrategia las haría, respetando los dos topes.
function planear(N, modo, prof, hojasMax) {
  const pasos = [];
  let hojas = 1;
  if (modo === "niveles") {
    const cola = [0];
    while (cola.length && hojas < hojasMax) {
      const i = cola.shift();
      const n = N[i];
      if (n.hoja || n.d >= prof) continue;
      pasos.push(i);
      hojas += 1;
      cola.push(n.si, n.no);
    }
  } else {
    let abiertas = [0];
    while (hojas < hojasMax) {
      let mejor = -1, gm = -Infinity;
      for (const i of abiertas) {
        const n = N[i];
        if (n.hoja || n.d >= prof) continue;
        if (n.gan > gm) { gm = n.gan; mejor = i; }
      }
      if (mejor < 0) break;
      pasos.push(mejor);
      abiertas = abiertas.filter((x) => x !== mejor).concat([N[mejor].si, N[mejor].no]);
      hojas += 1;
    }
  }
  return pasos;
}

function auc(hojas, N) {
  let P = 0, Q = 0;
  hojas.forEach((i) => { P += N[i].pte; Q += N[i].nte - N[i].pte; });
  if (!P || !Q) return NaN;
  let s = 0;
  hojas.forEach((j) => {
    const pj = N[j].tasa;
    let neg = 0;
    hojas.forEach((i) => {
      const ni = N[i].nte - N[i].pte;
      if (N[i].tasa < pj) neg += ni;
      else if (N[i].tasa === pj) neg += 0.5 * ni;
    });
    s += N[j].pte * neg;
  });
  return s / (P * Q);
}

export default function Arbol({ cfg, D, tk, modo: modoTema }) {
  const A = D[cfg.dato];
  const F = A.features;
  const N = useMemo(() => {
    const base = A.nodos.map((a, i) => {
      const [f, t, si, no, d, ntr, ptr, nte, pte] = a;
      return { i, f, t, si, no, d, ntr, ptr, nte, pte, tasa: ntr ? ptr / ntr : 0, hoja: f < 0 };
    });
    base.forEach((n) => {
      n.gan = n.hoja ? 0 : perdida(n.ntr, n.ptr, n.tasa)
        - perdida(base[n.si].ntr, base[n.si].ptr, base[n.si].tasa)
        - perdida(base[n.no].ntr, base[n.no].ptr, base[n.no].tasa);
    });
    return base;
  }, [A]);

  const [estrategia, setEstrategia] = useState("hoja");
  const [prof, setProf] = useState(4);
  const [hojasMax, setHojasMax] = useState(10);
  const [paso, setPaso] = useState(null);       // null = el árbol completo bajo los topes
  const [jugando, setJugando] = useState(false);
  const [sobre, setSobre] = useState(null);

  const pasos = useMemo(() => planear(N, estrategia, prof, hojasMax), [N, estrategia, prof, hojasMax]);
  const k = paso === null ? pasos.length : Math.min(paso, pasos.length);
  const abiertos = useMemo(() => new Set(pasos.slice(0, k)), [pasos, k]);

  // animación: avanza una partición cada ~0.7 s
  const refPasos = useRef(pasos.length);
  refPasos.current = pasos.length;
  useEffect(() => {
    if (!jugando) return undefined;
    const t = setInterval(() => {
      setPaso((p) => {
        const actual = p === null ? 0 : p;
        if (actual >= refPasos.current) { setJugando(false); return refPasos.current; }
        return actual + 1;
      });
    }, 700);
    return () => clearInterval(t);
  }, [jugando]);
  const reiniciar = (nuevo) => { setJugando(false); setPaso(nuevo); };
  const cambiar = (fn) => (...a) => { fn(...a); setPaso(null); setJugando(false); };

  // diseño: hojas de arriba abajo, cada nodo interno centrado entre sus dos hijos
  const { pos, hojasVisibles, filas, maxD } = useMemo(() => {
    const pos = new Map();
    let fila = 0, maxD = 0;
    const colocar = (i) => {
      const n = N[i];
      maxD = Math.max(maxD, n.d);
      if (!abiertos.has(i)) { pos.set(i, { x: n.d * COL_W, y: fila * FILA_H }); fila += 1; return; }
      colocar(n.si); colocar(n.no);
      pos.set(i, { x: n.d * COL_W, y: (pos.get(n.si).y + pos.get(n.no).y) / 2 });
    };
    colocar(0);
    const hojasVisibles = [...pos.keys()].filter((i) => !abiertos.has(i));
    return { pos, hojasVisibles, filas: fila, maxD };
  }, [N, abiertos]);

  const totTr = A.n_train, totTe = A.n_test;
  const lTr = hojasVisibles.reduce((s, i) => s + perdida(N[i].ntr, N[i].ptr, N[i].tasa), 0) / totTr;
  const lTe = hojasVisibles.reduce((s, i) => s + perdida(N[i].nte, N[i].pte, N[i].tasa), 0) / totTe;
  const aucTe = useMemo(() => auc(hojasVisibles, N), [hojasVisibles, N]);
  const profReal = maxD;
  const claro = modoTema !== "dark";
  const rampa = useMemo(() => (claro ? A.rampa : [...A.rampa].reverse()), [A, claro]);

  const pregunta = (n) => {
    const f = F[n.f];
    if (f.tipo === "bin") return `¿${f.etiqueta}?`;
    const v = Math.abs(n.t) < 10 ? n.t.toFixed(1) : String(Math.round(n.t));
    return `¿${f.etiqueta} ≤ ${v}${f.unidad === "°" ? "°" : ` ${f.unidad || ""}`.trimEnd()}?`;
  };
  const pct = (v) => `${(v * 100).toFixed(1)}%`;

  const W = (maxD + 1) * COL_W - (COL_W - CAJA_W) + 8;
  const H = Math.max(filas, 1) * FILA_H + 8;
  const nodoSobre = sobre ? N[sobre.i] : null;
  const refs = A.ref || [];
  const xgb = refs.find((r) => r.id === "xgb");

  return (
    <Box>
      <Typography component="h3" sx={{ fontSize: 17, fontWeight: 700, color: "primary.main", lineHeight: 1.25, m: 0 }}>{cfg.titulo}</Typography>
      {cfg.subtitulo && <Typography sx={{ fontSize: 13, color: "text.secondary", mb: 1.25 }}>{cfg.subtitulo}</Typography>}

      <Box sx={{ display: "grid", gap: 2.5, gridTemplateColumns: { xs: "minmax(0,1fr)", md: "minmax(0,1fr) 270px" }, alignItems: "start" }}>
        <Box sx={{ minWidth: 0 }}>
          <Box className="rx-chart" sx={{ overflow: "auto", maxHeight: 680, border: 1, borderColor: "divider", borderRadius: 2,
            bgcolor: "background.paper", p: 1 }}>
            <svg width={W} height={H} role="img" aria-label={cfg.alt} style={{ display: "block" }}
              onPointerLeave={() => setSobre(null)}>
              {[...pos.keys()].filter((i) => abiertos.has(i)).map((i) => {
                const n = N[i], p = pos.get(i);
                return [n.si, n.no].map((h, j) => {
                  const c = pos.get(h);
                  const x1 = p.x + CAJA_W, y1 = p.y + FILA_H / 2, x2 = c.x, y2 = c.y + FILA_H / 2;
                  const xm = (x1 + x2) / 2;
                  return (
                    <g key={`${i}-${h}`}>
                      <path d={`M${x1},${y1} C${xm},${y1} ${xm},${y2} ${x2},${y2}`} fill="none"
                        stroke={j === 0 ? tk.interactive : tk.muted} strokeWidth={1.6} strokeOpacity={j === 0 ? 0.9 : 0.6} />
                      <text x={x2 - 6} y={y2 - 5} textAnchor="end" fontSize={10.5} fontWeight={700}
                        fill={j === 0 ? tk.interactive : tk.muted}>{j === 0 ? "sí" : "no"}</text>
                    </g>
                  );
                });
              })}
              {[...pos.keys()].map((i) => {
                const n = N[i], p = pos.get(i);
                const hoja = !abiertos.has(i);
                const yc = p.y + FILA_H / 2;
                let fondo = tk.surface, trazo = tk.border, texto = tk["text-body"], sub = tk.muted;
                if (hoja) {
                  const [r, g, b] = colorRampa(rampa, n.tasa / TASA_MAX);
                  fondo = `rgb(${r},${g},${b})`;
                  const lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
                  texto = lum < 0.55 ? "#ffffff" : "#0b0b0b";
                  sub = texto;
                  trazo = tk.border;
                }
                const activo = sobre && sobre.i === i;
                return (
                  <g key={i} onPointerMove={(e) => setSobre({ i, px: e.clientX, py: e.clientY })} style={{ cursor: "default" }}>
                    <rect x={p.x} y={yc - CAJA_H / 2} width={CAJA_W} height={CAJA_H} rx={8} fill={fondo}
                      stroke={activo ? tk.primary : trazo} strokeWidth={activo ? 2 : 1} />
                    <text x={p.x + 10} y={yc - 3} fontSize={12} fontWeight={700} fill={texto}>
                      {hoja ? `xG ${n.tasa.toFixed(2)}` : pregunta(n)}
                    </text>
                    <text x={p.x + 10} y={yc + 12} fontSize={10.5} fill={sub} fillOpacity={hoja ? 0.9 : 1}>
                      {hoja ? `${miles(n.ntr)} tiros${!n.hoja ? " · aún sin partir" : ""}` : `${miles(n.ntr)} tiros · ${pct(n.tasa)} gol`}
                    </text>
                  </g>
                );
              })}
            </svg>
          </Box>
          {nodoSobre && (
            <Paper elevation={4} className="rx-tooltip" sx={{ position: "fixed", left: sobre.px + 14, top: sobre.py + 14, p: 1.1,
              pointerEvents: "none", zIndex: 1500, border: 1, borderColor: "divider", fontSize: 12.5, minWidth: 190 }}>
              <Typography sx={{ fontWeight: 700, fontSize: 13 }}>
                {abiertos.has(nodoSobre.i) ? pregunta(nodoSobre) : "Hoja"}
              </Typography>
              <Box sx={{ color: "text.secondary" }}>Entrenamiento: {miles(nodoSobre.ntr)} tiros · {miles(nodoSobre.ptr)} goles ({pct(nodoSobre.tasa)})</Box>
              <Box sx={{ color: "text.secondary" }}>Prueba: {miles(nodoSobre.nte)} tiros · {miles(nodoSobre.pte)} goles ({nodoSobre.nte ? pct(nodoSobre.pte / nodoSobre.nte) : "—"})</Box>
              {!nodoSobre.hoja && <Box sx={{ mt: 0.5 }}>Esta partición baja el error de entrenamiento {nodoSobre.gan.toFixed(0)} nats</Box>}
              {!abiertos.has(nodoSobre.i) && !nodoSobre.hoja && nodoSobre.d >= prof && <Box sx={{ color: "text.secondary" }}>No se parte: llegó al tope de profundidad.</Box>}
            </Paper>
          )}
          <Box sx={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", gap: 1, mt: 0.75 }}>
            <Typography sx={{ fontSize: 12, color: "text.secondary" }}>
              Pasa el mouse por un nodo para ver sus cuentas. El color de las hojas es su tasa de gol.
            </Typography>
            <Typography sx={{ fontSize: 12, color: "text.secondary" }}>Datos: {cfg.fuente}</Typography>
          </Box>
        </Box>

        <Box sx={{ display: "flex", flexDirection: "column", gap: 2, order: { xs: -1, md: 0 } }}>
          <Box>
            <Rotulo ayuda="Por niveles: parte todos los nodos de un nivel antes de pasar al siguiente (es lo que hace XGBoost). Por la mejor hoja: parte siempre la hoja donde más baja el error (es lo que hace LightGBM).">
              Cómo crece
            </Rotulo>
            <ToggleButtonGroup exclusive size="small" fullWidth value={estrategia} aria-label="Cómo crece el árbol"
              onChange={(_e, v) => { if (v) { setEstrategia(v); reiniciar(null); } }}>
              <ToggleButton value="niveles">Por niveles</ToggleButton>
              <ToggleButton value="hoja">Mejor hoja</ToggleButton>
            </ToggleButtonGroup>
            <Typography sx={{ fontSize: 11.5, color: "text.secondary", mt: 0.5 }}>
              {estrategia === "niveles" ? "Como XGBoost: todo el nivel antes de bajar." : "Como LightGBM: siempre la hoja que más gana."}
            </Typography>
          </Box>
          <Box>
            <Rotulo>Profundidad máxima: {prof}</Rotulo>
            <Slider size="small" min={1} max={A.profundidad} step={1} value={prof} marks valueLabelDisplay="auto"
              onChange={(_e, v) => cambiar(setProf)(v)} aria-label="Profundidad máxima" />
          </Box>
          <Box>
            <Rotulo>Hojas máximas: {hojasMax}</Rotulo>
            <Slider size="small" min={2} max={32} step={1} value={hojasMax} valueLabelDisplay="auto"
              onChange={(_e, v) => cambiar(setHojasMax)(v)} aria-label="Hojas máximas" />
          </Box>
          <Box>
            <Rotulo>Particiones: {k} de {pasos.length}</Rotulo>
            <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
              <IconButton size="small" aria-label={jugando ? "Pausar" : "Ver cómo se va abriendo"}
                onClick={() => { if (!jugando && k >= pasos.length) setPaso(0); setJugando((j) => !j); }}>
                {jugando ? <Pause /> : <PlayArrow />}
              </IconButton>
              <IconButton size="small" aria-label="Volver al árbol completo" onClick={() => reiniciar(null)}><Replay /></IconButton>
              <Slider size="small" min={0} max={Math.max(pasos.length, 1)} step={1} value={k} disabled={!pasos.length}
                onChange={(_e, v) => { setJugando(false); setPaso(v); }} aria-label="Particiones hechas" sx={{ ml: 1 }} />
            </Box>
          </Box>

          <Box sx={{ border: 1, borderColor: "divider", borderRadius: 2, p: 1.25, bgcolor: "background.paper" }} aria-live="polite">
            <Rotulo>Este árbol</Rotulo>
            <Fila k="Hojas · profundidad" v={`${hojasVisibles.length} · ${profReal}`} />
            <Fila k="Error en entrenamiento" v={lTr.toFixed(4)} />
            <Fila k="Error en 2025-26" v={lTe.toFixed(4)} fuerte />
            <Fila k="AUC en 2025-26" v={Number.isNaN(aucTe) ? "—" : aucTe.toFixed(3)} />
            {refs.length > 0 && <Box sx={{ borderTop: 1, borderColor: "divider", mt: 0.75, pt: 0.75 }}>
              {refs.map((r) => <Fila key={r.id} k={r.nombre} v={`${r.ll.toFixed(4)} · ${r.auc.toFixed(3)}`} suave />)}
            </Box>}
          </Box>
        </Box>
      </Box>

      {xgb && (
        <Typography sx={{ fontSize: 14, lineHeight: 1.6, mt: 2, maxWidth: 820 }}>
          Con {hojasVisibles.length} hojas, este árbol llega a <strong>{lTe.toFixed(4)}</strong> de log-loss en 2025-26. {xgb.nombre} suma
          {" "}{miles(xgb.arboles)} árboles de tamaño parecido, cada uno corrigiendo los errores de los anteriores, y llega a{" "}
          <strong>{xgb.ll.toFixed(4)}</strong>. El error en entrenamiento es {lTr.toFixed(4)}: la brecha con la prueba mezcla lo que el
          árbol memoriza con que 2025-26 es otra temporada.
        </Typography>
      )}
    </Box>
  );
}

function Fila({ k, v, fuerte, suave }) {
  return (
    <Box sx={{ display: "flex", justifyContent: "space-between", gap: 1, fontSize: suave ? 12 : 12.5, py: 0.15,
      color: suave ? "text.secondary" : "text.primary" }}>
      <span>{k}</span><strong style={{ fontWeight: fuerte ? 800 : 700 }}>{v}</strong>
    </Box>
  );
}
