"use strict";
/* Insidir Generate: open video models (Wan, LTX, ...) running on this PC. Talks only to 127.0.0.1. */

const G = { st: null, jobs: [], chars: [], tab: "create", form: null, film: null, poll: null };

function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") el.className = v;
    else if (k === "style" && typeof v === "object") Object.assign(el.style, v);
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "value") el.value = v;
    else if (k === "checked") el.checked = !!v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat()) if (kid !== null && kid !== undefined && kid !== false) el.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  return el;
}
async function api(method, path, body) {
  const opt = { method, headers: {} };
  if (body !== undefined) { opt.headers["Content-Type"] = "application/json"; opt.body = JSON.stringify(body); }
  const r = await fetch("/api/gen/" + path, opt);
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.error || r.statusText);
  return d;
}
function toast(msg, err) {
  const t = document.getElementById("toast");
  t.textContent = msg; t.className = "toast" + (err ? " err" : ""); t.hidden = false;
  clearTimeout(toast.t); toast.t = setTimeout(() => (t.hidden = true), err ? 7000 : 2600);
}
const field = (label, input, hint) => h("label", { class: "field" }, h("span", {}, label), input, hint ? h("div", { class: "hint" }, hint) : null);
const seg = (opts, cur, on) => h("div", { class: "seg" }, opts.map(([v, t]) => h("button", { class: String(cur) === String(v) ? "on" : "", onclick: () => on(v) }, t)));
const sel = (opts, cur, on, blank) => h("select", { onchange: e => on(e.target.value) }, blank ? h("option", { value: "" }, blank) : null,
  Object.entries(opts).map(([v, t]) => h("option", { value: v, selected: cur === v }, typeof t === "string" ? t : t.name)));

async function upload(file) {
  const r = await fetch(`/api/gen/uploads?filename=${encodeURIComponent(file.name)}`, { method: "POST", body: file });
  const d = await r.json();
  if (!r.ok) throw new Error(d.error || "Upload failed");
  return d;
}

// ------------------------------------------------------------ boot
async function boot() {
  try { G.st = await api("GET", "status"); } catch (e) { document.getElementById("gen").append(h("div", { class: "notice" }, "The generate engine isn't available: " + e.message)); return; }
  G.chars = (await api("GET", "characters")).characters;
  G.form = defaults("t2v");
  hwPills();
  render();
  refreshJobs();
  G.poll = setInterval(refreshJobs, 1500);
}

function defaults(task) {
  return { task, model: G.st.recommended[task] || "", prompt: "", negative: "", raw_prompt: false, camera: [], camera_speed: "medium",
    lens: "", lighting: "", style: "photoreal", motion: 0.5, adherence: 0.5, aspect: "16:9", seconds: 5, fps: 0, steps: 0,
    seed: -1, variations: 1, quality: "standard", refine: null, image: "", last_image: "", video: "", mask: "", references: [], character_ids: [],
    control: "none", control_scale: 1.0, strength: 0.7,
    post: { stabilize: false, deflicker: false, faces: false, fps: 0, upscale: 1, upscaler: "ai", film_finish: false, logo_corner: "top-left", codec: "h264", quality: "high", sound: true } };
}

// Mirrors engine.QUALITY so the switches below show what each level turns on.
const QUALITY = {
  draft: { variations: 1, refine: false, upscale: 1, finish: false, hint: "Fewer steps: a quick look at composition and motion." },
  standard: { variations: 1, refine: false, upscale: 1, finish: false, hint: "The model's own recommended settings." },
  high: { variations: 2, refine: true, upscale: 2, finish: true, hint: "25% more steps, best of 2 takes, a detail pass at 1.5× size, AI upscale 2×, film finish." },
  max: { variations: 3, refine: true, upscale: 2, finish: true, hint: "50% more steps, best of 3 takes, detail pass, AI upscale 2×, film finish. Slowest." },
};

function setQuality(f, q) {
  const Q = QUALITY[q];
  Object.assign(f, { quality: q, variations: Q.variations, refine: null });
  Object.assign(f.post, { upscale: Q.upscale, film_finish: Q.finish });
}

