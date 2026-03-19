#!/usr/bin/env python3
"""
init_build_status.py
====================
복사 위치: {project_br}/.github/scripts/init_build_status.py

설계 문서(ERD / API 명세)가 feature/** 브랜치에 push될 때 실행된다.
노션 구축현황 DB에 해당 서비스 페이지가 없으면 신규 생성한다.
이미 존재하면 스킵 (idempotent).

서비스명 결정 순서:
  1. {slug}/docs/.design-meta.json 의 "service_name" 필드
  2. 없으면 slug 값 그대로 사용

환경 변수 (GitHub Actions에서 주입):
  NOTION_API_KEY, GH_BRANCH, GH_BRANCH_URL
"""

import os
import re
import sys
import json
import requests
from pathlib import Path
from datetime import datetime

# ─────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────

NOTION_API_KEY     = os.environ.get("NOTION_API_KEY", "")
NOTION_VERSION     = "2022-06-28"
NOTION_BUILD_DB_ID = "56659de7-3a4e-40ab-8858-a2a46953488a"

HEADERS = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Notion-Version": NOTION_VERSION,
    "Content-Type": "application/json",
}


# ─────────────────────────────────────────────
# 헬퍼
# ─────────────────────────────────────────────

def get_slug_from_branch(branch: str) -> str | None:
    """'feature/{slug}' 형식의 브랜치명에서 slug를 추출한다."""
    m = re.match(r"feature/(.+)", branch)
    return m.group(1) if m else None


def get_service_name(slug: str) -> str:
    """
    {slug}/docs/.design-meta.json 에서 서비스명을 읽는다.
    파일이 없거나 파싱 실패 시 slug를 그대로 반환한다.
    """
    meta_path = Path(f"{slug}/docs/.design-meta.json")
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            name = meta.get("service_name", "").strip()
            if name:
                return name
        except Exception as e:
            print(f"[WARN] .design-meta.json 파싱 실패: {e}")
    return slug


def get_build_type(slug: str) -> str:
    """
    {slug}/docs/.design-meta.json 에서 build_type을 읽어 노션 선택값으로 변환한다.
    파일이 없거나 파싱 실패 시 "코드"를 반환한다.
    """
    meta_path = Path(f"{slug}/docs/.design-meta.json")
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            bt = meta.get("build_type", "").strip().lower()
            return {"n8n": "n8n", "code": "코드", "mixed": "혼합"}.get(bt, "코드")
        except Exception as e:
            print(f"[WARN] .design-meta.json 파싱 실패: {e}")
    return "코드"


def find_service_page(service_name: str) -> str | None:
    """구축현황 DB에서 서비스명이 일치하는 페이지 ID를 반환한다."""
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


def create_service_page(service_name: str, branch_url: str, build_type: str = "코드") -> str:
    """구축현황 DB에 새 서비스 페이지를 생성한다."""
    today = datetime.now().strftime("%Y-%m-%d")

    properties: dict = {
        "서비스명": {
            "title": [{"type": "text", "text": {"content": service_name}}]
        },
        "구축 방식": {"select": {"name": build_type}},
        "상태":     {"select": {"name": "구축 중"}},
        "시작일":   {"date": {"start": today}},
    }

    if branch_url:
        properties["GitHub 브랜치"] = {"url": branch_url}

    resp = requests.post(
        "https://api.notion.com/v1/pages",
        headers=HEADERS,
        json={
            "parent": {"database_id": NOTION_BUILD_DB_ID},
            "properties": properties,
        },
    )
    resp.raise_for_status()
    return resp.json()["id"]


# ─────────────────────────────────────────────
# main
# ─────────────────────────────────────────────

def main() -> None:
    if not NOTION_API_KEY:
        print("[ERROR] 환경 변수 NOTION_API_KEY가 설정되지 않았습니다.")
        sys.exit(1)

    branch     = os.environ.get("GH_BRANCH", "")
    branch_url = os.environ.get("GH_BRANCH_URL", "")

    # slug 추출
    slug = get_slug_from_branch(branch)
    if not slug:
        print(f"[SKIP] feature/** 브랜치가 아님: {branch}")
        sys.exit(0)

    # 서비스명 및 구축 방식 결정
    service_name = get_service_name(slug)
    build_type   = get_build_type(slug)
    print(f"[INFO] slug={slug} | service_name={service_name} | build_type={build_type}")

    # 이미 페이지가 있으면 스킵
    page_id = find_service_page(service_name)
    if page_id:
        print(f"[SKIP] 구축현황 페이지 이미 존재: {page_id}")
        sys.exit(0)

    # 신규 생성
    page_id = create_service_page(service_name, branch_url, build_type)
    print(f"[DONE] 구축현황 페이지 생성 완료: {page_id}")
    print(f"       서비스명: {service_name}")
    print(f"       GitHub 브랜치: {branch_url}")


if __name__ == "__main__":
    main()
