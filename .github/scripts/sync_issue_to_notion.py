#!/usr/bin/env python3
"""
sync_issue_to_notion.py
========================
복사 위치: {project_br}/.github/scripts/sync_issue_to_notion.py

GitHub Issues 이벤트 발생 시 노션 구축현황 DB에 기록한다.
- 서비스별 1페이지 누적 방식
- 기존 페이지(같은 서비스명)가 있으면 이슈 블록 추가, 없으면 신규 생성

라벨 규칙:
  - 'service:{slug}'  → 서비스명 (없으면 레포명 사용)
  - 'type:{이슈유형}' → 이슈 유형 (블록 내 표시)
  - 그 외 라벨       → 이슈 유형 폴백

환경 변수 (GitHub Actions에서 주입):
  NOTION_API_KEY, NOTION_BUILD_DB_ID
  GH_ISSUE_NUMBER, GH_ISSUE_TITLE, GH_ISSUE_URL
  GH_ISSUE_STATE, GH_ISSUE_LABELS (JSON array)
  GH_ISSUE_CREATED_AT, GH_ISSUE_UPDATED_AT, GH_ISSUE_CLOSED_AT
  GH_REPO_NAME, GH_EVENT_ACTION
"""

import os
import json
import sys
import requests
from datetime import datetime

# ─────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────

NOTION_API_KEY    = os.environ.get("NOTION_API_KEY", "")
NOTION_VERSION    = "2022-06-28"
NOTION_BUILD_DB_ID = os.environ.get(
    "NOTION_BUILD_DB_ID", "56659de7-3a4e-40ab-8858-a2a46953488a"
)

HEADERS = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Notion-Version": NOTION_VERSION,
    "Content-Type": "application/json",
}

# 이슈 상태 → 아이콘 / 컬러
STATE_ICON = {
    "open":   "🔵",
    "closed": "✅",
}
STATE_COLOR = {
    "open":   "blue_background",
    "closed": "green_background",
}

# 이벤트 액션 → 한국어 텍스트
ACTION_TEXT = {
    "opened":    "이슈 오픈",
    "closed":    "이슈 클로즈",
    "reopened":  "이슈 재오픈",
    "edited":    "이슈 수정",
    "labeled":   "라벨 추가",
    "unlabeled": "라벨 제거",
    "assigned":  "담당자 지정",
    "unassigned": "담당자 해제",
}


# ─────────────────────────────────────────────
# 파싱 헬퍼
# ─────────────────────────────────────────────

def parse_labels(labels_json: str) -> tuple[str | None, str | None]:
    """
    GitHub 라벨 JSON에서 서비스명과 이슈 유형을 추출한다.

    Returns:
        (service_name, issue_type)  — 각각 없으면 None
    """
    try:
        labels = json.loads(labels_json)
    except (json.JSONDecodeError, TypeError):
        labels = []

    service_name = None
    issue_type   = None
    other_labels = []

    for label in labels:
        name = label.get("name", "")
        if name.startswith("service:"):
            service_name = name.replace("service:", "").strip()
        elif name.startswith("type:"):
            issue_type = name.replace("type:", "").strip()
        else:
            other_labels.append(name)

    # type: 라벨 없으면 첫 번째 일반 라벨을 이슈 유형으로 사용
    if not issue_type and other_labels:
        issue_type = other_labels[0]

    return service_name, issue_type


def format_date(date_str: str) -> str:
    """ISO 날짜 문자열을 YYYY-MM-DD 형식으로 변환한다."""
    if not date_str:
        return ""
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except (ValueError, AttributeError):
        return ""


# ─────────────────────────────────────────────
# Notion API 헬퍼
# ─────────────────────────────────────────────

def find_service_page(service_name: str) -> str | None:
    """
    구축현황 DB에서 같은 서비스명을 가진 페이지를 조회한다.
    Returns: page_id 또는 None
    """
    resp = requests.post(
        f"https://api.notion.com/v1/databases/{NOTION_BUILD_DB_ID}/query",
        headers=HEADERS,
        json={
            "filter": {
                "property": "서비스명",
                "title": {"equals": service_name},
            }
        },
    )
    resp.raise_for_status()
    results = resp.json().get("results", [])
    return results[0]["id"] if results else None


