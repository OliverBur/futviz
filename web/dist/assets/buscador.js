// Buscador de la landing: un jugador, un equipo o una gráfica, y a la vista que lo muestra.
//
// El campo del hero es un combobox (patrón ARIA "combobox + listbox") con la lista desplegada debajo;
// en pantallas chicas se abre a pantalla completa porque el teclado del teléfono deja poco espacio.
// El índice (`assets/search-index.js`, lo escribe `web/landing.py`) se pide la primera vez que alguien
// apunta o enfoca el campo, nunca al cargar la página, y con <script> y no fetch para que funcione
// también desde file://. Sin JS el campo es un <form> que lleva al análisis exploratorio.
//
// Un jugador o equipo lleva a las dispersiones con `?t=<temporada>&fijar=<nombre>` (el esquema de
// `react/src/urlEstado.js`): la temporada es la última en la que tiene punto en ESA gráfica, así nunca
// cae en una vista donde no aparece.
(function () {
  "use strict";
  var form = document.getElementById("buscador");
  if (!form) return;
  var input = document.getElementById("q");
  var panel = document.getElementById("panel");
  var lista = document.getElementById("sugerencias");
  var aviso = document.getElementById("aviso");
  var anuncio = document.getElementById("anuncio");
  var cerrar = document.getElementById("cerrar");
  var EDA = form.getAttribute("action");
  var MAX = 8;
  var GRUPOS = [["j", "Jugadores"], ["e", "Equipos"], ["g", "Gráficas"]];
  var movil = window.matchMedia("(max-width: 640px)");
  var entradas = null, carga = null, opciones = [], activa = -1, tAnuncio = 0;

  // En un teléfono el texto completo no cabe en el campo: uno más corto que diga lo mismo.
  if (movil.matches) input.placeholder = "Jugador, equipo o gráfica…";

  function norm(s) { return s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase(); }

  function url(slug, temporada, nombre) {
    var q = temporada ? "?" + new URLSearchParams({ t: temporada, fijar: nombre }).toString() : "";
    return EDA + "#" + slug + q;
  }

  // El índice viaja compacto (ver landing.construir_indice); aquí se arma cada entrada con sus destinos.
  function preparar(ix) {
    var v = ix.v, out = [];
    function destinos(nombre, ds) {
      return ds.map(function (d) { return { etiqueta: v[d[0]][1], url: url(v[d[0]][0], ix.t[d[1]], nombre) }; });
    }
    ix.j.forEach(function (x) {
      out.push({ tipo: "j", nombre: x[0], det: x[1] + " · " + ix.l[x[2]], peso: x[3], acc: destinos(x[0], x[4]) });
    });
    ix.e.forEach(function (x) {
      out.push({ tipo: "e", nombre: x[0], det: ix.l[x[1]], peso: 0, acc: destinos(x[0], x[2]) });
    });
    v.forEach(function (x) {
      out.push({ tipo: "g", nombre: x[1], det: "Análisis exploratorio · " + x[3], peso: 0, acc: [{ etiqueta: "", url: EDA + "#" + x[0] }] });
    });
    ix.a.forEach(function (x) {
      out.push({ tipo: "g", nombre: x[0], det: x[2] + " · lectura", peso: 0, acc: [{ etiqueta: "", url: x[1] }] });
    });
    out.forEach(function (e) { e.n = norm(e.nombre); });
    return out;
  }

  function cargar() {
    if (!carga) {
      carga = new Promise(function (ok, mal) {
        var s = document.createElement("script");
        s.src = "assets/search-index.js";
        s.onload = function () { window.futvizIndice ? ok(entradas = preparar(window.futvizIndice)) : mal(); };
        s.onerror = function () { s.remove(); mal(); };
        document.head.appendChild(s);
      });
      carga.catch(function () { carga = null; });   // permite reintentar
    }
    return carga;
  }

  // Ranking: empieza con > una palabra empieza con > contiene. Empates: más minutos jugados, nombre más corto.
  var ORDEN_TIPO = { j: 0, e: 1, g: 2 };
  function buscar(qn) {
    var res = [];
    entradas.forEach(function (e) {
      var i = e.n.indexOf(qn);
      if (i < 0) return;
      var nivel = i === 0 ? 0 : /[\s\-.'’]/.test(e.n.charAt(i - 1)) ? 1 : 2;
      res.push({ e: e, nivel: nivel });
    });
    res.sort(function (a, b) {
      return a.nivel - b.nivel || b.e.peso - a.e.peso || ORDEN_TIPO[a.e.tipo] - ORDEN_TIPO[b.e.tipo] ||
        a.e.nombre.length - b.e.nombre.length || a.e.nombre.localeCompare(b.e.nombre, "es");
    });
    return res.slice(0, MAX).map(function (r) { return r.e; });
  }

  // El nombre con la coincidencia en <mark>: se normaliza letra por letra para mapear de vuelta al original.
  function resaltar(nombre, qn) {
    var mapa = [], normal = "";
    for (var i = 0; i < nombre.length; i++) {
      var n = norm(nombre.charAt(i));
      for (var k = 0; k < n.length; k++) { normal += n.charAt(k); mapa.push(i); }
    }
    var frag = document.createDocumentFragment(), p = normal.indexOf(qn);
    if (p < 0) { frag.appendChild(document.createTextNode(nombre)); return frag; }
    var a = mapa[p], b = mapa[p + qn.length - 1] + 1, m = document.createElement("mark");
    m.textContent = nombre.slice(a, b);
    frag.appendChild(document.createTextNode(nombre.slice(0, a)));
    frag.appendChild(m);
    frag.appendChild(document.createTextNode(nombre.slice(b)));
    return frag;
  }

  function span(clase, texto) {
    var s = document.createElement("span");
    s.className = clase;
    if (texto != null) s.textContent = texto;
    return s;
  }

  function opcion(nombreNodo, det, accion, destino, secundaria) {
    var li = document.createElement("li");
    li.id = "op-" + opciones.length;
    li.className = "opcion" + (secundaria ? " sec" : "");
    li.setAttribute("role", "option");
    li.setAttribute("aria-selected", "false");
    var txt = span("txt"), nom = span("nom");
    nom.appendChild(nombreNodo);
    txt.appendChild(nom);
    if (det) txt.appendChild(span("det", det));
    li.appendChild(txt);
    if (accion) li.appendChild(span("acc", accion));
    li.addEventListener("mousedown", function (ev) { ev.preventDefault(); });   // el foco se queda en el campo
    li.addEventListener("mousemove", function () { marcar(opciones.indexOf(destino)); });
    li.addEventListener("click", function () { ir(destino.url); });
    destino.li = li;
    opciones.push(destino);
    return li;
  }

  function pintar(q) {
    var qn = norm(q.trim());
    lista.textContent = "";
    opciones = [];
    activa = -1;
    input.removeAttribute("aria-activedescendant");
    aviso.hidden = true;
    if (!qn) { anunciar(""); return; }
    var res = buscar(qn), principal = null;
    GRUPOS.forEach(function (g) {
      var deGrupo = res.filter(function (e) { return e.tipo === g[0]; });
      if (!deGrupo.length) return;
      var grupo = document.createElement("li"), ul = document.createElement("ul"), id = "grupo-" + g[0];
      grupo.setAttribute("role", "presentation");
      grupo.appendChild(span("grupo", g[1])).id = id;
      ul.setAttribute("role", "group");
      ul.setAttribute("aria-labelledby", id);
      deGrupo.forEach(function (e) {
        var acc = e.acc[0];
        ul.appendChild(opcion(resaltar(e.nombre, qn), e.det, e.tipo === "g" ? "Abrir" : "Ver en " + acc.etiqueta, { url: acc.url }));
        // al primer jugador o equipo: "Ver a {nombre} en…" con las otras gráficas donde aparece
        if (!principal && e.tipo !== "g" && e.acc.length > 1) {
          principal = e;
          var rot = document.createElement("li");
          rot.setAttribute("role", "presentation");
          rot.appendChild(span("grupo", "Ver a " + e.nombre + " en…"));
          ul.appendChild(rot);
          e.acc.slice(1).forEach(function (a) {
            ul.appendChild(opcion(document.createTextNode(a.etiqueta), "", "", { url: a.url }, true));
          });
        }
      });
      grupo.appendChild(ul);
      lista.appendChild(grupo);
    });
    if (!res.length) {
      mostrarAviso("Sin resultados para «" + q.trim() + "». Prueba con un apellido o el nombre de un equipo.", "Ver todas las gráficas");
    }
    anunciar(res.length ? res.length + (res.length === 1 ? " resultado" : " resultados") : "Sin resultados");
  }

  function mostrarAviso(texto, enlace) {
    aviso.textContent = texto + " ";
    var a = document.createElement("a");
    a.href = EDA;
    a.textContent = enlace;
    aviso.appendChild(a);
    aviso.hidden = false;
  }

  function anunciar(texto) {
    clearTimeout(tAnuncio);
    tAnuncio = setTimeout(function () { anuncio.textContent = texto; }, 400);
  }

  function abrir() {
    if (!panel.hidden) return;
    panel.hidden = false;
    input.setAttribute("aria-expanded", "true");
    requestAnimationFrame(function () { panel.classList.add("visible"); });
  }

  function cerrarPanel() {
    panel.classList.remove("visible");
    panel.hidden = true;
    input.setAttribute("aria-expanded", "false");
    input.removeAttribute("aria-activedescendant");
    activa = -1;
  }

  // En pantallas chicas el buscador abierto ocupa la pantalla (CSS `.buscador.abierto`).
  function abrirMovil() {
    if (!movil.matches || form.classList.contains("abierto")) return;
    form.classList.add("abierto");
    document.documentElement.style.overflow = "hidden";
    abrir();
    if (!input.value.trim()) {
      aviso.textContent = "Escribe el nombre de un jugador, un equipo o una gráfica.";
      aviso.hidden = false;
    }
  }

  function cerrarMovil() {
    form.classList.remove("abierto");
    document.documentElement.style.overflow = "";
    cerrarPanel();
    input.blur();
  }

  function marcar(i) {
    if (activa >= 0 && opciones[activa]) opciones[activa].li.setAttribute("aria-selected", "false");
    activa = i;
    if (i < 0 || !opciones[i]) { input.removeAttribute("aria-activedescendant"); return; }
    opciones[i].li.setAttribute("aria-selected", "true");
    input.setAttribute("aria-activedescendant", opciones[i].li.id);
    opciones[i].li.scrollIntoView({ block: "nearest" });
  }

  function ir(destino) { window.location.href = destino; }

  function actualizar() {
    var q = input.value;
    if (!q.trim()) {
      pintar("");
      if (form.classList.contains("abierto")) abrirMovil(); else cerrarPanel();
      return;
    }
    abrir();
    if (!entradas) {
      lista.textContent = "";
      aviso.textContent = "Cargando…";
      aviso.hidden = false;
    }
    cargar().then(function () { if (input.value === q) pintar(q); }, function () {
      lista.textContent = "";
      mostrarAviso("No pude cargar el buscador.", "Ir a las gráficas");
    });
  }

  function precargar() { cargar().catch(function () {}); }

  form.addEventListener("pointerenter", precargar);
  input.addEventListener("focus", function () {
    precargar();
    abrirMovil();
    if (input.value.trim()) actualizar();
  });
  input.addEventListener("input", actualizar);
  form.addEventListener("submit", function (ev) {
    ev.preventDefault();
    if (opciones.length) ir(opciones[activa >= 0 ? activa : 0].url);
    else if (!input.value.trim()) ir(EDA);
  });
  input.addEventListener("keydown", function (ev) {
    var n = opciones.length;
    if (ev.key === "ArrowDown" || ev.key === "ArrowUp") {
      ev.preventDefault();
      if (panel.hidden && input.value.trim()) actualizar();
      if (n) marcar(ev.key === "ArrowDown" ? Math.min(n - 1, activa + 1) : Math.max(-1, activa - 1));
    } else if ((ev.key === "Home" || ev.key === "End") && activa >= 0 && n) {
      ev.preventDefault();   // sin opción marcada, Inicio/Fin mueven el cursor del texto como siempre
      marcar(ev.key === "Home" ? 0 : n - 1);
    } else if (ev.key === "Escape") {
      ev.preventDefault();
      if (form.classList.contains("abierto")) cerrarMovil();
      else if (!panel.hidden) cerrarPanel();
      else input.value = "";
    }
  });
  cerrar.addEventListener("click", cerrarMovil);
  // A pantalla completa el foco no sale del buscador: Tab va del campo a "Cerrar" y de vuelta.
  form.addEventListener("keydown", function (ev) {
    if (ev.key !== "Tab" || !form.classList.contains("abierto")) return;
    ev.preventDefault();
    (document.activeElement === input ? cerrar : input).focus();
  });
  // En escritorio la lista se cierra al salir del buscador.
  form.addEventListener("focusout", function (ev) {
    if (!form.classList.contains("abierto") && !form.contains(ev.relatedTarget)) cerrarPanel();
  });
  document.addEventListener("pointerdown", function (ev) {
    if (!form.contains(ev.target) && !form.classList.contains("abierto")) cerrarPanel();
  });
  // "/" fuera de un campo de texto lleva al buscador.
  document.addEventListener("keydown", function (ev) {
    if (ev.key !== "/" || ev.ctrlKey || ev.metaKey || ev.altKey) return;
    var t = ev.target;
    if (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)) return;
    ev.preventDefault();
    input.focus();
  });
})();
