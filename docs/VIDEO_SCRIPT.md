# Walkthrough video outline (3–5 min)

Not a deliverable; just a guide for recording. Use two browser windows (one normal, one incognito) so you can be Alice and Carol/Bob at the same time.

**0:00–0:20 · Framing.** "A lightweight Google-Docs-style editor. I focused on a reliable editing loop, real sharing with roles, and file import, and I cut real-time co-editing on purpose."

**0:20–1:30 · Main flow (as Alice).**
- Click *Alice* on the login page. Point out *My documents* vs *Shared with me*.
- *+ New document*, rename it, then type a heading, bold/italic/underline text, and a bulleted and a numbered list. Point at the status going *Saving… → All changes saved*.
- Refresh the page: everything is still there.

**1:30–2:15 · File upload.**
- Home → *Import file* → `sample-files/q4-hiring-plan.docx`. Headings, bold and bullets survive.
- Try a `.pdf` to show the clear rejection message. Optionally use *Insert file* inside a doc.

**2:15–3:15 · Sharing.**
- *Share* → add `carol@ajaia.test` as *Can view*. Show the validation error for an unknown email.
- In the other window, sign in as Carol: the doc is under *Shared with me* with a *View only* badge, and it opens read-only with no toolbar or Share button.
- Conflict demo: Bob and Alice both open *Welcome*. Bob edits and saves, then Alice edits, and the conflict banner appears.

**3:15–4:15 · Decisions.**
- Server-side access control in one module; inaccessible docs return 404.
- Content stored as sanitized HTML: why that format, and the XSS allowlist.
- Optimistic versioning instead of last-write-wins.
- Cut: real-time co-editing, comments, history. Free-tier hosting resets data on redeploy.

**4:15–5:00 · AI workflow.** Built with Claude. Verified with pytest and a Playwright browser run, which caught the empty-paragraph bug. Name what you changed or rejected (see AI_WORKFLOW.md), and mention anything you reviewed or rewrote yourself.
