# 『다가설 때와 멈출 때』 판매현황

교보문고 자기계발 순위, 교보문고 종합 순위, YES24 판매지수를 보여주는 비공식 대시보드.

- `index.html`: 전체 화면
- `widget.html`: 간편 위젯
- `data.json`: 마지막 확인 수치와 과거 기록. **최초값은 2026-10-22 기준값이며 실시간값이 아님.**
- `update_data.py`: 공개 웹페이지에서 수치를 추출하려고 시도. 접근 차단 또는 추출 실패 시 **이전값을 그대로 유지하며 오류를 기록**.
- `.github/workflows/update.yml`: GitHub Actions가 매 시간 수집 시도 (정시 실행 보장되지 않음).

## 공개하기

1. ZIP 압축 해제 후 `index.html`, `widget.html`, `data.json`, `update_data.py`, `manifest.webmanifest`, `icon.svg`, `.github/workflows/update.yml`을 **디렉터리 구조 그대로** 저장소의 기본 브랜치에 업로드.
2. 저장소 Settings → Pages → Build and deployment → Source `Deploy from a branch`, Branch `main`, Folder `/ (root)` → Save.
3. 공개 주소는 `https://goodmanoys.github.io/book-sales-dashboard/`.
4. 저장소 Actions 탭에서 `Refresh book sales metrics` → `Run workflow`를 눌러 첫 실행. Actions가 차단되거나 쓰기 권한이 제한된 경우 저장소 Settings → Actions에서 해당 권한을 확인.

## 한계

- 교보문고 페이지는 동적 렌더링·접근 제한 등으로 순위 추출에 실패할 수 있음. 자동 수집이 성공했다고 확인되기 전에는 초기 순위를 실시간 수치로 해석하면 안 됨.
- YES24 판매지수 또한 페이지 구조 변경이나 봇 차단으로 수집 실패할 수 있음.
- 에러가 발생해도 대시보드는 **마지막 확인값과 확인 시점**을 표시하고 가짜 갱신값을 만들지 않음.
- 수동 입력 기능은 현재 브라우저의 표시만 변경하고 GitHub의 `data.json`은 수정하지 않음.
