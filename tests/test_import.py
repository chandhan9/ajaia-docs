"""File upload: .txt / .md / .docx become editable documents with structure kept."""
import io

import docx  # python-docx, used only to build a realistic test fixture

from app.sanitize import sanitize_html


def upload(client, url, name, data: bytes):
    return client.post(url, data={"file": (io.BytesIO(data), name)},
                       content_type="multipart/form-data")


def test_import_markdown_creates_formatted_document(alice):
    md = b"# Launch plan\n\nShip **fast** and _safely_.\n\n- one\n- two\n\n1. first\n2. second\n"
    res = upload(alice, "/api/documents/import", "launch-plan.md", md)
    assert res.status_code == 201
    doc = res.get_json()
    assert doc["title"] == "launch-plan" and doc["role"] == "owner"
    html = doc["content"]
    for fragment in ("<h1>Launch plan</h1>", "<strong>fast</strong>", "<em>safely</em>",
                     "<ul>", "<li>one</li>", "<ol>"):
        assert fragment in html
    # And it shows up in the owner's list.
    assert doc["id"] in [d["id"] for d in alice.get("/api/documents").get_json()["owned"]]


def test_import_txt_keeps_paragraphs_and_escapes_markup(alice):
    res = upload(alice, "/api/documents/import", "notes.txt", b"line 1\nline 2\n\n<b>not bold</b>")
    assert res.get_json()["content"] == "<p>line 1<br>line 2</p><p>&lt;b&gt;not bold&lt;/b&gt;</p>"


def test_import_docx(alice):
    d = docx.Document()
    d.add_heading("Quarterly review", level=1)
    p = d.add_paragraph("Revenue is ")
    p.add_run("up").bold = True
    d.add_paragraph("Hire two engineers", style="List Bullet")
    buf = io.BytesIO()
    d.save(buf)
    res = upload(alice, "/api/documents/import", "review.docx", buf.getvalue())
    assert res.status_code == 201, res.get_json()
    html = res.get_json()["content"]
    assert "<h1>Quarterly review</h1>" in html
    assert "<strong>up</strong>" in html
    assert "<li>Hire two engineers</li>" in html


def test_import_rejects_unsupported_and_bad_files(alice):
    res = upload(alice, "/api/documents/import", "photo.png", b"\x89PNG....")
    assert res.status_code == 400 and ".txt, .md, .docx" in res.get_json()["error"]
    assert upload(alice, "/api/documents/import", "empty.txt", b"").status_code == 400
    assert upload(alice, "/api/documents/import", "fake.docx", b"not a zip").status_code == 400
    assert alice.post("/api/documents/import").status_code == 400  # no file at all


def test_insert_file_into_existing_draft_requires_edit_access(alice, carol):
    welcome_id = alice.get("/api/documents").get_json()["owned"][0]["id"]
    ok = upload(alice, f"/api/documents/{welcome_id}/import", "a.md", b"**hi**")
    assert ok.status_code == 200 and ok.get_json()["html"] == "<p><strong>hi</strong></p>"
    # Carol is a viewer on the welcome doc.
    assert upload(carol, f"/api/documents/{welcome_id}/import", "a.md", b"hi").status_code == 403


def test_sanitizer_normalises_and_closes_tags():
    assert sanitize_html("<div><b>x</b><i>y") == "<p><strong>x</strong><em>y</em></p>"
    assert sanitize_html('<a href="https://x.io" onclick="e()">x</a>') == \
        '<a href="https://x.io" rel="noopener noreferrer" target="_blank">x</a>'
    assert sanitize_html("<style>p{}</style><p>k</p>") == "<p>k</p>"
    assert sanitize_html("<span style='color:red'>t</span>") == "t"
    # empty blocks keep a <br> so blank lines survive a reload
    assert sanitize_html("<p></p><p><br></p>") == "<p><br></p><p><br></p>"
