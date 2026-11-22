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
//
// "Un equipo" y "Un jugador" cambian el mapa de calor por los tiros uno por uno (un punto por remate, del tamaño
// de su xG, lleno si fue gol). Esos tiros vienen de otra tabla, la de la temporada que se mira
// (`shot_map.tabla_temporada`), que se pide solo cuando alguien elige a quién mirar: por eso una temporada a la vez.
import { useEffect, useMemo, useRef, useState } from "react";
import { entre, leerParams, usePublicarParams } from "./urlEstado.js";
import { ThemeProvider, useTheme } from "@mui/material/styles";
import useMediaQuery from "@mui/material/useMediaQuery";
import Autocomplete from "@mui/material/Autocomplete";
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import ListSubheader from "@mui/material/ListSubheader";
import MenuItem from "@mui/material/MenuItem";
import Paper from "@mui/material/Paper";
import TextField from "@mui/material/TextField";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import Typography from "@mui/material/Typography";
import { useSitioTema } from "./theme.jsx";
import { cargarDatos, useTabla } from "./datos.js";
import { Aviso, ComoLeer, Cargando, Encabezado, Md, Parrafos, QueDice, Rotulo, sinAcentos } from "./ui.jsx";
import { tiros } from "./insights.js";
import { agregar, filasDe, lecturaEntidad, sumar } from "./tiros.js";
import { miles } from "./stats.js";
import { BotonDescarga } from "./BotonDescarga.jsx";
import { BarraFiltros, Campo, Segmentado, SelectUno, masRecientePrimero } from "./Filtros.jsx";
import { descargarPng, nombreArchivo } from "./descargarImagen.js";
import { conAlfa } from "./colores.js";

