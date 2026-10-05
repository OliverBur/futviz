// Una vista de dispersión (un punto por jugador o por equipo), configurada por `window.futvizVistas[id]`
// (ver `web/react_views.py`). Con una configuración distinta sale cada gráfica del sitio: Goles vs. xG,
// Perfil ofensivo, las defensivas, las de creación y las de equipos; y con `explorador` el "Crea tu
// gráfico", donde las dos variables las elige quien mira.
//
// Lo que MUI da y antes no había: highlight, color por rendimiento (colorGetter), controles accesibles,
// buscador con varios jugadores fijados, tabla (DataGrid) y panel de filtros en móvil. Zoom, pan y su
// barra de botones son propios (los de MUI son Pro): ver ZoomLayer.jsx.
import { useCallback, useDeferredValue, useEffect, useMemo, useRef, useState } from "react";
import { ThemeProvider, useTheme } from "@mui/material/styles";
import useMediaQuery from "@mui/material/useMediaQuery";
import Autocomplete, { createFilterOptions } from "@mui/material/Autocomplete";
import Accordion from "@mui/material/Accordion";
import AccordionSummary from "@mui/material/AccordionSummary";
import AccordionDetails from "@mui/material/AccordionDetails";
import Badge from "@mui/material/Badge";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import FormControlLabel from "@mui/material/FormControlLabel";
import IconButton from "@mui/material/IconButton";
import ListSubheader from "@mui/material/ListSubheader";
import MenuItem from "@mui/material/MenuItem";
import SwipeableDrawer from "@mui/material/SwipeableDrawer";
import Switch from "@mui/material/Switch";
import TextField from "@mui/material/TextField";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import ZoomIn from "@mui/icons-material/ZoomIn";
import ZoomOut from "@mui/icons-material/ZoomOut";
import ZoomOutMap from "@mui/icons-material/ZoomOutMap";
import CenterFocusStrong from "@mui/icons-material/CenterFocusStrong";
import ExpandMore from "@mui/icons-material/ExpandMore";
import TableChart from "@mui/icons-material/TableChart";
import FilterList from "@mui/icons-material/FilterList";
import Close from "@mui/icons-material/Close";
import { useSitioTema } from "./theme.jsx";
import { useTabla } from "./datos.js";
import { Grafica, FilaCtx } from "./Grafica.jsx";
import { Ranking } from "./Ranking.jsx";
import { Cuadrito, Posiciones } from "./Posiciones.jsx";
import { Tabla } from "./Tabla.jsx";
import { Aviso, Cargando, Md, Parrafos, Rotulo } from "./ui.jsx";
import { acercar, ajustarA, centrarEn, esBase } from "./zoom.js";
import { TOPE_DIF, colorRendimiento, conAlfa, divergente } from "./colores.js";
import { desvPob, media } from "./stats.js";
import { GENERADORES, lecturaExplorador } from "./insights.js";

const signo = (d, dec = 1) => (d >= 0 ? "+" : "−") + Math.abs(d).toFixed(dec);
const MAX_PINES = 6;   // fijados a la vez: con más, las etiquetas y los anillos dejan de leerse
const filtrar = createFilterOptions({ limit: 40, ignoreAccents: true });

// Lo que el explorador avisa sobre el r² (no depende de los datos).
const OJO_R2 = "El r² mide **relación lineal, y nada más**. Dos variables pueden tener un r² bajo y estar bien relacionadas de otra forma (en U, por ejemplo), y un r² alto no dice cuál causa cuál: puede haber una tercera cosa moviendo a las dos.\n\n"
  + "Ojo también con los pares que comparten aritmética. Un total y su tasa por 90' (goles y goles por 90'), o una parte y su todo (goles y goles + asistencias), van a dar un r² altísimo porque contienen literalmente el mismo dato — eso no es un hallazgo, es la definición.\n\n"
  + "Y el r² depende de la población: con el filtro de liga puesto se calcula sobre veinte y pico de puntos, donde salta mucho de una temporada a otra.";

// Rango de un eje: el de TODAS las temporadas, con margen (cambiar de temporada mueve los puntos, no la
// escala; y en el explorador cambiar de variable y volver deja el gráfico exactamente como estaba).
function rangoDe(valores) {
  let lo = Infinity, hi = -Infinity;
  for (const v of valores) { if (v == null) continue; if (v < lo) lo = v; if (v > hi) hi = v; }
  if (lo === Infinity) return { lo: 0, hi: 1, rango: [-0.06, 1.06] };
  const pad = (hi - lo) * 0.06 || (Math.abs(hi) * 0.06 || 1);
  return { lo, hi, rango: [lo - pad, hi + pad] };
}

