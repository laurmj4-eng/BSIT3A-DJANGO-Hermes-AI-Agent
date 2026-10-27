"""CSV/XLSX exporters for the news feed.

Both formats are built with the standard library only: ``csv`` for the text
export and ``zipfile`` + hand-written SpreadsheetML for a minimal but valid
``.xlsx`` package (no third-party spreadsheet dependency).
"""

from __future__ import annotations

import csv
import io
import re
import zipfile
from xml.sax.saxutils import escape

HEADERS = ["Title", "Source", "Published", "Topics", "URL", "Summary"]
MAX_SUMMARY_CHARS = 2000

# XML 1.0 forbids most control characters; strip them so Excel can open the
# file instead of reporting a corrupt workbook.
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _clean_summary(value: str | None) -> str:
    text = " ".join((value or "").split())
    return text[:MAX_SUMMARY_CHARS]


def article_rows(queryset) -> list[list[str]]:
    """Turn an Article queryset (prefetching topics) into export rows."""
    rows: list[list[str]] = [list(HEADERS)]
    for article in queryset:
        rows.append([
            article.title,
            article.source,
            article.published_at.isoformat() if article.published_at else "",
            ", ".join(topic.name for topic in article.topics.all()),
            article.url,
            _clean_summary(article.summary),
        ])
    return rows


def csv_bytes(rows) -> bytes:
    """UTF-8 CSV with a BOM so Excel detects the encoding."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    for row in rows:
        writer.writerow(row)
    return ("\ufeff" + buffer.getvalue()).encode("utf-8")


def _column_name(index: int) -> str:
    """0 -> A, 25 -> Z, 26 -> AA ... (columns A-F are all we need)."""
    name = ""
    index += 1
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _xml_text(value) -> str:
    return escape(_CONTROL_CHARS.sub("", str(value)))


def _cell(reference: str, value) -> str:
    return (
        f'<c r="{reference}" t="inlineStr"><is>'
        f'<t xml:space="preserve">{_xml_text(value)}</t></is></c>'
    )


_CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" '
    'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/xl/workbook.xml" '
    'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
    '<Override PartName="/xl/worksheets/sheet1.xml" '
    'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
    "</Types>"
)

_ROOT_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" '
    'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
    'Target="xl/workbook.xml"/>'
    "</Relationships>"
)

_WORKBOOK = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
    '<sheets><sheet name="Articles" sheetId="1" r:id="rId1"/></sheets>'
    "</workbook>"
)

_WORKBOOK_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" '
    'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
    'Target="worksheets/sheet1.xml"/>'
    "</Relationships>"
)


def _sheet_xml(rows) -> str:
    xml_rows = []
    for row_number, row in enumerate(rows, start=1):
        cells = "".join(
            _cell(f"{_column_name(column)}{row_number}", value)
            for column, value in enumerate(row)
        )
        xml_rows.append(f'<row r="{row_number}">{cells}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(xml_rows)}</sheetData>'
        "</worksheet>"
    )


def xlsx_bytes(rows) -> bytes:
    """Build a minimal valid XLSX workbook as an in-memory zip."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _CONTENT_TYPES)
        archive.writestr("_rels/.rels", _ROOT_RELS)
        archive.writestr("xl/workbook.xml", _WORKBOOK)
        archive.writestr("xl/_rels/workbook.xml.rels", _WORKBOOK_RELS)
        archive.writestr("xl/worksheets/sheet1.xml", _sheet_xml(rows))
    return buffer.getvalue()
