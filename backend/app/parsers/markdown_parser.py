import re
from app.parsers.base import DocumentParser, ParsedDocument, ParserError

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
_CHECKLIST_RE = re.compile(r"^\s*[-*]\s+\[([ xX])\]\s+(.+)$", re.MULTILINE)


class MarkdownParser(DocumentParser):
    file_type = "markdown"

    def parse(self, raw_bytes: bytes, filename: str = "") -> ParsedDocument:
        try:
            text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            text = raw_bytes.decode("utf-8", errors="replace")

        if not text.strip():
            raise ParserError("File is empty or contains no readable text.")

        headings = [
            {"level": len(m.group(1)), "text": m.group(2).strip()}
            for m in _HEADING_RE.finditer(text)
        ]
        checklist_items = [
            {"done": m.group(1).lower() == "x", "text": m.group(2).strip()}
            for m in _CHECKLIST_RE.finditer(text)
        ]

        return ParsedDocument(
            text=text,
            structured_data={"headings": headings, "checklist_items": checklist_items},
        )
