/* Ajaia Docs: single-page frontend (vanilla JS, no build step).
 *
 * Routes (hash-based so the Flask server only serves one page):
 *   #/          document list (owned + shared)
 *   #/doc/:id   editor
 */
"use strict";

const SUPPORTED_UPLOADS = ".txt,.md,.markdown,.docx";
const UPLOAD_HINT = "Supported: .txt, .md, .docx (max 2 MB)";
const AUTOSAVE_MS = 800;
const DEMO_ACCOUNTS = [
  { email: "alice@ajaia.test", label: "Alice", note: "owns the welcome doc" },
  { email: "bob@ajaia.test", label: "Bob", note: "editor on it" },
  { email: "carol@ajaia.test", label: "Carol", note: "viewer on it" },
];
const DEMO_PASSWORD = "demo1234";

const app = document.getElementById("app");
let me = null;          // signed-in user
let editor = null;      // active editor state, see openEditor()

/* ------------------------------------------------------------------ utils */

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === false || v == null) continue;
    if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else if (k === "class") node.className = v;
    else if (v === true) node.setAttribute(k, "");
    else node.setAttribute(k, v);
  }
  for (const c of children.flat()) {
    if (c == null || c === false) continue;
    node.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return node;
}

let toastTimer;
function toast(message, kind = "info") {
  const t = document.getElementById("toast");
  t.textContent = message;
  t.className = kind;
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (t.hidden = true), 4000);
}

