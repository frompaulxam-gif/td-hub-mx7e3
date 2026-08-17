/* TDG Hub app */
(() => {
"use strict";

const $ = (s, el) => (el || document).querySelector(s);
const $$ = (s, el) => Array.from((el || document).querySelectorAll(s));

const state = {
  live: false,
  venue: localStorage.getItem("hub-venue") || "merchants-yard",
  venues: [],
  weeks: {},
  weekIdx: {},
  view: "board",
};

const DONE = new Set(["approved", "posted"]);
const REACTIVE_MENU = [
  { name: "Poll question", prompt: "QUESTION BOX or poll sticker. A real decision: Sax or DJ this Saturday? Spritz or pint first?" },
  { name: "Clip of the vibe", prompt: "One clip that shows what it feels like: room mid-song, table mid-laugh, the pour. Raw is fine." },
  { name: "Weather check", prompt: "Weather sticker over a yard clip. Sun's out: you know where to be. Grey: the forecast says Friday's fine, book anyway." },
  { name: "Updates", prompt: "This week's acts, new drink on the bar, food truck this weekend, anything Chelsea flags." },
  { name: "DJ / music", prompt: "Clip of the decks or sax. Who's on this Friday name-drop, or guess-the-song from a 2 second clip." },
  { name: "Whole space", prompt: "Slow pan of the empty yard in the morning, festoon lights coming on, overhead at peak. The room is the star." },
  { name: "Drinks", prompt: "The pour, the garnish, the frozen tap, condensation macro. One drink per story, no menus." },
  { name: "Funny caption", prompt: "A normal clip with the caption doing the work: the table that said one drink, an hour ago." },
  { name: "Clips as-is", prompt: "Anything real from the camera roll, posted raw. No edit, no caption if it doesn't need one." },
  { name: "Behind the scenes", prompt: "Setup before doors, keg change, chalkboard being written, sound check. The venue waking up." },
  { name: "Booking nudge", prompt: "Booking-link sticker over a busy clip. Friday tables going, midweek." },
  { name: "People / UGC", prompt: "Reshare every tag and mention, repost customer stories, staff intro when someone new starts." },
  { name: "Countdown", prompt: "Countdown sticker to Friday doors, PL fixtures, bank holiday Sunday, season close weekend." },
];
const STATUS_LABEL = { waiting: "waiting on info", draft: "draft", ready: "ready for QC", approved: "approved", changes: "changes asked", posted: "✓ posted" };

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
  if (state.live) {
    state.banks = {};
    await Promise.all(state.venues.map(async v => {
      try {
        const r = await fetch(`/root/${v.slug}/captions-bank.json`);
        if (r.ok) state.banks[v.slug] = await r.json();
      } catch { /* no bank for this venue */ }
    }));
  }
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

function rootUrl(path) {
  const enc = path.split("/").map(encodeURIComponent).join("/");
  return state.live ? `/root/${state.venue}/${enc}` : `media/${state.venue}/refs/${enc.split("/").pop()}`;
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
    const v = slot._v;
    Object.assign(slot, j.slot);
    if (v) slot._v = v;
    if (!quiet) toast("Saved");
    return true;
  } catch (e) {
    toast("Save failed: " + e.message);
    return false;
  }
}

/* ---------- shared helpers ---------- */

function groupSlots(week) {
  const groups = [];
  const byDay = new Map();
  for (const s of week.slots) {
    const key = s.day || s.date;
    if (!byDay.has(key)) { byDay.set(key, []); groups.push({ key, date: s.date, slots: byDay.get(key) }); }
    byDay.get(key).push(s);
  }
  for (const g of groups) g.slots.sort((a, b) => (a.kind === b.kind ? 0 : a.kind === "grid" ? -1 : 1));
  const sortKey = g => (g.key.toLowerCase().includes("any") || g.key.toLowerCase().includes("quiet"))
    ? "9999-99-99" : (g.date || "9999-99-98");
  groups.sort((a, b) => sortKey(a) < sortKey(b) ? -1 : sortKey(a) > sortKey(b) ? 1 : 0);
  return groups;
}

function fmtDate(iso) {
  if (!iso) return "";
  const d = new Date(iso + "T12:00:00");
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}
const todayIso = () => new Date().toLocaleDateString("sv-SE");
const dayComplete = g => g.slots.length > 0 && g.slots.every(s => DONE.has(s.status));
const dayId = key => "xday-" + key.toLowerCase().replace(/[^a-z0-9]+/g, "-");

/* ---------- rendering ---------- */

function render() {
  renderWeekBar();
  renderLinks();
  renderKeyDates();
  renderBoard();
  renderPrep();
  renderExpanded();
  renderCalendar();
  const week = curWeek();
  const onBoard = state.view === "board" && !!week;
  $("#board").hidden = !onBoard;
  $("#expanded").hidden = !onBoard;
  $("#prep").hidden = !onBoard || !(week?.prep || []).length;
  applyCollapse("board", $("#board-body"), $('[data-collapse="board"]'));
  applyCollapse("prep", $("#prep-body"), $('[data-collapse="prep"]'));
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

/* ----- collapsible sections ----- */

const collapsed = new Set(JSON.parse(localStorage.getItem("hub-collapsed") || "[]"));

function applyCollapse(id, bodyEl, btn) {
  const off = collapsed.has(id);
  if (bodyEl) bodyEl.hidden = off;
  if (btn) btn.classList.toggle("is-collapsed", off);
}

function toggleCollapse(id) {
  if (collapsed.has(id)) collapsed.delete(id);
  else collapsed.add(id);
  localStorage.setItem("hub-collapsed", JSON.stringify([...collapsed]));
  render();
}

$$("[data-collapse]").forEach(b => b.addEventListener("click", () => toggleCollapse(b.dataset.collapse)));

function renderLinks() {
  const week = curWeek();
  const el = $("#links");
  const links = week?.links || [];
  el.hidden = !links.length || state.view !== "board";
  el.innerHTML = "";
  links.forEach(l => {
    const a = document.createElement("a");
    a.href = l.url;
    a.target = "_blank";
    a.rel = "noopener";
    a.textContent = l.label;
    el.appendChild(a);
  });
}

function renderKeyDates() {
  const week = curWeek();
  const el = $("#keydates");
  const dates = week?.key_dates || [];
  const alerts = week?.alerts || [];
  el.hidden = (!dates.length && !alerts.length) || state.view !== "board";
  el.innerHTML = "";
  for (const a of alerts) {
    const w = document.createElement("div");
    w.className = "week-alert";
    w.textContent = "* " + a;
    el.appendChild(w);
  }
  for (const d of dates) {
    const chip = document.createElement("span");
    chip.className = "keydate";
    chip.textContent = d;
    el.appendChild(chip);
  }
}

/* ----- compact board: one row per day, grid | story ----- */

function renderBoard() {
  const week = curWeek();
  const rows = $("#board-rows");
  rows.innerHTML = "";
  $("#board-head").hidden = !week;
  if (!week) return;
  const today = todayIso();
  let zebra = 0, prevDate = null;
  for (const g of groupSlots(week)) {
    const isSub = prevDate !== null && g.date === prevDate && !g.key.toLowerCase().includes("any");
    if (!isSub) zebra++;
    prevDate = g.date;
    const row = document.createElement("div");
    row.className = "day-row " + (zebra % 2 ? "z-a" : "z-b") + (isSub ? " sub" : "") +
      (dayComplete(g) ? " is-complete" : "");
    const label = document.createElement("div");
    label.className = "day-cell-label";
    const name = document.createElement("button");
    name.textContent = g.key;
    if (g.slots.some(s => s.alert)) {
      const star = document.createElement("span");
      star.className = "day-star";
      star.textContent = " *";
      star.title = g.slots.filter(s => s.alert).map(s => s.alert).join("\n");
      name.appendChild(star);
    }
    name.title = "Jump to " + g.key;
    name.addEventListener("click", () => {
      document.getElementById(dayId(g.key))?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
    const date = document.createElement("span");
    date.className = "d-date";
    date.textContent = g.key.toLowerCase().includes("any") ? "any day" :
      fmtDate(g.date) + (g.date === today ? " · today" : "");
    label.append(name, date);
    if (dayComplete(g)) {
      const done = document.createElement("span");
      done.className = "d-done";
      done.textContent = "Done";
      label.appendChild(done);
    }
    row.appendChild(label);
    for (const kind of ["grid", "story"]) {
      const cell = document.createElement("div");
      cell.className = "day-cell";
      const items = g.slots.filter(s => s.kind === kind);
      if (!items.length) {
        const off = document.createElement("span");
        off.className = "cell-off";
        off.textContent = kind === "grid" ? "Grid off" : "No story slot";
        cell.appendChild(off);
      }
      for (const s of items) cell.appendChild(makeMini(week, s, g));
      row.appendChild(cell);
    }
    rows.appendChild(row);
  }
}

function makeMini(week, s, g) {
  const b = document.createElement("button");
  b.className = "mini" + (DONE.has(s.status) ? " is-done" : "");
  const first = s.media?.[0];
  if (first && !/\.(mp4|mov|m4v|webm)$/i.test(first)) {
    const img = document.createElement("img");
    img.className = "mini-thumb";
    img.loading = "lazy";
    img.src = mediaUrl(week, first, s);
    img.alt = "";
    b.appendChild(img);
  } else if (first) {
    const d = document.createElement("div");
    d.className = "mini-thumb is-video";
    d.textContent = "▶";
    b.appendChild(d);
  } else {
    const d = document.createElement("div");
    d.className = "mini-thumb is-empty";
    b.appendChild(d);
  }
  const main = document.createElement("div");
  main.className = "mini-main";
  const t = document.createElement("div");
  t.className = "mini-title";
  t.textContent = s.title || s.slot;
  if (s.alert) {
    const star = document.createElement("span");
    star.className = "mini-alert";
    star.textContent = " *";
    star.title = s.alert;
    t.appendChild(star);
  }
  const st = document.createElement("div");
  st.className = "mini-status " + s.status;
  st.textContent = STATUS_LABEL[s.status] || s.status;
  main.append(t, st);
  b.appendChild(main);
  b.addEventListener("click", () => {
    document.getElementById("xpost-" + s.id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  });
  return b;
}

/* ----- week prep checklist ----- */

function renderPrep() {
  const week = curWeek();
  const list = $("#prep-list");
  list.innerHTML = "";
  if (!week?.prep?.length) return;
  week.prep.forEach((item, i) => {
    const li = document.createElement("li");
    li.className = item.done ? "is-ticked" : "";
    const wrap = document.createElement("label");
    wrap.className = "tick-label";
    const box = document.createElement("input");
    box.type = "checkbox";
    box.checked = !!item.done;
    box.disabled = !state.live;
    box.addEventListener("change", async () => {
      if (!state.live) return;
      const next = week.prep.map(x => ({ ...x }));
      next[i].done = box.checked;
      try {
        const r = await fetch("/api/week", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ venue: state.venue, week_start: week.week_start, set: { prep: next } }),
        });
        const j = await r.json();
        if (!j.ok) throw new Error(j.error || "save failed");
        week.prep = next;
        toast(box.checked ? "Ticked off" : "Unticked");
        renderPrep();
      } catch (e) { toast("Save failed: " + e.message); }
    });
    const label = document.createElement("span");
    label.textContent = item.text;
    wrap.append(box, label);
    li.appendChild(wrap);
    list.appendChild(li);
  });
}

/* ----- expanded day-by-day review ----- */

function renderExpanded() {
  const week = curWeek();
  const wrap = $("#expanded");
  wrap.innerHTML = "";
  if (!week) return;
  for (const g of groupSlots(week)) {
    const sec = document.createElement("section");
    sec.className = "xday" + (dayComplete(g) ? " is-complete" : "");
    sec.id = dayId(g.key);
    const head = document.createElement("div");
    head.className = "xday-head";
    const n = document.createElement("span");
    n.className = "xday-name";
    n.textContent = g.key;
    if (g.slots.some(s => s.alert)) {
      const star = document.createElement("span");
      star.className = "day-star";
      star.textContent = " *";
      star.title = g.slots.filter(s => s.alert).map(s => s.alert).join("\n");
      n.appendChild(star);
    }
    const d = document.createElement("span");
    d.className = "xday-date";
    d.textContent = g.key.toLowerCase().includes("any") ? "post any day" : fmtDate(g.date);
    head.append(n, d);
    const gridTitles = g.slots.filter(s => s.kind === "grid").map(s => s.title || s.slot);
    const storyTitles = g.slots.filter(s => s.kind === "story").map(s => s.title || s.slot);
    if (gridTitles.length || storyTitles.length) {
      const sum = document.createElement("span");
      sum.className = "xday-sum";
      sum.textContent = "- " + (gridTitles.join(" + ") || "grid off") + "  //  " + (storyTitles.join(" + ") || "no story");
      head.appendChild(sum);
    }
    if (dayComplete(g)) {
      const c = document.createElement("span");
      c.className = "xday-complete-chip";
      c.textContent = "Day done";
      head.appendChild(c);
    }
    const cid = "day:" + g.key;
    const cbtn = document.createElement("button");
    cbtn.className = "collapse-btn" + (collapsed.has(cid) ? " is-collapsed" : "");
    cbtn.setAttribute("aria-label", "Collapse " + g.key);
    cbtn.innerHTML = "&#8964;";
    cbtn.addEventListener("click", () => toggleCollapse(cid));
    head.appendChild(cbtn);
    sec.appendChild(head);
    const dayBody = document.createElement("div");
    dayBody.hidden = collapsed.has(cid);
    for (const kind of ["grid", "story"]) {
      const items = g.slots.filter(s => s.kind === kind);
      if (!items.length) continue;
      const kwrap = document.createElement("div");
      kwrap.className = "xkind " + (kind === "grid" ? "k-grid" : "k-story");
      const klabel = document.createElement("div");
      klabel.className = "xkind-head";
      klabel.textContent = kind === "grid" ? "Grid post" : "Story";
      kwrap.appendChild(klabel);
      for (const s of items) kwrap.appendChild(makeXpost(week, s));
      dayBody.appendChild(kwrap);
    }
    sec.appendChild(dayBody);
    wrap.appendChild(sec);
  }
}

function makeXpost(week, s) {
  const card = document.createElement("article");
  card.className = "xpost" + (DONE.has(s.status) ? " is-done" : "");
  card.id = "xpost-" + s.id;

  const head = document.createElement("div");
  head.className = "xpost-head";
  const title = document.createElement("span");
  title.className = "xpost-title";
  title.textContent = s.title || s.slot;
  const slotName = document.createElement("span");
  slotName.className = "xpost-slot";
  slotName.textContent = s.slot;
  const stTag = document.createElement("span");
  stTag.className = "mini-status " + s.status;
  stTag.textContent = STATUS_LABEL[s.status] || s.status;
  stTag.style.marginLeft = "auto";
  head.append(title, slotName, stTag);
  card.appendChild(head);
  if (s.alert) {
    const al = document.createElement("div");
    al.className = "xalert";
    al.textContent = "* " + s.alert;
    card.appendChild(al);
  }

  const body = document.createElement("div");
  body.className = "xpost-body";

  // LEFT: reference
  const left = document.createElement("div");
  left.className = "xpane";
  const refLabel = document.createElement("span");
  refLabel.className = "xpane-label";
  refLabel.textContent = s.reference_label || "Reference";
  left.appendChild(refLabel);
  const refMedia = document.createElement("div");
  refMedia.className = "xmedia";
  if (s.reference && /\.(mp4|mov|m4v|webm)$/i.test(s.reference)) {
    const v = document.createElement("video");
    v.src = rootUrl(s.reference);
    v.controls = true; v.playsInline = true; v.preload = "metadata";
    refMedia.appendChild(v);
  } else if (s.reference) {
    const img = document.createElement("img");
    img.loading = "lazy";
    img.src = rootUrl(s.reference);
    img.alt = "";
    img.onerror = () => { refMedia.innerHTML = '<div class="placeholder">Reference image not bundled in this snapshot.</div>'; };
    refMedia.appendChild(img);
  } else {
    const p = document.createElement("div");
    p.className = "placeholder";
    p.textContent = "No reference for this one. Next week this side becomes last week's post.";
    refMedia.appendChild(p);
  }
  left.appendChild(refMedia);
  body.appendChild(left);

  // RIGHT: this week
  const right = document.createElement("div");
  right.className = "xpane";
  const thisLabel = document.createElement("span");
  thisLabel.className = "xpane-label";
  thisLabel.textContent = "This week";
  right.appendChild(thisLabel);
  right.appendChild(makeMedia(week, s));

  const actions = document.createElement("div");
  actions.className = "xactions";
  const approve = document.createElement("button");
  approve.className = "xbtn approve" + (DONE.has(s.status) ? " is-on" : "");
  approve.textContent = DONE.has(s.status) ? "Approved" : "Happy with it";
  approve.addEventListener("click", async () => {
    const to = DONE.has(s.status) ? "ready" : "approved";
    if (await patchSlot(s, { set: { status: to } }, true)) {
      toast(to === "approved" ? "Approved" : "Back in review");
      render();
    }
  });
  actions.appendChild(approve);
  const posted = document.createElement("button");
  posted.className = "xbtn posted" + (s.status === "posted" ? " is-on" : "");
  posted.textContent = s.status === "posted" ? "Posted ✓" : "Mark posted";
  posted.addEventListener("click", async () => {
    const to = s.status === "posted" ? "approved" : "posted";
    if (await patchSlot(s, { set: { status: to } }, true)) { toast(to === "posted" ? "Marked posted" : "Back to approved"); render(); }
  });
  actions.appendChild(posted);
  if (state.live && s.template?.content && (s.template?.out || s.template?.outdir)) {
    const adj = document.createElement("button");
    adj.className = "xbtn";
    adj.textContent = "Adjust layout";
    adj.addEventListener("click", () => openEditor(s));
    actions.appendChild(adj);
    const photo = document.createElement("button");
    photo.className = "xbtn";
    photo.textContent = "Change photo";
    photo.addEventListener("click", () => openPicker(s));
    actions.appendChild(photo);
  }
  right.appendChild(actions);

  // caption
  const capRow = document.createElement("div");
  capRow.className = "xcap-label-row";
  const capLabel = document.createElement("span");
  capLabel.className = "xpane-label";
  capLabel.textContent = "Caption";
  const copyBtn = document.createElement("button");
  copyBtn.className = "mini-btn";
  copyBtn.textContent = "Copy";
  capRow.append(capLabel, copyBtn);
  right.appendChild(capRow);
  const cap = document.createElement("div");
  cap.className = "caption-edit";
  cap.textContent = s.caption || "";
  cap.contentEditable = state.live ? "plaintext-only" : "false";
  cap.spellcheck = false;
  cap.addEventListener("blur", async () => {
    if (!state.live) return;
    const text = cap.innerText.replace(/\n{3,}/g, "\n\n").trimEnd();
    if (text === (s.caption || "")) return;
    if (await patchSlot(s, { set: { caption: text } }, true)) toast("Caption saved");
  });
  copyBtn.addEventListener("click", async () => {
    await navigator.clipboard.writeText(cap.innerText);
    toast("Caption copied");
  });
  right.appendChild(cap);

  // alternates
  if (s.alternates?.length) {
    const altWrap = document.createElement("div");
    const altLabel = document.createElement("span");
    altLabel.className = "xpane-label";
    altLabel.style.marginTop = "10px";
    altLabel.textContent = "Alternates, tap to swap in";
    altWrap.appendChild(altLabel);
    const chips = document.createElement("div");
    chips.className = "alt-chips";
    s.alternates.forEach((alt, i) => {
      const b = document.createElement("button");
      b.className = "alt-chip";
      b.textContent = alt;
      b.addEventListener("click", async () => {
        const alts = s.alternates.slice();
        alts[i] = s.caption;
        if (await patchSlot(s, { set: { caption: alt, alternates: alts.filter(Boolean) } })) render();
      });
      chips.appendChild(b);
    });
    altWrap.appendChild(chips);
    right.appendChild(altWrap);
  }

  // caption helper: similar past captions of this slot's category
  const bank = state.banks?.[state.venue];
  if (bank && s.kind === "grid") {
    const hay = ((s.slot || "") + " " + (s.title || "")).toLowerCase();
    let catKey = null;
    for (const [needle, key] of Object.entries(bank.slot_category_map || {}))
      if (hay.includes(needle)) { catKey = key; break; }
    const cat = catKey && bank.categories[catKey];
    if (cat?.captions?.length) {
      const cWrap = document.createElement("div");
      const cLabel = document.createElement("span");
      cLabel.className = "xpane-label";
      cLabel.style.marginTop = "12px";
      cLabel.textContent = "Similar past captions · " + cat.label;
      cWrap.appendChild(cLabel);
      for (const past of cat.captions) {
        const card = document.createElement("div");
        card.className = "cap-ref" + (s.caption_ref === past.date + ":" + catKey ? " is-picked" : "");
        const txt = document.createElement("div");
        txt.className = "cap-ref-text";
        txt.textContent = past.text;
        const row = document.createElement("div");
        row.className = "cap-ref-row";
        const meta = document.createElement("span");
        meta.className = "cap-ref-meta";
        meta.textContent = past.date;
        const use = document.createElement("button");
        use.className = "mini-btn";
        use.textContent = s.caption_ref === past.date + ":" + catKey ? "Style reference ✓" : "Use as style reference";
        use.addEventListener("click", async () => {
          if (await patchSlot(s, {
            set: { caption_ref: past.date + ":" + catKey },
            add_note: { text: "Style reference picked: the " + past.date + " " + cat.label + " caption. Draft the next options in this style." },
          }, true)) { toast("Style reference saved"); render(); }
        });
        const copy = document.createElement("button");
        copy.className = "mini-btn";
        copy.textContent = "Copy";
        copy.addEventListener("click", async () => {
          await navigator.clipboard.writeText(past.text);
          toast("Copied");
        });
        row.append(meta, use, copy);
        card.append(txt, row);
        cWrap.appendChild(card);
      }
      right.appendChild(cWrap);
    }
  }

  // reactive idea clicker for open reactive story slots
  const isReactive = (s.slot || "").toLowerCase().includes("reactive") && s.kind === "story";
  if (isReactive && state.live) {
    const rWrap = document.createElement("div");
    const rLabel = document.createElement("span");
    rLabel.className = "xpane-label";
    rLabel.style.marginTop = "12px";
    rLabel.textContent = "Reactive menu, tap to pick";
    rWrap.appendChild(rLabel);
    const rRow = document.createElement("div");
    rRow.className = "reactive-row";
    for (const opt of REACTIVE_MENU) {
      const b = document.createElement("button");
      b.className = "r-chip" + ((s.title || "").includes(opt.name) ? " is-picked" : "");
      b.textContent = opt.name;
      b.title = opt.prompt;
      b.addEventListener("click", async () => {
        if (await patchSlot(s, {
          set: { title: "Reactive: " + opt.name, caption: opt.prompt },
          add_note: { text: "Picked " + opt.name + " from the reactive menu." },
        }, true)) { toast(opt.name + " picked"); render(); }
      });
      rRow.appendChild(b);
    }
    rWrap.appendChild(rRow);
    right.appendChild(rWrap);
  }

  // checklist with tickboxes (string items and {text, done} both supported)
  if (s.checklist?.length) {
    const cl = document.createElement("ul");
    cl.className = "xchecklist";
    s.checklist.forEach((item, i) => {
      const text = typeof item === "string" ? item : item.text;
      const done = typeof item === "object" && !!item.done;
      const li = document.createElement("li");
      li.className = done ? "is-ticked" : "";
      const wrap = document.createElement("label");
      wrap.className = "tick-label";
      const box = document.createElement("input");
      box.type = "checkbox";
      box.checked = done;
      box.disabled = !state.live;
      box.addEventListener("change", async () => {
        const next = s.checklist.map(it => typeof it === "string" ? { text: it, done: false } : { ...it });
        next[i].done = box.checked;
        if (await patchSlot(s, { set: { checklist: next } }, true)) {
          toast(box.checked ? "Ticked off" : "Unticked");
          render();
        }
      });
      const label = document.createElement("span");
      label.textContent = text;
      wrap.append(box, label);
      li.appendChild(wrap);
      cl.appendChild(li);
    });
    right.appendChild(cl);
  }

  // comment thread
  const thread = document.createElement("ul");
  thread.className = "thread";
  for (const n of s.notes || []) {
    const li = document.createElement("li");
    const meta = document.createElement("span");
    meta.className = "t-meta";
    meta.textContent = (n.by === "paul" ? "You" : "Studio") + " · " + n.ts;
    li.appendChild(meta);
    li.appendChild(document.createTextNode(n.text));
    thread.appendChild(li);
  }
  right.appendChild(thread);
  if (state.live) {
    const row = document.createElement("div");
    row.className = "thread-input";
    const input = document.createElement("input");
    input.type = "text";
    input.placeholder = "Comment or change request";
    const add = document.createElement("button");
    add.className = "mini-btn";
    add.textContent = "Add";
    const send = async () => {
      const text = input.value.trim();
      if (!text) return;
      const payload = { add_note: { text } };
      const flips = !DONE.has(s.status) && s.status !== "waiting";
      if (flips) payload.set = { status: "changes" };
      if (await patchSlot(s, payload, true)) {
        toast(flips ? "Comment saved · marked changes asked" : "Comment saved");
        render();
      }
    };
    add.addEventListener("click", send);
    input.addEventListener("keydown", e => { if (e.key === "Enter") send(); });
    row.append(input, add);
    right.appendChild(row);
  }

  body.appendChild(right);
  card.appendChild(body);
  return card;
}

function makeMedia(week, s) {
  const m = document.createElement("div");
  m.className = "xmedia";
  if (!s.media?.length) {
    const p = document.createElement("div");
    p.className = "placeholder";
    p.textContent = s.media_kind === "none"
      ? "No file needed, this one is an action on the day."
      : "Nothing here yet. " + (s.checklist?.[0] || "");
    m.appendChild(p);
    return m;
  }
  if (s.media.length > 1) {
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
    return m;
  }
  const path = s.media[0];
  if (/\.(mp4|mov|m4v|webm)$/i.test(path)) {
    const v = document.createElement("video");
    v.src = mediaUrl(week, path, s);
    v.controls = true; v.playsInline = true; v.preload = "metadata";
    m.appendChild(v);
  } else {
    const img = document.createElement("img");
    img.loading = "lazy";
    img.src = mediaUrl(week, path, s);
    img.alt = "";
    m.appendChild(img);
  }
  return m;
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
  let zebra = 0, prevDate = null;
  for (const g of groupSlots(week)) {
    const isSub = prevDate !== null && g.date === prevDate && !g.key.toLowerCase().includes("any");
    if (!isSub) zebra++;
    prevDate = g.date;
    const row = document.createElement("div");
    row.className = "cal-row " + (zebra % 2 ? "z-a" : "z-b") + (isSub ? " sub" : "") +
      (g.date === today && !g.key.toLowerCase().includes("any") ? " is-today" : "");
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
        const it = document.createElement("button");
        it.className = "cal-item" + (DONE.has(s.status) ? " is-done" : "");
        const dot = document.createElement("span");
        dot.className = "dot " + s.status;
        it.appendChild(dot);
        it.appendChild(document.createTextNode(s.title || s.slot));
        it.addEventListener("click", () => {
          state.view = "board";
          render();
          requestAnimationFrame(() =>
            document.getElementById("xpost-" + s.id)?.scrollIntoView({ behavior: "smooth", block: "start" }));
        });
        cell.appendChild(it);
      }
      row.appendChild(cell);
    }
    cal.appendChild(row);
  }
}

