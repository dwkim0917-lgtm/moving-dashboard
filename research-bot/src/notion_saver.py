"""Notion 저장 모듈 - notion-client 활용"""

from __future__ import annotations

import logging
import os

from notion_client import Client

from .models import ResearchReport

logger = logging.getLogger(__name__)


class NotionSaver:
    """리서치 결과를 Notion 데이터베이스에 저장한다."""

    def __init__(self, database_id: str = "", token: str = ""):
        self.token = token or os.getenv("NOTION_TOKEN", "")
        self.database_id = database_id or os.getenv("NOTION_DATABASE_ID", "")

        if not self.token:
            raise ValueError("NOTION_TOKEN 환경변수가 설정되지 않았습니다.")
        if not self.database_id:
            raise ValueError("NOTION_DATABASE_ID 환경변수가 설정되지 않았습니다.")

        self.client = Client(auth=self.token)

    def save(self, report: ResearchReport) -> str:
        """보고서를 Notion 데이터베이스에 저장하고 페이지 ID를 반환한다."""
        properties = self._build_properties(report)
        children = self._build_content_blocks(report)

        logger.info(f"Notion에 저장 중: '{report.topic}'")

        page = self.client.pages.create(
            parent={"database_id": self.database_id},
            properties=properties,
            children=children[:100],  # Notion API 블록 제한
        )

        page_id = page["id"]
        logger.info(f"Notion 저장 완료: {page_id}")
        return page_id

    def _build_properties(self, report: ResearchReport) -> dict:
        """Notion 페이지 속성을 구성한다."""
        properties: dict = {
            "제목": {
                "title": [{"text": {"content": f"{report.topic} - {report.date_str}"}}]
            },
            "날짜": {
                "date": {"start": report.created_at.isoformat()}
            },
            "카테고리": {
                "select": {"name": report.category}
            },
            "요약": {
                "rich_text": [{"text": {"content": report.summary[:2000]}}]
            },
            "상태": {
                "select": {"name": "완료"}
            },
        }

        if report.source_urls:
            properties["출처"] = {
                "url": report.source_urls[0]
            }

        return properties

    def _build_content_blocks(self, report: ResearchReport) -> list[dict]:
        """보고서 내용을 Notion 블록으로 변환한다."""
        blocks: list[dict] = []

        # 요약 섹션
        blocks.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"type": "text", "text": {"content": "요약"}}]
            },
        })
        blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"type": "text", "text": {"content": report.summary[:2000]}}]
            },
        })

        # 상세 보고서 (2000자씩 분할)
        if report.full_report:
            blocks.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": "상세 보고서"}}]
                },
            })

            # Notion 블록 텍스트 제한(2000자)에 맞게 분할
            text = report.full_report
            while text:
                chunk = text[:2000]
                text = text[2000:]
                blocks.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": chunk}}]
                    },
                })

        # 출처 섹션
        if report.source_urls:
            blocks.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": "출처"}}]
                },
            })
            for url in report.source_urls[:20]:
                blocks.append({
                    "object": "block",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {
                        "rich_text": [{"type": "text", "text": {"content": url, "link": {"url": url}}}]
                    },
                })

        return blocks
