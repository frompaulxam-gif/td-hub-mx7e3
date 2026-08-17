/* TDG Hub app */
(() => {
"use strict";

const $ = (s, el) => (el || document).querySelector(s);
const $$ = (s, el) => Array.from((el || document).querySelectorAll(s));

const state = {
  live: false,
  venue: localStorage.getItem("hub-venue") || "merchants-yard",
  venues: [],
  weeks: {},          // venue -> [week objects]
  weekIdx: {},        // venue -> current index
  view: "board",
  focusList: [],
  focusIdx: -1,
};

const DONE = new Set(["approved", "posted"]);
const STATUS_LABEL = { waiting: "waiting on info", draft: "draft", ready: "ready", approved: "approved", changes: "needs changes", posted: "posted" };

/* ---------- data ---------- */

async function boot() {
  try {
    const r = await fetch("/api/venues", { signal: AbortSignal.timeout(1500) });
    if (!r.ok) throw 0;
    const j = await r.json();
    state.live = true;
    state.venues = j.venues;
    await Promise.all(state.venues.map(async v => {
      const w = await (await fetch("/api/weeks?venue=" + v.slug)).json();
      state.weeks[v.slug] = w.weeks || [];
    }));
  } catch {
    state.live = false;
    $("#ro-pill").hidden = false;
    const m = await (await fetch("data/manifest.json")).json();
    state.venues = m.venues;
    await Promise.all(m.venues.map(async v => {
      state.weeks[v.slug] = await Promise.all(
        v.weeks.map(async wk => (await fetch(`data/${v.slug}/${wk}.json`)).json()));
    }));
  }
  for (const v of state.venues) {
    const ws = state.weeks[v.slug] || [];
    let idx = ws.length - 1;
    const cur = ws.findIndex(w => !w.archived);
    if (cur >= 0) idx = cur;
    state.weekIdx[v.slug] = idx;
  }
  if (!state.weeks[state.venue]) state.venue = state.venues[0]?.slug;
  document.documentElement.dataset.venue = state.venue;
  render();
}

function curWeek() {
  const ws = state.weeks[state.venue] || [];
  return ws[state.weekIdx[state.venue]] || null;
}

function mediaUrl(week, path, slot) {
  const base = state.live ? "/media/" : "media/";
  const v = state.live && slot?._v ? "?v=" + slot._v : "";
  return base + state.venue + "/" + week.week_start + "/" + path.split("/").map(encodeURIComponent).join("/") + v;
}

async function patchSlot(slot, payload, quiet) {
  if (!state.live) { toast("Read-only snapshot, changes not saved"); return false; }
  const week = curWeek();
  try {
    const r = await fetch("/api/slot", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ venue: state.venue, week_start: week.week_start, id: slot.id, ...payload }),
    });
    const j = await r.json();
    if (!r.ok || !j.ok) throw new Error(j.error || "save failed");
    Object.assign(slot, j.slot);
    if (!quiet) toast("Saved");
    return true;
  } catch (e) {
    toast("Save failed: " + e.message);
    return false;
  }
}

/* ---------- rendering ---------- */

function render() {
  renderWeekBar();
  renderKeyDates();
  renderBoard();
  renderCalendar();
  const week = curWeek();
  $("#board").hidden = state.view !== "board" || !week;
  $("#calendar").hidden = state.view !== "calendar" || !week;
  $("#empty").hidden = !!week;
  if (!week) $("#empty-text").textContent =
    "No weeks for this venue yet. A new session will scaffold one when you paste the week's info.";
  $$(".view-btn").forEach(b => b.classList.toggle("is-on", b.dataset.viewBtn === state.view));
}

function renderWeekBar() {
  const ws = state.weeks[state.venue] || [];
  const idx = state.weekIdx[state.venue] ?? -1;
  const week = ws[idx];
  $("#week-label").textContent = week ? week.label || week.week_start : "No weeks yet";
  $("#week-prev").disabled = idx <= 0;
  $("#week-next").disabled = idx >= ws.length - 1;
  if (week) {
    const total = week.slots.length;
    const cleared = week.slots.filter(s => DONE.has(s.status)).length;
    $("#week-progress").textContent = `${cleared} of ${total} cleared`;
  } else {
    $("#week-progress").textContent = "";
  }
}

function renderKeyDates() {
  const week = curWeek();
  const el = $("#keydates");
  const dates = week?.key_dates || [];
  el.hidden = !dates.length;
  el.innerHTML = "";
  for (const d of dates) {
    const chip = document.createElement("span");
    chip.className = "keydate";
    chip.textContent = d;
    el.appendChild(chip);
  }
}

