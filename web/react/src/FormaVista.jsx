// Forma durante la temporada: la diferencia de xG por partido (a favor − en contra, sin penales) de un equipo en ventana móvil
// de 6 partidos, con la diferencia de goles en la misma ventana (más tenue) y el resultado de cada partido (G/E/P, de local o
// de visita) como marcas sobre el eje. Se puede comparar con un segundo equipo de la misma temporada.
//
// Todo el cálculo está hecho en el build (`web/charts/forma.py`): aquí solo se dibuja lo que viaja en `datos-forma.js`.
// El dibujo de las líneas es `LineasSvg.jsx` (reutilizable); el texto «Con estos filtros» es `formaLectura.js`.
import { useEffect, useMemo, useState } from "react";
import { ThemeProvider } from "@mui/material/styles";
import Autocomplete from "@mui/material/Autocomplete";
import Box from "@mui/material/Box";
import TextField from "@mui/material/TextField";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import Typography from "@mui/material/Typography";
import { entre, leerParams, usePublicarParams } from "./urlEstado.js";
import { useSitioTema } from "./theme.jsx";
import { cargarDatos } from "./datos.js";
import { Aviso, Cargando, Encabezado, Md, Parrafos, Rotulo, sinAcentos } from "./ui.jsx";
import LineasSvg, { MuestraLinea } from "./LineasSvg.jsx";
import { fechaCorta, lecturaForma, sg } from "./formaLectura.js";
import { fmt } from "./stats.js";

const OPACIDAD_GOLES = 0.42;

function Partido({ D, g, equipo, color, i, V, conNombre }) {
  if (i < 0 || i >= g.d.length) return null;
  const local = g.h[i] === 1;
  const rival = D.nombres[g.r[i]];
  const marcador = local ? `${equipo} ${g.gf[i]}–${g.gc[i]} ${rival}` : `${rival} ${g.gc[i]}–${g.gf[i]} ${equipo}`;
  const res = g.gf[i] > g.gc[i] ? "Ganó" : g.gf[i] < g.gc[i] ? "Perdió" : "Empató";
  const sinXg = g.xf[i] == null || g.xc[i] == null;
  const xg = sinXg ? null : (local ? `${fmt(g.xf[i])} – ${fmt(g.xc[i])}` : `${fmt(g.xc[i])} – ${fmt(g.xf[i])}`);
  const hasta = i + 1;
  let ventana;
  if (g.vx[i] != null) ventana = `Ventana (partidos ${hasta - V + 1} a ${hasta}): xG ${sg(g.vx[i])} · goles ${sg(g.vg[i])}`;
  else if (hasta < V) ventana = `Todavía no hay una ventana de ${V} partidos`;
  else ventana = `Sin ventana: a alguno de los ${V} partidos le faltan los tiros en Understat`;
  return (
    <Box sx={{ "& + &": { mt: 1, pt: 1, borderTop: 1, borderColor: "divider" } }}>
      <Box sx={{ fontWeight: 700, display: "flex", alignItems: "center", gap: 0.75 }}>
        {conNombre && <Box component="span" sx={{ width: 10, height: 10, borderRadius: "2px", bgcolor: color, flex: "none" }} />}
        <span>Partido {hasta}{conNombre ? ` · ${equipo}` : ""}</span>
      </Box>
      <Box sx={{ color: "text.secondary", fontSize: 11.5 }}>{fechaCorta(g.d[i])} · {local ? "de local" : "de visita"}</Box>
      <Box>{marcador} <Box component="span" sx={{ color: "text.secondary" }}>({res})</Box></Box>
      <Box sx={{ color: "text.secondary" }}>{sinXg ? "Understat no trae los tiros de este partido" : `xG ${xg}`}</Box>
      <Box sx={{ color: "text.secondary" }}>{ventana}</Box>
    </Box>
  );
}