def create_service_page(service_name: str) -> str:
    """구축현황 DB에 새 서비스 페이지를 생성한다."""
    today = datetime.now().strftime("%Y-%m-%d")
    resp = requests.post(
        "https://api.notion.com/v1/pages",
        headers=HEADERS,
        json={
            "parent": {"database_id": NOTION_BUILD_DB_ID},
            "properties": {
                "서비스명": {
                    "title": [{"type": "text", "text": {"content": service_name}}]
                },
                "구축 방식": {"select": {"name": "코드"}},
                "상태":     {"select": {"name": "구축 중"}},
                "시작일":   {"date": {"start": today}},
            },
        },
    )
    resp.raise_for_status()
    return resp.json()["id"]


def append_issue_block(
    page_id:      str,
    issue_number: int,
    issue_title:  str,
    issue_url:    str,
    issue_state:  str,
    issue_type:   str | None,
    event_action: str,
    date_str:     str,
) -> None:
    """서비스 페이지에 이슈 이벤트 callout 블록을 추가한다."""
    icon       = STATE_ICON.get(issue_state, "🔵")
    color      = STATE_COLOR.get(issue_state, "gray_background")
    type_text  = f" [{issue_type}]" if issue_type else ""
    date_text  = f" · {date_str}" if date_str else ""
    action_str = ACTION_TEXT.get(event_action, event_action)

    summary = (
        f"{icon} #{issue_number}{type_text} "
        f"{issue_title} — {action_str}{date_text}"
    )

    children = [
        {
            "object": "block",
            "type": "callout",
            "callout": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {"content": summary + "\n"},
                    },
                    {
                        "type": "text",
                        "text": {
                            "content": issue_url,
                            "link": {"url": issue_url},
                        },
                    },
                ],
                "icon":  {"type": "emoji", "emoji": icon},
                "color": color,
            },
        }
    ]

    resp = requests.patch(
        f"https://api.notion.com/v1/blocks/{page_id}/children",
        headers=HEADERS,
        json={"children": children},
    )
    resp.raise_for_status()


# ─────────────────────────────────────────────
# main
# ─────────────────────────────────────────────

def main() -> None:
    if not NOTION_API_KEY:
        print("[ERROR] 환경 변수 NOTION_API_KEY가 설정되지 않았습니다.")
        sys.exit(1)

    # 환경 변수 읽기
    issue_number  = int(os.environ.get("GH_ISSUE_NUMBER", 0))
    issue_title   = os.environ.get("GH_ISSUE_TITLE", "")
    issue_url     = os.environ.get("GH_ISSUE_URL", "")
    issue_state   = os.environ.get("GH_ISSUE_STATE", "open")
    issue_labels  = os.environ.get("GH_ISSUE_LABELS", "[]")
    created_at    = os.environ.get("GH_ISSUE_CREATED_AT", "")
    updated_at    = os.environ.get("GH_ISSUE_UPDATED_AT", "")
    closed_at     = os.environ.get("GH_ISSUE_CLOSED_AT", "")
    repo_name     = os.environ.get("GH_REPO_NAME", "ai-service")
    event_action  = os.environ.get("GH_EVENT_ACTION", "")

    print(f"[INFO] 이슈 #{issue_number} | action={event_action} | state={issue_state}")

    # 서비스명 & 이슈 유형 추출
    service_name, issue_type = parse_labels(issue_labels)
    if not service_name:
        service_name = repo_name  # 라벨 없으면 레포명 사용
    print(f"[INFO] 서비스명={service_name} | 이슈유형={issue_type}")

    # 날짜: closed_at > updated_at > created_at 순
    date_str = (
        format_date(closed_at)
        or format_date(updated_at)
        or format_date(created_at)
    )

    # 서비스 페이지 조회 또는 생성
    page_id = find_service_page(service_name)
    if page_id:
        print(f"[FOUND] 기존 서비스 페이지: {page_id}")
    else:
        print("[CREATE] 신규 서비스 페이지 생성")
        page_id = create_service_page(service_name)
        print(f"[CREATED] {page_id}")

    # 이슈 블록 추가
    append_issue_block(
        page_id=page_id,
        issue_number=issue_number,
        issue_title=issue_title,
        issue_url=issue_url,
        issue_state=issue_state,
        issue_type=issue_type,
        event_action=event_action,
        date_str=date_str,
    )

    print(f"[DONE] 이슈 #{issue_number} 블록 추가 완료")


if __name__ == "__main__":
    main()
