from typing import Dict, Optional
from app.parsers.base import DocumentParser
from app.parsers.txt_parser import TxtParser
from app.parsers.markdown_parser import MarkdownParser
from app.parsers.json_parser import JsonParser
from app.parsers.csv_parser import CsvParser
from app.parsers.pdf_parser import PdfParser

_PARSERS: Dict[str, DocumentParser] = {
    "txt": TxtParser(),
    "markdown": MarkdownParser(),
    "json": JsonParser(),
    "csv": CsvParser(),
    "pdf": PdfParser(),
}

# Common file extensions mapped to a supported file_type. ".md"/".markdown"
# both mean markdown; anything not listed here is unsupported.
_EXTENSION_MAP = {
    "pdf": "pdf",
    "md": "markdown",
    "markdown": "markdown",
    "txt": "txt",
    "json": "json",
    "csv": "csv",
}


def get_parser(file_type: str) -> Optional[DocumentParser]:
    return _PARSERS.get(file_type)


def infer_file_type(filename: str) -> Optional[str]:
    """Best-effort file type from a filename's extension. Returns None for
    anything not in _EXTENSION_MAP - callers should treat that as
    unsupported rather than guessing further."""
    if "." not in filename:
        return None
    ext = filename.rsplit(".", 1)[-1].lower()
    return _EXTENSION_MAP.get(ext)


def supported_file_types() -> list:
    return sorted(_PARSERS.keys())
