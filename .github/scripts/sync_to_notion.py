#!/usr/bin/env python3
"""
sync_to_notion.py
=================
복사 위치: {project_br}/.github/scripts/sync_to_notion.py

동작:
  - GitHub Actions에서 변경된 docs 파일 경로를 받아
  - 파일 경로에서 서비스 슬러그를 추출하고
  - 해당 슬러그의 .design-meta.json에서 Notion 페이지 ID를 읽은 뒤
  - 대응하는 Notion 설계 문서 섹션을 최신 내용으로 교체한다

파일 구조 가정:
  {slug}/docs/erd/erd.md         → Notion 섹션 "2-3. ERD"
  {slug}/docs/api/api-spec.md    → Notion 섹션 "2-4. API 명세"
  {slug}/docs/.design-meta.json  → { "notion_design_page_id": "..." }

환경 변수:
  NOTION_API_KEY  : Notion Integration 토큰 (GitHub Secret)
  CHANGED_FILES   : 공백 구분 변경 파일 경로 목록 (GitHub Actions 주입)
"""

import os
import re
import json
import sys
from pathlib import Path

import requests

# ─────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────

NOTION_API_KEY = os.environ.get("NOTION_API_KEY", "")
NOTION_VERSION = "2022-06-28"

HEADERS = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Notion-Version": NOTION_VERSION,
    "Content-Type": "application/json",
}

# docs 하위 경로 패턴 → 노션 섹션 제목
SECTION_PATTERNS = [
    (re.compile(r".*/docs/erd/.*\.md$"), "2-3. ERD"),
    (re.compile(r".*/docs/api/.*\.md$"), "2-4. API 명세"),
]

CHUNK_SIZE = 100  # Notion API 1회 append 최대 블록 수


# ─────────────────────────────────────────────
# 경로 유틸
# ─────────────────────────────────────────────

def get_section_title(file_path: str) -> str | None:
    """파일 경로 패턴으로 노션 섹션 제목을 반환한다."""
    for pattern, title in SECTION_PATTERNS:
        if pattern.match(file_path):
            return title
    return None


def find_meta_json(file_path: str) -> Path | None:
    """
    파일 경로에서 상위 docs/ 폴더를 찾아 .design-meta.json 경로를 반환한다.

    예:
      jeongsong-bogoseo/docs/erd/erd.md
      → jeongsong-bogoseo/docs/.design-meta.json
    """
    p = Path(file_path)
    for parent in p.parents:
        if parent.name == "docs":
            meta = parent / ".design-meta.json"
            return meta if meta.exists() else None
    return None


# ─────────────────────────────────────────────
# Notion API 헬퍼
# ─────────────────────────────────────────────

def get_block_children(block_id: str) -> list:
    """페이지/블록의 모든 자식 블록을 페이지네이션 없이 반환한다."""
    results = []
    cursor = None
    while True:
        params = {"page_size": 100}
        if cursor:
            params["start_cursor"] = cursor
        resp = requests.get(
            f"https://api.notion.com/v1/blocks/{block_id}/children",
            headers=HEADERS,
            params=params,
        )
        resp.raise_for_status()
        data = resp.json()
        results.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
    return results


def archive_block(block_id: str) -> None:
    """블록을 아카이브(삭제)한다."""
    requests.patch(
        f"https://api.notion.com/v1/blocks/{block_id}",
        headers=HEADERS,
        json={"archived": True},
    )


def append_blocks(page_id: str, children: list, after_id: str | None = None) -> dict:
    """page_id의 자식 블록 목록에 children을 추가한다.
    after_id가 주어지면 해당 블록 바로 뒤에 삽입한다.
    """
    payload: dict = {"children": children}
    if after_id:
        payload["after"] = after_id
    resp = requests.patch(
        f"https://api.notion.com/v1/blocks/{page_id}/children",
        headers=HEADERS,
        json=payload,
    )
    return resp.json()


def get_block_plain_text(block: dict) -> str:
    """블록의 rich_text에서 plain text를 추출한다."""
    block_type = block.get("type", "")
    content = block.get(block_type, {})
    return "".join(
        rt.get("plain_text", "") for rt in content.get("rich_text", [])
    )


# ─────────────────────────────────────────────
# 섹션 탐색
# ─────────────────────────────────────────────

def find_section_heading(blocks: list, section_title: str) -> str | None:
    """section_title이 포함된 heading 블록의 ID를 반환한다."""
    for block in blocks:
        btype = block.get("type", "")
        if btype in ("heading_2", "heading_3"):
            if section_title.lower() in get_block_plain_text(block).lower():
                return block["id"]
    return None


