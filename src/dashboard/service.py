from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any

from src.dashboard.baseline import BaselineHolding, baseline_year_from_path, load_baseline_holdings, normalize_company_name
from src.db.repository import Repository
from src.models import BasisType, SnapshotRow
from src.snapshot.service import calculate_snapshot_rows


def export_dashboard(
    output_path: str | Path,
    baseline_path: str | Path,
    repository: Repository,
    as_of_date: str,
    basis_type: BasisType,
) -> Path:
    baseline_rows = load_baseline_holdings(baseline_path)
    snapshot_rows, sector_rows = calculate_snapshot_rows(repository, as_of_date, basis_type)
    event_rows = [dict(row) for row in repository.list_events_until(as_of_date, basis_type)]
    data = build_dashboard_data(
        baseline_rows=baseline_rows,
        snapshot_rows=snapshot_rows,
        event_rows=event_rows,
        sector_rows=[asdict(row) for row in sector_rows],
        as_of_date=as_of_date,
        basis_type=basis_type,
        baseline_year=baseline_year_from_path(baseline_path),
    )
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_dashboard_html(data), encoding="utf-8")
    return output


def build_dashboard_data(
    baseline_rows: list[BaselineHolding],
    snapshot_rows: list[SnapshotRow],
    event_rows: list[dict[str, Any]],
    sector_rows: list[dict[str, Any]],
    as_of_date: str,
    basis_type: BasisType,
    baseline_year: str,
) -> dict[str, Any]:
    enriched_events = _with_ownership_deltas(event_rows, baseline_rows)
    events_2025 = [row for row in enriched_events if str(row.get("disclosed_at", ""))[:4] == "2025"]
    changed_companies = {normalize_company_name(str(row.get("company_name", ""))) for row in events_2025}
    latest_disclosed_at = max((str(row.get("disclosed_at", "")) for row in events_2025), default="")
    baseline_total = sum(row.market_value_krw_100m or 0.0 for row in baseline_rows)
    increases = sum(1 for row in events_2025 if _as_float(row.get("delta_shares")) and _as_float(row.get("delta_shares")) > 0)
    decreases = sum(1 for row in events_2025 if _as_float(row.get("delta_shares")) and _as_float(row.get("delta_shares")) < 0)
    comparisons = _ownership_comparisons(baseline_rows, snapshot_rows)
    comparison_by_name = {normalize_company_name(str(row["companyName"])): row for row in comparisons}
    latest_event_by_key = _latest_event_by_key(enriched_events)
    sector_deltas = _sector_ownership_deltas(snapshot_rows, comparison_by_name)

    return {
        "meta": {
            "title": "국민연금 국내주식 변동 대시보드",
            "asOfDate": as_of_date,
            "basisType": basis_type,
            "basisLabel": "공시일 기준" if basis_type == "disclosure_date" else "변동일 기준",
            "baselineYear": baseline_year or "기준",
            "generatedAt": datetime.now().strftime("%Y-%m-%d %H:%M"),
        },
        "kpis": [
            {"label": f"{baseline_year or '기준'}년 말 종목", "value": f"{len(baseline_rows):,}", "detail": "기준 엑셀 전체 행"},
            {"label": "평가액 합계", "value": _format_krw_100m(baseline_total), "detail": "기준 엑셀 평가액"},
            {"label": "2025 변동 공시", "value": f"{len(events_2025):,}", "detail": f"최근 공시일 {latest_disclosed_at or '-'}"},
            {"label": "변동 종목", "value": f"{len(changed_companies):,}", "detail": f"증가 {increases:,} / 감소 {decreases:,}"},
            {"label": "최신 추적 종목", "value": f"{len(snapshot_rows):,}", "detail": "공시 기반 5% 이상"},
            {"label": "2024 대비 매칭", "value": f"{len(comparisons):,}", "detail": "종목명 기준 비교"},
        ],
        "baselineRows": [
            _baseline_dict(row, comparison_by_name.get(normalize_company_name(row.company_name)))
            for row in baseline_rows
        ],
        "snapshotRows": [
            _snapshot_dict(
                row,
                latest_event_by_key.get(_row_key(row.ticker, row.company_name)),
                comparison_by_name.get(normalize_company_name(row.company_name)),
            )
            for row in snapshot_rows
        ],
        "eventHistory": [_event_dict(row) for row in enriched_events],
        "baselineTop": [
            _baseline_dict(row, comparison_by_name.get(normalize_company_name(row.company_name)))
            for row in sorted(baseline_rows, key=lambda row: row.market_value_krw_100m or 0, reverse=True)[:20]
        ],
        "snapshotTop": [
            _snapshot_dict(
                row,
                latest_event_by_key.get(_row_key(row.ticker, row.company_name)),
                comparison_by_name.get(normalize_company_name(row.company_name)),
            )
            for row in sorted(snapshot_rows, key=lambda row: row.estimated_ownership or 0, reverse=True)[:20]
        ],
        "ownershipChanges": comparisons[:20],
        "dailySeries": _daily_series(events_2025),
        "largestChanges": _largest_changes(events_2025, 20),
        "latestEvents": [_event_dict(row) for row in sorted(events_2025, key=lambda row: (str(row.get("disclosed_at", "")), int(row.get("id") or 0)), reverse=True)[:30]],
        "sectorRows": [
            _sector_dict(row, sector_deltas.get(str(row.get("sector_name") or "미분류")))
            for row in sorted(sector_rows, key=lambda row: float(row.get("ownership_sum") or 0), reverse=True)[:12]
        ],
    }


