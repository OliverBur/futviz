// El botón de descarga de las gráficas: solo un ícono, sin texto, con su nombre en el tooltip. Va en la fila de controles o en
// el pie de la gráfica (junto a «Datos: …»), nunca encima del dibujo.
import { useEffect, useState } from "react";
import IconButton from "@mui/material/IconButton";
import Tooltip from "@mui/material/Tooltip";
import Download from "@mui/icons-material/Download";
import { precargarMarca } from "./descargarImagen.js";

// `alDescargar` puede ser asíncrona: mientras corre el botón se apaga, para que un segundo clic no baje dos imágenes.
export function BotonDescarga({ alDescargar, sx }) {
  const [ocupado, setOcupado] = useState(false);
  useEffect(() => { precargarMarca(); }, []);
  const clic = async () => {
    setOcupado(true);
    try { await alDescargar(); } catch (e) { console.error("futviz: no se pudo descargar la imagen", e); } finally { setOcupado(false); }
  };
  return (
    <Tooltip title="Descargar imagen">
      <span>
        <IconButton size="small" aria-label="Descargar imagen" onClick={clic} disabled={ocupado} sx={{ color: "text.secondary", "@media (pointer: coarse)": { p: "12px" }, ...sx }}>
          <Download fontSize="small" />
        </IconButton>
      </span>
    </Tooltip>
  );
}