function hwPills() {
  const hw = G.st.hardware, el = document.getElementById("hw");
  el.innerHTML = "";
  const pill = (cls, text, title) => el.append(h("span", { class: "pill " + cls, title }, text));
  pill(hw.device === "cuda" ? "ok" : hw.ready ? "off" : "bad", hw.device === "cuda" ? `${hw.name} · ${hw.vram_gb} GB` : hw.name, hw.reason);
  pill(G.st.tools.rife ? "ok" : "off", G.st.tools.rife ? "RIFE" : "Interp: FFmpeg MCI", "Frame interpolation");
  pill(G.st.tools.realesrgan || hw.ready ? "ok" : "off", G.st.tools.realesrgan ? "Real-ESRGAN" : hw.ready ? "Real-ESRGAN (PyTorch)" : "Upscale: Lanczos", "Upscaling");
}

const TABS = [["create", "Create"], ["film", "Film"], ["characters", "Characters"], ["models", "Models"], ["history", "History"]];
function render() {
  const main = document.getElementById("gen");
  main.innerHTML = "";
  const hw = G.st.hardware;
  if (hw.device !== "cuda") main.append(h("div", { class: "notice" },
    hw.device === "cpu" ? "No NVIDIA GPU found. Real models still run, on the CPU, but a few seconds of video can take hours. For practical use run this on a PC with an NVIDIA GPU (8 GB+ for Wan 1.3B/VACE 1.3B, 12 GB+ for Wan 2.2 5B, 24 GB+ for the 14B models)." : hw.reason));
  main.append(h("div", { class: "tabs" }, TABS.map(([id, t]) => h("button", { class: G.tab === id ? "on" : "", onclick: () => { G.tab = id; render(); } }, t))));
  const body = h("div", { id: "gbody", class: "enter" });
  main.append(body);
  ({ create: viewCreate, film: viewFilm, characters: viewCharacters, models: viewModels, history: viewHistory })[G.tab](body);
}

// ------------------------------------------------------------ create
function modelsFor(task) {
  return Object.fromEntries(Object.entries(G.st.models).filter(([, m]) => m.tasks.includes(task))
    .map(([id, m]) => [id, `${m.name}${m.installed ? "" : " (not downloaded)"}${m.fits ? "" : " (needs more VRAM)"}${m.license === "apache-2.0" ? "" : " · check licence"}`]));
}

function fileInput(label, key, accept, multiple) {
  const f = G.form;
  const input = h("input", { type: "file", accept, multiple, style: { display: "none" } });
  const preview = h("div", { class: "upl-prev" });
  const show = () => {
    preview.innerHTML = "";
    const ids = multiple ? f[key] : (f[key] ? [f[key]] : []);
    for (const id of ids) {
      const isVid = /\.(mp4|mov|webm|mkv)$/.test(id);
      preview.append(isVid ? h("video", { src: `/api/gen/uploads/${id}`, muted: true, loop: true, autoplay: true, playsinline: true })
        : h("img", { src: `/api/gen/uploads/${id}` }));
    }
  };
  input.onchange = async () => {
    try {
      for (const file of input.files) {
        const r = await upload(file);
        if (multiple) f[key] = [...f[key], r.id]; else f[key] = r.id;
      }
      show();
    } catch (e) { toast(e.message, true); }
  };
  show();
  return h("div", { class: "upl" }, h("div", { class: "row" }, h("b", {}, label),
    h("button", { class: "small", onclick: () => input.click() }, multiple ? "Add" : "Choose"),
    h("button", { class: "small ghost", onclick: () => { f[key] = multiple ? [] : ""; show(); } }, "Clear")), input, preview);
}

