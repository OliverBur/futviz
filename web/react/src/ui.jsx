// Piezas de interfaz compartidas por todas las vistas.
import Box from "@mui/material/Box";
import Skeleton from "@mui/material/Skeleton";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import InfoOutlined from "@mui/icons-material/InfoOutlined";

// "Texto con **negritas**" -> nodos. Los textos de insights.py traen ese marcado.
export function Md({ texto }) {
  return texto.split(/\*\*(.+?)\*\*/g).map((t, i) => (i % 2 ? <strong key={i}>{t}</strong> : t));
}

// Un texto de varios párrafos (separados por línea en blanco), cada uno con su marcado.
export function Parrafos({ texto, sx }) {
  return texto.split("\n\n").map((p, i) => (
    <Typography key={i} sx={{ fontSize: 14, lineHeight: 1.6, mb: 1.25, ...sx }}><Md texto={p} /></Typography>
  ));
}

export const Rotulo = ({ children, ayuda }) => (
  <Typography sx={{ fontSize: 10.5, fontWeight: 700, letterSpacing: ".07em", textTransform: "uppercase",
    color: "text.secondary", mb: 0.75, display: "flex", alignItems: "center", gap: 0.5 }}>
    {children}
    {ayuda && (
      <Tooltip title={ayuda} arrow enterTouchDelay={0}>
        <InfoOutlined aria-label="Más información" tabIndex={0}
          sx={{ fontSize: 14, cursor: "help", textTransform: "none", outlineOffset: 2 }} />
      </Tooltip>
    )}
  </Typography>
);

export function Cargando({ alto = 520 }) {
  return (
    <Box role="status" aria-label="Cargando la vista" sx={{ display: "grid", gap: 1.5 }}>
      <Skeleton variant="text" width="38%" height={28} />
      <Skeleton variant="rounded" width="100%" height={alto} />
    </Box>
  );
}

export function Aviso({ children }) {
  return (
    <Box role="alert" sx={{ minHeight: 200, display: "grid", placeItems: "center", color: "text.secondary", fontSize: 14 }}>
      {children}
    </Box>
  );
}
