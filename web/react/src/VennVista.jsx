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
import Button from "@mui/material/Button";
import Paper from "@mui/material/Paper";
import Slider from "@mui/material/Slider";
import TextField from "@mui/material/TextField";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import Typography from "@mui/material/Typography";
import Download from "@mui/icons-material/Download";
import { entre, leerParams, usePublicarParams } from "./urlEstado.js";
import { useSitioTema } from "./theme.jsx";
import { cargarDatos } from "./datos.js";
import { Aviso, Cargando, Encabezado, Md, Parrafos, Rotulo, sinAcentos } from "./ui.jsx";
import { miles } from "./milesComa.js";
import { acomodar, calcular, cuantos, pastillas, regionTxt } from "./vennCalculo.js";
import { VIEWBOX, VIEWBOX_COMPACTO, construirSvg, esc } from "./vennSvg.js";

const ANCHO_COMPACTO = 540;   // por debajo, las fichas van sin nombre (a esa escala no se leerían)
const MAX_NOMBRES = 14;       // los que se listan por cruce antes de mandar a la tabla
const NF = new Intl.NumberFormat("es-MX", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const f2 = (v) => NF.format(v);
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
  const pills = useMemo(() => pastillas(venn, V.cut, corte, compacto ? 1.9 : 1), [venn, V, corte, compacto]);
  const fichas = useMemo(() => acomodar(V.reg, pills.map((p) => p.bloq), compacto), [V, pills, compacto]);
  const L = useMemo(() => lectura(V), [V]);
  const enVista = buscado && V.pop.some((r) => r[0] === buscado) ? buscado : null;
  // Un jugador que ya no está en la vista (otra posición o temporada) se suelta en vez de quedarse pegado al buscador.
  useEffect(() => { if (buscado && !enVista) setBuscado(null); }, [buscado, enVista]);

  const contexto = { fichas, pills, reg: V.reg, tk, ligas, circ, buscado: enVista };
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
  const sub = `${venn.sets.map((s) => s.nombre).join(" · ")} · ${temp}${enCurso ? " (en curso)" : ""} · mínimo ${miles(minimo)} minutos · ${miles(N)} ${venn.plural}`;

  // el estado del buscador
  const estado = (() => {
    if (!buscado) return null;
    const k = V.pop.findIndex((r) => r[0] === buscado);
    if (k < 0) return null;
    const r = V.pop[k];
    let m = 0;
    venn.sets.forEach((s, j) => { if (V.P3[j][k] >= 1 - V.q) m |= 1 << j; });
    const ps = venn.sets.map((s, j) => `${s.nombre} P${Math.round(V.P3[j][k] * 100)}`).join(" · ");
    return `${r[0]} (${r[1]}): ${m ? "está en " + regionTxt(m, venn) : "no pasa ningún corte"} · ${ps}`;
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
          <Box sx={{ color: "text.secondary", fontSize: 11.5, mb: 0.5 }}>{f.it.r[1]} · {D.ligas[f.it.r[2]]} · {miles(f.it.r[4])} min</Box>
          {venn.sets.map((s, j) => {
            const ok = f.it.m & (1 << j);
            return (
              <Box key={s.nombre} sx={{ display: "flex", justifyContent: "space-between", gap: 1, fontWeight: ok ? 700 : 400 }}>
                <span>{ok ? "✓ " : ""}{s.nombre}</span>
                <span>{f2(f.it.r[V.col(s)])} · P{Math.round(f.it.p[j] * 100)}</span>
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

  // El logo va dentro del SVG como imagen incrustada: un SVG que se dibuja en un canvas no puede cargar archivos externos.
  const cargarLogo = async () => {
    try {
      const ruta = modo === "dark" ? "assets/logo-dark.png" : "assets/logo.png";
      const blob = await (await fetch(ruta)).blob();
      return await new Promise((ok, fallo) => { const fr = new FileReader(); fr.onload = () => ok(fr.result); fr.onerror = fallo; fr.readAsDataURL(blob); });
    } catch { return null; }
  };

  const descargar = async () => {
    const pn = pastillas(venn, V.cut, corte, 1);
    const full = acomodar(V.reg, pn.map((p) => p.bloq), false);
    const marca = construirSvg({ ...contexto, fichas: full, pills: pn, hover: null });
    const logo = await cargarLogo();
    const TW = 1200, TH = 1340, LH = 64, LW = LH * 1682 / 416;
    const doc = `<svg xmlns="http://www.w3.org/2000/svg" width="${TW}" height="${TH}" viewBox="0 0 ${TW} ${TH}" font-family="Inter, 'Segoe UI', Arial, sans-serif">`
      + `<rect width="${TW}" height="${TH}" fill="${tk.surface}"/>`
      + `<text x="60" y="96" font-size="52" font-weight="800" fill="${tk.primary}">${esc(venn.titulo)}</text>`
      + `<text x="60" y="140" font-size="23" fill="${tk.muted}">${esc(sub)}</text>`
      + `<text x="60" y="180" font-size="23" font-weight="600" fill="${tk["text-body"]}">${esc(L.centro.replace(/\*\*/g, "").split(" (")[0] + (V.reg[7].length ? "." : ""))}</text>`
      + `<svg x="60" y="200" width="1080" height="1066" viewBox="${VIEWBOX}">${marca}</svg>`
      + (logo ? `<image href="${logo}" x="${TW - 60 - LW}" y="${TH - 40 - LH}" width="${LW}" height="${LH}"/>` : "")
      + `<text x="60" y="1312" font-size="20" fill="${tk.muted}">Datos: ${esc(cfg.fuente)} · corte: el ${corte}% de arriba de su posición</text></svg>`;
    const url = URL.createObjectURL(new Blob([doc], { type: "image/svg+xml;charset=utf-8" }));
    const img = new Image();
    img.onload = () => {
      const c = document.createElement("canvas");
      c.width = TW * 2; c.height = TH * 2;
      c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
      URL.revokeObjectURL(url);
      c.toBlob((b) => {
        const a = document.createElement("a");
        a.href = URL.createObjectURL(b);
        a.download = `futviz-${venn.id}-${temp}-top${corte}.png`;
        a.click();
        setTimeout(() => URL.revokeObjectURL(a.href), 1000);
      }, "image/png");
    };
    img.src = url;
  };

  const resumenDetalle = { cursor: "pointer", font: "700 10.5px Inter, system-ui", letterSpacing: ".07em", textTransform: "uppercase", color: "var(--color-muted)", padding: "6px 0" };

  return (
    <>
      <Encabezado pregunta={cfg.pregunta} titulo={cfg.titulo} bajada={cfg.bajada} />

      <Box sx={{
        display: "grid", gap: { xs: 2, lg: 4 }, alignItems: "start",
        gridTemplateColumns: { xs: "minmax(0,1fr)", lg: "minmax(0,1fr) 340px" },
        gridTemplateAreas: { xs: '"controles" "venn" "info"', lg: '"venn controles" "venn info"' },
        gridTemplateRows: { lg: "auto 1fr" },
      }}>
        {/* ---- filtros ---- */}
        <Box sx={{ gridArea: "controles" }}>
          <Rotulo>Diagrama</Rotulo>
          <ToggleButtonGroup exclusive size="small" value={vid} aria-label="Diagrama" sx={{ flexWrap: "wrap", mb: 1.5 }}
            onChange={(_e, v) => { if (v) { setVid(v); setHover(null); } }}>
            {cfg.venns.map((v) => <ToggleButton key={v.id} value={v.id} sx={{ flex: "1 1 auto" }}>{v.tab}</ToggleButton>)}
          </ToggleButtonGroup>
          <Rotulo>Temporada</Rotulo>
          <ToggleButtonGroup exclusive size="small" value={temp} aria-label="Temporada" sx={{ flexWrap: "wrap", mb: 0.5 }}
            onChange={(_e, v) => { if (v) { setTemp(v); setHover(null); } }}>
            {temps.map((t) => <ToggleButton key={t} value={t}>{t}{D.enCurso.includes(t) ? "*" : ""}</ToggleButton>)}
          </ToggleButtonGroup>
          {D.enCurso.some((t) => temps.includes(t)) && (
            <Typography sx={{ fontSize: 11.5, color: "text.secondary", mb: 1.5 }}>* En curso: el mínimo de minutos es una fracción de lo jugado hasta ahora.</Typography>
          )}
          <Box sx={{ mt: 1.5 }}>
            <Rotulo>Corte: el {corte}% de arriba de su posición</Rotulo>
            <Slider size="small" min={qMin} max={qMax} step={1} value={corte} aria-label="Corte, porcentaje de arriba de su posición"
              valueLabelDisplay="auto" valueLabelFormat={(v) => `${v}%`} sx={{ mx: 1, width: "calc(100% - 28px)" }}
              marks={[qMin, 15, 30].map((value) => ({ value, label: `${value}%` }))}
              onChange={(_e, v) => { setCorte(v); setHover(null); }} />
          </Box>
          <Box sx={{ mt: 1.5, display: "flex", gap: 1, alignItems: "center", flexWrap: "wrap" }}>
            <Autocomplete size="small" sx={{ flex: "1 1 180px" }} options={V.pop.map((r) => r[0])} value={enVista} autoHighlight
              onChange={(_e, v) => setBuscado(v)}
              filterOptions={(opciones, { inputValue }) => {
                const q = sinAcentos(inputValue.trim());
                return q ? opciones.filter((o) => sinAcentos(o).includes(q)).slice(0, 30) : [];
              }}
              noOptionsText="Sin resultados: solo están quienes tienen minutos suficientes en esta posición y temporada"
              renderInput={(p) => <TextField {...p} label="Buscar jugador" />} />
            <Button size="small" variant="outlined" startIcon={<Download />} onClick={descargar}>Descargar imagen</Button>
          </Box>
          {estado && <Typography sx={{ fontSize: 13, color: "text.secondary", mt: 1 }}>{estado}</Typography>}
        </Box>

        {/* ---- el diagrama ---- */}
        <Box sx={{ gridArea: "venn", minWidth: 0 }}>
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
          <Typography sx={{ fontSize: 12, color: "text.secondary", mt: 1 }}>Datos: {cfg.fuente}</Typography>
        </Box>

        {/* ---- explicación ---- */}
        <Box sx={{ gridArea: "info", minWidth: 0 }}>
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
        <Rotulo>Qué más mirar</Rotulo>
        <Parrafos texto={cfg.queMirar} sx={{ color: "text.primary" }} />
        <details style={{ marginTop: 16, borderTop: "1px solid var(--color-border)", paddingTop: 8 }}>
          <summary style={resumenDetalle}>Por qué así</summary>
          <Parrafos texto={cfg.porQue} sx={{ fontSize: 13.5 }} />
        </details>
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