function viewCreate(el) {
  const f = G.form, st = G.st;
  const set = (k, v, redraw) => { f[k] = v; if (redraw) render(); };
  const promptBox = h("textarea", { rows: 4, value: f.prompt, placeholder: "Describe the shot: who or what, doing what, where. e.g. a woman in a red coat walks through a rainy Tokyo street at night, reflections on the wet ground" });
  promptBox.oninput = () => (f.prompt = promptBox.value);
  const final = h("pre", { class: "final-prompt" });
  const conflicts = h("div", {});
  const showFinal = async () => {
    const r = await api("POST", "prompt", { ...f });
    final.textContent = (f.raw_prompt ? f.prompt : r.prompt) + "\n\nNEGATIVE: " + r.negative;
    conflicts.innerHTML = "";
    for (const c of r.conflicts) conflicts.append(h("div", { class: "notice" }, "Conflicting instructions: " + c + ". The model will compromise; pick one."));
  };
  const chips = (opts, key, multi) => h("div", { class: "chips" }, Object.entries(opts).map(([v, t]) => {
    const on = multi ? f[key].includes(v) : f[key] === v;
    return h("span", { class: "chip" + (on ? " on" : ""), title: t, onclick: () => {
      f[key] = multi ? (on ? f[key].filter(x => x !== v) : [...f[key], v].slice(-2)) : (on ? "" : v); render();
    } }, v.replace(/_/g, " "));
  }));
  const task = f.task;
  const needs = {
    i2v: [fileInput("Start image", "image", "image/*")],
    flf2v: [fileInput("First frame", "image", "image/*"), fileInput("Last frame", "last_image", "image/*")],
    v2v: [fileInput("Source video (motion is kept)", "video", "video/*")],
    r2v: [fileInput("Reference images (faces, outfits, objects)", "references", "image/*", true)],
    control: [fileInput("Reference video (its motion is transferred)", "video", "video/*"), fileInput("Character / start image (optional)", "image", "image/*")],
    edit: [fileInput("Video to edit", "video", "video/*"), fileInput("Mask: white where to change (image or video)", "mask", "image/*,video/*")],
    extend: [fileInput("Clip to continue", "video", "video/*")],
  }[task] || [];
  const charPick = G.chars.length ? h("div", { class: "chips" }, G.chars.map(c => {
    const on = f.character_ids.includes(c.id);
    return h("span", { class: "chip" + (on ? " on" : ""), onclick: () => { f.character_ids = on ? f.character_ids.filter(x => x !== c.id) : [...f.character_ids, c.id]; render(); } }, c.name);
  })) : h("div", { class: "hint" }, "No saved characters yet (Characters tab).");
  const m = st.models[f.model];
  const num = (k, attrs) => { const i = h("input", { type: "number", value: f[k], ...attrs }); i.onchange = () => (f[k] = Number(i.value)); return i; };
  const range = (k, min, max, step) => { const i = h("input", { type: "range", min, max, step, value: f[k] }); const b = h("b", {}, f[k]); i.oninput = () => { f[k] = Number(i.value); b.textContent = i.value; }; return h("div", { class: "row" }, i, b); };
  const P = f.post;
  const pchk = (k, t) => h("label", { class: "check" + (P[k] ? " on" : "") }, h("input", { type: "checkbox", checked: P[k], onchange: e => { P[k] = e.target.checked; render(); } }), t);
  el.append(
    h("div", { class: "panel" },
      h("h2", {}, "What to make"),
      seg(Object.entries(st.tasks), task, v => { const keep = { prompt: f.prompt }; G.form = { ...defaults(v), ...keep }; render(); }),
      h("div", { style: { height: "12px" } }),
      field("Model", sel(modelsFor(task), f.model, v => set("model", v, true), "Pick a model"),
        m ? `${m.note} · ~${m.vram_gb} GB VRAM · ${m.disk_gb} GB download · ${m.license === "apache-2.0" ? "Apache-2.0 (commercial use OK)" : "custom licence: read it before commercial use"}${m.installed ? "" : " · download it on the Models tab first"}` : "No installed model can do this yet: see the Models tab."),
      ...needs,
      task === "r2v" || task === "control" || task === "t2v" || task === "i2v" ? field("Characters", charPick, "Saved characters keep the same face, hair and outfit: their description goes into the prompt and, with VACE models, their reference images go to the model.") : null),
    h("div", { class: "panel" },
      h("h2", {}, "Prompt"),
      promptBox,
      h("div", { class: "grid2" },
        field("Camera (up to two, combined)", chips(st.camera, "camera", true)),
        field("Camera speed", seg(Object.entries(st.speeds).map(([v]) => [v, v]), f.camera_speed, v => set("camera_speed", v, true)))),
      h("div", { class: "grid3" },
        field("Lens", sel(st.lenses, f.lens, v => set("lens", v), "Auto")),
        field("Lighting", sel(st.lighting, f.lighting, v => set("lighting", v), "As described")),
        field("Look", sel(st.styles, f.style, v => set("style", v)))),
      h("div", { class: "grid2" },
        field("Motion strength", range("motion", 0, 1, 0.05), "Subtle ↔ dynamic"),
        field("Prompt adherence", range("adherence", 0, 1, 0.05), "Loose ↔ literal (sets guidance scale)")),
      (task === "i2v" || task === "control") ? field("Precise camera path", seg([["none", "From the prompt"], ["camera", "Depth-guided (VACE)"], ["pose", "Pose from video"], ["depth", "Depth from video"], ["edges", "Edges from video"]], f.control, v => set("control", v, true)),
        "Depth-guided builds a 3D-ish scene from your image with Depth Anything and moves the camera through it, so the move is exact. Needs a VACE model.") : null,
      task === "v2v" ? field("How much to change", range("strength", 0.2, 1, 0.05)) : null,
      field("Negative prompt (added to the standard one)", (() => { const i = h("input", { type: "text", value: f.negative, placeholder: "e.g. text, watermark, extra people" }); i.oninput = () => (f.negative = i.value); return i; })()),
      h("label", { class: "check" + (f.raw_prompt ? " on" : "") }, h("input", { type: "checkbox", checked: f.raw_prompt, onchange: e => set("raw_prompt", e.target.checked, true) }), "Send my prompt exactly as written (skip enhancement)"),
      h("div", { class: "row" }, h("button", { onclick: showFinal }, "Show the final prompt")),
      conflicts, final),
    h("div", { class: "panel" },
      h("h2", {}, "Output"),
      field("Quality", seg([["draft", "Draft"], ["standard", "Standard"], ["high", "High"], ["max", "Max"]], f.quality, v => { setQuality(f, v); render(); }),
        QUALITY[f.quality].hint + (st.hardware.device === "cuda" ? "" : " On a CPU every step up multiplies the wait: High and Max can take hours.")),
      h("label", { class: "check" + ((f.refine ?? QUALITY[f.quality].refine) ? " on" : "") }, h("input", { type: "checkbox", checked: f.refine ?? QUALITY[f.quality].refine, onchange: e => set("refine", e.target.checked, true) }),
        "Detail pass: re-render the best take at 1.5× size so the model paints real fine detail (needs a Wan text-to-video model downloaded)"),
      h("div", { class: "grid3" },
        field("Aspect", seg([["16:9", "16:9"], ["9:16", "9:16"], ["1:1", "1:1"], ["4:5", "4:5"], ["21:9", "21:9"]], f.aspect, v => set("aspect", v, true))),
        field("Duration", seg([[5, "5s"], [10, "10s"], [15, "15s"], [30, "30s"], [60, "60s"]], f.seconds, v => set("seconds", Number(v), true)), "Past the model's clip length, the engine continues the shot from its last frames and blends the joins."),
        field("Variations", seg([[1, "1"], [2, "2"], [3, "3"], [4, "4"]], f.variations, v => set("variations", Number(v), true)), "Each is scored for consistency, flicker, sharpness and motion; the best is finished.")),
      h("div", { class: "grid3" },
        field("Seed (-1 = random)", num("seed", { min: -1 })),
        field("Steps (0 = model default)", num("steps", { min: 0, max: 100 })),
        field("Control strength", range("control_scale", 0.3, 1.5, 0.05)))),
    h("div", { class: "panel" },
      h("h2", {}, "Finishing"),
      h("div", { class: "fxgrid" }, pchk("stabilize", "Stabilise (vid.stab)"), pchk("deflicker", "Remove flicker"),
        pchk("faces", "Enhance faces (GFPGAN, if installed)"), pchk("sound", "Sound: ambience + effects timed to the motion"), pchk("clip_score", "Score prompt adherence with CLIP (downloads 600 MB once)"),
        pchk("film_finish", "Film finish: fine grain + micro-contrast, so surfaces don't look waxy")),
      h("div", { class: "grid3" },
        field("Frame rate", seg([[0, "Native"], [24, "24"], [30, "30"], [60, "60"]], P.fps, v => { P.fps = Number(v); render(); }), "Higher rates are interpolated (RIFE if installed, else motion-compensated)."),
        field("Upscale", h("div", { style: { display: "grid", gap: "6px" } }, seg([[1, "Off"], [2, "2×"], [4, "4×"]], P.upscale, v => { P.upscale = Number(v); render(); }),
          seg([["ai", "AI (Real-ESRGAN)"], ["fast", "Fast (Lanczos)"]], P.upscaler, v => { P.upscaler = v; render(); })),
          P.upscaler === "fast" ? "Plain resize: seconds, but no new detail." : G.st.tools.realesrgan ? "Real-ESRGAN (ncnn, GPU)" : `Real-ESRGAN in PyTorch (64 MB download once)${st.hardware.device === "cuda" ? "" : "; on a CPU about a minute per frame"}`),
        field("Format", seg([["h264", "MP4 H.264"], ["h265", "H.265"], ["prores", "ProRes"], ["webm", "WebM"]], P.codec, v => { P.codec = v; render(); }))),
      field("Insidir logo", seg([["top-left", "Top left"], ["top-right", "Top right"], ["bottom-left", "Bottom left"], ["bottom-right", "Bottom right"]], P.logo_corner || "top-left", v => { P.logo_corner = v; render(); }),
        "Always on every video, with the no-yellow filter: yellows come out neutral, while skin, orange and red stay as they are.")),
    h("div", { class: "row" }, h("button", { class: "primary big", onclick: submit }, "Generate"),
      h("span", { class: "hint" }, "Queued jobs run one at a time on this machine. Follow them on the History tab.")));
}