const TODOS = "todos";
const VERES = ["equipo", "jugador"];                    // "todos" es el mapa de calor
const RADIO_MIN = 0.3, RADIO_POR_XG = 1.5;              // el punto de un tiro, en metros: crece con su xG

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
  // Los filtros de la URL (ver urlEstado.js): se leen una vez, al montarse.
  const [P] = useState(() => leerParams(cfg.id));
  const ultima = T.temporadas[T.temporadas.length - 1];
  const [ver, setVer] = useState(() => entre(P.get("ver"), VERES, TODOS));
  const [temporada, setTemporada] = useState(() => entre(P.get("t"), T.temporadas, ultima));
  const [tipoId, setTipoId] = useState(() => entre(P.get("tipo"), T.tipos.map((t) => t.id), TODOS));
  const [contra, setContra] = useState(() => P.get("lado") === "contra");
  const [quien, setQuien] = useState(() => P.get("quien") || "");   // «Nombre · clubes»; se busca en la tabla de la temporada
  usePublicarParams(cfg.id, {
    t: temporada === ultima ? null : temporada,
    tipo: tipoId === TODOS ? null : tipoId,
    ver: ver === TODOS ? null : ver,
    quien: ver === TODOS || !quien ? null : quien,
    lado: ver === "equipo" && contra ? "contra" : null,
  });
  const [celdaSobre, setCeldaSobre] = useState(null);
  const [tiroSobre, setTiroSobre] = useState(null);
  const svgRef = useRef(null);

  // --- los tiros de la temporada, solo si se mira a alguien -----------------------------------------------
  const porEntidad = ver !== TODOS;
  const [D, setD] = useState(null);
  const [errorD, setErrorD] = useState(false);
  useEffect(() => {
    if (!porEntidad) return undefined;
    let vivo = true;
    setErrorD(false);
    cargarDatos(`tiros-${temporada}`).then((p) => vivo && setD(p)).catch(() => vivo && setErrorD(true));
    return () => { vivo = false; };
  }, [porEntidad, temporada]);
  const Dt = porEntidad && D && D.t === temporada ? D : null;   // la tabla de ESTA temporada (al cambiar, hay un instante de carga)

  const ti = T.temporadas.indexOf(temporada);
  const tipo = T.tipos.find((t) => t.id === tipoId);
  const tipoAgg = tipoId === TODOS ? null : tipo;
  const sel = useMemo(() => agregar(T, ti, tipoAgg), [T, ti, tipoAgg]);
  const base = useMemo(() => agregar(T, ti, null).tot, [T, ti]);   // la misma temporada sin filtro de tipo

  // Oscuro: la rampa va de oscuro a claro (lo más alto es lo más brillante sobre la superficie oscura).
  const rampa = useMemo(() => (modo === "dark" ? [...T.rampa].reverse() : T.rampa), [T, modo]);
  const total = sel.tot.n;
  const z = (i) => (total ? (100 * sel.n[i]) / total : 0);
  const zmax = useMemo(() => { let m = 0; for (let i = 0; i < sel.n.length; i++) if (total && sel.n[i] / total * 100 > m) m = sel.n[i] / total * 100; return m; }, [sel, total]);

  // --- a quién se mira: los candidatos de la temporada, ordenados por tiros --------------------------------
  // Cada candidato lleva sus propios textos: el desplegable (MUI) puede seguir pintando la lista de la temporada
  // anterior un instante mientras llega la nueva, y no debe necesitar la tabla para decir cómo se llama cada uno.
  const candidatos = useMemo(() => {
    if (!Dt) return [];
    const jugador = ver === "jugador";
    const de = jugador ? Dt.c.j : Dt.c.e;
    const cuenta = new Map();
    for (let i = 0; i < de.length; i++) cuenta.set(de[i], (cuenta.get(de[i]) || 0) + 1);
    return [...cuenta].sort((a, b) => b[1] - a[1] || a[0] - b[0]).map(([id, n]) => {
      const nombre = jugador ? Dt.jug[id] : Dt.eq[id];
      const donde = jugador ? Dt.jugClubes[id] : (Dt.ligas[Dt.eqLiga[id]] || "");
      return { id, n, nombre, etiqueta: jugador ? `${nombre} · ${donde}` : nombre, clubes: jugador ? donde : "",
        sub: `${donde} · ${miles(n)} tiros`, buscar: sinAcentos(nombre) };
    });
  }, [Dt, ver]);
  // `quien` es el texto con el que se eligió (puede venir de la URL o de otra temporada): primero el nombre y los
  // clubes iguales; si no, el mismo nombre con más tiros; si no, nadie.
  const elegido = useMemo(() => {
    if (!Dt || !quien) return null;
    const nombre = quien.split(" · ")[0];
    return candidatos.find((o) => o.etiqueta === quien) || candidatos.find((o) => o.nombre === nombre) || null;
  }, [Dt, quien, candidatos]);
  const filas = useMemo(
    () => (Dt && elegido ? filasDe(T, Dt, { modo: ver, id: elegido.id, contra, tipo: tipoAgg }) : []),
    [T, Dt, elegido, ver, contra, tipoAgg]);
  const tiro = tiroSobre && Dt && filas.includes(tiroSobre.i) ? tiroSobre : null;
  const puntos = useMemo(() => {
    if (!Dt || !elegido) return null;
    const orden = [...filas].sort((a, b) => Dt.c.xg[b] - Dt.c.xg[a]);   // los grandes abajo, los chicos se ven encima
    return { sin: orden.filter((i) => !Dt.c.g[i]), gol: orden.filter((i) => Dt.c.g[i]) };
  }, [Dt, elegido, filas]);

  const ambito = temporada;
  const lectura = useMemo(() => {
    if (Dt && elegido) {
      return lecturaEntidad({
        nombre: elegido.nombre, clubes: elegido.clubes, modo: ver, contra,
        temporada, frase: tipo.frase || "", s: sumar(T, Dt, filas), base: sel.tot,
      });
    }
    return tiros(sel.tot, base, tipo.frase || "", ambito);
  }, [sel, base, tipo, ambito, T, Dt, elegido, filas, ver, contra, temporada]);
  const periodo = temporada;
  const subtitulo = Dt && elegido
    ? `${tipo.etiqueta} · ${periodo} · ${miles(filas.length)} remates ${ver === "equipo" && contra ? "contra " : "de "}${elegido.nombre}, sin penales`
    : `${tipo.etiqueta} · ${periodo} · ${miles(total)} remates, sin penales`;
  const enCurso = cfg.enCurso && cfg.enCurso[temporada];
  const cambiarVer = (v) => {
    setVer(v); setQuien(""); setTiroSobre(null);
  };
  const nombreTipo = (s, b) => {   // «Jugada abierta · Pie derecho» para el tooltip de un tiro
    const j = T.tipos.find((t) => t.col === "situation" && t.valor === T.jugadas[s]);
    const p = T.tipos.find((t) => t.col === "body_part" && t.valor === T.partes[b]);
    return `${j ? j.etiqueta : ""} · ${p ? p.etiqueta : "Otra parte del cuerpo"}`;
  };

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
    if (porEntidad) {   // el tiro más cercano al puntero, si cae dentro de su punto (con un poco de margen para el dedo)
      let mejor = null, d2 = Infinity;
      if (Dt && elegido) {
        for (const i of filas) {
          const dx = Dt.c.x[i] / 10 - p.x, dy = Dt.c.y[i] / 10 - p.y, q = dx * dx + dy * dy;
          const r = RADIO_MIN + (Dt.c.xg[i] / 1000) * RADIO_POR_XG + 0.9;
          if (q < r * r && q < d2) { mejor = i; d2 = q; }
        }
      }
      setTiroSobre(mejor == null ? null : { i: mejor, px: e.clientX, py: e.clientY });
      return;
    }
    const cx = Math.floor(p.x / lado), cy = Math.floor(p.y / lado);
    setCeldaSobre(cx >= 0 && cx < nx && cy >= 0 && cy < ny ? { cx, cy, px: e.clientX, py: e.clientY } : null);
  };
  const cel = celdaSobre ? celdaSobre.cy * nx + celdaSobre.cx : -1;

  const descargar = () => descargarPng({
    interior: svgRef.current.innerHTML, viewBox: [vb.x, vb.y, vb.w, vb.h],
    titulo: porEntidad && elegido ? elegido.nombre : cfg.titulo,
    subtitulo: [temporada, tipoId !== TODOS ? tipo.etiqueta : null, ver === "equipo" && contra ? "en contra" : null].filter(Boolean).join(" · "),
    nota: porEntidad ? "Lleno: gol · vacío: sin gol · tamaño: xG" : `Más ${modo === "dark" ? "claro" : "oscuro"}: más tiros`,
    fuente: `Datos: ${cfg.fuente}`, tk, modo,
    archivo: nombreArchivo("mapa-tiros", temporada, porEntidad && elegido ? elegido.nombre : null),
  });

  return (
    <>
      <Encabezado
            pregunta={!porEntidad ? cfg.pregunta
              : ver === "jugador" ? "¿Desde dónde remata este jugador?"
                : contra ? "¿Desde dónde le rematan a este equipo?" : "¿Desde dónde remata este equipo?"}
            titulo={porEntidad ? "Mapa de tiros" : cfg.titulo}
            bajada={porEntidad ? "Cada punto es un remate: lleno si fue gol, vacío si no. Entre más grande, más valía la ocasión (su xG)." : cfg.bajada}
            muestra={subtitulo} />

      <BarraFiltros sx={{ mb: 1 }}>
        <Segmentado etiqueta="Ver" valor={ver} onChange={cambiarVer} ancho={330}
          opciones={[{ valor: TODOS, texto: "Todos" }, { valor: "equipo", texto: "Un equipo" }, { valor: "jugador", texto: "Un jugador" }]} />
        {ver !== TODOS && (
          <Campo ancho={240}>
              <Autocomplete size="small" options={candidatos} value={elegido}
                loading={!Dt && !errorD} loadingText="Cargando los tiros…"
                onChange={(_e, o) => { setQuien(o ? o.etiqueta : ""); setTiroSobre(null); }}
                getOptionLabel={(o) => o.nombre} isOptionEqualToValue={(a, b) => a.id === b.id}
                filterOptions={(opciones, { inputValue }) => {
                  const q = sinAcentos(inputValue.trim());
                  return (q ? opciones.filter((o) => o.buscar.includes(q)) : opciones).slice(0, 60);
                }}
                renderOption={(props, o) => {
                  const { key, ...resto } = props;
                  return (
                    <li key={key} {...resto}>
                      <Box sx={{ minWidth: 0 }}>
                        <Box sx={{ fontSize: 13.5 }}>{o.nombre}</Box>
                        <Box sx={{ fontSize: 11.5, color: "text.secondary" }}>{o.sub}</Box>
                      </Box>
                    </li>
                  );
                }}
                noOptionsText={`Ningún ${ver === "jugador" ? "jugador" : "equipo"} con ese nombre en ${temporada}`}
                renderInput={(p) => <TextField {...p} label={ver === "jugador" ? "Jugador" : "Equipo"} />} />
          </Campo>
        )}
        {ver === "equipo" && (
          <Segmentado etiqueta="Tiros" valor={contra ? "contra" : "favor"} onChange={(v) => setContra(v === "contra")} ancho={190}
            opciones={[{ valor: "favor", texto: "A favor" }, { valor: "contra", texto: "En contra" }]} />
        )}
        <Campo ancho={130}>
          <SelectUno etiqueta="Temporada" valor={temporada} onChange={setTemporada}
            opciones={masRecientePrimero(T.temporadas).map((t) => ({ valor: t, texto: t }))} />
        </Campo>
        <Campo ancho={220}>
            <TextField select size="small" fullWidth label="Tipo de tiro" value={tipoId} onChange={(e) => setTipoId(e.target.value)}>
              {[null, "Jugada", "Parte del cuerpo"].flatMap((g) => [
                ...(g ? [<ListSubheader key={`g-${g}`}>{g}</ListSubheader>] : []),
                ...T.tipos.filter((t) => (t.grupo || null) === g).map((t) => (
                  <MenuItem key={t.id} value={t.id} sx={{ fontSize: 13 }}>{t.etiqueta}</MenuItem>)),
              ])}
            </TextField>
        </Campo>
      </BarraFiltros>
      {(ver !== TODOS || tipoId === "Set Piece") && (
        <Box sx={{ mb: 2 }}>
          {ver !== TODOS && Dt && !elegido && candidatos.length > 0 && (
            <Box sx={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 0.5, mb: 0.5 }}>
              <Typography sx={{ fontSize: 11.5, color: "text.secondary" }}>Prueba con</Typography>
              {candidatos.slice(0, 3).map((o) => (
                <Chip key={o.id} size="small" variant="outlined" label={o.nombre} onClick={() => setQuien(o.etiqueta)} />
              ))}
            </Box>
          )}
          {ver !== TODOS && (
            <Typography sx={{ fontSize: 11.5, color: "text.secondary" }}>
              {enCurso ? `${temporada} va en curso (${enCurso} jornadas): hay pocos tiros. ` : ""}
              Un {ver} se ve de una temporada a la vez.
            </Typography>
          )}
          {tipoId === "Set Piece" && <Typography sx={{ fontSize: 11.5, color: "text.secondary" }}>{T.hint}</Typography>}
        </Box>
      )}

      <Box>
        <Box sx={{ minWidth: 0 }}>

          <Box sx={{ display: "flex", flexDirection: { xs: "column", sm: "row" }, gap: 2, alignItems: "stretch" }}>
            <Box sx={{ flex: 1, minWidth: 0, maxWidth: 1000, position: "relative" }}>
              <svg ref={svgRef} role="img" aria-label={`Mapa de calor de los tiros: ${subtitulo}`}
                viewBox={`${vb.x} ${vb.y} ${vb.w} ${vb.h}`} style={{ width: "100%", height: "auto", display: "block", touchAction: "pan-y" }}
                onPointerMove={alMover} onPointerLeave={() => { setCeldaSobre(null); setTiroSobre(null); }} onPointerDown={alMover}>
                {/* el campo: la región dibujada, apenas teñida con el primer tono de la rampa */}
                <rect x={0} y={0} width={ancho} height={profundidad} fill={conAlfa(rampa[0], 0.28)} />
                {!porEntidad && Array.from({ length: nx * ny }, (_, i) => {
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
                  const e = capa === 0 ? { stroke: "rgba(7,12,14,.45)", strokeWidth: 3.4 } : { stroke: "rgba(255,255,255,.92)", strokeWidth: 1.5 };
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
                {/* los tiros uno por uno, encima de la cancha: vacío = sin gol, lleno = gol, tamaño = xG */}
                {puntos && (
                  <g pointerEvents="none">
                    {puntos.sin.map((i) => (
                      <circle key={i} cx={Dt.c.x[i] / 10} cy={Dt.c.y[i] / 10} r={RADIO_MIN + (Dt.c.xg[i] / 1000) * RADIO_POR_XG}
                        fill={conAlfa(tk.muted, 0.22)} stroke={tk.muted} strokeWidth={1.2} vectorEffect="non-scaling-stroke" />
                    ))}
                    {puntos.gol.map((i) => (
                      <circle key={i} cx={Dt.c.x[i] / 10} cy={Dt.c.y[i] / 10} r={RADIO_MIN + (Dt.c.xg[i] / 1000) * RADIO_POR_XG}
                        fill={tk.primary} stroke={tk.bg} strokeWidth={1.2} vectorEffect="non-scaling-stroke" />
                    ))}
                    {tiro && (
                      <circle cx={Dt.c.x[tiro.i] / 10} cy={Dt.c.y[tiro.i] / 10}
                        r={RADIO_MIN + (Dt.c.xg[tiro.i] / 1000) * RADIO_POR_XG + 0.5} fill="none" stroke={tk.primary}
                        strokeWidth={2} vectorEffect="non-scaling-stroke" />
                    )}
                  </g>
                )}
              </svg>
              {porEntidad && !puntos && (
                <Box sx={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center",
                  pointerEvents: "none", p: 2, textAlign: "center" }}>
                  <Typography sx={{ fontSize: 14, color: "text.primary", bgcolor: "background.paper", border: 1, borderColor: "divider",
                    borderRadius: 1, px: 1.5, py: 1 }}>
                    {errorD ? "No se pudieron cargar los tiros de esta temporada."
                      : !Dt ? "Cargando los tiros de la temporada…"
                        : quien ? `${quien.split(" · ")[0]} no tiene tiros en ${temporada}.`
                          : `Elige ${ver === "jugador" ? "un jugador" : "un equipo"} para ver sus tiros.`}
                  </Typography>
                </Box>
              )}
              {tiro && (
                <Paper elevation={4} className="rx-tooltip" sx={{ position: "fixed", left: tiro.px + 14, top: tiro.py + 14,
                  p: 1.25, pointerEvents: "none", zIndex: 1500, border: 1, borderColor: "divider", fontSize: 12.5 }}>
                  <Box sx={{ color: "text.secondary", mb: 0.5 }}>{nombreTipo(Dt.c.s[tiro.i], Dt.c.b[tiro.i])}</Box>
                  <Box><strong>{Dt.c.g[tiro.i] ? "Gol" : "Sin gol"}</strong> · xG {(Dt.c.xg[tiro.i] / 1000).toFixed(2)}</Box>
                  <Box sx={{ color: "text.secondary" }}>A {(Dt.c.y[tiro.i] / 10).toFixed(0)} m de la línea de fondo</Box>
                  {ver === "jugador" && <Box sx={{ color: "text.secondary" }}>
                    {Dt.eq[Dt.c.e[tiro.i]]}{Dt.c.v[tiro.i] >= 0 ? ` contra ${Dt.eq[Dt.c.v[tiro.i]]}` : ""}
                  </Box>}
                  {ver === "equipo" && Dt.c.v[tiro.i] >= 0 && <Box sx={{ color: "text.secondary" }}>
                    {contra ? `${Dt.eq[Dt.c.e[tiro.i]]}, ${Dt.jug[Dt.c.j[tiro.i]]}` : `Contra ${Dt.eq[Dt.c.v[tiro.i]]}, ${Dt.jug[Dt.c.j[tiro.i]]}`}
                  </Box>}
                </Paper>
              )}
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
            {!porEntidad && <Box sx={{ width: { xs: "100%", sm: 64 }, flex: "none", display: "flex", flexDirection: "column", alignItems: "flex-start" }}>
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
            </Box>}
          </Box>

          <Box sx={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", gap: 1, mt: 0.75 }}>
            <Typography sx={{ fontSize: 12, color: "text.secondary" }}>
              {porEntidad ? "Lleno: gol. Vacío: sin gol. El tamaño es el xG del tiro. Pasa el mouse o toca uno para ver el detalle."
                : "Pasa el mouse o toca una celda para ver los números crudos."}
            </Typography>
            <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
              <Typography sx={{ fontSize: 12, color: "text.secondary" }}>Datos: {cfg.fuente}</Typography>
              <BotonDescarga alDescargar={descargar} />
          </Box>
          </Box>
        </Box>
      </Box>

      <Box sx={{ mt: 3, maxWidth: 1040 }}>
        <Rotulo>Cómo leer la gráfica</Rotulo>
        <ComoLeer texto={cfg.queMirar} />
        <QueDice texto={lectura.fija} />
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
