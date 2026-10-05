// Filtro de posición: los mismos colores que tenía la mini cancha (`viz_theme.PITCH_ZONAS`,
// llegan en `coloresPos`), ahora sobre un ToggleButtonGroup.
//
// El color SOLO se ve al elegir la posición (decisión del usuario: sin cuadritos en reposo).
// Cuidado de data viz: tres de esos matices se parecen a colores de liga (el rojo de Delantero
// al de la Bundesliga, el azul de Defensa al de la Serie A, el naranja de Medio al de La Liga) y
// en las gráficas el color de los puntos significa LIGA, así que el color de posición vive solo
// en este control (seleccionado) y en la tabla, nunca sobre los puntos. El texto no cambia de
// color: el seleccionado se tiñe de fondo y lleva una barra, así el contraste no depende del matiz.
import Box from "@mui/material/Box";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import Typography from "@mui/material/Typography";
import { conAlfa } from "./colores.js";

export const Cuadrito = ({ color, tam = 8 }) => (
  <Box component="span" aria-hidden="true"
    sx={{ width: tam, height: tam, borderRadius: "2px", bgcolor: color, flex: "none", display: "inline-block" }} />
);

export function Posiciones({ opciones, colores, valor, onChange, modo, etiqueta = "Posición" }) {
  return (
    <>
      <ToggleButtonGroup size="small" fullWidth value={valor} aria-label={etiqueta}
        onChange={(_e, v) => onChange(v)}>
        {opciones.map((p) => {
          const c = colores[p];
          return (
            <ToggleButton key={p} value={p}
              sx={{
                px: 0.5, fontSize: "11.5px !important",
                "&.Mui-selected": {
                  bgcolor: conAlfa(c, modo === "dark" ? 0.32 : 0.22),
                  color: "text.primary",
                  boxShadow: `inset 0 -3px 0 ${c}`,
                  "&:hover": { bgcolor: conAlfa(c, modo === "dark" ? 0.4 : 0.3) },
                },
              }}>
              {p}
            </ToggleButton>
          );
        })}
      </ToggleButtonGroup>
      {/* Sin ninguna marcada se ven todas; decirlo evita leer "nada seleccionado" como "nada". */}
      <Typography sx={{ fontSize: 11.5, color: "text.secondary", mt: 0.5 }}>
        {valor.length ? valor.join(" + ") : "Todas las posiciones"}
      </Typography>
    </>
  );
}
