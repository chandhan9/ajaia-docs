"""Convert uploaded files into sanitized document HTML.

Supported: .txt, .md/.markdown, .docx. Everything else is rejected with a clear
message (the same list is shown in the UI).
"""
import io
import os
from html import escape

import mammoth
import markdown as md

from .sanitize import sanitize_html

SUPPORTED_EXTENSIONS = {".txt", ".md", ".markdown", ".docx"}
MAX_UPLOAD_BYTES = 2 * 1024 * 1024  # 2 MB


class ImportErrorForUser(ValueError):
    """Raised with a message that is safe to show to the user."""


def _decode_text(raw: bytes) -> str:
    for enc in ("utf-8-sig", "utf-16"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise ImportErrorForUser("The file is not valid UTF-8 text.")


def _txt_to_html(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    paragraphs = [p for p in text.split("\n\n") if p.strip()]
    return "".join(
        "<p>" + "<br>".join(escape(line) for line in p.split("\n")) + "</p>"
        for p in paragraphs
    )


def _docx_to_html(raw: bytes) -> str:
    try:
        result = mammoth.convert_to_html(io.BytesIO(raw))
    except Exception as exc:  # mammoth raises various zip/xml errors on bad input
        raise ImportErrorForUser("Could not read this .docx file. Is it a valid Word document?") from exc
    return result.value


def file_to_document(filename: str, raw: bytes) -> tuple[str, str]:
    """Return (suggested_title, sanitized_html) for an uploaded file."""
    name = os.path.basename(filename or "").strip()
    stem, ext = os.path.splitext(name)
    ext = ext.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ImportErrorForUser(
            f"Unsupported file type '{ext or 'none'}'. Supported: .txt, .md, .docx."
        )
    if not raw:
        raise ImportErrorForUser("The file is empty.")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise ImportErrorForUser("File is larger than the 2 MB limit.")

    if ext == ".txt":
        html = _txt_to_html(_decode_text(raw))
    elif ext in (".md", ".markdown"):
        html = md.markdown(_decode_text(raw), extensions=["sane_lists"])
    else:
        html = _docx_to_html(raw)

    clean = sanitize_html(html)
    if not clean.strip():
        clean = "<p></p>"
    return (stem.strip() or "Imported document")[:200], clean
