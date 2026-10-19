"use strict";
/* Insidir Video Studio: local UI. Talks only to the app on 127.0.0.1. */

const S = {
  status: null, settings: null, facts: null, voices: {},
  projects: [], project: null, tab: "brief", issues: [],
  saveTimer: null, lintTimer: null, job: null, uploads: {},
};

// ------------------------------------------------------------ helpers
function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") el.className = v;
    else if (k === "style" && typeof v === "object") Object.assign(el.style, v);
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "value") el.value = v;
    else if (k === "checked") el.checked = !!v;
    else if (k === "html") el.innerHTML = v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat()) {
    if (kid === null || kid === undefined || kid === false) continue;
    el.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  }
  return el;
}

async function api(method, path, body) {
  const opt = { method, headers: {} };
  if (body !== undefined) { opt.headers["Content-Type"] = "application/json"; opt.body = JSON.stringify(body); }
  const r = await fetch("/api/" + path, opt);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || r.statusText);
  return data;
}

// Icon from the studio sprite (web/icons.svg), sized by CSS (.i)
function ic(name) {
  const NS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("class", "i");
  svg.setAttribute("aria-hidden", "true");
  const use = document.createElementNS(NS, "use");
  use.setAttribute("href", `/icons.svg#${name}`);
  svg.append(use);
  return svg;
}

function toast(msg, err) {
  const t = document.getElementById("toast");
  t.textContent = msg; t.className = "toast" + (err ? " err" : ""); t.hidden = false;
  clearTimeout(toast.t); toast.t = setTimeout(() => (t.hidden = true), err ? 6000 : 2400);
}

function field(label, input, hint) {
  return h("label", { class: "field" }, h("span", {}, label), input, hint ? h("div", { class: "hint" }, hint) : null);
}

function fmtSec(s) { return (Math.round(s * 10) / 10).toFixed(1) + "s"; }
const P = () => S.project;

// ------------------------------------------------------------ boot
async function boot() {
  document.getElementById("new-project").onclick = newProject;
  document.getElementById("new-project-2").onclick = newProject;
  document.querySelectorAll("[data-modal]").forEach(b => b.onclick = () => openModal(b.dataset.modal));
  document.getElementById("modal-close").onclick = closeModal;
  document.getElementById("modal").addEventListener("click", e => { if (e.target.id === "modal") closeModal(); });
  try {
    let v;
    [S.status, S.settings, S.facts, v] = await Promise.all([
      api("GET", "status"), api("GET", "settings"), api("GET", "facts"), api("GET", "voices"),
    ]);
    S.voices = v.voices; S.voiceGender = v.gender; S.voiceDefaults = v.defaults;
  } catch (e) { toast("Could not reach the studio: " + e.message, true); return; }
  renderPills();
  document.getElementById("ver").textContent = "v" + S.status.version;
  await loadProjects();
  const last = localStorage.getItem("ivs:last");
  if (last && S.projects.some(p => p.id === last)) openProject(last);
}

function renderPills() {
  const st = S.status, el = document.getElementById("pills");
  el.innerHTML = "";
  const pill = (cls, text, title) => el.append(h("span", { class: "pill " + cls, title }, text));
  pill(st.ffmpeg ? "ok" : "bad", "FFmpeg", st.ffmpeg || "Not found: run install.bat");
  pill(st.kokoro.ready ? "ok" : "bad", "Kokoro voice", st.kokoro.ready ? st.kokoro.model : "Model missing: run install.bat");
  const g = st.avatar.gpus[0];
  pill(g ? "ok" : "off", g ? `GPU ${g.vram_gb} GB` : "No GPU (not needed)", g ? g.name : "Avatars are optional");
  pill(st.motion.ready ? "ok" : "bad", "Motion Canvas", st.motion.ready ? `Node ${st.motion.node_version}` : "Node.js or motion packages missing: run install.bat");
  pill(st.whisper.installed ? "ok" : "off", st.whisper.installed ? "Faster Whisper" : "Whisper off", st.whisper.installed ? `Caption timing model ${st.whisper.model}` : "Optional: captions use estimated timing");
  pill(st.avatar.usable ? "ok" : "off", st.avatar.usable ? "Avatar on" : "Avatar off", st.avatar.reasons.join(" "));
}

async function loadProjects() {
  S.projects = (await api("GET", "projects")).projects;
  const ul = document.getElementById("project-list");
  ul.innerHTML = "";
  for (const p of S.projects) {
    ul.append(h("li", { class: P() && P().id === p.id ? "active" : "", onclick: () => openProject(p.id) },
      p.name, h("small", {}, `${p.beats} beats · ${p.renders.length} renders`)));
  }
}

async function newProject() {
  const name = prompt("Name this video", "Insider trades in 30 seconds");
  if (!name) return;
  const proj = await api("POST", "projects", { name });
  await loadProjects();
  openProject(proj.id);
}

async function openProject(id) {
  S.project = await api("GET", "projects/" + id);
  localStorage.setItem("ivs:last", id);
  S.tab = S.project.script.beats.length ? "script" : (S.project.assets.length ? "script" : "brief");
  await loadProjects();
  renderProject();
  lintSoon(0);
}

// The local copy stays authoritative while editing; the server only stores it.
function save(immediate) {
  clearTimeout(S.saveTimer);
  const mark = document.querySelector(".saved");
  if (mark) mark.textContent = "Saving…";
  return new Promise(resolve => {
    S.saveTimer = setTimeout(async () => {
      try {
        await api("PUT", "projects/" + P().id, P());
        const m = document.querySelector(".saved"); if (m) m.textContent = "Saved";
      } catch (e) { toast(e.message, true); }
      resolve();
    }, immediate ? 0 : 500);
  });
}

function lintSoon(delay = 600) {
  clearTimeout(S.lintTimer);
  S.lintTimer = setTimeout(async () => {
    try {
      S.issues = (await api("POST", `projects/${P().id}/lint`, { script: P().script })).issues;
      renderIssues();
    } catch (e) { /* project may be closed */ }
  }, delay);
}

// ------------------------------------------------------------ project view
const TABS = [["brief", "Brief", "brief"], ["footage", "Footage", "footage"], ["script", "Script", "script"], ["look", "Voice & look", "voice"], ["render", "Render", "render"]];

function renderProject() {
  const main = document.getElementById("main");
  main.innerHTML = "";
  const p = P();
  main.append(
    h("div", { class: "phead" },
      h("h1", {}, p.name), h("span", { class: "saved" }, "Saved"),
      h("span", { style: { flex: 1 } }),
      h("button", { class: "small danger", onclick: deleteProject }, ic("trash"), "Delete project")),
    h("div", { class: "tabs" }, TABS.map(([id, label, icon], i) =>
      h("button", { class: S.tab === id ? "on" : "", onclick: () => { S.tab = id; renderProject(); } }, ic(icon), h("i", {}, i + 1), label))),
    h("div", { id: "tab" }));
  ({ brief: tabBrief, footage: tabFootage, script: tabScript, look: tabLook, render: tabRender })[S.tab](document.getElementById("tab"));
}

async function deleteProject() {
  if (!confirm(`Delete "${P().name}" and its files? This cannot be undone.`)) return;
  await api("DELETE", "projects/" + P().id);
  S.project = null; localStorage.removeItem("ivs:last");
  await loadProjects(); location.reload();
}

// ------------------------------------------------------------ 1 brief
function tabBrief(el) {
  const b = P().brief;
  const bind = (key, input) => { input.addEventListener("input", () => { b[key] = input.type === "range" || input.type === "number" ? Number(input.value) : input.value; save(); }); return input; };
  const secs = h("b", {}, b.target_seconds + "s");
  const range = bind("target_seconds", h("input", { type: "range", min: 21, max: 33, step: 1, value: b.target_seconds }));
  range.addEventListener("input", () => (secs.textContent = range.value + "s"));
  el.append(stylePicker());
  el.append(h("div", { class: "panel" },
    h("h2", {}, "What is this video about?"),
    field("Video name", (() => { const i = h("input", { type: "text", value: P().name }); i.oninput = () => { P().name = i.value; save(); }; return i; })()),
    field("Topic", bind("topic", h("input", { type: "text", value: b.topic, placeholder: "e.g. How to read a Form 4 in Insidir" }))),
    h("div", { class: "grid2" },
      field("Angle / tone", bind("angle", h("input", { type: "text", value: b.angle, placeholder: "curious, practical, plain-spoken" }))),
      field("Audience", bind("audience", h("input", { type: "text", value: b.audience })))),
    h("div", { class: "grid3" },
      field("Hook style", bind("hook_style", h("select", {},
        ["question", "myth", "how-to", "pov"].map(v => h("option", { value: v, selected: b.hook_style === v }, v))))),
      field("Call to action", bind("cta", h("input", { type: "text", value: b.cta }))),
      h("label", { class: "field" }, h("span", {}, "Target length "), h("div", { class: "row" }, range, secs))),
    h("p", { class: "hint" }, "Videos must land between 20 and 35 seconds. The studio adjusts the speaking rate a little to fit, and refuses to render outside that range."),
    h("button", { class: "primary", onclick: () => { S.tab = "footage"; renderProject(); } }, "Next: footage")));
}

