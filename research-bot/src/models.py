"""리서치 봇 데이터 모델"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class TopicConfig(BaseModel):
    """리서치 주제 설정"""
    name: str
    keywords: list[str] = Field(default_factory=list)
    urls: list[str] = Field(default_factory=list)
    category: str = "일반"


class ApiEndpoint(BaseModel):
    """API 엔드포인트 설정"""
    path: str
    params: dict = Field(default_factory=dict)


class ApiConfig(BaseModel):
    """API 설정"""
    name: str
    base_url: str
    endpoints: list[ApiEndpoint] = Field(default_factory=list)
    auth: dict = Field(default_factory=dict)


class ScrapedItem(BaseModel):
    """스크래핑된 개별 항목"""
    title: str
    content: str = ""
    url: str = ""
    published_at: Optional[str] = None
    source: str = ""


class ApiResult(BaseModel):
    """API 호출 결과"""
    api_name: str
    endpoint: str
    data: list[dict] = Field(default_factory=list)
    collected_at: datetime = Field(default_factory=datetime.now)


class ResearchReport(BaseModel):
    """리서치 보고서"""
    topic: str
    category: str = "일반"
    summary: str = ""
    full_report: str = ""
    source_urls: list[str] = Field(default_factory=list)
    scraped_items: list[ScrapedItem] = Field(default_factory=list)
    api_results: list[ApiResult] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)

    @property
    def date_str(self) -> str:
        return self.created_at.strftime("%Y-%m-%d")

    @property
    def filename_safe_topic(self) -> str:
        return self.topic.replace(" ", "_").replace("/", "_")
