// Una vista de dispersión (un punto por jugador o por equipo), configurada por `window.futvizVistas[id]`
// (ver `web/react_views.py`). Con una configuración distinta sale cada gráfica del sitio: Goles vs. xG,
// Perfil ofensivo, las defensivas, las de creación y las de equipos; y con `explorador` el "Crea tu
// gráfico", donde las dos variables las elige quien mira.
//
// Lo que MUI da y antes no había: highlight, color por rendimiento (colorGetter), controles accesibles,
// buscador con varios jugadores fijados, tabla (DataGrid) y panel de filtros en móvil. Zoom, pan y su
// barra de botones son propios (los de MUI son Pro): ver ZoomLayer.jsx.
import { useCallback, useDeferredValue, useEffect, useMemo, useRef, useState } from "react";
import { entre, leerParams, usePublicarParams } from "./urlEstado.js";
import { ThemeProvider, useTheme } from "@mui/material/styles";
import useMediaQuery from "@mui/material/useMediaQuery";
import Autocomplete from "@mui/material/Autocomplete";
import Badge from "@mui/material/Badge";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import Checkbox from "@mui/material/Checkbox";
import ListItemText from "@mui/material/ListItemText";
import Popover from "@mui/material/Popover";
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
import FilterList from "@mui/icons-material/FilterList";
import Close from "@mui/icons-material/Close";
import { useSitioTema } from "./theme.jsx";
import { useTabla } from "./datos.js";
import { Grafica, FilaCtx } from "./Grafica.jsx";
import { Ranking } from "./Ranking.jsx";
import { Posiciones } from "./Posiciones.jsx";
import { BotonDescarga } from "./BotonDescarga.jsx";
import { capturar, descargarPng, limpiarDispersion, nombreArchivo } from "./descargarImagen.js";
import { Aviso, Cargando, ComoLeer, Encabezado, QueDice, Rotulo, sinAcentos } from "./ui.jsx";
import { acercar, ajustarA, centrarEn, esBase, vistaDeZona, zonaDe } from "./zoom.js";
import { TOPE_DIF, colorRendimiento, conAlfa, divergente } from "./colores.js";
import { cuantil, media } from "./stats.js";
import { GENERADORES, lecturaExplorador } from "./insights.js";

const signo = (d, dec = 1) => (d >= 0 ? "+" : "−") + Math.abs(d).toFixed(dec);
const AJUSTE_MAX = 5;   // lo más que la vista de arranque se acerca a la base (con pocos puntos, más sería ver ampliado el vacío)
const MAX_PINES = 10;   // fijados a la vez: con más, las etiquetas y los anillos dejan de leerse

