import pytest
from app.parsers.txt_parser import TxtParser
from app.parsers.markdown_parser import MarkdownParser
from app.parsers.json_parser import JsonParser
from app.parsers.csv_parser import CsvParser
from app.parsers.pdf_parser import PdfParser
from app.parsers.base import ParserError
from app.parsers.registry import get_parser, infer_file_type, supported_file_types


def test_txt_parser_extracts_plain_text():
    parsed = TxtParser().parse(b"Hello, this is a plain text note.")
    assert "plain text note" in parsed.text
    assert parsed.structured_data == {}


def test_txt_parser_rejects_empty_file():
    with pytest.raises(ParserError):
        TxtParser().parse(b"   \n\n  ")


def test_markdown_parser_extracts_headings_and_checklist():
    content = b"# Project Atlas\n\n## Tasks\n\n- [ ] Write report\n- [x] Set up repo\n"
    parsed = MarkdownParser().parse(content)
    headings = parsed.structured_data["headings"]
    assert {"level": 1, "text": "Project Atlas"} in headings
    assert {"level": 2, "text": "Tasks"} in headings

    checklist = parsed.structured_data["checklist_items"]
    assert {"done": False, "text": "Write report"} in checklist
    assert {"done": True, "text": "Set up repo"} in checklist


def test_json_parser_handles_object():
    parsed = JsonParser().parse(b'{"name": "Atlas", "version": 6}')
    assert parsed.structured_data["type"] == "object"
    assert "name" in parsed.structured_data["keys"]
    assert parsed.structured_data["body"]["version"] == 6


def test_json_parser_handles_array():
    parsed = JsonParser().parse(b'[{"a": 1}, {"a": 2}]')
    assert parsed.structured_data["type"] == "array"
    assert parsed.structured_data["item_count"] == 2


def test_json_parser_rejects_invalid_json():
    with pytest.raises(ParserError):
        JsonParser().parse(b"{not valid json")


def test_csv_parser_extracts_columns_and_rows():
    content = b"name,age\nAlice,30\nBob,25\n"
    parsed = CsvParser().parse(content)
    assert parsed.structured_data["columns"] == ["name", "age"]
    assert parsed.structured_data["row_count"] == 2
    assert parsed.structured_data["body"][0]["name"] == "Alice"
    assert "Alice" in parsed.text


def test_csv_parser_rejects_file_with_no_header():
    with pytest.raises(ParserError):
        CsvParser().parse(b"")


def test_pdf_parser_rejects_non_pdf_bytes():
    with pytest.raises(ParserError):
        PdfParser().parse(b"this is definitely not a pdf file")


def test_registry_infers_file_type_from_extension():
    assert infer_file_type("notes.md") == "markdown"
    assert infer_file_type("report.PDF") == "pdf"
    assert infer_file_type("data.csv") == "csv"
    assert infer_file_type("readme") is None
    assert infer_file_type("weird.docx") is None


def test_registry_returns_parser_for_supported_types():
    for file_type in supported_file_types():
        assert get_parser(file_type) is not None
    assert get_parser("docx") is None


def test_supported_file_types_matches_phase_6_scope():
    assert set(supported_file_types()) == {"pdf", "markdown", "txt", "json", "csv"}
