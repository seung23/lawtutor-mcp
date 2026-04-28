"""대법원 판례 수집기.

국가법령정보센터 OPEN API에서 판례를 검색하고 본문을 수집한다.
constants.py의 PREC_SEARCH_KEYWORDS를 사용하여 행정법 관련 판례를 수집한다.
"""

import asyncio
import structlog

from lawtutor.collectors.base import BaseCollector
from lawtutor.constants import (
    LAW_API_SEARCH_PATH,
    LAW_API_SERVICE_PATH,
    TARGET_PREC,
    PREC_SEARCH_KEYWORDS,
    API_DEFAULT_DISPLAY,
)

logger = structlog.get_logger()


class PrecCollector(BaseCollector):
    """대법원 판례 수집기."""

    def __init__(self) -> None:
        """PrecCollector를 초기화한다."""
        super().__init__(target=TARGET_PREC)

    async def search_precedents(
        self, query: str, display: int = API_DEFAULT_DISPLAY, page: int = 1
    ) -> tuple[list[dict[str, str]], int]:
        """판례 목록을 검색한다.

        Args:
            query: 검색 키워드
            display: 한 페이지당 결과 수
            page: 페이지 번호

        Returns:
            (판례 목록, 전체 결과 수) 튜플
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
        logger.info("prec_search_result", query=query, total=total, page=page)

        results: list[dict[str, str]] = []
        for prec_el in root.findall("prec"):
            results.append({
                "판례일련번호": self._get_text(prec_el, "판례일련번호"),
                "사건명": self._get_text(prec_el, "사건명"),
                "사건번호": self._get_text(prec_el, "사건번호"),
                "선고일자": self._get_text(prec_el, "선고일자"),
                "사건종류명": self._get_text(prec_el, "사건종류명"),
            })
        return results, total

    async def fetch_precedent_detail(self, prec_id: str) -> bytes:
        """판례 본문(XML)을 조회하고 원본을 저장한다.

        Args:
            prec_id: 판례일련번호

        Returns:
            API 응답 원본 바이트
        """
        raw = await self._request(LAW_API_SERVICE_PATH, {
            "target": self.target,
            "ID": prec_id,
        })
        self._save_raw(raw, f"detail_{prec_id}.xml")
        logger.info("prec_detail_fetched", prec_id=prec_id, size=len(raw))
        return raw

    async def collect_all(self, max_pages_per_keyword: int = 5) -> list[dict[str, str]]:
        """PREC_SEARCH_KEYWORDS로 판례를 수집한다.

        Args:
            max_pages_per_keyword: 키워드당 최대 수집 페이지 수

        Returns:
            수집된 판례 정보 리스트
        """
        collected: list[dict[str, str]] = []
        seen_ids: set[str] = set()

        for keyword in PREC_SEARCH_KEYWORDS:
            logger.info("collecting_prec", keyword=keyword)

            for page in range(1, max_pages_per_keyword + 1):
                results, total = await self.search_precedents(keyword, page=page)
                if not results:
                    break

                for result in results:
                    prec_id = result["판례일련번호"]
                    if not prec_id or prec_id in seen_ids:
                        continue

                    seen_ids.add(prec_id)
                    await self.fetch_precedent_detail(prec_id)
                    collected.append(result)
                    await asyncio.sleep(0.5)

                # 마지막 페이지면 중단
                if page * API_DEFAULT_DISPLAY >= total:
                    break

                await asyncio.sleep(0.3)

        logger.info("prec_collection_complete", total=len(collected))
        return collected