def get_section_content_ids(blocks: list, heading_id: str) -> list[str]:
    """heading 블록 다음부터 다음 같은 레벨 heading 전까지의 블록 ID 목록을 반환한다."""
    heading_level = None
    in_section = False
    ids = []

    for block in blocks:
        if block["id"] == heading_id:
            heading_level = block.get("type")
            in_section = True
            continue

        if in_section:
            btype = block.get("type", "")
            if btype in ("heading_2", "heading_3"):
                if heading_level == "heading_2":
                    break
                if heading_level == "heading_3" and btype in ("heading_2", "heading_3"):
                    break
            ids.append(block["id"])

    return ids


# ─────────────────────────────────────────────
# Markdown → Notion 블록 변환
# ─────────────────────────────────────────────

def rich_text(content: str) -> list:
    """단순 텍스트를 Notion rich_text 배열로 변환한다."""
    return [{"type": "text", "text": {"content": content}}]


def md_to_notion_blocks(content: str) -> list:
    """Markdown 텍스트를 Notion 블록 객체 리스트로 변환한다.

    지원 요소:
      ## heading_2  /  ### heading_3  /  #### heading_3
      ---  divider
      - bullet list  /  1. numbered list
      | table |
      ``` code block ```
      > blockquote → callout (이모지로 색상 결정)
      일반 텍스트 paragraph
    """
    blocks = []
    lines = content.splitlines()
    i = 0

    while i < len(lines):
        line = lines[i]

        # ── 코드 블록 ────────────────────────────
        if line.startswith("```"):
            lang = line[3:].strip() or "plain text"
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                code_lines.append(lines[i])
                i += 1
            blocks.append({
                "object": "block",
                "type": "code",
                "code": {
                    "rich_text": rich_text("\n".join(code_lines)),
                    "language": lang,
                },
            })
            i += 1
            continue

        # ── Divider ──────────────────────────────
        if line.strip() == "---":
            blocks.append({"object": "block", "type": "divider", "divider": {}})
            i += 1
            continue

        # ── Heading 2 ────────────────────────────
        if line.startswith("## "):
            blocks.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {"rich_text": rich_text(line[3:].strip())},
            })
            i += 1
            continue

        # ── Heading 3 (### 또는 ####) ────────────
        if line.startswith("### ") or line.startswith("#### "):
            text = re.sub(r"^#{3,4} ", "", line).strip()
            blocks.append({
                "object": "block",
                "type": "heading_3",
                "heading_3": {"rich_text": rich_text(text)},
            })
            i += 1
            continue

        # ── Bullet list ──────────────────────────
        if line.startswith("- "):
            blocks.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": rich_text(line[2:].strip())},
            })
            i += 1
            continue

        # ── Numbered list ────────────────────────
        if re.match(r"^\d+\. ", line):
            text = re.sub(r"^\d+\. ", "", line).strip()
            blocks.append({
                "object": "block",
                "type": "numbered_list_item",
                "numbered_list_item": {"rich_text": rich_text(text)},
            })
            i += 1
            continue

        # ── Table ────────────────────────────────
        if line.startswith("|") and "|" in line[1:]:
            table_rows = []
            while i < len(lines) and lines[i].startswith("|"):
                row = lines[i]
                # 구분선 행(---|---) 건너뜀
                if re.match(r"^\|[-|:\s]+\|$", row):
                    i += 1
                    continue
                cells = [c.strip() for c in row.split("|")[1:-1]]
                table_rows.append(cells)
                i += 1

            if table_rows:
                max_cols = max(len(r) for r in table_rows)
                padded = [r + [""] * (max_cols - len(r)) for r in table_rows]
                blocks.append({
                    "object": "block",
                    "type": "table",
                    "table": {
                        "table_width": max_cols,
                        "has_column_header": True,
                        "has_row_header": False,
                        "children": [
                            {
                                "object": "block",
                                "type": "table_row",
                                "table_row": {
                                    "cells": [
                                        [{"type": "text", "text": {"content": c}}]
                                        for c in row
                                    ]
                                },
                            }
                            for row in padded
                        ],
                    },
                })
            continue

        # ── Blockquote / Callout ─────────────────
        if line.startswith("> "):
            text = line[2:].strip()
            if text.startswith("⚠️"):
                color, icon = "yellow_background", "⚠️"
            elif text.startswith("✅"):
                color, icon = "green_background", "✅"
            elif text.startswith("ℹ️"):
                color, icon = "blue_background", "ℹ️"
            else:
                color, icon = "gray_background", "📌"
            blocks.append({
                "object": "block",
                "type": "callout",
                "callout": {
                    "rich_text": rich_text(text),
                    "icon": {"type": "emoji", "emoji": icon},
                    "color": color,
                },
            })
            i += 1
            continue

        # ── Paragraph (비어 있지 않은 줄) ─────────
        if line.strip():
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": rich_text(line)},
            })

        i += 1

    return blocks


