"""formatter 단위 테스트."""

import time

import pytest

from lawtutor.retrieval.formatter import format_results


class TestFormatResults:
    """format_results 함수 테스트."""

    def test_empty_results(self) -> None:
        """빈 결과 리스트를 처리한다."""
        resp = format_results([], "test query", ["laws"])
        assert resp.total_found == 0
        assert resp.results == []
        assert resp.query == "test query"

    def test_single_result(self) -> None:
        """단일 결과를 올바르게 변환한다."""
        raw = [{
            "payload": {
                "text": "행정절차법 제21조 내용",
                "law_name": "행정절차법",
                "article_no": "21",
                "chunk_id": "internal-id",
                "chunk_type": "article",
            },
            "score": 0.85,
        }]

        resp = format_results(raw, "처분의 사전통지", ["laws"])
        assert resp.total_found == 1
        result = resp.results[0]
        assert result.content == "행정절차법 제21조 내용"
        assert result.score == 0.85
        assert result.metadata["law_name"] == "행정절차법"
        # chunk_id, chunk_type은 제거되어야 함
        assert "chunk_id" not in result.metadata
        assert "chunk_type" not in result.metadata

    def test_multiple_results(self) -> None:
        """여러 결과를 올바르게 변환한다."""
        raw = [
            {"payload": {"text": "첫째", "key": "val1"}, "score": 0.9},
            {"payload": {"text": "둘째", "key": "val2"}, "score": 0.7},
            {"payload": {"text": "셋째", "key": "val3"}, "score": 0.5},
        ]

        resp = format_results(raw, "query", ["laws", "precedents"])
        assert resp.total_found == 3
        assert resp.results[0].content == "첫째"
        assert resp.results[2].score == 0.5

    def test_search_metadata(self) -> None:
        """검색 메타데이터가 올바르게 포함된다."""
        start = time.time()
        resp = format_results(
            [], "query", ["laws"],
            filters_applied={"is_active": True},
            start_time=start,
        )
        meta = resp.search_metadata
        assert meta["collections_searched"] == ["laws"]
        assert meta["filters_applied"] == {"is_active": True}
        assert "search_time_ms" in meta

    def test_missing_score(self) -> None:
        """score가 없으면 0.0으로 기본값."""
        raw = [{"payload": {"text": "내용"}}]
        resp = format_results(raw, "query", ["laws"])
        assert resp.results[0].score == 0.0

    def test_filters_default_empty(self) -> None:
        """filters_applied가 None이면 빈 딕트."""
        resp = format_results([], "q", ["laws"], filters_applied=None)
        assert resp.search_metadata["filters_applied"] == {}