function groupSlots(week) {
  const groups = [];
  const byDay = new Map();
  for (const s of week.slots) {
    const key = s.day || s.date;
    if (!byDay.has(key)) { byDay.set(key, []); groups.push({ key, date: s.date, slots: byDay.get(key) }); }
    byDay.get(key).push(s);
  }
  for (const g of groups) g.slots.sort((a, b) => (a.kind === b.kind ? 0 : a.kind === "grid" ? -1 : 1));
  return groups;
}

function fmtDate(iso) {
  if (!iso) return "";
  const d = new Date(iso + "T12:00:00");
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}
const todayIso = () => new Date().toLocaleDateString("sv-SE");

function renderBoard() {
  const week = curWeek();
  const board = $("#board");
  board.innerHTML = "";
  if (!week) return;
  state.focusList = [];
  const today = todayIso();
  let i = 0;
  for (const g of groupSlots(week)) {
    const sec = document.createElement("section");
    sec.className = "day-section";
    const head = document.createElement("div");
    head.className = "day-head";
    head.innerHTML = `<span class="day-name"></span><span class="day-date"></span>`;
    $(".day-name", head).textContent = g.key;
    $(".day-date", head).textContent = g.key.toLowerCase().includes("any") ? "post any day" : fmtDate(g.date);
    if (g.date === today && !g.key.toLowerCase().includes("any")) {
      const t = document.createElement("span");
      t.className = "today-chip"; t.textContent = "Today";
      head.appendChild(t);
    }
    sec.appendChild(head);
    const cards = document.createElement("div");
    cards.className = "cards";
    for (const s of g.slots) {
      const idx = state.focusList.length;
      state.focusList.push(s);
      cards.appendChild(makeCard(week, s, idx, i++));
    }
    sec.appendChild(cards);
    board.appendChild(sec);
  }
}

function makeCard(week, s, focusIdx, animIdx) {
  const card = document.createElement("button");
  card.className = "card" + (DONE.has(s.status) ? " is-done" : "");
  if (document.hidden) card.style.animation = "none";
  else card.style.animationDelay = Math.min(animIdx * 28, 400) + "ms";
  card.addEventListener("click", () => openFocus(focusIdx));

  const thumb = makeThumb(week, s);
  card.appendChild(thumb);

  const main = document.createElement("div");
  main.className = "card-main";
  const slotLabel = document.createElement("div");
  slotLabel.className = "slot-label";
  const kind = document.createElement("span");
  kind.className = "kind-tag";
  kind.textContent = s.kind === "grid" ? "Grid" : "Story";
  slotLabel.appendChild(kind);
  slotLabel.appendChild(document.createTextNode(s.slot || ""));
  const title = document.createElement("div");
  title.className = "card-title";
  title.textContent = s.title || s.slot;
  const cap = document.createElement("div");
  cap.className = "card-cap";
  cap.textContent = s.caption || "";
  const foot = document.createElement("div");
  foot.className = "card-foot";
  const chip = document.createElement("span");
  chip.className = "chip " + s.status;
  chip.textContent = STATUS_LABEL[s.status] || s.status;
  foot.appendChild(chip);
  if (s.checklist?.length) {
    const m = document.createElement("span");
    m.className = "meta-note";
    m.textContent = s.checklist.length + " to-do" + (s.checklist.length > 1 ? "s" : "");
    foot.appendChild(m);
  }
  if (s.notes?.length) {
    const m = document.createElement("span");
    m.className = "meta-note";
    m.textContent = s.notes.length + " note" + (s.notes.length > 1 ? "s" : "");
    foot.appendChild(m);
  }
  main.append(slotLabel, title, cap, foot);
  card.appendChild(main);
  return card;
}

function makeThumb(week, s) {
  const first = s.media?.[0];
  if (!first) {
    const d = document.createElement("div");
    d.className = "thumb is-empty";
    d.textContent = s.media_kind === "none" ? "action" : "no file";
    return d;
  }
  if (/\.(mp4|mov|m4v|webm)$/i.test(first)) {
    const v = document.createElement("video");
    v.className = "thumb";
    v.src = mediaUrl(week, first) + "#t=0.5";
    v.muted = true; v.playsInline = true; v.preload = "metadata";
    return v;
  }
  const img = document.createElement("img");
  img.className = "thumb";
  img.loading = "lazy";
  img.src = mediaUrl(week, first);
  img.alt = "";
  return img;
}

