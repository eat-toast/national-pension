# 국민연금 포트폴리오 추적기 실행 계획

## Summary
이 계획은 `/Users/isaac/Documents/national pension` 폴더를 작업 루트로 사용합니다.
구현 시작 시 가장 먼저 `PLAN.md`에 이 문서를 저장하고, 이어서 Python 기반 수집기, SQLite 저장소, 기준일별 스냅샷 생성기, 엑셀 출력기, 알림/섹터 분석 순서로 진행합니다.
최종 결과는 "원천 이벤트 DB + 기준일별 엑셀 산출물 + 알림/섹터 요약"입니다.

## Implementation Changes
- 초기 구조
  - 루트에 `PLAN.md`, `.env.example`, `requirements.txt`, `src/`, `data/`, `output/`를 생성합니다.
  - `src/`는 `collect/`, `parse/`, `db/`, `snapshot/`, `export/`, `alerts/`, `analysis/`, `cli/`로 분리합니다.
  - DB는 `data/nps_portfolio.sqlite3`를 기본 경로로 사용합니다.

- 데이터 수집/파싱
  - DART API 수집기는 기간 기준으로 공시 목록을 가져오고, `주식등의대량보유상황보고서`와 `국민연금공단`만 필터링합니다.
  - 각 공시에 대해 접수번호, 공시일, 정정 여부, 원문 URL을 저장하고, 본문 표에서 종목코드, 종목명, 변동일, 증감수량, 변동 후 보유수량, 지분율, 변동사유를 추출합니다.
  - 정정 공시는 원본과 연결해 관리하고, 기본 조회에서는 최신 유효본만 반영합니다.
  - 파싱 실패 공시는 별도 상태로 남겨 재처리 가능하게 둡니다.

- 저장소/도메인 모델
  - `reports` 테이블: 공시 메타데이터와 파싱 상태 저장.
  - `holding_events` 테이블: 종목별 변동 이벤트 저장.
  - `sector_map` 테이블: 종목코드-섹터 매핑 저장.
  - `snapshot_runs`와 `snapshot_rows` 테이블: 생성한 기준일 스냅샷 이력 저장.
  - 조회는 `effective_date`와 `disclosure_date` 두 기준을 모두 지원합니다.

- 스냅샷/엑셀 출력
  - 스냅샷 생성기는 특정 날짜와 기준 타입을 받아 해당 시점까지 유효한 이벤트를 누적해 종목별 현재 상태를 계산합니다.
  - 엑셀 출력기는 기존 연말 파일의 보기 형식을 참고하되, 출력 파일은 `output/nps_snapshot_YYYY-MM-DD_{basis}.xlsx` 규칙을 사용합니다.
  - 시트는 `포트폴리오`, `이벤트이력`, `섹터요약`, `메타정보` 4개로 고정합니다.
  - `포트폴리오` 시트에는 종목명, 종목코드, 추정 보유수량, 추정 지분율, 최근 변동수량, 최근 변동사유, 최근 변동일, 최근 공시일을 포함합니다.

- 알림/섹터 분석
  - 알림은 카카오톡 나에게 보내기 기준으로 구현하고, 조건은 `신규 5% 편입`, `10% 이상 도달`, `직전 대비 지분율 1%p 이상 변동`으로 시작합니다.
  - 섹터 분석은 `종목 수`, `지분율 합계`, `최근 순매수/순매도 방향`을 일자 기준으로 계산합니다.
  - 섹터 매핑이 없는 종목은 `미분류`로 처리합니다.

- CLI 인터페이스
  - `sync-reports --from YYYY-MM-DD --to YYYY-MM-DD`
  - `build-snapshot --date YYYY-MM-DD --basis effective_date|disclosure_date`
  - `export-xlsx --date YYYY-MM-DD --basis effective_date|disclosure_date --output <path>`
  - `send-alerts --since YYYY-MM-DD`
  - `rebuild-sector-summary --date YYYY-MM-DD --basis effective_date|disclosure_date`

## Test Plan
- 공시 목록 필터링이 정확한지 확인합니다.
- 본문 표 파싱이 성공하는 실제 샘플 공시와 실패 샘플 공시를 각각 검증합니다.
- 정정 공시가 있을 때 최신 유효본만 반영되는지 확인합니다.
- 같은 데이터로 `effective_date` 기준과 `disclosure_date` 기준 결과가 다르게 나오는 케이스를 검증합니다.
- 스냅샷 생성 결과가 특정 날짜 전후로 기대한 보유 상태를 유지하는지 확인합니다.
- 엑셀 파일의 한글, 숫자 포맷, 퍼센트 포맷, 빈 결과 처리 여부를 확인합니다.
- 알림 조건 3종이 중복 없이 정확히 발송되는지 검증합니다.
- 섹터 매핑 누락 종목이 `미분류`로 집계되는지 확인합니다.

## Execution Order
1. `PLAN.md` 저장.
2. 프로젝트 골격과 의존성 파일 생성.
3. DB 스키마와 도메인 모델 구현.
4. DART 수집기와 보고서 파서 구현.
5. 스냅샷 계산기 구현.
6. 엑셀 출력기 구현.
7. 카카오톡 알림과 섹터 분석 구현.
8. 샘플 기간으로 동작 검증 후 운영 실행 스크립트 정리.

## Assumptions
- 구현 시작 시 `PLAN.md` 파일명으로 루트에 저장합니다.
- v1의 기준 DB는 SQLite입니다.
- `평가액(억원)`은 별도 시세 데이터 없이는 정확히 복원하지 않으므로 초기 버전 핵심 컬럼에서 제외합니다.
- 결과물은 "국민연금 전체 보유 주식"이 아니라 "공시로 확인 가능한 5% 이상 보유 종목"입니다.
- 기본 조회 기준은 `effective_date`이며, `disclosure_date`는 비교 조회용으로 함께 제공합니다.
