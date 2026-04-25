from __future__ import annotations


def render_strategy_html() -> str:
    return """<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>국민연금 10% 이상 보유주 매수 전략</title>
  <style>
    :root {
      --bg: #f6f7f9;
      --surface: #ffffff;
      --ink: #18202b;
      --muted: #667085;
      --line: #d9dee7;
      --blue: #2d5b9a;
      --green: #2f7d52;
      --amber: #a16207;
      --red: #b42318;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      letter-spacing: 0;
    }
    .wrap {
      width: min(1180px, calc(100vw - 40px));
      margin: 0 auto;
      padding: 28px 0 44px;
    }
    header {
      margin-bottom: 18px;
    }
    h1 {
      margin: 0;
      font-size: 28px;
      line-height: 1.22;
      font-weight: 780;
    }
    .meta {
      margin-top: 8px;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.55;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
      margin-bottom: 14px;
    }
    .metric, section {
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
    }
    .metric {
      min-height: 118px;
      padding: 16px;
    }
    .metric-label {
      color: var(--muted);
      font-size: 12px;
      font-weight: 760;
    }
    .metric-value {
      margin-top: 8px;
      font-size: 26px;
      font-weight: 780;
    }
    .metric-note {
      margin-top: 8px;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.45;
    }
    section {
      padding: 18px;
      margin-top: 14px;
    }
    h2 {
      margin: 0 0 12px;
      font-size: 18px;
      line-height: 1.25;
    }
    h3 {
      margin: 14px 0 8px;
      font-size: 15px;
    }
    p {
      margin: 8px 0;
      color: #2f3947;
      line-height: 1.65;
      font-size: 14px;
    }
    ul, ol {
      margin: 8px 0 0 20px;
      padding: 0;
      color: #2f3947;
      line-height: 1.65;
      font-size: 14px;
    }
    li { margin: 5px 0; }
    .flow {
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 8px;
      margin-top: 12px;
    }
    .step {
      min-height: 86px;
      border: 1px solid var(--line);
      border-left: 4px solid var(--blue);
      border-radius: 8px;
      padding: 12px;
      background: #fbfcfd;
    }
    .step strong {
      display: block;
      margin-bottom: 6px;
      font-size: 13px;
    }
    .step span {
      display: block;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.45;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      margin-top: 10px;
      font-size: 13px;
    }
    th, td {
      border-bottom: 1px solid var(--line);
      padding: 10px 8px;
      text-align: left;
      vertical-align: top;
    }
    th {
      color: var(--muted);
      font-size: 12px;
      font-weight: 760;
      background: #fbfcfd;
    }
    .tag {
      display: inline-block;
      border-radius: 999px;
      padding: 3px 8px;
      font-size: 12px;
      font-weight: 760;
      background: #eef4ff;
      color: var(--blue);
      white-space: nowrap;
    }
    .good { color: var(--green); font-weight: 760; }
    .watch { color: var(--amber); font-weight: 760; }
    .bad { color: var(--red); font-weight: 760; }
    .sources a {
      color: var(--blue);
      text-decoration: none;
      font-weight: 650;
    }
    .sources a:hover { text-decoration: underline; }
    @media (max-width: 900px) {
      .grid, .flow { grid-template-columns: 1fr; }
      h1 { font-size: 23px; }
      table { font-size: 12px; }
      th, td { padding: 9px 6px; }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <header>
      <h1>국민연금 10% 이상 보유주 매수 전략</h1>
      <div class="meta">기준: DART 지분공시 2026-04-20까지 반영, 2024년 연결 재무제표 기준. 이 탭은 국민연금 보유를 매수 신호가 아니라 관심종목 필터로 사용하는 전략 메모입니다.</div>
    </header>

    <div class="grid">
      <div class="metric">
        <div class="metric-label">관심 유니버스</div>
        <div class="metric-value">35개</div>
        <div class="metric-note">최신 공시 기준 국민연금 추정 지분율 10% 이상 유지 종목</div>
      </div>
      <div class="metric">
        <div class="metric-label">중심 섹터</div>
        <div class="metric-value">금융·소재·유통</div>
        <div class="metric-note">각 7개, 7개, 5개로 대형 IT보다 중대형 가치·산업재 성격이 강함</div>
      </div>
      <div class="metric">
        <div class="metric-label">핵심 원칙</div>
        <div class="metric-value">후행성 보정</div>
        <div class="metric-note">지분공시만 추종하지 않고 이격도, 시장 국면, 외국인 수급으로 재검증</div>
      </div>
    </div>

    <section>
      <h2>전략 요약</h2>
      <p>국민연금 10% 이상 보유는 매수 트리거가 아니라 1차 필터입니다. 국민연금은 장기·분산·초대형 자금이라 시장 하락을 피하지 못하고, 공시는 후행적입니다. 따라서 실제 매수는 실적 개선, 과열이 아닌 주가 위치, 대형주 우호 국면, 외국인 수급 유지가 함께 확인될 때만 진행합니다.</p>
      <div class="flow">
        <div class="step"><strong>1. 10% 이상</strong><span>최신 DART 지분공시 기준 유니버스 구성</span></div>
        <div class="step"><strong>2. 실적 개선</strong><span>매출·이익 개선 또는 컨센서스 상향 확인</span></div>
        <div class="step"><strong>3. 시장 국면</strong><span>KOSPI200/대형주 상대강도 우호 여부 점검</span></div>
        <div class="step"><strong>4. 이격도</strong><span>강하지만 과열이 아닌 가격대만 허용</span></div>
        <div class="step"><strong>5. 외국인 수급</strong><span>공격형 종목은 외국인 이탈 여부를 교차 검증</span></div>
      </div>
    </section>

    <section>
      <h2>보완점 및 주의사항</h2>
      <h3>국내 증시의 특수성: 국민연금도 물린다</h3>
      <p>국내 증시는 장기 박스권과 수급 쏠림이 자주 나타납니다. 국민연금 보유 종목은 대형·우량·유동성 종목이 많기 때문에 중소형주나 테마주 장세에서는 전략 효율이 떨어질 수 있습니다. 이 구간에서는 포트폴리오 비중을 줄이고, 실적 서프라이즈가 확인된 종목만 남깁니다.</p>
      <h3>데이터의 후행성</h3>
      <p>지분공시는 실시간 신호가 아닙니다. 공시 확인 시점에는 실적 모멘텀이 이미 주가에 반영됐을 수 있습니다. 그래서 업종 대비 강한 종목이라도 60일선 대비 과열, 52주 신고가 이후 거래량 급증, 단기 장대음봉은 매수 금지 신호로 둡니다.</p>
      <h3>공격형 종목의 변동성</h3>
      <p>이수페타시스, 효성중공업, 삼양식품, 코스맥스·한국콜마 같은 종목은 성장성이 뚜렷하지만 차익 실현 압력도 커질 수 있습니다. 국민연금이 10%를 유지해도 외국인 20거래일 순매도가 지속되면 매수 보류 또는 비중 축소로 처리합니다.</p>
    </section>

    <section>
      <h2>매수·보류·매도 규칙</h2>
      <table>
        <thead>
          <tr><th>구분</th><th>조건</th><th>판단</th></tr>
        </thead>
        <tbody>
          <tr><td><span class="tag">매수</span></td><td>국민연금 10% 이상, 실적 개선, 대형주 우호 국면, 60일선 대비 -5%~+15%, 외국인 20거래일 순매수 또는 지분율 안정</td><td class="good">신규 편입 가능</td></tr>
          <tr><td><span class="tag">보류</span></td><td>실적은 좋지만 60일선 대비 +20% 이상, RSI 75 이상, 52주 신고가 이후 거래량 과열</td><td class="watch">관심 유지, 추격 매수 금지</td></tr>
          <tr><td><span class="tag">축소</span></td><td>외국인 20거래일 순매도 지속, 업종 대비 상대강도 둔화, 국민연금 순매도 반복</td><td class="watch">비중 감축</td></tr>
          <tr><td><span class="tag">제외</span></td><td>국민연금 지분율 10% 하회, 2회 연속 의미 있는 순매도, 실적 전망 하향, 대형주 장세 종료</td><td class="bad">유니버스 제외</td></tr>
        </tbody>
      </table>
    </section>

    <section>
      <h2>종목군 운영 방식</h2>
      <table>
        <thead>
          <tr><th>군</th><th>대표 후보</th><th>운영 포인트</th></tr>
        </thead>
        <tbody>
          <tr><td>공격형</td><td>이수페타시스, 효성중공업, 삼양식품, 코스맥스, 한국콜마</td><td>실적 성장과 테마가 분명하지만 외국인 수급과 이격도 필터를 가장 엄격하게 적용</td></tr>
          <tr><td>균형형</td><td>삼성전기, HD건설기계, CJ대한통운, KCC, 한국금융지주, 신세계</td><td>10~12개 종목으로 분산하고 한 종목 10%, 한 테마 30%를 넘기지 않음</td></tr>
          <tr><td>가치형</td><td>삼성증권, 키움증권, 한국금융지주, 현대백화점, 롯데쇼핑, KCC</td><td>밸류에이션, 배당·자사주, 업황 바닥 통과 여부를 함께 확인</td></tr>
        </tbody>
      </table>
    </section>

    <section class="sources">
      <h2>데이터 출처와 한계</h2>
      <p>보유 지분은 DART 지분공시와 로컬 스냅샷 DB를 기준으로 계산했습니다. 매출은 OpenDART 단일회사 전체 재무제표 API의 2024년 사업보고서 연결 재무제표를 사용했습니다. 금융사는 제조업식 매출액과 비교가 어려워 해석에 주의가 필요합니다.</p>
      <ul>
        <li><a href="https://fund.nps.or.kr/oprtprcn/ivsmprcn/getOHED0003M0.do" target="_blank" rel="noreferrer">국민연금 국내주식 운용현황</a></li>
        <li><a href="https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS003&amp;apiId=2019020" target="_blank" rel="noreferrer">OpenDART 단일회사 전체 재무제표 API</a></li>
        <li><a href="https://data.krx.co.kr/contents/MDC/MAIN/main/index.cmd?vsView=Y" target="_blank" rel="noreferrer">KRX 투자자별 매매동향</a></li>
      </ul>
    </section>
  </div>
</body>
</html>
"""