/* ---------- calendar ---------- */

function renderCalendar() {
  const week = curWeek();
  const cal = $("#calendar");
  cal.innerHTML = "";
  if (!week) return;
  const head = document.createElement("div");
  head.className = "cal-row cal-head-row";
  head.innerHTML = "<div></div><div>Grid</div><div>IG Story</div>";
  cal.appendChild(head);
  const today = todayIso();
  for (const g of groupSlots(week)) {
    const row = document.createElement("div");
    row.className = "cal-row" + (g.date === today && !g.key.toLowerCase().includes("any") ? " is-today" : "");
    const day = document.createElement("div");
    day.className = "cal-day";
    day.innerHTML = `${g.key}<small></small>`;
    $("small", day).textContent = g.key.toLowerCase().includes("any") ? "any day" : fmtDate(g.date);
    row.appendChild(day);
    for (const kind of ["grid", "story"]) {
      const cell = document.createElement("div");
      cell.className = "cal-cell" + (kind === "story" ? " cal-cell-story" : "");
      const items = g.slots.filter(s => s.kind === kind);
      if (!items.length) {
        const off = document.createElement("span");
        off.className = "cal-off";
        off.textContent = kind === "grid" ? "Grid off" : "no story slot";
        cell.appendChild(off);
      }
      for (const s of items) {
        const idx = state.focusList.indexOf(s);
        const it = document.createElement("button");
        it.className = "cal-item" + (DONE.has(s.status) ? " is-done" : "");
        const dot = document.createElement("span");
        dot.className = "dot " + s.status;
        it.appendChild(dot);
        it.appendChild(document.createTextNode(s.title || s.slot));
        it.addEventListener("click", () => openFocus(idx));
        cell.appendChild(it);
      }
      row.appendChild(cell);
    }
    cal.appendChild(row);
  }
}

/* ---------- focus mode ---------- */

function openFocus(idx) {
  if (idx < 0 || idx >= state.focusList.length) return;
  state.focusIdx = idx;
  const f = $("#focus");
  f.hidden = false;
  requestAnimationFrame(() => f.classList.add("is-open"));
  fillFocus();
  document.body.style.overflow = "hidden";
}

function closeFocus() {
  const f = $("#focus");
  f.classList.remove("is-open");
  setTimeout(() => { f.hidden = true; }, 280);
  document.body.style.overflow = "";
  state.focusIdx = -1;
  renderBoard(); renderCalendar(); renderWeekBar();
}

