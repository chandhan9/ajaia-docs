"""End-to-end API tests for the core product flows: create/edit/persist,
access control, sharing and concurrent-edit protection."""
from app import create_app


def create_doc(client, title="Plan", content="<p>hi</p>"):
    res = client.post("/api/documents", json={"title": title, "content": content})
    assert res.status_code == 201, res.get_json()
    return res.get_json()


def test_requires_login(app):
    res = app.test_client().get("/api/documents")
    assert res.status_code == 401
    assert res.get_json()["error"]


def test_bad_password_is_rejected(app):
    res = app.test_client().post("/api/auth/login",
                                 json={"email": "alice@ajaia.test", "password": "nope"})
    assert res.status_code == 401


def test_create_rename_edit_and_reopen_after_restart(alice, db_path):
    doc = create_doc(alice, "Draft", "<h1>Title</h1><p><b>bold</b> and <i>it</i></p>")
    res = alice.patch(f"/api/documents/{doc['id']}", json={
        "title": "  Q3   Roadmap ", "version": doc["version"],
        "content": "<h2>Goals</h2><ul><li><u>Ship</u></li></ul><ol><li>One</li></ol>",
    })
    assert res.status_code == 200
    assert res.get_json()["version"] == doc["version"] + 1

    # A brand-new app instance on the same database = server restart / page refresh.
    fresh = create_app({"DATABASE_PATH": db_path, "SECRET_KEY": "test"}).test_client()
    fresh.post("/api/auth/login", json={"email": "alice@ajaia.test", "password": "demo1234"})
    reopened = fresh.get(f"/api/documents/{doc['id']}").get_json()
    assert reopened["title"] == "Q3 Roadmap"
    assert reopened["content"] == "<h2>Goals</h2><ul><li><u>Ship</u></li></ul><ol><li>One</li></ol>"


def test_validation_errors(alice):
    doc = create_doc(alice)
    assert alice.post("/api/documents", json={"title": "   "}).status_code == 400
    assert alice.post("/api/documents", json={"title": "x" * 201}).status_code == 400
    # version is required so clients can't blindly overwrite
    assert alice.patch(f"/api/documents/{doc['id']}", json={"title": "x"}).status_code == 400
    assert alice.patch(f"/api/documents/{doc['id']}", json={"version": 1}).status_code == 400


def test_stored_content_is_sanitized(alice):
    doc = create_doc(alice, content='<p onclick="x()">ok<script>alert(1)</script>'
                                    '<img src=x onerror=alert(1)><a href="javascript:alert(1)">l</a></p>')
    html = alice.get(f"/api/documents/{doc['id']}").get_json()["content"]
    assert html == "<p>ok<a>l</a></p>"


def test_owned_vs_shared_lists(alice, bob):
    doc = create_doc(alice, "Alice private")
    bob_lists = bob.get("/api/documents").get_json()
    assert all(d["id"] != doc["id"] for d in bob_lists["owned"] + bob_lists["shared"])

    alice_lists = alice.get("/api/documents").get_json()
    assert doc["id"] in [d["id"] for d in alice_lists["owned"]]
    # The seeded welcome doc is owned by Alice and shared with Bob as editor.
    shared = bob_lists["shared"]
    assert [d["title"] for d in shared] == ["Welcome to Ajaia Docs"]
    assert shared[0]["role"] == "editor" and shared[0]["owner"]["name"] == "Alice Owner"


def test_sharing_grants_and_revokes_access(alice, bob, carol):
    doc = create_doc(alice)
    url = f"/api/documents/{doc['id']}"

    # Before sharing: Bob can't even tell the document exists.
    assert bob.get(url).status_code == 404

    # Non-owners can't manage sharing.
    assert bob.put(f"{url}/shares", json={"email": "bob@ajaia.test"}).status_code == 404

    # Owner grants Bob edit and Carol view access.
    assert alice.put(f"{url}/shares", json={"email": "bob@ajaia.test", "role": "editor"}).status_code == 200
    shares = alice.put(f"{url}/shares", json={"email": "CAROL@ajaia.test", "role": "viewer"}).get_json()
    assert {s["email"]: s["role"] for s in shares} == {"bob@ajaia.test": "editor", "carol@ajaia.test": "viewer"}

    # Editor can edit; viewer can read but not edit.
    v = bob.get(url).get_json()["version"]
    assert bob.patch(url, json={"content": "<p>bob was here</p>", "version": v}).status_code == 200
    assert carol.get(url).get_json()["content"] == "<p>bob was here</p>"
    assert carol.patch(url, json={"content": "<p>no</p>", "version": v + 1}).status_code == 403
    # Only the owner can delete or view the share list.
    assert bob.delete(url).status_code == 403
    assert bob.get(f"{url}/shares").status_code == 403

    # Revoke Bob: access disappears.
    bob_id = next(s["id"] for s in shares if s["email"] == "bob@ajaia.test")
    alice.delete(f"{url}/shares/{bob_id}")
    assert bob.get(url).status_code == 404


def test_share_validation(alice):
    doc = create_doc(alice)
    url = f"/api/documents/{doc['id']}/shares"
    assert alice.put(url, json={"email": "nobody@ajaia.test"}).status_code == 404
    assert alice.put(url, json={"email": "alice@ajaia.test"}).status_code == 400
    assert alice.put(url, json={"email": "bob@ajaia.test", "role": "admin"}).status_code == 400


def test_concurrent_edit_returns_conflict_instead_of_overwriting(alice, bob):
    doc = create_doc(alice)
    url = f"/api/documents/{doc['id']}"
    alice.put(f"{url}/shares", json={"email": "bob@ajaia.test", "role": "editor"})
    base = doc["version"]

    assert alice.patch(url, json={"content": "<p>alice</p>", "version": base}).status_code == 200
    stale = bob.patch(url, json={"content": "<p>bob</p>", "version": base})
    assert stale.status_code == 409
    body = stale.get_json()
    assert body["document"]["content"] == "<p>alice</p>"
    assert body["document"]["updated_by"] == "Alice Owner"
    # Bob can deliberately overwrite by sending the latest version.
    ok = bob.patch(url, json={"content": "<p>bob</p>", "version": body["document"]["version"]})
    assert ok.status_code == 200
