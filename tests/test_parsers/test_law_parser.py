"""law_parser 단위 테스트."""

import pytest
from pathlib import Path

from lawtutor.parsers.law_parser import parse_law_detail, _clean_text, _extract_full_article_text


class TestCleanText:
    """텍스트 정리 함수 테스트."""

    def test_none(self) -> None:
        assert _clean_text(None) == ""

    def test_empty(self) -> None:
        assert _clean_text("") == ""

    def test_strips_whitespace(self) -> None:
        assert _clean_text("  hello  ") == "hello"

    def test_collapses_spaces(self) -> None:
        assert _clean_text("a   b    c") == "a b c"


class TestParseLawDetail:
    """parse_law_detail 테스트."""

    def test_invalid_xml(self, tmp_path: Path) -> None:
        """잘못된 XML은 None 반환."""
        bad = tmp_path / "bad.xml"
        bad.write_bytes(b"not xml")
        assert parse_law_detail(bad) is None

    def test_wrong_root_tag(self, tmp_path: Path) -> None:
        """루트 태그가 '법령'이 아니면 None."""
        wrong = tmp_path / "wrong.xml"
        wrong.write_bytes(b'<?xml version="1.0"?><Response><result>error</result></Response>')
        assert parse_law_detail(wrong) is None

    def test_minimal_law(self, tmp_path: Path) -> None:
        """최소한의 법령 XML 파싱."""
        xml = tmp_path / "detail_999.xml"
        xml.write_bytes("""<?xml version="1.0" encoding="UTF-8"?>
<법령 법령키="test">
<기본정보>
<법령ID>999</법령ID>
<법령명_한글>테스트법</법령명_한글>
<시행일자>20240101</시행일자>
<공포일자>20231201</공포일자>
<공포번호>12345</공포번호>
<제개정구분>제정</제개정구분>
</기본정보>
<조문>
<조문단위>
<조문번호>1</조문번호>
<조문여부>조문</조문여부>
<조문제목>목적</조문제목>
<조문시행일자>20240101</조문시행일자>
<조문내용>제1조(목적) 이 법은 테스트를 목적으로 한다.</조문내용>
</조문단위>
<조문단위>
<조문번호>1</조문번호>
<조문여부>전문</조문여부>
<조문내용>제1장 총칙</조문내용>
</조문단위>
</조문>
</법령>""".encode("utf-8"))

        result = parse_law_detail(xml)
        assert result is not None
        assert result.meta.law_name == "테스트법"
        assert result.meta.law_id == "999"
        assert len(result.articles) == 1  # '전문'은 제외
        assert result.articles[0].article_no == "1"
        assert result.articles[0].article_title == "목적"
        assert "테스트를 목적으로" in result.articles[0].article_content