function stylePicker() {
  const p = P(), m = S.status.motion, av = S.status.avatar;
  const choose = (mode, template) => {
    const changed = p.mode !== mode || (mode === "animated" && p.template !== template);
    p.mode = mode; if (template) p.template = template;
    save(); renderProject(); lintSoon(0);
    if (changed && p.script.beats.length) toast(mode === "ugc" ? "Format changed. Transcribe your footage on the Script tab." : "Format changed. Rewrite or redraft the script to use its fields.");
  };
  const card = (on, img, title, text, onclick, note) => h("button", { class: "tcard" + (on ? " on" : ""), onclick },
    img ? h("img", { src: img, alt: "" }) : h("div", { class: "tdemo" }, "▶"),
    h("b", {}, title), h("span", {}, text), note ? h("em", { class: "tnote" }, note) : null);
  const anim = (cat) => Object.entries(m.templates).filter(([, t]) => (t.category || "animated") === cat)
    .map(([id, t]) => card(p.mode === "animated" && p.template === id, `/templates/${id}.jpg`, t.name, t.description,
      () => choose("animated", id), m.ready ? null : "Needs install.bat"));
  const group = (title, hint, cards) => h("div", { class: "tgroup" }, h("h3", {}, title), h("p", { class: "hint" }, hint), h("div", { class: "tgrid" }, cards));
  return h("div", { class: "panel" },
    h("h2", {}, "Video format"),
    m.ready ? null : h("div", { class: "notice" }, "Animated and avatar formats need Node.js and the Motion Canvas packages. Run install.bat."),
    group("Animated", "Motion graphics drawn on this PC with Motion Canvas and Rough.js, read by a Kokoro voice.", anim("animated")),
    group("Avatars", "A presenter on screen without filming anyone. Avatars are always disclosed as AI or animated.", [
      ...anim("avatar"),
      card(p.mode === "photo_avatar", "/templates/photo-avatar.jpg", "AI photo avatar",
        "Your presenter photo lip-synced by a local talking-avatar model, cut like UGC with real Insidir screens. Labelled \"AI-generated presenter\".",
        () => choose("photo_avatar"), av.usable ? null : "Needs a GPU + avatar model (Settings)"),
    ]),
    group("UGC: real people", "Film yourself (or upload a clip) and the studio transcribes it, cuts the pauses into jump cuts and adds captions, screens and sound.", [
      card(p.mode === "ugc", "/templates/ugc.jpg", "Talking head (UGC)",
        "Your own face and voice. Pick per sentence: full face, split with the app, face bubble over the app, or app only.",
        () => choose("ugc"), S.status.whisper.installed ? null : "Needs Faster Whisper (install.bat)"),
    ]),
    group("Screen demo", "Cinematic cuts of your real Insidir recordings with a Kokoro voice-over.", [
      card(p.mode === "demo" || !p.mode, null, "Screen-recording demo", "Push-ins, whip cuts and captions over your genuine Insidir screen recordings and screenshots.", () => choose("demo")),
    ]));
}

// ------------------------------------------------------------ 2 footage
function tabFootage(el) {
  const input = h("input", { type: "file", multiple: true, accept: "video/*,image/*,audio/*", style: { display: "none" } });
  input.onchange = () => uploadFiles([...input.files]);
  const drop = h("div", { class: "drop" },
    h("p", {}, h("b", {}, P().mode === "ugc" ? "Drop your talking-head clips (set them to \"Me on camera\") and Insidir screen recordings here"
      : P().mode === "photo_avatar" ? "Drop a presenter photo (set it to Presenter) and Insidir screen recordings here"
      : "Drop screen recordings, screenshots, a presenter photo or a music track here")),
    h("p", { class: "hint" }, "MP4 / MOV / WebM, PNG / JPG / WebP, MP3 / WAV. Record the real Insidir product (Windows: Win+Alt+R with Xbox Game Bar, or OBS). Music must be licensed for commercial use."),
    h("button", { onclick: () => input.click() }, "Choose files"), input);
  drop.addEventListener("dragover", e => { e.preventDefault(); drop.classList.add("over"); });
  drop.addEventListener("dragleave", () => drop.classList.remove("over"));
  drop.addEventListener("drop", e => { e.preventDefault(); drop.classList.remove("over"); uploadFiles([...e.dataTransfer.files]); });
  if (P().mode === "ugc") el.append(recorderPanel());
  el.append(drop);
  const grid = h("div", { class: "assets" });
  for (const [name, up] of Object.entries(S.uploads)) {
    grid.append(h("div", { class: "asset" }, h("div", { class: "meta" }, "Uploading " + name),
      h("div", { class: "progress" }, h("div", { style: { width: (up * 100).toFixed(0) + "%" } }))));
  }
  for (const a of P().assets) grid.append(assetCard(a));
  el.append(grid);
  if (P().assets.length) el.append(h("p", {}, h("button", { class: "primary", onclick: () => { S.tab = "script"; renderProject(); } }, "Next: script")));
}

function assetCard(a) {
  const set = (k, v) => { a[k] = v; save(); lintSoon(); renderProject(); };
  const thumb = a.type === "audio" ? h("div", { class: "thumb", style: { display: "grid", placeItems: "center" } }, "♪ audio")
    : h("div", { class: "thumb", style: { backgroundImage: `url(/api/projects/${P().id}/thumb/${a.id}?t=${a.type === "video" ? Math.min(1, a.duration / 2) : 0})` } });
  const badges = [
    a.genuine ? h("span", { class: "badge gen" }, "genuine") : null,
    a.ai_generated ? h("span", { class: "badge ai" }, "AI") : null,
    a.rights_confirmed ? null : h("span", { class: "badge no" }, "rights?"),
  ];
  const label = h("input", { type: "text", value: a.label });
  label.onchange = () => { a.label = label.value; save(); };
  const notes = h("input", { type: "text", value: a.notes || "", placeholder: "What it shows (helps Claude pick shots)" });
  notes.onchange = () => { a.notes = notes.value; save(); };
  const role = h("select", { onchange: e => set("role", e.target.value) },
    [["creator", "Me on camera (UGC)"], ["screen", "Insidir demo"], ["image", "Other image / b-roll"], ["presenter", "Presenter"], ["music", "Music"]]
      .filter(([v]) => v !== "creator" || a.type === "video" || a.role === "creator")
      .map(([v, t]) => h("option", { value: v, selected: a.role === v }, t)));
  const check = (k, text) => h("label", { class: "check" + (a[k] ? " on" : "") },
    h("input", { type: "checkbox", checked: a[k], onchange: e => set(k, e.target.checked) }), text);
  return h("div", { class: "asset" }, thumb,
    h("div", { class: "meta" }, `${a.type} · ${a.width ? a.width + "×" + a.height : ""} ${a.duration ? "· " + fmtSec(a.duration) : ""} `, badges),
    label, h("div", { style: { height: "6px" } }), notes, h("div", { style: { height: "6px" } }), role,
    check("rights_confirmed", "I made this or have the rights to use it commercially"),
    a.role === "screen" || a.role === "image" ? check("genuine", "Genuine recording/screenshot of the real Insidir product") : null,
    a.role === "presenter" || a.role === "image" ? check("ai_generated", "Shows an AI-generated person or scene (labelled on screen)") : null,
    a.role === "presenter" && !a.ai_generated ? h("div", { class: "hint" }, "A real person must have agreed to appear in an ad. If unsure, mark it AI-generated or don't use it.") : null,
    a.role === "creator" ? check("ai_generated", "This is an AI avatar, not a real person (labelled on screen)") : null,
    a.role === "creator" ? h("div", { class: "hint" }, a.ai_generated ? "Shown with an \"AI-generated presenter\" label." : "You, or someone who agreed to appear. Their own words; if they are paid, say #ad.") : null,
    (a.role === "creator" || a.role === "presenter") && a.type !== "audio" ? h("div", {}, h("div", { class: "hint" }, "Click the face (crops follow it)"),
      focusPicker(a, a.type === "video" ? Math.min(1, a.duration / 2) : 0, a.focus || [0.5, 0.4], f => { a.focus = f; save(); renderProject(); })) : null,
    h("div", { class: "row", style: { marginTop: "6px" } },
      h("button", { class: "small danger", onclick: async () => {
        if (!confirm("Remove this file from the project?")) return;
        await save(true);
        S.project = await api("DELETE", `projects/${P().id}/assets/${a.id}`); renderProject(); lintSoon(0);
      } }, "Remove")));
}

