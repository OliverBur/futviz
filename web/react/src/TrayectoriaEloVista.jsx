// Trayectoria del club en ELO: el ELO de hasta 6 clubes a la vez, temporada a temporada, contra el promedio de ELO de las
// 5 ligas. Cada club conserva su color mientras está elegido; si un club no jugó en las 5 ligas alguna temporada (ascenso o
// descenso), su línea se corta en un hueco en vez de unir los puntos.
//
// Todo el cálculo está hecho en el build (`web/charts/trayectoria_elo.py`): aquí solo se dibuja lo que viaja en
// `datos-trayectoria-elo.js`. El dibujo de las líneas es `LineasSvg.jsx` (el de «Forma»); el texto «Con estos filtros» es
// `trayectoriaEloLectura.js`. Los filtros van a la derecha (arriba de la gráfica en pantalla angosta).
import { useEffect, useMemo, useState } from "react";
import { ThemeProvider } from "@mui/material/styles";
import Autocomplete from "@mui/material/Autocomplete";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import MenuItem from "@mui/material/MenuItem";
import TextField from "@mui/material/TextField";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import Typography from "@mui/material/Typography";
import Cancel from "@mui/icons-material/Cancel";
import { entre, leerParams, usePublicarParams } from "./urlEstado.js";
import { useSitioTema } from "./theme.jsx";
import { cargarDatos } from "./datos.js";
import { Aviso, Cargando, Encabezado, Md, Parrafos, Rotulo, sinAcentos } from "./ui.jsx";
import LineasSvg, { MuestraLinea } from "./LineasSvg.jsx";
import { elo, lecturaElo, sg, valoresClub } from "./trayectoriaEloLectura.js";

const REF = "__ref";
const TODAS = "todas";

const Muestra = ({ color }) => (
  <Box component="span" sx={{ width: 10, height: 10, borderRadius: "50%", bgcolor: color, flex: "none", display: "inline-block" }} />
);

