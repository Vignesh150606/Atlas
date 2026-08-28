from app.parsers.base import DocumentParser, ParsedDocument, ParserError


class PdfParser(DocumentParser):
    file_type = "pdf"

    def parse(self, raw_bytes: bytes, filename: str = "") -> ParsedDocument:
        try:
            import io
            from pypdf import PdfReader
        except ImportError as e:
            raise ParserError(
                f"PDF support requires the 'pypdf' package, which isn't installed: {e}"
            )

        try:
            reader = PdfReader(io.BytesIO(raw_bytes))
        except Exception as e:
            raise ParserError(f"Could not open file as a PDF: {e}")

        if reader.is_encrypted:
            # Attempt an empty-password unlock (common for PDFs that are
            # "encrypted" only to disable editing, not to actually restrict
            # reading) before giving up.
            try:
                reader.decrypt("")
            except Exception:
                pass
            if reader.is_encrypted:
                raise ParserError("PDF is password-protected and can't be read.")

        try:
            page_texts = [page.extract_text() or "" for page in reader.pages]
        except Exception as e:
            raise ParserError(f"Failed to extract text from PDF: {e}")

        text = "\n\n".join(t.strip() for t in page_texts if t.strip())
        if not text.strip():
            raise ParserError(
                "No extractable text found in PDF (it may be a scanned image with no text layer)."
            )

        return ParsedDocument(text=text, structured_data={"page_count": len(reader.pages)})
