# API 명세 — 데이터기반행정 활성화 제고 노력_정성보고서

> 최종 수정: 2026-03-19

## 개요

| 항목 | 값 |
|---|---|
| Base URL | n8n Webhook URL (배포 환경에 따라 상이) |
| 인증 방식 | 없음 (내부 도구) |
| 응답 형식 | JSON |
| 인코딩 | UTF-8 |

> 이 서비스는 n8n Form Trigger를 사용하는 내부 도구입니다.
> REST API 형태로 호출되며, n8n 워크플로우가 Claude API를 통해 분석 후 동기 응답을 반환합니다.

---

## 엔드포인트 목록

| 메서드 | 경로 | 설명 |
|---|---|---|
| POST | /webhook/{form-id} | 기관명 + 증빙파일 제출 → 실적 분류 + 첨부7 초안 반환 |

---

## 상세 명세

### POST /webhook/{form-id}

**설명**: 기관명과 증빙파일들을 업로드하면, AI가 파일을 분석하여 실적을 분류하고 첨부7 양식 초안을 반환한다.

**Request Headers**

| 헤더 | 필수 | 값 |
|---|---|---|
| Content-Type | Y | `multipart/form-data` |

**Request Body (multipart/form-data)**

| 파라미터 | 타입 | 필수 | 설명 |
|---|---|---|---|
| agency_name | String | Y | 기관명 |
| files[] | File[] | Y | 증빙파일 목록 (복수 업로드 가능, PDF / DOCX / JPG / PNG) |

**제약 조건**
- 파일당 최대 20MB
- 파일 수 권장: 5건 이내 (초과 시 처리 시간 증가)
- 지원 형식: PDF, DOCX, JPG, PNG

**Response 200 — 성공**

```json
{
  "agency_name": "○○기관",
  "submitted_at": "2026-03-19T10:00:00+09:00",
  "total_files": 3,
  "achievements": [
    {
      "achievement_id": "ach-001",
      "title": "데이터기반행정 카드뉴스 제작 및 배포",
      "related_files": ["카드뉴스_계획서.pdf", "카드뉴스_결과물.pdf"],
      "report_draft": {
        "목적_및_필요성": "데이터기반행정 인식 제고를 위해...",
        "추진_내용": "2026년 1분기 카드뉴스 3종 제작하여...",
        "기대_효과": "직원 인식 제고 및 데이터 활용 문화 확산..."
      }
    },
    {
      "achievement_id": "ach-002",
      "title": "데이터 활용 우수사례 공유 세미나 개최",
      "related_files": ["세미나_공문.pdf"],
      "report_draft": {
        "목적_및_필요성": "내부 데이터 활용 역량 강화를 위해...",
        "추진_내용": "분기별 사내 세미나 1회 개최...",
        "기대_효과": "부서 간 데이터 활용 사례 공유 및..."
      }
    }
  ]
}
```

**Response 400 — 파일 형식 오류**

```json
{
  "error": "invalid_file_type",
  "message": "지원하지 않는 파일 형식입니다. PDF, DOCX, JPG, PNG만 허용됩니다.",
  "unsupported_files": ["증빙자료.hwp"]
}
```

**Response 400 — 파일 크기 초과**

```json
{
  "error": "file_too_large",
  "message": "파일 크기가 제한을 초과했습니다. 파일당 최대 20MB까지 허용됩니다.",
  "oversized_files": ["대용량파일.pdf"]
}
```

**Response 200 — 실적 추출 불가 (정상 응답이나 내용 없음)**

```json
{
  "agency_name": "○○기관",
  "submitted_at": "2026-03-19T10:00:00+09:00",
  "total_files": 2,
  "achievements": [],
  "warning": "no_achievement_found",
  "warning_message": "업로드된 파일에서 실적을 추출하지 못했습니다. 파일 내용을 확인해주세요."
}
```

**Response 500 — Claude API 오류**

```json
{
  "error": "ai_analysis_failed",
  "message": "AI 분석 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
}
```

**Response 500 — 서버 내부 오류**

```json
{
  "error": "internal_error",
  "message": "서버 내부 오류가 발생했습니다."
}
```

---

## 에러 코드 정의

| 코드 | HTTP 상태 | 설명 |
|---|---|---|
| invalid_file_type | 400 | 지원하지 않는 파일 형식 (PDF, DOCX, JPG, PNG만 허용) |
| file_too_large | 400 | 파일 크기 초과 (파일당 20MB 제한) |
| no_achievement_found | 200 | AI가 파일에서 실적을 추출하지 못함 (warning으로 반환) |
| ai_analysis_failed | 500 | Claude API 호출 실패 (재시도 1회 후 반환) |
| internal_error | 500 | 서버 내부 오류 |
