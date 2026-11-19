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

// El encabezado de cada tarjeta: la pregunta que responde (la misma de la portada), el título, UNA bajada de
// cómo leer la gráfica (máximo ~140 caracteres) y, en gris, la muestra (mínimo de minutos, temporada).
export function Encabezado({ pregunta, titulo, bajada, muestra }) {
  return (
    <Box sx={{ mb: 1.5 }}>
      {pregunta && (
        <Typography sx={{ fontSize: 13, fontWeight: 600, color: "success.main", mb: 0.25 }}>{pregunta}</Typography>
      )}
      <Typography component="h2" sx={{ fontSize: 17, fontWeight: 700, color: "primary.main" }}>{titulo}</Typography>
      {bajada && <Typography sx={{ fontSize: 14.5, lineHeight: 1.5, mt: 0.5, maxWidth: 760 }}>{bajada}</Typography>}
      {muestra && <Typography sx={{ fontSize: 12.5, color: "text.secondary", mt: 0.5 }}>{muestra}</Typography>}
    </Box>
  );
}

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
