from __future__ import annotations

import sys
import types
import zipfile
from pathlib import Path

import pytest

from xhs_agent.projects.extractors import ExtractionError, extract_document


def test_extracts_docx_paragraphs_and_table_locators(tmp_path: Path) -> None:
    path = tmp_path / "brief.docx"
    document = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>
<w:p><w:r><w:t>品牌合作要求</w:t></w:r></w:p>
<w:tbl><w:tr><w:tc><w:p><w:r><w:t>合成字段</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>测试值A</w:t></w:r></w:p></w:tc></w:tr></w:tbl>
</w:body></w:document>"""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", document)
    media, text, blocks, warnings = extract_document(path)
    assert media.endswith("wordprocessingml.document")
    assert "品牌合作要求" in text and "合成字段 | 测试值A" in text
    assert {item["locator"] for item in blocks} == {"paragraph:1", "table-row:1"}
    assert warnings == []


def test_extracts_xlsx_sheet_and_cell_locators(tmp_path: Path) -> None:
    path = tmp_path / "brief.xlsx"
    workbook = """<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="合作要求" sheetId="1" r:id="rId1"/></sheets></workbook>"""
    rels = """<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml" Type="worksheet"/></Relationships>"""
    shared = """<?xml version="1.0" encoding="UTF-8"?><sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><si><t>合成字段</t></si><si><t>测试值A</t></si></sst>"""
    sheet = """<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c></row></sheetData></worksheet>"""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", rels)
        archive.writestr("xl/sharedStrings.xml", shared)
        archive.writestr("xl/worksheets/sheet1.xml", sheet)
    media, text, blocks, warnings = extract_document(path)
    assert media.endswith("spreadsheetml.sheet")
    assert "[sheet:合作要求!A1] 合成字段" in text
    assert blocks[1] == {"locator": "sheet:合作要求!B1", "text": "测试值A"}
    assert warnings


def test_extracts_pdf_by_page_through_pypdf_contract(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "brief.pdf"; path.write_bytes(b"%PDF synthetic")

    class Page:
        def __init__(self, text: str): self.text = text
        def extract_text(self): return self.text

    class Reader:
        def __init__(self, _path: str): self.pages = [Page("第一页要求"), Page("第二页卖点")]

    monkeypatch.setitem(sys.modules, "pypdf", types.SimpleNamespace(PdfReader=Reader))
    media, text, blocks, warnings = extract_document(path)
    assert media == "application/pdf"
    assert [item["locator"] for item in blocks] == ["page:1", "page:2"]
    assert "第二页卖点" in text and warnings


def test_rejects_unsupported_or_empty_brief(tmp_path: Path) -> None:
    unsupported = tmp_path / "brief.pptx"; unsupported.write_bytes(b"x")
    with pytest.raises(ExtractionError, match="仅支持"):
        extract_document(unsupported)
    empty = tmp_path / "brief.txt"; empty.write_text("   ", encoding="utf-8")
    with pytest.raises(ExtractionError, match="没有提取到"):
        extract_document(empty)
