"""법령 데이터 수집기.

국가법령정보센터 OPEN API에서 법령 목록을 조회하고 본문을 수집한다.
constants.py의 TARGET_LAWS에 정의된 법령만 수집한다.
"""

import asyncio
import structlog

from lxml import etree

from lawtutor.collectors.base import BaseCollector
from lawtutor.constants import (
    LAW_API_SEARCH_PATH,
    LAW_API_SERVICE_PATH,
    TARGET_LAW,
    TARGET_LAWS,
    LAW_SUFFIX_VARIANTS,
    API_DEFAULT_DISPLAY,
)

logger = structlog.get_logger()


class LawCollector(BaseCollector):
    """법령(법률/시행령/시행규칙) 수집기."""

    def __init__(self) -> None:
        """LawCollector를 초기화한다."""
        super().__init__(target=TARGET_LAW)

    async def search_laws(
        self, query: str, display: int = API_DEFAULT_DISPLAY, page: int = 1
    ) -> list[dict[str, str]]:
        """법령 목록을 검색한다.

        Args:
            query: 검색 키워드 (법령명)
            display: 한 페이지당 결과 수
            page: 페이지 번호

        Returns:
            법령 목록. 각 항목은 법령일련번호, 법령명, 법령ID 등 포함.
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
        logger.info("law_search_result", query=query, total=total, page=page)

        results: list[dict[str, str]] = []
        for law_el in root.findall("law"):
            results.append({
                "법령일련번호": self._get_text(law_el, "법령일련번호"),
                "법령명한글": self._get_text(law_el, "법령명한글"),
                "법령ID": self._get_text(law_el, "법령ID"),
                "현행연혁코드": self._get_text(law_el, "현행연혁코드"),
                "공포일자": self._get_text(law_el, "공포일자"),
                "시행일자": self._get_text(law_el, "시행일자"),
                "법령구분명": self._get_text(law_el, "법령구분명"),
                "소관부처명": self._get_text(law_el, "소관부처명"),
            })
        return results

    async def fetch_law_detail(self, mst: str) -> bytes:
        """법령 본문(XML)을 조회하고 원본을 저장한다.

        Args:
            mst: 법령일련번호 (lawSearch의 법령일련번호 값)

        Returns:
            API 응답 원본 바이트
        """
        raw = await self._request(LAW_API_SERVICE_PATH, {
            "target": self.target,
            "MST": mst,
        })
        self._save_raw(raw, f"detail_{mst}.xml")
        logger.info("law_detail_fetched", mst=mst, size=len(raw))
        return raw

    async def collect_target_laws(self) -> list[dict[str, str]]:
        """TARGET_LAWS에 정의된 모든 법령과 시행령/시행규칙을 수집한다.

        Returns:
            수집된 법령 정보 리스트
        """
        collected: list[dict[str, str]] = []

        for law_info in TARGET_LAWS:
            law_name = law_info["name"]
            for suffix in LAW_SUFFIX_VARIANTS:
                query = f"{law_name}{suffix}"
                logger.info("collecting_law", query=query)

                results = await self.search_laws(query)
                if not results:
                    logger.info("no_results", query=query)
                    continue

                for result in results:
                    mst = result["법령일련번호"]
                    if not mst:
                        continue

                    # 본문 수집
                    await self.fetch_law_detail(mst)
                    collected.append(result)

                    # API rate limit 배려
                    await asyncio.sleep(0.5)

                await asyncio.sleep(0.3)

        logger.info("law_collection_complete", total=len(collected))
        return collected
