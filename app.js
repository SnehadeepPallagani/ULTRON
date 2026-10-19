"use strict";
/* ULTRON prototype (Phases 1-2).
   Persistence: localStorage only (prototype, single browser, not a real backend).
   Backend: set API.endpoint below. No endpoint is assumed to exist. */


 const API = {
  baseUrl: "",

  async post(path, payload) {
    const res = await fetch(`${this.baseUrl}${path}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload)
    });

    const data = await res.json();

    if (!res.ok) {
      throw new Error(
        data.error || data.message || `Request failed (${res.status})`
      );
    }

    return data;
  },

  async send(brain, messages) {
    const latest = messages[messages.length - 1];

    if (!latest || latest.role !== "user") {
      throw new Error("Could not identify the latest user message.");
    }

    const switched = await this.post("/switch", {
      brain: brain || "nexus"
    });

    if (!switched.success) {
      throw new Error(switched.message || "Brain switch failed.");
    }

    const result = await this.post("/ask", {
      prompt: latest.content,
      history: messages.slice(0, -1).map(message => ({
        role: message.role,
        content: message.content
      }))
    });

    if (!result.success) {
      throw new Error(
        result.response || result.error || "ULTRON could not answer."
      );
    }

    if (typeof result.response !== "string") {
      throw new Error("Unexpected response from ULTRON's backend.");
    }

    return result.response;
  }
};


const BRAINS = [
  { id: "nexus", name: "Nexus", desc: "Automatic routing (ULTRON NEXUS)" },
  { id: "velocity", name: "Velocity", desc: "Fast general-purpose · Llama 3.1 8B" },
  { id: "forge", name: "Forge", desc: "Coding and technical · Qwen 3.5 9B" },
  { id: "apex", name: "Apex", desc: "Analysis and multimodal · Gemma 3 12B" },
  { id: "titan", name: "Titan", desc: "Deep reasoning · GPT-OSS 20B" }
];

const $ = id => document.getElementById(id);
const store = {
  get(k, d) { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { toast("Could not save to browser storage"); } }
};
/* Phase 3: load projects and normalise older data safely (older conversations have no projectId) */
function loadProjects() {
  const raw = store.get("ultron.projects", []); if (!Array.isArray(raw)) return [];
  const seen = new Set();
  return raw.filter(p => p && typeof p === "object" && typeof p.id === "string" && typeof p.name === "string" && p.name.trim() && !seen.has(p.id) && seen.add(p.id))
    .map(p => ({ id: p.id, name: p.name.trim(), created: Number(p.created) || Date.now() }));
}
function normalizeConvs(list, projects) {
  if (!Array.isArray(list)) return [];
  const ids = new Set(projects.map(p => p.id));
  return list.filter(c => c && typeof c === "object" && typeof c.id === "string").map(c => {
    if (!Array.isArray(c.messages)) c.messages = [];
    if (typeof c.title !== "string") c.title = "Untitled";
    if (typeof c.updated !== "number") c.updated = Date.now();
    c.projectId = (typeof c.projectId === "string" && ids.has(c.projectId)) ? c.projectId : null;
    return c;
  });
}
const _projects = loadProjects();
let state = { projects: _projects, convs: normalizeConvs(store.get("ultron.convs", []), _projects), active: null, brain: store.get("ultron.brain", "nexus"), view: "all", busy: false };
if (state.view !== "all" && !state.projects.some(p => p.id === state.view)) state.view = "all";
{ const a0 = state.convs.find(c => c.id === state.active); if (!a0 || (state.view !== "all" && a0.projectId !== state.view)) state.active = null; }
const save = () => { store.set("ultron.convs", state.convs); store.set("ultron.active", state.active); store.set("ultron.brain", state.brain); store.set("ultron.projects", state.projects); store.set("ultron.view", state.view); };
const uid = () => Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
const active = () => state.convs.find(c => c.id === state.active);
const projectById = id => state.projects.find(p => p.id === id);
const projectName = id => { const p = projectById(id); return p ? p.name : ""; };
const inView = c => state.view === "all" || c.projectId === state.view;

function toast(t) { const el = $("toast"); el.textContent = t; el.hidden = false; clearTimeout(toast.t); toast.t = setTimeout(() => el.hidden = true, 2200); }
function isMobile() { return matchMedia("(max-width:800px)").matches; }

/* theme */
function setTheme(t) {
  document.documentElement.dataset.theme = t; store.set("ultron.theme", t);
  document.querySelectorAll(".seg button").forEach(b => b.setAttribute("aria-pressed", b.dataset.theme === t));
}
setTheme(store.get("ultron.theme", "dark"));
document.querySelectorAll(".seg button").forEach(b => b.onclick = () => setTheme(b.dataset.theme));

/* sidebar */
const app = $("app");
function toggleSidebar() { isMobile() ? app.classList.toggle("drawer") : app.classList.toggle("collapsed"); }
$("collapseBtn").onclick = toggleSidebar;
$("openSidebarBtn").onclick = toggleSidebar;
$("scrim").onclick = () => app.classList.remove("drawer");

/* dialogs */
function ask(text, { input, select, value = "", ok = "OK" } = {}) {
  return new Promise(resolve => {
    const d = $("dialog"), i = $("dlgInput"), s = $("dlgSelect");
    $("dlgText").textContent = text; $("dlgOk").textContent = ok;
    i.hidden = !input; i.value = value;
    s.hidden = !select; s.textContent = "";
    if (select) { select.forEach(o => { const op = document.createElement("option"); op.value = o.value; op.textContent = o.label; s.append(op); }); s.value = value; }
    /* Enter confirms (the first submit button in the form is Cancel, so the browser default would cancel) */
    const enter = e => { if (e.key === "Enter" && !e.isComposing) { e.preventDefault(); d.close("ok"); } };
    i.onkeydown = enter; s.onkeydown = enter;
    d.returnValue = ""; /* otherwise Esc could reuse the previous dialog's result */
    d.onclose = () => resolve(d.returnValue === "ok" ? (select ? s.value : input ? i.value.trim() : true) : null);
    d.showModal(); if (input) { i.focus(); i.select(); } else if (select) s.focus();
  });
}
$("settingsBtn").onclick = () => $("settings").showModal();

/* history */
function groupOf(ts) {
  const day = 864e5, start = new Date().setHours(0, 0, 0, 0), age = start - new Date(ts).setHours(0, 0, 0, 0);
  if (age <= 0) return "Today"; if (age <= day) return "Yesterday"; if (age <= 7 * day) return "Previous 7 days"; return "Older";
}
function renderHistory() {
  const q = $("searchInput").value.trim().toLowerCase(), box = $("history"); box.textContent = "";
  const list = state.convs.filter(c => inView(c) && (!q || c.title.toLowerCase().includes(q) || c.messages.some(m => m.content.toLowerCase().includes(q)))).sort((a, b) => b.updated - a.updated);
  if (!list.length) { const d = document.createElement("div"); d.className = "none"; d.textContent = q ? "No matching chats" : (state.view === "all" ? "No conversations yet" : "No conversations in this project yet"); box.append(d); return; }
  let last = "";
  for (const c of list) {
    const g = groupOf(c.updated);
    if (g !== last) { const h = document.createElement("div"); h.className = "group"; h.textContent = g; box.append(h); last = g; }
    const row = document.createElement("div"); row.className = "conv" + (c.id === state.active ? " active" : "");
    const open = document.createElement("button"); open.className = "open"; open.textContent = c.title;
    if (state.view === "all" && c.projectId) { const bd = document.createElement("span"); bd.className = "badge"; bd.textContent = projectName(c.projectId); open.append(bd); }
    if (c.id === state.active) open.setAttribute("aria-current", "true");
    open.onclick = () => { state.active = c.id; save(); render(); if (isMobile()) app.classList.remove("drawer"); };
    const more = document.createElement("button"); more.className = "more"; more.textContent = "…"; more.setAttribute("aria-label", "Options for " + c.title);
    more.onclick = e => { e.stopPropagation(); showCtx(c.id, more); };
    row.append(open, more); box.append(row);
  }
}
$("searchInput").oninput = renderHistory;

let ctxId = null, ctxKind = "conv";
function showCtx(id, anchor, kind = "conv") {
  ctxId = id; ctxKind = kind; const m = $("ctx"), r = anchor.getBoundingClientRect();
  m.querySelectorAll("[data-for]").forEach(b => b.hidden = kind !== "conv");
  if (kind === "conv") { const cv = state.convs.find(x => x.id === id); $("ctxRemove").hidden = !(cv && cv.projectId); }
  m.hidden = false; m.style.top = r.bottom + 4 + "px"; m.style.left = Math.min(r.left, innerWidth - 160) + "px";
}
document.addEventListener("click", e => { if (!e.target.closest("#ctx")) $("ctx").hidden = true; if (!e.target.closest(".brain")) closeBrain(); });
$("ctx").onclick = async e => {
  const act = e.target.dataset.act; if (!act) return; $("ctx").hidden = true;
  if (ctxKind === "project") {
    const p = projectById(ctxId); if (!p) return;
    if (act === "rename") await renameProject(p);
    if (act === "delete") await deleteProject(p);
    return;
  }
  const c = state.convs.find(x => x.id === ctxId); if (!c) return;
  if (act === "move") {
    if (!state.projects.length) { toast("Create a project first"); return; }
    const opts = [{ value: "none", label: "No project (All chats)" }, ...state.projects.map(p => ({ value: p.id, label: p.name }))];
    const v = await ask(`Move "${c.title}" to:`, { select: opts, value: c.projectId || "none", ok: "Move" });
    if (v !== null) moveConv(c, v === "none" ? null : v);
  }
  if (act === "remove") moveConv(c, null);
  if (act === "rename") { const n = await ask("Rename conversation", { input: true, value: c.title, ok: "Rename" }); if (n) { c.title = n; save(); render(); toast("Renamed"); } }
  if (act === "delete") { if (await ask(`Delete "${c.title}"? This cannot be undone.`, { ok: "Delete" })) { state.convs = state.convs.filter(x => x !== c); if (state.active === c.id) state.active = null; save(); render(); toast("Deleted"); } }
};
$("newChatBtn").onclick = () => { state.active = null; save(); render(); $("input").focus(); if (isMobile()) app.classList.remove("drawer"); };

/* projects (Phase 3) */
const cleanName = raw => (raw || "").replace(/\s+/g, " ").trim().slice(0, 40);
function uniqueName(name, exceptId) {
  const taken = new Set(state.projects.filter(p => p.id !== exceptId).map(p => p.name.toLowerCase()));
  if (!taken.has(name.toLowerCase())) return name;
  let n = 2; while (taken.has(`${name} (${n})`.toLowerCase())) n++;
  return `${name} (${n})`;
}
function setView(v) {
  state.view = v; const c = active();
  if (c && v !== "all" && c.projectId !== v) state.active = null;
  save(); render();
}
function setPanel(open) {
  $("projectsPanel").hidden = !open; $("projectsBtn").setAttribute("aria-expanded", String(open)); store.set("ultron.projectsOpen", open);
}
async function createProject() {
  const raw = await ask("New project name", { input: true, ok: "Create" }); if (raw === null) return;
  const name = cleanName(raw); if (!name) { toast("Project name can't be empty"); return; }
  const final = uniqueName(name);
  const p = { id: uid(), name: final, created: Date.now() };
  state.projects.push(p); setPanel(true); setView(p.id);
  toast(final !== name ? `Created "${final}" (that name was already used)` : `Created "${final}"`);
}
async function renameProject(p) {
  const raw = await ask("Rename project", { input: true, value: p.name, ok: "Rename" }); if (raw === null) return;
  const name = cleanName(raw); if (!name) { toast("Project name can't be empty"); return; }
  if (name === p.name) return;
  p.name = uniqueName(name, p.id); save(); render(); toast(`Renamed to "${p.name}"`);
}
async function deleteProject(p) {
  const n = state.convs.filter(c => c.projectId === p.id).length;
  const msg = n ? `Delete project "${p.name}"? Its ${n} conversation${n === 1 ? "" : "s"} will be kept and moved to All chats.` : `Delete project "${p.name}"?`;
  if (!(await ask(msg, { ok: "Delete" }))) return;
  state.convs.forEach(c => { if (c.projectId === p.id) c.projectId = null; });
  state.projects = state.projects.filter(x => x.id !== p.id);
  if (state.view === p.id) state.view = "all";
  save(); render(); toast("Project deleted");
}
function moveConv(c, pid) {
  if ((c.projectId || null) === pid) return;
  c.projectId = pid;
  if (state.view !== "all" && state.view !== pid && state.active === c.id) state.active = null;
  save(); render(); toast(pid ? `Moved to "${projectName(pid)}"` : "Returned to All chats");
}
function renderProjects() {
  $("projectsCount").textContent = state.projects.length;
  $("allChatsRow").classList.toggle("active", state.view === "all");
  if (state.view === "all") $("allChatsBtn").setAttribute("aria-current", "true"); else $("allChatsBtn").removeAttribute("aria-current");
  const box = $("projectList"); box.textContent = "";
  if (!state.projects.length) { const d = document.createElement("div"); d.className = "none"; d.textContent = "No projects yet"; box.append(d); }
  for (const p of state.projects) {
    const row = document.createElement("div"); row.className = "conv" + (p.id === state.view ? " active" : "");
    const open = document.createElement("button"); open.type = "button"; open.className = "open"; open.textContent = p.name;
    const cnt = document.createElement("span"); cnt.className = "cnt"; cnt.textContent = state.convs.filter(c => c.projectId === p.id).length; open.append(cnt);
    if (p.id === state.view) open.setAttribute("aria-current", "true");
    open.onclick = () => setView(p.id);
    const more = document.createElement("button"); more.type = "button"; more.className = "more"; more.textContent = "…"; more.setAttribute("aria-label", "Options for project " + p.name);
    more.onclick = e => { e.stopPropagation(); showCtx(p.id, more, "project"); };
    row.append(open, more); box.append(row);
  }
  const vp = state.view !== "all" ? projectById(state.view) : null;
  $("viewbar").hidden = !vp; $("viewbarText").textContent = vp ? "Project: " + vp.name : "";
}
$("projectsBtn").onclick = () => setPanel($("projectsPanel").hidden);
$("createProjectBtn").onclick = createProject;
$("allChatsBtn").onclick = () => setView("all");
$("viewbarBack").onclick = () => setView("all");

/* Tools and Website Studio navigation */
$("toolsBtn").onclick = () => {
  $("toolsPage").hidden = false;
  $("websiteStudioPage").hidden = true;
  $("chat").hidden = true;
};

$("openWebsiteStudio").onclick = () => {
  $("toolsPage").hidden = true;
  $("websiteStudioPage").hidden = false;
  $("chat").hidden = true;
};

$("backToTools").onclick = () => {
  $("websiteStudioPage").hidden = true;
  $("toolsPage").hidden = false;
};

/* Tools Grid / List View */
const toolsAppGrid = $("toolsAppGrid");
const toolsGridViewBtn = $("toolsGridView");
const toolsListViewBtn = $("toolsListView");

function setToolsLayout(layout) {
  const isGrid = layout === "grid";

  toolsAppGrid.classList.toggle("list-view", !isGrid);

  toolsGridViewBtn.classList.toggle("active", isGrid);
  toolsListViewBtn.classList.toggle("active", !isGrid);

  toolsGridViewBtn.setAttribute("aria-pressed", String(isGrid));
  toolsListViewBtn.setAttribute("aria-pressed", String(!isGrid));
}

toolsGridViewBtn.onclick = () => setToolsLayout("grid");
toolsListViewBtn.onclick = () => setToolsLayout("list");

setToolsLayout("grid");


/* messages */
function renderContent(text) {
  const frag = document.createDocumentFragment(); const parts = text.split(/```/);
  parts.forEach((p, i) => {
    if (i % 2) {
      const code = p.replace(/^[^\n]*\n/, ""); const pre = document.createElement("pre"), cd = document.createElement("code");
      cd.textContent = code.replace(/\n$/, ""); const b = document.createElement("button"); b.type = "button"; b.className = "copy"; b.textContent = "Copy";
      b.onclick = () => navigator.clipboard.writeText(cd.textContent).then(() => toast("Copied"), () => toast("Copy failed"));
      pre.append(b, cd); frag.append(pre);
    } else if (p) {
      p.split(/(`[^`\n]+`)/).forEach(s => {
        if (/^`[^`]+`$/.test(s)) { const c = document.createElement("code"); c.textContent = s.slice(1, -1); frag.append(c); } else frag.append(document.createTextNode(s));
      });
    }
  });
  return frag;
}
function renderMessages() {
  const c = active(), box = $("messages"); box.textContent = "";
  const pr = c ? (c.projectId ? projectById(c.projectId) : null) : (state.view !== "all" ? projectById(state.view) : null);
  $("empty").hidden = !!c;
  $("chatTitle").textContent = pr ? (c ? pr.name + " / " + c.title : pr.name) : (c ? c.title : "New chat");
  $("emptySub").textContent = pr && !c ? "New chat in " + pr.name : "How can I help you?";
  if (!c) return;
  c.messages.forEach((m, i) => {
    const w = document.createElement("div"); w.className = "msg " + m.role + (m.error ? " error" : "");
    const b = document.createElement("div"); b.className = "bubble"; b.append(renderContent(m.content)); w.append(b);
    const a = document.createElement("div"); a.className = "actions";
    const mk = (t, f) => { const x = document.createElement("button"); x.type = "button"; x.textContent = t; x.onclick = f; a.append(x); };
    if (m.role === "assistant" && !m.error) { mk("Copy", () => navigator.clipboard.writeText(m.content).then(() => toast("Copied"), () => toast("Copy failed"))); }
    if (m.role === "assistant" && i === c.messages.length - 1) mk(m.error ? "Retry" : "Regenerate", () => regenerate());
    if (m.role === "user") mk("Edit", () => editMsg(i));
    if (a.children.length) w.append(a); box.append(w);
  });
  if (state.busy) { const w = document.createElement("div"); w.className = "msg assistant"; w.innerHTML = '<div class="bubble"><span class="dots" aria-label="Generating"><i></i><i></i><i></i></span></div>'; box.append(w); }
  $("chat").scrollTop = $("chat").scrollHeight;
}
function render() { renderProjects(); renderHistory(); renderMessages(); $("sendBtn").disabled = state.busy; }