/* ---------- top-level events ---------- */

$$(".venue-btn").forEach(b => b.addEventListener("click", () => {
  if (state.venue === b.dataset.venueBtn) return;
  state.venue = b.dataset.venueBtn;
  localStorage.setItem("hub-venue", state.venue);
  document.documentElement.dataset.venue = state.venue;
  window.scrollTo({ top: 0 });
  render();
}));

$$(".view-btn").forEach(b => b.addEventListener("click", () => {
  state.view = b.dataset.viewBtn;
  render();
}));

$("#week-prev").addEventListener("click", () => { state.weekIdx[state.venue]--; window.scrollTo({ top: 0 }); render(); });
$("#week-next").addEventListener("click", () => { state.weekIdx[state.venue]++; window.scrollTo({ top: 0 }); render(); });

/* ---------- layout editor ---------- */

const ed = { layout: null, content: null, slot: null, scale: 1, sel: null };
const ED_FONTS = [
  "", "Poppins", "Poppins SemiBold", "Bodoni 72", "Snell Roundhand",
  "Barlow Semi Condensed", "Playfair Display", "Helvetica Neue",
];

$("#editor-cancel").addEventListener("click", () => closeEditor());
$("#size-down").addEventListener("click", () => bumpSize(-2));
$("#size-up").addEventListener("click", () => bumpSize(2));
$("#width-down").addEventListener("click", () => bumpWidth(-20));
$("#width-up").addEventListener("click", () => bumpWidth(20));
$("#font-select").addEventListener("change", e => {
  if (!ed.sel) return;
  ed.dirty = true;
  if (e.target.value) ed.sel.font = e.target.value;
  else delete ed.sel.font;
  const el = $(`.ed-block[data-id="${ed.sel.id}"]`);
  if (el) styleEdBlock(el, ed.sel);
});
$("#text-edit").addEventListener("input", e => {
  if (!ed.sel) return;
  ed.dirty = true;
  const id = ed.sel.id, val = e.target.value;
  if (id === "acts") ed.content.acts = val.split("\n").map(line => ({ time: "", name: line }));
  else if (Array.isArray(ed.content[id])) ed.content[id] = val.split("\n");
  else ed.content[id] = val;
  const el = $(`.ed-block[data-id="${id}"]`);
  if (el) el.textContent = id === "acts" ? edText("acts") : val;
});
$("#editor-save").addEventListener("click", saveEditor);

