from dataclasses import dataclass, field
from typing import Any, Dict


class ParserError(Exception):
    """Raised when a file's bytes can't be parsed as its declared type
    (corrupt file, invalid JSON, encrypted/unreadable PDF, wrong encoding,
    etc). DocumentImporter catches this and turns it into a clean 400
    rather than a raw 500 - the rest of the import pipeline for other file
    types keeps working even if one file fails to parse."""


@dataclass
class ParsedDocument:
    text: str
    structured_data: Dict[str, Any] = field(default_factory=dict)


class DocumentParser:
    """Base interface: extract plain text (for keyword search) + a
    format-specific structured payload from raw file bytes.

    Deliberately synchronous and pure - parsing is CPU-bound text
    processing, not I/O, so there's no async boundary to cross here (the
    async lives one layer up, in DocumentImporter/DocumentService's DB
    calls).
    """

    file_type: str = "unknown"

    def parse(self, raw_bytes: bytes, filename: str = "") -> ParsedDocument:
        raise NotImplementedError
