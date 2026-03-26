"""외부 API 데이터 수집 모듈"""

from __future__ import annotations

import logging
import os
from datetime import datetime

import httpx

from .models import ApiConfig, ApiResult

logger = logging.getLogger(__name__)


class ApiCollector:
    """외부 API에서 데이터를 수집한다."""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout

    async def collect(self, api_config: ApiConfig, query: str = "") -> list[ApiResult]:
        """API 설정에 따라 데이터를 수집한다."""
        results: list[ApiResult] = []
        headers = self._build_auth_headers(api_config.auth)

        async with httpx.AsyncClient(timeout=self.timeout, headers=headers) as client:
            for endpoint in api_config.endpoints:
                try:
                    result = await self._call_endpoint(
                        client, api_config, endpoint.path, endpoint.params, query
                    )
                    results.append(result)
                except Exception as e:
                    logger.error(f"API 호출 실패 {api_config.name}{endpoint.path}: {e}")

        return results

    async def _call_endpoint(
        self,
        client: httpx.AsyncClient,
        api_config: ApiConfig,
        path: str,
        params: dict,
        query: str,
    ) -> ApiResult:
        """개별 엔드포인트를 호출한다."""
        url = f"{api_config.base_url.rstrip('/')}{path}"
        request_params = {**params}

        if query:
            request_params["q"] = query

        logger.info(f"API 호출: {api_config.name} - {path}")
        response = await client.get(url, params=request_params)
        response.raise_for_status()

        data = response.json()

        # 응답이 리스트가 아닌 경우 articles/results/data 키를 탐색
        items = data
        if isinstance(data, dict):
            for key in ["articles", "results", "data", "items", "entries"]:
                if key in data and isinstance(data[key], list):
                    items = data[key]
                    break
            else:
                items = [data]

        if not isinstance(items, list):
            items = [items]

        return ApiResult(
            api_name=api_config.name,
            endpoint=path,
            data=items,
            collected_at=datetime.now(),
        )

    def _build_auth_headers(self, auth: dict) -> dict:
        """인증 헤더를 구성한다."""
        headers: dict[str, str] = {}

        if not auth:
            return headers

        auth_type = auth.get("type", "")

        if auth_type == "api_key":
            env_var = auth.get("env_var", "")
            header_name = auth.get("header", "Authorization")
            api_key = os.getenv(env_var, "")
            if api_key:
                headers[header_name] = api_key
            else:
                logger.warning(f"환경변수 {env_var}가 설정되지 않음")

        elif auth_type == "bearer":
            env_var = auth.get("env_var", "")
            token = os.getenv(env_var, "")
            if token:
                headers["Authorization"] = f"Bearer {token}"

        return headers

    async def collect_all(
        self, api_configs: list[ApiConfig], query: str = ""
    ) -> list[ApiResult]:
        """모든 API에서 데이터를 수집한다."""
        all_results: list[ApiResult] = []
        for config in api_configs:
            results = await self.collect(config, query)
            all_results.extend(results)
        return all_results
