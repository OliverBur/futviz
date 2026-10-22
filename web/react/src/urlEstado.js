// Los filtros de cada vista viven en la URL: `analisis-exploratorio.html#goles-vs-xg?t=2025-26&pos=Delantero`.
//
// El hash es `#<vista>` (lo lee el cascarón, `web/section_views.py`) más, opcionalmente, `?clave=valor&...`
// con los filtros de ESA vista. Así un enlace abre la vista con la misma temporada, posición, jugadores
// fijados, etc., y se puede compartir.
//
// Cómo encaja con el cascarón:
// - Una vista lee sus parámetros UNA vez, al montarse (`leerParams`): se monta al activarse, y en ese momento
//   el hash ya es el suyo.
// - Cada vez que cambia un filtro, la vista reescribe el hash con `history.replaceState` (no agrega entradas
//   al historial ni dispara `hashchange`), y solo si es la vista activa: las demás siguen montadas pero
//   ocultas y no deben pisar la URL.
// - Al activar una vista el cascarón dispara `futviz-vista-activa`; la vista que se activa repone ahí sus
//   parámetros (cambiar de pestaña deja el hash en `#<vista>` a secas).
//
// Un valor igual al de por defecto se omite, para que la URL se quede corta; una lista va como clave repetida
// (`pos=Medio&pos=Delantero`).
import { useEffect, useState } from "react";

const EVENTO = "futviz-vista-activa";

function partirHash() {
  // La parte de los parámetros se deja SIN decodificar: URLSearchParams la decodifica por su cuenta, y
  // decodificarla antes rompería un valor que lleve "&" o "=".
  const h = window.location.hash.slice(1);
  const i = h.indexOf("?");
  return i < 0 ? { slug: decodeURIComponent(h), q: "" } : { slug: decodeURIComponent(h.slice(0, i)), q: h.slice(i + 1) };
}

// Los parámetros de la URL si el hash es de la vista `id`; vacío si no (otra vista, o ninguna).
export function leerParams(id) {
  const { slug, q } = partirHash();
  return new URLSearchParams(slug === id ? q : "");
}

// `estado` es `{clave: valor | [valores] | null}`; null, "" y [] no se escriben.
function codificar(estado) {
  const p = new URLSearchParams();
  for (const [clave, valor] of Object.entries(estado)) {
    if (valor == null || valor === "") continue;
    if (Array.isArray(valor)) valor.forEach((v) => p.append(clave, v));
    else p.set(clave, valor);
  }
  return p.toString();
}

function useVistaActiva(id) {
  const [activa, setActiva] = useState(() => partirHash().slug === id);
  useEffect(() => {
    const alActivar = (e) => setActiva(e.detail.slug === id);
    document.addEventListener(EVENTO, alActivar);
    return () => document.removeEventListener(EVENTO, alActivar);
  }, [id]);
  return activa;
}

// Mantiene el hash al día con los filtros de la vista mientras es la activa.
export function usePublicarParams(id, estado) {
  const activa = useVistaActiva(id);
  const q = codificar(estado);
  useEffect(() => {
    if (!activa) return;
    window.history.replaceState(window.history.state, "", `#${id}${q ? `?${q}` : ""}`);
  }, [activa, id, q]);
}

// Para validar lo que viene de la URL: el valor si está entre los permitidos, si no `por`.
export const entre = (valor, permitidos, por) => (permitidos.includes(valor) ? valor : por);
