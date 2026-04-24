from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile


_MAIN_NS = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


@dataclass(slots=True)
class BaselineHolding:
    rank: int
    company_name: str
    market_value_krw_100m: float | None
    asset_weight: float | None
    ownership: float | None


def load_baseline_holdings(path: str | Path) -> list[BaselineHolding]:
    workbook_path = Path(path)
    with ZipFile(workbook_path) as archive:
        shared_strings = _read_shared_strings(archive)
        sheet_name = _first_worksheet_name(archive)
        rows = _read_rows(archive, sheet_name, shared_strings)

    header_index = _find_header_index(rows)
    if header_index is None:
        raise ValueError(f"Cannot find holding table header in {workbook_path}")

    header = rows[header_index]
    columns = {str(value).strip(): index for index, value in enumerate(header) if value not in (None, "")}
    required = ("번호", "종목명", "평가액(억원)", "자산군 내 비중", "지분율")
    missing = [name for name in required if name not in columns]
    if missing:
        raise ValueError(f"Missing baseline columns in {workbook_path}: {', '.join(missing)}")

    holdings: list[BaselineHolding] = []
    for row in rows[header_index + 1 :]:
        rank = _parse_int(_get(row, columns["번호"]))
        company_name = str(_get(row, columns["종목명"]) or "").strip()
        if rank is None or not company_name:
            continue
        holdings.append(
            BaselineHolding(
                rank=rank,
                company_name=company_name,
                market_value_krw_100m=_parse_float(_get(row, columns["평가액(억원)"])),
                asset_weight=_parse_float(_get(row, columns["자산군 내 비중"])),
                ownership=_parse_float(_get(row, columns["지분율"])),
            )
        )
    return holdings


def baseline_year_from_path(path: str | Path) -> str:
    match = re.search(r"(20\d{2})", Path(path).name)
    return match.group(1) if match else ""


def normalize_company_name(value: str) -> str:
    text = re.sub(r"\s+", "", value)
    text = text.replace("(주)", "")
    text = text.replace("㈜", "")
    text = text.lower()
    suffixes = ("보통주", "우선주", "우")
    for suffix in suffixes:
        if text.endswith(suffix):
            text = text[: -len(suffix)]
    return text


def _first_worksheet_name(archive: ZipFile) -> str:
    names = sorted(name for name in archive.namelist() if name.startswith("xl/worksheets/sheet") and name.endswith(".xml"))
    if not names:
        raise ValueError("XLSX workbook has no worksheets")
    return names[0]


def _read_shared_strings(archive: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
    strings: list[str] = []
    for item in root.findall("x:si", _MAIN_NS):
        strings.append("".join(text.text or "" for text in item.findall(".//x:t", _MAIN_NS)))
    return strings


def _read_rows(archive: ZipFile, sheet_name: str, shared_strings: list[str]) -> list[list[object | None]]:
    root = ElementTree.fromstring(archive.read(sheet_name))
    rows: list[list[object | None]] = []
    for row in root.findall(".//x:sheetData/x:row", _MAIN_NS):
        values: list[object | None] = []
        for cell in row.findall("x:c", _MAIN_NS):
            column = _column_index(cell.attrib.get("r", ""))
            while len(values) < column:
                values.append(None)
            values[column - 1] = _cell_value(cell, shared_strings)
        rows.append(values)
    return rows


def _cell_value(cell: ElementTree.Element, shared_strings: list[str]) -> object | None:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(text.text or "" for text in cell.findall(".//x:t", _MAIN_NS))
    value = cell.find("x:v", _MAIN_NS)
    if value is None or value.text is None:
        return ""
    if cell_type == "s":
        return shared_strings[int(value.text)]
    parsed = _parse_float(value.text)
    return parsed if parsed is not None else value.text


def _column_index(cell_ref: str) -> int:
    letters = "".join(char for char in cell_ref if char.isalpha())
    index = 0
    for char in letters:
        index = index * 26 + ord(char.upper()) - 64
    return index or 1


def _find_header_index(rows: list[list[object | None]]) -> int | None:
    for index, row in enumerate(rows):
        labels = {str(value).strip() for value in row if value not in (None, "")}
        if {"번호", "종목명", "지분율"}.issubset(labels):
            return index
    return None


def _get(row: list[object | None], index: int) -> object | None:
    return row[index] if index < len(row) else None


def _parse_float(value: object | None) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return None


def _parse_int(value: object | None) -> int | None:
    number = _parse_float(value)
    if number is None:
        return None
    return int(number)
