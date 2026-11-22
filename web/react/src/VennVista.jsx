// «Jugador completo»: diagramas de Venn de tres criterios por posición (ver `web/charts/venn.py`).
//
// Cada círculo es «estar en el X% de arriba de su posición» en una medida; el centro es quien cumple las tres. El corte
// lo mueve un deslizador, así que el cálculo (percentiles dentro de la posición y la temporada) se hace aquí, con la
// misma regla que el módulo de Python (`vennCalculo.js`). El dibujo es un SVG como texto (`vennSvg.js`) para que la
// misma función sirva a la pantalla y a la imagen que se descarga.
import { useEffect, useMemo, useRef, useState } from "react";
import { ThemeProvider } from "@mui/material/styles";
import Autocomplete from "@mui/material/Autocomplete";
import Box from "@mui/material/Box";
import Paper from "@mui/material/Paper";
import Slider from "@mui/material/Slider";
import TextField from "@mui/material/TextField";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import Typography from "@mui/material/Typography";
import { entre, leerParams, usePublicarParams } from "./urlEstado.js";
import { useSitioTema } from "./theme.jsx";
import { cargarDatos } from "./datos.js";
import { Aviso, Cargando, Encabezado, Md, Parrafos, Rotulo, sinAcentos, ComoLeer } from "./ui.jsx";
import { miles } from "./milesComa.js";
import { acomodar, calcular, cuantos, pastillas, regionTxt } from "./vennCalculo.js";
import { BotonDescarga } from "./BotonDescarga.jsx";
import { BarraFiltros, Campo, Segmentado, SelectTemporada } from "./Filtros.jsx";
import { descargarPng, nombreArchivo } from "./descargarImagen.js";
import { VIEWBOX, VIEWBOX_COMPACTO, construirSvg } from "./vennSvg.js";

const ANCHO_COMPACTO = 540;   // por debajo, las fichas van sin nombre (a esa escala no se leerían)
const MAX_NOMBRES = 14;       // los que se listan por cruce antes de mandar a la tabla
const NF = new Intl.NumberFormat("es-MX", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const f2 = (v) => NF.format(v);
const fdec = (v, dec = 2) => v.toLocaleString("es-MX", { minimumFractionDigits: dec, maximumFractionDigits: dec });
const signo = (v) => (v < 0 ? "−" : "+") + NF.format(Math.abs(v));
const dec1 = (v) => v.toFixed(1).replace(".", ",");

function useAncho(ref) {
  const [w, setW] = useState(0);
  useEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    const medir = () => setW(el.clientWidth);
    const ro = new ResizeObserver(medir);
    ro.observe(el);
    medir();
    return () => ro.disconnect();
  }, [ref]);
  return w;
}

// Lo que se dice sobre el centro: cuántos caen y cuántos caerían si los tres criterios no tuvieran relación.
function lectura(V) {
  const N = V.pop.length, c = V.reg[7], esperado = N * V.q ** 3, v = V.venn;
  const nombres = c.slice(0, 6).map((x) => x.r[0]).join(", ");
  const centro = c.length
    ? `En el centro caen **${c.length}** de ${miles(N)} ${v.plural} (${nombres}${c.length > 6 ? "…" : ""}). Si los tres criterios no tuvieran relación, caerían ${dec1(esperado)}.`
    : `En el centro no cae nadie, de ${miles(N)} ${v.plural}. Si los tres criterios no tuvieran relación, caerían ${dec1(esperado)}.`;
  const corr = "Correlación de rangos entre criterios: " + V.corr.map((x) => `${v.sets[x.a].nombre}–${v.sets[x.b].nombre} ${signo(x.r)}`).join(" · ");
  return { centro, corr };
}

