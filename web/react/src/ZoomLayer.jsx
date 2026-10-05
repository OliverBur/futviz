// Zoom y pan propios (los oficiales de MUI X son Pro). Viven DENTRO del chart porque
// necesitan `useDrawingArea` para pasar de píxeles a datos, pero no dibujan nada:
// escuchan eventos del <svg> directamente, sin una capa encima que le robe el
// puntero al tooltip y al highlight de MUI.
//
// Gestos:
//   arrastrar ........ mover la vista
//   Ctrl/⌘ + rueda ... acercar/alejar en el cursor (el pellizco del trackpad llega
//                      como Ctrl + rueda). La rueda sola NO hace zoom a propósito:
//                      la gráfica ocupa media pantalla y secuestrar el scroll de la
//                      página al pasar por encima es una trampa. Se avisa con una pista.
//   doble clic ....... acercar al punto
//   pellizco (táctil)  acercar/alejar + mover
import { useEffect, useRef } from "react";
import { useDrawingArea } from "@mui/x-charts/hooks";
import { acercar, desplazar } from "./zoom.js";

const UMBRAL_ARRASTRE = 4; // px antes de que un clic se considere arrastre

export function ZoomLayer({ viewRef, base, onView, onArea, onPista }) {
  const area = useDrawingArea();
  const g = useRef(null);
  const areaRef = useRef(area);
  areaRef.current = area;

  useEffect(() => { onArea({ left: area.left, top: area.top, width: area.width, height: area.height }); },
    [area.left, area.top, area.width, area.height]);

  useEffect(() => {
    const svg = g.current && g.current.ownerSVGElement;
    if (!svg) return undefined;

    let raf = 0;
    let pendiente = null;
    const aplicar = (v) => {
      viewRef.current = v;            // ya vale para el próximo evento, antes del render
      pendiente = v;
      if (!raf) raf = requestAnimationFrame(() => { raf = 0; onView(pendiente); });
    };

    const punto = (e) => {
      const r = svg.getBoundingClientRect();
      const a = areaRef.current;
      return {
        px: e.clientX - r.left - a.left, py: e.clientY - r.top - a.top,
        fx: (e.clientX - r.left - a.left) / a.width,
        fy: 1 - (e.clientY - r.top - a.top) / a.height,
      };
    };
    const dentro = (p) => p.fx >= 0 && p.fx <= 1 && p.fy >= 0 && p.fy <= 1;

    // ---- rueda -------------------------------------------------------------
    const onWheel = (e) => {
      const p = punto(e);
      if (!dentro(p)) return;
      if (!(e.ctrlKey || e.metaKey)) { onPista(); return; }   // scroll normal de la página
      e.preventDefault();
      aplicar(acercar(viewRef.current, base, Math.exp(e.deltaY * 0.0022), p.fx, p.fy));
    };

    // ---- punteros: arrastre de un dedo y pellizco de dos ---------------------
    const activos = new Map();      // pointerId -> { x, y }
    let arrastrando = false;
    let origen = null;              // dónde empezó el gesto (para el umbral)
    let ultimaDist = 0;
    let bloquearClicHasta = 0;

    const centroYDist = () => {
      const [a, b] = [...activos.values()];
      return { cx: (a.x + b.x) / 2, cy: (a.y + b.y) / 2, d: Math.hypot(a.x - b.x, a.y - b.y) };
    };
    const onDown = (e) => {
      if (e.pointerType === "mouse" && e.button !== 0) return;
      const p = punto(e);
      if (!dentro(p)) return;
      activos.set(e.pointerId, { x: e.clientX, y: e.clientY });
      origen = { x: e.clientX, y: e.clientY };
      if (activos.size === 2) { ultimaDist = centroYDist().d; arrastrando = true; }
    };
    const onMove = (e) => {
      if (!activos.has(e.pointerId)) return;
      const previo = activos.get(e.pointerId);
      const ahora = { x: e.clientX, y: e.clientY };
      activos.set(e.pointerId, ahora);
      const a = areaRef.current;

      if (activos.size === 2) {                       // pellizco
        const { cx, cy, d } = centroYDist();
        const r = svg.getBoundingClientRect();
        const fx = (cx - r.left - a.left) / a.width;
        const fy = 1 - (cy - r.top - a.top) / a.height;
        if (ultimaDist > 0 && d > 0) {
          aplicar(acercar(viewRef.current, base, ultimaDist / d, fx, fy));
        }
        ultimaDist = d;
        return;
      }
      if (!arrastrando) {
        if (Math.hypot(ahora.x - origen.x, ahora.y - origen.y) < UMBRAL_ARRASTRE) return;
        arrastrando = true;
        try { svg.setPointerCapture(e.pointerId); } catch (_) { /* puntero ya liberado */ }
        // En <html> y no en el contenedor: el tooltip de MUI se pinta en un portal.
        document.documentElement.classList.add("rx-arrastrando");     // oculta el tooltip, cursor "grabbing"
      }
      aplicar(desplazar(viewRef.current, base, ahora.x - previo.x, ahora.y - previo.y, a.width, a.height));
    };
    const onUp = (e) => {
      if (!activos.delete(e.pointerId)) return;
      if (arrastrando) bloquearClicHasta = performance.now() + 60;  // el clic que cierra el arrastre no es un clic
      if (activos.size === 0) {
        arrastrando = false;
        document.documentElement.classList.remove("rx-arrastrando");
      } else if (activos.size === 1) {
        ultimaDist = 0;
      }
    };
    // En captura, para llegar antes que el plugin de MUI que convierte el clic en
    // "seleccionar este punto".
    const onClic = (e) => {
      if (performance.now() < bloquearClicHasta) { e.stopPropagation(); e.preventDefault(); }
    };
    const onDoble = (e) => {
      const p = punto(e);
      if (!dentro(p)) return;
      e.preventDefault();
      aplicar(acercar(viewRef.current, base, 0.5, p.fx, p.fy));
    };

    svg.addEventListener("wheel", onWheel, { passive: false });
    svg.addEventListener("pointerdown", onDown);
    svg.addEventListener("pointermove", onMove);
    svg.addEventListener("pointerup", onUp);
    svg.addEventListener("pointercancel", onUp);
    svg.addEventListener("click", onClic, true);
    svg.addEventListener("dblclick", onDoble);
    return () => {
      if (raf) cancelAnimationFrame(raf);
      svg.removeEventListener("wheel", onWheel);
      svg.removeEventListener("pointerdown", onDown);
      svg.removeEventListener("pointermove", onMove);
      svg.removeEventListener("pointerup", onUp);
      svg.removeEventListener("pointercancel", onUp);
      svg.removeEventListener("click", onClic, true);
      svg.removeEventListener("dblclick", onDoble);
    };
  }, [base, onView, onPista, viewRef]);

  return <g ref={g} />;
}