// El explorador es un lienzo libre: el texto solo dice cómo usarlo, sin medir nada entre las dos variables.
const EXPLICA_LIENZO = "Elige una variable para cada eje y cada punto es un jugador o un equipo, según la sección en la que estés. "
  + "Los filtros recortan la muestra y las dos variables se pueden cambiar las veces que quieras.\n"
  + "Resalta a quien quieras comparar para ver dónde cae en tus dos ejes y acerca el zoom para mirar una zona de cerca. "
  + "Los nombres escritos en la gráfica son los cinco que más tienen en uno de los dos ejes."



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
  const [masAbierto, setMasAbierto] = useState(false);   // "Más filtros" (solo en escritorio)
  const esJugadores = cfg.entidad === "jugadores";
  const plural = esJugadores ? "jugadores" : "equipos";
  const filtros = cfg.filtros || {};
  const ayudas = T.ayudas || {};

  // Los filtros de la URL (ver urlEstado.js): se leen una vez, al montarse, y cada estado de abajo arranca de ahí.
  const [P] = useState(() => leerParams(cfg.id));

  // --- los ejes ----------------------------------------------------------------------------------
  const colesExp = exp ? exp.variables.map((v) => v.col) : [];
  const [colX, setColX] = useState(exp ? entre(P.get("x"), colesExp, exp.x) : cfg.x.col);
  const [colY, setColY] = useState(exp ? entre(P.get("y"), colesExp, exp.y) : cfg.y.col);
  const infoVar = useMemo(() => (exp ? Object.fromEntries(exp.variables.map((v) => [v.col, v])) : null), [exp]);
  const X = exp ? { col: colX, label: infoVar[colX].label, corto: infoVar[colX].label, dec: infoVar[colX].dec } : cfg.x;
  const Y = exp ? { col: colY, label: infoVar[colY].label, corto: infoVar[colY].label, dec: infoVar[colY].dec } : cfg.y;
  const sgX = X.invertir ? -1 : 1;
  const xCrudo = T.c[X.col];
  const xs = useMemo(() => (sgX === 1 ? xCrudo : xCrudo.map((v) => (v == null ? null : -v))), [xCrudo, sgX]);
  // Un eje que se dibuja al revés (`invertir`, p. ej. el xG en contra: lo más bajo, arriba) se trabaja con los valores negados
  // —así el zoom, las líneas de percentil, los cuadrantes y el Top 5 no cambian— y solo se escribe con su signo al mostrarlo
  // (marcas del eje, lista, tooltip y tabla).
  const sgY = Y.invertir ? -1 : 1;
  const yCrudo = T.c[Y.col];
  const ys = useMemo(() => (sgY === 1 ? yCrudo : yCrudo.map((v) => (v == null ? null : -v))), [yCrudo, sgY]);
  const decL = (a) => (a.decLista != null ? a.decLista : a.dec);   // decimales en la lista y en las etiquetas
  const ref = cfg.referencia || null;
  const diag = !!ref && ref.tipo === "diagonal";
  // "goles − xG" en medio de una frase ("la diagonal (goles − xG)") y "Goles − xG" como rótulo.
  const difEt = diag ? ref.dif[0].toUpperCase() + ref.dif.slice(1) : null;
  const decDif = diag && ref.decDif != null ? ref.decDif : 1;   // decimales de la diferencia (por partido: 2)

  // --- estado de los filtros ------------------------------------------------------------------
  const [temporada, setTemporada] = useState(() => {                // null: se resuelve abajo con las que tienen datos
    const i = T.temporadas.indexOf(P.get("t"));
    return i >= 0 ? i : null;
  });
  const [ligasOn, setLigasOn] = useState(() => {
    const ligas = P.getAll("ligas").map((n) => T.ligas.indexOf(n)).filter((i) => i >= 0);
    return new Set(ligas.length ? ligas : T.ligas.map((_, i) => i));
  });
  // Las posiciones marcadas al abrir: las de la URL; si no hay `pos`, las de la vista (`posicionesIni`, p. ej. Medio y
  // Delantero en "Rematar vs. crear"). `pos=todas` es "ninguna marcada" cuando la vista abre con alguna.
  const posIni = useMemo(() => (cfg.posicionesIni || []).filter((p) => (T.posiciones || []).includes(p)), [cfg, T]);
  const [posiciones, setPosiciones] = useState(() => (P.has("pos")
    ? P.getAll("pos").filter((p) => (T.posiciones || []).includes(p)) : posIni));  // vacío = todas menos porteros
  const [nivel, setNivel] = useState(() => entre(P.get("nivel"), T.niveles || [], "todos"));
  const [sub21, setSub21] = useState(() => P.get("sub21") === "1");
  const [club, setClub] = useState(() => (T.f.e ? (T.equipos || []).indexOf(P.get("club")) : -1));   // -1: todos los clubes
  // Los puntos abren con el color de su liga pero tenues; lo que importa (el Top 5 y lo que se resalta) sale opaco. «Un tono» y
  // «Rendimiento» son opciones.
  const [colorPor, setColorPor] = useState(() => entre(P.get("color"), ["neutro", ...cfg.colorPor.filter((c) => c !== "liga")], "liga"));
  // Fijados: índices de JUGADOR (o equipo), no de fila, para que sobrevivan al cambio de temporada.
  // En la URL van por nombre: el índice cambia cuando se actualizan los datos.
  const [fijados, setFijados] = useState(() => P.getAll("fijar").map((n) => T.nombres.indexOf(n)).filter((j) => j >= 0).slice(-MAX_PINES));
  const [hoverBruto, setHoverBruto] = useState(null);
  const [hoverLiga, setHoverLiga] = useState(null);
  const metricas = useMemo(() => (exp ? [
    { id: "x", etiqueta: X.label, ayuda: `Los de mayor ${X.label}` },
    { id: "y", etiqueta: Y.label, ayuda: `Los de mayor ${Y.label}` },
  ] : cfg.metricas), [exp, cfg, X.label, Y.label]);
  // Por qué se ordena el Top 5 (y qué se rotula). Abre por la variable del eje Y: son los nombres que se conocen
  // (los que más goles, más asistencias...), no los más atípicos, que casi siempre son desconocidos.
  const [metrica, setMetrica] = useState(() => entre(P.get("top"), metricas.map((m) => m.id), "y"));
  const [hoverFila, setHoverFila] = useState(null);                // fila de la lista bajo el mouse
  const [pista, setPista] = useState(false);
  const [filtrosAbiertos, setFiltrosAbiertos] = useState(false);
  const [anclaMas, setAnclaMas] = useState(null);   // el botón «Más» de la barra de escritorio, ancla de su panel

  // --- población: las filas con dato en lo que la vista necesita --------------------------------------
  const requiere = exp ? [X.col, Y.col] : cfg.requiere;
  const claveReq = requiere.join("|");
  const pobl = useMemo(() => {
    const cols = requiere.map((c) => T.c[c]);
    // Las vistas "por 90'" piden más minutos (`minimoPor90`, ver `players.MIN_MINUTES_90`): con 500 una tasa se dispara
    // con un solo gol, y eso también estiraría los ejes.
    const minimos = cfg.minimoPor90 && T.minimos90 ? T.temporadas.map((t) => T.minimos90[t]) : null;
    const out = [];
    for (let r = 0; r < T.n; r++) {
      let ok = true;
      for (const c of cols) if (c[r] == null) { ok = false; break; }
      if (ok && minimos && T.c.min[r] < minimos[T.f.t[r]]) ok = false;
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

  const clubesDisp = useMemo(() => {
    if (!T.f.e || !esJugadores) return [];
    const vs = new Set();
    for (const r of pobl) if (T.f.t[r] === tEf) vs.add(T.f.e[r]);
    return [...vs].sort((a, b) => T.equipos[a].localeCompare(T.equipos[b], "es"));
  }, [pobl, T, tEf, esJugadores]);

  // --- datos derivados ---------------------------------------------------------------------------
  const rx = useMemo(() => rangoDe(exp ? xs : pobl.map((r) => xs[r])), [exp, xs, pobl]);
  const ry = useMemo(() => rangoDe(exp ? ys : pobl.map((r) => ys[r])), [exp, ys, pobl]);
  const base = useMemo(() => ({ x0: rx.rango[0], x1: rx.rango[1], y0: ry.rango[0], y1: ry.rango[1] }), [rx, ry]);
  // Lo que se ve: las filas de la temporada y los filtros elegidos.
  const visibles = useMemo(() => {
    const out = [];
    const posIdx = posiciones.map((p) => (T.posiciones || []).indexOf(p));
    const iPortero = (T.posiciones || []).indexOf("Portero");
    const nivelIdx = nivel === "todos" ? -1 : (T.niveles || []).indexOf(nivel);
    for (const r of pobl) {
      if (T.f.t[r] !== tEf || !ligasOn.has(T.f.l[r])) continue;
      // Sin ninguna posición marcada se ven todas MENOS los porteros: 77 de cada 97 quedan en (0, 0) en las vistas de
      // campo y, además, hacen casi todo "arriba del promedio". Marcar "Portero" (o las cuatro) los incluye.
      if (posIdx.length ? !posIdx.includes(T.f.p[r]) : (iPortero >= 0 && T.f.p[r] === iPortero)) continue;
      if (nivelIdx >= 0 && T.f.v[r] !== nivelIdx) continue;
      if (sub21 && !T.f.u[r]) continue;
      if (club >= 0 && T.f.e[r] !== club) continue;
      out.push(r);
    }
    return out;
  }, [pobl, T, tEf, ligasOn, posiciones, nivel, sub21, club]);

  const puntos = useMemo(() => visibles.map((r) => ({ r, x: xs[r], y: ys[r] })), [visibles, xs, ys]);

  // La vista de arranque se AJUSTA a esos puntos, no al rango de todas las temporadas (`base`): con una temporada
  // a medias, o con un filtro que deja pocos, abrir con todo el rango dejaba los puntos amontonados en una
  // esquina. `base` sigue siendo el límite del zoom y lo que enseña "Ver todo". Se reajusta al cambiar los
  // filtros, la temporada o los ejes.
  const ajuste = useMemo(() => ajustarA(puntos, base, 0.08, AJUSTE_MAX), [puntos, base]);
  const [view, setView] = useState(ajuste);
  const viewRef = useRef(view);
  viewRef.current = view;
  useEffect(() => { viewRef.current = ajuste; setView(ajuste); }, [ajuste]);

  // Los promedios de las líneas punteadas son los de las temporadas juntas, no los de la mostrada:
  // si se movieran con cada cambio, "estar por encima del promedio" significaría algo distinto en cada una.
  // La línea de la élite (`referencia.zonas`): el valor de X que deja arriba al `1 − pct` de lo que se ve.
  const corteElite = useMemo(() => (ref && ref.zonas && visibles.length >= 5
    ? cuantil(visibles.map((r) => xs[r]), ref.zonas.pct) : null), [ref, visibles, xs]);
  // Las líneas punteadas de las vistas con cuadrantes: un valor fijo de la vista (`fijo`, p. ej. el percentil 70 de una escala
  // de percentiles); el percentil `cuantil` de lo que se ve en cada eje (así el cuadrante bueno deja solo a los más
  // destacados); o el promedio de las temporadas juntas.
  const medias = useMemo(() => {
    if (!ref || ref.tipo !== "promedios" || !pobl.length) return null;
    if (ref.fijo) return ref.fijo;
    if (ref.cuantil) {
      return visibles.length >= 5
        ? { x: cuantil(visibles.map((r) => xs[r]), ref.cuantil), y: cuantil(visibles.map((r) => ys[r]), ref.cuantil) } : null;
    }
    return { x: media(pobl.map((r) => xs[r])), y: media(pobl.map((r) => ys[r])) };
  }, [ref, pobl, visibles, xs, ys]);
  // Las líneas que parten la gráfica en cuadrantes que se pueden señalar con el cursor y acercar con un clic.
  const lineas = useMemo(() => {
    if (ref && ref.zonas && corteElite != null) return { tipo: "diag", cx: corteElite };
    if (ref && ref.tipo === "promedios" && ref.cuadrantes && medias) return { tipo: "rect", cx: medias.x, cy: medias.y };
    return null;
  }, [ref, corteElite, medias]);

  // Memoizados: si cambiaran de identidad en cada render, `series` se recalcularía y MUI
  // volvería a pintar los ~2.000 marcadores en cada movimiento del mouse.
  const colores = useMemo(() => T.colores[modo === "dark" ? "oscuro" : "claro"], [T, modo]);
  const div = useMemo(() => divergente(modo, T.divergente), [T, modo]);


  // jugador -> su fila en lo que se ve (un jugador sin fila no juega en esta temporada o filtro).
  const filaDeJug = useMemo(() => {
    const m = new Map();
    for (const r of visibles) if (!m.has(T.f.j[r])) m.set(T.f.j[r], r);
    return m;
  }, [visibles, T]);
  const filasFijadas = useMemo(
    () => fijados.map((j) => filaDeJug.get(j)).filter((r) => r != null), [fijados, filaDeJug]);
  const pines = useMemo(() => new Set(filasFijadas), [filasFijadas]);


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
          const c = colorPor === "rendimiento" ? colorRendimiento(value.y - value.x, div)
            : colorPor === "neutro" && !pines.has(value.id) ? tk["brand-accent"] : color;
          return apagada ? conAlfa(c, 0.12) : c;
        },
      };
    });
    return { series, posEnSerie, idsPorSerie, cuentas: pts.map((p) => p.length) };
  }, [T, cfg.entidad, xs, ys, visibles, colores, colorPor, div, hoverLiga, pines, tk["brand-accent"]]);

  // --- Top 5 y etiquetas --------------------------------------------------------------
  // El Top 5 es de LO QUE SE VE: filtros y también el zoom (con la vista entera es el de siempre).
  // Y es lo único que la gráfica rotula, con el mismo número: lo escrito sobre los puntos y la
  // lista no pueden contradecirse. La vista se difiere para que la lista no parpadee mientras
  // se arrastra o se hace zoom.
  const vistaDiferida = useDeferredValue(view);
  // El Top 5 ordena por una de las dos variables. Donde MENOS es mejor (los goles o el xG en contra) abre por los
  // que menos tienen: la lista es de los mejores, no de los peores (`menosEsMejor` en la configuración).
  const menosEsMejor = !!(metricas.find((m) => m.id === metrica) || {}).menosEsMejor;
  const valorDe = useCallback((r) => (metrica === "x" ? xs[r] : ys[r]), [metrica, xs, ys]);
  const ranking = useMemo(() => {
    const v = vistaDiferida;
    return visibles
      .filter((r) => xs[r] >= v.x0 && xs[r] <= v.x1 && ys[r] >= v.y0 && ys[r] <= v.y1)
      .sort((a, b) => (menosEsMejor ? -1 : 1) * (valorDe(b) - valorDe(a) || ys[b] - ys[a] || xs[b] - xs[a]))
      .slice(0, 5);
  }, [visibles, vistaDiferida, valorDe, xs, ys, menosEsMejor]);
  // Lo que se lee de cada fila, en la lista y en la etiqueta: el valor de la métrica elegida.
  const valX = (r) => (sgX * xs[r]).toFixed(decL(X)), valY = (r) => (sgY * ys[r]).toFixed(decL(Y));
  const textoValor = useCallback((r) => {
    return metrica === "x" ? valX(r) : valY(r);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [metrica, xs, ys, X.dec, Y.dec]);
  const nombre = useCallback((r) => T.nombre(r), [T]);
  const rotulos = useMemo(() => {
    // Con jugadores fijados el resto se atenúa: rotular a los demás sería ponerle nombre a puntos casi
    // invisibles. Se rotula solo a los fijados (con su diferencia, o sus dos valores si no hay diagonal).
    if (filasFijadas.length) {
      return filasFijadas.map((r) => ({ r, x: xs[r], y: ys[r], fijado: true,
        texto: `${nombre(r)} ${diag ? signo(sgY * ys[r] - sgX * xs[r], decDif) : `${valX(r)} · ${valY(r)}`}` }));
    }
    return ranking.map((r, i) => ({ r, x: xs[r], y: ys[r], rango: i + 1, texto: `${nombre(r)} ${textoValor(r)}` }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filasFijadas, ranking, xs, ys, nombre, textoValor, diag, X.dec, Y.dec, decDif]);

  // --- interacción ------------------------------------------------------------------
  const itemDe = (r) => (r != null && posEnSerie.has(r) ? { type: "scatter", ...posEnSerie.get(r) } : null);
  // Resaltado de MUI: la fila de la lista bajo el mouse, o si no el punto bajo el mouse.
  const destacado = itemDe(hoverFila) || hover;
  const onDestacar = useCallback((it) => {
    setHoverBruto(it ? { clave: claveDatos, item: it } : null);
  }, [claveDatos]);

  const onView = useCallback((v) => setView(v), []);
  // "Con zoom" es haberse movido de la vista de arranque (el ajuste) y de la base; `fueraDeBase`, en cambio,
  // es poder alejarse todavía más.
  const hayZoom = !esBase(view, ajuste) && !esBase(view, base);
  const fueraDeBase = !esBase(view, base);
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
  const onClicPunto = useCallback((_e, { seriesId, dataIndex }) => {
    const r = idsPorSerie[seriesId] ? idsPorSerie[seriesId][dataIndex] : null;
    if (r != null) setFijados((p) => (p.includes(T.f.j[r]) ? p.filter((x) => x !== T.f.j[r]) : [...p, T.f.j[r]].slice(-MAX_PINES)));
  }, [idsPorSerie, T]);

  // Un clic en un cuadrante: la vista se recorta justo en las líneas punteadas y se ajusta a los jugadores que caen en él.
  const [zonaAct, setZonaAct] = useState(null);       // el cuadrante al que se acercó el último clic, y la vista que dejó
  const alZona = (id) => {
    if (!lineas) return;
    const pts = visibles.filter((r) => zonaDe(lineas, xs[r], ys[r]) === id).map((r) => ({ x: xs[r], y: ys[r] }));
    if (!pts.length) return;
    const v = vistaDeZona(pts, lineas, id, base);
    mover(v);
    setZonaAct({ id, v });
  };
  // El chip «zona» vive mientras la vista siga siendo la que dejó ese clic: al mover o acercar a mano desaparece solo.
  const nombreZona = zonaAct && ref ? ((ref.zonas && ref.zonas[zonaAct.id]) || (ref.cuadrantes && ref.cuadrantes[zonaAct.id]) || null) : null;
  const enZona = !!nombreZona && ["x0", "x1", "y0", "y1"].every((k) => Math.abs(view[k] - zonaAct.v[k]) < 1e-9);

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
      return lecturaExplorador({
        nombres: visibles.map((r) => T.nombre(r)), xs: visibles.map((r) => sgX * xs[r]), ys: visibles.map((r) => sgY * ys[r]),
        etX: X.label, etY: Y.label, decX: X.dec, decY: Y.dec, ambito,
      });
    }
    if (!cfg.insight) return null;
    if (!visibles.length) return { fija: `Ningún ${esJugadores ? "jugador" : "equipo"} cumple los filtros elegidos.`, salta: null };
    return GENERADORES[cfg.insight](T, visibles, ambito);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [exp, cfg, visibles, T, ambito, xs, ys, X.label, Y.label]);
  // Los filtros a la URL. La temporada va siempre (un enlace compartido no debe saltar a otra cuando salga una
  // nueva); lo demás solo si no es lo de por defecto.
  usePublicarParams(cfg.id, {
    t: tLabel,
    ligas: todasLigas ? [] : [...ligasOn].sort((a, b) => a - b).map((i) => T.ligas[i]),
    pos: posiciones.length === posIni.length && posiciones.every((p) => posIni.includes(p)) ? null
      : posiciones.length ? posiciones : ["todas"],
    nivel: nivel === "todos" ? null : nivel,
    sub21: sub21 ? "1" : null,
    club: club >= 0 ? T.equipos[club] : null,
    color: colorPor === "liga" ? null : colorPor,
    fijar: fijados.map((j) => T.nombres[j]),
    top: metrica === "y" ? null : metrica,
    x: exp && colX !== exp.x ? colX : null,
    y: exp && colY !== exp.y ? colY : null,
  });
  const sinPorteros = !posiciones.length && posDisp.includes("Portero");

  const info = useCallback((r) => ({
    nombre: T.nombre(r),
    sub: esJugadores ? `${T.equipo(r)} · ${T.liga(r)}` : T.liga(r),
    colorLiga: colores[T.liga(r)],
    filas: [
      [exp ? X.label : X.corto, (sgX * xs[r]).toFixed(X.dec)],
      [exp ? Y.label : Y.corto, (sgY * ys[r]).toFixed(Y.dec)],
      ...(diag ? [[difEt, signo(sgY * ys[r] - sgX * xs[r], decDif)]] : []),
    ],
  }), [T, esJugadores, colores, exp, X, Y, xs, ys, diag, difEt, decDif]);
  const ctx = useMemo(() => ({ info }), [info]);

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
  const selectorVariable = (rotulo, valor, onChange, enBarra = false) => (
    <Box>
      {!enBarra && <Rotulo>{rotulo}</Rotulo>}
      <TextField select size="small" fullWidth label={enBarra ? rotulo : undefined} value={valor} onChange={(e) => onChange(e.target.value)}
        slotProps={{ select: { MenuProps: { slotProps: { paper: { sx: { maxHeight: 420 } } } } } }}>
        {exp && [...new Set(exp.variables.map((v) => v.grupo))].flatMap((g) => [
          <ListSubheader key={`g-${g}`}>{g}</ListSubheader>,
          ...exp.variables.filter((v) => v.grupo === g).map((v) => (
            <MenuItem key={v.col} value={v.col} sx={{ fontSize: 13, whiteSpace: "normal" }}>{v.label}</MenuItem>)),
        ])}
      </TextField>
    </Box>
  );
  const hayNivel = filtros.nivel && nivelesDisp.length > 0;
  const haySub = filtros.sub21 && haySub21;
  const hayClub = clubesDisp.length > 0;
  const opcionesColor = ["liga", "neutro", ...cfg.colorPor.filter((c) => c !== "liga")];
  const nMas = (nivel !== "todos" ? 1 : 0) + (sub21 ? 1 : 0) + (club >= 0 ? 1 : 0) + (colorPor !== "liga" ? 1 : 0);
  const bloqueClub = (enBarra) => !hayClub ? null : (
    <Box>
      {!enBarra && <Rotulo>Club</Rotulo>}
      <Autocomplete size="small" options={clubesDisp} value={club >= 0 && clubesDisp.includes(club) ? club : null}
        onChange={(_e, v) => setClub(v == null ? -1 : v)}
        getOptionLabel={(i) => T.equipos[i]} isOptionEqualToValue={(a, b) => a === b}
        filterOptions={(opciones, { inputValue }) => {
          const q = sinAcentos(inputValue.trim());
          return opciones.filter((i) => sinAcentos(T.equipos[i]).includes(q));
        }}
        noOptionsText="Ningún club con ese nombre"
        renderInput={(p) => <TextField {...p} label={enBarra ? "Club" : undefined} placeholder={enBarra ? undefined : "Todos los clubes"} />} />
    </Box>
  );
  const bloqueNivel = !hayNivel ? null : (
    <Box>
      <Rotulo ayuda={ayudas.nivel}>Nivel del club</Rotulo>
      <ToggleButtonGroup exclusive size="small" fullWidth value={nivel} aria-label="Nivel del club"
        onChange={(_e, v) => v && setNivel(v)}>
        <ToggleButton value="todos">Todos</ToggleButton>
        {nivelesDisp.map((nv) => (
          <ToggleButton key={nv} value={nv} sx={{ px: 0.5, fontSize: "11.5px !important" }}>
            {nv.replace("Clubes ", "").replace(/^./, (c) => c.toUpperCase())}
          </ToggleButton>
        ))}
      </ToggleButtonGroup>
    </Box>
  );
  const bloqueSub21 = !haySub ? null : (
    <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
      <Rotulo ayuda={ayudas.sub21} sx={{ mb: 0 }}>Jugadores sub-21</Rotulo>
      <Switch size="small" checked={sub21} onChange={(e) => setSub21(e.target.checked)} slotProps={{ input: { "aria-label": "Jugadores sub-21" } }} />
    </Box>
  );
  const ctlColor = (
    <Box>
      <Rotulo>Color de los puntos</Rotulo>
      <ToggleButtonGroup exclusive size="small" fullWidth value={colorPor} aria-label="Color de los puntos"
        onChange={(_e, v) => v && setColorPor(v)}>
        {opcionesColor.map((o) => (
          <ToggleButton key={o} value={o} sx={{ px: 0.5, fontSize: "11.5px !important" }}>
            {{ neutro: "Un tono", liga: "Por liga", rendimiento: "Rendimiento" }[o]}
          </ToggleButton>
        ))}
      </ToggleButtonGroup>
    </Box>
  );
  const ctlTemporada = (
    <TextField select size="small" fullWidth label="Temporada" value={tEf} onChange={(e) => setTemporada(Number(e.target.value))}>
      {[...temporadasOk].reverse().map((i) => (
        <MenuItem key={i} value={i} dense>{T.temporadas[i]}</MenuItem>
      ))}
    </TextField>
  );
  const ligasTxt = ligasOn.size === T.ligas.length ? "Todas las ligas" : T.ligas.filter((_, li) => ligasOn.has(li)).join(", ");
  const ctlLiga = (
    <TextField select size="small" fullWidth label="Liga" value={[...ligasOn]}
      onChange={(e) => { const v = e.target.value; setLigasOn(new Set(v.length ? v : T.ligas.map((_, i) => i))); }}
      slotProps={{ select: { multiple: true, renderValue: () => ligasTxt }, inputLabel: { shrink: true } }}>
      {T.ligas.map((nombreLiga, li) => (
        <MenuItem key={nombreLiga} value={li} dense>
          <Checkbox size="small" checked={ligasOn.has(li)} sx={{ py: 0.25 }} />
          {colorPor === "liga" && <Box component="span" aria-hidden="true" sx={{ width: 10, height: 10, borderRadius: "50%", bgcolor: colores[nombreLiga], mr: 1, flex: "none" }} />}
          <ListItemText primary={nombreLiga} />
        </MenuItem>
      ))}
    </TextField>
  );
  // En el campo van las siglas (DEF, MED, DEL, POR); sin ninguna marcada se ven las tres de campo, sin porteros.
  const SIGLA = { Defensa: "DEF", Medio: "MED", Delantero: "DEL", Portero: "POR" };
  const marcadas = posiciones.length ? posiciones : posDisp.filter((p) => p !== "Portero");
  const posTxt = (marcadas.length ? marcadas : posDisp).map((p) => SIGLA[p] || p).join(", ");
  const ctlPosicion = !(filtros.posicion && posDisp.length > 0) ? null : (
    <TextField select size="small" fullWidth label="Posición" value={posiciones}
      onChange={(e) => setPosiciones(e.target.value)}
      slotProps={{ select: { multiple: true, displayEmpty: true, renderValue: () => posTxt }, inputLabel: { shrink: true } }}>
      {posDisp.map((p) => (
        <MenuItem key={p} value={p} dense>
          <Checkbox size="small" checked={posiciones.includes(p)} sx={{ py: 0.25 }} />
          <ListItemText primary={p} />
        </MenuItem>
      ))}
    </TextField>
  );
  // Resaltar: antes se llamaba "Buscar"; lo que hace es marcar puntos, no encontrar gráficas. En la barra lleva su etiqueta
  // dentro del campo y solo enseña un nombre (el resto, «+N»); en el panel del celular, como los demás: rótulo arriba.
  const resaltar = (enBarra) => (
    <Box>
      {!enBarra && <Rotulo>Resaltar {esJugadores ? "jugadores" : "clubes"}</Rotulo>}
      <Autocomplete multiple size="small" options={opcionesJug} limitTags={enBarra ? 1 : -1}
        filterOptions={(opciones, { inputValue }) => {
          const q = sinAcentos(inputValue.trim());
          return opciones.filter((j) => sinAcentos(T.nombres[j]).includes(q)).slice(0, 40);
        }}
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
        renderInput={(p) => <TextField {...p} label={enBarra ? `Resaltar ${esJugadores ? "jugadores" : "clubes"}` : undefined}
          placeholder={fijados.length ? "" : enBarra ? "Escribe un nombre…" : `Escribe un ${palabra}…`} />} />
    </Box>
  );
  const ctlTop = metricas.length > 1 ? (
    <Box>
      <Rotulo>Rotular los 5 con más</Rotulo>
      <ToggleButtonGroup exclusive size="small" fullWidth value={metrica} aria-label="Rotular los 5 con más"
        onChange={(_e, v) => v && setMetrica(v)}>
        {metricas.map((m) => (
          <ToggleButton key={m.id} value={m.id} title={m.ayuda} sx={{ px: 0.5, fontSize: "11.5px !important", lineHeight: 1.2 }}>{m.etiqueta}</ToggleButton>
        ))}
      </ToggleButtonGroup>
    </Box>
  ) : null;
  const masOpciones = <>{bloqueNivel}{bloqueSub21}{ctlTop}{ctlColor}</>;
  // Celular: todo en el panel de filtros.
  const controles = (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 2.25 }}>
      {exp && selectorVariable("Eje horizontal", colX, setColX)}
      {exp && selectorVariable("Eje vertical", colY, setColY)}
      {ctlLiga}
      {ctlPosicion}
      {resaltar(false)}
      {bloqueClub(false)}
      {masOpciones}
    </Box>
  );
  // Escritorio: UNA fila sobre la gráfica (temporada, liga, posición, resaltar) y lo demás detrás de «Más».
  const barra = (
    <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1.25, alignItems: "flex-start", mb: 2 }}>
      {exp && <Box sx={{ width: 230 }}>{selectorVariable("Eje horizontal", colX, setColX, true)}</Box>}
      {exp && <Box sx={{ width: 230 }}>{selectorVariable("Eje vertical", colY, setColY, true)}</Box>}
      <Box sx={{ width: 130 }}>{ctlTemporada}</Box>
      <Box sx={{ width: 180 }}>{ctlLiga}</Box>
      {ctlPosicion && <Box sx={{ width: 160 }}>{ctlPosicion}</Box>}
      {hayClub && <Box sx={{ width: 180 }}>{bloqueClub(true)}</Box>}
      <Box sx={{ width: 230 }}>{resaltar(true)}</Box>
      <Button variant="outlined" startIcon={<FilterList />} onClick={(e) => setAnclaMas(e.currentTarget)}
        aria-haspopup="dialog" aria-expanded={!!anclaMas}
        sx={{ textTransform: "none", fontWeight: 600, height: 40, borderColor: "divider", color: "text.primary" }}>Más</Button>
      <Popover open={!!anclaMas} anchorEl={anclaMas} onClose={() => setAnclaMas(null)}
        anchorOrigin={{ vertical: "bottom", horizontal: "right" }} transformOrigin={{ vertical: "top", horizontal: "right" }}>
        <Box sx={{ p: 2, width: 300, display: "flex", flexDirection: "column", gap: 2.25 }}>{masOpciones}</Box>
      </Popover>
    </Box>
  );

  const ranking5 = (
    <Ranking metricas={metricas} metrica={metrica} onMetrica={setMetrica} filas={ranking} nombre={nombre}
      equipo={(r) => (esJugadores ? T.equipo(r) : "")} valor={textoValor} fijadas={pines} enZoom={hayZoom}
      onElegir={alternarFila} onSobrevolar={setHoverFila} />
  );

  // Cuántos filtros "de verdad" hay puestos (temporada y color no cuentan: son vistas, no recortes).
  const nFiltros = (ligasOn.size < T.ligas.length ? 1 : 0) + (posiciones.length && !(posiciones.length === posIni.length && posiciones.every((p) => posIni.includes(p))) ? 1 : 0)
    + (nivel !== "todos" ? 1 : 0) + (sub21 ? 1 : 0) + (club >= 0 ? 1 : 0);

  const minimo = (cfg.minimoPor90 && T.minimos90 ? T.minimos90 : T.minimos || {})[tLabel] ?? null;
  // la temporada que va en curso se marca: con pocas jornadas los extremos son casi todo muestra
  const jornadas = T.enCurso ? T.enCurso[tLabel] : null;
  const tTexto = jornadas ? `${tLabel} (en curso, ${jornadas} jornadas)` : tLabel;
  const subtitulo = exp
    ? `${Y.label} vs. ${X.label} · ${tTexto}`
    : cfg.subtitulo.replace("{min}", minimo != null ? String(minimo) : "").replace("{temporada}", tTexto);
  // La imagen: la gráfica tal como está en pantalla (zoom, jugadores resaltados, colores y filtros) con una sola línea de contexto.
  const lienzoRef = useRef(null);
  const filtrosTxt = [
    jornadas ? `${tLabel} (en curso)` : tLabel,
    posiciones.length && !(posiciones.length === posIni.length && posiciones.every((p) => posIni.includes(p))) ? posiciones.join(", ") : null,
    ligasOn.size < T.ligas.length ? T.ligas.filter((_, li) => ligasOn.has(li)).join(", ") : null,
    nivel !== "todos" ? nivel : null, sub21 ? "sub-21" : null, club >= 0 ? (T.equipos || [])[club] : null,
  ].filter(Boolean).join(" · ");
  const descargar = () => descargarPng({
    ...capturar(lienzoRef.current, { limpiar: limpiarDispersion(tk, { apagado: colorPor !== "rendimiento", oscuro: modo === "dark" }) }),
    titulo: exp ? `${Y.label} vs. ${X.label}` : cfg.titulo, subtitulo: filtrosTxt,
    leyenda: colorPor === "liga" ? T.ligas.filter((_, li) => ligasOn.has(li)).map((l) => ({ color: colores[l], texto: l })) : null,
    fuente: `Datos: ${cfg.fuente}`, tk, modo, archivo: nombreArchivo(exp ? `${Y.label} vs ${X.label}` : cfg.id, tLabel),
  });
  const vacio = visibles.length === 0 ? `Ningún ${esJugadores ? "jugador" : "equipo"} con estos filtros.` : null;

  return (
    <FilaCtx.Provider value={ctx}>
      <Encabezado pregunta={cfg.pregunta} titulo={cfg.titulo} bajada={cfg.bajada} muestra={subtitulo} />

      {/* En celular la temporada se queda a la vista; el resto de filtros van en el panel. En escritorio, una sola barra. */}
      {movil ? (
        <Box sx={{ display: "flex", gap: 1, alignItems: "center", mb: 1.5 }}>
          <TextField select size="small" label="Temporada" value={tEf}
            onChange={(e) => setTemporada(Number(e.target.value))}
            slotProps={{ select: { native: true }, htmlInput: { "aria-label": "Temporada" } }} sx={{ minWidth: 112 }}>
            {[...temporadasOk].reverse().map((i) => <option key={i} value={i}>{T.temporadas[i]}</option>)}
          </TextField>
          <Button variant="outlined" size="small" startIcon={<FilterList />} onClick={() => setFiltrosAbiertos(true)}
            sx={{ textTransform: "none", fontWeight: 600, minHeight: 40 }}>{exp ? "Ejes y filtros" : "Filtros"}</Button>
        </Box>
      ) : barra}

      <Box sx={{ display: "grid", gap: 3, gridTemplateColumns: "minmax(0,1fr)", alignItems: "start" }}>

        {/* ---------------- columna del gráfico ---------------- */}
        <Box sx={{ minWidth: 0 }}>

          <Box ref={lienzoRef}>
          <Grafica series={series} view={view} viewRef={viewRef} base={base} onView={onView}
            rotulos={rotulos} destacado={destacado}
            onDestacar={onDestacar} onClicPunto={onClicPunto} tk={tk}
            hayZoom={hayZoom} pista={pista} onPista={onPista} tenue={colorPor === "rendimiento" ? 0 : modo === "dark" ? 0.55 : 0.4}
            // En móvil, el título corto del eje ("Precisión") en vez de la frase entera, que no cabe.
            ejeX={movil && !exp ? X.corto : X.label} ejeY={movil && !exp ? Y.corto : Y.label}
            claveDatos={claveDatos} pines={pines} idsPorSerie={idsPorSerie}
            referencia={ref} medias={medias} corte={corteElite} lineas={lineas} onZona={alZona} vacio={vacio}
            soloPositivoX={sgX === -1 || rx.lo >= 0} soloPositivoY={sgY === -1 || ry.lo >= 0} invertirX={sgX === -1} invertirY={sgY === -1} />
          </Box>

          {colorPor === "liga" && (
            <Box role="group" aria-label="Colores de las ligas" sx={{ display: "flex", flexWrap: "wrap", gap: "2px 14px", mt: 0.75, fontSize: 12, color: "text.secondary" }}>
              {T.ligas.map((l, li) => ligasOn.has(li) && (
                <Box key={l} sx={{ display: "inline-flex", alignItems: "center", gap: 0.6 }}>
                  <Box component="span" aria-hidden="true" sx={{ width: 10, height: 10, borderRadius: "50%", bgcolor: colores[l] }} />{l}
                </Box>
              ))}
            </Box>
          )}
          <Box sx={{ display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 1, mt: 0.75 }}>
            {enZona ? (
              <Chip size="small" label={`Zona: ${nombreZona}`} title="Volver a la vista de arranque" onClick={() => mover(ajuste)} onDelete={() => mover(ajuste)}
                sx={{ maxWidth: { xs: 240, sm: 380 }, bgcolor: conAlfa(tk.muted, 0.14) }} />
            ) : (
              <Typography sx={{ fontSize: 12, color: "text.secondary" }}>
                {cfg.nota ? `${cfg.nota} · ` : ""}
                {ref && ref.banda ? "Franja gris: hasta donde llega el azar · " : ""}
                {movil
                  ? `Arrastra para mover · toca un punto${lineas ? " o un cuadrante" : ""}`
                  : `Arrastra para mover · Ctrl + rueda para zoom · clic en un punto${lineas ? " o un cuadrante" : ""}`}
              </Typography>
            )}
            <Box role="toolbar" aria-label="Zoom y descarga" sx={{ display: "flex", alignItems: "center", gap: 0.25, minWidth: 0,
              "& .MuiIconButton-root": { "@media (pointer: coarse)": { p: "12px" } } }}>
              <Tooltip title="Acercar"><span><IconButton size="small" aria-label="Acercar"
                onClick={() => mover(acercar(viewRef.current, base, 0.6))}><ZoomIn fontSize="small" /></IconButton></span></Tooltip>
              <Tooltip title="Alejar"><span><IconButton size="small" aria-label="Alejar" disabled={!fueraDeBase}
                onClick={() => mover(acercar(viewRef.current, base, 1 / 0.6))}><ZoomOut fontSize="small" /></IconButton></span></Tooltip>
              <Tooltip title="Volver a la vista de arranque"><span><IconButton size="small" aria-label="Volver a la vista de arranque" disabled={esBase(view, ajuste)}
                onClick={() => mover(ajuste)}><CenterFocusStrong fontSize="small" /></IconButton></span></Tooltip>
              <Typography sx={{ fontSize: 12, color: "text.secondary", ml: 1 }}>Datos: {cfg.fuente}</Typography>
              <BotonDescarga alDescargar={descargar} />
            </Box>
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

      </Box>

      {/* ---------------- caja de lectura ---------------- */}
      <Box sx={{ mt: 3, maxWidth: 1040 }}>
        {(cfg.queMirar || exp) && (
          <>
            <Rotulo>Cómo leer la gráfica</Rotulo>
            <ComoLeer texto={exp ? EXPLICA_LIENZO : cfg.queMirar} />
          </>
        )}
        {lectura && <QueDice texto={exp ? lectura.fija : (lectura.salta || lectura.fija)} />}
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
