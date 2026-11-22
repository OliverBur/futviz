// Filtro de posición: un ToggleButtonGroup con el estilo de los demás botones del sitio. Las posiciones no llevan color
// propio: los matices que tenían (azul, naranja y rojo) eran casi los de Serie A, La Liga y Bundesliga, y en las gráficas
// el color significa liga.
import Box from "@mui/material/Box";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import Typography from "@mui/material/Typography";

export const Cuadrito = ({ color, tam = 8 }) => (
  <Box component="span" aria-hidden="true"
    sx={{ width: tam, height: tam, borderRadius: "2px", bgcolor: color, flex: "none", display: "inline-block" }} />
);

export function Posiciones({ opciones, valor, onChange, etiqueta = "Posición" }) {
  const hayPortero = opciones.includes("Portero");
  return (
    <>
      <ToggleButtonGroup size="small" fullWidth value={valor} aria-label={etiqueta}
        onChange={(_e, v) => onChange(v)}>
        {opciones.map((p) => {
          return (
            <ToggleButton key={p} value={p} sx={{ px: 0.5, fontSize: "11.5px !important" }}>
              {p}
            </ToggleButton>
          );
        })}
      </ToggleButtonGroup>
      {/* Sin ninguna marcada se ven todas (menos los porteros, si hay); decirlo evita leer "nada seleccionado" como "nada". */}
      {!valor.length && (
        <Typography sx={{ fontSize: 11.5, color: "text.secondary", mt: 0.5 }}>
          {hayPortero ? "Todas, sin porteros. Marca Portero para incluirlos." : "Todas las posiciones"}
        </Typography>
      )}
    </>
  );
}
