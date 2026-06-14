/* Editor interactivo de revisión fonológica.
   Por palabra: onda + línea de tiempo de letras arrastrables + añadir/quitar/renombrar.
   "Re-puntuar" envía las secuencias editadas a POST /logopeda/reanalizar/{sesion}. */
(function () {
  "use strict";
  const D = window.DATOS, API = window.API_BASE || "";
  const $ = (t, c, txt) => { const e = document.createElement(t); if (c) e.className = c; if (txt != null) e.textContent = txt; return e; };
  const COLS = ["#dbeafe", "#fef3c7"];

  function render() {
    const app = document.getElementById("app");
    app.innerHTML = "";
    app.appendChild($("h1", null, "Revisión fonológica — " + D.sesion));
    const sub = $("div", "sub", "Edad " + D.edad + " · " + D.palabras.length +
      " palabras · cribado orientativo, NO diagnóstico");
    app.appendChild(sub);

    const barra = $("div", "barra");
    const badge = $("span", "badge " + D.resumen.riesgo, "RIESGO " + D.resumen.riesgo.toUpperCase());
    badge.id = "badge";
    const meta = $("span", "meta"); meta.id = "meta"; actualizarMeta(meta, D.resumen);
    const btn = $("button", "primario", "Re-puntuar sesión");
    btn.onclick = repuntuar;
    barra.append(badge, meta, btn);
    app.appendChild(barra);

    const aviso = $("div", "aviso", "");
    aviso.id = "aviso"; app.appendChild(aviso);

    D.palabras.forEach((p, i) => app.appendChild(tarjeta(p, i)));
  }

  function actualizarMeta(el, r) {
    el.textContent = "impropios: " + r.n_errores_impropios + " · correctas: " +
      r.palabras_correctas + " · inteligibilidad: " + Math.round(r.inteligibilidad_media * 100) + "%";
  }

  function tarjeta(p, idx) {
    const w = $("div", "word"); w.dataset.idx = idx;
    const h = $("h3"); h.innerHTML = p.palabra.toUpperCase() +
      ' <small>(confianza ' + Math.round(p.confianza * 100) + '%' +
      (p.pcc != null ? ' · PCC ' + p.pcc + '%' + (p.severidad ? ' (' + p.severidad + ')' : '') : '') +
      ')</small>';
    w.appendChild(h);
    const line = $("p");
    line.innerHTML = 'Esperado: <span class="fonemas">' + p.esperado +
      '</span> &nbsp; Dijo: <span class="fonemas detec" id="detec-' + idx + '">' + p.detectado + '</span>';
    w.appendChild(line);

    const audio = $("audio"); audio.controls = true; audio.src = p.audio_b64; w.appendChild(audio);

    const cv = $("canvas"); cv.id = "cv-" + idx; w.appendChild(cv);
    const chips = $("div", "chips"); chips.id = "chips-" + idx; w.appendChild(chips);

    const ev = $("div", "eventos"); ev.id = "ev-" + idx; w.appendChild(ev);
    if (p.valida === false) {
      const al = $("div", "err", "⚠ producción no válida (" + (p.motivo_no_valida || "") +
        ") — a repetir, no puntúa");
      w.insertBefore(al, ev);
    }
    pintarEventos(ev, p.eventos);

    w.appendChild($("div", "nota", "Arrastra los bordes para mover dónde está cada letra. " +
      "Pulsa la letra para cambiarla, × para borrarla, + para añadir."));

    // estado de segmentos (fuente de verdad de la secuencia)
    p._segs = p.segmentos.map(s => ({ label: s.label, t_ini: s.t_ini, t_fin: s.t_fin }));
    setTimeout(() => { dibujar(p, idx); pintarChips(p, idx); }, 0);
    return w;
  }

  function pintarEventos(el, eventos) {
    const clin = (eventos || []).filter(e => e.tipo !== "otro");
    if (!clin.length) { el.innerHTML = '<span class="ok">✓ sin procesos clínicos</span>'; return; }
    el.innerHTML = clin.map(e => '<div class="err">• ' + e.tipo + ": " + (e.detalle || "") + "</div>").join("");
  }

  // ---------------- canvas (onda + segmentos) ----------------
  function dibujar(p, idx) {
    const cv = document.getElementById("cv-" + idx);
    const dpr = window.devicePixelRatio || 1;
    const W = cv.clientWidth, H = cv.clientHeight;
    cv.width = W * dpr; cv.height = H * dpr;
    const ctx = cv.getContext("2d"); ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);
    const dur = p.duracion || 1, x = t => (t / dur) * W;

    // bloques de cada letra
    p._segs.forEach((s, i) => {
      ctx.fillStyle = COLS[i % 2];
      ctx.fillRect(x(s.t_ini), 0, x(s.t_fin) - x(s.t_ini), H);
      ctx.fillStyle = "#c0392b"; ctx.font = "bold 15px ui-monospace,monospace";
      ctx.textAlign = "center";
      ctx.fillText(s.label, (x(s.t_ini) + x(s.t_fin)) / 2, 20);
    });
    // onda
    ctx.strokeStyle = "#475569"; ctx.lineWidth = 1; ctx.beginPath();
    const pk = p.peaks, mid = H / 2;
    pk.forEach((v, i) => {
      const px = (i / (pk.length - 1)) * W, h = v * (H * 0.42);
      ctx.moveTo(px, mid - h); ctx.lineTo(px, mid + h);
    });
    ctx.stroke();
    // bordes (handles) entre letras
    ctx.strokeStyle = "#1d4ed8"; ctx.lineWidth = 2;
    for (let i = 0; i < p._segs.length - 1; i++) {
      const bx = x(p._segs[i].t_fin);
      ctx.beginPath(); ctx.moveTo(bx, 0); ctx.lineTo(bx, H); ctx.stroke();
    }
    activarArrastre(p, idx, cv, dur);
  }

  function activarArrastre(p, idx, cv, dur) {
    if (cv._wired) return; cv._wired = true;
    let drag = -1;
    const tAt = e => {
      const r = cv.getBoundingClientRect();
      const cx = (e.touches ? e.touches[0].clientX : e.clientX) - r.left;
      return Math.max(0, Math.min(dur, (cx / r.width) * dur));
    };
    const cerca = t => {
      let best = -1, bd = 1e9;
      for (let i = 0; i < p._segs.length - 1; i++) {
        const d = Math.abs(p._segs[i].t_fin - t);
        if (d < bd) { bd = d; best = i; }
      }
      return (bd < dur * 0.06) ? best : -1;
    };
    const down = e => { drag = cerca(tAt(e)); if (drag >= 0) e.preventDefault(); };
    const move = e => {
      if (drag < 0) return;
      const t = tAt(e);
      const lo = p._segs[drag].t_ini + 0.01, hi = p._segs[drag + 1].t_fin - 0.01;
      const nt = Math.max(lo, Math.min(hi, t));
      p._segs[drag].t_fin = nt; p._segs[drag + 1].t_ini = nt;
      dibujar(p, idx);
    };
    const up = () => { drag = -1; };
    cv.addEventListener("mousedown", down); cv.addEventListener("touchstart", down, { passive: false });
    window.addEventListener("mousemove", move); cv.addEventListener("touchmove", move, { passive: false });
    window.addEventListener("mouseup", up); cv.addEventListener("touchend", up);
  }

  // ---------------- chips (secuencia de letras) ----------------
  function pintarChips(p, idx) {
    const cont = document.getElementById("chips-" + idx);
    cont.innerHTML = "";
    cont.appendChild(botonInsertar(p, idx, 0));
    p._segs.forEach((s, i) => {
      const chip = $("span", "chip");
      const inp = $("input"); inp.value = s.label; inp.maxLength = 3;
      inp.oninput = () => { s.label = inp.value.trim(); sincronizar(p, idx); };
      const x = $("span", "x", "×");
      x.onclick = () => { borrar(p, i); pintarChips(p, idx); dibujar(p, idx); sincronizar(p, idx); };
      chip.append(inp, x);
      cont.appendChild(chip);
      cont.appendChild(botonInsertar(p, idx, i + 1));
    });
  }

  function botonInsertar(p, idx, pos) {
    const b = $("span", "ins", "+");
    b.title = "añadir letra aquí";
    b.onclick = () => { insertar(p, pos); pintarChips(p, idx); dibujar(p, idx); sincronizar(p, idx); };
    return b;
  }

  function insertar(p, pos) {
    const segs = p._segs;
    let t0, t1;
    if (!segs.length) { t0 = 0; t1 = p.duracion || 1; }
    else if (pos === 0) { t0 = 0; t1 = segs[0].t_ini || 0.05; }
    else if (pos >= segs.length) { t0 = segs[segs.length - 1].t_fin; t1 = p.duracion || (t0 + 0.05); }
    else { // partir el hueco a la mitad del segmento previo
      const prev = segs[pos - 1]; const mid = (prev.t_ini + prev.t_fin) / 2;
      t1 = prev.t_fin; prev.t_fin = mid; t0 = mid;
    }
    segs.splice(pos, 0, { label: "a", t_ini: t0, t_fin: t1 });
  }

  function borrar(p, i) {
    const segs = p._segs;
    if (i > 0 && segs[i + 1]) segs[i + 1].t_ini = segs[i].t_ini;
    else if (i > 0) segs[i - 1].t_fin = segs[i].t_fin;
    segs.splice(i, 1);
  }

  function sincronizar(p, idx) {
    const seq = p._segs.map(s => s.label).filter(Boolean).join(" ");
    const el = document.getElementById("detec-" + idx);
    if (el) el.textContent = seq;
    p.detectado = seq;
  }

  // ---------------- re-puntuar contra la API ----------------
  async function repuntuar() {
    const aviso = document.getElementById("aviso");
    const ediciones = {};
    D.palabras.forEach(p => { ediciones[p.palabra] = p._segs.map(s => s.label).filter(Boolean).join(" "); });
    try {
      const r = await fetch(API + "/logopeda/reanalizar/" + encodeURIComponent(D.sesion), {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ediciones, edad: D.edad }),
      });
      if (!r.ok) throw new Error("HTTP " + r.status);
      const data = await r.json();
      const rr = data.resumen_riesgo || data.resumen;
      const badge = document.getElementById("badge");
      badge.className = "badge " + rr.riesgo; badge.textContent = "RIESGO " + rr.riesgo.toUpperCase();
      actualizarMeta(document.getElementById("meta"), rr);
      (data.palabras || []).forEach(pp => {
        const i = D.palabras.findIndex(x => x.palabra === pp.palabra);
        if (i >= 0) pintarEventos(document.getElementById("ev-" + i), pp.eventos);
      });
      aviso.style.display = "none";
    } catch (e) {
      aviso.textContent = "No se pudo re-puntuar (¿estás abriendo la página vía el servidor? " +
        "Inicia la API y abre /sesion/" + D.sesion + "/revision.html). Detalle: " + e.message;
      aviso.style.display = "block";
    }
  }

  render();
  window.addEventListener("resize", () => D.palabras.forEach((p, i) => dibujar(p, i)));
})();