function Vista({ cfg, D, modo, tk }) {
  const [P] = useState(() => leerParams(cfg.id));
  const T = D.temporadas, u = T.length - 1;
  const MAX = D.maxClubes;
  const ids = cfg.medidas.map((m) => m.id);
  const porNombre = useMemo(() => new Map(D.clubes.map((c) => [c.n, c])), [D]);

  const [medida, setMedida] = useState(() => entre(P.get("m"), ids, D.medida));
  const [liga, setLiga] = useState(() => entre(P.get("l"), D.ligas, TODAS));
  const [texto, setTexto] = useState("");
  // Los clubes elegidos, cada uno con su casilla de color (0..MAX-1): al quitar uno, los demás no cambian de color.
  const [sel, setSel] = useState(() => {
    const url = P.getAll("c");
    const validos = [...new Set(url)].filter((n) => porNombre.has(n)).slice(0, MAX);
    const nombres = url.includes("ninguno") ? [] : validos.length ? validos : D.iniciales;
    return nombres.map((n, i) => ({ n, s: i }));
  });
  const nombres = sel.map((x) => x.n);
  const esInicial = nombres.length === D.iniciales.length && nombres.every((n, i) => n === D.iniciales[i]);
  usePublicarParams(cfg.id, {
    m: medida === D.medida ? null : medida,
    l: liga === TODAS ? null : liga,
    c: esInicial ? null : nombres.length ? nombres : ["ninguno"],
  });

  const anadir = (n) => setSel((prev) => (prev.length >= MAX || prev.some((x) => x.n === n) ? prev
    : [...prev, { n, s: Array.from({ length: MAX }, (_, s) => s).find((s) => !prev.some((x) => x.s === s)) }]));
  const quitar = (n) => setSel((prev) => prev.filter((x) => x.n !== n));
  const lleno = sel.length >= MAX;

  const col = cfg.colores[modo === "dark" ? "oscuro" : "claro"];
  const etiqueta = cfg.medidas.find((m) => m.id === medida).etiqueta;
  const ayuda = cfg.medidas.find((m) => m.id === medida).ayuda;

  // --- lo que se dibuja ---------------------------------------------------------------------------
  const refVals = useMemo(() => D.ref[medida].map((v) => (v == null ? null : Math.round(v))), [D, medida]);
  const series = useMemo(() => [
    { id: REF, color: tk.muted, ancho: 1.8, opacidad: 0.9, punteada: true, puntos: refVals.map((y, x) => ({ x, y })) },
    ...sel.map(({ n, s }) => ({
      id: n, color: col[s], ancho: 2.6, radio: 3.4,
      puntos: valoresClub(porNombre.get(n), medida).map((y, x) => ({ x, y })),
    })),
  ], [sel, medida, modo, refVals, porNombre]);   // eslint-disable-line react-hooks/exhaustive-deps

  const lectura = useMemo(() => lecturaElo(D, nombres, medida, etiqueta), [D, sel, medida]);   // eslint-disable-line react-hooks/exhaustive-deps

  const aria = `Líneas del ELO ${etiqueta.toLowerCase()} de ${sel.length} ${sel.length === 1 ? "club" : "clubes"} de ${T[0]} a ${T[u]}, `
    + `junto al promedio de las 5 ligas (${refVals.map((v, i) => `${T[i]} ${elo(v)}`).join(", ")}). `
    + sel.map(({ n }) => `${n}: ${valoresClub(porNombre.get(n), medida).map((v, i) => (v == null ? `${T[i]} no jugó en las 5 ligas` : `${T[i]} ${elo(v)}`)).join(", ")}.`).join(" ");

  const tooltip = (x, puntos) => {
    const filas = puntos.filter((p) => p.serie.id !== REF).sort((a, b) => (b.y ?? -1) - (a.y ?? -1));
    const previa = x > 0 ? T[x - 1] : null;
    return (
      <>
        <Box sx={{ fontWeight: 700 }}>{T[x]}</Box>
        <Box sx={{ color: "text.secondary", fontSize: 11.5, mb: 0.75 }}>ELO {etiqueta.toLowerCase()}</Box>
        {filas.map((p) => {
          const antes = previa == null ? null : valoresClub(porNombre.get(p.serie.id), medida)[x - 1];
          return (
            <Box key={p.serie.id} sx={{ "& + &": { mt: 0.75 } }}>
              <Box sx={{ display: "flex", alignItems: "center", gap: 0.75 }}>
                <Muestra color={p.serie.color} />
                <Box component="span" sx={{ flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                  fontWeight: 600, color: p.y == null ? "text.secondary" : "text.primary" }}>{p.serie.id}</Box>
                {p.y == null
                  ? <Box component="span" sx={{ color: "text.secondary", fontSize: 11.5 }}>no jugó en las 5 ligas</Box>
                  : <strong>{elo(p.y)}</strong>}
              </Box>
              {p.y != null && previa != null && (
                <Box sx={{ color: "text.secondary", fontSize: 11.5, pl: 2.25 }}>
                  {antes == null ? `Sin dato en ${previa}: no jugó en las 5 ligas`
                    : `${p.y > antes ? "▲" : p.y < antes ? "▼" : "="} ${sg(p.y - antes)} contra ${previa}`}
                </Box>
              )}
            </Box>
          );
        })}
        <Box sx={{ mt: 1, pt: 0.75, borderTop: 1, borderColor: "divider", color: "text.secondary", display: "flex", alignItems: "center", gap: 0.75 }}>
          <MuestraLinea color={tk.muted} punteada ancho={1.8} />
          <span>Promedio de las 5 ligas: <strong style={{ color: "inherit" }}>{elo(refVals[x])}</strong> ({D.n[x]} clubes)</span>
        </Box>
      </>
    );
  };

  // --- controles ----------------------------------------------------------------------------------
  const delLiga = D.clubes.filter((c) => liga === TODAS || D.ligas[c.l] === liga);
  const opciones = delLiga.filter((c) => !nombres.includes(c.n)).sort((a, b) => a.n.localeCompare(b.n, "es"));
  const sugeridos = delLiga.filter((c) => !nombres.includes(c.n) && c[medida][u] != null)
    .sort((a, b) => b[medida][u] - a[medida][u] || a.n.localeCompare(b.n, "es")).slice(0, 5);
  const nTemporadas = (c) => c.med.filter((v) => v != null).length;

  const controles = (
    <Box sx={{ gridArea: "ctl", display: "flex", flexDirection: "column", gap: 2.25, minWidth: 0 }}>
      <Box>
        <Rotulo>{`Clubes (hasta ${MAX})`}</Rotulo>
        <Autocomplete size="small" options={opciones} value={null} inputValue={texto} disabled={lleno}
          onInputChange={(_e, v) => setTexto(v)}
          onChange={(_e, o) => { if (o) anadir(o.n); setTexto(""); }}
          getOptionLabel={(o) => o.n} isOptionEqualToValue={(a, b) => a.n === b.n}
          filterOptions={(ops, { inputValue }) => {
            const q = sinAcentos(inputValue.trim());
            return (q ? ops.filter((o) => sinAcentos(o.n).includes(q)) : ops).slice(0, 80);
          }}
          renderOption={(props, o) => {
            const { key, ...resto } = props;
            return (
              <li key={key} {...resto}>
                <Box sx={{ minWidth: 0 }}>
                  <Box sx={{ fontSize: 13.5 }}>{o.n}</Box>
                  <Box sx={{ fontSize: 11.5, color: "text.secondary" }}>{D.ligas[o.l]} · {nTemporadas(o)} de {T.length} temporadas</Box>
                </Box>
              </li>
            );
          }}
          noOptionsText={liga === TODAS ? "Ningún club con ese nombre" : `Ningún club de ${liga} con ese nombre`}
          renderInput={(p) => <TextField {...p} placeholder={lleno ? `Ya hay ${MAX} clubes` : "Busca un club…"} />} />
        <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.75, mt: 1, minHeight: 28 }} aria-label="Clubes elegidos">
          {sel.map(({ n, s }) => (
            <Chip key={n} size="small" variant="outlined" label={n}
              icon={<Box component="span" sx={{ width: 10, height: 10, borderRadius: "50%", bgcolor: col[s], ml: "8px !important", flex: "none" }} />}
              deleteIcon={<Cancel aria-label={`Quitar ${n}`} />} onDelete={() => quitar(n)} />
          ))}
        </Box>
        <Box sx={{ display: "flex", gap: 1, mt: 0.5, alignItems: "center" }}>
          <Button size="small" onClick={() => setSel([])} disabled={!sel.length} sx={{ textTransform: "none", fontWeight: 600, minWidth: 0, px: 1 }}>
            Limpiar
          </Button>
          {!esInicial && (
            <Button size="small" onClick={() => setSel(D.iniciales.map((n, i) => ({ n, s: i })))}
              sx={{ textTransform: "none", fontWeight: 600, minWidth: 0, px: 1 }}>
              Selección inicial
            </Button>
          )}
        </Box>
      </Box>

      <Box>
        <Rotulo>ELO que se dibuja</Rotulo>
        <ToggleButtonGroup exclusive size="small" fullWidth value={medida} aria-label="Qué ELO se dibuja"
          onChange={(_e, v) => v && setMedida(v)}>
          {cfg.medidas.map((m) => <ToggleButton key={m.id} value={m.id} sx={{ px: 0.5 }}>{m.etiqueta}</ToggleButton>)}
        </ToggleButtonGroup>
        <Typography sx={{ fontSize: 11.5, color: "text.secondary", mt: 0.5 }}>{ayuda}</Typography>
      </Box>

      <Box>
        <Rotulo>Liga</Rotulo>
        <TextField select size="small" fullWidth value={liga} onChange={(e) => setLiga(e.target.value)}
          inputProps={{ "aria-label": "Liga para sugerir clubes" }}>
          <MenuItem value={TODAS} sx={{ fontSize: 13 }}>Las 5 ligas</MenuItem>
          {D.ligas.map((l) => <MenuItem key={l} value={l} sx={{ fontSize: 13 }}>{l}</MenuItem>)}
        </TextField>
        <Typography sx={{ fontSize: 11.5, color: "text.secondary", mt: 0.5 }}>
          Muestra los clubes que jugaron en esa liga su última temporada con ELO: uno que subió o bajó sale en la liga donde jugó al final.
        </Typography>
        {sugeridos.length > 0 && (
          <Box sx={{ mt: 0.75 }}>
            <Typography sx={{ fontSize: 11.5, color: "text.secondary", mb: 0.5 }}>
              Los más fuertes en {T[u]} ({etiqueta.toLowerCase()}){liga === TODAS ? "" : `, ${liga}`}
            </Typography>
            <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.5 }}>
              {sugeridos.map((c) => (
                <Chip key={c.n} size="small" variant="outlined" label={c.n} disabled={lleno} onClick={() => anadir(c.n)} />
              ))}
            </Box>
          </Box>
        )}
      </Box>
    </Box>
  );

  return (
    <>
      <Box sx={{
        display: "grid", columnGap: 3, rowGap: 0, alignItems: "start",
        gridTemplateColumns: { xs: "minmax(0,1fr)", md: "minmax(0,1fr) 270px" },
        gridTemplateRows: { xs: "auto", md: "auto 1fr" },
        gridTemplateAreas: { xs: '"enc" "ctl" "graf"', md: '"enc ctl" "graf ctl"' },
      }}>
        <Box sx={{ gridArea: "enc", minWidth: 0 }}>
          <Encabezado pregunta={cfg.pregunta} titulo={cfg.titulo} bajada={cfg.bajada} />
        </Box>
        {controles}
        <Box sx={{ gridArea: "graf", minWidth: 0, maxWidth: 1000, mt: { xs: 2, md: 0 } }}>
          <Typography component="h3" sx={{ fontSize: 13.5, fontWeight: 700, mb: 0.25 }}>
            ELO {etiqueta.toLowerCase()}
            <Box component="span" sx={{ fontWeight: 500, color: "text.secondary" }}> · {T[0]} a {T[u]} · {sel.length} {sel.length === 1 ? "club" : "clubes"}</Box>
          </Typography>
          <Box sx={{ display: "flex", flexWrap: "wrap", columnGap: 2, rowGap: 0.5, fontSize: 12, color: "text.secondary", mb: 0.5 }}>
            {sel.map(({ n, s }) => (
              <Box key={n} component="span" sx={{ display: { xs: "none", md: "inline-flex" }, alignItems: "center", gap: 0.75 }}>
                <MuestraLinea color={col[s]} ancho={2.6} /><span>{n}</span>
              </Box>
            ))}
            <Box component="span" sx={{ display: "inline-flex", alignItems: "center", gap: 0.75 }}>
              <MuestraLinea color={tk.muted} punteada ancho={1.8} /><span>Promedio de las 5 ligas</span>
            </Box>
          </Box>
          {!sel.length && (
            <Typography sx={{ fontSize: 12.5, color: "text.secondary", mb: 0.5 }}>
              No hay clubes elegidos: busca uno o toca una sugerencia. Mientras tanto se ve solo el promedio de las 5 ligas.
            </Typography>
          )}
          <LineasSvg
            tk={tk} ariaLabel={aria} series={series} alto={300}
            x={{ categorias: T }}
            y={{ formato: elo }}
            tooltip={tooltip} />
          <Typography sx={{ fontSize: 11.5, color: "text.secondary", mt: 0.5 }}>
            Eje: temporada. La línea se corta donde el club no jugó en las 5 ligas (ascensos y descensos).
            {D.sinElo.length > 0 && ` ${D.sinElo.join(" y ")} no tiene ELO todavía: la vista llega hasta ${T[u]}.`}
            {" "}Pasa el cursor o toca una temporada para ver el ELO de cada club y su cambio.
          </Typography>
          <Box sx={{ mt: 1, display: "flex", justifyContent: "flex-end" }}>
            <Typography sx={{ fontSize: 12, color: "text.secondary" }}>Datos: {cfg.fuente}</Typography>
          </Box>
        </Box>
      </Box>

      <Box sx={{ mt: 3, maxWidth: 1040 }}>
        <Rotulo>Qué más mirar</Rotulo>
        <Parrafos texto={cfg.queMirar} sx={{ color: "text.primary" }} />
        <Box sx={{ mt: 2, pl: 2, borderLeft: 3, borderColor: "success.main" }}>
          <Typography sx={{ fontSize: 10.5, fontWeight: 700, letterSpacing: ".07em", textTransform: "uppercase", color: "success.main", mb: 0.75 }}>
            Con estos filtros · ELO {etiqueta.toLowerCase()} · {sel.length} {sel.length === 1 ? "club" : "clubes"}
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

export default function TrayectoriaEloVista({ id }) {
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
