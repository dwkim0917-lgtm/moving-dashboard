"""리서치 봇 웹 대시보드 - FastAPI"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

import yaml
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

logger = logging.getLogger("research-bot.web")

app = FastAPI(title="리서치 자동화 봇 대시보드")

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def load_config() -> dict:
    config_path = BASE_DIR / "config.yaml"
    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}


def load_reports() -> list[dict]:
    """output/data 폴더에서 JSON 리포트들을 로드한다."""
    data_dir = BASE_DIR / "output" / "data"
    reports = []
    if not data_dir.exists():
        return reports

    for json_file in sorted(data_dir.glob("*.json"), reverse=True):
        try:
            with open(json_file, encoding="utf-8") as f:
                data = json.load(f)
                data["_filename"] = json_file.name
                reports.append(data)
        except Exception as e:
            logger.warning(f"JSON 파일 로드 실패: {json_file}: {e}")

    return reports


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    config = load_config()
    reports = load_reports()
    topics = config.get("topics", [])

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "topics": topics,
        "reports": reports,
        "total_reports": len(reports),
        "now": datetime.now().strftime("%Y-%m-%d %H:%M"),
    })


@app.get("/report/{filename}", response_class=HTMLResponse)
async def view_report(request: Request, filename: str):
    data_dir = BASE_DIR / "output" / "data"
    filepath = data_dir / filename

    if not filepath.exists() or not filepath.suffix == ".json":
        return HTMLResponse("<h1>보고서를 찾을 수 없습니다</h1>", status_code=404)

    with open(filepath, encoding="utf-8") as f:
        report = json.load(f)

    # 대응하는 마크다운 파일 확인
    md_filename = filename.replace(".json", ".md")
    md_path = BASE_DIR / "output" / "reports" / md_filename
    markdown_content = ""
    if md_path.exists():
        markdown_content = md_path.read_text(encoding="utf-8")

    return templates.TemplateResponse("report.html", {
        "request": request,
        "report": report,
        "markdown_content": markdown_content,
        "filename": filename,
    })


@app.get("/api/reports")
async def api_reports():
    return load_reports()


@app.get("/api/config")
async def api_config():
    return load_config()
