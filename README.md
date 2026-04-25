# 국민연금 국내주식 대시보드

국민연금 국내주식 보유 변동 공시를 수집해 정적 HTML 대시보드로 배포하는 프로젝트입니다. 배포 대상은 GitHub Pages이며, 업데이트는 GitHub Actions를 수동 실행할 때만 이뤄집니다.

## 공개 사이트 구성

- `index.html`: 포트폴리오와 섹터 변화를 탭으로 묶은 통합 대시보드
- `dashboard.html`: 포트폴리오 대시보드 단독 화면
- `sector-trends.html`: 섹터 변화 단독 화면
- `nps_sector_trends.csv`: 섹터 변화 원본 CSV

GitHub Actions가 위 파일들을 `site/` 폴더에 만든 뒤 Pages 아티팩트로 배포합니다. `site/` 폴더는 생성물이라 저장소에 커밋하지 않아도 됩니다.

## 처음 준비할 것

1. GitHub 저장소의 `Settings > Pages`에서 Source를 `GitHub Actions`로 설정합니다.
2. `Settings > Secrets and variables > Actions`에 `DART_API_KEY` 저장소 시크릿을 추가합니다.
3. `Actions > Build and deploy GitHub Pages > Run workflow`를 실행합니다.
4. 실행이 끝나면 Actions 실행 화면 또는 `Settings > Pages`에서 공개 URL을 확인합니다.

## 비정기 업데이트 방법

새 공시를 반영하고 싶을 때만 `Run workflow`를 누르면 됩니다.

- `sync_from`: 다시 수집할 시작일
- `sync_to`: 다시 수집할 종료일
- `sync_sector_map`: 수집된 종목의 섹터 매핑도 갱신할지 여부
- `dashboard_date`: 포트폴리오 대시보드 기준일
- `trend_start`: 섹터 변화 시작일
- `trend_end`: 섹터 변화 종료일
- `basis`: 보통 `disclosure_date` 유지

스케줄 실행은 일부러 넣지 않았습니다. 원할 때만 수동으로 돌리는 구조입니다.

## 로컬에서 미리 확인

로컬 DB가 있을 때 아래 명령으로 Pages에 올라갈 HTML을 미리 만들 수 있습니다.

```bash
python3 scripts/build_site.py \
  --date 2025-12-31 \
  --from 2025-01-01 \
  --to 2026-04-20 \
  --basis disclosure_date \
  --site-dir site
```

생성된 `site/index.html`을 브라우저에서 열어 확인하면 됩니다.

## 주의할 점

- `data/nps_portfolio.sqlite3`는 커밋하지 않습니다. GitHub Actions 실행 때마다 DART에서 다시 수집해 HTML을 만듭니다.
- 공개 저장소에 `.env`, API 키, 개인 토큰을 올리지 않습니다.
- 기준 엑셀 파일과 생성된 HTML에는 공개해도 되는 데이터만 포함되어야 합니다.
