import json
from app.parsers.base import DocumentParser, ParsedDocument, ParserError


class JsonParser(DocumentParser):
    file_type = "json"

    def parse(self, raw_bytes: bytes, filename: str = "") -> ParsedDocument:
        try:
            text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError as e:
            raise ParserError(f"File is not valid UTF-8: {e}")

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as e:
            raise ParserError(f"Invalid JSON: {e}")

        # Keyword search operates over `content` (plain text), not the raw
        # structured payload, so re-serialize pretty-printed for readability
        # rather than storing the original (possibly minified) text twice.
        pretty_text = json.dumps(parsed, indent=2, ensure_ascii=False)

        if isinstance(parsed, dict):
            structured_data = {"type": "object", "keys": list(parsed.keys())[:100], "body": parsed}
        elif isinstance(parsed, list):
            structured_data = {"type": "array", "item_count": len(parsed), "body": parsed[:500]}
        else:
            structured_data = {"type": type(parsed).__name__, "body": parsed}

        return ParsedDocument(text=pretty_text, structured_data=structured_data)
