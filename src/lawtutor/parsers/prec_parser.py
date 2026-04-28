"""판례 raw XML → Pydantic 모델 파서."""

import re
from pathlib import Path

from lxml import etree

from lawtutor.models.precedent import Precedent


def _clean_text(text: str | None) -> str:
    """CDATA, HTML 태그, 다중 공백 정리."""
    if not text:
        return ""
    text = text.strip()
    # <br/> 등 HTML 태그를 줄바꿈으로 변환
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    # 연속 줄바꿈 정리
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def parse_precedent_detail(xml_path: Path) -> Precedent | None:
    """판례 상세 XML 파일을 파싱한다.

    Args:
        xml_path: raw XML 파일 경로

    Returns:
        Precedent 모델, 파싱 실패 시 None
    """
    raw = xml_path.read_bytes()
    try:
        root = etree.fromstring(raw)
    except etree.XMLSyntaxError:
        return None

    if root.tag != "PrecService":
        return None

    case_id = root.findtext("판례정보일련번호", "")
    if not case_id:
        return None

    return Precedent(
        case_id=case_id,
        case_no=root.findtext("사건번호", ""),
        case_name=_clean_text(root.findtext("사건명")),
        court=root.findtext("법원명", ""),
        court_type_code=root.findtext("법원종류코드", ""),
        case_type=root.findtext("사건종류명", ""),
        judgment_date=root.findtext("선고일자", ""),
        judgment_type=root.findtext("판결유형", ""),
        holding=_clean_text(root.findtext("판시사항")),
        summary=_clean_text(root.findtext("판결요지")),
        reasoning=_clean_text(root.findtext("판례내용")),
        referenced_articles=_clean_text(root.findtext("참조조문")),
        referenced_cases=_clean_text(root.findtext("참조판례")),
    )
