"""evaluation/eval_set.py 단위 테스트."""

import pytest
from pathlib import Path

from lawtutor.evaluation.eval_set import EvalItem, load_eval_set, save_eval_item


class TestEvalItem:
    """EvalItem 모델 테스트."""

    def test_minimal(self) -> None:
        """최소 필드로 생성."""
        item = EvalItem(
            question="테스트 질문",
            category="행정법",
            difficulty="하",
            tool="search_law",
        )
        assert item.expected_articles == []
        assert item.expected_case_nos == []

    def test_full(self) -> None:
        """모든 필드 포함."""
        item = EvalItem(
            question="행정절차법 제21조",
            category="행정법",
            difficulty="중",
            tool="fetch_article_by_number",
            expected_articles=["행정절차법 제21조"],
            expected_case_nos=["2018두12345"],
        )
        assert len(item.expected_articles) == 1
        assert item.expected_case_nos[0] == "2018두12345"


class TestLoadSaveEvalSet:
    """평가셋 로드/저장 테스트."""

    def test_round_trip(self, tmp_path: Path) -> None:
        """저장 후 로드하면 동일."""
        path = tmp_path / "test.jsonl"
        item = EvalItem(
            question="테스트",
            category="헌법",
            difficulty="상",
            tool="search_constitutional_decision",
            expected_articles=["대한민국헌법 제37조"],
        )
        save_eval_item(path, item)
        loaded = load_eval_set(path)
        assert len(loaded) == 1
        assert loaded[0].question == "테스트"
        assert loaded[0].expected_articles == ["대한민국헌법 제37조"]

    def test_multiple_items(self, tmp_path: Path) -> None:
        """여러 항목 저장 후 로드."""
        path = tmp_path / "multi.jsonl"
        for i in range(3):
            save_eval_item(path, EvalItem(
                question=f"질문{i}",
                category="행정법",
                difficulty="하",
                tool="search_law",
            ))
        loaded = load_eval_set(path)
        assert len(loaded) == 3

    def test_load_actual_eval_set(self) -> None:
        """실제 평가셋 파일 로드."""
        from lawtutor.config import PROJECT_ROOT
        path = PROJECT_ROOT / "data" / "eval" / "eval_set_v1.jsonl"
        if path.exists():
            items = load_eval_set(path)
            assert len(items) >= 1
            for item in items:
                assert item.question
                assert item.tool