function focusPicker(asset, t, cur, onset) {
  const focus = h("div", { class: "focus", title: "Click to set the focus point" });
  focus.style.backgroundImage = `url(/api/projects/${P().id}/thumb/${asset.id}?t=${t})`;
  focus.append(h("div", { class: "dot", style: { left: cur[0] * 100 + "%", top: cur[1] * 100 + "%" } }));
  focus.onclick = e => {
    const r = focus.getBoundingClientRect();
    const ar = asset.width / asset.height, br = r.width / r.height;
    let w = r.width, hh = r.height, ox = 0, oy = 0;
    if (ar > br) { hh = r.width / ar; oy = (r.height - hh) / 2; } else { w = r.height * ar; ox = (r.width - w) / 2; }
    onset([Math.round(Math.min(1, Math.max(0, (e.clientX - r.left - ox) / w)) * 100) / 100,
      Math.round(Math.min(1, Math.max(0, (e.clientY - r.top - oy) / hh)) * 100) / 100]);
  };
  return focus;
}

function uploadFiles(files, role) {
  for (const f of files) {
    S.uploads[f.name] = 0;
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `/api/projects/${P().id}/assets?filename=${encodeURIComponent(f.name)}` + (role ? `&role=${role}` : ""));
    xhr.upload.onprogress = e => { if (e.lengthComputable) { S.uploads[f.name] = e.loaded / e.total; if (S.tab === "footage") renderProject(); } };
    xhr.onload = async () => {
      delete S.uploads[f.name];
      let data = {};
      try { data = JSON.parse(xhr.responseText); } catch (e) { /* ignore */ }
      if (xhr.status >= 300) toast(`${f.name}: ${data.error || xhr.statusText}`, true);
      else P().assets.push(data);
      if (S.tab === "footage") renderProject();
    };
    xhr.onerror = () => { delete S.uploads[f.name]; toast("Upload failed: " + f.name, true); renderProject(); };
    xhr.send(f);
  }
  renderProject();
}

// Webcam recorder with a teleprompter. Runs in the browser (127.0.0.1 counts as secure, so
// the camera is allowed); the take is uploaded to the project like any other clip.
function recorderPanel() {
  const p = P();
  p.teleprompter = p.teleprompter || [];
  const video = h("video", { autoplay: true, muted: true, playsinline: true });
  const prompter = h("div", { class: "prompter" }, h("div", { class: "prompter-text" }, p.teleprompter.join("\n\n") || "Write your lines below, or get them from Claude on the Script tab."));
  const stage = h("div", { class: "rec-stage" }, video, prompter, h("div", { class: "rec-dot", hidden: true }));
  const lines = h("textarea", { rows: 5, value: p.teleprompter.join("\n"), placeholder: "One line per sentence. Say it your way; the studio cuts to what you actually say." });
  lines.oninput = () => { p.teleprompter = lines.value.split("\n").map(x => x.trim()).filter(Boolean); prompter.firstChild.textContent = p.teleprompter.join("\n\n"); save(); };
  const speed = h("input", { type: "range", min: 10, max: 80, step: 1, value: S.prompterSpeed || 34, title: "Scroll speed" });
  speed.oninput = () => (S.prompterSpeed = Number(speed.value));
  const camSel = h("select", {}), micSel = h("select", {});
  let stream = null, rec = null, chunks = [], raf = 0, t0 = 0;
  const stopStream = () => { if (stream) stream.getTracks().forEach(t => t.stop()); stream = null; };
  const startCam = async () => {
    stopStream();
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { deviceId: camSel.value ? { exact: camSel.value } : undefined, width: { ideal: 1920 }, height: { ideal: 1080 }, frameRate: { ideal: 30 } },
        audio: { deviceId: micSel.value ? { exact: micSel.value } : undefined, echoCancellation: false, noiseSuppression: true, autoGainControl: false, channelCount: 1 },
      });
    } catch (e) { toast("Camera: " + e.message, true); return; }
    video.srcObject = stream;
    const devs = await navigator.mediaDevices.enumerateDevices();
    const fill = (sel, kind, cur) => { sel.innerHTML = ""; devs.filter(d => d.kind === kind).forEach((d, i) => sel.append(h("option", { value: d.deviceId, selected: d.deviceId === cur }, d.label || `${kind} ${i + 1}`))); };
    fill(camSel, "videoinput", stream.getVideoTracks()[0].getSettings().deviceId);
    fill(micSel, "audioinput", stream.getAudioTracks()[0].getSettings().deviceId);
    recBtn.disabled = false;
  };
  camSel.onchange = startCam; micSel.onchange = startCam;
  const scroll = () => {
    const txt = prompter.firstChild;
    const y = ((performance.now() - t0) / 1000) * (S.prompterSpeed || 34);
    txt.style.transform = `translateY(${-y}px)`;
    raf = requestAnimationFrame(scroll);
  };
  const recBtn = h("button", { class: "primary", disabled: true, onclick: () => {
    if (rec && rec.state === "recording") { rec.stop(); return; }
    const type = ["video/webm;codecs=vp9,opus", "video/webm;codecs=vp8,opus", "video/webm", "video/mp4"].find(t => MediaRecorder.isTypeSupported(t));
    chunks = [];
    rec = new MediaRecorder(stream, { mimeType: type, videoBitsPerSecond: 12000000, audioBitsPerSecond: 192000 });
    rec.ondataavailable = e => e.data.size && chunks.push(e.data);
    rec.onstop = () => {
      cancelAnimationFrame(raf); prompter.firstChild.style.transform = "";
      stage.querySelector(".rec-dot").hidden = true;
      recBtn.replaceChildren(ic("record"), "Record");
      const ext = (type || "").includes("mp4") ? "mp4" : "webm";
      const n = P().assets.filter(a => a.role === "creator").length + 1;
      uploadFiles([new File(chunks, `creator-take-${n}.${ext}`, { type: type || "video/webm" })], "creator");
      toast("Take saved. Record another or go to the Script tab to transcribe.");
    };
    // 3-2-1 so the first word isn't clipped
    let c = 3;
    recBtn.disabled = true;
    const tick = () => {
      recBtn.textContent = c ? `Starting in ${c}…` : "";
      if (c-- > 0) return setTimeout(tick, 700);
      rec.start(1000); t0 = performance.now() + 1500; scroll();
      stage.querySelector(".rec-dot").hidden = false;
      recBtn.disabled = false; recBtn.replaceChildren(ic("stop"), "Stop and save take");
    };
    tick();
  } }, ic("record"), "Record");
  return h("div", { class: "panel" },
    h("h2", {}, "Record yourself"),
    h("p", { class: "hint" }, "Hold the phone-style framing in mind: keep your face in the middle third. Look at the lens, not the text. Takes are saved to this project only."),
    h("div", { class: "recorder" }, stage,
      h("div", {},
        h("div", { class: "row" }, h("button", { onclick: startCam }, ic("camera"), "Start camera"), recBtn),
        h("div", { class: "grid2", style: { marginTop: "10px" } }, field("Camera", camSel), field("Microphone", micSel)),
        field("Teleprompter lines", lines),
        h("div", { class: "row" }, h("span", { class: "hint" }, "Scroll speed"), speed))));
}