async function submit() {
  const f = G.form;
  if (!f.model) return toast("Pick a model", true);
  if (!f.prompt.trim() && !["extend", "edit"].includes(f.task)) return toast("Write a prompt", true);
  if (!G.st.models[f.model].installed) return toast("Download the model first (Models tab)", true);
  try {
    await api("POST", "jobs", { kind: "generate", title: f.prompt.slice(0, 80), payload: f });
    toast("Queued"); G.tab = "history"; render();
  } catch (e) { toast(e.message, true); }
}

// ------------------------------------------------------------ models
function viewModels(el) {
  const hw = G.st.hardware;
  el.append(h("div", { class: "panel" }, h("h2", {}, "Models"),
    h("p", { class: "hint" }, `This machine: ${hw.name}${hw.vram_gb ? ` (${hw.vram_gb} GB)` : ""}. Models download once from Hugging Face (free) and run locally. "Strategy" is how the model fits: all on the GPU, offloaded in turns, or layer by layer (slowest).`),
    h("table", { class: "mtable" }, h("tr", {}, ["Model", "Does", "VRAM", "Download", "Licence", "Strategy", ""].map(t => h("th", {}, t))),
      Object.entries(G.st.models).map(([id, m]) => {
        const job = G.jobs.find(j => j.kind === "download" && j.payload.model === id && ["queued", "running"].includes(j.status));
        return h("tr", {},
          h("td", {}, h("b", {}, m.name), h("div", { class: "hint" }, m.note)),
          h("td", {}, m.tasks.map(t => G.st.tasks[t]).join(", ")),
          h("td", {}, `${m.vram_gb} GB`), h("td", {}, `${m.disk_gb} GB`),
          h("td", {}, m.license === "apache-2.0" ? "Apache-2.0" : h("a", { href: m.license_url, target: "_blank", rel: "noopener" }, "Custom: read ↗")),
          h("td", {}, m.fits ? m.strategy : "too little VRAM"),
          h("td", {}, m.installed ? h("span", { class: "badge gen" }, "installed")
            : job ? h("div", {}, h("div", { class: "hint" }, job.message), h("div", { class: "big-progress" }, h("div", { style: { width: (job.progress * 100) + "%" } })))
              : h("button", { class: "small", onclick: async () => { await api("POST", "jobs", { kind: "download", title: "Download " + m.name, payload: { model: id } }); toast("Downloading"); refreshJobs(); } }, "Download")));
      }))));
}

