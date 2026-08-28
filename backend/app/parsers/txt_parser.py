from app.parsers.base import DocumentParser, ParsedDocument, ParserError


class TxtParser(DocumentParser):
    file_type = "txt"

    def parse(self, raw_bytes: bytes, filename: str = "") -> ParsedDocument:
        try:
            text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            # Best-effort fallback rather than failing the whole import over
            # a handful of non-UTF-8 bytes in an otherwise-text file.
            text = raw_bytes.decode("utf-8", errors="replace")

        if not text.strip():
            raise ParserError("File is empty or contains no readable text.")

        return ParsedDocument(text=text, structured_data={})