function fillFocus() {
  const week = curWeek();
  const s = state.focusList[state.focusIdx];
  if (!s) return;
  $(".focus-scroll").scrollTop = 0;
  $("#focus-slotname").textContent = s.title || s.slot;
  $("#focus-daytag").textContent =
    `${s.day}${s.day !== s.slot ? " · " + s.slot : ""} · ${s.kind === "grid" ? "grid post" : "story"}`;
  $("#focus-prev").disabled = state.focusIdx <= 0;
  $("#focus-next").disabled = state.focusIdx >= state.focusList.length - 1;

  // media
  const m = $("#focus-media");
  m.innerHTML = "";
  if (!s.media?.length) {
    const p = document.createElement("div");
    p.className = "placeholder";
    p.textContent = s.media_kind === "none"
      ? "No file needed, this one is an action on the day."
      : "Nothing here yet. " + (s.checklist?.[0] || "");
    m.appendChild(p);
  } else if (s.media.length > 1) {
    const strip = document.createElement("div");
    strip.className = "carousel";
    for (const path of s.media) {
      const img = document.createElement("img");
      img.loading = "lazy";
      img.src = mediaUrl(week, path, s);
      img.alt = "";
      strip.appendChild(img);
    }
    m.appendChild(strip);
    const dots = document.createElement("div");
    dots.className = "car-dots";
    s.media.forEach((_, i) => {
      const d = document.createElement("span");
      d.className = "car-dot" + (i === 0 ? " is-on" : "");
      dots.appendChild(d);
    });
    m.appendChild(dots);
    strip.addEventListener("scroll", () => {
      const i = Math.round(strip.scrollLeft / strip.clientWidth);
      $$(".car-dot", dots).forEach((d, j) => d.classList.toggle("is-on", j === i));
    }, { passive: true });
  } else {
    const path = s.media[0];
    if (/\.(mp4|mov|m4v|webm)$/i.test(path)) {
      const v = document.createElement("video");
      v.src = mediaUrl(week, path, s);
      v.controls = true; v.playsInline = true; v.preload = "metadata";
      m.appendChild(v);
    } else {
      const img = document.createElement("img");
      img.src = mediaUrl(week, path, s);
      img.alt = "";
      m.appendChild(img);
    }
  }

  // caption
  const cap = $("#caption-edit");
  cap.textContent = s.caption || "";
  cap.contentEditable = state.live ? "plaintext-only" : "false";

  // alternates
  $("#alternates-wrap").hidden = !s.alternates?.length;
  const chips = $("#alt-chips");
  chips.innerHTML = "";
  (s.alternates || []).forEach((alt, i) => {
    const b = document.createElement("button");
    b.className = "alt-chip";
    b.textContent = alt;
    b.addEventListener("click", async () => {
      const old = s.caption;
      const alts = s.alternates.slice();
      alts[i] = old;
      if (await patchSlot(s, { set: { caption: alt, alternates: alts.filter(Boolean) } })) fillFocus();
    });
    chips.appendChild(b);
  });

  // checklist
  $("#checklist-wrap").hidden = !s.checklist?.length;
  const cl = $("#checklist");
  cl.innerHTML = "";
  (s.checklist || []).forEach(item => {
    const li = document.createElement("li");
    li.textContent = item;
    cl.appendChild(li);
  });

  // notes
  const notes = $("#notes");
  notes.innerHTML = "";
  (s.notes || []).forEach(n => {
    const li = document.createElement("li");
    const b = document.createElement("b");
    b.textContent = n.ts + " ";
    li.appendChild(b);
    li.appendChild(document.createTextNode(n.text));
    notes.appendChild(li);
  });
  $("#note-input").value = "";

  // layout editor availability
  $("#editor-open").hidden = !(state.live && s.template?.content && s.template?.out);

  // actions
  const approved = s.status === "approved" || s.status === "posted";
  $("#act-approve").textContent = approved ? "Approved ✓" : "Approve";
  $("#act-approve").style.opacity = approved ? .7 : 1;
  $("#act-posted").hidden = !(s.status === "approved" || s.status === "posted");
  $("#act-posted").textContent = s.status === "posted" ? "Posted ✓" : "Mark posted";
  $("#focus-actions").style.display = state.live ? "" : "none";
}

function focusStep(delta) {
  const next = state.focusIdx + delta;
  if (next < 0 || next >= state.focusList.length) return;
  state.focusIdx = next;
  fillFocus();
}

async function saveCaption() {
  const s = state.focusList[state.focusIdx];
  if (!s || !state.live) return;
  const text = $("#caption-edit").innerText.replace(/\n{3,}/g, "\n\n").trimEnd();
  if (text === (s.caption || "")) return;
  if (await patchSlot(s, { set: { caption: text } }, true)) toast("Caption saved");
}

/* ---------- events ---------- */

$$(".venue-btn").forEach(b => b.addEventListener("click", () => {
  if (state.venue === b.dataset.venueBtn) return;
  state.venue = b.dataset.venueBtn;
  localStorage.setItem("hub-venue", state.venue);
  document.documentElement.dataset.venue = state.venue;
  render();
}));

$$(".view-btn").forEach(b => b.addEventListener("click", () => {
  state.view = b.dataset.viewBtn;
  render();
}));

$("#week-prev").addEventListener("click", () => { state.weekIdx[state.venue]--; render(); });
$("#week-next").addEventListener("click", () => { state.weekIdx[state.venue]++; render(); });

$("#focus-close").addEventListener("click", closeFocus);
$("#focus").addEventListener("click", e => { if (e.target === $("#focus")) closeFocus(); });
$("#focus-prev").addEventListener("click", () => focusStep(-1));
$("#focus-next").addEventListener("click", () => focusStep(1));

$("#caption-edit").addEventListener("blur", saveCaption);
$("#caption-edit").addEventListener("keydown", e => {
  if ((e.metaKey || e.ctrlKey) && e.key === "Enter") e.target.blur();
});

$("#copy-caption").addEventListener("click", async () => {
  const s = state.focusList[state.focusIdx];
  await navigator.clipboard.writeText($("#caption-edit").innerText);
  toast("Caption copied");
});

$("#note-add").addEventListener("click", addNote);
$("#note-input").addEventListener("keydown", e => { if (e.key === "Enter") addNote(); });
async function addNote() {
  const s = state.focusList[state.focusIdx];
  const text = $("#note-input").value.trim();
  if (!s || !text) return;
  if (await patchSlot(s, { add_note: { text } })) fillFocus();
}

