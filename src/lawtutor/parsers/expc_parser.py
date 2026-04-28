"""법령해석례 raw XML → Pydantic 모델 파서."""

import re
from pathlib import Path

from lxml import etree

from lawtutor.models.interpretation import LegalInterpretation


def _clean_text(text: str | None) -> str:
    """CDATA, HTML 태그, 다중 공백 정리."""
    if not text:
        return ""
    text = text.strip()
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def parse_interpretation_detail(xml_path: Path) -> LegalInterpretation | None:
    """법령해석례 상세 XML 파일을 파싱한다.

    Args:
        xml_path: raw XML 파일 경로

    Returns:
        LegalInterpretation 모델, 파싱 실패 시 None
    """
    raw = xml_path.read_bytes()
    try:
        root = etree.fromstring(raw)
    except etree.XMLSyntaxError:
        return None

    if root.tag != "ExpcService":
        return None

    interp_id = root.findtext("법령해석례일련번호", "")
    if not interp_id:
        return None

    return LegalInterpretation(
        interpretation_id=interp_id,
        title=_clean_text(root.findtext("안건명")),
        case_no=root.findtext("안건번호", ""),
        interpretation_date=root.findtext("해석일자", ""),
        interpreting_agency=root.findtext("해석기관명", ""),
        requesting_agency=root.findtext("질의기관명", ""),
        question=_clean_text(root.findtext("질의요지")),
        answer=_clean_text(root.findtext("회답")),
        reasoning=_clean_text(root.findtext("이유")),
    )
