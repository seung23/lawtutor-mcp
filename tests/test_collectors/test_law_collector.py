"""LawCollector 단위 테스트 (mock 사용)."""

import pytest
from unittest.mock import AsyncMock, patch

from lawtutor.collectors.law_collector import LawCollector


SAMPLE_LAW_SEARCH_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<LawSearch>
    <target>law</target>
    <totalCnt>1</totalCnt>
    <page>1</page>
    <law id="1">
        <\xeb\xb2\x95\xeb\xa0\xb9\xec\x9d\xbc\xeb\xa0\xa8\xeb\xb2\x88\xed\x98\xb8>239291</\xeb\xb2\x95\xeb\xa0\xb9\xec\x9d\xbc\xeb\xa0\xa8\xeb\xb2\x88\xed\x98\xb8>
        <\xeb\xb2\x95\xeb\xa0\xb9\xeb\xaa\x85\xed\x95\x9c\xea\xb8\x80>\xed\x96\x89\xec\xa0\x95\xec\xa0\x88\xec\xb0\xa8\xeb\xb2\x95</\xeb\xb2\x95\xeb\xa0\xb9\xeb\xaa\x85\xed\x95\x9c\xea\xb8\x80>
        <\xeb\xb2\x95\xeb\xa0\xb9ID>001362</\xeb\xb2\x95\xeb\xa0\xb9ID>
        <\xed\x98\x84\xed\x96\x89\xec\x97\xb0\xed\x98\x81\xec\xbd\x94\xeb\x93\x9c>\xed\x98\x84\xed\x96\x89</\xed\x98\x84\xed\x96\x89\xec\x97\xb0\xed\x98\x81\xec\xbd\x94\xeb\x93\x9c>
        <\xea\xb3\xb5\xed\x8f\xac\xec\x9d\xbc\xec\x9e\x90>20220111</\xea\xb3\xb5\xed\x8f\xac\xec\x9d\xbc\xec\x9e\x90>
        <\xec\x8b\x9c\xed\x96\x89\xec\x9d\xbc\xec\x9e\x90>20230324</\xec\x8b\x9c\xed\x96\x89\xec\x9d\xbc\xec\x9e\x90>
        <\xeb\xb2\x95\xeb\xa0\xb9\xea\xb5\xac\xeb\xb6\x84\xeb\xaa\x85>\xeb\xb2\x95\xeb\xa5\xa0</\xeb\xb2\x95\xeb\xa0\xb9\xea\xb5\xac\xeb\xb6\x84\xeb\xaa\x85>
        <\xec\x86\x8c\xea\xb4\x80\xeb\xb6\x80\xec\xb2\x98\xeb\xaa\x85>\xed\x96\x89\xec\xa0\x95\xec\x95\x88\xec\xa0\x84\xeb\xb6\x80</\xec\x86\x8c\xea\xb4\x80\xeb\xb6\x80\xec\xb2\x98\xeb\xaa\x85>
    </law>
</LawSearch>"""

# 한글 태그를 직접 사용하는 깨끗한 버전
SAMPLE_LAW_SEARCH_CLEAN = """<?xml version="1.0" encoding="UTF-8"?>
<LawSearch>
    <target>law</target>
    <totalCnt>1</totalCnt>
    <page>1</page>
    <law id="1">
        <법령일련번호>239291</법령일련번호>
        <법령명한글>행정절차법</법령명한글>
        <법령ID>001362</법령ID>
        <현행연혁코드>현행</현행연혁코드>
        <공포일자>20220111</공포일자>
        <시행일자>20230324</시행일자>
        <법령구분명>법률</법령구분명>
        <소관부처명>행정안전부</소관부처명>
    </law>
</LawSearch>""".encode("utf-8")


class TestLawCollector:
    """LawCollector 테스트."""

    @pytest.mark.asyncio
    async def test_search_laws(self, tmp_path) -> None:
        """법령 검색이 XML을 올바르게 파싱하는지 확인."""
        with patch("lawtutor.collectors.base.settings") as mock_settings:
            mock_settings.law_go_kr_oc = "test_oc"
            mock_settings.data_raw_dir = tmp_path / "raw"

            collector = LawCollector()
            collector._client = AsyncMock()
            collector._request = AsyncMock(return_value=SAMPLE_LAW_SEARCH_CLEAN)

            results = await collector.search_laws("행정절차법")

            assert len(results) == 1
            assert results[0]["법령일련번호"] == "239291"
            assert results[0]["법령명한글"] == "행정절차법"
            assert results[0]["현행연혁코드"] == "현행"
            assert results[0]["법령구분명"] == "법률"

    @pytest.mark.asyncio
    async def test_search_laws_empty(self, tmp_path) -> None:
        """결과가 없을 때 빈 리스트를 반환하는지 확인."""
        empty_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
        <LawSearch><totalCnt>0</totalCnt></LawSearch>"""

        with patch("lawtutor.collectors.base.settings") as mock_settings:
            mock_settings.law_go_kr_oc = "test_oc"
            mock_settings.data_raw_dir = tmp_path / "raw"

            collector = LawCollector()
            collector._request = AsyncMock(return_value=empty_xml)

            results = await collector.search_laws("존재하지않는법")
            assert results == []
