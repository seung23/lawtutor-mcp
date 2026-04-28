"""법령해석례 수집기.

국가법령정보센터 OPEN API에서 법령해석례를 검색하고 본문을 수집한다.
"""

import asyncio
import structlog

from lawtutor.collectors.base import BaseCollector
from lawtutor.constants import (
    LAW_API_SEARCH_PATH,
    LAW_API_SERVICE_PATH,
    TARGET_EXPC,
    EXPC_SEARCH_KEYWORDS,
    API_DEFAULT_DISPLAY,
)

logger = structlog.get_logger()


class ExpcCollector(BaseCollector):
    """법령해석례 수집기."""

    def __init__(self) -> None:
        """ExpcCollector를 초기화한다."""
        super().__init__(target=TARGET_EXPC)

    async def search_interpretations(
        self, query: str, display: int = API_DEFAULT_DISPLAY, page: int = 1
    ) -> tuple[list[dict[str, str]], int]:
        """법령해석례 목록을 검색한다.

        Args:
            query: 검색 키워드
            display: 한 페이지당 결과 수
            page: 페이지 번호

        Returns:
            (해석례 목록, 전체 결과 수) 튜플
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
        logger.info("expc_search_result", query=query, total=total, page=page)

        results: list[dict[str, str]] = []
        for expc_el in root.findall("expc"):
            results.append({
                "법령해석례일련번호": self._get_text(expc_el, "법령해석례일련번호"),
                "안건명": self._get_text(expc_el, "안건명"),
                "안건번호": self._get_text(expc_el, "안건번호"),
                "회신일자": self._get_text(expc_el, "회신일자"),
                "질의기관명": self._get_text(expc_el, "질의기관명"),
            })
        return results, total

    async def fetch_interpretation_detail(self, expc_id: str) -> bytes:
        """법령해석례 본문(XML)을 조회하고 원본을 저장한다.

        Args:
            expc_id: 법령해석례일련번호

        Returns:
            API 응답 원본 바이트
        """
        raw = await self._request(LAW_API_SERVICE_PATH, {
            "target": self.target,
            "ID": expc_id,
        })
        self._save_raw(raw, f"detail_{expc_id}.xml")
        logger.info("expc_detail_fetched", expc_id=expc_id, size=len(raw))
        return raw

    async def collect_all(self, max_pages_per_keyword: int = 5) -> list[dict[str, str]]:
        """EXPC_SEARCH_KEYWORDS로 법령해석례를 수집한다.

        Args:
            max_pages_per_keyword: 키워드당 최대 수집 페이지 수

        Returns:
            수집된 해석례 정보 리스트
        """
        collected: list[dict[str, str]] = []
        seen_ids: set[str] = set()

        for keyword in EXPC_SEARCH_KEYWORDS:
            logger.info("collecting_expc", keyword=keyword)

            for page in range(1, max_pages_per_keyword + 1):
                results, total = await self.search_interpretations(keyword, page=page)
                if not results:
                    break

                for result in results:
                    expc_id = result["법령해석례일련번호"]
                    if not expc_id or expc_id in seen_ids:
                        continue

                    seen_ids.add(expc_id)
                    await self.fetch_interpretation_detail(expc_id)
                    collected.append(result)
                    await asyncio.sleep(0.5)

                if page * API_DEFAULT_DISPLAY >= total:
                    break

                await asyncio.sleep(0.3)

        logger.info("expc_collection_complete", total=len(collected))
        return collected
