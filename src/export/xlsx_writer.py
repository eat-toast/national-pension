from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from src.models import SectorSummaryRow, SnapshotRow


@dataclass(slots=True)
class Sheet:
    name: str
    rows: list[list[str | int | float | None]]


def export_snapshot_workbook(
    output_path: str | Path,
    as_of_date: str,
    basis_type: str,
    snapshot_rows: list[SnapshotRow],
    event_rows: list[dict[str, object]],
    sector_rows: list[SectorSummaryRow],
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    workbook = [
        Sheet(
            "포트폴리오",
            _portfolio_sheet_rows(as_of_date, basis_type, snapshot_rows),
        ),
        Sheet(
            "이벤트이력",
            _event_sheet_rows(event_rows),
        ),
        Sheet(
            "섹터요약",
            _sector_sheet_rows(sector_rows),
        ),
        Sheet(
            "메타정보",
            [
                ["조회 기준일", as_of_date],
                ["기준 타입", basis_type],
                ["데이터 범위", "공시로 확인 가능한 5% 이상 보유 종목"],
                ["비고", "변동일 기준과 공시일 기준은 서로 다른 시차를 가질 수 있습니다."],
            ],
        ),
    ]
    _write_xlsx(output, workbook)
    return output


def _portfolio_sheet_rows(as_of_date: str, basis_type: str, rows: list[SnapshotRow]) -> list[list[str | int | float | None]]:
    rendered: list[list[str | int | float | None]] = [
        ["국민연금 핵심 포트폴리오 스냅샷"],
        [f"기준일: {as_of_date} / 기준: {basis_type}"],
        [],
        ["번호", "종목명", "종목코드", "추정 보유수량", "추정 지분율", "최근 변동수량", "변동 사유", "최근 변동일", "최근 공시일", "섹터"],
    ]
    for index, row in enumerate(rows, start=1):
        rendered.append(
            [
                index,
                row.company_name,
                row.ticker or "",
                _format_number(row.estimated_shares),
                _format_percent(row.estimated_ownership),
                _format_number(row.last_delta_shares),
                row.last_change_reason or "",
                row.last_effective_date or "",
                row.last_disclosed_at,
                row.sector_name,
            ]
        )
    return rendered


def _event_sheet_rows(event_rows: list[dict[str, object]]) -> list[list[str | int | float | None]]:
    rows: list[list[str | int | float | None]] = [
        ["종목명", "종목코드", "변동일", "공시일", "증감수량", "변동 후 보유수량", "변동 후 지분율", "변동사유", "구분"]
    ]
    for event in event_rows:
        rows.append(
            [
                event.get("company_name", ""),
                event.get("ticker", "") or "",
                event.get("effective_date", "") or "",
                event.get("disclosed_at", ""),
                _format_number(event.get("delta_shares")),
                _format_number(event.get("shares_after")),
                _format_percent(event.get("ownership_after")),
                event.get("change_reason", "") or "",
                event.get("event_type", "") or "",
            ]
        )
    return rows


def _sector_sheet_rows(sector_rows: list[SectorSummaryRow]) -> list[list[str | int | float | None]]:
    rows: list[list[str | int | float | None]] = [["섹터", "종목 수", "지분율 합계", "최근 방향"]]
    for sector in sector_rows:
        rows.append(
            [
                sector.sector_name,
                sector.company_count,
                _format_percent(sector.ownership_sum),
                sector.net_direction,
            ]
        )
    return rows


def _format_number(value: object) -> str:
    if value in (None, ""):
        return ""
    return f"{float(value):,.0f}"


def _format_percent(value: object) -> str:
    if value in (None, ""):
        return ""
    return f"{float(value):.2%}"


def _write_xlsx(path: Path, sheets: list[Sheet]) -> None:
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _content_types(len(sheets)))
        archive.writestr("_rels/.rels", _root_rels())
        archive.writestr("xl/workbook.xml", _workbook_xml(sheets))
        archive.writestr("xl/_rels/workbook.xml.rels", _workbook_rels(sheets))
        archive.writestr("xl/styles.xml", _styles_xml())
        for index, sheet in enumerate(sheets, start=1):
            archive.writestr(f"xl/worksheets/sheet{index}.xml", _sheet_xml(sheet.rows))
        archive.writestr("docProps/core.xml", _core_xml())
        archive.writestr("docProps/app.xml", _app_xml(len(sheets)))


def _escape(value: object) -> str:
    text = str(value)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _column_name(index: int) -> str:
    result = ""
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _sheet_xml(rows: list[list[str | int | float | None]]) -> str:
    xml_rows: list[str] = []
    for row_index, row in enumerate(rows, start=1):
        cells: list[str] = []
        for col_index, value in enumerate(row, start=1):
            if value in (None, ""):
                continue
            cell_ref = f"{_column_name(col_index)}{row_index}"
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                cells.append(f'<c r="{cell_ref}"><v>{value}</v></c>')
            else:
                cells.append(f'<c r="{cell_ref}" t="inlineStr"><is><t>{_escape(value)}</t></is></c>')
        xml_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(xml_rows)}</sheetData>'
        "</worksheet>"
    )


def _content_types(sheet_count: int) -> str:
    overrides = "".join(
        f'<Override PartName="/xl/worksheets/sheet{index}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for index in range(1, sheet_count + 1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/styles.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
        '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
        f"{overrides}</Types>"
    )


def _root_rels() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
        '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
        "</Relationships>"
    )


def _workbook_xml(sheets: list[Sheet]) -> str:
    sheet_nodes = "".join(
        f'<sheet name="{_escape(sheet.name)}" sheetId="{index}" r:id="rId{index}"/>'
        for index, sheet in enumerate(sheets, start=1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f"<sheets>{sheet_nodes}</sheets>"
        "</workbook>"
    )


def _workbook_rels(sheets: list[Sheet]) -> str:
    relationships = "".join(
        f'<Relationship Id="rId{index}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        f'Target="worksheets/sheet{index}.xml"/>'
        for index, _ in enumerate(sheets, start=1)
    )
    relationships += (
        f'<Relationship Id="rId{len(sheets) + 1}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
        'Target="styles.xml"/>'
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f"{relationships}</Relationships>"
    )


def _styles_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>'
        '<fills count="1"><fill><patternFill patternType="none"/></fill></fills>'
        '<borders count="1"><border/></borders>'
        '<cellStyleXfs count="1"><xf/></cellStyleXfs>'
        '<cellXfs count="1"><xf xfId="0"/></cellXfs>'
        '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
        "</styleSheet>"
    )


def _core_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:dcmitype="http://purl.org/dc/dcmitype/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        "<dc:creator>Codex</dc:creator>"
        "<cp:lastModifiedBy>Codex</cp:lastModifiedBy>"
        "</cp:coreProperties>"
    )


def _app_xml(sheet_count: int) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
        'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
        '<Application>Codex</Application>'
        f"<Sheets>{sheet_count}</Sheets>"
        "</Properties>"
    )