// ------------------------------------------------------------ characters
function viewCharacters(el) {
  const name = h("input", { type: "text", placeholder: "Name, e.g. Mara" });
  const desc = h("textarea", { rows: 3, placeholder: "Exact look, repeated in every shot: e.g. a woman in her 30s with short black hair, freckles, green eyes, wearing a worn brown leather jacket and a grey scarf" });
  el.append(h("div", { class: "panel" }, h("h2", {}, "Characters"),
    h("p", { class: "hint" }, "Characters stay the same across shots and videos: the description is written into every prompt, and with Wan VACE models their reference photos go to the model itself. Use 2-4 clear photos (face, full body) of a person you have the rights to, or an AI-generated face."),
    h("div", { class: "grid2" }, field("Name", name), field("Description", desc)),
    h("button", { class: "primary", onclick: async () => {
      if (!name.value.trim()) return toast("Name the character", true);
      await api("POST", "characters", { name: name.value, description: desc.value });
      G.chars = (await api("GET", "characters")).characters; render();
    } }, "Add character")));
  for (const c of G.chars) {
    const input = h("input", { type: "file", accept: "image/*", multiple: true, style: { display: "none" } });
    input.onchange = async () => {
      for (const file of input.files) await fetch(`/api/gen/characters/${c.id}/images?filename=${encodeURIComponent(file.name)}`, { method: "POST", body: file });
      G.chars = (await api("GET", "characters")).characters; render();
    };
    const d = h("textarea", { rows: 2, value: c.description || "" });
    d.onchange = () => api("PUT", `characters/${c.id}`, { description: d.value });
    el.append(h("div", { class: "panel" }, h("div", { class: "row" }, h("h3", {}, c.name), h("span", { style: { flex: 1 } }),
      h("button", { class: "small", onclick: () => input.click() }, "Add photos"), input,
      h("button", { class: "small danger", onclick: async () => { if (!confirm(`Delete ${c.name}?`)) return; await api("DELETE", `characters/${c.id}`); G.chars = (await api("GET", "characters")).characters; render(); } }, "Delete")),
      d, h("div", { class: "upl-prev" }, (c.files || []).map(n => h("img", { src: `/api/gen/characters/${c.id}/images/${n}` })))));
  }
}

