"""헌법재판소 결정례 수집기.

국가법령정보센터 OPEN API에서 헌재결정례를 검색하고 본문을 수집한다.
"""

import asyncio
import structlog

from lawtutor.collectors.base import BaseCollector
from lawtutor.constants import (
    LAW_API_SEARCH_PATH,
    LAW_API_SERVICE_PATH,
    TARGET_DETC,
    DETC_SEARCH_KEYWORDS,
    API_DEFAULT_DISPLAY,
)

logger = structlog.get_logger()


class DetcCollector(BaseCollector):
    """헌법재판소 결정례 수집기."""

    def __init__(self) -> None:
        """DetcCollector를 초기화한다."""
        super().__init__(target=TARGET_DETC)

    async def search_decisions(
        self, query: str, display: int = API_DEFAULT_DISPLAY, page: int = 1
    ) -> tuple[list[dict[str, str]], int]:
        """헌재결정례 목록을 검색한다.

        Args:
            query: 검색 키워드
            display: 한 페이지당 결과 수
            page: 페이지 번호

        Returns:
            (결정례 목록, 전체 결과 수) 튜플
        """
        raw = await self._request(LAW_API_SEARCH_PATH, {
            "target": self.target,
            "query": query,
            "display": display,
            "page": page,
        })
        self._save_raw(raw, f"search_{query}_{page}.xml")

        root = self._parse_xml(raw)
        total = self._get_int(root, "totalCnt")
        logger.info("detc_search_result", query=query, total=total, page=page)

        results: list[dict[str, str]] = []
        for detc_el in root.findall("Detc"):
            results.append({
                "헌재결정례일련번호": self._get_text(detc_el, "헌재결정례일련번호"),
                "사건명": self._get_text(detc_el, "사건명"),
                "사건번호": self._get_text(detc_el, "사건번호"),
                "종국일자": self._get_text(detc_el, "종국일자"),
            })
        return results, total

    async def fetch_decision_detail(self, detc_id: str) -> bytes:
        """헌재결정례 본문(XML)을 조회하고 원본을 저장한다.

        Args:
            detc_id: 헌재결정례일련번호

        Returns:
            API 응답 원본 바이트
        """
        raw = await self._request(LAW_API_SERVICE_PATH, {
            "target": self.target,
            "ID": detc_id,
        })
        self._save_raw(raw, f"detail_{detc_id}.xml")
        logger.info("detc_detail_fetched", detc_id=detc_id, size=len(raw))
        return raw

    async def collect_all(self, max_pages_per_keyword: int = 5) -> list[dict[str, str]]:
        """DETC_SEARCH_KEYWORDS로 헌재결정례를 수집한다.

        Args:
            max_pages_per_keyword: 키워드당 최대 수집 페이지 수

        Returns:
            수집된 결정례 정보 리스트
        """
        collected: list[dict[str, str]] = []
        seen_ids: set[str] = set()

        for keyword in DETC_SEARCH_KEYWORDS:
            logger.info("collecting_detc", keyword=keyword)

            for page in range(1, max_pages_per_keyword + 1):
                results, total = await self.search_decisions(keyword, page=page)
                if not results:
                    break

                for result in results:
                    detc_id = result["헌재결정례일련번호"]
                    if not detc_id or detc_id in seen_ids:
                        continue

                    seen_ids.add(detc_id)
                    await self.fetch_decision_detail(detc_id)
                    collected.append(result)
                    await asyncio.sleep(0.5)

                if page * API_DEFAULT_DISPLAY >= total:
                    break

                await asyncio.sleep(0.3)

        logger.info("detc_collection_complete", total=len(collected))
        return collected