# ─────────────────────────────────────────────
# 파일 동기화
# ─────────────────────────────────────────────

def sync_file(file_path: str) -> bool:
    """file_path의 내용을 해당 Notion 섹션에 반영한다."""

    # 섹션 제목 결정
    section_title = get_section_title(file_path)
    if not section_title:
        print(f"[SKIP] 매핑 없음: {file_path}")
        return True

    # 파일 존재 확인
    if not os.path.exists(file_path):
        print(f"[SKIP] 파일 없음 (삭제됨?): {file_path}")
        return True

    # .design-meta.json 탐색
    meta_path = find_meta_json(file_path)
    if not meta_path:
        print(f"[ERROR] .design-meta.json 을 찾을 수 없습니다: {file_path}")
        return False

    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)

    page_id = meta.get("notion_design_page_id")
    if not page_id:
        print(f"[ERROR] notion_design_page_id 없음: {meta_path}")
        return False

    print(f"[SYNC] {file_path}")
    print(f"  섹션: '{section_title}' | Notion 페이지: {page_id}")

    with open(file_path, encoding="utf-8") as f:
        content = f.read()

    # 페이지 블록 전체 조회
    blocks = get_block_children(page_id)

    # 섹션 heading 탐색
    heading_id = find_section_heading(blocks, section_title)

    if not heading_id:
        # 섹션이 없으면 페이지 맨 끝에 추가
        print(f"  [INFO] 섹션 '{section_title}' 없음 → 페이지 끝에 추가")
        new_blocks = md_to_notion_blocks(content)
        for j in range(0, len(new_blocks), CHUNK_SIZE):
            resp = append_blocks(page_id, new_blocks[j:j + CHUNK_SIZE])
            if "message" in resp:
                print(f"  [ERROR] {resp['message']}")
                return False
        return True

    # 기존 섹션 내용 삭제
    old_ids = get_section_content_ids(blocks, heading_id)
    print(f"  기존 블록 {len(old_ids)}개 삭제 중...")
    for bid in old_ids:
        archive_block(bid)

    # 새 블록 변환
    new_blocks = md_to_notion_blocks(content)

    # 파일 최상단 heading이 섹션 제목과 동일하면 중복 제거
    if new_blocks:
        first = new_blocks[0]
        if first.get("type") in ("heading_2", "heading_3"):
            first_text = (
                first.get(first["type"], {})
                .get("rich_text", [{}])[0]
                .get("text", {})
                .get("content", "")
            )
            if section_title.lower() in first_text.lower():
                new_blocks = new_blocks[1:]

    # heading 바로 뒤에 청크 단위로 삽입
    print(f"  새 블록 {len(new_blocks)}개 삽입 중...")
    after_id: str | None = heading_id
    for j in range(0, len(new_blocks), CHUNK_SIZE):
        chunk = new_blocks[j:j + CHUNK_SIZE]
        resp = append_blocks(page_id, chunk, after_id=after_id)
        if "results" in resp and resp["results"]:
            after_id = resp["results"][-1]["id"]
        elif "message" in resp:
            print(f"  [ERROR] {resp['message']}")
            return False

    print(f"  ✓ 동기화 완료: {file_path}")
    return True


# ─────────────────────────────────────────────
# main
# ─────────────────────────────────────────────

def main():
    if not NOTION_API_KEY:
        print("[ERROR] 환경 변수 NOTION_API_KEY가 설정되지 않았습니다.")
        sys.exit(1)

    changed_raw = os.environ.get("CHANGED_FILES", "").strip()
    changed_files = [f for f in changed_raw.split() if f.strip()]

    # 동기화 대상 필터링
    target_files = [f for f in changed_files if get_section_title(f) is not None]

    if not target_files:
        print("동기화 대상 파일 없음. 종료.")
        return

    print(f"동기화 대상: {target_files}")
    success = all(sync_file(fp) for fp in target_files)

    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