async function respond(c) {
  state.busy = true; render();
  const showNotice = t => { const n = $("notice"); n.hidden = !t; n.textContent = t || ""; };
  showNotice("");
  try {
    const reply = await API.send(state.brain, c.messages.filter(m => !m.error).map(({ role, content }) => ({ role, content })));
    c.messages.push({ role: "assistant", content: reply });
  } catch (e) {
    c.messages.push({ role: "assistant", content: "Request failed: " + e.message, error: true });
    showNotice(e.message);
  }
  c.updated = Date.now(); state.busy = false; save(); render();
}
async function submit() {
  if (state.busy) return; const input = $("input"), text = input.value.trim(); if (!text) return;
  let c = active();
  if (!c) { c = { id: uid(), title: text.slice(0, 40), messages: [], updated: Date.now(), projectId: state.view !== "all" ? state.view : null }; state.convs.push(c); state.active = c.id; }
  c.messages.push({ role: "user", content: text }); c.updated = Date.now();
  input.value = ""; autosize(); save(); await respond(c);
}
async function regenerate() {
  const c = active(); if (!c || state.busy) return;
  while (c.messages.length && c.messages[c.messages.length - 1].role === "assistant") c.messages.pop();
  await respond(c);
}
async function editMsg(i) {
  const c = active(); if (!c || state.busy) return;
  const t = await ask("Edit message and resend", { input: true, value: c.messages[i].content, ok: "Resend" }); if (!t) return;
  c.messages = c.messages.slice(0, i); c.messages.push({ role: "user", content: t }); save(); await respond(c);
}
$("composer").onsubmit = e => { e.preventDefault(); submit(); };
const input = $("input");
function autosize() { input.style.height = "auto"; input.style.height = Math.min(input.scrollHeight, 200) + "px"; }
input.oninput = autosize;
input.onkeydown = e => { if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); submit(); } };