// ------------------------------------------------------------ 3 script
function tabScript(el) {
  const left = h("div", {});
  const right = h("div", {});
  el.append(h("div", { class: "scriptgrid" }, left, right));

  // writer panel
  const reply = h("textarea", { rows: 6, placeholder: "Paste Claude's whole reply here" });
  const promptBox = h("textarea", { class: "prompt-box", rows: 6, readonly: true });
  const variant = h("select", {}, ["How to read an insider trade", "Follow the people who file", "Try it for a dollar"].map((t, i) => h("option", { value: i }, t)));
  const ugcMode = P().mode === "ugc";
  const useScript = (res) => {
    if (ugcMode) {
      P().teleprompter = res.script.beats.map(b => b.text);
      save(true); toast("Lines added to the teleprompter on the Footage tab"); return;
    }
    P().script = res.script; S.issues = res.issues; save(true); renderProject();
    toast(res.issues.some(i => i.level === "error") ? "Script loaded. Fix the claim guard errors." : "Script loaded");
  };
  if (ugcMode) {
    const creators = P().assets.filter(a => a.role === "creator");
    left.append(h("div", { class: "panel" },
      h("h2", {}, "Your footage"),
      h("p", { class: "hint" }, creators.length
        ? `Faster Whisper listens to ${creators.length} clip${creators.length > 1 ? "s" : ""} on this PC and splits what you said into sentences. Untick the ones to cut; the pauses and "um"s are cut for you.`
        : "Record yourself or upload a clip on the Footage tab (set it to \"Me on camera\") first."),
      h("button", { class: "primary", disabled: !creators.length || !S.status.whisper.installed, onclick: async (e) => {
        if (P().script.beats.length && !confirm("Transcribe again? Your keep/layout choices will be reset.")) return;
        e.target.disabled = true; e.target.textContent = "Transcribing…";
        try {
          const res = await api("POST", `projects/${P().id}/script/transcribe`, {});
          P().script = res.script; S.issues = res.issues; save(true); renderProject();
          toast(`${res.script.beats.length} sentences found`);
        } catch (err) { toast(err.message, true); e.target.disabled = false; e.target.replaceChildren(ic("transcribe"), "Transcribe my footage"); }
      } }, ic("transcribe"), "Transcribe my footage"),
      S.status.whisper.installed ? null : h("div", { class: "notice" }, "UGC needs Faster Whisper. Run install.bat.")));
  }
  left.append(h("div", { class: "panel" },
    h("h2", {}, ugcMode ? "Lines for the teleprompter" : "Write with Claude"),
    h("p", { class: "hint" }, ugcMode ? "Optional. Claude writes talking points from your brief and the approved facts; they go to the teleprompter on the Footage tab." : "Free: copy the prompt into Claude on claude.ai (a free account works), then paste the reply below. The prompt includes your brief, your footage and the approved facts."),
    h("div", { class: "row" },
      h("button", { class: "primary", onclick: async () => {
        const { prompt } = await api("GET", `projects/${P().id}/prompt`);
        promptBox.value = prompt;
        try { await navigator.clipboard.writeText(prompt); toast("Prompt copied"); } catch (e) { promptBox.select(); toast("Select the prompt and copy it (Ctrl+C)"); }
      } }, ic("copy"), "1. Copy prompt"),
      h("a", { href: "https://claude.ai/new", target: "_blank", rel: "noopener" }, "Open claude.ai ↗")),
    h("div", { style: { height: "8px" } }), promptBox,
    h("div", { style: { height: "10px" } }), reply,
    h("div", { class: "row", style: { marginTop: "8px" } },
      h("button", { class: "primary", onclick: async () => {
        try { useScript(await api("POST", `projects/${P().id}/script/parse`, { reply: reply.value })); } catch (e) { toast(e.message, true); }
      } }, "2. Use this reply"),
      S.settings.claude.api_enabled ? h("button", { onclick: async (e) => {
        e.target.disabled = true; e.target.textContent = "Asking Claude…";
        try { useScript(await api("POST", `projects/${P().id}/script/api`, {})); } catch (err) { toast(err.message, true); }
        e.target.disabled = false; e.target.textContent = "Ask Claude API";
      } }, "Ask Claude API") : null)),
    h("div", { class: "panel" },
      h("h3", {}, "Or start from an offline draft"),
      h("p", { class: "hint" }, P().mode === "animated" ? `A ${S.status.motion.templates[P().template]?.name || ""} draft written only from the approved facts.` : "Written only from the approved facts. Edit it to make it yours."),
      h("div", { class: "row" }, P().mode === "animated" ? null : variant, h("button", { onclick: async () => {
        if (P().script.beats.length && !confirm("Replace the current script?")) return;
        useScript(await api("POST", `projects/${P().id}/script/template`, { variant: Number(variant.value) }));
      } }, "Use draft"))),
    h("div", { class: "panel" }, h("h3", {}, "Claim guard"), h("ul", { class: "issues", id: "issues" })));

  // editor
  const sc = P().script;
  const title = h("input", { type: "text", value: sc.title, placeholder: "Title (for your files and the post)" });
  title.oninput = () => { sc.title = title.value; save(); lintSoon(); };
  right.append(h("div", { class: "panel" },
    h("div", { class: "row", style: { justifyContent: "space-between" } }, h("h2", {}, "Script"), h("div", { class: "stats", id: "stats" })),
    field("Title", title),
    h("div", { id: "beats" }),
    P().mode === "ugc" ? null : h("button", { onclick: () => { sc.beats.push({ id: "b" + (sc.beats.length + 1), text: "", visual: { kind: P().mode === "photo_avatar" ? "ugc" : "screen", layout: "face", asset: null, focus: [0.5, 0.5], zoom: 1 }, overlay: "" }); save(); renderProject(); } }, "+ Add beat"),
    h("div", { class: "label" }, "Facts this script relies on"),
    h("div", { class: "chips" }, S.facts.facts.map(f => {
      const on = (sc.facts_used || []).includes(f.id);
      return h("span", { class: "chip" + (on ? " on" : ""), title: f.text + "\nSource: " + f.source, onclick: () => {
        sc.facts_used = on ? sc.facts_used.filter(x => x !== f.id) : [...(sc.facts_used || []), f.id];
        save(); renderProject();
      } }, f.id);
    })),
    sc.beats.length ? h("p", {}, h("button", { class: "primary", onclick: () => { S.tab = "look"; renderProject(); } }, "Next: voice & look")) : null));
  renderBeats();
  renderIssues();
}

function renumber() { P().script.beats.forEach((b, i) => (b.id = "b" + (i + 1))); }

function renderBeats() {
  const wrap = document.getElementById("beats");
  if (!wrap) return;
  wrap.innerHTML = "";
  if (P().mode === "animated") return renderAnimatedBeats(wrap);
  if (P().mode === "ugc" || P().mode === "photo_avatar") return renderPresenterBeats(wrap);
  const sc = P().script;
  const assets = P().assets.filter(a => a.role !== "music");
  sc.beats.forEach((b, i) => {
    b.visual = b.visual || { kind: "screen" };
    const text = h("textarea", { value: b.text, rows: 2 });
    text.oninput = () => { b.text = text.value; save(); lintSoon(); updateStats(); };
    const overlay = h("input", { type: "text", value: b.overlay || "", placeholder: "On-screen headline (optional)" });
    overlay.oninput = () => { b.overlay = overlay.value; save(); lintSoon(); };
    const kind = h("select", { title: "Visual type", onchange: e => { b.visual.kind = e.target.value; save(); renderBeats(); } },
      [["screen", "Insidir demo"], ["image", "Image"], ["presenter", "Presenter"], ["title", "Title card"]].map(([v, t]) => h("option", { value: v, selected: b.visual.kind === v }, t)));
    const asset = h("select", { title: "Footage", onchange: e => { b.visual.asset = e.target.value || null; save(); lintSoon(); renderBeats(); } },
      h("option", { value: "" }, "Auto pick"), assets.map(a => h("option", { value: a.id, selected: b.visual.asset === a.id }, a.label)));
    const chosen = assets.find(a => a.id === b.visual.asset);
    const start = h("input", { type: "number", min: 0, step: 0.5, value: b.visual.start ?? "", placeholder: "start s", title: "Start time in the recording (seconds). Blank = continue where the last beat left off." });
    start.onchange = () => { b.visual.start = start.value === "" ? null : Number(start.value); save(); renderBeats(); };
    const zoom = h("input", { type: "range", min: 1, max: 2.5, step: 0.05, value: b.visual.zoom || 1, title: "Zoom for close shots" });
    zoom.onchange = () => { b.visual.zoom = Number(zoom.value); save(); };
    const focus = h("div", { class: "focus", title: "Click where the close-up shots should aim" });
    if (chosen && chosen.type !== "audio") {
      const t = chosen.type === "video" ? (b.visual.start ?? 0) + 0.5 : 0;
      focus.style.backgroundImage = `url(/api/projects/${P().id}/thumb/${chosen.id}?t=${t})`;
      const f = b.visual.focus || [0.5, 0.5];
      focus.append(h("div", { class: "dot", style: { left: f[0] * 100 + "%", top: f[1] * 100 + "%" } }));
      focus.onclick = e => {
        const r = focus.getBoundingClientRect();
        const ar = chosen.width / chosen.height, br = r.width / r.height;
        let w = r.width, hh = r.height, ox = 0, oy = 0;
        if (ar > br) { hh = r.width / ar; oy = (r.height - hh) / 2; } else { w = r.height * ar; ox = (r.width - w) / 2; }
        const x = Math.min(1, Math.max(0, (e.clientX - r.left - ox) / w)), y = Math.min(1, Math.max(0, (e.clientY - r.top - oy) / hh));
        b.visual.focus = [Math.round(x * 100) / 100, Math.round(y * 100) / 100]; save(); renderBeats();
      };
    } else {
      focus.append(h("div", { class: "empty-note" }, b.visual.kind === "title" ? "Title card" : "Pick footage to set where close-ups aim"));
    }
    const move = (d) => { const j = i + d; if (j < 0 || j >= sc.beats.length) return; [sc.beats[i], sc.beats[j]] = [sc.beats[j], sc.beats[i]]; renumber(); save(); renderBeats(); lintSoon(); };
    wrap.append(h("div", { class: "beat" },
      h("div", { class: "num" }, i === 0 ? "HOOK" : i + 1),
      h("div", {}, text,
        h("div", { class: "opts" }, kind, asset, chosen && chosen.type === "video" ? start : overlay),
        chosen && chosen.type === "video" ? h("div", { style: { marginTop: "8px" } }, overlay) : null,
        b.visual.shot ? h("div", { class: "shot" }, "Shot idea: " + b.visual.shot) : null),
      h("div", { class: "side-tools" }, focus,
        h("div", { class: "row" }, h("span", { class: "hint" }, "close-up zoom"), zoom),
        h("div", { class: "btns" },
          h("button", { class: "small", onclick: () => move(-1), title: "Move up" }, "↑"),
          h("button", { class: "small", onclick: () => move(1), title: "Move down" }, "↓"),
          h("button", { class: "small danger", onclick: () => { sc.beats.splice(i, 1); renumber(); save(); renderBeats(); lintSoon(); }, title: "Delete beat" }, "✕")))));
  });
  if (!sc.beats.length) wrap.append(h("p", { class: "hint" }, "No beats yet. Paste a reply from Claude or use an offline draft."));
  updateStats();
}