function Vista({ cfg, D, modo, tk }) {
  const temps = Object.keys(D.temporadas);
  const ids = cfg.venns.map((v) => v.id);
  const [P] = useState(() => leerParams(cfg.id));
  const [vid, setVid] = useState(() => entre(P.get("v"), ids, ids[0]));
  const [temp, setTemp] = useState(() => entre(P.get("t"), temps, temps[temps.length - 1]));
  const { min: qMin, max: qMax, ini: qIni } = D.corte;
  const [corte, setCorte] = useState(() => { const q = Math.round(+P.get("q")); return q >= qMin && q <= qMax ? q : qIni; });
  const [buscado, setBuscado] = useState(() => P.get("j") || null);
  const [hover, setHover] = useState(null);       // {i, px, py}
  usePublicarParams(cfg.id, {
    v: vid === ids[0] ? null : vid, t: temp === temps[temps.length - 1] ? null : temp,
    q: corte === qIni ? null : corte, j: buscado,
  });

  const caja = useRef(null);
  const w = useAncho(caja);
  const compacto = w > 0 && w < ANCHO_COMPACTO;
  const venn = cfg.venns.find((v) => v.id === vid);
  const paleta = modo === "dark" ? "oscuro" : "claro";
  const ligas = D.colores[paleta], circ = D.coloresCirculo[paleta];

  const V = useMemo(() => calcular(D, venn, temp, corte), [D, venn, temp, corte]);
  const pills = useMemo(() => pastillas(venn, compacto ? 1.9 : 1), [venn, compacto]);
  const fichas = useMemo(() => acomodar(V.reg, pills.map((p) => p.bloq), compacto), [V, pills, compacto]);
  const L = useMemo(() => lectura(V), [V]);
  const enVista = buscado && V.pop.some((r) => r[0] === buscado) ? buscado : null;
  // Un jugador que ya no está en la vista (otra posición o temporada) se suelta en vez de quedarse pegado al buscador.
  useEffect(() => { if (buscado && !enVista) setBuscado(null); }, [buscado, enVista]);

  const equipo = !!cfg.equipo;      // la misma vista sirve a «Equipo completo»: sin posición ni minutos
  const ambito = cfg.ambito || "de su posición";
  const contexto = { fichas, pills, reg: V.reg, tk, ligas, circ, buscado: enVista, equipo };
  const svg = useMemo(() => construirSvg({ ...contexto, hover: hover ? hover.i : null }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [fichas, pills, V, tk, ligas, circ, enVista, hover ? hover.i : null]);

  const mover = (e) => {
    const g = e.target.closest ? e.target.closest("[data-i]") : null;
    setHover(g ? { i: +g.dataset.i, px: e.clientX, py: e.clientY } : null);
  };
  const salir = (e) => { if (e.pointerType === "mouse") setHover(null); };

  const N = V.pop.length;
  const minimo = D.temporadas[temp].minimo;
  const enCurso = D.enCurso.includes(temp);
  const sub = `${venn.sets.map((s) => s.nombre).join(" · ")} · ${temp}${enCurso ? " (en curso)" : ""}${equipo ? "" : ` · mínimo ${miles(minimo)} minutos`} · ${miles(N)} ${venn.plural}`;

  // el estado del buscador
  const estado = (() => {
    if (!buscado) return null;
    const k = V.pop.findIndex((r) => r[0] === buscado);
    if (k < 0) return null;
    const r = V.pop[k];
    let m = 0;
    venn.sets.forEach((s, j) => { if (V.P3[j][k] >= 1 - V.q) m |= 1 << j; });
    const ps = venn.sets.map((s, j) => `${s.nombre} P${Math.round(V.P3[j][k] * 100)}`).join(" · ");
    return `${r[0]}${equipo ? "" : ` (${r[1]})`}: ${m ? "está en " + regionTxt(m, venn) : "no pasa ningún corte"} · ${ps}`;
  })();

  // ---- tooltip ----
  const f = hover ? fichas[hover.i] : null;
  const tip = f && (
    <Paper elevation={4} className="rx-tooltip" sx={{
      position: "fixed", left: Math.max(8, Math.min(hover.px + 14, window.innerWidth - 260)), top: hover.py + 14,
      p: 1.25, pointerEvents: "none", zIndex: 1500, border: 1, borderColor: "divider", fontSize: 12.5, width: 244,
    }}>
      {f.mas ? (
        <>
          <Box sx={{ fontWeight: 700 }}>{f.mas} más en «{regionTxt(f.mask, venn)}»</Box>
          <Box sx={{ color: "text.secondary" }}>Se muestran los que más destacan.</Box>
        </>
      ) : (
        <>
          <Box sx={{ fontWeight: 700 }}>{f.it.r[0]}</Box>
          <Box sx={{ color: "text.secondary", fontSize: 11.5, mb: 0.5 }}>{equipo ? `${D.ligas[f.it.r[2]]} · ${miles(f.it.r[4])} partidos` : `${f.it.r[1]} · ${D.ligas[f.it.r[2]]} · ${miles(f.it.r[4])} min`}</Box>
          {venn.sets.map((s, j) => {
            const ok = f.it.m & (1 << j);
            return (
              <Box key={s.nombre} sx={{ display: "flex", justifyContent: "space-between", gap: 1, fontWeight: ok ? 700 : 400 }}>
                <span>{ok ? "✓ " : ""}{s.nombre}</span>
                <span>{fdec(f.it.r[V.col(s)], s.dec ?? 2)} · P{Math.round(f.it.p[j] * 100)}</span>
              </Box>
            );
          })}
        </>
      )}
    </Paper>
  );

  // ---- los cruces, con nombre completo ----
  const cruces = [7, 3, 5, 6].filter((m) => V.reg[m].length).sort((a, b) => cuantos(b) - cuantos(a));
  const solos = [1, 2, 4];

  const descargar = () => {
    const pn = pastillas(venn, 1);
    const full = acomodar(V.reg, pn.map((p) => p.bloq), false);
    const [vx, vy, vw, vh] = VIEWBOX.split(" ").map(Number);
    return descargarPng({
      interior: construirSvg({ ...contexto, fichas: full, pills: pn, hover: null }), viewBox: [vx, vy, vw, vh],
      titulo: venn.titulo, subtitulo: `${temp}${enCurso ? " (en curso)" : ""} · el ${corte}% de arriba ${cfg.ambito || `de sus ${venn.plural}`}`,
      linea: `${V.reg[7].length} de ${miles(N)} cumplen las tres`,
      leyenda: D.ligas.map((l, i) => ({ color: ligas[i], texto: l })),
      fuente: `Datos: ${cfg.fuente}`, tk, modo, archivo: nombreArchivo(venn.id, temp, `top${corte}`),
    });
  };

  return (
    <>
      <Encabezado pregunta={cfg.pregunta} titulo={cfg.titulo} bajada={cfg.bajada} />

      {/* ---- filtros: una fila sobre el diagrama ---- */}
      <BarraFiltros sx={{ mb: estado ? 0.5 : 2 }}>
        {cfg.venns.length > 1 && (
          <Segmentado etiqueta="Diagrama" valor={vid} ancho={cfg.venns.length * 152}
            opciones={cfg.venns.map((v) => ({ valor: v.id, texto: v.tab }))}
            onChange={(v) => { setVid(v); setHover(null); }} />
        )}
        <Campo ancho={120}>
          <SelectTemporada valor={temp} temporadas={temps} onChange={(v) => { setTemp(v); setHover(null); }} />
        </Campo>
        <Box sx={{ width: 200, height: 40, display: "flex", flexDirection: "column", justifyContent: "center" }}>
          <Typography sx={{ fontSize: 11.5, color: "text.secondary", lineHeight: 1.1 }}>Corte: el {corte}% de arriba</Typography>
          <Slider min={qMin} max={qMax} step={1} value={corte} aria-label={`Corte, porcentaje de arriba ${ambito}`}
            valueLabelDisplay="auto" valueLabelFormat={(v) => `${v}%`} sx={{ py: "8px", mx: 1, width: "calc(100% - 16px)" }}
            onChange={(_e, v) => { setCorte(v); setHover(null); }} />
        </Box>
        <Campo ancho={210}>
          <Autocomplete size="small" options={V.pop.map((r) => r[0])} value={enVista} autoHighlight
            onChange={(_e, v) => setBuscado(v)}
            filterOptions={(opciones, { inputValue }) => {
              const q = sinAcentos(inputValue.trim());
              return q ? opciones.filter((o) => sinAcentos(o).includes(q)).slice(0, 30) : [];
            }}
            noOptionsText={equipo ? "Sin resultados: busca un equipo de esta temporada" : "Sin resultados: solo están quienes tienen minutos suficientes en esta posición y temporada"}
            renderInput={(p) => <TextField {...p} label={equipo ? "Buscar equipo" : "Buscar jugador"} />} />
        </Campo>
      </BarraFiltros>
      {estado && <Typography sx={{ fontSize: 13, color: "text.secondary", mb: 2 }}>{estado}</Typography>}

      <Box sx={{ display: "grid", gap: { xs: 2, lg: "0 32px" }, alignItems: "start", gridTemplateColumns: { xs: "minmax(0,1fr)", lg: "minmax(0,1fr) 340px" } }}>
        {/* ---- el diagrama ---- */}
        <Box sx={{ minWidth: 0 }}>
          <Typography component="h3" sx={{ fontSize: 17, fontWeight: 700, lineHeight: 1.25 }}>{venn.titulo}</Typography>
          <Typography sx={{ fontSize: 12.5, color: "text.secondary", mb: 1 }}>{sub}</Typography>
          <Typography sx={{ fontSize: 14, lineHeight: 1.5 }}><Md texto={L.centro} /></Typography>
          <Typography sx={{ fontSize: 12, color: "text.secondary", mb: 1 }}>{L.corr}</Typography>
          <Box ref={caja} sx={{ width: "100%", position: "relative" }}>
            {w > 0 && (
              <svg xmlns="http://www.w3.org/2000/svg" viewBox={compacto ? VIEWBOX_COMPACTO : VIEWBOX} width="100%" role="img"
                style={{ display: "block", height: "auto", maxHeight: compacto ? undefined : "max(440px, calc(100vh - 250px))", touchAction: "pan-y" }}
                aria-label={`Diagrama de Venn de ${venn.plural}: ${venn.sets.map((s) => s.nombre).join(", ")}. ${L.centro.replace(/\*\*/g, "")}`}
                onPointerMove={mover} onPointerDown={mover} onPointerLeave={salir}
                dangerouslySetInnerHTML={{ __html: svg }} />
            )}
            {tip}
          </Box>
          <Box sx={{ display: "flex", flexWrap: "wrap", gap: "4px 14px", fontSize: 12, color: "text.secondary", mt: 1 }}>
            {D.ligas.map((l, i) => (
              <Box key={l} sx={{ display: "inline-flex", alignItems: "center", gap: 0.6 }}>
                <Box sx={{ width: 11, height: 11, borderRadius: "50%", bgcolor: ligas[i] }} />{l}
              </Box>
            ))}
          </Box>
          <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mt: 0.5 }}>
            <Typography sx={{ fontSize: 12, color: "text.secondary" }}>Datos: {cfg.fuente}</Typography>
            <BotonDescarga alDescargar={descargar} />
          </Box>
        </Box>


        {/* ---- explicación ---- */}
        <Box sx={{ minWidth: 0 }}>
          <Rotulo>Qué mide cada círculo</Rotulo>
          <Box sx={{ display: "grid", gap: 0.5, mb: 2 }}>
            {venn.sets.map((s, j) => (
              <Box key={s.nombre} sx={{ display: "flex", gap: 1, alignItems: "baseline", fontSize: 12.5, color: "text.secondary" }}>
                <Box sx={{ width: 10, height: 10, borderRadius: "50%", flex: "none", bgcolor: circ[j], transform: "translateY(1px)" }} />
                <span><Box component="b" sx={{ color: "text.primary" }}>{s.nombre}.</Box> {s.def}</span>
              </Box>
            ))}
          </Box>

          <Rotulo>Quiénes caen en cada región</Rotulo>
          {cruces.map((m) => (
            <Typography key={m} sx={{ fontSize: 13, lineHeight: 1.5, mb: 0.75 }}>
              <Md texto={`**${regionTxt(m, venn)}** (${V.reg[m].length}${m === 7 ? ", los tres" : ""}): `
                + V.reg[m].slice(0, MAX_NOMBRES).map((x) => x.r[0]).join(", ")
                + (V.reg[m].length > MAX_NOMBRES ? ` y ${V.reg[m].length - MAX_NOMBRES} más.` : ".")} />
            </Typography>
          ))}
          <Typography sx={{ fontSize: 13, lineHeight: 1.5, color: "text.secondary", mb: 2 }}>
            Solo en un círculo: {solos.map((m) => `${venn.sets[Math.log2(m)].nombre} ${V.reg[m].length}`).join(" · ")}.
          </Typography>
        </Box>
      </Box>

      <Box sx={{ mt: 3, maxWidth: 1040 }}>
        <Rotulo>Cómo leer la gráfica</Rotulo>
        <ComoLeer texto={cfg.queMirar} />
      </Box>
    </>
  );
}

export default function VennVista({ id }) {
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