async function openEditor(slot) {
  const week = curWeek();
  try {
    const r = await fetch(`/api/template?venue=${state.venue}&week=${week.week_start}&id=${slot.id}`);
    const j = await r.json();
    if (!j.layout) throw new Error(j.error || "no layout");
    ed.fullLayout = j.layout;
    ed.fullContent = j.content || {};
    ed.slot = slot; ed.sel = null; ed.dirty = false;
    if (j.layout.slides && j.content?.slides?.length) {
      // multi-slide template: edit the first slide's blocks
      const type = j.content.slides[0].type;
      ed.layout = { width: j.layout.width, height: j.layout.height, blocks: j.layout.slides[type] || [] };
      ed.content = j.content.slides[0];
      ed.slideType = type;
    } else {
      ed.layout = j.layout;
      ed.content = j.content || {};
      ed.slideType = null;
    }
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
  const bgPath = ed.slot.media?.[0];
  if (bgPath) stage.style.backgroundImage = `url("${mediaUrl(week, bgPath)}?v=${ed.slot._v || 0}")`;
  const blocks = ed.layout.blocks || [];
  for (const b of blocks) {
    if (b.id === "logo") continue;
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
    fontFamily: b.font ? `"${b.font}", "Helvetica Neue", sans-serif` : "",
    textAlign: b.align || "center",
    lineHeight: String(b.lineHeight || 1.16),
    letterSpacing: (b.letterSpacing || 0) + "em",
    textTransform: b.uppercase === true ? "uppercase" : "none",
    color: b.color || "#ffffff",
  });
}

