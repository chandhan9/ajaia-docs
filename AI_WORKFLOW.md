# AI workflow note

> **Sai: review and edit this before submitting.** It records what happened while building with Claude. Add your own review steps, and anything you change after this point, in your own words. Reviewers will ask you about it in the video.

## Tools used

- **Claude (Anthropic), agentic mode:** scaffolding, the backend and frontend code, tests, a Playwright browser test, and first drafts of the docs.
- **pytest + Playwright:** the verification layer. AI-written code was only accepted once it passed these.

## Where AI materially sped things up

- **Boilerplate with a known shape:** the Flask app factory, SQLite schema, JSON error handling, CSS, and the share dialog. Hours became minutes.
- **Library glue:** mammoth for `.docx` → HTML, and Markdown for `.md`, plus making a realistic `.docx` test fixture with python-docx.
- **Test breadth:** 15 API tests and a full browser walk-through (login → format → reload → share → import → viewer → conflict) that also produced the screenshots.

## What I changed or rejected

- **Empty paragraphs collapsed after reload.** The browser test showed blank lines stored as `<p></p>`, which render at zero height and can't hold the cursor. The sanitizer now keeps empty blocks as `<p><br></p>`, with a regression test.
- **Bold looked "on" inside headings.** `queryCommandState('bold')` reports headings as bold. I suppressed that so the toolbar shows what the user actually applied.
- **Badges stretched across the document cards.** A flex layout issue caught when reviewing screenshots; fixed.
- **Rejected client-side sanitizing as the defence.** The sanitizer runs on the server on every write, so the raw API and the importers are covered too, not just the UI.
- **Rejected rich-HTML paste.** Pasted HTML from other apps brings inline styles and odd markup; plain-text paste is predictable for this scope.
- **Rejected last-write-wins saving.** I added version-checked saves (409 + a resolve banner) once sharing made concurrent edits possible.
- **Kept scope tight.** I didn't add real-time co-editing, comments or version history. Each would have been shallow in the timebox; see ARCHITECTURE.md.
- *(Add your own items here: anything you rewrote or pushed back on while reviewing.)*

## How correctness, UX and reliability were verified

- **API tests (`pytest -q`):** access rules for each role, sharing lifecycle, 404 for non-shared documents, validation errors, the XSS payload stripped, persistence across a fresh app instance on the same DB, conflict detection, and each import type plus bad files.
- **Real browser run (`tests/e2e/browser-smoke.js`):** drove the actual UI in Chromium with three users, asserted the saved HTML after reload, and failed on any JavaScript error. It found the empty-paragraph bug that the API tests couldn't.
- **Screenshot review:** checked every screen in `docs/screenshots/` by eye for layout and copy problems.
- **Manual pass:** *(add what you clicked through yourself on the deployed URL).*