function Vista({ cfg, T, modo, tk }) {
  const theme = useTheme();
  // `noSsr`: se lee de una vez y no tras el primer render, para no parpadear de escritorio a móvil.
  const movil = useMediaQuery(theme.breakpoints.down("md"), { noSsr: true });
  const exp = cfg.explorador || null;
  const esJugadores = cfg.entidad === "jugadores";
  const plural = esJugadores ? "jugadores" : "equipos";
  const filtros = cfg.filtros || {};
  const ayudas = T.ayudas || {};

  // --- los ejes ----------------------------------------------------------------------------------
  const [colX, setColX] = useState(exp ? exp.x : cfg.x.col);
  const [colY, setColY] = useState(exp ? exp.y : cfg.y.col);
  const infoVar = useMemo(() => (exp ? Object.fromEntries(exp.variables.map((v) => [v.col, v])) : null), [exp]);
  const X = exp ? { col: colX, label: infoVar[colX].label, corto: "Eje X", dec: infoVar[colX].dec } : cfg.x;
  const Y = exp ? { col: colY, label: infoVar[colY].label, corto: "Eje Y", dec: infoVar[colY].dec } : cfg.y;
  const xs = T.c[X.col], ys = T.c[Y.col];
  const decL = (a) => (a.decLista != null ? a.decLista : a.dec);   // decimales en la lista y en las etiquetas
  const ref = cfg.referencia || null;
  const diag = !!ref && ref.tipo === "diagonal";
  // "goles − xG" en medio de una frase ("la diagonal (goles − xG)") y "Goles − xG" como rótulo.
  const difEt = diag ? ref.dif[0].toUpperCase() + ref.dif.slice(1) : null;

  // --- estado de los filtros ------------------------------------------------------------------
  const [temporada, setTemporada] = useState(null);                // se resuelve abajo con las que tienen datos
  const [ligasOn, setLigasOn] = useState(() => new Set(T.ligas.map((_, i) => i)));
  const [posiciones, setPosiciones] = useState([]);                // vacío = todas
  const [nivel, setNivel] = useState("todos");
  const [sub21, setSub21] = useState(false);
  const [colorPor, setColorPor] = useState("liga");
  // Fijados: índices de JUGADOR (o equipo), no de fila, para que sobrevivan al cambio de temporada.
  const [fijados, setFijados] = useState([]);
  const [hoverBruto, setHoverBruto] = useState(null);
  const [hoverLiga, setHoverLiga] = useState(null);
  const metricas = useMemo(() => (exp ? [
    { id: "x", etiqueta: "Eje X", ayuda: `Los de mayor ${X.label}` },
    { id: "y", etiqueta: "Eje Y", ayuda: `Los de mayor ${Y.label}` },
  ] : cfg.metricas), [exp, cfg, X.label, Y.label]);
  const [metrica, setMetrica] = useState(metricas[0].id);          // por qué se ordena el Top 5 (y qué se rotula)
  const [hoverFila, setHoverFila] = useState(null);                // fila de la lista bajo el mouse
  const [pista, setPista] = useState(false);
  const [tablaAbierta, setTablaAbierta] = useState(false);
  const [filtrosAbiertos, setFiltrosAbiertos] = useState(false);

  // --- población: las filas con dato en lo que la vista necesita --------------------------------------
  const requiere = exp ? [X.col, Y.col] : cfg.requiere;
  const claveReq = requiere.join("|");
  const pobl = useMemo(() => {
    const cols = requiere.map((c) => T.c[c]);
    const out = [];
    for (let r = 0; r < T.n; r++) {
      let ok = true;
      for (const c of cols) if (c[r] == null) { ok = false; break; }
      if (ok) out.push(r);
    }
    return out;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [T, claveReq]);

  // Qué temporadas, posiciones y niveles existen en esa población (un control no ofrece una opción
  // que dejaría el gráfico vacío).
  const { temporadasOk, posDisp, nivelesDisp, haySub21 } = useMemo(() => {
    const ts = new Set(), ps = new Set(), vs = new Set();
    let sub = false;
    for (const r of pobl) {
      ts.add(T.f.t[r]);
      if (T.f.p) ps.add(T.f.p[r]);
      if (T.f.v) vs.add(T.f.v[r]);
      if (T.f.u && T.f.u[r]) sub = true;
    }
    return {
      temporadasOk: [...ts].sort((a, b) => a - b),
      posDisp: (T.posiciones || []).filter((_, i) => ps.has(i)),
      nivelesDisp: (T.niveles || []).filter((_, i) => vs.has(i)),
      haySub21: sub,
    };
  }, [pobl, T]);
  const tEf = temporadasOk.includes(temporada) ? temporada : temporadasOk[temporadasOk.length - 1];
  const tLabel = T.temporadas[tEf];

  // --- datos derivados ---------------------------------------------------------------------------
  const rx = useMemo(() => rangoDe(exp ? xs : pobl.map((r) => xs[r])), [exp, xs, pobl]);
  const ry = useMemo(() => rangoDe(exp ? ys : pobl.map((r) => ys[r])), [exp, ys, pobl]);
  const base = useMemo(() => ({ x0: rx.rango[0], x1: rx.rango[1], y0: ry.rango[0], y1: ry.rango[1] }), [rx, ry]);
  const [view, setView] = useState(base);
  const viewRef = useRef(view);
  viewRef.current = view;
  // Al cambiar de variables (explorador) la vista vuelve a la base de las nuevas.
  useEffect(() => { viewRef.current = base; setView(base); }, [base]);

  // Los promedios de las líneas punteadas son los de las temporadas juntas, no los de la mostrada:
  // si se movieran con cada cambio, "estar por encima del promedio" significaría algo distinto en cada una.
  const medias = useMemo(() => (ref && ref.tipo === "promedios" && pobl.length
    ? { x: media(pobl.map((r) => xs[r])), y: media(pobl.map((r) => ys[r])) } : null), [ref, pobl, xs, ys]);

  // Memoizados: si cambiaran de identidad en cada render, `series` se recalcularía y MUI
  // volvería a pintar los ~2.000 marcadores en cada movimiento del mouse.
  const colores = useMemo(() => T.colores[modo === "dark" ? "oscuro" : "claro"], [T, modo]);
  const div = useMemo(() => divergente(modo, T.divergente), [T, modo]);

  const visibles = useMemo(() => {
    const out = [];
    const posIdx = posiciones.map((p) => (T.posiciones || []).indexOf(p));
    const nivelIdx = nivel === "todos" ? -1 : (T.niveles || []).indexOf(nivel);
    for (const r of pobl) {
      if (T.f.t[r] !== tEf || !ligasOn.has(T.f.l[r])) continue;
      if (posIdx.length && !posIdx.includes(T.f.p[r])) continue;
      if (nivelIdx >= 0 && T.f.v[r] !== nivelIdx) continue;
      if (sub21 && !T.f.u[r]) continue;
      out.push(r);
    }
    return out;
  }, [pobl, T, tEf, ligasOn, posiciones, nivel, sub21]);

  // jugador -> su fila en lo que se ve (un jugador sin fila no juega en esta temporada o filtro).
  const filaDeJug = useMemo(() => {
    const m = new Map();
    for (const r of visibles) if (!m.has(T.f.j[r])) m.set(T.f.j[r], r);
    return m;
  }, [visibles, T]);
  const filasFijadas = useMemo(
    () => fijados.map((j) => filaDeJug.get(j)).filter((r) => r != null), [fijados, filaDeJug]);
  const pines = useMemo(() => new Set(filasFijadas), [filasFijadas]);

  const puntos = useMemo(() => visibles.map((r) => ({ r, x: xs[r], y: ys[r] })), [visibles, xs, ys]);

  // Identifica QUÉ puntos hay. Si cambia, el chart se remonta (ver Grafica.jsx) y el highlight por hover
  // que venía de los datos anteriores deja de valer.
  const claveDatos = `${cfg.id}|${X.col}|${Y.col}|${tEf}|${[...ligasOn].join(",")}|${posiciones.join("+")}|${nivel}|${sub21 ? 1 : 0}`;
  const hover = hoverBruto && hoverBruto.clave === claveDatos ? hoverBruto.item : null;

  // Un punto por fila, una serie por liga (así el color sigue a la entidad y el filtro de
  // liga es solo "qué series hay"). `posEnSerie` traduce fila -> (serie, índice) para el highlight,
  // e `idsPorSerie` al revés (para que el marcador sepa de qué fila es).
  const { series, posEnSerie, idsPorSerie, cuentas } = useMemo(() => {
    const pts = T.ligas.map(() => []);
    const posEnSerie = new Map();
    const idsPorSerie = {};
    T.ligas.forEach((n) => { idsPorSerie[n] = []; });
    visibles.forEach((r) => {
      const li = T.f.l[r];
      posEnSerie.set(r, { seriesId: T.ligas[li], dataIndex: pts[li].length });
      pts[li].push({ x: xs[r], y: ys[r], id: r });
      idsPorSerie[T.ligas[li]].push(r);
    });
    const series = T.ligas.map((nombre, li) => {
      const color = colores[nombre];
      const apagada = hoverLiga != null && hoverLiga !== li;   // pasar el mouse por un chip atenúa las demás
      return {
        id: nombre, type: "scatter", label: nombre, color, markerSize: cfg.entidad === "equipos" ? 5 : 4, data: pts[li],
        // El resaltado de MUI es solo del mouse (un punto); los fijados los pinta el marcador.
        highlightScope: { highlight: "item", fade: "none" },
        // El "color callback" de MUI X: un color por punto, calculado de su valor.
        colorGetter: ({ value }) => {
          const c = colorPor === "rendimiento" ? colorRendimiento(value.y - value.x, div) : color;
          return apagada ? conAlfa(c, 0.12) : c;
        },
      };
    });
    return { series, posEnSerie, idsPorSerie, cuentas: pts.map((p) => p.length) };
  }, [T, cfg.entidad, xs, ys, visibles, colores, colorPor, div, hoverLiga]);

  // --- Top 5 y etiquetas --------------------------------------------------------------
  // El Top 5 es de LO QUE SE VE: filtros y también el zoom (con la vista entera es el de siempre).
  // Y es lo único que la gráfica rotula, con el mismo número: lo escrito sobre los puntos y la
  // lista no pueden contradecirse. La vista se difiere para que la lista no parpadee mientras
  // se arrastra o se hace zoom.
  const vistaDiferida = useDeferredValue(view);
  // Para "Alejados": la distancia al centro de la nube, en desviaciones estándar de cada eje.
  const centro = useMemo(() => {
    if (visibles.length < 2) return null;
    const vx = visibles.map((r) => xs[r]), vy = visibles.map((r) => ys[r]);
    return { mx: media(vx), my: media(vy), sx: desvPob(vx) || 1, sy: desvPob(vy) || 1 };
  }, [visibles, xs, ys]);
  const valorDe = useCallback((r) => {
    if (metrica === "dif") return Math.abs(ys[r] - xs[r]);
    if (metrica === "dist") return centro ? Math.hypot((xs[r] - centro.mx) / centro.sx, (ys[r] - centro.my) / centro.sy) : 0;
    return metrica === "x" ? xs[r] : ys[r];
  }, [metrica, xs, ys, centro]);
  const ranking = useMemo(() => {
    const v = vistaDiferida;
    return visibles
      .filter((r) => xs[r] >= v.x0 && xs[r] <= v.x1 && ys[r] >= v.y0 && ys[r] <= v.y1)
      .sort((a, b) => valorDe(b) - valorDe(a) || ys[b] - ys[a] || xs[b] - xs[a])
      .slice(0, 5);
  }, [visibles, vistaDiferida, valorDe, xs, ys]);
  // Lo que se lee de cada fila, en la lista y en la etiqueta: el valor de la métrica elegida.
  const valX = (r) => xs[r].toFixed(decL(X)), valY = (r) => ys[r].toFixed(decL(Y));
  const textoValor = useCallback((r) => {
    if (metrica === "dif") return signo(ys[r] - xs[r], 1);
    if (metrica === "dist") return `${valX(r)} · ${valY(r)}`;
    return metrica === "x" ? valX(r) : valY(r);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [metrica, xs, ys, X.dec, Y.dec]);
  const nombre = useCallback((r) => T.nombre(r), [T]);
  const rotulos = useMemo(() => {
    // Con jugadores fijados el resto se atenúa: rotular a los demás sería ponerle nombre a puntos casi
    // invisibles. Se rotula solo a los fijados (con su diferencia, o sus dos valores si no hay diagonal).
    if (filasFijadas.length) {
      return filasFijadas.map((r) => ({ r, x: xs[r], y: ys[r], fijado: true,
        texto: `${nombre(r)} ${diag ? signo(ys[r] - xs[r], 1) : `${valX(r)} · ${valY(r)}`}` }));
    }
    return ranking.map((r, i) => ({ r, x: xs[r], y: ys[r], rango: i + 1, texto: `${nombre(r)} ${textoValor(r)}` }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filasFijadas, ranking, xs, ys, nombre, textoValor, diag, X.dec, Y.dec]);

  // --- interacción ------------------------------------------------------------------
  const itemDe = (r) => (r != null && posEnSerie.has(r) ? { type: "scatter", ...posEnSerie.get(r) } : null);
  // Resaltado de MUI: la fila de la lista bajo el mouse, o si no el punto bajo el mouse.
  const destacado = itemDe(hoverFila) || hover;
  const onDestacar = useCallback((it) => {
    setHoverBruto(it ? { clave: claveDatos, item: it } : null);
  }, [claveDatos]);

  const onView = useCallback((v) => setView(v), []);
  const hayZoom = !esBase(view, base);
  const tempPista = useRef(0);
  const onPista = useCallback(() => {
    setPista(true);
    clearTimeout(tempPista.current);
    tempPista.current = setTimeout(() => setPista(false), 1500);
  }, []);

  const mover = (v) => { viewRef.current = v; setView(v); };
  // Si el jugador que se acaba de fijar quedó fuera de lo que se ve, se centra la vista en él.
  const asegurarVisible = (r) => {
    const v = viewRef.current;
    if (xs[r] < v.x0 || xs[r] > v.x1 || ys[r] < v.y0 || ys[r] > v.y1) {
      mover(centrarEn(v, base, xs[r], ys[r]));
    }
  };
  // Pasados MAX_PINES se va el más antiguo: un clic nunca queda sin efecto.
  const agregarPin = (j) => {
    setFijados((p) => (p.includes(j) ? p : [...p, j].slice(-MAX_PINES)));
    const r = filaDeJug.get(j);
    if (r != null) asegurarVisible(r);
  };
  const quitarPin = (j) => setFijados((p) => p.filter((x) => x !== j));
  const alternarFila = (r) => (fijados.includes(T.f.j[r]) ? quitarPin(T.f.j[r]) : agregarPin(T.f.j[r]));
  // Desde la tabla llega el conjunto completo de filas marcadas: se aplica solo la diferencia
  // con lo que ya está fijado (los fijados sin fila en esta vista no se tocan).
  const fijarDesdeTabla = (ids) => {
    const quitar = new Set(filasFijadas.filter((r) => !ids.has(r)).map((r) => T.f.j[r]));
    const agregar = [...ids].filter((r) => !pines.has(r)).map((r) => T.f.j[r]);
    setFijados((p) => [...p.filter((j) => !quitar.has(j)), ...agregar.filter((j) => !p.includes(j))].slice(-MAX_PINES));
  };
  const onClicPunto = useCallback((_e, { seriesId, dataIndex }) => {
    const r = idsPorSerie[seriesId] ? idsPorSerie[seriesId][dataIndex] : null;
    if (r != null) setFijados((p) => (p.includes(T.f.j[r]) ? p.filter((x) => x !== T.f.j[r]) : [...p, T.f.j[r]].slice(-MAX_PINES)));
  }, [idsPorSerie, T]);

  const alternarLiga = (li) => setLigasOn((on) => {
    const todas = on.size === T.ligas.length;
    const sig = new Set(todas ? [li] : on);             // con todas activas, un clic aísla esa liga
    if (!todas) { if (sig.has(li)) sig.delete(li); else sig.add(li); }
    return sig.size ? sig : new Set(T.ligas.map((_, i) => i));
  });

  // --- caja de lectura, calculada sobre lo que se está viendo ------------------------------
  const todasLigas = ligasOn.size === T.ligas.length;
  const ambito = todasLigas ? "las 5 ligas" : [...ligasOn].sort().map((i) => T.ligas[i]).join(" + ");
  const lectura = useMemo(() => {
    if (exp) {
      return lecturaExplorador(visibles.map((r) => xs[r]), visibles.map((r) => ys[r]), X.label, Y.label, plural);
    }
    if (!cfg.insight) return null;
    if (!visibles.length) return { fija: `Ningún ${esJugadores ? "jugador" : "equipo"} cumple los filtros elegidos.`, salta: null };
    return GENERADORES[cfg.insight](T, visibles, ambito);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [exp, cfg, visibles, T, ambito, xs, ys, X.label, Y.label]);
  const estado = [tLabel, todasLigas ? "todas las ligas" : ambito,
    ...posiciones, nivel !== "todos" ? nivel.replace("Clubes ", "clubes ") : null, sub21 ? "sub-21" : null]
    .filter(Boolean).join(" · ");

  const info = useCallback((r) => ({
    nombre: T.nombre(r),
    sub: esJugadores ? `${T.equipo(r)} · ${T.liga(r)}` : T.liga(r),
    colorLiga: colores[T.liga(r)],
    filas: [
      [exp ? X.label : X.corto, xs[r].toFixed(X.dec)],
      [exp ? Y.label : Y.corto, ys[r].toFixed(Y.dec)],
      ...(diag ? [[difEt, signo(ys[r] - xs[r], 1)]] : []),
    ],
  }), [T, esJugadores, colores, exp, X, Y, xs, ys, diag, difEt]);
  const ctx = useMemo(() => ({ info }), [info]);

  // --- tabla -------------------------------------------------------------------------------------
  const filasTabla = useMemo(() => (tablaAbierta ? visibles.map((r) => ({
    id: r, nombre: T.nombre(r), equipo: T.equipo(r), liga: T.liga(r), posicion: T.posicion(r),
    min: T.c.min ? T.c.min[r] : null, x: xs[r], y: ys[r], dif: ys[r] - xs[r],
  })) : []), [tablaAbierta, visibles, T, xs, ys]);
  const columnas = useMemo(() => [
    { field: "nombre", headerName: esJugadores ? "Jugador" : "Equipo", flex: 1.4, minWidth: 130 },
    ...(esJugadores ? [{ field: "equipo", headerName: "Equipo", flex: 1, minWidth: 100 }] : []),
    { field: "liga", headerName: "Liga", width: 118 },
    ...(esJugadores && T.posiciones ? [{ field: "posicion", headerName: "Posición", width: 108,
      renderCell: ({ value }) => (value ? (
        <Box sx={{ display: "flex", alignItems: "center", gap: 0.75 }}><Cuadrito color={T.coloresPos[value]} />{value}</Box>
      ) : <Box sx={{ color: "text.secondary" }}>—</Box>) }] : []),
    ...(esJugadores && T.c.min ? [{ field: "min", headerName: "Minutos", type: "number", width: 92 }] : []),
    { field: "x", headerName: exp ? X.label : X.corto, type: "number", width: exp ? 140 : 100,
      valueFormatter: (v) => Number(v).toFixed(X.dec) },
    { field: "y", headerName: exp ? Y.label : Y.corto, type: "number", width: exp ? 140 : 100,
      valueFormatter: (v) => Number(v).toFixed(Y.dec) },
    ...(diag ? [{ field: "dif", headerName: difEt, type: "number", width: 124,
      valueFormatter: (v) => signo(Number(v), 2) }] : []),
  ], [esJugadores, T, exp, X, Y, diag, difEt]);

  // --- buscador: varios jugadores a la vez ----------------------------------------------------
  // Las opciones son JUGADORES (no filas): así un fijado sigue en la lista de chips aunque en esta
  // temporada o con estos filtros no tenga punto (se ve atenuado y dice por qué).
  const opcionesJug = useMemo(() => {
    const out = [...filaDeJug.keys()];
    fijados.forEach((j) => { if (!filaDeJug.has(j)) out.push(j); });
    return out;
  }, [filaDeJug, fijados]);
  const palabra = esJugadores ? "jugador" : "club";

  // --- los controles (se reutilizan en la columna lateral y en el panel móvil) ---------------------
  const ctlTemporada = (
    <Box>
      <Rotulo>Temporada</Rotulo>
      <ToggleButtonGroup exclusive size="small" fullWidth value={tEf} aria-label="Temporada"
        onChange={(_e, v) => v != null && setTemporada(v)}>
        {temporadasOk.map((i) => (
          <ToggleButton key={i} value={i} aria-label={T.temporadas[i]} sx={{ px: 0.5, fontSize: "11.5px !important" }}>
            {T.temporadas[i].slice(2)}
          </ToggleButton>
        ))}
      </ToggleButtonGroup>
    </Box>
  );
  const selectorVariable = (rotulo, valor, onChange) => (
    <Box>
      <Rotulo>{rotulo}</Rotulo>
      <TextField select size="small" fullWidth value={valor} onChange={(e) => onChange(e.target.value)}
        slotProps={{ select: { MenuProps: { slotProps: { paper: { sx: { maxHeight: 420 } } } } } }}>
        {exp && [...new Set(exp.variables.map((v) => v.grupo))].flatMap((g) => [
          <ListSubheader key={`g-${g}`}>{g}</ListSubheader>,
          ...exp.variables.filter((v) => v.grupo === g).map((v) => (
            <MenuItem key={v.col} value={v.col} sx={{ fontSize: 13, whiteSpace: "normal" }}>{v.label}</MenuItem>)),
        ])}
      </TextField>
    </Box>
  );
  const controles = (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 2.25 }}>
      {exp && selectorVariable("Eje horizontal", colX, setColX)}
      {exp && selectorVariable("Eje vertical", colY, setColY)}
      {!movil && ctlTemporada}

      {cfg.colorPor.length > 1 && (
        <Box>
          <Rotulo>Color por</Rotulo>
          <ToggleButtonGroup exclusive size="small" fullWidth value={colorPor} aria-label="Color por"
            onChange={(_e, v) => v && setColorPor(v)}>
            <ToggleButton value="liga">Liga</ToggleButton>
            <ToggleButton value="rendimiento">Rendimiento</ToggleButton>
          </ToggleButtonGroup>
        </Box>
      )}

      {filtros.posicion && posDisp.length > 0 && (
        <Box>
          <Rotulo>Posición</Rotulo>
          <Posiciones opciones={posDisp} colores={T.coloresPos} valor={posiciones} modo={modo}
            onChange={(v) => setPosiciones(v.length === posDisp.length ? [] : v)} />
        </Box>
      )}

      {filtros.nivel && nivelesDisp.length > 0 && (
        <Box>
          <Rotulo ayuda={ayudas.nivel}>Nivel del club</Rotulo>
          <ToggleButtonGroup exclusive size="small" fullWidth value={nivel} aria-label="Nivel del club"
            onChange={(_e, v) => v && setNivel(v)}>
            <ToggleButton value="todos">Todos</ToggleButton>
            {nivelesDisp.map((n) => (
              <ToggleButton key={n} value={n} sx={{ px: 0.5, fontSize: "11.5px !important" }}>
                {n.replace("Clubes ", "").replace(/^./, (c) => c.toUpperCase())}
              </ToggleButton>
            ))}
          </ToggleButtonGroup>
        </Box>
      )}

      <Box>
        <Rotulo>Buscar {esJugadores ? "jugadores" : "clubes"}</Rotulo>
        <Autocomplete multiple size="small" options={opcionesJug} filterOptions={filtrar}
          value={fijados}
          onChange={(_e, v) => {
            const nuevo = v.filter((j) => !fijados.includes(j));
            setFijados(v.slice(-MAX_PINES));
            nuevo.forEach((j) => { const r = filaDeJug.get(j); if (r != null) asegurarVisible(r); });
          }}
          getOptionLabel={(j) => T.nombres[j]}
          isOptionEqualToValue={(a, b) => a === b}
          disableCloseOnSelect filterSelectedOptions
          noOptionsText={`Ningún ${palabra} con esos filtros`}
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
          renderOption={(props, j) => {
            const { key, ...resto } = props;
            const r = filaDeJug.get(j);
            return (
              <li key={key} {...resto}>
                <Box sx={{ minWidth: 0 }}>
                  <Box sx={{ fontWeight: 600, fontSize: 13 }}>{T.nombres[j]}</Box>
                  <Box sx={{ fontSize: 11.5, color: "text.secondary" }}>
                    {r == null ? "Sin datos en esta vista" : esJugadores ? `${T.equipo(r)} · ${T.liga(r)}` : T.liga(r)}
                  </Box>
                </Box>
              </li>
            );
          }}
          renderInput={(p) => <TextField {...p} placeholder={fijados.length ? "" : `Escribe un ${palabra}…`} />} />
        <Typography sx={{ fontSize: 11.5, color: "text.secondary", mt: 0.5 }}>
          Fija hasta {MAX_PINES} para compararlos.
        </Typography>
      </Box>

      {filtros.sub21 && haySub21 && (
        <FormControlLabel sx={{ m: 0 }}
          label={<Typography sx={{ fontSize: 13, display: "flex", alignItems: "center", gap: 0.5 }}>
            Jugadores sub-21
            {ayudas.sub21 && <Tooltip title={ayudas.sub21} arrow enterTouchDelay={0}>
              <Box component="span" aria-label="Más información" tabIndex={0}
                sx={{ fontSize: 12, color: "text.secondary", cursor: "help", fontStyle: "italic", px: 0.5 }}>i</Box>
            </Tooltip>}
          </Typography>}
          control={<Switch size="small" checked={sub21} onChange={(e) => setSub21(e.target.checked)} />} />
      )}
    </Box>
  );

  const ranking5 = (
    <Ranking metricas={metricas} metrica={metrica} onMetrica={setMetrica} filas={ranking} nombre={nombre}
      equipo={(r) => (esJugadores ? T.equipo(r) : "")} valor={textoValor} fijadas={pines} enZoom={hayZoom}
      onElegir={alternarFila} onSobrevolar={setHoverFila} />
  );

  // Cuántos filtros "de verdad" hay puestos (temporada y color no cuentan: son vistas, no recortes).
  const nFiltros = (ligasOn.size < T.ligas.length ? 1 : 0) + (posiciones.length ? 1 : 0)
    + (nivel !== "todos" ? 1 : 0) + (sub21 ? 1 : 0);

  const minimo = T.minimos ? T.minimos[tLabel] : null;
  const subtitulo = exp
    ? `${Y.label} vs. ${X.label} · ${tLabel}`
    : cfg.subtitulo.replace("{min}", minimo != null ? String(minimo) : "").replace("{temporada}", tLabel);
  const vacio = visibles.length === 0 ? `Ningún ${esJugadores ? "jugador" : "equipo"} con estos filtros.` : null;

  return (
    <FilaCtx.Provider value={ctx}>
      <Box sx={{ display: "grid", gap: 3, gridTemplateColumns: { xs: "minmax(0,1fr)", md: "minmax(0,1fr) 270px" }, alignItems: "start" }}>

        {/* ---------------- columna del gráfico ---------------- */}
        <Box sx={{ minWidth: 0 }}>
          <Typography component="h2" sx={{ fontSize: 17, fontWeight: 700, color: "primary.main" }}>{cfg.titulo}</Typography>
          <Typography sx={{ fontSize: 13, color: "text.secondary", mb: 1.5 }}>{subtitulo}</Typography>

          {/* En móvil la temporada se queda a la vista; el resto de filtros van en el panel. */}
          {movil && (
            <Box sx={{ mb: 1.5 }}>
              {ctlTemporada}
              <Box sx={{ display: "flex", gap: 1, mt: 1.25 }}>
                <Badge color="primary" badgeContent={nFiltros} invisible={!nFiltros}>
                  <Button variant="outlined" size="small" startIcon={<FilterList />} onClick={() => setFiltrosAbiertos(true)}
                    sx={{ textTransform: "none", fontWeight: 600 }}>{exp ? "Ejes y filtros" : "Filtros"}</Button>
                </Badge>
                <Button variant="outlined" size="small" startIcon={<TableChart />} onClick={() => setTablaAbierta(true)}
                  sx={{ textTransform: "none", fontWeight: 600 }}>Ver tabla</Button>
              </Box>
            </Box>
          )}

          {/* leyenda-filtro + barra de zoom, en una fila */}
          <Box sx={{ display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 1, mb: 1 }}>
            <Box role="group" aria-label="Filtrar por liga" sx={{ display: "flex", flexWrap: "wrap", gap: 0.75 }}>
              {T.ligas.map((nombreLiga, li) => {
                const on = ligasOn.has(li);
                const color = colores[nombreLiga];
                return (
                  <Chip key={nombreLiga} size="small" clickable
                    variant={on ? "filled" : "outlined"}
                    aria-pressed={on}
                    title={ligasOn.size === T.ligas.length ? "Clic para ver solo esta liga" : undefined}
                    onClick={() => alternarLiga(li)}
                    onMouseEnter={() => setHoverLiga(li)} onMouseLeave={() => setHoverLiga(null)}
                    onFocus={() => setHoverLiga(li)} onBlur={() => setHoverLiga(null)}
                    label={`${nombreLiga} · ${on ? cuentas[li] : "—"}`}
                    avatar={<Box component="span" sx={{ width: "10px !important", height: "10px !important",
                      borderRadius: "50%", bgcolor: colorPor === "liga" ? color : tk.muted,
                      opacity: on ? 1 : 0.4, ml: "8px !important" }} />}
                    sx={{ bgcolor: on ? conAlfa(colorPor === "liga" ? color : "#888888", 0.14) : "transparent",
                      color: on ? "text.primary" : "text.secondary", borderColor: "divider" }} />
                );
              })}
            </Box>
            <Box role="toolbar" aria-label="Zoom y tabla" sx={{ display: "flex", alignItems: "center", gap: 0.25 }}>
              <Tooltip title="Acercar"><span><IconButton size="small" aria-label="Acercar"
                onClick={() => mover(acercar(viewRef.current, base, 0.6))}><ZoomIn fontSize="small" /></IconButton></span></Tooltip>
              <Tooltip title="Alejar"><span><IconButton size="small" aria-label="Alejar" disabled={!hayZoom}
                onClick={() => mover(acercar(viewRef.current, base, 1 / 0.6))}><ZoomOut fontSize="small" /></IconButton></span></Tooltip>
              <Tooltip title="Ajustar a los datos de esta vista"><span><IconButton size="small" aria-label="Ajustar a los datos"
                onClick={() => mover(ajustarA(puntos, base))}><CenterFocusStrong fontSize="small" /></IconButton></span></Tooltip>
              <Tooltip title="Ver todo"><span><IconButton size="small" aria-label="Ver todo" disabled={!hayZoom}
                onClick={() => mover(base)}><ZoomOutMap fontSize="small" /></IconButton></span></Tooltip>
              {!movil && (
                <Button size="small" startIcon={<TableChart fontSize="small" />} onClick={() => setTablaAbierta(true)}
                  sx={{ ml: 0.75, textTransform: "none", fontWeight: 600 }}>Ver tabla</Button>
              )}
            </Box>
          </Box>

          <Grafica series={series} view={view} viewRef={viewRef} base={base} onView={onView}
            rotulos={rotulos} destacado={destacado}
            onDestacar={onDestacar} onClicPunto={onClicPunto} tk={tk}
            pos={div.pos} neg={div.neg} hayZoom={hayZoom} pista={pista} onPista={onPista}
            // En móvil, el título corto del eje ("Precisión") en vez de la frase entera, que no cabe.
            ejeX={movil && !exp ? X.corto : X.label} ejeY={movil && !exp ? Y.corto : Y.label}
            claveDatos={claveDatos} pines={pines} idsPorSerie={idsPorSerie}
            referencia={ref} medias={medias} vacio={vacio}
            soloPositivoX={rx.lo >= 0} soloPositivoY={ry.lo >= 0} />

          <Box sx={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", gap: 1, mt: 0.75 }}>
            <Typography sx={{ fontSize: 12, color: "text.secondary" }}>
              Arrastra para mover · Ctrl + rueda o los botones para hacer zoom · clic en un punto para fijarlo
            </Typography>
            <Typography sx={{ fontSize: 12, color: "text.secondary" }}>Datos: {cfg.fuente}</Typography>
          </Box>

          {colorPor === "rendimiento" && diag && (
            <Box sx={{ mt: 1, maxWidth: 320 }}>
              <Typography sx={{ fontSize: 11.5, fontWeight: 600, color: "text.secondary", mb: 0.5 }}>{difEt}</Typography>
              <Box sx={{ height: 8, borderRadius: 1, border: 1, borderColor: "divider",
                background: `linear-gradient(to right, ${div.neg}, ${div.mid}, ${div.pos})` }} />
              <Box sx={{ display: "flex", justifyContent: "space-between", fontSize: 11.5, color: "text.secondary", mt: 0.25 }}>
                <span>−{TOPE_DIF} o menos</span><span>0</span><span>+{TOPE_DIF} o más</span>
              </Box>
            </Box>
          )}
        </Box>

        {/* ---------------- columna lateral: controles (escritorio) y Top 5 ---------------- */}
        <Box sx={{ display: "flex", flexDirection: "column", gap: 2.25 }}>
          {!movil && controles}
          {ranking5}
        </Box>
      </Box>

      {/* ---------------- caja de lectura ---------------- */}
      <Box sx={{ mt: 3, maxWidth: 820 }}>
        {cfg.queMirar && (
          <>
            <Rotulo>Qué mirar aquí</Rotulo>
            <Parrafos texto={cfg.queMirar} sx={{ color: "text.primary" }} />
          </>
        )}
        {lectura && (
          <Box sx={{ mt: cfg.queMirar ? 2 : 0, pl: 2, borderLeft: 3, borderColor: "success.main" }}>
            <Typography sx={{ fontSize: 10.5, fontWeight: 700, letterSpacing: ".07em", textTransform: "uppercase", color: "success.main", mb: 0.75 }}>
              En lo que estás viendo · {estado}
            </Typography>
            <Typography sx={{ fontSize: 14, lineHeight: 1.6, mb: lectura.salta ? 1 : 0 }}><Md texto={lectura.fija} /></Typography>
            {lectura.salta && <Typography sx={{ fontSize: 14, lineHeight: 1.6 }}><Md texto={lectura.salta} /></Typography>}
          </Box>
        )}
        {(cfg.porQue || exp) && (
          <Accordion disableGutters elevation={0} square sx={{ mt: 2, bgcolor: "transparent", "&:before": { display: "none" },
            borderTop: 1, borderColor: "divider" }}>
            <AccordionSummary expandIcon={<ExpandMore />} sx={{ px: 0 }}>
              <Rotulo>{exp ? "Qué no dice el r²" : "Por qué estas variables"}</Rotulo>
            </AccordionSummary>
            <AccordionDetails sx={{ px: 0 }}>
              <Parrafos texto={exp ? OJO_R2 : cfg.porQue} sx={{ fontSize: 13.5 }} />
            </AccordionDetails>
          </Accordion>
        )}
      </Box>

      {/* ---------------- panel de filtros (móvil) ---------------- */}
      {movil && (
        <SwipeableDrawer anchor="bottom" open={filtrosAbiertos} disableSwipeToOpen
          onOpen={() => setFiltrosAbiertos(true)} onClose={() => setFiltrosAbiertos(false)}
          slotProps={{ paper: { sx: { maxHeight: "82vh", borderTopLeftRadius: 16, borderTopRightRadius: 16, p: 2, pb: 3, overflowY: "auto" } } }}>
          <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mb: 2 }}>
            <Typography component="h2" sx={{ fontSize: 17, fontWeight: 700, color: "primary.main" }}>{exp ? "Ejes y filtros" : "Filtros"}</Typography>
            <IconButton aria-label="Cerrar los filtros" edge="end" onClick={() => setFiltrosAbiertos(false)}><Close /></IconButton>
          </Box>
          {controles}
          {/* El gráfico de atrás ya se actualiza en vivo; el botón dice cuánto queda y cierra. */}
          <Button fullWidth variant="contained" sx={{ mt: 2.5, textTransform: "none", fontWeight: 700 }}
            onClick={() => setFiltrosAbiertos(false)}>
            Ver {visibles.length.toLocaleString("es-MX")} {plural}
          </Button>
        </SwipeableDrawer>
      )}

      {/* ---------------- tabla ---------------- */}
      {tablaAbierta && (
        <Tabla abierta={tablaAbierta} onCerrar={() => setTablaAbierta(false)} filas={filasTabla} columnas={columnas}
          ordenInicial={{ field: "y", sort: "desc" }} fijadas={pines} onAlternar={alternarFila} onFijar={fijarDesdeTabla}
          titulo={tLabel} entidad={plural} archivo={`${cfg.id}-${tLabel}`} />
      )}
    </FilaCtx.Provider>
  );
}

// La vista con su tema y la tabla de datos que necesita (se pide la primera vez y se comparte).
export default function ScatterVista({ id }) {
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
