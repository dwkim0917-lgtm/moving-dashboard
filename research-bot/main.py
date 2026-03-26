"""리서치 자동화 봇 - CLI 진입점"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

import click
import yaml
from dotenv import load_dotenv

from src.ai_researcher import AiResearcher
from src.api_collector import ApiCollector
from src.file_saver import FileSaver
from src.models import ApiConfig, ApiEndpoint, TopicConfig
from src.notion_saver import NotionSaver
from src.scraper import WebScraper

# .env 파일 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("research-bot")


def load_config(config_path: str = "config.yaml") -> dict:
    """설정 파일을 로드한다."""
    path = Path(config_path)
    if not path.exists():
        logger.error(f"설정 파일을 찾을 수 없습니다: {config_path}")
        sys.exit(1)

    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_topics(config: dict) -> list[TopicConfig]:
    """설정에서 주제 목록을 파싱한다."""
    return [TopicConfig(**t) for t in config.get("topics", [])]


def get_api_configs(config: dict) -> list[ApiConfig]:
    """설정에서 API 설정을 파싱한다."""
    apis = []
    for api in config.get("apis", []):
        endpoints = [ApiEndpoint(**ep) for ep in api.get("endpoints", [])]
        apis.append(ApiConfig(
            name=api["name"],
            base_url=api["base_url"],
            endpoints=endpoints,
            auth=api.get("auth", {}),
        ))
    return apis


async def run_research(
    topic: TopicConfig,
    config: dict,
    skip_notion: bool = False,
    skip_ai: bool = False,
) -> None:
    """단일 주제에 대해 리서치를 수행한다."""
    logger.info(f"=== 리서치 시작: '{topic.name}' ===")

    scraping_config = config.get("scraping", {})
    ai_config = config.get("ai", {})
    output_config = config.get("output", {})

    # 1. 웹 스크래핑
    scraper = WebScraper(
        timeout=scraping_config.get("timeout", 30),
        max_retries=scraping_config.get("max_retries", 3),
        delay=scraping_config.get("delay_between_requests", 2.0),
        user_agent=scraping_config.get("user_agent", "ResearchBot/1.0"),
    )
    scraped_items = await scraper.scrape_urls(topic.urls) if topic.urls else []
    logger.info(f"스크래핑 완료: {len(scraped_items)}개 항목 수집")

    # 2. API 데이터 수집
    api_configs = get_api_configs(config)
    api_results = []
    if api_configs:
        collector = ApiCollector(timeout=scraping_config.get("timeout", 30))
        for keyword in topic.keywords[:3]:
            try:
                results = await collector.collect_all(api_configs, query=keyword)
                api_results.extend(results)
            except Exception as e:
                logger.warning(f"API 수집 실패 ({keyword}): {e}")
    logger.info(f"API 수집 완료: {len(api_results)}개 결과")

    # 3. AI 분석
    if skip_ai:
        from src.models import ResearchReport
        report = ResearchReport(
            topic=topic.name,
            category=topic.category,
            summary="AI 분석 건너뜀",
            scraped_items=scraped_items,
            api_results=api_results,
            source_urls=[item.url for item in scraped_items if item.url],
        )
    else:
        try:
            researcher = AiResearcher(
                model=ai_config.get("model", "claude-sonnet-4-20250514"),
                max_tokens=ai_config.get("max_tokens", 4096),
                temperature=ai_config.get("temperature", 0.3),
                prompt_template=ai_config.get("prompt_template", ""),
            )

            if scraped_items or api_results:
                report = researcher.analyze(
                    topic.name, scraped_items, api_results, topic.category
                )
            else:
                report = researcher.research_topic(topic.name, topic.category)
        except Exception as e:
            logger.error(f"AI 분석 실패: {e}")
            from src.models import ResearchReport
            report = ResearchReport(
                topic=topic.name,
                category=topic.category,
                summary=f"AI 분석 실패: {e}",
                scraped_items=scraped_items,
                api_results=api_results,
                source_urls=[item.url for item in scraped_items if item.url],
            )

    # 4. 로컬 저장
    file_saver = FileSaver(
        reports_dir=output_config.get("reports_dir", "output/reports"),
        data_dir=output_config.get("data_dir", "output/data"),
    )
    md_path, json_path = file_saver.save(report)
    logger.info(f"로컬 저장 완료: {md_path}, {json_path}")

    # 5. Notion 저장
    if not skip_notion:
        try:
            notion_saver = NotionSaver()
            page_id = notion_saver.save(report)
            logger.info(f"Notion 저장 완료: {page_id}")
        except Exception as e:
            logger.warning(f"Notion 저장 실패 (건너뜀): {e}")

    logger.info(f"=== 리서치 완료: '{topic.name}' ===\n")


@click.group()
def cli():
    """리서치 자동화 봇 CLI"""
    pass


@cli.command()
@click.option("--topic", "-t", help="리서치할 주제 이름")
@click.option("--all", "run_all", is_flag=True, help="모든 주제 리서치")
@click.option("--config", "config_path", default="config.yaml", help="설정 파일 경로")
@click.option("--skip-notion", is_flag=True, help="Notion 저장 건너뛰기")
@click.option("--skip-ai", is_flag=True, help="AI 분석 건너뛰기 (데이터 수집만)")
def run(topic: str | None, run_all: bool, config_path: str, skip_notion: bool, skip_ai: bool):
    """리서치를 수동 실행한다."""
    config = load_config(config_path)
    topics = get_topics(config)

    if not topics:
        logger.error("설정에 주제가 없습니다. config.yaml을 확인하세요.")
        return

    if run_all:
        selected = topics
    elif topic:
        selected = [t for t in topics if t.name == topic]
        if not selected:
            available = ", ".join(t.name for t in topics)
            logger.error(f"주제 '{topic}'을 찾을 수 없습니다. 사용 가능: {available}")
            return
    else:
        logger.error("--topic 또는 --all 옵션을 지정하세요.")
        return

    for t in selected:
        asyncio.run(run_research(t, config, skip_notion=skip_notion, skip_ai=skip_ai))

    logger.info("모든 리서치 완료!")


@cli.command("list-topics")
@click.option("--config", "config_path", default="config.yaml", help="설정 파일 경로")
def list_topics(config_path: str):
    """설정된 주제 목록을 표시한다."""
    config = load_config(config_path)
    topics = get_topics(config)

    if not topics:
        click.echo("설정된 주제가 없습니다.")
        return

    click.echo(f"\n설정된 리서치 주제 ({len(topics)}개):\n")
    for i, t in enumerate(topics, 1):
        click.echo(f"  {i}. {t.name}")
        click.echo(f"     카테고리: {t.category}")
        click.echo(f"     키워드: {', '.join(t.keywords)}")
        click.echo(f"     URL: {len(t.urls)}개")
        click.echo()


@cli.command()
@click.option("--config", "config_path", default="config.yaml", help="설정 파일 경로")
def schedule(config_path: str):
    """스케줄러를 시작한다."""
    from scheduler import start_scheduler
    config = load_config(config_path)
    start_scheduler(config)


if __name__ == "__main__":
    cli()
