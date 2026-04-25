from __future__ import annotations

from html import escape
from pathlib import Path


def export_combined_html(
    output_path: str | Path,
    *,
    dashboard_html: str,
    sector_trends_html: str,
    title: str = "국민연금 국내주식 통합 대시보드",
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        _render_combined_html(
            dashboard_html=dashboard_html,
            sector_trends_html=sector_trends_html,
            title=title,
        ),
        encoding="utf-8",
    )
    return output


def _render_combined_html(*, dashboard_html: str, sector_trends_html: str, title: str) -> str:
    dashboard_srcdoc = escape(dashboard_html, quote=True)
    sector_srcdoc = escape(sector_trends_html, quote=True)
    escaped_title = escape(title)
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escaped_title}</title>
  <style>
    :root {{
      --bg: #f1f3f5;
      --surface: #ffffff;
      --ink: #18202b;
      --muted: #697282;
      --line: #d6dce4;
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
      position: sticky;
      top: 0;
      z-index: 10;
      background: var(--surface);
      border-bottom: 1px solid var(--line);
    }}
    .wrap {{
      width: min(1440px, calc(100vw - 32px));
      margin: 0 auto;
    }}
    .top {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 18px;
      padding: 14px 0;
    }}
    h1 {{
      margin: 0;
      font-size: 20px;
      line-height: 1.2;
    }}
    .tabs {{
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }}
    button {{
      height: 34px;
      border: 1px solid var(--line);
      border-radius: 7px;
      background: var(--surface);
      color: var(--ink);
      padding: 0 12px;
      font: inherit;
      font-size: 13px;
      font-weight: 700;
      cursor: pointer;
    }}
    button[aria-pressed="true"] {{
      background: var(--ink);
      border-color: var(--ink);
      color: #fff;
    }}
    .frame-wrap {{
      width: min(1440px, calc(100vw - 32px));
      margin: 14px auto 28px;
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
    }}
    iframe {{
      display: block;
      width: 100%;
      min-height: calc(100vh - 92px);
      height: 1900px;
      border: 0;
      background: #fff;
    }}
    iframe[hidden] {{ display: none; }}
    .note {{
      color: var(--muted);
      font-size: 12px;
      padding: 0 0 10px;
    }}
    @media (max-width: 760px) {{
      .top {{ align-items: flex-start; flex-direction: column; }}
      .tabs {{ justify-content: flex-start; }}
      iframe {{ height: 2200px; }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="wrap top">
      <div>
        <h1>{escaped_title}</h1>
        <div class="note">포트폴리오와 섹터 변화를 하나의 정적 HTML 안에 탭으로 묶었습니다.</div>
      </div>
      <div class="tabs">
        <button type="button" data-frame="dashboardFrame" aria-pressed="true">포트폴리오</button>
        <button type="button" data-frame="sectorFrame" aria-pressed="false">섹터 변화</button>
      </div>
    </div>
  </header>
  <main class="frame-wrap">
    <iframe id="dashboardFrame" title="포트폴리오 대시보드" srcdoc="{dashboard_srcdoc}"></iframe>
    <iframe id="sectorFrame" title="섹터 변화" srcdoc="{sector_srcdoc}" hidden></iframe>
  </main>
  <script>
    const buttons = document.querySelectorAll("button[data-frame]");
    const frames = document.querySelectorAll("iframe");
    buttons.forEach(button => {{
      button.addEventListener("click", () => {{
        buttons.forEach(item => item.setAttribute("aria-pressed", "false"));
        frames.forEach(frame => frame.hidden = true);
        button.setAttribute("aria-pressed", "true");
        document.getElementById(button.dataset.frame).hidden = false;
        window.scrollTo({{top: 0, behavior: "auto"}});
      }});
    }});
  </script>
</body>
</html>
"""