/* brain selector */
function closeBrain() { $("brainMenu").hidden = true; $("brainBtn").setAttribute("aria-expanded", "false"); }
function renderBrain() {
  const cur = BRAINS.find(b => b.id === state.brain) || BRAINS[0]; $("brainBtn").textContent = cur.name + " ▾";
  const ul = $("brainMenu"); ul.textContent = "";
  BRAINS.forEach(b => {
    const li = document.createElement("li"); li.setAttribute("role", "option"); li.tabIndex = 0; li.setAttribute("aria-selected", b.id === state.brain);
    li.innerHTML = "<strong></strong><small></small><small></small>";
    li.children[0].textContent = b.name; li.children[1].textContent = b.desc;
    li.children[2].textContent = "Availability: not checked";
    const pick = () => { state.brain = b.id; save(); renderBrain(); closeBrain(); };
    li.onclick = pick; li.onkeydown = e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(); } };
    ul.append(li);
  });
}
$("brainBtn").onclick = () => { const m = $("brainMenu"); m.hidden = !m.hidden; $("brainBtn").setAttribute("aria-expanded", String(!m.hidden)); };
document.addEventListener("keydown", e => { if (e.key === "Escape") { closeBrain(); $("ctx").hidden = true; } });

setPanel(store.get("ultron.projectsOpen", false) === true || state.view !== "all");
renderBrain(); render();