function renderAnimatedBeats(wrap) {
  const sc = P().script, m = S.status.motion, tid = P().template;
  const fields = (m.templates[tid] || {}).fields || [];
  const footage = P().assets.filter(a => a.role === "screen" || a.role === "image");
  const sel = (vals, cur, onchange, blank) => h("select", { onchange }, blank ? h("option", { value: "" }, blank) : null,
    vals.map(v => h("option", { value: v, selected: cur === v }, v)));
  sc.beats.forEach((b, i) => {
    b.visual = b.visual || {};
    const v = b.visual;
    const set = (k, val, redraw) => { v[k] = val; save(); lintSoon(); if (redraw) renderBeats(); };
    const text = h("textarea", { value: b.text, rows: 2 });
    text.oninput = () => { b.text = text.value; save(); lintSoon(); updateStats(); };
    const headline = h("input", { type: "text", value: b.overlay || "", placeholder: "Headline drawn on screen (2-5 words)" });
    headline.oninput = () => { b.overlay = headline.value; save(); lintSoon(); };
    const emph = h("input", { type: "text", value: v.emphasis || "", placeholder: "Big figure (approved facts only)" });
    emph.oninput = () => set("emphasis", emph.value);
    const opts = [
      fields.includes("icon") ? field("Doodle", sel(m.icons, v.icon, e => set("icon", e.target.value), "auto")) : null,
      field("Dot figure pose", sel(m.poses, v.pose, e => set("pose", e.target.value), "auto")),
      fields.includes("label") ? field("Card", sel(["MYTH", "FACT"], (v.label || "").toUpperCase(), e => set("label", e.target.value), "no label")) : null,
      fields.includes("emphasis") ? field("Emphasis", emph) : null,
      fields.includes("asset") ? field("Real footage", h("select", { onchange: e => set("asset", e.target.value || null, true) },
        h("option", { value: "" }, "none (draw a doodle)"), footage.map(a => h("option", { value: a.id, selected: v.asset === a.id }, a.label)))) : null,
    ].filter(Boolean);
    const chosen = footage.find(a => a.id === v.asset);
    let focus = null;
    if (chosen && fields.includes("focus")) {
      focus = h("div", { class: "focus", title: "Click what the circle should go around" });
      focus.style.backgroundImage = `url(/api/projects/${P().id}/thumb/${chosen.id}?t=${chosen.type === "video" ? 0.5 : 0})`;
      const f = v.focus || [0.5, 0.5];
      focus.append(h("div", { class: "dot", style: { left: f[0] * 100 + "%", top: f[1] * 100 + "%" } }));
      focus.onclick = e => {
        const r = focus.getBoundingClientRect();
        const ar = chosen.width / chosen.height, br = r.width / r.height;
        let w = r.width, hh = r.height, ox = 0, oy = 0;
        if (ar > br) { hh = r.width / ar; oy = (r.height - hh) / 2; } else { w = r.height * ar; ox = (r.width - w) / 2; }
        set("focus", [Math.round(Math.min(1, Math.max(0, (e.clientX - r.left - ox) / w)) * 100) / 100,
          Math.round(Math.min(1, Math.max(0, (e.clientY - r.top - oy) / hh)) * 100) / 100], true);
      };
    }
    const move = (d) => { const j = i + d; if (j < 0 || j >= sc.beats.length) return; [sc.beats[i], sc.beats[j]] = [sc.beats[j], sc.beats[i]]; renumber(); save(); renderBeats(); lintSoon(); };
    wrap.append(h("div", { class: "beat" },
      h("div", { class: "num" }, i === 0 ? "HOOK" : i + 1),
      h("div", {}, text, h("div", { style: { height: "8px" } }), headline,
        h("div", { class: "aopts" }, opts),
        v.shot ? h("div", { class: "shot" }, "Shot idea: " + v.shot) : null),
      h("div", { class: "side-tools" }, focus,
        h("div", { class: "btns" },
          h("button", { class: "small", onclick: () => move(-1), title: "Move up" }, "↑"),
          h("button", { class: "small", onclick: () => move(1), title: "Move down" }, "↓"),
          h("button", { class: "small danger", onclick: () => { sc.beats.splice(i, 1); renumber(); save(); renderBeats(); lintSoon(); }, title: "Delete beat" }, "✕")))));
  });
  if (!sc.beats.length) wrap.append(h("p", { class: "hint" }, "No beats yet. Paste a reply from Claude or use the offline draft."));
  updateStats();
}

const LAYOUTS = [["face", "Face"], ["split", "Split: app on top"], ["bubble", "Face bubble over app"], ["screen", "App only"]];

function renderPresenterBeats(wrap) {
  const p = P(), sc = p.script, ugcMode = p.mode === "ugc";
  const screens = p.assets.filter(a => a.role === "screen" || a.role === "image");
  const byId = Object.fromEntries(p.assets.map(a => [a.id, a]));
  sc.beats.forEach((b, i) => {
    b.visual = b.visual || {};
    const v = b.visual;
    v.layout = v.layout || "face";
    const redraw = () => { save(); lintSoon(); renderBeats(); };
    const text = h("textarea", { value: b.text, rows: 2 });
    text.oninput = () => { b.text = text.value; save(); lintSoon(); updateStats(); };
    const words = (b.text || "").trim().split(/\s+/).length;
    const fixNote = ugcMode && b.words && words !== b.words.length
      ? h("div", { class: "hint", style: { color: "var(--warn)" } }, `Captions use what you said: keep ${b.words.length} words to fix spellings.`) : null;
    const keep = ugcMode ? h("label", { class: "check" + (b.keep !== false ? " on" : ""), title: "Keep this sentence in the video" },
      h("input", { type: "checkbox", checked: b.keep !== false, onchange: e => { b.keep = e.target.checked; redraw(); } }), "Keep") : null;
    const layout = h("select", { onchange: e => {
      v.layout = e.target.value;
      if (v.layout !== "face" && !v.asset && screens.length) v.asset = screens[0].id;
      redraw();
    } }, LAYOUTS.map(([val, t]) => h("option", { value: val, selected: v.layout === val }, t)));
    const scr = v.layout === "face" ? null : h("select", { onchange: e => { v.asset = e.target.value || null; redraw(); } },
      h("option", { value: "" }, screens.length ? "Pick a screen" : "Upload an Insidir recording first"),
      screens.map(a => h("option", { value: a.id, selected: v.asset === a.id }, a.label)));
    const overlay = h("input", { type: "text", value: b.overlay || "", placeholder: "On-screen headline (optional)" });
    overlay.oninput = () => { b.overlay = overlay.value; save(); lintSoon(); };
    const src = b.source && byId[b.source.asset];
    const chosen = byId[v.asset];
    let side;
    if (v.layout !== "face" && chosen) side = focusPicker(chosen, chosen.type === "video" ? 0.5 : 0, v.focus || [0.5, 0.5], f => { v.focus = f; redraw(); });
    else if (src) side = h("div", { class: "focus", style: { backgroundImage: `url(/api/projects/${p.id}/thumb/${src.id}?t=${(b.source.start + 0.3).toFixed(1)})` } });
    else side = h("div", { class: "focus" }, h("div", { class: "empty-note" }, ugcMode ? "" : "AI presenter"));
    const move = (d) => { const j = i + d; if (j < 0 || j >= sc.beats.length) return; [sc.beats[i], sc.beats[j]] = [sc.beats[j], sc.beats[i]]; renumber(); redraw(); };
    wrap.append(h("div", { class: "ubeat" + (b.keep === false ? " off" : "") },
      h("div", { class: "num" }, i + 1),
      h("div", {},
        ugcMode && b.source ? h("div", { class: "time" }, `${src ? src.label : "clip"} · ${fmtSec(b.source.start)}–${fmtSec(b.source.end)}`) : null,
        text, fixNote,
        h("div", { class: "opts" }, keep, layout, scr),
        h("div", { style: { marginTop: "8px" } }, overlay),
        v.shot ? h("div", { class: "shot" }, "Shot idea: " + v.shot) : null),
      h("div", { class: "side-tools" }, side,
        h("div", { class: "btns" },
          h("button", { class: "small", onclick: () => move(-1), title: "Move up" }, "↑"),
          h("button", { class: "small", onclick: () => move(1), title: "Move down" }, "↓"),
          ugcMode ? null : h("button", { class: "small danger", onclick: () => { sc.beats.splice(i, 1); renumber(); redraw(); }, title: "Delete beat" }, "✕")))));
  });
  if (!sc.beats.length) wrap.append(h("p", { class: "hint" }, ugcMode ? "Nothing yet. Record or upload yourself, then press Transcribe." : "No beats yet. Paste a reply from Claude or use an offline draft."));
  updateStats();
}

