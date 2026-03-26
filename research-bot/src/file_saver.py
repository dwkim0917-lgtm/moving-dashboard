"""로컬 파일 저장 모듈 - Markdown + JSON"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .models import ResearchReport

logger = logging.getLogger(__name__)


class FileSaver:
    """리서치 결과를 로컬 파일로 저장한다."""

    def __init__(self, reports_dir: str = "output/reports", data_dir: str = "output/data"):
        self.reports_dir = Path(reports_dir)
        self.data_dir = Path(data_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def save(self, report: ResearchReport) -> tuple[Path, Path]:
        """보고서를 Markdown과 JSON으로 저장한다."""
        md_path = self.save_markdown(report)
        json_path = self.save_json(report)
        return md_path, json_path

    def save_markdown(self, report: ResearchReport) -> Path:
        """Markdown 형식으로 리포트를 저장한다."""
        filename = f"{report.date_str}_{report.filename_safe_topic}.md"
        filepath = self.reports_dir / filename

        content = self._build_markdown(report)
        filepath.write_text(content, encoding="utf-8")

        logger.info(f"Markdown 보고서 저장: {filepath}")
        return filepath

    def save_json(self, report: ResearchReport) -> Path:
        """JSON 형식으로 원본 데이터를 저장한다."""
        filename = f"{report.date_str}_{report.filename_safe_topic}.json"
        filepath = self.data_dir / filename

        data = {
            "topic": report.topic,
            "category": report.category,
            "summary": report.summary,
            "full_report": report.full_report,
            "source_urls": report.source_urls,
            "created_at": report.created_at.isoformat(),
            "scraped_items": [item.model_dump() for item in report.scraped_items],
            "api_results": [
                {
                    "api_name": r.api_name,
                    "endpoint": r.endpoint,
                    "data": r.data,
                    "collected_at": r.collected_at.isoformat(),
                }
                for r in report.api_results
            ],
        }

        filepath.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        logger.info(f"JSON 데이터 저장: {filepath}")
        return filepath

    def _build_markdown(self, report: ResearchReport) -> str:
        """Markdown 보고서를 생성한다."""
        lines = [
            f"# {report.topic} - 리서치 보고서",
            f"",
            f"- **날짜**: {report.date_str}",
            f"- **카테고리**: {report.category}",
            f"",
            f"---",
            f"",
            f"## 요약",
            f"",
            report.summary,
            f"",
            f"---",
            f"",
        ]

        if report.full_report:
            lines.extend([
                f"## 상세 보고서",
                f"",
                report.full_report,
                f"",
            ])

        if report.source_urls:
            lines.extend([
                f"---",
                f"",
                f"## 출처",
                f"",
            ])
            for url in report.source_urls:
                lines.append(f"- {url}")
            lines.append("")

        return "\n".join(lines)
