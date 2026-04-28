"""law_chunker 단위 테스트."""

import pytest

from lawtutor.models.law import LawArticle, LawMeta, ParsedLaw
from lawtutor.chunking.law_chunker import chunk_law


def _make_article(no: str, content: str, title: str = "") -> LawArticle:
    """테스트용 LawArticle 생성."""
    return LawArticle(
        law_id="001",
        law_mst="100",
        law_name="테스트법",
        article_no=no,
        article_title=title,
        article_content=content,
        effective_date="20240101",
    )


def _make_parsed(articles: list[LawArticle]) -> ParsedLaw:
    """테스트용 ParsedLaw 생성."""
    return ParsedLaw(
        meta=LawMeta(law_id="001", law_mst="100", law_name="테스트법"),
        articles=articles,
    )


class TestChunkLaw:
    """법령 청킹 테스트."""

    def test_short_article_single_chunk(self) -> None:
        """짧은 조문은 하나의 청크로."""
        parsed = _make_parsed([_make_article("1", "짧은 내용", "목적")])
        chunks = chunk_law(parsed)
        assert len(chunks) == 1
        assert chunks[0].chunk_type == "article"
        assert "테스트법 제1조" in chunks[0].text

    def test_long_article_split(self) -> None:
        """800자 초과 조문은 분할."""
        long_content = "\n".join([f"① 항{i} 내용입니다. " * 10 for i in range(20)])
        parsed = _make_parsed([_make_article("2", long_content, "긴조문")])
        chunks = chunk_law(parsed)
        assert len(chunks) > 1
        for c in chunks:
            assert len(c.text) <= 900  # 약간의 여유

    def test_metadata_preserved(self) -> None:
        """청크 메타데이터에 법령 정보가 포함."""
        parsed = _make_parsed([_make_article("3", "내용", "제목")])
        chunks = chunk_law(parsed)
        meta = chunks[0].metadata
        assert meta["law_name"] == "테스트법"
        assert meta["article_no"] == "3"
        assert meta["source_type"] == "law"
        assert meta["is_active"] is True

    def test_empty_articles(self) -> None:
        """조문이 없으면 빈 리스트."""
        parsed = _make_parsed([])
        chunks = chunk_law(parsed)
        assert chunks == []