function updateStats() {
  const el = document.getElementById("stats");
  if (!el) return;
  const beats = P().script.beats;
  if (P().mode === "ugc") {
    const kept = beats.filter(b => b.keep !== false && b.source);
    const secs = kept.reduce((n, b) => n + (b.source.end - b.source.start) * 0.97, 0) + (P().style.end_card !== false ? 1.8 : 0);
    const ok = secs >= 20 && secs <= 35;
    el.innerHTML = "";
    el.append(h("b", {}, kept.length), ` of ${beats.length} sentences · about `, h("b", { style: { color: ok ? "" : "var(--warn)" } }, fmtSec(secs)), " after cuts");
    return;
  }
  const words = beats.reduce((n, b) => n + (b.text.trim() ? b.text.trim().split(/\s+/).length : 0), 0);
  const speed = P().voice.speed || 1;
  const est = words / (2.35 * speed) + beats.length * 0.32 + 1.8;
  const ok = est >= 20 && est <= 35;
  el.innerHTML = "";
  el.append(h("b", {}, words), " words · about ", h("b", { style: { color: ok ? "" : "var(--warn)" } }, fmtSec(est)), " with end card");
}

function renderIssues() {
  const ul = document.getElementById("issues");
  if (!ul) return;
  ul.innerHTML = "";
  if (!P().script.beats.length) { ul.append(h("li", { class: "warning" }, "No script yet.")); return; }
  if (!S.issues.length) ul.append(h("li", { class: "ok" }, "No problems found. Every figure comes from an approved fact."));
  for (const i of S.issues) ul.append(h("li", { class: i.level }, h("small", {}, i.where), i.message));
}

// ------------------------------------------------------------ 4 look
function tabLook(el) {
  const p = P(), v = p.voice, st = p.style;
  if (!S.voices[v.voice]) v.voice = S.voiceDefaults.man;
  const gender = S.voiceGender[v.voice];
  const voice = h("select", { onchange: e => { v.voice = e.target.value; save(); } },
    Object.entries(S.voices).filter(([id]) => S.voiceGender[id] === gender)
      .map(([id, name]) => h("option", { value: id, selected: v.voice === id }, name)));
  const pick = g => () => { if (gender !== g) { v.voice = S.voiceDefaults[g]; save(); renderProject(); } };
  const genderSwitch = h("div", { class: "seg" },
    h("button", { class: gender === "man" ? "on" : "", onclick: pick("man") }, "Man"),
    h("button", { class: gender === "woman" ? "on" : "", onclick: pick("woman") }, "Woman"));
  const speedLabel = h("b", {}, (v.speed || 1).toFixed(2) + "×");
  const speed = h("input", { type: "range", min: 0.85, max: 1.2, step: 0.01, value: v.speed || 1 });
  speed.oninput = () => { v.speed = Number(speed.value); speedLabel.textContent = v.speed.toFixed(2) + "×"; save(); };
  const sample = h("input", { type: "text", value: p.script.beats[0]?.text || "Insidir shows you what insiders file with the SEC." });
  const audio = h("audio", { controls: true, style: { width: "100%", marginTop: "8px" } });
  const play = h("button", { onclick: async () => {
    play.disabled = true; play.textContent = "Voicing…";
    try { const r = await api("POST", `projects/${p.id}/voice-preview`, { text: sample.value, voice: v.voice, speed: v.speed }); audio.src = r.url; audio.play(); }
    catch (e) { toast(e.message, true); }
    play.disabled = false; play.replaceChildren(ic("voice"), "Preview voice");
  } }, ic("voice"), "Preview voice");
  const color = h("input", { type: "color", value: (!st.caption_highlight || st.caption_highlight.toUpperCase() === "#FFD84D" ? "#FFFFFF" : st.caption_highlight) });
  color.oninput = () => { st.caption_highlight = color.value; save(); };
  const trans = h("select", { onchange: e => { st.transitions = e.target.value; save(); } },
    [["cinematic", "Cinematic: hard cuts + quick transitions when the subject changes"], ["cuts", "Hard cuts only"]].map(([val, t]) => h("option", { value: val, selected: st.transitions === val }, t)));
  const music = p.assets.find(a => a.role === "music");
  const vol = h("input", { type: "range", min: -32, max: -10, step: 1, value: p.music.volume_db });
  vol.onchange = () => { p.music.volume_db = Number(vol.value); save(); };
  const presenter = p.assets.find(a => a.role === "presenter");
  const av = S.status.avatar;
  const chars = S.status.motion.characters || {};
  p.avatar = p.avatar || { character: "dot" };
  p.chat = p.chat || { me: "Insidir", them: "Alex" };
  const chatInput = (k) => { const i = h("input", { type: "text", value: p.chat[k], maxlength: 24 }); i.oninput = () => { p.chat[k] = i.value; save(); }; return i; };
  el.append(
    p.mode === "animated" && p.template === "avatar-host" ? h("div", { class: "panel" }, h("h2", {}, "Host"),
      h("p", { class: "hint" }, "A cartoon character drawn on this PC. Its mouth follows the voice frame by frame; it blinks, nods and gestures on each beat."),
      h("div", { class: "seg" }, Object.entries(chars).map(([id, name]) =>
        h("button", { class: p.avatar.character === id ? "on" : "", onclick: () => { p.avatar.character = id; save(); renderProject(); } }, name)))) : null,
    p.mode === "animated" && p.template === "chat" ? h("div", { class: "panel" }, h("h2", {}, "Chat"),
      h("div", { class: "grid2" }, field("Person asking (THEM)", chatInput("them")), field("Person answering (ME)", chatInput("me"))),
      h("p", { class: "hint" }, "Set each beat's Card to ME or THEM on the Script tab; otherwise they alternate.")) : null,
    p.mode === "ugc" ? h("div", { class: "panel" }, h("h2", {}, "Voice"),
      h("p", { class: "hint" }, "UGC uses your own recorded voice. It is cleaned on this PC: steady background noise removed, EQ, de-essing, compression and -14 LUFS loudness. No AI voice is added.")) : null,
    p.mode === "ugc" ? null : h("div", { class: "panel" }, h("h2", {}, "Voice"),
      h("p", { class: "hint" }, "Kokoro-82M runs on this computer (Apache-2.0, commercial use allowed). Every render is mastered like a voice-over: EQ, de-essing, compression and -14 LUFS loudness. \"Insidir\" is pronounced \"insider\"."),
      field("Narrator", genderSwitch),
      h("div", { class: "grid2" }, field("Kokoro voice", voice), h("label", { class: "field" }, h("span", {}, "Speaking rate"), h("div", { class: "row" }, speed, speedLabel))),
      field("Preview line", sample), play, audio),
    h("div", { class: "panel" }, h("h2", {}, "Look"),
      h("div", { class: "grid2" }, field("Caption highlight", color, "The word being spoken lights up in this colour."),
        p.mode === "animated" ? field("Template", h("div", { class: "hint" }, (S.status.motion.templates[p.template] || {}).name || p.template, " (change it on the Brief tab)")) : field("Cuts", trans)),
      h("div", { class: "grid2" },
        fontPicker(st, "caption_font", "Caption font", false, p.script.beats[0]?.text || "Insiders have to report their trades"),
        fontPicker(st, "headline_font", "Headline font", true, p.script.beats[0]?.overlay || p.script.title || "Insiders file too")),
      field("Caption timing", (() => h("select", { onchange: e => { st.captions = e.target.value; save(); } },
        [["auto", S.status.whisper.installed ? "Automatic: Faster Whisper" : "Automatic: estimated (Faster Whisper not installed)"],
         ["whisper", "Faster Whisper (most accurate)"], ["estimate", "Estimated from the audio (fastest)"]]
          .map(([val, t]) => h("option", { value: val, selected: (st.captions || "auto") === val, disabled: val === "whisper" && !S.status.whisper.installed }, t))))(),
        "Whisper listens to the finished narration and times each caption word to it, on this computer."),
      h("label", { class: "check on" }, h("input", { type: "checkbox", checked: st.end_card !== false, onchange: e => { st.end_card = e.target.checked; save(); } }),
        "End card (1.8 s): Insidir wordmark, line and URL from Facts, with the disclaimer"),
      h("label", { class: "check" + (st.ai_voice_label ? " on" : "") }, h("input", { type: "checkbox", checked: !!st.ai_voice_label, onchange: e => { st.ai_voice_label = e.target.checked; save(); renderProject(); } }),
        "Show an \"AI voice\" label on screen (the post disclosure text always mentions it)"),
      field("Quality", (() => h("select", { onchange: e => { st.quality = e.target.value; save(); } },
        [["high", "High: 60 fps animation, studio encode (slower)"], ["standard", "Standard: 30 fps, faster render"]]
          .map(([val, t]) => h("option", { value: val, selected: (st.quality || "high") === val }, t))))())),
    h("div", { class: "panel" }, h("h2", {}, "Music"),
      music ? h("div", {},
        h("label", { class: "check on" }, h("input", { type: "checkbox", checked: p.music.enabled, onchange: e => { p.music.enabled = e.target.checked; save(); } }), `Use "${music.label}" (ducked under the voice)`),
        h("div", { class: "row" }, h("span", { class: "hint" }, "Music level"), vol),
        music.rights_confirmed ? null : h("div", { class: "notice" }, "Confirm you have a commercial licence for this track on the Footage tab, or it will be left out."))
        : h("p", { class: "hint" }, "Add a track you have a commercial licence for on the Footage tab, or use the studio's own bed below."),
      h("label", { class: "check" + (st.music_bed !== false ? " on" : "") }, h("input", { type: "checkbox", checked: st.music_bed !== false, onchange: e => { st.music_bed = e.target.checked; save(); renderProject(); } }),
        "Original music bed when no track is added: a dark, minimal beat generated on this PC for each video (yours to use, nothing to license)"),
      h("label", { class: "check" + (st.sfx !== false ? " on" : "") }, h("input", { type: "checkbox", checked: st.sfx !== false, onchange: e => { st.sfx = e.target.checked; save(); renderProject(); } }),
        "Sound design: whooshes on cuts, hits on the hook and big numbers, a riser into the end card (also generated on this PC)")),
    h("div", { class: "panel" }, h("h2", {}, "Presenter"),
      presenter ? h("p", {}, `Presenter image: ${presenter.label}${presenter.ai_generated ? " (AI-generated, labelled on screen)" : ""}. Use "Presenter" as the visual type on any beat.`)
        : h("p", { class: "hint" }, "Optional. Upload a presenter photo on the Footage tab and set it to Presenter. Without a talking-avatar model it appears with slow camera motion while the voice plays."),
      h("label", { class: "check" + (p.presenter.use_avatar ? " on" : "") },
        h("input", { type: "checkbox", checked: p.presenter.use_avatar, disabled: !av.usable, onchange: e => { p.presenter.use_avatar = e.target.checked; save(); } }),
        "Animate the presenter with the local talking-avatar model"),
      av.usable ? h("div", { class: "notice ok" }, "Avatar model ready. Avatar shots are always labelled \"AI-generated presenter\".")
        : h("div", { class: "notice" }, "Avatar step unavailable: " + av.reasons.join(" "))),
    h("button", { class: "primary", onclick: () => { S.tab = "render"; renderProject(); } }, "Next: render"));
}

