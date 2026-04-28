"""BaseCollector 단위 테스트."""

import pytest
from unittest.mock import AsyncMock, patch

from lawtutor.collectors.base import BaseCollector


SAMPLE_SEARCH_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<LawSearch>
    <totalCnt>1</totalCnt>
    <law id="1">
        <name>test</name>
        <value>123</value>
    </law>
</LawSearch>"""


class TestBaseCollector:
    """BaseCollector 테스트."""

    @pytest.mark.asyncio
    async def test_context_manager(self) -> None:
        """async context manager로 클라이언트가 생성/종료되는지 확인."""
        collector = BaseCollector("law")
        assert collector._client is None

        async with collector:
            assert collector._client is not None

        assert collector._client is None

    def test_client_without_context(self) -> None:
        """context manager 없이 client 접근 시 RuntimeError."""
        collector = BaseCollector("law")
        with pytest.raises(RuntimeError):
            _ = collector.client

    def test_parse_xml(self) -> None:
        """XML 파싱이 정상적으로 동작하는지 확인."""
        collector = BaseCollector("law")
        root = collector._parse_xml(SAMPLE_SEARCH_XML)
        assert root.tag == "LawSearch"
        assert collector._get_text(root, "totalCnt") == "1"

    def test_get_text_missing_tag(self) -> None:
        """존재하지 않는 태그에 대해 빈 문자열 반환."""
        collector = BaseCollector("law")
        root = collector._parse_xml(SAMPLE_SEARCH_XML)
        assert collector._get_text(root, "nonexistent") == ""

    def test_get_int(self) -> None:
        """정수 파싱이 정상적으로 동작하는지 확인."""
        collector = BaseCollector("law")
        root = collector._parse_xml(SAMPLE_SEARCH_XML)
        assert collector._get_int(root, "totalCnt") == 1
        assert collector._get_int(root, "nonexistent", default=-1) == -1

    @pytest.mark.asyncio
    async def test_save_raw(self, tmp_path) -> None:
        """원본 저장이 정상적으로 동작하는지 확인."""
        with patch("lawtutor.collectors.base.settings") as mock_settings:
            mock_settings.data_raw_dir = tmp_path / "raw"
            collector = BaseCollector("law")
            filepath = collector._save_raw(b"test data", "test.xml")

            assert filepath.exists()
            assert filepath.read_bytes() == b"test data"
            assert "law" in str(filepath)
