# 05. AI 서비스

## 📁 폴더 구조

```
ai-service/
├── docs/
│   ├── erd/
│   │   └── erd.md
│   └── api/
│       ├── openapi.yaml
│       └── CHANGELOG.md
├── src/                        ← 개발팀이 채워나갈 코드
├── .github/
│   └── workflows/
│       ├── sync-to-notion.yml  ← 문서 변경 동기화 (이미 완성)
│       ├── sync-issues.yml     ← Issue 동기화 (신규)
│       ├── sync-release.yml    ← 배포 이력 동기화 (신규)
│       └── test-notify.yml     ← 테스트 결과 알림 (신규)
└── README.md
```

## 🔄 자동화 동작 방식

| 깃허브 이벤트 | 자동으로 일어나는 일 | 노션에서 확인 위치 |
|---|---|---|
| `docs/erd/` 파일 수정 | ERD 변경 내용 기록 | 설계DB → 2-3.ERD |
| `docs/api/` 파일 수정 | API 명세 변경 내용 기록 | 설계DB → 2-4.API명세 |
| Issue 생성 | 작업현황DB에 행 자동 추가 | 작업현황DB / 대시보드 |
| Issue 완료 | 작업현황DB 상태 → ✅ 완료 | 작업현황DB / 대시보드 |
| Release 배포 | 배포이력DB에 버전 자동 기록 | 배포이력DB / 대시보드 |
| main 브랜치 push | 테스트 실행 → 결과 기록 | 작업현황DB |

## 📌 깃허브 시크릿 목록

> Settings → Secrets and variables → Actions 에서 관리

| 시크릿 이름 | 설명 |
|---|---|
| `NOTION_API_KEY` | 노션 통합 API 키 |
| `NOTION_ERD_PAGE_ID` | 설계DB → 2-3.ERD 페이지 ID |
| `NOTION_API_PAGE_ID` | 설계DB → 2-4.API명세 페이지 ID |
| `NOTION_TASK_DB_ID` | 작업현황DB ID |
| `NOTION_DEPLOY_DB_ID` | 배포이력DB ID |
| `NOTION_DASHBOARD_CALLOUT_ID` | 대시보드 상태 콜아웃 블록 ID |

## 🔗 노션 링크

- [05.AI서비스 노션 페이지] https://www.notion.so/05-AI-318b6131fa2f80438b98eabfc339bdec?source=copy_link

## ✏️ 문서 수정 방법

**ERD 변경이 필요할 때**
1. `docs/erd/erd.md` 파일 수정
2. 하단 변경이력 테이블에 날짜/내용 추가
3. Commit → 노션 자동 반영 (약 30초 소요)

**API 명세 변경이 필요할 때**
1. `docs/api/openapi.yaml` 수정
2. `docs/api/CHANGELOG.md` 상단에 변경 내용 추가
3. Commit → 노션 자동 반영 (약 30초 소요)
