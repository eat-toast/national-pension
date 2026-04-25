from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime
from html import escape
from pathlib import Path

from src.analysis.sector_trends import SectorTrendRow


def export_sector_trends_report(
    output_path: str | Path,
    csv_path: str | Path,
    monthly_rows: list[SectorTrendRow],
    quarterly_rows: list[SectorTrendRow],
    *,
    start_date: str,
    end_date: str,
    basis_type: str,
    sector_company_rows: list[dict[str, object]] | None = None,
) -> tuple[Path, Path]:
    output = Path(output_path)
    csv_output = Path(csv_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    csv_output.parent.mkdir(parents=True, exist_ok=True)
    all_rows = monthly_rows + quarterly_rows
    _write_csv(csv_output, all_rows)
    output.write_text(
        render_sector_trends_html(
            monthly_rows,
            quarterly_rows,
            start_date=start_date,
            end_date=end_date,
            basis_type=basis_type,
            csv_name=csv_output.name,
            sector_company_rows=sector_company_rows,
        ),
        encoding="utf-8",
    )
    return output, csv_output


def export_sector_trends_csv(output_path: str | Path, rows: list[SectorTrendRow]) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    _write_csv(output, rows)
    return output


def render_sector_trends_html(
    monthly_rows: list[SectorTrendRow],
    quarterly_rows: list[SectorTrendRow],
    *,
    start_date: str,
    end_date: str,
    basis_type: str,
    csv_name: str,
    sector_company_rows: list[dict[str, object]] | None = None,
) -> str:
    return _render_html(
        monthly_rows,
        quarterly_rows,
        start_date=start_date,
        end_date=end_date,
        basis_type=basis_type,
        csv_name=csv_name,
        sector_company_rows=sector_company_rows,
    )


def _write_csv(path: Path, rows: list[SectorTrendRow]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "period_type",
                "period",
                "sector_name",
                "event_count",
                "company_count",
                "increase_count",
                "decrease_count",
                "net_delta_shares",
                "abs_delta_shares",
                "net_ownership_delta",
                "abs_ownership_delta",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row.period_type,
                    row.period,
                    row.sector_name,
                    row.event_count,
                    row.company_count,
                    row.increase_count,
                    row.decrease_count,
                    round(row.net_delta_shares, 4),
                    round(row.abs_delta_shares, 4),
                    round(row.net_ownership_delta, 8),
                    round(row.abs_ownership_delta, 8),
                ]
            )


