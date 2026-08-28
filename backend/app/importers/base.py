class DocumentImportError(Exception):
    """Raised for import-time failures that aren't a parsing problem
    (unsupported file type, file too large, etc) - see ParserError
    (app/parsers/base.py) for format-level parse failures."""
