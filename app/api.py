"""JSON API. All routes live under /api and return JSON errors of the form
{"error": "<message>"} with an appropriate status code."""
from functools import wraps

from flask import Blueprint, jsonify, request, session
from werkzeug.security import check_password_hash

from .access import can, role_for
from .db import get_db, now_iso
from .importers import ImportErrorForUser, file_to_document
from .sanitize import sanitize_html

bp = Blueprint("api", __name__, url_prefix="/api")

MAX_TITLE = 200
MAX_CONTENT_BYTES = 1_000_000  # 1 MB of HTML per document


class ApiError(Exception):
    def __init__(self, status: int, message: str, **extra):
        super().__init__(message)
        self.status, self.message, self.extra = status, message, extra


@bp.errorhandler(ApiError)
def _handle_api_error(err: ApiError):
    return jsonify({"error": err.message, **err.extra}), err.status


# ---------------------------------------------------------------- helpers

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            raise ApiError(401, "Please sign in.")
        return fn(*args, **kwargs)
    return wrapper


def current_user_id() -> int:
    return session["user_id"]


def json_body() -> dict:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError(400, "Request body must be a JSON object.")
    return data


def clean_title(value) -> str:
    if not isinstance(value, str):
        raise ApiError(400, "Title must be a string.")
    title = " ".join(value.split())  # collapse whitespace / newlines
    if not title:
        raise ApiError(400, "Title cannot be empty.")
    if len(title) > MAX_TITLE:
        raise ApiError(400, f"Title must be at most {MAX_TITLE} characters.")
    return title


def clean_content(value) -> str:
    if not isinstance(value, str):
        raise ApiError(400, "Content must be a string of HTML.")
    if len(value.encode()) > MAX_CONTENT_BYTES:
        raise ApiError(413, "Document is too large (1 MB limit).")
    return sanitize_html(value)


def require_role(doc_id: int, needed: str) -> str:
    role = role_for(get_db(), doc_id, current_user_id())
    if role is None:
        raise ApiError(404, "Document not found.")
    if not can(role, needed):
        raise ApiError(403, f"You need {needed} access to do that.")
    return role