def _render_html(
    monthly_rows: list[SectorTrendRow],
    quarterly_rows: list[SectorTrendRow],
    *,
    start_date: str,
    end_date: str,
    basis_type: str,
    csv_name: str,
    sector_company_rows: list[dict[str, object]] | None = None,
) -> str:
    data = {
        "meta": {
            "startDate": start_date,
            "endDate": end_date,
            "basisType": basis_type,
            "basisLabel": "공시일 기준" if basis_type == "disclosure_date" else "변동일 기준",
            "generatedAt": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "csvName": csv_name,
        },
        "monthly": [_row_dict(row) for row in monthly_rows],
        "quarterly": [_row_dict(row) for row in quarterly_rows],
        "sectorTotals": _sector_totals(monthly_rows),
        "sectorCompanies": sector_company_rows or [],
    }
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    title = "국민연금 섹터별 월간/분기 변화"
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    :root {{
      --bg: #f7f7f4;
      --surface: #ffffff;
      --ink: #1d2430;
      --muted: #697282;
      --line: #d8ddd8;
      --green: #24745a;
      --red: #b74c42;
      --blue: #2f5f99;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      letter-spacing: 0;
    }}
    header {{
      background: var(--surface);
      border-bottom: 1px solid var(--line);
    }}
    .wrap {{
      width: min(1320px, calc(100vw - 36px));
      margin: 0 auto;
    }}
    .top {{
      display: flex;
      justify-content: space-between;
      align-items: end;
      gap: 18px;
      padding: 22px 0 18px;
    }}
    h1 {{
      margin: 0;
      font-size: 25px;
      line-height: 1.2;
    }}
    .meta {{
      margin-top: 8px;
      color: var(--muted);
      font-size: 13px;
    }}
    main {{ padding: 18px 0 34px; }}
    .controls {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }}
    button, select, input {{
      height: 34px;
      border: 1px solid var(--line);
      border-radius: 7px;
      background: var(--surface);
      color: var(--ink);
      padding: 0 10px;
      font: inherit;
      font-size: 13px;
    }}
    button {{ cursor: pointer; font-weight: 650; }}
    .kpis {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 18px;
    }}
    .metric {{
      min-height: 88px;
      padding: 14px;
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
    }}
    .metric .label {{ color: var(--muted); font-size: 12px; font-weight: 700; }}
    .metric .value {{ margin-top: 8px; font-size: 25px; font-weight: 780; }}
    .metric .detail {{ margin-top: 6px; color: var(--muted); font-size: 12px; }}
    .grid {{
      display: grid;
      grid-template-columns: minmax(0, 1.2fr) minmax(360px, 0.8fr);
      gap: 14px;
      align-items: start;
    }}
    section {{
      border-top: 1px solid var(--line);
      padding-top: 14px;
      margin-top: 6px;
    }}
    .section-head {{
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: 12px;
      margin-bottom: 10px;
    }}
    h2 {{ margin: 0; font-size: 16px; }}
    .hint {{ color: var(--muted); font-size: 12px; }}
    .surface {{
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }}
    th, td {{
      padding: 9px 10px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: middle;
      white-space: nowrap;
    }}
    th {{
      color: var(--muted);
      background: #fbfbf8;
      font-size: 12px;
      font-weight: 740;
      position: sticky;
      top: 0;
      z-index: 1;
    }}
    td.num, th.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
    .table-scroll {{ max-height: 610px; overflow: auto; }}
    .pos {{ color: var(--green); }}
    .neg {{ color: var(--red); }}
    .bar-row {{
      display: grid;
      grid-template-columns: 110px minmax(0, 1fr) 92px;
      gap: 10px;
      align-items: center;
      padding: 9px 10px;
      border-bottom: 1px solid var(--line);
      font-size: 13px;
      cursor: pointer;
    }}
    .bar-row:hover, .bar-row.selected {{ background: #f2f6f4; }}
    .bar-row.selected .bar-label {{ color: var(--blue); }}
    .bar-label {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-weight: 650; }}
    .bar-track {{ height: 8px; background: #edf0ee; border-radius: 999px; overflow: hidden; }}
    .bar-fill {{ height: 100%; background: var(--blue); border-radius: 999px; }}
    .bar-value {{ text-align: right; font-variant-numeric: tabular-nums; }}
    #sectorCompanyTable {{ min-width: 780px; }}
    @media (max-width: 900px) {{
      .top {{ align-items: start; flex-direction: column; }}
      .controls {{ justify-content: flex-start; }}
      .kpis {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="wrap top">
      <div>
        <h1>{escape(title)}</h1>
        <div class="meta" id="meta"></div>
      </div>
      <div class="controls">
        <select id="periodType" aria-label="기간 단위">
          <option value="quarterly">분기별</option>
          <option value="monthly">월별</option>
        </select>
        <select id="metric" aria-label="정렬 기준">
          <option value="netOwnershipDelta">지분율 순변화</option>
          <option value="absOwnershipDelta">지분율 변동폭</option>
          <option value="netDeltaShares">수량 순변화</option>
          <option value="absDeltaShares">수량 변동폭</option>
          <option value="eventCount">공시 건수</option>
        </select>
        <input id="filter" placeholder="섹터 또는 기간 검색" aria-label="검색">
        <button id="downloadCsv" type="button">CSV</button>
      </div>
    </div>
  </header>
  <main class="wrap">
    <div class="kpis" id="kpis"></div>
    <div class="grid">
      <section>
        <div class="section-head">
          <h2>기간별 섹터 변화</h2>
          <div class="hint" id="rowCount"></div>
        </div>
        <div class="surface table-scroll">
          <table id="trendTable"></table>
        </div>
      </section>
      <section>
        <div class="section-head">
          <h2>전체 기간 섹터 누적</h2>
          <div class="hint">월별 집계 기준</div>
        </div>
        <div class="surface" id="sectorBars"></div>
      </section>
    </div>
    <section>
      <div class="section-head">
        <h2 id="sectorCompanyTitle">섹터별 종목 정보</h2>
        <div class="hint" id="sectorCompanyCount"></div>
      </div>
      <div class="surface table-scroll">
        <table id="sectorCompanyTable"></table>
      </div>
    </section>
  </main>
  <script>
    const DATA = {payload};
    const fmt = new Intl.NumberFormat("ko-KR");
    const pct = value => value == null ? "" : `${{(value * 100).toFixed(2)}}%p`;
    const signedPct = value => value == null ? "" : `${{value > 0 ? "+" : ""}}${{(value * 100).toFixed(2)}}%p`;
    const signedNum = value => value == null ? "" : `${{value > 0 ? "+" : ""}}${{fmt.format(Math.round(value))}}`;
    const cls = value => Number(value) > 0 ? "pos" : Number(value) < 0 ? "neg" : "";
    const metricValue = (row, metric) => Math.abs(Number(row[metric] || 0));
    let selectedSector = "";
    const cell = (value, className = "") => `<td class="${{className}}">${{value ?? ""}}</td>`;
    function renderMeta() {{
      document.getElementById("meta").textContent =
        `${{DATA.meta.startDate}} - ${{DATA.meta.endDate}} · ${{DATA.meta.basisLabel}} · 생성 ${{DATA.meta.generatedAt}}`;
    }}
    function renderKpis() {{
      const rows = DATA.monthly;
      const eventCount = rows.reduce((sum, row) => sum + row.eventCount, 0);
      const companyCount = new Set(rows.map(row => `${{row.period}}:${{row.sectorName}}`)).size;
      const netOwnership = rows.reduce((sum, row) => sum + row.netOwnershipDelta, 0);
      const absShares = rows.reduce((sum, row) => sum + row.absDeltaShares, 0);
      const items = [
        ["월별 섹터 행", fmt.format(companyCount), "섹터와 월 조합"],
        ["공시 이벤트", fmt.format(eventCount), "집계 대상 이벤트"],
        ["지분율 순변화", signedPct(netOwnership), "기준선/직전 공시 대비"],
        ["수량 변동폭", fmt.format(Math.round(absShares)), "절대 증감수량 합계"],
      ];
      document.getElementById("kpis").innerHTML = items.map(item => `
        <div class="metric"><div class="label">${{item[0]}}</div><div class="value">${{item[1]}}</div><div class="detail">${{item[2]}}</div></div>
      `).join("");
    }}
    function renderTable() {{
      const periodType = document.getElementById("periodType").value;
      const metric = document.getElementById("metric").value;
      const query = document.getElementById("filter").value.trim().toLowerCase();
      let rows = [...DATA[periodType]];
      if (query) rows = rows.filter(row => row.period.toLowerCase().includes(query) || row.sectorName.toLowerCase().includes(query));
      rows.sort((a, b) => b.period.localeCompare(a.period) || metricValue(b, metric) - metricValue(a, metric));
      document.getElementById("rowCount").textContent = `${{fmt.format(rows.length)}}건`;
      const head = `<thead><tr>
        <th>기간</th><th>섹터</th><th class="num">종목</th><th class="num">공시</th><th class="num">증가</th><th class="num">감소</th>
        <th class="num">수량 순변화</th><th class="num">수량 변동폭</th><th class="num">지분율 순변화</th><th class="num">지분율 변동폭</th>
      </tr></thead>`;
      const body = rows.map(row => `<tr>
        <td>${{row.period}}</td><td>${{row.sectorName}}</td><td class="num">${{fmt.format(row.companyCount)}}</td><td class="num">${{fmt.format(row.eventCount)}}</td>
        <td class="num pos">${{fmt.format(row.increaseCount)}}</td><td class="num neg">${{fmt.format(row.decreaseCount)}}</td>
        <td class="num ${{cls(row.netDeltaShares)}}">${{signedNum(row.netDeltaShares)}}</td><td class="num">${{fmt.format(Math.round(row.absDeltaShares))}}</td>
        <td class="num ${{cls(row.netOwnershipDelta)}}">${{signedPct(row.netOwnershipDelta)}}</td><td class="num">${{pct(row.absOwnershipDelta)}}</td>
      </tr>`).join("");
      document.getElementById("trendTable").innerHTML = `${{head}}<tbody>${{body}}</tbody>`;
    }}
    function renderBars() {{
      const rows = DATA.sectorTotals.slice().sort((a, b) => b.absOwnershipDelta - a.absOwnershipDelta).slice(0, 16);
      if (!selectedSector && rows.length) selectedSector = rows[0].sectorName;
      const max = Math.max(...rows.map(row => row.absOwnershipDelta), 0.0001);
      document.getElementById("sectorBars").innerHTML = rows.map(row => `
        <div class="bar-row ${{row.sectorName === selectedSector ? "selected" : ""}}" data-sector="${{row.sectorName}}">
          <div class="bar-label" title="${{row.sectorName}}">${{row.sectorName}}</div>
          <div class="bar-track"><div class="bar-fill" style="width:${{Math.max(2, row.absOwnershipDelta / max * 100)}}%"></div></div>
          <div class="bar-value ${{cls(row.netOwnershipDelta)}}">${{signedPct(row.netOwnershipDelta)}}</div>
        </div>
      `).join("");
      document.querySelectorAll(".bar-row[data-sector]").forEach(row => {{
        row.addEventListener("click", () => {{
          selectedSector = row.dataset.sector;
          renderBars();
          renderSectorCompanies();
        }});
      }});
    }}
    function renderSectorCompanies() {{
      const rows = DATA.sectorCompanies
        .filter(row => row.sectorName === selectedSector)
        .sort((a, b) => Number(b.ownership || 0) - Number(a.ownership || 0));
      document.getElementById("sectorCompanyTitle").textContent = selectedSector ? `${{selectedSector}} 종목 정보` : "섹터별 종목 정보";
      document.getElementById("sectorCompanyCount").textContent = `${{fmt.format(rows.length)}}개 종목`;
      const head = `<thead><tr>
        <th>종목</th><th>코드</th><th class="num">지분율</th><th class="num">보유수량</th><th class="num">최근 변동수량</th><th>최근 공시일</th><th>사유</th>
      </tr></thead>`;
      const body = rows.map(row => `<tr>
        ${{cell(row.companyName)}}${{cell(row.ticker)}}${{cell(row.ownership == null ? "" : (row.ownership * 100).toFixed(2) + "%", "num")}}${{cell(row.estimatedShares == null ? "" : fmt.format(Math.round(row.estimatedShares)), "num")}}${{cell(row.lastDeltaShares == null ? "" : signedNum(row.lastDeltaShares), `num ${{cls(row.lastDeltaShares)}}`)}}${{cell(row.lastDisclosedAt)}}${{cell(row.lastChangeReason)}}
      </tr>`).join("");
      document.getElementById("sectorCompanyTable").innerHTML = `${{head}}<tbody>${{body || `<tr><td colspan="7">선택한 섹터의 종목 정보가 없습니다.</td></tr>`}}</tbody>`;
    }}
    document.getElementById("periodType").addEventListener("change", renderTable);
    document.getElementById("metric").addEventListener("change", renderTable);
    document.getElementById("filter").addEventListener("input", renderTable);
    document.getElementById("downloadCsv").addEventListener("click", () => {{
      window.location.href = DATA.meta.csvName;
    }});
    renderMeta();
    renderKpis();
    renderTable();
    renderBars();
    renderSectorCompanies();
  </script>
</body>
</html>
"""


def _row_dict(row: SectorTrendRow) -> dict[str, object]:
    return {
        "periodType": row.period_type,
        "period": row.period,
        "sectorName": row.sector_name,
        "eventCount": row.event_count,
        "companyCount": row.company_count,
        "increaseCount": row.increase_count,
        "decreaseCount": row.decrease_count,
        "netDeltaShares": row.net_delta_shares,
        "absDeltaShares": row.abs_delta_shares,
        "netOwnershipDelta": row.net_ownership_delta,
        "absOwnershipDelta": row.abs_ownership_delta,
    }


def _sector_totals(rows: list[SectorTrendRow]) -> list[dict[str, object]]:
    grouped: dict[str, dict[str, float | int | str]] = defaultdict(
        lambda: {
            "sectorName": "",
            "eventCount": 0,
            "companyCount": 0,
            "netDeltaShares": 0.0,
            "absDeltaShares": 0.0,
            "netOwnershipDelta": 0.0,
            "absOwnershipDelta": 0.0,
        }
    )
    for row in rows:
        target = grouped[row.sector_name]
        target["sectorName"] = row.sector_name
        target["eventCount"] = int(target["eventCount"]) + row.event_count
        target["companyCount"] = int(target["companyCount"]) + row.company_count
        target["netDeltaShares"] = float(target["netDeltaShares"]) + row.net_delta_shares
        target["absDeltaShares"] = float(target["absDeltaShares"]) + row.abs_delta_shares
        target["netOwnershipDelta"] = float(target["netOwnershipDelta"]) + row.net_ownership_delta
        target["absOwnershipDelta"] = float(target["absOwnershipDelta"]) + row.abs_ownership_delta
    return sorted(grouped.values(), key=lambda item: float(item["absOwnershipDelta"]), reverse=True)