function bumpWidth(d) {
  if (!ed.sel) return;
  ed.dirty = true;
  ed.sel.w = Math.max(80, Math.min((ed.layout.width || 1080), ed.sel.w + d));
  const el = $(`.ed-block[data-id="${ed.sel.id}"]`);
  if (el) styleEdBlock(el, ed.sel);
}

function attachDrag(el, b) {
  el.addEventListener("pointerdown", e => {
    e.preventDefault();
    el.setPointerCapture(e.pointerId);
    selectBlock(el, b);
    const startX = e.clientX, startY = e.clientY;
    let dx = 0, dy = 0, raf = null;
    el.style.willChange = "transform";
    const apply = () => { raf = null; el.style.transform = `translate3d(${dx}px, ${dy}px, 0)`; };
    const move = ev => {
      dx = ev.clientX - startX;
      dy = ev.clientY - startY;
      ed.dirty = true;
      if (!raf) raf = requestAnimationFrame(apply);
    };
    const up = () => {
      el.removeEventListener("pointermove", move);
      el.removeEventListener("pointerup", up);
      if (raf) cancelAnimationFrame(raf);
      b.x = Math.round(b.x + dx / ed.scale);
      b.y = Math.round(b.y + dy / ed.scale);
      el.style.transform = "";
      el.style.willChange = "";
      styleEdBlock(el, b);
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
  const te = $("#text-edit");
  te.value = edText(b.id);
  te.rows = Math.min(3, te.value.split("\n").length);
}

function bumpSize(d) {
  if (!ed.sel) return;
  ed.dirty = true;
  ed.sel.size = Math.max(12, ed.sel.size + d);
  $("#size-val").textContent = ed.sel.size + "px";
  const el = $(`.ed-block[data-id="${ed.sel.id}"]`);
  if (el) styleEdBlock(el, ed.sel);
}

async function saveEditor() {
  const s = ed.slot, week = curWeek();
  $("#editor-save").textContent = "Rendering…";
  let layout = ed.layout, content = ed.content;
  if (ed.slideType) {
    ed.fullLayout.slides[ed.slideType] = ed.layout.blocks;
    ed.fullContent.slides[0] = ed.content;
    layout = ed.fullLayout;
    content = ed.fullContent;
  }
  try {
    const r = await fetch("/api/render", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ venue: state.venue, week_start: week.week_start, id: s.id, layout, content }),
    });
    const j = await r.json();
    if (!j.ok) throw new Error(j.error || "render failed");
    s._v = Date.now();
    ed.dirty = false;
    $("#editor").hidden = true;
    toast("Re-rendered");
    render();
  } catch (e) {
    toast("Render failed: " + e.message);
  } finally {
    $("#editor-save").textContent = "Save & re-render";
  }
}