// Font choice with a live preview. The fonts are served by the studio itself (/fonts/...).
function fontPicker(st, key, label, allowDefault, sample) {
  const cat = S.status.fonts || {};
  if (!document.getElementById("font-previews")) {
    document.head.append(h("style", { id: "font-previews" }, Object.entries(cat)
      .map(([id, f]) => `@font-face { font-family: "ivsprev-${id}"; src: url("/fonts/${f.preview}"); }`).join("\n")));
  }
  const cur = st[key] || (allowDefault ? "" : "inter");
  const preview = h("div", { class: "font-preview" }, sample.toUpperCase());
  const paint = (id) => {
    preview.style.fontFamily = id ? `"ivsprev-${id}", sans-serif` : "inherit";
    preview.textContent = id ? sample.toUpperCase() : "Each format keeps its own headline face (Inter, or the hand-drawn face in sketch templates). Screen-demo headlines follow the caption font.";
    preview.classList.toggle("muted", !id);
  };
  const group = (g, title) => h("optgroup", { label: title }, Object.entries(cat).filter(([, f]) => f.group === g)
    .map(([id, f]) => h("option", { value: id, selected: cur === id }, `${f.name} · ${f.note}`)));
  const sel = h("select", { onchange: e => { st[key] = e.target.value; paint(e.target.value); save(); } },
    allowDefault ? h("option", { value: "", selected: !cur }, "Template default") : null,
    group("insidir", "From insidir.com"), group("display", "Display fonts"));
  paint(cur);
  return h("label", { class: "field" }, h("span", {}, label), sel, preview);
}

// ------------------------------------------------------------ 5 render
function tabRender(el) {
  const p = P();
  const errors = S.issues.filter(i => i.level === "error");
  const used = new Set(p.script.beats.map(b => b.visual && b.visual.asset).filter(Boolean));
  const checks = [
    [!!S.status.ffmpeg, "FFmpeg installed"],
    p.mode === "ugc" ? null : [S.status.kokoro.ready, "Kokoro voice model installed"],
    [p.script.beats.length > 0, "Script written"],
    [errors.length === 0, errors.length ? `Claim guard: ${errors.length} problem(s) on the Script tab` : "Claim guard passed"],
    p.mode === "animated"
      ? [S.status.motion.ready, "Motion Canvas installed (Node.js + packages)"]
      : p.mode === "ugc"
        ? [p.assets.some(a => a.role === "creator" && a.rights_confirmed), "A cleared \"Me on camera\" clip"]
        : p.mode === "photo_avatar"
          ? [p.assets.some(a => a.role === "presenter" && a.type === "image" && a.rights_confirmed), "A cleared presenter photo"]
          : [p.assets.some(a => a.rights_confirmed && (a.role === "screen" || a.role === "image")), "At least one cleared demo recording or screenshot"],
    ...(p.mode === "ugc" ? [[S.status.whisper.installed, "Faster Whisper installed"],
      [p.script.beats.some(b => b.keep !== false), "Footage transcribed, at least one sentence kept"]] : []),
    ...(p.mode === "photo_avatar" ? [[S.status.avatar.usable, S.status.avatar.usable ? "Talking-avatar model ready" : "Talking-avatar model: " + S.status.avatar.reasons.join(" ")]] : []),
    ...(p.mode === "animated" && p.template === "screen-sketch"
      ? [[p.assets.some(a => a.rights_confirmed && a.genuine), "At least one cleared, genuine Insidir screenshot or recording"]] : []),
    [p.assets.filter(a => used.has(a.id)).every(a => a.rights_confirmed), "Rights confirmed for every file used"],
  ];
  const ready = checks.filter(Boolean).every(c => c[0]);
  const prog = h("div", { class: "big-progress" }, h("div", {}));
  const msg = h("div", { class: "hint" });
  const log = h("pre", { class: "log", hidden: true });
  const btn = h("button", { class: "primary", disabled: !ready, onclick: () => startRender(btn, prog, msg, log) }, ic("render"), "Render MP4");
  el.append(
    h("div", { class: "panel" }, h("h2", {}, "Ready to render?"),
      h("ul", { class: "issues" }, checks.filter(Boolean).map(([ok, t]) => h("li", { class: ok ? "ok" : "error" }, t))),
      h("div", { style: { height: "12px" } }), btn, prog, msg,
      h("button", { class: "small ghost", onclick: () => (log.hidden = !log.hidden) }, "Show log"), log),
    h("div", { class: "panel" }, h("div", { class: "row", style: { justifyContent: "space-between" } }, h("h2", {}, "Renders"),
      h("button", { class: "small", onclick: () => api("POST", `projects/${p.id}/open-folder`) }, ic("folder"), "Open folder")),
      h("div", { class: "renders", id: "renders" })));
  if (S.job && S.job.project === p.id && ["queued", "running"].includes(S.job.status)) pollJob(btn, prog, msg, log);
  renderRenders();
}

