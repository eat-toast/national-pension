# 국민연금 국내주식 대시보드

국민연금 국내주식 보유 변동 대시보드를 정적 HTML로 공개하는 프로젝트입니다.

배포 방식은 단순합니다.

1. 로컬에서 HTML을 만듭니다.
2. 생성된 `output_html/` 파일을 GitHub에 커밋하고 푸시합니다.
3. GitHub Actions가 `output_html/` 파일만 GitHub Pages에 올립니다.

GitHub Actions 안에서 DART 수집이나 HTML 재생성은 하지 않습니다.

## 공개되는 파일

현재 Pages 배포 대상은 `output_html/` 폴더입니다.

- `nps_combined_*.html`: 통합 대시보드
- `nps_dashboard_*.html`: 포트폴리오 대시보드
- `nps_sector_trends_*.html`: 섹터 변화 대시보드
- `*.csv`: 다운로드용 CSV

GitHub Pages 첫 화면에는 `index.html`이 필요합니다. 워크플로가 `output_html/nps_combined_*.html` 중 하나를 `index.html`로 복사해서 배포합니다.

## 처음 준비할 것

1. GitHub 저장소의 `Settings > Pages`에서 Source를 `GitHub Actions`로 설정합니다.
2. 로컬에서 만든 HTML 파일들이 `output_html/`에 있는지 확인합니다.
3. 변경된 HTML 파일을 커밋하고 푸시합니다.
4. 푸시 후 GitHub Actions 배포가 자동으로 실행되는지 확인합니다.

`DART_API_KEY` 같은 GitHub Secret은 이 방식에서는 필요 없습니다.

## 터미널에서 업데이트하는 방법

새 데이터를 반영할 때는 내 맥 터미널에서 수집, 섹터 갱신, HTML 생성을 끝낸 뒤 `output_html/`을 커밋하고 푸시합니다.

아래 예시는 2026년 4월 24일까지 반영하는 경우입니다. 다음에 갱신할 때는 `2026-04-24`만 새 기준일로 바꾸면 됩니다.

### 0. 프로젝트 폴더로 이동

터미널을 열고 항상 이 폴더에서 실행합니다.

```bash
cd "/Users/isaac/Documents/national pension"
```

현재 위치가 맞는지 확인합니다.

```bash
pwd
```

정상이라면 아래처럼 나와야 합니다.

```text
/Users/isaac/Documents/national pension
```

### 1. 데이터 수집

DART API는 `corp_code` 없이 전체 공시를 찾을 때 한 번에 3개월까지만 조회할 수 있습니다. 2026년 1월 1일부터 2026년 4월 24일까지 수집하려면 월별로 나눠 실행하는 것이 가장 안전합니다.

```bash
python3 -m src.cli.main sync-reports --from 2026-01-01 --to 2026-01-31
python3 -m src.cli.main sync-reports --from 2026-02-01 --to 2026-02-28
python3 -m src.cli.main sync-reports --from 2026-03-01 --to 2026-03-31
python3 -m src.cli.main sync-reports --from 2026-04-01 --to 2026-04-24
```

다음에 2026년 5월 31일까지 갱신한다면 마지막 줄을 이런 식으로 추가하면 됩니다.

```bash
python3 -m src.cli.main sync-reports --from 2026-05-01 --to 2026-05-31
```

수집된 데이터는 로컬 DB인 `data/nps_portfolio.sqlite3`에 저장됩니다. 이 DB 파일은 GitHub에 올리지 않습니다.

### 2. 섹터 갱신

새 종목이 생겼거나 섹터가 비어 있을 수 있으니 HTML 생성 전에 한 번 실행합니다.

```bash
python3 -m src.cli.main sync-sector-map --progress
```

### 3. HTML 생성

통합 대시보드와 CSV를 `output_html/`에 다시 만듭니다. 이 명령을 실행하면 포트폴리오, 섹터 변화, 전략 탭이 들어간 통합 HTML이 생성됩니다.

```bash
python3 -m src.cli.main export-combined-dashboard \
  --date 2026-04-24 \
  --from 2025-01-01 \
  --to 2026-04-24 \
  --basis disclosure_date \
  --output output_html/nps_combined_2026-04-24_disclosure_date.html \
  --csv-output output_html/nps_combined_2026-04-24_disclosure_date_sector_trends.csv
```