$("#act-approve").addEventListener("click", async () => {
  const s = state.focusList[state.focusIdx];
  if (!s) return;
  const to = DONE.has(s.status) ? "ready" : "approved";
  if (await patchSlot(s, { set: { status: to } }, true)) {
    toast(to === "approved" ? "Approved" : "Back to ready");
    fillFocus();
    if (to === "approved") setTimeout(() => {
      const nxt = state.focusList.findIndex((x, i) => i > state.focusIdx && !DONE.has(x.status));
      if (nxt >= 0) { state.focusIdx = nxt; fillFocus(); } else closeFocus();
    }, 420);
  }
});

$("#act-changes").addEventListener("click", async () => {
  const s = state.focusList[state.focusIdx];
  if (!s) return;
  const note = $("#note-input").value.trim();
  const payload = { set: { status: "changes" } };
  if (note) payload.add_note = { text: note };
  if (await patchSlot(s, payload, true)) {
    toast(note ? "Flagged with note" : "Flagged, add a note so the next session knows why");
    fillFocus();
  }
});

$("#act-posted").addEventListener("click", async () => {
  const s = state.focusList[state.focusIdx];
  if (!s) return;
  const to = s.status === "posted" ? "approved" : "posted";
  if (await patchSlot(s, { set: { status: to } }, true)) { toast(to === "posted" ? "Marked posted" : "Back to approved"); fillFocus(); }
});

document.addEventListener("keydown", e => {
  if ($("#focus").hidden) return;
  if (e.key === "Escape") { e.target.blur?.(); closeFocus(); }
  if (e.target.closest?.("[contenteditable], input")) return;
  if (e.key === "ArrowLeft") focusStep(-1);
  if (e.key === "ArrowRight") focusStep(1);
});

let touchX = null, touchY = null;
$("#focus").addEventListener("touchstart", e => {
  touchX = e.touches[0].clientX; touchY = e.touches[0].clientY;
}, { passive: true });
$("#focus").addEventListener("touchend", e => {
  if (touchX == null) return;
  const dx = e.changedTouches[0].clientX - touchX;
  const dy = e.changedTouches[0].clientY - touchY;
  if (Math.abs(dx) > 70 && Math.abs(dx) > Math.abs(dy) * 1.6 && !e.target.closest(".carousel"))
    focusStep(dx < 0 ? 1 : -1);
  touchX = null;
}, { passive: true });

/* ---------- layout editor ---------- */

const ed = { layout: null, content: null, slot: null, scale: 1, sel: null };

const ED_FONTS = [
  "", "Poppins", "Poppins SemiBold", "Bodoni 72", "Snell Roundhand",
  "Barlow Semi Condensed", "Playfair Display", "Helvetica Neue",
];

$("#editor-open").addEventListener("click", openEditor);
$("#editor-cancel").addEventListener("click", () => { $("#editor").hidden = true; });
$("#size-down").addEventListener("click", () => bumpSize(-2));
$("#size-up").addEventListener("click", () => bumpSize(2));
$("#width-down").addEventListener("click", () => bumpWidth(-20));
$("#width-up").addEventListener("click", () => bumpWidth(20));
$("#font-select").addEventListener("change", e => {
  if (!ed.sel) return;
  if (e.target.value) ed.sel.font = e.target.value;
  else delete ed.sel.font;
  const el = $(`.ed-block[data-id="${ed.sel.id}"]`);
  if (el) styleEdBlock(el, ed.sel);
});
$("#editor-save").addEventListener("click", saveEditor);

async function openEditor() {
  const s = state.focusList[state.focusIdx];
  const week = curWeek();
  if (!s?.template) return;
  try {
    const r = await fetch(`/api/template?venue=${state.venue}&week=${week.week_start}&id=${s.id}`);
    const j = await r.json();
    if (!j.layout) throw new Error(j.error || "no layout");
    ed.layout = j.layout; ed.content = j.content || {}; ed.slot = s; ed.sel = null;
    $("#editor").hidden = false;
    $("#editor-size").hidden = true;
    buildEditorStage();
  } catch (e) { toast("Editor failed: " + e.message); }
}

function edText(id) {
  const c = ed.content;
  if (id === "acts") return (c.acts || []).map(a => a.time ? a.time + "  ·  " + a.name : a.name).join("\n");
  const v = c[id];
  return Array.isArray(v) ? v.join("\n") : (v ?? "");
}

