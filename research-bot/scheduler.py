"""예약 실행 모듈 - APScheduler 기반"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from src.models import TopicConfig

logger = logging.getLogger("research-bot.scheduler")


def _run_topic_research(topic_dict: dict, config: dict) -> None:
    """스케줄러에서 호출되는 리서치 실행 함수"""
    from main import run_research

    topic = TopicConfig(**topic_dict)
    logger.info(f"[스케줄] 리서치 실행: '{topic.name}'")

    try:
        asyncio.run(run_research(topic, config))
    except Exception as e:
        logger.error(f"[스케줄] 리서치 실패 '{topic.name}': {e}")


def start_scheduler(config: dict) -> None:
    """스케줄러를 시작한다."""
    scheduler = BlockingScheduler()
    schedule_config = config.get("schedule", {})
    default_cron = schedule_config.get("default_cron", "0 9 * * *")
    topic_schedules = schedule_config.get("topic_schedules", {})

    topics = config.get("topics", [])
    if not topics:
        logger.error("설정에 주제가 없습니다.")
        return

    for topic_data in topics:
        topic_name = topic_data["name"]
        cron_expr = topic_schedules.get(topic_name, default_cron)

        # cron 표현식 파싱 (분 시 일 월 요일)
        parts = cron_expr.split()
        if len(parts) != 5:
            logger.error(f"잘못된 cron 표현식: {cron_expr} (주제: {topic_name})")
            continue

        trigger = CronTrigger(
            minute=parts[0],
            hour=parts[1],
            day=parts[2],
            month=parts[3],
            day_of_week=parts[4],
        )

        scheduler.add_job(
            _run_topic_research,
            trigger=trigger,
            args=[topic_data, config],
            id=f"research_{topic_name}",
            name=f"리서치: {topic_name}",
            replace_existing=True,
        )

        logger.info(f"스케줄 등록: '{topic_name}' - cron: {cron_expr}")

    # 등록된 작업 목록 출력
    jobs = scheduler.get_jobs()
    logger.info(f"\n총 {len(jobs)}개 작업 등록 완료")
    for job in jobs:
        logger.info(f"  - {job.name} | 다음 실행: {job.next_run_time}")

    # 종료 시그널 처리
    def shutdown(signum, frame):
        logger.info("스케줄러 종료 중...")
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    logger.info("\n스케줄러 시작! (Ctrl+C로 종료)")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("스케줄러 종료됨")