function Vista({ cfg, D, modo, tk }) {
  const [P] = useState(() => leerParams(cfg.id));
  const V = D.ventana;
  const cerradas = D.temporadas.filter((t) => !D.enCurso[t]);
  const porDefecto = cerradas[cerradas.length - 1] || D.temporadas[D.temporadas.length - 1];
  const [temp, setTemp] = useState(() => entre(P.get("t"), D.temporadas, porDefecto));
  const [quiero, setQuiero] = useState(() => P.get("e") || D.inicial);
  const [cmp, setCmp] = useState(() => P.get("c") || null);

  const datos = D.t[temp];
  const lista = useMemo(() => Object.keys(datos).sort((a, b) => a.localeCompare(b, "es")), [datos]);
  const equipo = lista.includes(quiero) ? quiero : lista.includes(D.inicial) ? D.inicial : lista[0];
  const equipoB = cmp && cmp !== equipo && lista.includes(cmp) ? cmp : null;
  usePublicarParams(cfg.id, { t: temp === porDefecto ? null : temp, e: equipo === D.inicial ? null : equipo, c: equipoB });

  const col = cfg.colores[modo === "dark" ? "oscuro" : "claro"];
  const colRes = { G: cfg.resultado.G, E: tk.muted, P: cfg.resultado.P };
  const gA = datos[equipo], gB = equipoB ? datos[equipoB] : null;
  const enCurso = D.enCurso[temp];
  const equipos = [{ nombre: equipo, g: gA, color: col.a, punteada: false }, ...(gB ? [{ nombre: equipoB, g: gB, color: col.b, punteada: true }] : [])];

  const nMax = Math.max(...equipos.map((e) => e.g.d.length));
  const series = useMemo(() => equipos.flatMap((e, k) => [
    { id: `g${k}`, color: e.color, ancho: 1.8, opacidad: OPACIDAD_GOLES, punteada: e.punteada, puntos: e.g.vg.map((v, i) => ({ x: i + 1, y: v })) },
    { id: `x${k}`, color: e.color, ancho: 2.8, punteada: e.punteada, puntos: e.g.vx.map((v, i) => ({ x: i + 1, y: v })) },
  ]), [equipo, equipoB, temp, modo]);   // eslint-disable-line react-hooks/exhaustive-deps
  const marcas = useMemo(() => equipos.flatMap((e, k) => e.g.d.map((_, i) => {
    const res = e.g.gf[i] > e.g.gc[i] ? "G" : e.g.gf[i] < e.g.gc[i] ? "P" : "E";
    return { x: i + 1, fila: k, forma: e.g.h[i] === 1 ? "circulo" : "cuadrado", color: colRes[res], hueco: res === "E" };
  })), [equipo, equipoB, temp, modo]);   // eslint-disable-line react-hooks/exhaustive-deps

  const lectura = useMemo(
    () => equipos.flatMap((e) => lecturaForma(D, e.g, e.nombre, !!enCurso)),
    [D, equipo, equipoB, temp]);   // eslint-disable-line react-hooks/exhaustive-deps

  const resumen = (e) => {
    const n = e.g.d.length;
    const w = e.g.gf.filter((v, i) => v > e.g.gc[i]).length, l = e.g.gf.filter((v, i) => v < e.g.gc[i]).length;
    const v = e.g.vx.filter((q) => q != null);
    const rango = v.length ? ` La diferencia de xG por partido en ventanas de ${V} va de ${sg(Math.min(...v))} a ${sg(Math.max(...v))}.` : ` Aún no hay ventana de ${V} partidos.`;
    return `${e.nombre}, ${temp}: ${n} partidos, ${w} ganados, ${n - w - l} empatados y ${l} perdidos.${rango}`;
  };
  const aria = `Líneas de la diferencia de xG y de goles por partido en ventana móvil de ${V} partidos, con el resultado de cada partido debajo. ${equipos.map(resumen).join(" ")}`;

  const tooltip = (x) => (x - 1 >= nMax ? null : (
    <>
      {equipos.map((e) => <Partido key={e.nombre} D={D} g={e.g} equipo={e.nombre} color={e.color} i={x - 1} V={V} conNombre={equipos.length > 1} />)}
    </>
  ));

  const buscador = (valor, onChange, { etiqueta, placeholder, limpiable, excluir }) => (
    <Box>
      <Rotulo>{etiqueta}</Rotulo>
      <Autocomplete size="small" options={lista.filter((n) => n !== excluir)} value={valor} disableClearable={!limpiable}
        onChange={(_e, v) => onChange(v)}
        filterOptions={(opciones, { inputValue }) => {
          const q = sinAcentos(inputValue.trim());
          return opciones.filter((n) => sinAcentos(n).includes(q));
        }}
        noOptionsText="Ningún equipo con ese nombre en esta temporada"
        renderOption={(props, n) => {
          const { key, ...resto } = props;
          return (
            <li key={key} {...resto}>
              <Box sx={{ display: "flex", justifyContent: "space-between", gap: 1, width: "100%" }}>
                <span>{n}</span>
                <Box component="span" sx={{ color: "text.secondary", fontSize: 11.5 }}>{datos[n].l}</Box>
              </Box>
            </li>
          );
        }}
        renderInput={(p) => <TextField {...p} placeholder={placeholder} />} />
    </Box>
  );

  const leyendaMarca = (forma, texto) => (
    <Box component="span" sx={{ display: "inline-flex", alignItems: "center", gap: 0.5 }}>
      <svg width={11} height={11} aria-hidden="true">
        {forma === "circulo" ? <circle cx={5.5} cy={5.5} r={4.4} fill={tk.muted} /> : <rect x={1} y={1} width={9} height={9} rx={1} fill={tk.muted} />}
      </svg>
      {texto}
    </Box>
  );
  const leyendaRes = (color, hueco, texto) => (
    <Box component="span" sx={{ display: "inline-flex", alignItems: "center", gap: 0.5 }}>
      <svg width={11} height={11} aria-hidden="true">
        <circle cx={5.5} cy={5.5} r={4} fill={hueco ? tk.surface : color} stroke={color} strokeWidth={1.7} />
      </svg>
      {texto}
    </Box>
  );

  return (
    <>
      <Box sx={{ display: "grid", gap: 3, gridTemplateColumns: { xs: "minmax(0,1fr)", md: "minmax(0,1fr) 270px" }, alignItems: "start" }}>
        <Box sx={{ minWidth: 0 }}>
          <Encabezado pregunta={cfg.pregunta} titulo={cfg.titulo} bajada={cfg.bajada} />

          {quiero !== equipo && (
            <Typography sx={{ fontSize: 12, color: "text.secondary", mb: 1.5 }}>
              {quiero} no está en {temp} en las 5 ligas; se muestra {equipo}.
            </Typography>
          )}
          {enCurso && (
            <Typography sx={{ fontSize: 12.5, color: "text.secondary", mb: 1.5, maxWidth: 760 }}>
              {temp} va en curso ({enCurso} partidos por equipo como máximo): hay pocos puntos en la línea y nada de esto es una conclusión sobre su forma.
            </Typography>
          )}

          <Box sx={{ maxWidth: 1000, width: "100%" }}>
            <Typography component="h3" sx={{ fontSize: 13.5, fontWeight: 700, mb: 0.25 }}>
              {equipos.map((e, k) => (
                <span key={e.nombre}>{k > 0 && " y "}{e.nombre}</span>
              ))}
              <Box component="span" sx={{ fontWeight: 500, color: "text.secondary" }}> · {temp} · {gB && gA.l !== gB.l ? `${gA.l} y ${gB.l}` : gA.l}</Box>
            </Typography>
            <Box sx={{ display: "flex", flexWrap: "wrap", flexDirection: equipos.length > 1 ? { xs: "column", sm: "row" } : "row", columnGap: 2.5, rowGap: 0.5, fontSize: 12, color: "text.secondary", mb: 0.5 }}>
              {equipos.map((e) => (
                <Box key={e.nombre} component="span" sx={{ display: "inline-flex", flexWrap: "wrap", alignItems: "center", columnGap: 0.75, rowGap: 0.25 }}>
                  <MuestraLinea color={e.color} punteada={e.punteada} />
                  <span>{equipos.length > 1 && <strong style={{ color: "inherit" }}>{e.nombre}: </strong>}diferencia de xG por partido</span>
                  <MuestraLinea color={e.color} punteada={e.punteada} opacidad={OPACIDAD_GOLES} ancho={1.8} />
                  <span>diferencia de goles</span>
                </Box>
              ))}
            </Box>
            <LineasSvg
              tk={tk} ariaLabel={aria} series={series} alto={250}
              x={{ dominio: [1, Math.max(nMax, 2)], formato: (v) => String(v) }}
              y={{ formato: (v) => (v > 0 ? `+${v}` : String(v)) }}
              referencias={[{ y: 0, ancho: 1.4 }]}
              marcas={marcas} filasMarcas={equipos.map((e) => ({ color: e.color }))}
              tooltip={tooltip} />
            <Box sx={{ display: "flex", flexWrap: "wrap", columnGap: 2, rowGap: 0.25, fontSize: 11.5, color: "text.secondary", mt: 0.5 }}>
              {leyendaMarca("circulo", "De local")}
              {leyendaMarca("cuadrado", "De visita")}
              {leyendaRes(cfg.resultado.G, false, "Ganó")}
              {leyendaRes(tk.muted, true, "Empató")}
              {leyendaRes(cfg.resultado.P, false, "Perdió")}
            </Box>
            <Typography sx={{ fontSize: 11.5, color: "text.secondary", mt: 0.5 }}>
              Eje: número de partido en el orden en que se jugó. Cada punto de la línea promedia los {V} partidos que terminan ahí, así que empieza en el {V}.
              {gB && " Con dos equipos, el partido 12 de uno y el del otro no son del mismo día."}
              {" "}Arriba del cero, el equipo crea más de lo que concede.
            </Typography>
          </Box>

          <Box sx={{ mt: 1, display: "flex", justifyContent: "flex-end", maxWidth: 1000 }}>
            <Typography sx={{ fontSize: 12, color: "text.secondary" }}>Datos: {cfg.fuente}</Typography>
          </Box>

        </Box>
        <Box sx={{ display: "flex", flexDirection: "column", gap: 2.25, order: { xs: -1, md: 0 } }}>
          <Box sx={{ display: "grid", gap: 2.25, gridTemplateColumns: "minmax(0,1fr)" }}>
            <Box sx={{ gridColumn: "1 / -1" }}>
              <Rotulo>Temporada</Rotulo>
              <ToggleButtonGroup exclusive size="small" value={temp} aria-label="Temporada" sx={{ flexWrap: "wrap" }}
                onChange={(_e, v) => { if (v) setTemp(v); }}>
                {D.temporadas.map((t) => (
                  <ToggleButton key={t} value={t} sx={{ flex: "1 1 auto" }}>{t}{D.enCurso[t] ? " · en curso" : ""}</ToggleButton>
                ))}
              </ToggleButtonGroup>
            </Box>
            {buscador(equipo, (v) => setQuiero(v), { etiqueta: "Equipo", placeholder: "Busca un equipo" })}
            {buscador(equipoB, (v) => setCmp(v), { etiqueta: "Comparar con (opcional)", placeholder: "Sin comparar", limpiable: true, excluir: equipo })}
          </Box>
        </Box>
      </Box>

      <Box sx={{ mt: 2, maxWidth: 1040 }}>
        <Rotulo>Qué más mirar</Rotulo>
        <Parrafos texto={cfg.queMirar} sx={{ color: "text.primary" }} />
        <Box sx={{ mt: 2, pl: 2, borderLeft: 3, borderColor: "success.main" }}>
          <Typography sx={{ fontSize: 10.5, fontWeight: 700, letterSpacing: ".07em", textTransform: "uppercase", color: "success.main", mb: 0.75 }}>
            Con estos filtros · {equipos.map((e) => e.nombre).join(" y ")} · {temp}
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

export default function FormaVista({ id }) {
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