다음에 기준일을 바꾸면 `--date`, `--to`, 파일명 날짜를 모두 같은 날짜로 맞춥니다. 예를 들어 2026년 5월 31일까지 반영한다면 이렇게 바꿉니다.

```bash
python3 -m src.cli.main export-combined-dashboard \
  --date 2026-05-31 \
  --from 2025-01-01 \
  --to 2026-05-31 \
  --basis disclosure_date \
  --output output_html/nps_combined_2026-05-31_disclosure_date.html \
  --csv-output output_html/nps_combined_2026-05-31_disclosure_date_sector_trends.csv
```

필요하면 단독 HTML도 다시 만들 수 있습니다. 보통은 통합 HTML만 만들면 충분합니다.

```bash
python3 -m src.cli.main export-dashboard \
  --date 2026-04-24 \
  --basis disclosure_date \
  --output output_html/nps_dashboard_2026-04-24_disclosure_date.html

python3 -m src.cli.main export-sector-trends \
  --from 2025-01-01 \
  --to 2026-04-24 \
  --basis disclosure_date \
  --output output_html/nps_sector_trends_2025-01-01_2026-04-24_disclosure_date.html \
  --csv-output output_html/nps_sector_trends_2025-01-01_2026-04-24_disclosure_date.csv
```

### 4. 로컬에서 HTML 확인

전략 탭이 들어갔는지 터미널에서 먼저 확인합니다.

```bash
grep -n "strategyFrame\\|전략\\|국민연금 10% 이상 보유주 매수 전략" \
  output_html/nps_combined_2026-04-24_disclosure_date.html
```

브라우저에서 직접 열어보고 싶으면 Finder에서 `output_html/nps_combined_2026-04-24_disclosure_date.html` 파일을 더블클릭합니다.

### 5. GitHub에 올리기

변경 파일을 확인합니다.

```bash
git status
```

대시보드 HTML과 CSV만 올릴 때는 보통 이렇게 추가합니다.

```bash
git add output_html
git commit -m "Update dashboard HTML through 2026-04-24"
git push
```

전략 문서나 코드도 같이 바꿨다면 해당 파일도 같이 추가합니다.

```bash
git add output_html docs src tests .github/workflows
git commit -m "Update dashboard and strategy tab"
git push
```

### 6. GitHub Actions 배포 확인

`main`에 푸시하면 `.github/workflows/pages.yml`이 자동으로 실행됩니다. GitHub에서 아래 순서로 확인합니다.

1. GitHub 저장소로 이동합니다.
2. `Actions` 탭을 누릅니다.
3. `Deploy output_html to GitHub Pages` 실행이 초록색 체크로 끝났는지 봅니다.
4. Pages 주소를 새로고침합니다.

배포 직후 예전 화면이 보이면 브라우저 캐시일 수 있습니다. 강력 새로고침을 하거나 주소 끝에 `?v=20260424`처럼 임시 쿼리를 붙여 확인합니다.

수동으로 다시 배포하고 싶을 때는 GitHub에서 `Actions > Deploy output_html to GitHub Pages > Run workflow`를 눌러도 됩니다.

## 자주 하는 실수

- `sync-reports`만 실행하고 `export-combined-dashboard`를 안 하면 HTML은 갱신되지 않습니다.
- `output_html/`을 커밋하지 않으면 GitHub Pages에는 예전 HTML이 올라갑니다.
- `site/`는 GitHub Actions가 배포 직전에 새로 만드는 폴더입니다. 로컬 `site/`를 고쳐도 배포에는 직접 쓰이지 않습니다.
- 날짜를 바꿀 때 `--date`, `--to`, `--output` 파일명, `--csv-output` 파일명을 같은 기준일로 맞춥니다.
- 전략 탭 내용은 HTML 생성 시 자동 포함됩니다. 전략 문구 자체를 바꾸려면 `src/export/strategy_html_writer.py` 또는 `docs/nps_10pct_strategy.md`를 수정한 뒤 다시 HTML을 생성합니다.

## 주의할 점

- `.env`, API 키, 개인 토큰은 커밋하지 않습니다.
- `data/nps_portfolio.sqlite3`는 커밋하지 않습니다.
- 공개되는 HTML과 CSV 안에 민감한 정보가 없는지 확인합니다.