function timeAgo(iso) {
  const s = Math.round((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 45) return "just now";
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  if (s < 86400) return `${Math.round(s / 3600)} h ago`;
  return new Date(iso).toLocaleDateString();
}

class HttpError extends Error {
  constructor(status, body) {
    super((body && body.error) || `Request failed (${status})`);
    this.status = status;
    this.body = body;
  }
}

async function api(path, { method = "GET", body, form } = {}) {
  const opts = { method, headers: {}, credentials: "same-origin" };
  if (form) opts.body = form;
  else if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  let res;
  try {
    res = await fetch(`/api${path}`, opts);
  } catch {
    throw new HttpError(0, { error: "Network error: check your connection." });
  }
  if (res.status === 204) return null;
  const data = await res.json().catch(() => null);
  if (res.status === 401 && path !== "/auth/login" && path !== "/auth/me") {
    me = null;
    renderLogin("Your session expired. Please sign in again.");
  }
  if (!res.ok) throw new HttpError(res.status, data);
  return data;
}

function roleBadge(role) {
  const label = { owner: "Owner", editor: "Can edit", viewer: "View only" }[role];
  return el("span", { class: `badge badge-${role}` }, label);
}

function filePicker(onFile) {
  const input = el("input", { type: "file", accept: SUPPORTED_UPLOADS, hidden: true });
  input.addEventListener("change", () => {
    const f = input.files[0];
    input.value = "";
    if (f) onFile(f);
  });
  document.body.append(input);
  input.click();
  setTimeout(() => input.remove(), 60_000);
}

/* ------------------------------------------------------------------ routing */

async function route() {
  if (editor) await editor.teardown();
  if (!me) {
    try { me = await api("/auth/me"); } catch { return renderLogin(); }
  }
  const m = location.hash.match(/^#\/doc\/(\d+)$/);
  if (m) return openEditor(Number(m[1]));
  return renderHome();
}
window.addEventListener("hashchange", route);

/* ------------------------------------------------------------------ login */

function renderLogin(message) {
  if (editor) editor.teardown();
  const error = el("p", { class: "error small", hidden: !message }, message || "");
  const email = el("input", { type: "email", id: "email", required: true, autocomplete: "username", placeholder: "you@ajaia.test" });
  const password = el("input", { type: "password", id: "password", required: true, autocomplete: "current-password" });
  const submit = el("button", { class: "btn primary wide", type: "submit" }, "Sign in");

  async function doLogin(e) {
    e && e.preventDefault();
    submit.disabled = true;
    error.hidden = true;
    try {
      me = await api("/auth/login", { method: "POST", body: { email: email.value, password: password.value } });
      location.hash = "#/";
      route();
    } catch (err) {
      error.textContent = err.message;
      error.hidden = false;
    } finally {
      submit.disabled = false;
    }
  }

  app.replaceChildren(
    el("main", { class: "login" },
      el("form", { class: "card login-card", onsubmit: doLogin },
        el("div", { class: "brand big" }, el("span", { class: "logo" }, "A"), "Ajaia Docs"),
        el("label", { for: "email" }, "Email"), email,
        el("label", { for: "password" }, "Password"), password,
        error, submit,
        el("div", { class: "demo" },
          el("p", { class: "small muted" }, `Demo accounts (password `, el("code", {}, DEMO_PASSWORD), `):`),
          el("div", { class: "demo-buttons" },
            DEMO_ACCOUNTS.map((a) =>
              el("button", {
                type: "button", class: "btn demo-btn",
                onclick: () => { email.value = a.email; password.value = DEMO_PASSWORD; doLogin(); },
              }, el("strong", {}, a.label), el("span", { class: "small muted" }, a.note))
            )
          )
        )
      )
    )
  );
  email.focus();
}

async function logout() {
  if (editor) await editor.teardown();
  await api("/auth/logout", { method: "POST" }).catch(() => {});
  me = null;
  location.hash = "#/";
  renderLogin();
}

function topbar(...middle) {
  return el("header", { class: "topbar" },
    el("a", { class: "brand", href: "#/" }, el("span", { class: "logo" }, "A"), "Ajaia Docs"),
    el("div", { class: "topbar-middle" }, ...middle),
    el("div", { class: "user" },
      el("span", { class: "avatar", title: me.email }, me.name[0]),
      el("span", { class: "user-name" }, me.name),
      el("button", { class: "btn ghost small", onclick: logout }, "Sign out")
    )
  );
}

/* ------------------------------------------------------------------ home */

async function renderHome() {
  document.title = "Ajaia Docs";
  const owned = el("div", { class: "doc-grid" }, el("p", { class: "muted" }, "Loading…"));
  const shared = el("div", { class: "doc-grid" });

  async function createBlank() {
    try {
      const doc = await api("/documents", { method: "POST", body: { title: "Untitled document" } });
      location.hash = `#/doc/${doc.id}`;
    } catch (err) { toast(err.message, "error"); }
  }

  function importFile() {
    filePicker(async (file) => {
      const form = new FormData();
      form.append("file", file);
      toast(`Importing ${file.name}…`);
      try {
        const doc = await api("/documents/import", { method: "POST", form });
        toast(`Imported “${doc.title}”`, "success");
        location.hash = `#/doc/${doc.id}`;
      } catch (err) { toast(err.message, "error"); }
    });
  }

  app.replaceChildren(
    topbar(),
    el("main", { class: "home" },
      el("section", { class: "home-actions" },
        el("button", { class: "btn primary", onclick: createBlank }, "+ New document"),
        el("button", { class: "btn", onclick: importFile }, "Import file"),
        el("span", { class: "small muted" }, `Import creates a new editable document. ${UPLOAD_HINT}.`)
      ),
      el("h2", {}, "My documents"), owned,
      el("h2", {}, "Shared with me"), shared
    )
  );

  let data;
  try { data = await api("/documents"); } catch (err) {
    owned.replaceChildren(el("p", { class: "error" }, err.message));
    return;
  }

  const card = (d) => el("a", { class: "doc-card", href: `#/doc/${d.id}` },
    el("div", { class: "doc-thumb" }, el("span", {}, "≡")),
    el("div", { class: "doc-meta" },
      el("div", { class: "doc-title" }, d.title),
      el("div", { class: "small muted" },
        d.role === "owner" ? `Edited ${timeAgo(d.updated_at)}` : `${d.owner.name} · ${timeAgo(d.updated_at)}`),
      roleBadge(d.role)
    ),
    d.role === "owner" && el("button", {
      class: "icon-btn danger", title: "Delete document", "aria-label": `Delete ${d.title}`,
      onclick: async (e) => {
        e.preventDefault();
        if (!confirm(`Delete “${d.title}”? This cannot be undone.`)) return;
        try { await api(`/documents/${d.id}`, { method: "DELETE" }); renderHome(); }
        catch (err) { toast(err.message, "error"); }
      },
    }, "🗑")
  );

  owned.replaceChildren(...(data.owned.length ? data.owned.map(card)
    : [el("p", { class: "empty muted" }, "No documents yet. Create one or import a file.")]));
  shared.replaceChildren(...(data.shared.length ? data.shared.map(card)
    : [el("p", { class: "empty muted" }, "Nothing has been shared with you yet.")]));
}

/* ------------------------------------------------------------------ editor */

const TOOLBAR = [
  { cmd: "bold", label: "B", title: "Bold (Ctrl/Cmd+B)", cls: "b" },
  { cmd: "italic", label: "I", title: "Italic (Ctrl/Cmd+I)", cls: "i" },
  { cmd: "underline", label: "U", title: "Underline (Ctrl/Cmd+U)", cls: "u" },
  { cmd: "strikeThrough", label: "S", title: "Strikethrough", cls: "s" },
  "sep",
  { block: "p", label: "Normal", title: "Normal text" },
  { block: "h1", label: "H1", title: "Heading 1" },
  { block: "h2", label: "H2", title: "Heading 2" },
  { block: "h3", label: "H3", title: "Heading 3" },
  "sep",
  { cmd: "insertUnorderedList", label: "• List", title: "Bulleted list" },
  { cmd: "insertOrderedList", label: "1. List", title: "Numbered list" },
  { block: "blockquote", label: "❝", title: "Quote" },
  "sep",
  { cmd: "undo", label: "↶", title: "Undo (Ctrl/Cmd+Z)" },
  { cmd: "redo", label: "↷", title: "Redo (Ctrl/Cmd+Shift+Z)" },
  { cmd: "removeFormat", label: "Tx", title: "Clear formatting" },
];

async function openEditor(docId) {
  app.replaceChildren(topbar(), el("main", { class: "editor-loading muted" }, "Loading document…"));
  let doc;
  try {
    doc = await api(`/documents/${docId}`);
  } catch (err) {
    app.replaceChildren(topbar(), el("main", { class: "home" },
      el("p", { class: "error" }, err.status === 404 ? "This document doesn't exist or you don't have access to it." : err.message),
      el("a", { href: "#/", class: "btn" }, "← Back to documents")));
    return;
  }

  const canEdit = doc.role === "owner" || doc.role === "editor";
  const state = {
    doc, version: doc.version, dirty: false, saving: null, timer: null,
    conflict: false, lastRange: null, teardown: null,
  };
  editor = state;
  document.title = `${doc.title} · Ajaia Docs`;

  const status = el("span", { class: "save-status small muted", "aria-live": "polite" }, "All changes saved");
  const title = el("input", {
    class: "title-input", value: doc.title, maxlength: 200, "aria-label": "Document title",
    readonly: !canEdit,
  });
  const page = el("div", {
    class: "page", id: "editor", contenteditable: canEdit ? "true" : "false",
    role: "textbox", "aria-multiline": "true", "aria-label": "Document content", spellcheck: "true",
  });
  page.innerHTML = doc.content || "<p><br></p>";   // content was sanitized server-side

  const banner = el("div", { class: "banner", hidden: true });

  function setStatus(text, kind = "") {
    status.textContent = text;
    status.className = `save-status small ${kind || "muted"}`;
  }

  /* ---- saving: one in-flight request at a time, version-checked ---- */
  function markDirty() {
    if (!canEdit || state.conflict) return;
    state.dirty = true;
    setStatus("Unsaved changes…");
    clearTimeout(state.timer);
    state.timer = setTimeout(save, AUTOSAVE_MS);
  }

  async function save() {
    clearTimeout(state.timer);
    if (!state.dirty || state.conflict) return;
    if (state.saving) { await state.saving; return save(); }
    const titleValue = title.value.trim() || "Untitled document";
    state.dirty = false;
    setStatus("Saving…");
    state.saving = (async () => {
      try {
        const updated = await api(`/documents/${doc.id}`, {
          method: "PATCH",
          body: { title: titleValue, content: page.innerHTML, version: state.version },
        });
        state.version = updated.version;
        document.title = `${updated.title} · Ajaia Docs`;
        setStatus(state.dirty ? "Unsaved changes…" : "All changes saved");
      } catch (err) {
        state.dirty = true;
        if (err.status === 409) return showConflict(err.body.document);
        setStatus("Not saved", "error");
        toast(`Save failed: ${err.message}`, "error");
        if (err.status !== 401 && err.status !== 403) state.timer = setTimeout(save, 5000); // retry
      } finally {
        state.saving = null;
      }
    })();
    return state.saving;
  }

  function showConflict(latest) {
    state.conflict = true;
    setStatus("Conflict", "error");
    banner.replaceChildren(
      el("span", {}, `${latest.updated_by || "Someone"} saved a newer version of this document while you were editing.`),
      el("button", { class: "btn small", onclick: () => {
        page.innerHTML = latest.content || "<p><br></p>";
        title.value = latest.title;
        state.version = latest.version;
        resolve("Loaded the latest version.");
      } }, "Load their version"),
      el("button", { class: "btn small primary", onclick: () => {
        state.version = latest.version;   // overwrite on purpose
        resolve(null);
        state.dirty = true;
        save();
      } }, "Keep mine (overwrite)")
    );
    banner.hidden = false;
    function resolve(msg) {
      state.conflict = false;
      state.dirty = false;
      banner.hidden = true;
      setStatus("All changes saved");
      if (msg) toast(msg);
    }
  }

  /* ---- toolbar ---- */
  const buttons = [];
  const toolbar = el("div", { class: "toolbar", role: "toolbar", "aria-label": "Formatting" },
    TOOLBAR.map((t) => {
      if (t === "sep") return el("span", { class: "sep" });
      const b = el("button", {
        type: "button", class: `tool ${t.cls || ""}`, title: t.title, "aria-label": t.title,
        onmousedown: (e) => e.preventDefault(), // keep the editor selection
        onclick: () => {
          page.focus();
          if (t.block) document.execCommand("formatBlock", false, t.block);
          else document.execCommand(t.cmd, false, null);
          markDirty();
          refreshToolbar();
        },
      }, t.label);
      buttons.push([t, b]);
      return b;
    }),
    el("span", { class: "sep" }),
    el("button", {
      type: "button", class: "tool wide-tool", title: `Insert a file's content at the cursor. ${UPLOAD_HINT}`,
      onmousedown: (e) => e.preventDefault(),
      onclick: insertFromFile,
    }, "⤓ Insert file")
  );

  function currentBlock() {
    const sel = window.getSelection();
    if (!sel.rangeCount) return null;
    let n = sel.anchorNode;
    while (n && n !== page) {
      if (n.nodeType === 1 && /^(P|H1|H2|H3|BLOCKQUOTE|LI|PRE)$/.test(n.nodeName)) return n.nodeName.toLowerCase();
      n = n.parentNode;
    }
    return n === page ? "p" : null;
  }

  function refreshToolbar() {
    if (!page.contains(window.getSelection().anchorNode)) return;
    const block = currentBlock();
    for (const [t, b] of buttons) {
      let on = false;
      if (t.block) on = block === t.block;
      else if (["bold", "italic", "underline", "strikeThrough", "insertUnorderedList", "insertOrderedList"].includes(t.cmd)) {
        try { on = document.queryCommandState(t.cmd); } catch { on = false; }
        // Headings are bold by style; don't light up the Bold button for them.
        if (t.cmd === "bold" && /^h[1-3]$/.test(block || "")) on = false;
      }
      b.classList.toggle("active", on);
      b.setAttribute("aria-pressed", String(on));
    }
  }

  function onSelectionChange() {
    const sel = window.getSelection();
    if (sel.rangeCount && page.contains(sel.anchorNode)) {
      state.lastRange = sel.getRangeAt(0).cloneRange();
      refreshToolbar();
    }
  }

  function insertFromFile() {
    filePicker(async (file) => {
      const form = new FormData();
      form.append("file", file);
      try {
        const { html } = await api(`/documents/${doc.id}/import`, { method: "POST", form });
        page.focus();
        const sel = window.getSelection();
        sel.removeAllRanges();
        if (state.lastRange) sel.addRange(state.lastRange);
        else { const r = document.createRange(); r.selectNodeContents(page); r.collapse(false); sel.addRange(r); }
        document.execCommand("insertHTML", false, html);
        markDirty();
        toast(`Inserted ${file.name}`, "success");
      } catch (err) { toast(err.message, "error"); }
    });
  }

  /* ---- events ---- */
  page.addEventListener("input", markDirty);
  page.addEventListener("paste", (e) => {
    // Paste as plain text (line breaks kept) so foreign styles never leak in.
    if (!canEdit) return;
    e.preventDefault();
    const text = e.clipboardData.getData("text/plain");
    document.execCommand("insertText", false, text);
  });
  page.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") { e.preventDefault(); state.dirty = true; save(); }
  });
  title.addEventListener("input", markDirty);
  title.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); page.focus(); } });
  document.addEventListener("selectionchange", onSelectionChange);
  const beforeUnload = (e) => { if (state.dirty || state.saving) { e.preventDefault(); e.returnValue = ""; } };
  window.addEventListener("beforeunload", beforeUnload);

  state.teardown = async () => {
    document.removeEventListener("selectionchange", onSelectionChange);
    window.removeEventListener("beforeunload", beforeUnload);
    if (state.dirty && !state.conflict) await save();   // flush before leaving
    clearTimeout(state.timer);
    if (editor === state) editor = null;
  };

  try { document.execCommand("defaultParagraphSeparator", false, "p"); } catch { /* older browsers */ }

  const shareBtn = doc.role === "owner" &&
    el("button", { class: "btn primary", onclick: () => openShareDialog(doc) }, "Share");

  app.replaceChildren(
    topbar(
      el("a", { href: "#/", class: "btn ghost small", title: "Back to documents" }, "←"),
      title, roleBadge(doc.role), status, shareBtn
    ),
    canEdit ? toolbar : el("div", { class: "readonly-note" },
      `You have view-only access. ${doc.owner.name} owns this document.`),
    banner,
    el("main", { class: "editor-wrap" }, page)
  );
  if (canEdit && !page.textContent.trim()) page.focus();
}