// ------------------------------------------------------------ film
function viewFilm(el) {
  const text = h("textarea", { rows: 6, placeholder: "Describe the film or paste a script. Blank lines (or INT./EXT. headings) start new scenes; each sentence becomes a shot. Put dialogue in quotes." });
  const model = sel(Object.fromEntries(Object.entries(G.st.models).filter(([, m]) => m.tasks.includes("t2v")).map(([id, m]) => [id, m.name + (m.installed ? "" : " (not downloaded)")])), G.filmModel || G.st.recommended.t2v || "", v => (G.filmModel = v));
  const reply = h("textarea", { rows: 4, placeholder: "Optional: paste Claude's JSON reply here" });
  let music = "";
  const musicIn = h("input", { type: "file", accept: "audio/*", style: { display: "none" } });
  musicIn.onchange = async () => { try { music = (await upload(musicIn.files[0])).id; toast("Music added"); } catch (e) { toast(e.message, true); } };
  const beat = h("input", { type: "checkbox" });
  el.append(h("div", { class: "panel" }, h("h2", {}, "Film"),
    h("p", { class: "hint" }, "One description becomes scenes and shots with varied coverage (establishing, medium, close-up) and camera moves. Edit any shot, generate, then regenerate single shots without redoing the rest."),
    text,
    h("div", { class: "row" },
      h("button", { class: "primary", onclick: async () => { G.film = await api("POST", "story/plan", { text: text.value, characters: G.chars.map(c => c.id) }); render(); } }, "Plan shots"),
      h("button", { onclick: async () => { const r = await api("POST", "story/claude-prompt", { text: text.value }); await navigator.clipboard.writeText(r.prompt).catch(() => {}); toast("Prompt for claude.ai copied"); } }, "Copy a prompt for Claude"),
      h("button", { onclick: async () => { try { G.film = await api("POST", "story/parse", { reply: reply.value }); render(); } catch (e) { toast(e.message, true); } } }, "Use Claude's reply")),
    reply));
  if (!G.film) return;
  const shots = G.film.scenes.flatMap(s => s.shots);
  for (const sc of G.film.scenes) {
    el.append(h("h3", {}, sc.heading));
    for (const sh of sc.shots) {
      const p = h("textarea", { rows: 2, value: sh.prompt }); p.oninput = () => (sh.prompt = p.value);
      const secs = h("input", { type: "number", min: 2, max: 30, value: sh.seconds }); secs.onchange = () => (sh.seconds = Number(secs.value));
      const speed = h("input", { type: "number", min: 0.25, max: 4, step: 0.25, value: sh.speed || 1 }); speed.onchange = () => (sh.speed = Number(speed.value));
      el.append(h("div", { class: "panel shot" },
        h("div", { class: "row" }, h("b", {}, sh.id), h("span", { class: "hint" }, sh.shot), h("span", { style: { flex: 1 } }),
          sh.take ? h("button", { class: "small", onclick: () => { sh.take = null; toast("This shot will be regenerated on the next render"); render(); } }, "Regenerate this shot") : null),
        boardFrame(sh),
        p,
        h("div", { class: "grid3" },
          field("Camera", sel(G.st.camera, (sh.camera || [])[0] || "", v => (sh.camera = v ? [v] : []), "none")),
          field("Seconds", secs), field("Speed (slow-mo < 1)", speed)),
        h("div", { class: "grid2" },
          field("Transition in", sel(G.st.transitions, sh.transition || "cut", v => (sh.transition = v))),
          field("Dialogue (spoken by a Kokoro voice)", (() => { const i = h("input", { type: "text", value: sh.dialogue || "" }); i.oninput = () => (sh.dialogue = i.value); return i; })()))));
    }
  }
  el.append(h("div", { class: "row" }, h("button", { onclick: async () => {
    const mid = G.filmModel || G.st.recommended.t2v;
    if (!mid || !G.st.models[mid].installed) return toast("Download a text-to-video model first", true);
    for (const sh of shots) {
      const j = await api("POST", "jobs", { kind: "generate", title: `Storyboard ${sh.id}`, payload: { ...defaults("t2v"), model: mid,
        prompt: sh.prompt, camera: sh.camera || [], lens: sh.lens || "", lighting: sh.lighting || "", seconds: 0, post: { codec: "h264", sound: false } } });
      sh.board = j.id;
    }
    toast("Storyboard frames queued: one still per shot"); render();
  } }, "Storyboard: one still per shot (quick preview)")));
  el.append(h("div", { class: "panel" }, h("h2", {}, "Render"),
    h("div", { class: "grid2" }, field("Model", model), field("Music (optional, yours or licensed)", h("div", { class: "row" }, h("button", { onclick: () => musicIn.click() }, "Choose music"), musicIn, h("label", { class: "check" }, beat, "Cut on the beat")))),
    h("button", { class: "primary big", onclick: async () => {
      const mid = G.filmModel || G.st.recommended.t2v;
      if (!mid || !G.st.models[mid].installed) return toast("Download a text-to-video model first", true);
      await api("POST", "jobs", { kind: "film", title: `Film: ${shots.length} shots`, payload: { film: G.film, model: mid, settings: { aspect: "16:9", fps: 24, music, beat_sync: beat.checked } } });
      toast("Film queued"); G.tab = "history"; render();
    } }, `Render ${shots.length} shots`)));
}

