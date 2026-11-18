# Architecture note

## Shape

```
Browser (vanilla JS SPA, contenteditable editor)
   │  JSON over fetch, session cookie
   ▼
Flask app ── api.py (routes, validation) ── access.py (role rules)
   │                                       ├─ sanitize.py (allowlist HTML)
   │                                       └─ importers.py (.txt/.md/.docx)
   ▼
SQLite: users · documents(content HTML, version) · document_shares(role)
```

One process serves both the API and the static frontend. That means one deploy, one URL, and no CORS.

## What I prioritized and why

1. **The core loop had to be solid before anything else.** That loop is create → edit with formatting → autosave → refresh → still there. Autosave runs one request at a time, flushes when you navigate away, warns on tab close with unsaved changes, and retries on network errors. Saving is invisible when it works, and losing work is the worst failure an editor can have.

2. **Access control lives on the server, in one place.** `access.role_for()` resolves owner / editor / viewer with a single query, and every route calls `require_role(doc, needed)`. The UI hides controls by role for usability, but the server is what enforces it. Inaccessible documents return 404, not 403, so their ids don't leak.

3. **Content is stored as sanitized HTML.** HTML is what `contenteditable` produces and what mammoth/markdown output, so the editor, the importers and storage all speak the same format with no conversion layer. The cost is that HTML is untrusted input. Every write therefore goes through an allowlist sanitizer: unknown tags are unwrapped, `script`/`style` are dropped along with their contents, attributes are stripped except safe `href`s, and `<b>`/`<div>` are normalized to `<strong>`/`<p>`. That blocks stored XSS whichever client sent the HTML, and keeps stored content consistent across browsers.

4. **Concurrent edits are detected, not merged.** Sharing means two editors can open the same document. Without protection, the last save would silently erase the other person's work. Each document has a `version`; a `PATCH` only applies `WHERE version = ?`, otherwise it returns 409 with the latest copy. The UI then offers *Load their version* or *Keep mine*. This costs about 20 lines and removes a real data-loss bug. Real-time merging (CRDT/OT) would be the next step, but it's days of work, not hours.

5. **Uploads became a real workflow, not a file locker.** Importing `.txt`/`.md`/`.docx` creates an editable document that keeps headings, emphasis and lists. That's what a docs product user expects. *Insert file* reuses the same converter for an existing draft. The supported types and the 2 MB limit are shown in the UI and enforced on the server.

6. **The stretch goal I took was role-based sharing** (viewer vs editor). It was cheap given the access module, and it makes the sharing demo more meaningful.

## Key decisions and tradeoffs

| Decision | Why | Cost |
|---|---|---|
| Flask + SQLite | Fewest moving parts to ship a testable build in the timebox. SQLite needs no external service (reviewers pay nothing). | Single-writer DB; the schema is plain SQL, so moving to Postgres is mechanical. |
| Vanilla JS, no build step | No bundler or toolchain to configure or break during deploy; the frontend is ~600 lines. | `document.execCommand` is deprecated (though still supported everywhere). A production editor would use TipTap/ProseMirror for a real document model, schema-driven paste and collaborative editing. |
| Mocked auth: seeded users + sessions | The brief allows it; real sign-up adds no signal for this exercise. | No registration or password reset. |
| Paste as plain text | Pasting from Word/Google Docs brings messy styles. Plain text is predictable. | You lose formatting when pasting; use *Import file* or reformat. |
| Hash routing (`#/doc/12`) | The server only serves one page, and deep links still work. | URLs are less clean. |
| Render free tier | Free and one-click from `render.yaml`. | Ephemeral disk: the database resets on redeploy or cold start. Fine for a demo; documented. |

## What I cut (deliberately)

- Real-time co-editing and presence (conflict detection covers the data-loss risk)
- Comments, suggestions, version history, export
- Images, tables, links UI, font/colour pickers
- Sign-up, password reset, sharing with people who aren't users yet
- Pagination or search on the document list

## Next 2–4 hours

1. **Version history.** Snapshot `(doc_id, version, content, user, time)` on each save, with a "restore" button. The version counter already exists.
2. **Presence and soft real-time.** Poll `GET /documents/:id` meta every ~10 s. Show "Bob is editing" and pull in remote changes when the local copy is clean.
3. **Durable hosting.** Use Postgres (e.g. a free Neon instance) behind the same SQL, so the live demo keeps data across redeploys.
4. **Export to Markdown/PDF.** Mostly reuses the HTML pipeline.
