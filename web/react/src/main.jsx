// Punto de entrada del bundle. El cascarón del sitio (`web/section_views.py`) lo carga UNA vez y, cada
// vez que inserta el fragmento de una vista, llama a `window.futvizReact.montar()`. Un fragmento trae un
// <div data-rx="tipo" data-rx-id="id"> y, justo detrás, su configuración en `window.futvizVistas[id]`
// (ver `web/react_views.py`); aquí se monta cada contenedor que todavía no esté montado.
import { createRoot } from "react-dom/client";
import ScatterVista from "./ScatterVista.jsx";
import CajasVista from "./CajasVista.jsx";
import MapaTiros from "./MapaTiros.jsx";

const VISTAS = { scatter: ScatterVista, cajas: CajasVista, tiros: MapaTiros };

function montar() {
  document.querySelectorAll("[data-rx]:not([data-rx-listo])").forEach((el) => {
    const tipo = el.getAttribute("data-rx");
    const id = el.getAttribute("data-rx-id");
    const Vista = VISTAS[tipo];
    if (!Vista || !(window.futvizVistas || {})[id]) {
      console.error(`futviz-react: falta el tipo "${tipo}" o la configuración de "${id}"`);
      return;
    }
    el.setAttribute("data-rx-listo", "1");
    createRoot(el).render(<Vista id={id} />);
  });
}

window.futvizReact = { montar };
montar();
