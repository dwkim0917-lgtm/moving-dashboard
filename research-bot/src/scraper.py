"""웹 스크래핑 모듈 - httpx + BeautifulSoup 기반"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from .models import ScrapedItem

logger = logging.getLogger(__name__)


class WebScraper:
    """웹 페이지에서 데이터를 수집하는 스크래퍼"""

    def __init__(
        self,
        timeout: int = 30,
        max_retries: int = 3,
        delay: float = 2.0,
        user_agent: str = "ResearchBot/1.0",
    ):
        self.timeout = timeout
        self.max_retries = max_retries
        self.delay = delay
        self.headers = {"User-Agent": user_agent}

    async def scrape_url(self, url: str) -> list[ScrapedItem]:
        """단일 URL에서 데이터를 수집한다."""
        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(
                    timeout=self.timeout, headers=self.headers, follow_redirects=True
                ) as client:
                    response = await client.get(url)
                    response.raise_for_status()
                    return self._parse_html(response.text, url)
            except httpx.HTTPStatusError as e:
                logger.warning(f"HTTP 오류 {e.response.status_code} for {url} (시도 {attempt + 1}/{self.max_retries})")
            except httpx.RequestError as e:
                logger.warning(f"요청 오류 {url}: {e} (시도 {attempt + 1}/{self.max_retries})")

            if attempt < self.max_retries - 1:
                await asyncio.sleep(self.delay * (attempt + 1))

        logger.error(f"모든 재시도 실패: {url}")
        return []

    async def scrape_urls(self, urls: list[str]) -> list[ScrapedItem]:
        """여러 URL에서 순차적으로 데이터를 수집한다 (rate limiting 적용)."""
        all_items: list[ScrapedItem] = []
        for url in urls:
            items = await self.scrape_url(url)
            all_items.extend(items)
            if url != urls[-1]:
                await asyncio.sleep(self.delay)
        return all_items

    def _parse_html(self, html: str, source_url: str) -> list[ScrapedItem]:
        """HTML을 파싱하여 ScrapedItem 리스트를 반환한다."""
        soup = BeautifulSoup(html, "lxml")
        items: list[ScrapedItem] = []

        # <article> 태그 기반 추출 시도
        articles = soup.find_all("article")
        if articles:
            for article in articles[:20]:
                item = self._extract_article(article, source_url)
                if item:
                    items.append(item)
            return items

        # 대체: 제목+링크 기반 추출
        for heading in soup.find_all(["h1", "h2", "h3"], limit=20):
            link = heading.find("a")
            title = heading.get_text(strip=True)
            if title and len(title) > 5:
                href = ""
                if link and link.get("href"):
                    href = link["href"]
                    if href.startswith("/"):
                        from urllib.parse import urljoin
                        href = urljoin(source_url, href)

                # 다음 형제에서 본문 추출
                content = ""
                next_el = heading.find_next_sibling(["p", "div", "span"])
                if next_el:
                    content = next_el.get_text(strip=True)[:500]

                items.append(ScrapedItem(
                    title=title,
                    content=content,
                    url=href or source_url,
                    source=source_url,
                ))

        return items

    def _extract_article(self, article, source_url: str) -> Optional[ScrapedItem]:
        """<article> 요소에서 ScrapedItem을 추출한다."""
        title_el = article.find(["h1", "h2", "h3", "h4"])
        if not title_el:
            return None

        title = title_el.get_text(strip=True)
        if not title or len(title) < 3:
            return None

        # 링크 추출
        link = title_el.find("a") or article.find("a")
        href = ""
        if link and link.get("href"):
            href = link["href"]
            if href.startswith("/"):
                from urllib.parse import urljoin
                href = urljoin(source_url, href)

        # 본문 추출
        paragraphs = article.find_all("p")
        content = " ".join(p.get_text(strip=True) for p in paragraphs[:3])[:500]

        # 날짜 추출
        time_el = article.find("time")
        published_at = time_el.get("datetime") if time_el else None

        return ScrapedItem(
            title=title,
            content=content,
            url=href or source_url,
            published_at=published_at,
            source=source_url,
        )