async function startRender(btn, prog, msg, log) {
  btn.disabled = true;
  try { await save(true); S.job = await api("POST", `projects/${P().id}/render`, {}); pollJob(btn, prog, msg, log); }
  catch (e) { toast(e.message, true); btn.disabled = false; }
}

function pollJob(btn, prog, msg, log) {
  btn.disabled = true;
  const tick = async () => {
    try { S.job = await api("GET", "jobs/" + S.job.id); } catch (e) { return; }
    const j = S.job;
    prog.firstChild.style.width = (j.progress * 100).toFixed(0) + "%";
    msg.textContent = j.status === "error" ? "" : j.message;
    log.textContent = j.log.join("\n");
    if (j.status === "done") { toast("Video ready"); btn.disabled = false; await loadProjects(); renderRenders(); return; }
    if (j.status === "error") { btn.disabled = false; msg.innerHTML = ""; msg.append(h("div", { class: "notice" }, j.error)); return; }
    setTimeout(tick, 800);
  };
  tick();
}

async function renderRenders() {
  const el = document.getElementById("renders");
  if (!el) return;
  const info = S.projects.find(x => x.id === P().id);
  el.innerHTML = "";
  const files = (info ? info.renders : []).slice().reverse();
  if (!files.length) { el.append(h("p", { class: "hint" }, "Nothing rendered yet.")); return; }
  for (const f of files) {
    const base = `/api/projects/${P().id}/file/out/`;
    const disc = h("textarea", { rows: 4, readonly: true });
    fetch(base + f.replace(/\.mp4$/, ".txt")).then(r => r.ok ? r.text() : "").then(t => (disc.value = t.trim()));
    el.append(h("div", {},
      h("video", { src: base + f, poster: base + f.replace(/\.mp4$/, ".jpg"), controls: true, preload: "metadata", playsinline: true }),
      h("div", { class: "file" }, f),
      h("div", { class: "row" }, h("a", { class: "btnlink", href: base + f, download: f }, ic("download"), "Download MP4"),
        h("button", { class: "small", onclick: () => { navigator.clipboard.writeText(disc.value.split("\n\n").pop()); toast("Disclosure copied"); } }, ic("copy"), "Copy disclosure")),
      disc));
  }
}

// ------------------------------------------------------------ modals
function openModal(which) {
  const body = document.getElementById("modal-body");
  body.innerHTML = "";
  (which === "facts" ? modalFacts : modalSettings)(body);
  document.getElementById("modal").hidden = false;
}
function closeModal() { document.getElementById("modal").hidden = true; }

function modalFacts(el) {
  const data = JSON.parse(JSON.stringify(S.facts));
  const list = h("div", {});
  const draw = () => {
    list.innerHTML = "";
    data.facts.forEach((f, i) => {
      const inp = (k, ph) => { const x = h("input", { type: "text", value: k === "numbers" ? (f.numbers || []).join(", ") : f[k] || "", placeholder: ph });
        x.oninput = () => { f[k] = k === "numbers" ? x.value.split(",").map(s => s.trim()).filter(Boolean) : x.value; }; return x; };
      const txt = h("textarea", { rows: 2, value: f.text }); txt.oninput = () => (f.text = txt.value);
      list.append(h("div", { class: "fact" },
        h("div", { class: "grid2" }, field("Id", inp("id", "short_id")), field("Numbers it allows", inp("numbers", "e.g. 3, three, $1"))),
        field("Claim", txt), field("Source you can show", inp("source", "URL or document")),
        h("button", { class: "small danger", onclick: () => { data.facts.splice(i, 1); draw(); } }, "Remove")));
    });
  };
  draw();
  const disc = h("input", { type: "text", value: data.disclaimer || "" }); disc.oninput = () => (data.disclaimer = disc.value);
  data.end_card = data.end_card || {};
  const ec = (k) => { const x = h("input", { type: "text", value: data.end_card[k] || "" }); x.oninput = () => (data.end_card[k] = x.value); return x; };
  el.append(h("h2", {}, "Approved facts"),
    h("p", { class: "hint" }, "Scripts may only state numbers and product claims listed here. Every fact needs a source. Check pricing and features before each campaign."),
    list,
    h("button", { onclick: () => { data.facts.push({ id: "", text: "", source: "", numbers: [] }); draw(); } }, "+ Add fact"),
    h("div", { class: "label" }, "Disclaimer and end card"),
    field("Disclaimer (always shown on the last beat and end card)", disc),
    h("div", { class: "grid3" }, field("Headline", ec("headline")), field("Line", ec("line")), field("URL", ec("url"))),
    h("button", { class: "primary", onclick: async () => {
      try { S.facts = await api("PUT", "facts", data); toast("Facts saved"); closeModal(); if (P()) { lintSoon(0); renderProject(); } }
      catch (e) { toast(e.message, true); }
    } }, "Save facts"));
}

function modalSettings(el) {
  const s = JSON.parse(JSON.stringify(S.settings));
  const av = s.avatar, cl = s.claude;
  const engines = S.status.avatar.engines;
  const note = h("div", { class: "notice" });
  const showNote = () => { const e = engines[av.engine]; note.textContent = e ? `${e.name}: ${e.note}${e.url ? " " + e.url : ""}` : "Pick the engine you installed."; };
  showNote();
  const t = (obj, k, ph, type = "text") => { const x = h("input", { type, value: obj[k] ?? "", placeholder: ph }); x.oninput = () => (obj[k] = type === "number" ? Number(x.value) : x.value); return x; };
  const c = (obj, k, text) => h("label", { class: "check" }, h("input", { type: "checkbox", checked: obj[k], onchange: e => (obj[k] = e.target.checked) }), text);
  const gpus = S.status.avatar.gpus;
  el.append(h("h2", {}, "Settings"),
    h("div", { class: "panel" }, h("h3", {}, "Claude"),
      h("p", { class: "hint" }, "The free way is copy and paste with claude.ai. If you already pay for an Anthropic API key you can let the studio send the prompt directly; API calls are billed by Anthropic."),
      c(cl, "api_enabled", "Use the Claude API (optional, paid by your API account)"),
      h("div", { class: "grid2" }, field("API key (stored only on this computer)", t(cl, "api_key", "sk-ant-…", "password")), field("Model", t(cl, "model", "claude-opus-5-5")))),
    h("div", { class: "panel" }, h("h3", {}, "Talking avatar (optional)"),
      h("p", { class: "hint" }, `GPU: ${gpus.length ? gpus.map(g => `${g.name} (${g.vram_gb} GB)`).join(", ") : "none detected"}. Install a model yourself, check its licence and the licence of every weight file it downloads, then give the command the studio should run. Placeholders: {image} {audio} {output} {outdir}.`),
      c(av, "enabled", "Enable the avatar step"),
      field("Engine", (() => { const x = h("select", { onchange: e => { av.engine = e.target.value; showNote(); } },
        h("option", { value: "" }, "—"), Object.entries(engines).map(([id, e]) => h("option", { value: id, selected: av.engine === id }, e.name + (e.commercial === "no" ? " (non-commercial)" : "")))); return x; })()),
      note,
      field("Command", t(av, "command", 'python inference.py --source_image "{image}" --driven_audio "{audio}" --result_dir "{outdir}"')),
      h("div", { class: "grid2" }, field("Working folder", t(av, "workdir", "C:\\AI\\SadTalker")), field("Minimum GPU memory (GB)", t(av, "min_vram_gb", "8", "number"))),
      c(av, "commercial_use", "These videos are for commercial use (blocks engines that forbid it)"),
      c(av, "license_confirmed", "I checked the licence of this model, its code and all its weights, and it allows this use")),
    h("div", { class: "panel" }, h("h3", {}, "Defaults for new videos"),
      h("div", { class: "grid2" },
        field("Voice", (() => h("select", { onchange: e => (s.voice = e.target.value) }, Object.entries(S.voices).map(([id, n]) => h("option", { value: id, selected: s.voice === id }, (S.voiceGender[id] === "man" ? "Man · " : "Woman · ") + n))))()),
        field("Caption highlight", (() => { const x = h("input", { type: "color", value: s.caption_highlight }); x.oninput = () => (s.caption_highlight = x.value); return x; })()))),
    h("p", { class: "hint" }, "Projects and models live in " + S.status.home),
    h("button", { class: "primary", onclick: async () => {
      try { S.settings = await api("PUT", "settings", s); S.status = await api("GET", "status"); renderPills(); toast("Settings saved"); closeModal(); if (P()) renderProject(); }
      catch (e) { toast(e.message, true); }
    } }, "Save settings"));
}

boot();
