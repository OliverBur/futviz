// Piezas de interfaz compartidas por todas las vistas.
import Box from "@mui/material/Box";
import Skeleton from "@mui/material/Skeleton";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import InfoOutlined from "@mui/icons-material/InfoOutlined";

// Para buscar por nombre: sin mayúsculas, sin acentos y con las letras que no se descomponen (ø, ł, ß...) en su
// equivalente simple, así "odegaard" encuentra a "Ødegaard". Es la misma tabla que `consolidate_data.TRANSLITERA`.
const TRANS = { ø: "o", ł: "l", đ: "d", ð: "d", ı: "i", ħ: "h", ŧ: "t", þ: "th", ß: "ss", æ: "ae", œ: "oe" };
export const sinAcentos = (s) => s.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase()
  .replace(/[øłđðıħŧþßæœ]/g, (c) => TRANS[c]);

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

// «Cómo leer la gráfica»: un párrafo explicativo (cada línea del texto es un párrafo), sin negritas y al ancho de los demás textos.
export function ComoLeer({ texto }) {
  return texto.split("\n").map((l) => l.trim()).filter(Boolean).map((l, i) => (
    <Typography key={i} sx={{ fontSize: 14, lineHeight: 1.65, mb: 1, color: "text.primary" }}>{l}</Typography>
  ));
}

// La primera frase de un texto calculado (y sin la cola que va después de una raya larga).
export function unaFrase(texto) {
  const t = String(texto || "").replace(/\s+—\s+[\s\S]*$/, ".");
  const m = t.match(/^[\s\S]*?[.!?](?=\s+[A-ZÁÉÍÓÚÑ¿¡0-9]|$)/);
  return (m ? m[0] : t).trim();
}

// «Qué dice esta gráfica»: un solo renglón, con lo que muestra la gráfica con lo que hay elegido.
export function QueDice({ texto }) {
  if (!texto) return null;
  return (
    <Typography sx={{ mt: 1.5, fontSize: 13, lineHeight: 1.5, color: "text.secondary" }}>
      <Box component="span" sx={{ fontWeight: 700 }}>Qué dice esta gráfica: </Box>
      <Md texto={unaFrase(texto)} />
    </Typography>
  );
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
      {bajada && <Typography sx={{ fontSize: 14.5, lineHeight: 1.5, mt: 0.5 }}>{bajada}</Typography>}
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