window.addEventListener("resize", () => {
  if (!$("#editor").hidden && ed.layout) buildEditorStage();
});

document.addEventListener("keydown", e => {
  if (e.key !== "Escape") return;
  if (!$("#photo-picker").hidden) { $("#photo-picker").hidden = true; return; }
  if (!$("#editor").hidden) closeEditor();
});

function closeEditor() {
  if (ed.dirty && !confirm("Discard layout and text changes?")) return;
  $("#editor").hidden = true;
  ed.dirty = false;
}

/* ---------- photo picker ---------- */

let pickerSlot = null;
$("#picker-close").addEventListener("click", () => { $("#photo-picker").hidden = true; });
$("#photo-picker").addEventListener("click", e => { if (e.target === $("#photo-picker")) $("#photo-picker").hidden = true; });

async function openPicker(slot) {
  pickerSlot = slot;
  const grid = $("#picker-grid");
  grid.innerHTML = '<div class="placeholder">Loading photos…</div>';
  $("#photo-picker").hidden = false;
  try {
    const r = await fetch("/api/photos?venue=" + state.venue);
    const j = await r.json();
    grid.innerHTML = "";
    for (const rel of j.photos || []) {
      const b = document.createElement("button");
      b.title = rel;
      const img = document.createElement("img");
      img.loading = "lazy";
      img.src = rootUrl(rel);
      img.alt = "";
      b.appendChild(img);
      b.addEventListener("click", () => pickPhoto(rel));
      grid.appendChild(b);
    }
    if (!grid.children.length) grid.innerHTML = '<div class="placeholder">No photos found.</div>';
  } catch (e) {
    grid.innerHTML = '<div class="placeholder">Could not load photos.</div>';
  }
}

async function pickPhoto(rel) {
  const s = pickerSlot, week = curWeek();
  if (!s) return;
  $("#photo-picker").hidden = true;
  toast("Re-rendering with the new photo…");
  try {
    const r = await fetch("/api/setbg", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ venue: state.venue, week_start: week.week_start, id: s.id, photo: rel }),
    });
    const j = await r.json();
    if (!j.ok) throw new Error(j.error || "failed");
    s._v = Date.now();
    toast("Photo swapped");
    render();
  } catch (e) {
    toast("Photo swap failed: " + e.message);
  }
}

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
