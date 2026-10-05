// Las tablas de datos viajan UNA vez por entidad (`react/datos-jugadores.js`, `datos-equipos.js`,
// `datos-tiros.js`) y las comparten todas las vistas de esa entidad: cada vista solo trae su
// configuración. Se piden con <script src> y no con fetch, por la misma razón que los fragmentos
// del cascarón (`web/section_views.py`): tiene que funcionar abierto con doble clic (file://).
import { useEffect, useState } from "react";

const pedidas = {};   // nombre -> Promise de la tabla

export function cargarDatos(nombre) {
  const g = (window.futvizDatos = window.futvizDatos || {});
  if (g[nombre]) return Promise.resolve(g[nombre]);
  if (!pedidas[nombre]) {
    pedidas[nombre] = new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src = `react/datos-${nombre}.js`;
      s.onload = () => (g[nombre] ? resolve(g[nombre]) : reject(new Error(`datos-${nombre}.js no define la tabla`)));
      s.onerror = () => { delete pedidas[nombre]; reject(new Error(`no se pudo cargar datos-${nombre}.js`)); };
      document.head.appendChild(s);
    });
  }
  return pedidas[nombre];
}

// La tabla con sus accesos de lectura. `c` son las columnas numéricas (null = sin dato); `f` las de
// códigos (jugador/equipo, liga, temporada, posición, nivel, sub-21).
export function prepararTabla(p) {
  const f = p.f;
  // Columnas derivadas (`derivadas`, ver `react_views.registrar_tabla`): no viajan, se calculan AQUÍ
  // con la misma operación que usó Python (`xG90 + xA90`, `goles / (minutos / 90)`). Redondear el
  // resultado al viajar perdería el ruido de coma flotante (0.15000000000000002) que decide empates
  // exactos como "xga90 <= mediana" cuando la mediana es justo 0.15.
  const c = { ...p.c };
  for (const [nombre, [tipo, a, b]] of Object.entries(p.derivadas || {})) {
    if (!c[a]) continue;
    if (tipo === "suma") {
      if (!c[b]) continue;
      c[nombre] = c[a].map((v, i) => (v == null || c[b][i] == null ? null : v + c[b][i]));
    } else if (tipo === "por90") {
      const m = c.min;
      c[nombre] = c[a].map((v, i) => (v == null || m[i] == null ? null : v / (m[i] / 90)));
    }
  }
  return {
    ...p,
    c,
    nombre: (r) => p.nombres[f.j[r]],
    equipo: (r) => (f.e ? p.equipos[f.e[r]] : ""),
    liga: (r) => p.ligas[f.l[r]],
    posicion: (r) => (f.p && f.p[r] >= 0 ? p.posiciones[f.p[r]] : ""),
  };
}

const memo = new WeakMap();
export function useTabla(nombre) {
  const [estado, setEstado] = useState({ T: null, error: null });
  useEffect(() => {
    let vivo = true;
    cargarDatos(nombre).then((p) => {
      if (!memo.has(p)) memo.set(p, prepararTabla(p));
      if (vivo) setEstado({ T: memo.get(p), error: null });
    }).catch((e) => vivo && setEstado({ T: null, error: e }));
    return () => { vivo = false; };
  }, [nombre]);
  return estado;
}
