// El tema de MUI NO inventa colores: los lee de las variables CSS del sitio
// (`BRAND_ROOT_CSS` en web/site_utils.py) y se vuelve a construir cuando el
// botón sol/luna cambia `data-theme`. MUI necesita colores reales (no `var(...)`)
// porque calcula tonos derivados, así que se resuelven con getComputedStyle.
import { useEffect, useMemo, useState } from "react";
import { createTheme } from "@mui/material/styles";

const TOKENS = ["bg", "surface", "primary", "brand-accent", "interactive", "interactive-soft",
  "text-body", "muted", "border"];

export const modoActual = () =>
  document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";

function leerTokens() {
  const cs = getComputedStyle(document.documentElement);
  const t = {};
  TOKENS.forEach((k) => { t[k] = cs.getPropertyValue(`--color-${k}`).trim(); });
  return t;
}

export function useSitioTema() {
  const [estado, setEstado] = useState(() => ({ modo: modoActual(), t: leerTokens() }));
  useEffect(() => {
    const actualizar = () => setEstado({ modo: modoActual(), t: leerTokens() });
    const mo = new MutationObserver(actualizar);
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => mo.disconnect();
  }, []);

  const theme = useMemo(() => {
    const { modo, t } = estado;
    const fuente = '"Inter", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';
    return createTheme({
      palette: {
        mode: modo,
        primary: { main: t.primary, contrastText: t.bg },
        background: { default: t.bg, paper: t.surface },
        text: { primary: t["text-body"], secondary: t.muted },
        divider: t.border,
      },
      shape: { borderRadius: 8 },
      typography: { fontFamily: fuente, fontSize: 13 },
      components: {
        // Mismo lenguaje que el control segmentado del cascarón (`.seg`): seleccionado
        // en el color primario del sitio, hover con el verde suave.
        MuiToggleButton: {
          styleOverrides: {
            root: {
              textTransform: "none", fontWeight: 600, fontSize: 12.5, lineHeight: 1.2,
              padding: "6px 10px", color: t.muted, borderColor: t.border,
              "&:hover": { backgroundColor: t["interactive-soft"], color: t.primary },
              "&.Mui-selected": {
                backgroundColor: t.primary, color: t.bg,
                "&:hover": { backgroundColor: t.primary },
              },
              "&.Mui-focusVisible": { outline: `2px solid ${t.interactive}`, outlineOffset: 1 },
            },
          },
        },
        MuiChip: { styleOverrides: { root: { fontWeight: 600, fontSize: 12.5 } } },
        MuiTooltip: {
          styleOverrides: {
            tooltip: { backgroundColor: t.primary, color: t.bg, fontSize: 12, fontWeight: 500 },
          },
        },
      },
    });
  }, [estado]);

  return { ...estado, theme };
}
