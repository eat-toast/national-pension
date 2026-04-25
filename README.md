# 국민연금 국내주식 대시보드

국민연금 국내주식 보유 변동 대시보드를 정적 HTML로 공개하는 프로젝트입니다.

배포 방식은 단순합니다.

1. 로컬에서 HTML을 만듭니다.
2. 생성된 `output_html/` 파일을 GitHub에 커밋하고 푸시합니다.
3. GitHub Actions의 `Run workflow`를 누르면 `output_html/` 파일만 GitHub Pages에 올라갑니다.

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
4. GitHub의 `Actions > Deploy output_html to GitHub Pages > Run workflow`를 실행합니다.

`DART_API_KEY` 같은 GitHub Secret은 이 방식에서는 필요 없습니다.

## 업데이트 방법

새 데이터를 반영할 때는 로컬에서 수집, 섹터 갱신, HTML 생성을 끝낸 뒤 `output_html/`만 커밋하고 배포합니다.

### 1. 데이터 수집

DART API는 `corp_code` 없이 전체 공시를 찾을 때 한 번에 3개월까지만 조회할 수 있습니다. 2026년 1월 1일부터 2026년 4월 24일까지 수집하려면 월별로 나눠 실행하는 것이 가장 안전합니다.

```bash
cd "/Users/isaac/Documents/national pension"

python3 -m src.cli.main sync-reports --from 2026-01-01 --to 2026-01-31
python3 -m src.cli.main sync-reports --from 2026-02-01 --to 2026-02-28
python3 -m src.cli.main sync-reports --from 2026-03-01 --to 2026-03-31
python3 -m src.cli.main sync-reports --from 2026-04-01 --to 2026-04-24
```

수집된 데이터는 로컬 DB인 `data/nps_portfolio.sqlite3`에 저장됩니다. 이 DB 파일은 GitHub에 올리지 않습니다.

### 2. 섹터 갱신

```bash
python3 -m src.cli.main sync-sector-map --progress
```

### 3. HTML 생성

통합 대시보드와 CSV를 `output_html/`에 다시 만듭니다. 날짜는 새로 반영하고 싶은 기준에 맞게 바꾸면 됩니다.

```bash
python3 -m src.cli.main export-combined-dashboard \
  --date 2026-04-24 \
  --from 2025-01-01 \
  --to 2026-04-24 \
  --basis disclosure_date \
  --output output_html/nps_combined_2026-04-24_disclosure_date.html \
  --csv-output output_html/nps_combined_2026-04-24_disclosure_date_sector_trends.csv
```

필요하면 단독 HTML도 다시 만들 수 있습니다.

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

### 4. GitHub에 올리기

```bash
git status
git add output_html
git commit -m "Update dashboard HTML through 2026-04-24"
git push
```

그 다음 GitHub에서 `Actions > Deploy output_html to GitHub Pages > Run workflow`를 누르면 방금 푸시한 HTML이 다시 배포됩니다.

## 주의할 점

- `.env`, API 키, 개인 토큰은 커밋하지 않습니다.
- `data/nps_portfolio.sqlite3`는 커밋하지 않습니다.
- 공개되는 HTML과 CSV 안에 민감한 정보가 없는지 확인합니다.
