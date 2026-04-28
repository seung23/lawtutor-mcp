"""법령 raw XML → Pydantic 모델 파서.

data/raw/law/ 의 detail XML을 파싱하여 ParsedLaw 모델로 변환한다.
"""

import re
from pathlib import Path

from lxml import etree

from lawtutor.models.law import LawArticle, LawMeta, ParsedLaw


def _clean_text(text: str | None) -> str:
    """CDATA, 다중 공백, 앞뒤 공백을 정리한다."""
    if not text:
        return ""
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    return text


def _extract_full_article_text(article_el: etree._Element) -> str:
    """조문단위 엘리먼트에서 조문 전체 텍스트를 추출한다.

    조문내용 + 항/호/목을 계층 구조 그대로 텍스트로 조합한다.

    Args:
        article_el: 조문단위 XML 엘리먼트

    Returns:
        조문 전체 텍스트
    """
    parts: list[str] = []

    content = article_el.findtext("조문내용")
    if content:
        parts.append(_clean_text(content))

    # 항 처리
    for hang in article_el.findall("항"):
        hang_no = _clean_text(hang.findtext("항번호"))
        hang_content = _clean_text(hang.findtext("항내용"))
        if hang_content:
            parts.append(hang_content)
        elif hang_no:
            parts.append(hang_no)

        # 호 처리
        for ho in hang.findall("호"):
            ho_content = _clean_text(ho.findtext("호내용"))
            if ho_content:
                parts.append(f"  {ho_content}")

            # 목 처리
            for mok in ho.findall("목"):
                mok_content = _clean_text(mok.findtext("목내용"))
                if mok_content:
                    parts.append(f"    {mok_content}")

    # 조문참고자료
    ref = article_el.findtext("조문참고자료")
    if ref:
        cleaned = _clean_text(ref)
        if cleaned:
            parts.append(cleaned)

    return "\n".join(parts)


def parse_law_detail(xml_path: Path, mst: str = "") -> ParsedLaw | None:
    """법령 상세 XML 파일을 파싱한다.

    Args:
        xml_path: raw XML 파일 경로
        mst: 법령일련번호 (파일명에서 추출 가능)

    Returns:
        ParsedLaw 모델, 파싱 실패 시 None
    """
    raw = xml_path.read_bytes()
    try:
        root = etree.fromstring(raw)
    except etree.XMLSyntaxError:
        return None

    # 루트 태그가 '법령'이 아니면 에러 응답
    if root.tag != "법령":
        return None

    info = root.find("기본정보")
    if info is None:
        return None

    # 메타데이터
    law_id = info.findtext("법령ID", "")
    law_name = _clean_text(info.findtext("법령명_한글"))
    effective_date = info.findtext("시행일자", "")

    # 법종구분 (속성에 있을 수도 있음)
    law_type_el = info.find("법종구분")
    law_type = _clean_text(law_type_el.text) if law_type_el is not None else ""

    ministry_el = info.find("소관부처")
    ministry = _clean_text(ministry_el.text) if ministry_el is not None else ""

    if not mst:
        mst = xml_path.stem.replace("detail_", "")

    meta = LawMeta(
        law_id=law_id,
        law_mst=mst,
        law_name=law_name,
        law_type=law_type,
        ministry=ministry,
        effective_date=effective_date,
        promulgation_date=info.findtext("공포일자", ""),
        promulgation_no=info.findtext("공포번호", ""),
        is_active=True,  # 수집 시점 기준 현행
        revision_type=_clean_text(info.findtext("제개정구분")),
    )

    # 조문 파싱 (조문여부 == "조문"인 것만)
    articles: list[LawArticle] = []
    for article_el in root.findall(".//조문단위"):
        if article_el.findtext("조문여부") != "조문":
            continue

        article_no = _clean_text(article_el.findtext("조문번호"))
        if not article_no:
            continue

        article_text = _extract_full_article_text(article_el)
        if not article_text:
            continue

        article_eff = article_el.findtext("조문시행일자", effective_date)

        articles.append(LawArticle(
            law_id=law_id,
            law_mst=mst,
            law_name=law_name,
            law_type=law_type,
            ministry=ministry,
            article_no=article_no,
            article_title=_clean_text(article_el.findtext("조문제목")),
            article_content=article_text,
            effective_date=article_eff,
            promulgation_date=meta.promulgation_date,
            promulgation_no=meta.promulgation_no,
            is_active=True,
            revision_type=meta.revision_type,
        ))

    return ParsedLaw(meta=meta, articles=articles)
