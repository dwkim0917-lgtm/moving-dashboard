"""AI 기반 리서치 모듈 - Anthropic Claude API 활용"""

from __future__ import annotations

import logging
import os

import anthropic

from .models import ApiResult, ResearchReport, ScrapedItem

logger = logging.getLogger(__name__)

DEFAULT_PROMPT_TEMPLATE = """다음 데이터를 분석하여 리서치 보고서를 작성해주세요.

주제: {topic}
수집된 데이터:
{data}

다음 형식으로 보고서를 작성해주세요:
1. 핵심 요약 (3-5문장)
2. 주요 발견사항 (불릿 포인트)
3. 트렌드 분석
4. 시사점 및 제안
"""


class AiResearcher:
    """Claude API를 활용한 AI 리서치 분석"""

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 4096,
        temperature: float = 0.3,
        prompt_template: str = "",
    ):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다.")

        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.prompt_template = prompt_template or DEFAULT_PROMPT_TEMPLATE

    def analyze(
        self,
        topic: str,
        scraped_items: list[ScrapedItem],
        api_results: list[ApiResult],
        category: str = "일반",
    ) -> ResearchReport:
        """수집된 데이터를 분석하여 리서치 보고서를 생성한다."""
        data_text = self._format_data(scraped_items, api_results)

        if not data_text.strip():
            logger.warning(f"'{topic}' 주제에 대한 수집 데이터가 없습니다.")
            return ResearchReport(
                topic=topic,
                category=category,
                summary="수집된 데이터가 없어 보고서를 생성할 수 없습니다.",
                full_report="",
                source_urls=[item.url for item in scraped_items if item.url],
                scraped_items=scraped_items,
                api_results=api_results,
            )

        prompt = self.prompt_template.format(topic=topic, data=data_text)

        logger.info(f"Claude API 호출 중: '{topic}' 분석")
        message = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            messages=[{"role": "user", "content": prompt}],
        )

        full_report = message.content[0].text

        # 요약 추출 (첫 번째 섹션)
        summary = self._extract_summary(full_report)

        source_urls = [item.url for item in scraped_items if item.url]

        return ResearchReport(
            topic=topic,
            category=category,
            summary=summary,
            full_report=full_report,
            source_urls=source_urls,
            scraped_items=scraped_items,
            api_results=api_results,
        )

    def research_topic(self, topic: str, category: str = "일반") -> ResearchReport:
        """주제에 대해 AI가 직접 리서치를 수행한다 (수집 데이터 없이)."""
        prompt = f"""'{topic}' 주제에 대해 깊이 있는 리서치 보고서를 작성해주세요.

다음 형식으로 작성해주세요:
1. 핵심 요약 (3-5문장)
2. 현재 상황 및 배경
3. 주요 발견사항 (불릿 포인트)
4. 트렌드 분석
5. 시사점 및 제안

가능한 최신 정보를 기반으로 작성해주세요."""

        logger.info(f"Claude API 직접 리서치: '{topic}'")
        message = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            messages=[{"role": "user", "content": prompt}],
        )

        full_report = message.content[0].text
        summary = self._extract_summary(full_report)

        return ResearchReport(
            topic=topic,
            category=category,
            summary=summary,
            full_report=full_report,
        )

    def _format_data(
        self, scraped_items: list[ScrapedItem], api_results: list[ApiResult]
    ) -> str:
        """수집된 데이터를 텍스트로 포맷한다."""
        parts: list[str] = []

        if scraped_items:
            parts.append("## 웹 스크래핑 결과")
            for i, item in enumerate(scraped_items[:15], 1):
                parts.append(f"\n### {i}. {item.title}")
                if item.content:
                    parts.append(item.content[:300])
                if item.url:
                    parts.append(f"출처: {item.url}")

        if api_results:
            parts.append("\n## API 수집 결과")
            for result in api_results:
                parts.append(f"\n### {result.api_name} ({result.endpoint})")
                for i, data in enumerate(result.data[:10], 1):
                    # 주요 필드만 추출
                    title = data.get("title", data.get("name", f"항목 {i}"))
                    desc = data.get("description", data.get("content", data.get("summary", "")))
                    parts.append(f"- {title}")
                    if desc:
                        parts.append(f"  {str(desc)[:200]}")

        return "\n".join(parts)

    def _extract_summary(self, full_report: str) -> str:
        """보고서에서 핵심 요약을 추출한다."""
        lines = full_report.split("\n")
        summary_lines: list[str] = []
        in_summary = False

        for line in lines:
            if "핵심 요약" in line or "요약" in line.lower():
                in_summary = True
                continue
            if in_summary:
                if line.startswith("#") or line.startswith("2."):
                    break
                if line.strip():
                    summary_lines.append(line.strip())

        if summary_lines:
            return " ".join(summary_lines[:5])

        # 요약 섹션을 못 찾으면 첫 3줄 사용
        non_empty = [l.strip() for l in lines if l.strip() and not l.startswith("#")]
        return " ".join(non_empty[:3])[:500]
