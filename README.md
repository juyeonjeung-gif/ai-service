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

`docs/erd/` 또는 `docs/api/` 폴더의 파일이 수정되면
→ GitHub Actions가 자동 감지
→ 노션의 해당 설계 페이지에 변경 내용 자동 기록

## 📌 문서 링크

- 노션 기획DB: (링크 추가)
- 노션 설계DB: (링크 추가)# ai-service