function buildEditorStage() {
  const stage = $("#editor-stage");
  stage.innerHTML = "";
  const W = ed.layout.width || 1080, H = ed.layout.height || 1920;
  const wrap = $(".editor-stage-wrap");
  let scale = Math.min((wrap.clientWidth - 20) / W, (wrap.clientHeight - 20) / H);
  if (!isFinite(scale) || scale <= 0.05) scale = 0.35;
  ed.scale = scale;
  stage.style.width = W * scale + "px";
  stage.style.height = H * scale + "px";
  const week = curWeek();
  const bgPath = ed.slot.media?.[0] || ed.slot.template.out;
  stage.style.backgroundImage = `url("${mediaUrl(week, bgPath)}?v=${ed.slot._v || 0}")`;
  for (const b of ed.layout.blocks || []) {
    const t = edText(b.id);
    if (!t) continue;
    const el = document.createElement("div");
    el.className = "ed-block";
    el.dataset.id = b.id;
    el.textContent = t;
    styleEdBlock(el, b);
    stage.appendChild(el);
    attachDrag(el, b);
  }
}

function styleEdBlock(el, b) {
  const k = ed.scale;
  Object.assign(el.style, {
    left: b.x * k + "px",
    top: b.y * k + "px",
    width: b.w * k + "px",
    fontSize: b.size * k + "px",
    fontWeight: b.weight || 700,
    fontFamily: b.font ? `"${b.font}", Poppins, sans-serif` : "",
    textAlign: b.align || "center",
    lineHeight: String(b.lineHeight || 1.28),
    letterSpacing: (b.letterSpacing || 0) + "em",
    textTransform: b.uppercase === false ? "none" : "uppercase",
    color: b.color || "#f5e9b3",
  });
}

function bumpWidth(d) {
  if (!ed.sel) return;
  ed.sel.w = Math.max(80, Math.min((ed.layout.width || 1080), ed.sel.w + d));
  const el = $(`.ed-block[data-id="${ed.sel.id}"]`);
  if (el) styleEdBlock(el, ed.sel);
}

function attachDrag(el, b) {
  el.addEventListener("pointerdown", e => {
    e.preventDefault();
    el.setPointerCapture(e.pointerId);
    selectBlock(el, b);
    const startX = e.clientX, startY = e.clientY, ox = b.x, oy = b.y;
    const move = ev => {
      b.x = Math.round(ox + (ev.clientX - startX) / ed.scale);
      b.y = Math.round(oy + (ev.clientY - startY) / ed.scale);
      styleEdBlock(el, b);
    };
    const up = () => {
      el.removeEventListener("pointermove", move);
      el.removeEventListener("pointerup", up);
    };
    el.addEventListener("pointermove", move);
    el.addEventListener("pointerup", up);
  });
}

function selectBlock(el, b) {
  $$(".ed-block").forEach(x => x.classList.remove("is-sel"));
  el.classList.add("is-sel");
  ed.sel = b;
  $("#editor-size").hidden = false;
  $("#size-val").textContent = b.size + "px";
  const sel = $("#font-select");
  if (!sel.options.length)
    for (const f of ED_FONTS) {
      const o = document.createElement("option");
      o.value = f;
      o.textContent = f || "Template font";
      sel.appendChild(o);
    }
  sel.value = ED_FONTS.includes(b.font) ? b.font : "";
}

function bumpSize(d) {
  if (!ed.sel) return;
  ed.sel.size = Math.max(12, ed.sel.size + d);
  $("#size-val").textContent = ed.sel.size + "px";
  const el = $(`.ed-block[data-id="${ed.sel.id}"]`);
  if (el) styleEdBlock(el, ed.sel);
}

async function saveEditor() {
  const s = ed.slot, week = curWeek();
  $("#editor-save").textContent = "Rendering…";
  try {
    const r = await fetch("/api/render", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ venue: state.venue, week_start: week.week_start, id: s.id, layout: ed.layout }),
    });
    const j = await r.json();
    if (!j.ok) throw new Error(j.error || "render failed");
    s._v = Date.now();
    $("#editor").hidden = true;
    toast("Re-rendered");
    fillFocus();
  } catch (e) {
    toast("Render failed: " + e.message);
  } finally {
    $("#editor-save").textContent = "Save & re-render";
  }
}

window.addEventListener("resize", () => {
  if (!$("#editor").hidden && ed.layout) buildEditorStage();
});

let toastTimer;
function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.add("is-on");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove("is-on"), 2200);
}

boot();
})();
