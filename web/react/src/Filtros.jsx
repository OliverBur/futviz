// Los filtros de las vistas, en UNA fila sobre la gráfica y con las mismas piezas en todas: un menú para la temporada (la más
// reciente arriba), un menú para la liga (con casillas cuando se pueden juntar varias, sin conteos), botones segmentados para
// lo que solo tiene dos o tres opciones. Cada campo lleva su etiqueta dentro, así que la fila se ve pareja.
import Box from "@mui/material/Box";
import Checkbox from "@mui/material/Checkbox";
import ListItemText from "@mui/material/ListItemText";
import MenuItem from "@mui/material/MenuItem";
import TextField from "@mui/material/TextField";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import Typography from "@mui/material/Typography";

// La fila que junta los filtros. Los campos se acomodan solos; en pantallas angostas pasan a la línea de abajo.
export const BarraFiltros = ({ children, sx }) => (
  <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1.25, alignItems: "flex-start", mb: 2, ...sx }}>{children}</Box>
);

// Envuelve un campo con un ancho fijo para que la fila no se estire.
export const Campo = ({ ancho = 170, children }) => <Box sx={{ width: ancho, maxWidth: "100%" }}>{children}</Box>;

// Un menú de una sola opción. `opciones`: [{ valor, texto }].
export function SelectUno({ etiqueta, valor, opciones, onChange, nativo = false }) {
  return (
    <TextField select size="small" fullWidth label={etiqueta} value={valor}
      onChange={(e) => onChange(e.target.value)}
      slotProps={nativo ? { select: { native: true }, htmlInput: { "aria-label": etiqueta } } : undefined}>
      {opciones.map((o) => (nativo
        ? <option key={o.valor} value={o.valor}>{o.texto}</option>
        : <MenuItem key={o.valor} value={o.valor} dense>{o.texto}</MenuItem>))}
    </TextField>
  );
}

// Las temporadas con la más reciente primero. `temporadas`: etiquetas como «2026-27» (el orden de texto es el cronológico).
export const masRecientePrimero = (temporadas) => [...temporadas].sort((a, b) => (a < b ? 1 : a > b ? -1 : 0));

export function SelectTemporada({ valor, temporadas, onChange, nativo }) {
  return (
    <SelectUno etiqueta="Temporada" valor={valor} nativo={nativo} onChange={onChange}
      opciones={masRecientePrimero(temporadas).map((t) => ({ valor: t, texto: t }))} />
  );
}

// Varias a la vez, con casillas; si no queda ninguna marcada se ven todas. `colores`: { liga: color } pinta un punto en cada una.
export function SelectLigas({ ligas, activas, onChange, colores }) {
  const todas = activas.size === ligas.length;
  const texto = todas ? "Todas las ligas" : ligas.filter((_, i) => activas.has(i)).join(", ");
  return (
    <TextField select size="small" fullWidth label="Liga" value={[...activas]}
      onChange={(e) => { const v = e.target.value; onChange(new Set(v.length ? v : ligas.map((_, i) => i))); }}
      slotProps={{ select: { multiple: true, renderValue: () => texto }, inputLabel: { shrink: true } }}>
      {ligas.map((nombre, i) => (
        <MenuItem key={nombre} value={i} dense>
          <Checkbox size="small" checked={activas.has(i)} sx={{ py: 0.25 }} />
          {colores && <Box component="span" aria-hidden="true" sx={{ width: 10, height: 10, borderRadius: "50%", bgcolor: colores[nombre], mr: 1, flex: "none" }} />}
          <ListItemText primary={nombre} />
        </MenuItem>
      ))}
    </TextField>
  );
}

// Dos o tres opciones: botones pegados dentro de un recuadro, con la etiqueta en la muesca como los demás campos de la fila.
export function Segmentado({ etiqueta, valor, opciones, onChange, ancho, ayuda }) {
  return (
    <Box title={ayuda} sx={{ width: ancho, maxWidth: "100%", height: 40, position: "relative", border: 1, borderColor: "divider",
      borderRadius: "8px", px: "5px", display: "flex", alignItems: "center", boxSizing: "border-box" }}>
      <Typography component="span" sx={{ position: "absolute", top: -7, left: 9, px: 0.5, fontSize: 11, lineHeight: "14px", color: "text.secondary",
        bgcolor: "background.paper", pointerEvents: "none" }}>{etiqueta}</Typography>
      <ToggleButtonGroup exclusive size="small" fullWidth value={valor} aria-label={etiqueta} onChange={(_e, v) => v != null && onChange(v)}
        sx={{ height: 28, "& .MuiToggleButtonGroup-grouped": { border: 0, borderRadius: "6px !important", mx: "1px" } }}>
        {opciones.map((o) => (
          <ToggleButton key={o.valor} value={o.valor} sx={{ px: 1, py: 0, fontSize: "12.5px !important", textTransform: "none", lineHeight: 1.15 }}>{o.texto}</ToggleButton>
        ))}
      </ToggleButtonGroup>
    </Box>
  );
}