def serialize_doc(doc_id: int, role: str, include_content: bool = True) -> dict:
    db = get_db()
    row = db.execute(
        """SELECT d.*, o.name AS owner_name, o.email AS owner_email, ub.name AS updated_by_name
           FROM documents d JOIN users o ON o.id = d.owner_id
           LEFT JOIN users ub ON ub.id = d.updated_by
           WHERE d.id = ?""",
        (doc_id,),
    ).fetchone()
    out = {
        "id": row["id"],
        "title": row["title"],
        "version": row["version"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "updated_by": row["updated_by_name"],
        "owner": {"id": row["owner_id"], "name": row["owner_name"], "email": row["owner_email"]},
        "role": role,
    }
    if include_content:
        out["content"] = row["content"]
    return out


def list_shares(doc_id: int) -> list[dict]:
    rows = get_db().execute(
        """SELECT u.id, u.name, u.email, s.role FROM document_shares s
           JOIN users u ON u.id = s.user_id WHERE s.document_id = ? ORDER BY u.name""",
        (doc_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def insert_document(title: str, content: str) -> int:
    ts, uid = now_iso(), current_user_id()
    cur = get_db().execute(
        "INSERT INTO documents (owner_id, title, content, created_at, updated_at, updated_by)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (uid, title, content, ts, ts, uid),
    )
    get_db().commit()
    return cur.lastrowid


def uploaded_file():
    f = request.files.get("file")
    if f is None or not f.filename:
        raise ApiError(400, "Choose a file to upload (field name 'file').")
    try:
        return file_to_document(f.filename, f.read())
    except ImportErrorForUser as exc:
        raise ApiError(400, str(exc)) from exc


# ---------------------------------------------------------------- auth

@bp.post("/auth/login")
def login():
    data = json_body()
    email = str(data.get("email", "")).strip()
    password = str(data.get("password", ""))
    user = get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if user is None or not check_password_hash(user["password_hash"], password):
        raise ApiError(401, "Incorrect email or password.")
    session.clear()
    session["user_id"] = user["id"]
    session.permanent = True
    return jsonify({"id": user["id"], "name": user["name"], "email": user["email"]})


@bp.post("/auth/logout")
def logout():
    session.clear()
    return jsonify({"ok": True})


@bp.get("/auth/me")
@login_required
def me():
    user = get_db().execute("SELECT id, name, email FROM users WHERE id = ?",
                            (current_user_id(),)).fetchone()
    if user is None:  # user removed after the session was issued
        session.clear()
        raise ApiError(401, "Please sign in.")
    return jsonify(dict(user))


@bp.get("/users")
@login_required
def users():
    """Directory used by the share dialog (internal tool: all users are visible)."""
    rows = get_db().execute(
        "SELECT id, name, email FROM users WHERE id != ? ORDER BY name", (current_user_id(),)
    ).fetchall()
    return jsonify([dict(r) for r in rows])


# ---------------------------------------------------------------- documents

@bp.get("/documents")
@login_required
def list_documents():
    db, uid = get_db(), current_user_id()
    owned = db.execute(
        "SELECT id FROM documents WHERE owner_id = ? ORDER BY updated_at DESC", (uid,)
    ).fetchall()
    shared = db.execute(
        """SELECT d.id, s.role FROM documents d
           JOIN document_shares s ON s.document_id = d.id
           WHERE s.user_id = ? ORDER BY d.updated_at DESC""",
        (uid,),
    ).fetchall()
    return jsonify({
        "owned": [serialize_doc(r["id"], "owner", include_content=False) for r in owned],
        "shared": [serialize_doc(r["id"], r["role"], include_content=False) for r in shared],
    })


@bp.post("/documents")
@login_required
def create_document():
    data = request.get_json(silent=True) or {}
    title = clean_title(data.get("title", "Untitled document"))
    content = clean_content(data.get("content", ""))
    doc_id = insert_document(title, content)
    return jsonify(serialize_doc(doc_id, "owner")), 201


@bp.get("/documents/<int:doc_id>")
@login_required
def get_document(doc_id):
    role = require_role(doc_id, "viewer")
    out = serialize_doc(doc_id, role)
    if role == "owner":
        out["shares"] = list_shares(doc_id)
    return jsonify(out)


@bp.patch("/documents/<int:doc_id>")
@login_required
def update_document(doc_id):
    """Update title and/or content.

    Clients send the `version` they last loaded. If someone else saved in the
    meantime we return 409 with the latest document instead of silently
    overwriting their work (optimistic concurrency)."""
    require_role(doc_id, "editor")
    data = json_body()
    if "title" not in data and "content" not in data:
        raise ApiError(400, "Nothing to update: send 'title' and/or 'content'.")
    base_version = data.get("version")
    if not isinstance(base_version, int):
        raise ApiError(400, "Missing integer 'version' of the document you edited.")

    fields, params = [], []
    if "title" in data:
        fields.append("title = ?")
        params.append(clean_title(data["title"]))
    if "content" in data:
        fields.append("content = ?")
        params.append(clean_content(data["content"]))
    fields += ["version = version + 1", "updated_at = ?", "updated_by = ?"]
    params += [now_iso(), current_user_id(), doc_id, base_version]

    db = get_db()
    cur = db.execute(
        f"UPDATE documents SET {', '.join(fields)} WHERE id = ? AND version = ?", params
    )
    db.commit()
    role = role_for(db, doc_id, current_user_id())
    if cur.rowcount == 0:
        raise ApiError(409, "This document was changed by someone else since you opened it.",
                       document=serialize_doc(doc_id, role))
    return jsonify(serialize_doc(doc_id, role))


@bp.delete("/documents/<int:doc_id>")
@login_required
def delete_document(doc_id):
    require_role(doc_id, "owner")
    db = get_db()
    db.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    db.commit()
    return "", 204


# ---------------------------------------------------------------- file import

@bp.post("/documents/import")
@login_required
def import_new_document():
    """Upload .txt/.md/.docx -> new editable document owned by the caller."""
    title, html = uploaded_file()
    doc_id = insert_document(title, html)
    return jsonify(serialize_doc(doc_id, "owner")), 201


@bp.post("/documents/<int:doc_id>/import")
@login_required
def import_into_document(doc_id):
    """Upload a file and return its converted HTML for insertion into an open
    draft. Nothing is saved here: the editor inserts the HTML at the cursor and
    the normal (version-checked) save persists it."""
    require_role(doc_id, "editor")
    _title, html = uploaded_file()
    return jsonify({"html": html})


# ---------------------------------------------------------------- sharing

@bp.get("/documents/<int:doc_id>/shares")
@login_required
def get_shares(doc_id):
    require_role(doc_id, "owner")
    return jsonify(list_shares(doc_id))


@bp.put("/documents/<int:doc_id>/shares")
@login_required
def upsert_share(doc_id):
    """Grant (or change) a user's access by email."""
    require_role(doc_id, "owner")
    data = json_body()
    email = str(data.get("email", "")).strip()
    role = data.get("role", "editor")
    if role not in ("viewer", "editor"):
        raise ApiError(400, "Role must be 'viewer' or 'editor'.")
    if not email:
        raise ApiError(400, "Enter the email of the person to share with.")
    db = get_db()
    target = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if target is None:
        raise ApiError(404, f"No user with email {email}.")
    if target["id"] == current_user_id():
        raise ApiError(400, "You already own this document.")
    db.execute(
        """INSERT INTO document_shares (document_id, user_id, role, created_at)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(document_id, user_id) DO UPDATE SET role = excluded.role""",
        (doc_id, target["id"], role, now_iso()),
    )
    db.commit()
    return jsonify(list_shares(doc_id))


@bp.delete("/documents/<int:doc_id>/shares/<int:user_id>")
@login_required
def remove_share(doc_id, user_id):
    require_role(doc_id, "owner")
    db = get_db()
    db.execute("DELETE FROM document_shares WHERE document_id = ? AND user_id = ?",
               (doc_id, user_id))
    db.commit()
    return jsonify(list_shares(doc_id))