/* ------------------------------------------------------------------ sharing */

async function openShareDialog(doc) {
  const dialog = document.getElementById("share-dialog");
  const form = document.getElementById("share-form");
  const emailInput = document.getElementById("share-email");
  const roleSelect = document.getElementById("share-role");
  const errorEl = document.getElementById("share-error");
  const list = document.getElementById("share-list");
  const directory = document.getElementById("user-directory");

  const showError = (msg) => { errorEl.textContent = msg; errorEl.hidden = !msg; };

  function renderShares(shares) {
    list.replaceChildren(
      el("li", {}, el("span", {}, el("strong", {}, `${me.name} (you)`), el("br"), el("span", { class: "small muted" }, me.email)),
        el("span", { class: "small muted" }, "Owner")),
      ...shares.map((s) => {
        const sel = el("select", { "aria-label": `Access for ${s.name}`,
          onchange: () => save(s.email, sel.value) },
          el("option", { value: "editor", selected: s.role === "editor" }, "Can edit"),
          el("option", { value: "viewer", selected: s.role === "viewer" }, "Can view"));
        return el("li", {},
          el("span", {}, el("strong", {}, s.name), el("br"), el("span", { class: "small muted" }, s.email)),
          el("span", { class: "share-controls" }, sel,
            el("button", { type: "button", class: "icon-btn danger", title: `Remove ${s.name}`, "aria-label": `Remove ${s.name}`,
              onclick: async () => {
                try { renderShares(await api(`/documents/${doc.id}/shares/${s.id}`, { method: "DELETE" })); }
                catch (err) { showError(err.message); }
              } }, "✕")));
      })
    );
  }

  async function save(email, role) {
    showError("");
    try {
      renderShares(await api(`/documents/${doc.id}/shares`, { method: "PUT", body: { email, role } }));
      return true;
    } catch (err) { showError(err.message); return false; }
  }

  form.onsubmit = async (e) => {
    e.preventDefault();
    if (await save(emailInput.value.trim(), roleSelect.value)) {
      toast(`Shared with ${emailInput.value.trim()}`, "success");
      emailInput.value = "";
    }
  };
  document.getElementById("share-close").onclick = () => dialog.close();

  showError("");
  emailInput.value = "";
  list.replaceChildren(el("li", { class: "muted" }, "Loading…"));
  dialog.showModal();
  emailInput.focus();
  try {
    const [shares, users] = await Promise.all([api(`/documents/${doc.id}/shares`), api("/users")]);
    renderShares(shares);
    directory.replaceChildren(...users.map((u) => el("option", { value: u.email }, u.name)));
  } catch (err) { showError(err.message); }
}

route();
