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

새 HTML을 만들었을 때 아래 순서만 반복하면 됩니다.

```bash
git status
git add output_html
git commit -m "Update dashboard HTML"
git push
```

그 다음 GitHub에서 `Run workflow`를 누르면 방금 푸시한 HTML이 다시 배포됩니다.

## 주의할 점

- `.env`, API 키, 개인 토큰은 커밋하지 않습니다.
- `data/nps_portfolio.sqlite3`는 커밋하지 않습니다.
- 공개되는 HTML과 CSV 안에 민감한 정보가 없는지 확인합니다.
