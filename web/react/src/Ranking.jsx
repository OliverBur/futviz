// Top 5 de la columna derecha. Es la ÚNICA fuente de lo que la gráfica rotula: los nombres
// que se pintan sobre los puntos son estas cinco filas, con el mismo número (ver Grafica.jsx).
//
// Cada fila es un botón: un clic fija a ese jugador en la gráfica (y la centra en él si el
// zoom lo dejó fuera); pasar el mouse por encima lo resalta en el gráfico, sin fijarlo.
// Las métricas por las que se puede ordenar vienen de la configuración de la vista (`metricas`).
import Box from "@mui/material/Box";
import List from "@mui/material/List";
import ListItemButton from "@mui/material/ListItemButton";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import Typography from "@mui/material/Typography";

export function Ranking({ metricas, metrica, onMetrica, filas, nombre, equipo, valor, fijadas, onElegir,
  onSobrevolar, enZoom }) {
  const actual = metricas.find((m) => m.id === metrica) || metricas[0];
  return (
    <Box>
      <Typography sx={{ fontSize: 10.5, fontWeight: 700, letterSpacing: ".07em", textTransform: "uppercase",
        color: "text.secondary", mb: 0.75 }}>Top 5</Typography>
      <ToggleButtonGroup exclusive size="small" fullWidth value={actual.id} aria-label="Ordenar el Top 5 por"
        onChange={(_e, v) => v && onMetrica(v)}>
        {metricas.map((m) => (
          <ToggleButton key={m.id} value={m.id} sx={{ px: 0.5, fontSize: "11.5px !important" }}>{m.etiqueta}</ToggleButton>
        ))}
      </ToggleButtonGroup>
      <Typography sx={{ fontSize: 11.5, color: "text.secondary", mt: 0.5, mb: 0.5 }}>
        {actual.ayuda}{enZoom ? " · dentro del zoom" : ""}
      </Typography>

      <List dense disablePadding aria-label="Top 5">
        {filas.map((r, i) => {
          const sel = fijadas.has(r);
          const sub = equipo(r);
          return (
            <ListItemButton key={r} selected={sel} aria-pressed={sel}
              onClick={() => onElegir(r)}
              onMouseEnter={() => onSobrevolar(r)} onMouseLeave={() => onSobrevolar(null)}
              onFocus={() => onSobrevolar(r)} onBlur={() => onSobrevolar(null)}
              sx={{ px: 0.75, py: 0.5, gap: 1, borderRadius: 1, borderBottom: 1, borderColor: "divider",
                "&.Mui-selected": { bgcolor: "action.selected" } }}>
              <Box sx={{ width: 14, flex: "none", fontSize: 13, fontWeight: 700, color: "text.secondary" }}>{i + 1}</Box>
              <Box sx={{ flex: 1, minWidth: 0 }}>
                <Box sx={{ fontSize: 13, fontWeight: sel ? 700 : 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {nombre(r)}
                </Box>
                {sub && (
                  <Box sx={{ fontSize: 11.5, color: "text.secondary", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {sub}
                  </Box>
                )}
              </Box>
              <Box sx={{ fontSize: 13, fontWeight: 700, flex: "none" }}>{valor(r)}</Box>
            </ListItemButton>
          );
        })}
        {!filas.length && (
          <Typography sx={{ fontSize: 12.5, color: "text.secondary", py: 1 }}>Nadie en esta vista.</Typography>
        )}
      </List>
    </Box>
  );
}
