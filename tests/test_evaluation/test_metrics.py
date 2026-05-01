"""evaluation/metrics.py 단위 테스트."""

import pytest

from lawtutor.evaluation.metrics import (
    compute_aggregate_metrics,
    metadata_integrity_rate,
    reciprocal_rank,
    retrieval_recall_at_k,
)


class TestRetrievalRecallAtK:
    """retrieval_recall_at_k 테스트."""

    def test_no_expected(self) -> None:
        """정답이 없으면 1.0 (해당 없음)."""
        assert retrieval_recall_at_k([], [], []) == 1.0

    def test_perfect_recall(self) -> None:
        """정답이 모두 포함되면 1.0."""
        retrieved = [
            {"metadata": {"law_name": "행정절차법", "article_no": "21"}},
        ]
        assert retrieval_recall_at_k(retrieved, ["행정절차법 제21조"], []) == 1.0

    def test_partial_recall(self) -> None:
        """정답 2개 중 1개만 포함."""
        retrieved = [
            {"metadata": {"law_name": "행정절차법", "article_no": "21"}},
        ]
        recall = retrieval_recall_at_k(
            retrieved, ["행정절차법 제21조", "행정절차법 제22조"], [],
        )
        assert recall == 0.5

    def test_zero_recall(self) -> None:
        """정답이 하나도 없으면 0.0."""
        retrieved = [
            {"metadata": {"law_name": "행정소송법", "article_no": "1"}},
        ]
        assert retrieval_recall_at_k(retrieved, ["행정절차법 제21조"], []) == 0.0

    def test_case_no_recall(self) -> None:
        """사건번호 매칭 테스트."""
        retrieved = [
            {"metadata": {"case_no": "2018두12345"}},
        ]
        assert retrieval_recall_at_k(retrieved, [], ["2018두12345"]) == 1.0


class TestReciprocalRank:
    """reciprocal_rank 테스트."""

    def test_no_expected(self) -> None:
        """정답이 없으면 1.0."""
        assert reciprocal_rank([], [], []) == 1.0

    def test_first_position(self) -> None:
        """정답이 1번째면 RR=1.0."""
        retrieved = [
            {"metadata": {"law_name": "행정절차법", "article_no": "21"}},
        ]
        assert reciprocal_rank(retrieved, ["행정절차법 제21조"], []) == 1.0

    def test_second_position(self) -> None:
        """정답이 2번째면 RR=0.5."""
        retrieved = [
            {"metadata": {"law_name": "행정소송법", "article_no": "1"}},
            {"metadata": {"law_name": "행정절차법", "article_no": "21"}},
        ]
        assert reciprocal_rank(retrieved, ["행정절차법 제21조"], []) == 0.5

    def test_not_found(self) -> None:
        """정답이 없으면 RR=0.0."""
        retrieved = [
            {"metadata": {"law_name": "행정소송법", "article_no": "1"}},
        ]
        assert reciprocal_rank(retrieved, ["행정절차법 제21조"], []) == 0.0


class TestMetadataIntegrityRate:
    """metadata_integrity_rate 테스트."""

    def test_empty_results(self) -> None:
        """결과가 없으면 1.0."""
        assert metadata_integrity_rate([], ["law_name"]) == 1.0

    def test_all_complete(self) -> None:
        """모든 결과에 필수 필드 존재."""
        results = [
            {"metadata": {"law_name": "행정절차법", "article_no": "21"}},
            {"metadata": {"law_name": "행정소송법", "article_no": "1"}},
        ]
        assert metadata_integrity_rate(results, ["law_name", "article_no"]) == 1.0

    def test_partial_complete(self) -> None:
        """일부 결과에 필수 필드 누락."""
        results = [
            {"metadata": {"law_name": "행정절차법", "article_no": "21"}},
            {"metadata": {"law_name": "행정소송법"}},  # article_no 누락
        ]
        assert metadata_integrity_rate(results, ["law_name", "article_no"]) == 0.5


class TestComputeAggregateMetrics:
    """compute_aggregate_metrics 테스트."""

    def test_empty(self) -> None:
        """빈 입력."""
        result = compute_aggregate_metrics([])
        assert result["total_items"] == 0
        assert result["recall_at_k"] == 0.0

    def test_aggregation(self) -> None:
        """집계 계산."""
        items = [
            {"recall": 1.0, "rr": 1.0, "integrity": 1.0},
            {"recall": 0.5, "rr": 0.5, "integrity": 0.5},
        ]
        result = compute_aggregate_metrics(items)
        assert result["total_items"] == 2
        assert result["recall_at_k"] == 0.75
        assert result["mrr"] == 0.75
        assert result["metadata_integrity"] == 0.75
