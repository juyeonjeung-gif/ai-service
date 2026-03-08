# 05. AI 서비스

## 📁 폴더 구조

```
ai-service/
├── docs/                        ← 설계 문서 (이 폴더가 수정되면 노션 자동 업데이트)
│   ├── erd/
│   │   └── erd.md               ← ERD (데이터 구조 설계서)
│   └── api/
│       ├── openapi.yaml         ← API 명세 원본
│       └── CHANGELOG.md         ← API 변경 이력 (비개발 인력용)
├── src/                         ← 실제 코드 (개발팀 작업 공간)
└── .github/
    └── workflows/
        └── sync-to-notion.yml   ← 자동화 설정 
```

## 🔄 자동화 동작 방식

`docs/erd/` 또는 `docs/api/` 폴더의 파일이 수정되면
→ GitHub Actions가 자동 감지
→ 노션의 해당 설계 페이지에 변경 내용 자동 기록

## 📌 문서 링크

- 노션 기획DB: (링크 추가)
- 노션 설계DB: (링크 추가)# ai-service
