"""Allowlist HTML sanitizer for document content.

The editor stores rich text as HTML. Anything that reaches the database passes
through `sanitize_html`, so stored XSS is blocked regardless of which client
(editor, importer, raw API call) produced the HTML.

Rules:
- Only tags in ALLOWED_TAGS survive. Disallowed tags are unwrapped (their text
  is kept), except DROP_WITH_CONTENT tags (script, style, ...) which are removed
  together with everything inside them.
- All attributes are stripped except `href` on <a>, and only for http(s)/mailto.
- Browser-specific synonyms are normalised (<b> -> <strong>, <div> -> <p>, ...),
  so stored content stays consistent across browsers.
"""
from html import escape
from html.parser import HTMLParser

ALLOWED_TAGS = {
    "p", "br", "strong", "em", "u", "s", "h1", "h2", "h3",
    "ul", "ol", "li", "blockquote", "pre", "code", "a",
}
VOID_TAGS = {"br"}
RENAME = {"b": "strong", "i": "em", "strike": "s", "del": "s", "div": "p",
          "h4": "h3", "h5": "h3", "h6": "h3"}
DROP_WITH_CONTENT = {"script", "style", "iframe", "object", "embed", "noscript",
                     "template", "svg", "math", "head", "title"}
KEEP_HEIGHT = {"p", "h1", "h2", "h3", "li", "blockquote"}
SAFE_URL_PREFIXES =("http://", "https://", "mailto:")


class _Sanitizer(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.open: list[str] = []   # stack of tags we actually emitted
        self.drop_depth = 0         # >0 while inside a DROP_WITH_CONTENT element

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in DROP_WITH_CONTENT:
            self.drop_depth += 1
            return
        if self.drop_depth:
            return
        tag = RENAME.get(tag, tag)
        if tag not in ALLOWED_TAGS:
            return  # unwrap: skip the tag, keep its children
        if tag in VOID_TAGS:
            self.out.append(f"<{tag}>")
            return
        attr_str = ""
        if tag == "a":
            href = dict(attrs).get("href") or ""
            if href.strip().lower().startswith(SAFE_URL_PREFIXES):
                attr_str = f' href="{escape(href.strip(), quote=True)}" rel="noopener noreferrer" target="_blank"'
        self.out.append(f"<{tag}{attr_str}>")
        self.open.append(tag)

    def handle_startendtag(self, tag, attrs):
        if RENAME.get(tag.lower(), tag.lower()) in VOID_TAGS:
            self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in DROP_WITH_CONTENT:
            self.drop_depth = max(0, self.drop_depth - 1)
            return
        if self.drop_depth:
            return
        tag = RENAME.get(tag, tag)
        if tag not in self.open:
            return  # stray close tag
        # Close everything opened after `tag` so output is always well-formed.
        while self.open:
            t = self.open.pop()
            if t in KEEP_HEIGHT and self.out and self.out[-1] == f"<{t}>":
                # Empty blocks collapse to zero height in a browser and can't
                # hold the cursor; keep them as a visible blank line.
                self.out.append("<br>")
            self.out.append(f"</{t}>")
            if t == tag:
                break

    def handle_data(self, data):
        if not self.drop_depth:
            self.out.append(escape(data, quote=False))

    def result(self) -> str:
        while self.open:
            self.out.append(f"</{self.open.pop()}>")
        return "".join(self.out)


def sanitize_html(html: str) -> str:
    parser = _Sanitizer()
    parser.feed(html or "")
    parser.close()
    return parser.result()