function boardFrame(sh) {
  if (!sh.board) return null;
  const j = G.jobs.find(x => x.id === sh.board);
  if (!j || j.status !== "done") return h("div", { class: "hint" }, j ? `Storyboard: ${j.message}` : "Storyboard queued");
  const name = (j.result.final || "").split(/[\\/]/).pop();
  return h("video", { class: "board", src: `/api/gen/file/${j.id}/${name}`, muted: true, preload: "auto" });
}

// ------------------------------------------------------------ history
async function refreshJobs() {
  try { G.jobs = (await api("GET", "jobs")).jobs; } catch (e) { return; }
  if (G.tab === "history") drawHistory();
  if (G.tab === "film" && G.film && G.film.scenes.some(sc => sc.shots.some(sh => sh.board && !document.querySelector(`video.board[src*="${sh.board}"]`)))
      && G.jobs.some(j => j.status === "done" && G.film.scenes.some(sc => sc.shots.some(sh => sh.board === j.id)))) render();
  if (G.tab === "models" && G.jobs.some(j => j.kind === "download" && j.status === "running")) render();
  for (const j of G.jobs) if (j.kind === "download" && j.status === "done" && !G.st.models[j.payload.model]?.installed) { G.st = await api("GET", "status"); render(); break; }
}

function viewHistory(el) { el.append(h("div", { id: "hist" })); drawHistory(); }

