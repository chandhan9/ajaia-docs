# Submission: Ajaia Docs (Sai Chandhan Bonthala)

* **Live product URL:** `https://ajaia-docs-2wrh.onrender.com`
* **Walkthrough video:** see `VIDEO\_URL.txt`
* **Test accounts:** `alice@ajaia.test`, `bob@ajaia.test`, `carol@ajaia.test`, all with password `demo1234` (one-click buttons on the login page). The seeded welcome doc is owned by Alice, editable by Bob and view-only for Carol.

## What's included

|Item|Location|
|-|-|
|Source code|`app/` (Flask API), `static/` (frontend), `wsgi.py`|
|Local setup and run instructions|`README.md`|
|Architecture note|`ARCHITECTURE.md`|
|AI workflow note|`AI\_WORKFLOW.md`|
|Automated tests|`tests/` (pytest, 15 tests); `tests/e2e/browser-smoke.js` (Playwright)|
|Deployment config|`render.yaml` (Render), `Dockerfile`, `.github/workflows/test.yml` (CI)|
|Screenshots|`docs/screenshots/01–08`|
|Sample files for upload|`sample-files/` (`.md`, `.txt`, `.docx`)|
|Video link|`VIDEO\_URL.txt`|
|This file|`SUBMISSION.md`|

## Status

**Working end to end:** create / rename / edit / delete / reopen; rich text (B/I/U/S, H1–H3, bulleted and numbered lists, quote); autosave; `.txt`/`.md`/`.docx` import as a new document or into an open draft; sharing by email with editor/viewer roles, role changes and revoke; owned vs shared views; server-enforced access control; SQLite persistence; edit-conflict detection; HTML sanitizing.

**Incomplete or deliberately out of scope:** real-time co-editing and presence, comments, version history, export, images/tables, sign-up. On the free hosting tier the database resets on redeploy or cold start.

**Next 2–4 hours:** version history with restore, presence and polling for remote changes, Postgres for durable hosting, Markdown/PDF export. Details are in ARCHITECTURE.md.

