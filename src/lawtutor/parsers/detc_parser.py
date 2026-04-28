"""헌재결정례 raw XML → Pydantic 모델 파서."""

import re
from pathlib import Path

from lxml import etree

from lawtutor.models.decision import ConstitutionalDecision


def _clean_text(text: str | None) -> str:
    """CDATA, HTML 태그, 다중 공백 정리."""
    if not text:
        return ""
    text = text.strip()
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def parse_decision_detail(xml_path: Path) -> ConstitutionalDecision | None:
    """헌재결정례 상세 XML 파일을 파싱한다.

    Args:
        xml_path: raw XML 파일 경로

    Returns:
        ConstitutionalDecision 모델, 파싱 실패 시 None
    """
    raw = xml_path.read_bytes()
    try:
        root = etree.fromstring(raw)
    except etree.XMLSyntaxError:
        return None

    if root.tag != "DetcService":
        return None

    decision_id = root.findtext("헌재결정례일련번호", "")
    if not decision_id:
        return None

    return ConstitutionalDecision(
        decision_id=decision_id,
        case_no=root.findtext("사건번호", ""),
        case_name=_clean_text(root.findtext("사건명")),
        case_type=root.findtext("사건종류명", ""),
        case_type_code=root.findtext("사건종류코드", ""),
        decision_date=root.findtext("종국일자", ""),
        holding=_clean_text(root.findtext("판시사항")),
        summary=_clean_text(root.findtext("결정요지")),
        full_text=_clean_text(root.findtext("전문")),
        referenced_articles=_clean_text(root.findtext("참조조문")),
        referenced_cases=_clean_text(root.findtext("참조판례")),
        review_target=_clean_text(root.findtext("심판대상조문")),
    )
