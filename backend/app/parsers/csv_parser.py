import csv
import io
from app.parsers.base import DocumentParser, ParsedDocument, ParserError

_MAX_STORED_ROWS = 500  # cap structured_data payload size; row_count still reflects the true total


class CsvParser(DocumentParser):
    file_type = "csv"

    def parse(self, raw_bytes: bytes, filename: str = "") -> ParsedDocument:
        try:
            text = raw_bytes.decode("utf-8-sig")  # -sig strips a BOM if Excel added one
        except UnicodeDecodeError as e:
            raise ParserError(f"File is not valid UTF-8: {e}")

        try:
            reader = csv.DictReader(io.StringIO(text))
            fieldnames = reader.fieldnames or []
            rows = list(reader)
        except csv.Error as e:
            raise ParserError(f"Invalid CSV: {e}")

        if not fieldnames:
            raise ParserError("CSV has no header row / no columns detected.")

        stored_rows = rows[:_MAX_STORED_ROWS]

        # Text used for keyword search: header + a readable sample of rows,
        # not the full CSV re-serialized (could be huge and adds no search
        # value beyond what's already in structured_data.body).
        preview_lines = [", ".join(fieldnames)]
        for row in rows[:50]:
            preview_lines.append(", ".join(str(row.get(f, "")) for f in fieldnames))
        text_preview = "\n".join(preview_lines)

        structured_data = {
            "columns": fieldnames,
            "row_count": len(rows),
            "body": stored_rows,
        }

        return ParsedDocument(text=text_preview, structured_data=structured_data)
