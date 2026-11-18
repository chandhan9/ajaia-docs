"""Access-control rules in one place.

Roles, from most to least privileged:
  owner  - read, edit, rename, delete, manage sharing
  editor - read, edit, rename
  viewer - read only
"""
ROLE_RANK = {"viewer": 1, "editor": 2, "owner": 3}


def role_for(db, doc_id: int, user_id: int) -> str | None:
    """Return the user's role on a document, or None if they have no access
    (or the document does not exist; callers return 404 in both cases so we
    don't leak which document ids exist)."""
    row = db.execute(
        """
        SELECT CASE WHEN d.owner_id = :uid THEN 'owner' ELSE s.role END AS role
        FROM documents d
        LEFT JOIN document_shares s ON s.document_id = d.id AND s.user_id = :uid
        WHERE d.id = :doc
        """,
        {"uid": user_id, "doc": doc_id},
    ).fetchone()
    return row["role"] if row else None


def can(role: str | None, needed: str) -> bool:
    return role is not None and ROLE_RANK[role] >= ROLE_RANK[needed]