def render_dashboard_html(data: dict[str, Any]) -> str:
    title = escape(str(data["meta"]["title"]))
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    :root {{
      --bg: #f6f7f9;
      --surface: #ffffff;
      --ink: #18202b;
      --muted: #667085;
      --line: #d9dee7;
      --teal: #007c89;
      --plum: #6d3a8f;
      --coral: #d55b4a;
      --amber: #b7791f;
      --green: #2f7d52;
      --blue: #2d5b9a;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: var(--bg);
      letter-spacing: 0;
    }}
    header {{
      border-bottom: 1px solid var(--line);
      background: var(--surface);
    }}
    .wrap {{
      width: min(1440px, calc(100vw - 40px));
      margin: 0 auto;
    }}
    .topbar {{
      display: flex;
      justify-content: space-between;
      align-items: flex-end;
      gap: 24px;
      padding: 22px 0 18px;
    }}
    h1 {{
      margin: 0;
      font-size: 26px;
      line-height: 1.2;
      font-weight: 760;
    }}
    .meta {{
      margin-top: 8px;
      color: var(--muted);
      font-size: 13px;
    }}
    .actions {{
      display: flex;
      gap: 8px;
      align-items: center;
      flex-wrap: wrap;
      justify-content: flex-end;
    }}
    select, button {{
      height: 34px;
      border: 1px solid var(--line);
      border-radius: 7px;
      background: var(--surface);
      color: var(--ink);
      padding: 0 10px;
      font: inherit;
      font-size: 13px;
    }}
    button {{
      cursor: pointer;
      font-weight: 650;
    }}
    main {{
      padding: 18px 0 36px;
    }}
    .kpis {{
      display: grid;
      grid-template-columns: repeat(6, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 18px;
    }}
    .metric {{
      min-height: 96px;
      padding: 14px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface);
    }}
    .metric-label {{
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
    }}
    .metric-value {{
      margin-top: 9px;
      font-size: 26px;
      font-weight: 780;
      white-space: nowrap;
    }}
    .metric-detail {{
      margin-top: 8px;
      color: var(--muted);
      font-size: 12px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: minmax(0, 1.35fr) minmax(360px, 0.65fr);
      gap: 14px;
      align-items: start;
    }}
    .section {{
      border-top: 1px solid var(--line);
      padding: 16px 0 0;
      margin-top: 2px;
    }}
    .section-title {{
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: 16px;
      margin-bottom: 10px;
    }}
    h2 {{
      margin: 0;
      font-size: 16px;
      line-height: 1.25;
    }}
    .hint {{
      color: var(--muted);
      font-size: 12px;
    }}
    .chart-surface, .table-surface {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface);
      overflow: hidden;
    }}
    .chart {{
      min-height: 290px;
      padding: 14px 14px 10px;
    }}
    .bars {{
      display: grid;
      grid-template-columns: repeat(var(--bar-count), minmax(2px, 1fr));
      align-items: end;
      gap: 3px;
      height: 220px;
      padding: 8px 4px 0;
      border-bottom: 1px solid var(--line);
    }}
    .bar {{
      min-height: 1px;
      border-radius: 4px 4px 0 0;
      background: var(--teal);
      position: relative;
    }}
    .bar.negative {{ background: var(--coral); }}
    .chart-legend {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      color: var(--muted);
      font-size: 12px;
      padding-top: 10px;
    }}
    .split {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 14px;
      margin-top: 14px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }}
    th, td {{
      padding: 10px 12px;
      border-bottom: 1px solid #e9edf3;
      vertical-align: middle;
      text-align: left;
    }}
    th {{
      color: var(--muted);
      font-size: 11px;
      font-weight: 750;
      background: #fafbfc;
      white-space: nowrap;
    }}
    td.num, th.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
    tbody tr:hover {{ background: #f8fafc; }}
    .delta-up {{ color: var(--green); font-weight: 700; }}
    .delta-down {{ color: var(--coral); font-weight: 700; }}
    .rank {{
      width: 30px;
      color: var(--muted);
      font-variant-numeric: tabular-nums;
    }}
    .company {{
      font-weight: 700;
      max-width: 220px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }}
    .mini-bars {{
      display: grid;
      gap: 8px;
      padding: 14px;
    }}
    .mini-row {{
      display: grid;
      grid-template-columns: minmax(96px, 150px) 1fr 76px;
      gap: 8px;
      align-items: center;
      font-size: 12px;
    }}
    .track {{
      height: 8px;
      background: #edf1f5;
      border-radius: 999px;
      overflow: hidden;
    }}
    .track.diverging {{
      position: relative;
      overflow: visible;
      background: #eef2f6;
    }}
    .track.diverging::after {{
      content: "";
      position: absolute;
      left: 50%;
      top: -3px;
      width: 1px;
      height: 14px;
      background: #b8c0cc;
    }}
    .fill {{
      height: 100%;
      width: var(--w);
      background: var(--plum);
    }}
    .fill.down {{ background: var(--coral); }}
    .fill.up {{ background: var(--green); }}
    .fill.diverging {{
      position: absolute;
      top: 0;
      width: var(--w);
      z-index: 1;
    }}
    .fill.diverging.up {{
      left: 50%;
      border-radius: 0 999px 999px 0;
    }}
    .fill.diverging.down {{
      right: 50%;
      border-radius: 999px 0 0 999px;
    }}
    .tabs {{
      display: flex;
      gap: 6px;
      margin-bottom: 10px;
      flex-wrap: wrap;
    }}
    .tab[aria-pressed="true"] {{
      color: #fff;
      background: var(--ink);
      border-color: var(--ink);
    }}
    .search-panel {{
      display: grid;
      grid-template-columns: minmax(220px, 320px) 1fr;
      gap: 12px;
      align-items: center;
      margin-bottom: 10px;
    }}
    .search-input {{
      width: 100%;
      height: 38px;
      border: 1px solid var(--line);
      border-radius: 7px;
      padding: 0 12px;
      font: inherit;
      background: var(--surface);
    }}
    .search-summary {{
      color: var(--muted);
      font-size: 13px;
    }}
    .empty {{
      padding: 18px;
      color: var(--muted);
      font-size: 13px;
    }}
    @media (max-width: 1100px) {{
      .kpis {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
      .grid, .split {{ grid-template-columns: 1fr; }}
    }}
    @media (max-width: 700px) {{
      .wrap {{ width: min(100vw - 24px, 1440px); }}
      .topbar {{ align-items: flex-start; flex-direction: column; }}
      .actions {{ justify-content: flex-start; }}
      .kpis {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .search-panel {{ grid-template-columns: 1fr; }}
      .metric-value {{ font-size: 21px; }}
      table {{ font-size: 12px; }}
      th, td {{ padding: 8px; }}
      .company {{ max-width: 140px; }}
      .mini-row {{ grid-template-columns: 96px 1fr 64px; }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="wrap topbar">
      <div>
        <h1>{title}</h1>
        <div class="meta" id="meta"></div>
      </div>
      <div class="actions">
        <select id="trendMetric" aria-label="추세 지표">
          <option value="eventCount">공시 건수</option>
          <option value="increaseCount">증가 건수</option>
          <option value="decreaseCount">감소 건수</option>
          <option value="absDeltaShares">변동 수량</option>
          <option value="absOwnershipDelta">지분율 변동</option>
        </select>
        <button id="downloadJson" type="button">JSON</button>
      </div>
    </div>
  </header>
  <main class="wrap">
    <section class="kpis" id="kpis"></section>
    <div class="grid">
      <section class="section">
        <div class="section-title">
          <h2>2025 일일 변동 흐름</h2>
          <span class="hint">공시일 기준 집계</span>
        </div>
        <div class="chart-surface"><div class="chart" id="trendChart"></div></div>
        <div class="split">
          <div>
            <div class="section-title"><h2>2024 평가액 상위</h2><span class="hint">최신 대비 포함</span></div>
            <div class="table-surface"><table id="baselineTable"></table></div>
          </div>
          <div>
            <div class="section-title"><h2>최신 지분율 상위</h2><span class="hint">지분율 변동 포함</span></div>
            <div class="table-surface"><table id="snapshotTable"></table></div>
          </div>
        </div>
      </section>
      <aside class="section">
        <div class="section-title"><h2>큰 변동</h2><span class="hint">절대 증감수량</span></div>
        <div class="table-surface"><div class="mini-bars" id="changeBars"></div></div>
        <div class="section-title" style="margin-top:14px"><h2>2024 대비 지분율</h2><span class="hint">%p</span></div>
        <div class="table-surface"><div class="mini-bars" id="ownershipBars"></div></div>
      </aside>
    </div>
    <section class="section">
      <div class="section-title"><h2>종목별 히스토리</h2><span class="hint">2024 엑셀 + 공시 DB</span></div>
      <div class="search-panel">
        <input class="search-input" id="stockSearch" type="search" placeholder="종목명 입력" autocomplete="off">
        <div class="search-summary" id="searchSummary"></div>
      </div>
      <div class="table-surface"><table id="searchTable"></table></div>
    </section>
    <section class="section">
      <div class="tabs">
        <button class="tab" data-table="events" aria-pressed="true" type="button">최근 이벤트</button>
        <button class="tab" data-table="sectors" aria-pressed="false" type="button">섹터 요약</button>
      </div>
      <div class="table-surface"><table id="detailTable"></table></div>
    </section>
  </main>
  <script>
    const DASHBOARD_DATA = {payload};
    const fmt = new Intl.NumberFormat("ko-KR");
    const pct = (v, digits = 2) => v == null ? "" : `${{(v * 100).toFixed(digits)}}%`;
    const pp = v => v == null ? "" : `${{(v * 100).toFixed(2)}}%p`;
    const signedPp = v => v == null ? "" : `${{v > 0 ? "+" : ""}}${{(v * 100).toFixed(2)}}%p`;
    const shares = v => v == null ? "" : fmt.format(Math.round(v));
    const money = v => v == null ? "" : fmt.format(Math.round(v));
    const signed = v => v == null ? "" : `${{v > 0 ? "+" : ""}}${{shares(v)}}`;
    const cls = v => v > 0 ? "delta-up" : v < 0 ? "delta-down" : "";
    const norm = value => String(value || "").toLowerCase().replace(/\\s+/g, "").replaceAll("(주)", "").replaceAll("㈜", "").replace(/보통주$|우선주$/g, "");

    function cell(value, className = "") {{
      return `<td class="${{className}}">${{value ?? ""}}</td>`;
    }}

    function renderKpis() {{
      document.getElementById("meta").textContent =
        `${{DASHBOARD_DATA.meta.baselineYear}}년 말 엑셀 기준 | ${{DASHBOARD_DATA.meta.basisLabel}} | 기준일 ${{DASHBOARD_DATA.meta.asOfDate}} | 생성 ${{DASHBOARD_DATA.meta.generatedAt}}`;
      document.getElementById("kpis").innerHTML = DASHBOARD_DATA.kpis.map(item => `
        <article class="metric">
          <div class="metric-label">${{item.label}}</div>
          <div class="metric-value">${{item.value}}</div>
          <div class="metric-detail">${{item.detail}}</div>
        </article>
      `).join("");
    }}

    function renderTrend(metric = "eventCount") {{
      const rows = DASHBOARD_DATA.dailySeries;
      const isOwnershipMetric = metric.toLowerCase().includes("ownership");
      const max = Math.max(isOwnershipMetric ? 0.0001 : 1, ...rows.map(row => Math.abs(row[metric] || 0)));
      const labels = rows.length ? `${{rows[0].date}} - ${{rows[rows.length - 1].date}}` : "데이터 없음";
      const formatMetric = isOwnershipMetric ? signedPp : shares;
      document.getElementById("trendChart").innerHTML = `
        <div class="bars" style="--bar-count:${{Math.max(rows.length, 1)}}">
          ${{rows.map(row => {{
            const value = row[metric] || 0;
            const h = Math.max(1, Math.round(Math.abs(value) / max * 100));
            return `<div class="bar ${{value < 0 ? "negative" : ""}}" style="height:${{h}}%" title="${{row.date}}: ${{formatMetric(value)}}"></div>`;
          }}).join("")}}
        </div>
        <div class="chart-legend"><span>${{labels}}</span><span>최대 ${{formatMetric(max)}}</span></div>
      `;
    }}

    function renderTable(id, headers, rows) {{
      document.getElementById(id).innerHTML = `
        <thead><tr>${{headers.map(h => `<th class="${{h.className || ""}}">${{h.label}}</th>`).join("")}}</tr></thead>
        <tbody>${{rows.join("")}}</tbody>
      `;
    }}

    function renderBaseline() {{
      renderTable("baselineTable",
        [{{label:"#"}}, {{label:"종목"}}, {{label:"평가액", className:"num"}}, {{label:"지분율", className:"num"}}, {{label:"최신 대비", className:"num"}}],
        DASHBOARD_DATA.baselineTop.slice(0, 12).map(row => `<tr>
          ${{cell(row.rank, "rank")}}${{cell(row.companyName, "company")}}${{cell(money(row.marketValue), "num")}}${{cell(pct(row.ownership), "num")}}${{cell(signedPp(row.currentOwnershipDiff), `num ${{cls(row.currentOwnershipDiff)}}`)}}
        </tr>`)
      );
      renderTable("snapshotTable",
        [{{label:"#"}}, {{label:"종목"}}, {{label:"코드"}}, {{label:"지분율", className:"num"}}, {{label:"지분율 변동", className:"num"}}, {{label:"수량 변동", className:"num"}}],
        DASHBOARD_DATA.snapshotTop.slice(0, 12).map((row, index) => `<tr>
          ${{cell(index + 1, "rank")}}${{cell(row.companyName, "company")}}${{cell(row.ticker)}}${{cell(pct(row.ownership), "num")}}${{cell(signedPp(row.lastOwnershipDelta), `num ${{cls(row.lastOwnershipDelta)}}`)}}${{cell(signed(row.lastDeltaShares), `num ${{cls(row.lastDeltaShares)}}`)}}
        </tr>`)
      );
    }}

    function renderMiniBars(id, rows, valueKey, labelKey, formatValue, limit = 10) {{
      const shown = rows.slice(0, limit);
      const max = Math.max(1, ...shown.map(row => Math.abs(row[valueKey] || 0)));
      document.getElementById(id).innerHTML = shown.map(row => {{
        const value = row[valueKey] || 0;
        const width = Math.max(2, Math.round(Math.abs(value) / max * 100));
        const direction = value < 0 ? "down" : "up";
        return `<div class="mini-row">
          <div class="company" title="${{row[labelKey]}}">${{row[labelKey]}}</div>
          <div class="track"><div class="fill ${{direction}}" style="--w:${{width}}%"></div></div>
          <div class="num ${{cls(value)}}">${{formatValue(value)}}</div>
        </div>`;
      }}).join("");
    }}

    function renderDivergingMiniBars(id, rows, valueKey, labelKey, formatValue, limit = 10) {{
      const shown = rows.slice(0, limit);
      const max = Math.max(0.0001, ...shown.map(row => Math.abs(row[valueKey] || 0)));
      document.getElementById(id).innerHTML = shown.map(row => {{
        const value = row[valueKey] || 0;
        const width = Math.max(2, Math.round(Math.abs(value) / max * 45));
        const direction = value < 0 ? "down" : "up";
        return `<div class="mini-row">
          <div class="company" title="${{row[labelKey]}}">${{row[labelKey]}}</div>
          <div class="track diverging"><div class="fill diverging ${{direction}}" style="--w:${{width}}%"></div></div>
          <div class="num ${{cls(value)}}">${{formatValue(value)}}</div>
        </div>`;
      }}).join("");
    }}

    function renderChangeBars() {{
      const shown = DASHBOARD_DATA.largestChanges.slice(0, 10);
      const max = Math.max(1, ...shown.map(row => Math.abs(row.deltaShares || 0)));
      document.getElementById("changeBars").innerHTML = shown.map(row => {{
        const value = row.deltaShares || 0;
        const width = Math.max(2, Math.round(Math.abs(value) / max * 100));
        const direction = value < 0 ? "down" : "up";
        return `<div class="mini-row">
          <div class="company" title="${{row.companyName}}">${{row.companyName}}</div>
          <div class="track"><div class="fill ${{direction}}" style="--w:${{width}}%"></div></div>
          <div class="num ${{cls(value)}}">${{signed(value)}}<br>${{signedPp(row.ownershipDelta)}}</div>
        </div>`;
      }}).join("");
    }}

    function renderDetails(kind = "events") {{
      if (kind === "sectors") {{
        renderTable("detailTable",
          [{{label:"섹터"}}, {{label:"종목 수", className:"num"}}, {{label:"지분율 합계", className:"num"}}, {{label:"지분율 변동", className:"num"}}, {{label:"방향"}}],
          DASHBOARD_DATA.sectorRows.map(row => `<tr>
            ${{cell(row.sectorName)}}${{cell(fmt.format(row.companyCount), "num")}}${{cell(pct(row.ownershipSum), "num")}}${{cell(signedPp(row.ownershipDiffSum), `num ${{cls(row.ownershipDiffSum)}}`)}}${{cell(row.netDirection)}}
          </tr>`)
        );
        return;
      }}
      renderTable("detailTable",
        [{{label:"공시일"}}, {{label:"종목"}}, {{label:"코드"}}, {{label:"수량 증감", className:"num"}}, {{label:"지분율 증감", className:"num"}}, {{label:"변동 후 수량", className:"num"}}, {{label:"지분율", className:"num"}}, {{label:"사유"}}],
        DASHBOARD_DATA.latestEvents.map(row => `<tr>
          ${{cell(row.disclosedAt)}}${{cell(row.companyName, "company")}}${{cell(row.ticker)}}${{cell(signed(row.deltaShares), `num ${{cls(row.deltaShares)}}`)}}${{cell(signedPp(row.ownershipDelta), `num ${{cls(row.ownershipDelta)}}`)}}${{cell(shares(row.sharesAfter), "num")}}${{cell(pct(row.ownershipAfter), "num")}}${{cell(row.changeReason)}}
        </tr>`)
      );
    }}

    function renderSearch(query = "") {{
      const q = norm(query);
      const summary = document.getElementById("searchSummary");
      if (!q) {{
        summary.textContent = "";
        document.getElementById("searchTable").innerHTML = `<tbody><tr><td class="empty">종목명을 입력하면 2024 엑셀 기준점과 공시 DB 변동 내역이 이어서 표시됩니다.</td></tr></tbody>`;
        return;
      }}
      const baseline = DASHBOARD_DATA.baselineRows
        .filter(row => norm(row.companyName).includes(q))
        .map(row => ({{
          date: `${{DASHBOARD_DATA.meta.baselineYear}}-12-31`,
          source: "기준 엑셀",
          companyName: row.companyName,
          ticker: "",
          sharesAfter: null,
          deltaShares: null,
          ownershipAfter: row.ownership,
          ownershipDelta: null,
          reason: `평가액 ${{money(row.marketValue)}}억원`
        }}));
      const events = DASHBOARD_DATA.eventHistory.filter(row =>
        norm(row.companyName).includes(q) || norm(row.ticker).includes(q)
      );
      const rows = [...baseline, ...events].sort((a, b) =>
        `${{a.date || a.disclosedAt || ""}}${{a.source}}`.localeCompare(`${{b.date || b.disclosedAt || ""}}${{b.source}}`)
      );
      summary.textContent = `${{rows.length}}건`;
      if (!rows.length) {{
        document.getElementById("searchTable").innerHTML = `<tbody><tr><td class="empty">검색 결과가 없습니다.</td></tr></tbody>`;
        return;
      }}
      renderTable("searchTable",
        [{{label:"일자"}}, {{label:"출처"}}, {{label:"종목"}}, {{label:"코드"}}, {{label:"수량 증감", className:"num"}}, {{label:"지분율 증감", className:"num"}}, {{label:"보유수량", className:"num"}}, {{label:"지분율", className:"num"}}, {{label:"내용"}}],
        rows.map(row => `<tr>
          ${{cell(row.date || row.disclosedAt)}}${{cell(row.source || "공시 DB")}}${{cell(row.companyName, "company")}}${{cell(row.ticker)}}${{cell(signed(row.deltaShares), `num ${{cls(row.deltaShares)}}`)}}${{cell(signedPp(row.ownershipDelta), `num ${{cls(row.ownershipDelta)}}`)}}${{cell(shares(row.sharesAfter), "num")}}${{cell(pct(row.ownershipAfter), "num")}}${{cell(row.reason || row.changeReason)}}
        </tr>`)
      );
    }}

    renderKpis();
    renderTrend();
    renderBaseline();
    renderChangeBars();
    renderDivergingMiniBars("ownershipBars", DASHBOARD_DATA.ownershipChanges, "ownershipDiff", "companyName", signedPp);
    renderDetails();
    renderSearch();

    document.getElementById("trendMetric").addEventListener("change", event => renderTrend(event.target.value));
    document.getElementById("stockSearch").addEventListener("input", event => renderSearch(event.target.value));
    document.querySelectorAll(".tab").forEach(button => {{
      button.addEventListener("click", () => {{
        document.querySelectorAll(".tab").forEach(item => item.setAttribute("aria-pressed", "false"));
        button.setAttribute("aria-pressed", "true");
        renderDetails(button.dataset.table);
      }});
    }});
    document.getElementById("downloadJson").addEventListener("click", () => {{
      const blob = new Blob([JSON.stringify(DASHBOARD_DATA, null, 2)], {{type: "application/json"}});
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `nps-dashboard-${{DASHBOARD_DATA.meta.asOfDate}}.json`;
      link.click();
      URL.revokeObjectURL(url);
    }});
  </script>
</body>
</html>
"""


def _ownership_comparisons(baseline_rows: list[BaselineHolding], snapshot_rows: list[SnapshotRow]) -> list[dict[str, Any]]:
    baseline_by_name = {normalize_company_name(row.company_name): row for row in baseline_rows}
    comparisons: list[dict[str, Any]] = []
    for row in snapshot_rows:
        baseline = baseline_by_name.get(normalize_company_name(row.company_name))
        if baseline is None or baseline.ownership is None or row.estimated_ownership is None:
            continue
        comparisons.append(
            {
                "companyName": row.company_name,
                "ticker": row.ticker or "",
                "baselineOwnership": baseline.ownership,
                "currentOwnership": row.estimated_ownership,
                "ownershipDiff": row.estimated_ownership - baseline.ownership,
                "baselineRank": baseline.rank,
            }
        )
    return sorted(comparisons, key=lambda item: abs(float(item["ownershipDiff"])), reverse=True)


def _with_ownership_deltas(
    event_rows: list[dict[str, Any]],
    baseline_rows: list[BaselineHolding],
) -> list[dict[str, Any]]:
    baseline_by_name = {normalize_company_name(row.company_name): row.ownership for row in baseline_rows}
    previous_by_key: dict[str, float] = {}
    enriched: list[dict[str, Any]] = []
    for row in sorted(event_rows, key=lambda item: (str(item.get("disclosed_at") or ""), str(item.get("effective_date") or ""), int(item.get("id") or 0))):
        copied = dict(row)
        key = _row_key(str(row.get("ticker") or ""), str(row.get("company_name") or ""))
        ownership_after = _as_float(row.get("ownership_after"))
        previous = previous_by_key.get(key)
        if previous is None:
            previous = baseline_by_name.get(normalize_company_name(str(row.get("company_name") or "")))
        copied["ownership_delta"] = (
            ownership_after - previous
            if ownership_after is not None and previous is not None
            else None
        )
        if ownership_after is not None:
            previous_by_key[key] = ownership_after
        enriched.append(copied)
    return enriched


def _latest_event_by_key(event_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in event_rows:
        latest[_row_key(str(row.get("ticker") or ""), str(row.get("company_name") or ""))] = row
    return latest


def _row_key(ticker: str | None, company_name: str) -> str:
    return ticker or normalize_company_name(company_name)


def _sector_ownership_deltas(
    snapshot_rows: list[SnapshotRow],
    comparison_by_name: dict[str, dict[str, Any]],
) -> dict[str, float]:
    grouped: dict[str, float] = defaultdict(float)
    for row in snapshot_rows:
        comparison = comparison_by_name.get(normalize_company_name(row.company_name))
        if not comparison:
            continue
        grouped[row.sector_name or "미분류"] += float(comparison.get("ownershipDiff") or 0.0)
    return dict(grouped)


def _daily_series(event_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "date": "",
            "eventCount": 0,
            "increaseCount": 0,
            "decreaseCount": 0,
            "netDeltaShares": 0.0,
            "absDeltaShares": 0.0,
            "netOwnershipDelta": 0.0,
            "absOwnershipDelta": 0.0,
        }
    )
    for row in event_rows:
        date = str(row.get("disclosed_at") or "")
        if not date:
            continue
        target = grouped[date]
        target["date"] = date
        target["eventCount"] += 1
        delta = _as_float(row.get("delta_shares")) or 0.0
        if delta > 0:
            target["increaseCount"] += 1
        elif delta < 0:
            target["decreaseCount"] += 1
        target["netDeltaShares"] += delta
        target["absDeltaShares"] += abs(delta)
        ownership_delta = _as_float(row.get("ownership_delta")) or 0.0
        target["netOwnershipDelta"] += ownership_delta
        target["absOwnershipDelta"] += abs(ownership_delta)
    return [grouped[date] for date in sorted(grouped)]


def _largest_changes(event_rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    rows = [row for row in event_rows if _as_float(row.get("delta_shares")) not in (None, 0.0)]
    rows = sorted(rows, key=lambda row: abs(float(row.get("delta_shares") or 0)), reverse=True)
    return [_event_dict(row) for row in rows[:limit]]


def _baseline_dict(row: BaselineHolding, comparison: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "rank": row.rank,
        "companyName": row.company_name,
        "marketValue": row.market_value_krw_100m,
        "assetWeight": row.asset_weight,
        "ownership": row.ownership,
        "currentOwnership": comparison.get("currentOwnership") if comparison else None,
        "currentOwnershipDiff": comparison.get("ownershipDiff") if comparison else None,
    }


def _snapshot_dict(
    row: SnapshotRow,
    latest_event: dict[str, Any] | None = None,
    comparison: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "companyName": row.company_name,
        "ticker": row.ticker or "",
        "estimatedShares": row.estimated_shares,
        "ownership": row.estimated_ownership,
        "baselineOwnership": comparison.get("baselineOwnership") if comparison else None,
        "baselineOwnershipDiff": comparison.get("ownershipDiff") if comparison else None,
        "lastDeltaShares": row.last_delta_shares,
        "lastOwnershipDelta": _as_float(latest_event.get("ownership_delta")) if latest_event else None,
        "lastChangeReason": row.last_change_reason or "",
        "lastDisclosedAt": row.last_disclosed_at,
        "sectorName": row.sector_name,
    }


def _event_dict(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "companyName": str(row.get("company_name") or ""),
        "ticker": str(row.get("ticker") or ""),
        "effectiveDate": str(row.get("effective_date") or ""),
        "disclosedAt": str(row.get("disclosed_at") or ""),
        "deltaShares": _as_float(row.get("delta_shares")),
        "ownershipDelta": _as_float(row.get("ownership_delta")),
        "sharesAfter": _as_float(row.get("shares_after")),
        "ownershipAfter": _as_float(row.get("ownership_after")),
        "changeReason": str(row.get("change_reason") or ""),
        "eventType": str(row.get("event_type") or ""),
    }


def _sector_dict(row: dict[str, Any], ownership_diff_sum: float | None = None) -> dict[str, Any]:
    return {
        "sectorName": str(row.get("sector_name") or "미분류"),
        "companyCount": int(row.get("company_count") or 0),
        "ownershipSum": _as_float(row.get("ownership_sum")) or 0.0,
        "ownershipDiffSum": ownership_diff_sum,
        "netDirection": str(row.get("net_direction") or ""),
    }


def _as_float(value: object | None) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_krw_100m(value: float) -> str:
    if value >= 10000:
        return f"{value / 10000:,.1f}조원"
    return f"{value:,.0f}억원"
