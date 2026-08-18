from __future__ import annotations

import re
import subprocess
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


class ExtractionError(ValueError):
    pass


def _clean(value: str) -> str:
    return re.sub(r"[ \t]+", " ", value).strip()


def _text(path: Path) -> tuple[str, list[dict[str, str]], list[str]]:
    text = path.read_text(encoding="utf-8-sig")
    blocks = [
        {"locator": f"line:{number}", "text": line.strip()}
        for number, line in enumerate(text.splitlines(), start=1) if line.strip()
    ]
    return text.strip(), blocks, []


def _docx(path: Path) -> tuple[str, list[dict[str, str]], list[str]]:
    try:
        with zipfile.ZipFile(path) as archive:
            root = ET.fromstring(archive.read("word/document.xml"))
    except (zipfile.BadZipFile, KeyError, ET.ParseError) as exc:
        raise ExtractionError(f"DOCX 无法读取：{exc}") from exc
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    blocks: list[dict[str, str]] = []
    for number, paragraph in enumerate(root.findall(".//w:body/w:p", ns), start=1):
        value = _clean("".join(node.text or "" for node in paragraph.findall(".//w:t", ns)))
        if value:
            blocks.append({"locator": f"paragraph:{number}", "text": value})
    for row_number, row in enumerate(root.findall(".//w:tbl/w:tr", ns), start=1):
        cells = []
        for cell in row.findall("./w:tc", ns):
            cells.append(_clean("".join(node.text or "" for node in cell.findall(".//w:t", ns))))
        if any(cells):
            value = " | ".join(cells)
            blocks.append({"locator": f"table-row:{row_number}", "text": value})
    return "\n".join(item["text"] for item in blocks), blocks, []


def _xlsx(path: Path) -> tuple[str, list[dict[str, str]], list[str]]:
    try:
        with zipfile.ZipFile(path) as archive:
            shared: list[str] = []
            if "xl/sharedStrings.xml" in archive.namelist():
                root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
                shared = ["".join(node.text or "" for node in item.iter() if node.tag.endswith("}t")) for item in root]
            workbook = ET.fromstring(archive.read("xl/workbook.xml"))
            rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
            targets = {item.attrib["Id"]: item.attrib["Target"] for item in rels}
            ns_rel = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
            blocks: list[dict[str, str]] = []
            for sheet in [node for node in workbook.iter() if node.tag.endswith("}sheet")]:
                sheet_name = sheet.attrib.get("name", "Sheet")
                target = targets.get(sheet.attrib.get(ns_rel, ""), "")
                member = target.lstrip("/") if target.startswith("/xl/") else "xl/" + target.lstrip("/")
                root = ET.fromstring(archive.read(member))
                for cell in [node for node in root.iter() if node.tag.endswith("}c")]:
                    ref = cell.attrib.get("r", "?")
                    kind = cell.attrib.get("t")
                    raw = next((node.text or "" for node in cell if node.tag.endswith("}v")), "")
                    if kind == "s" and raw.isdigit() and int(raw) < len(shared):
                        value = shared[int(raw)]
                    elif kind == "inlineStr":
                        value = "".join(node.text or "" for node in cell.iter() if node.tag.endswith("}t"))
                    else:
                        value = raw
                    value = _clean(value)
                    if value:
                        blocks.append({"locator": f"sheet:{sheet_name}!{ref}", "text": value})
    except (zipfile.BadZipFile, KeyError, ET.ParseError) as exc:
        raise ExtractionError(f"XLSX 无法读取：{exc}") from exc
    warnings = ["XLSX 只提取单元格显示底稿；公式结果、图片、批注和版式需人工核对。"]
    return "\n".join(f"[{item['locator']}] {item['text']}" for item in blocks), blocks, warnings


def _pdf(path: Path) -> tuple[str, list[dict[str, str]], list[str]]:
    pages: list[str] = []
    try:
        from pypdf import PdfReader  # type: ignore

        pages = [(page.extract_text() or "").strip() for page in PdfReader(str(path)).pages]
    except ModuleNotFoundError:
        with tempfile.TemporaryDirectory(prefix="xhs-pdf-") as directory:
            output = Path(directory) / "brief.txt"
            try:
                subprocess.run(
                    ["pdftotext", "-layout", str(path), str(output)],
                    check=True, capture_output=True, text=True,
                )
            except (FileNotFoundError, subprocess.CalledProcessError) as exc:
                raise ExtractionError("PDF 提取需要 pypdf 或 pdftotext；请安装任一依赖") from exc
            pages = output.read_text(encoding="utf-8", errors="replace").split("\f")
    blocks = [
        {"locator": f"page:{number}", "text": page.strip()}
        for number, page in enumerate(pages, start=1) if page.strip()
    ]
    warnings = ["PDF 文本不代表原版式；表格、图片和扫描页需对照原件核验。"]
    return "\n\n".join(item["text"] for item in blocks), blocks, warnings


def extract_document(path: Path) -> tuple[str, str, list[dict[str, str]], list[str]]:
    suffix = path.suffix.lower()
    if suffix in {".md", ".txt"}:
        text, blocks, warnings = _text(path)
        media = "text/markdown" if suffix == ".md" else "text/plain"
    elif suffix == ".docx":
        text, blocks, warnings = _docx(path)
        media = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif suffix == ".xlsx":
        text, blocks, warnings = _xlsx(path)
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif suffix == ".pdf":
        text, blocks, warnings = _pdf(path)
        media = "application/pdf"
    else:
        raise ExtractionError("Brief 仅支持 MD、TXT、PDF、DOCX、XLSX")
    if not text.strip():
        raise ExtractionError("文件没有提取到可用文本")
    return media, text.strip(), blocks, warnings