function drawHistory() {
  const el = document.getElementById("hist");
  if (!el) return;
  const open = new Set([...el.querySelectorAll("details[open]")].map(d => d.dataset.id));
  el.innerHTML = "";
  if (!G.jobs.length) el.append(h("p", { class: "hint" }, "Nothing generated yet."));
  for (const j of G.jobs) {
    const r = j.result || {};
    const file = r.final ? `/api/gen/file/${j.id}/${r.final.split(/[\\/]/).pop()}` : null;
    el.append(h("div", { class: "panel job " + j.status },
      h("div", { class: "row" }, h("b", {}, j.title), h("span", { class: "badge" }, j.status), h("span", { style: { flex: 1 } }),
        ["queued", "running"].includes(j.status) ? h("button", { class: "small", onclick: () => api("POST", `jobs/${j.id}/cancel`).then(refreshJobs) }, "Cancel")
          : h("button", { class: "small danger", onclick: () => api("DELETE", `jobs/${j.id}`).then(refreshJobs) }, "Delete")),
      ["queued", "running"].includes(j.status) ? h("div", {}, h("div", { class: "big-progress" }, h("div", { style: { width: (j.progress * 100).toFixed(1) + "%" } })), h("div", { class: "hint" }, j.message)) : null,
      j.error ? h("div", { class: "notice" }, j.error) : null,
      file ? h("div", { class: "result" }, h("video", { src: file, controls: true, loop: true, playsinline: true, preload: "metadata" }),
        h("div", {},
          r.size ? h("div", { class: "hint" }, `${r.size[0]}×${r.size[1]} · ${r.frames} frames @ ${r.fps} fps · seed ${r.seed} · ${r.seconds}s on ${r.device}`) : null,
          r.candidates && r.candidates.length > 1 ? h("div", { class: "hint" }, "Candidates (best finished): " + r.candidates.map(c => `seed ${c.seed}: ${c.scores.total.toFixed(3)}`).join(" · ")) : null,
          h("a", { class: "btnlink", href: file, download: "" }, "Download"),
          r.prompt ? h("details", { "data-id": j.id, open: open.has(j.id) }, h("summary", {}, "Prompt and scores"),
            h("pre", { class: "final-prompt" }, (r.prompt.prompt || "") + "\n\nNEGATIVE: " + (r.prompt.negative || "") + "\n\n" + JSON.stringify((r.candidates || [])[0]?.scores || {}, null, 1))) : null)) : null));
  }
}

boot();
