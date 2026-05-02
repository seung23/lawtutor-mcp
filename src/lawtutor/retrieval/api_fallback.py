"""API 폴백 모듈.

DB에 없는 판례/헌재결정례를 국가법령정보센터 API에서 실시간으로 조회한다.
fetch_case_by_number 도구에서 DB 조회 실패 시 사용한다.
"""

import asyncio
import re

import httpx
from lxml import etree

import structlog

from lawtutor.config import settings
from lawtutor.constants import (
    LAW_API_BASE_URL,
    LAW_API_SEARCH_PATH,
    LAW_API_SERVICE_PATH,
    API_RESPONSE_TYPE,
    TARGET_PREC,
    TARGET_DETC,
)

logger = structlog.get_logger()


def _clean_text(text: str | None) -> str:
    """CDATA, HTML 태그, 다중 공백 정리."""
    if not text:
        return ""
    text = text.strip()
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _detect_target(case_no: str) -> str | None:
    """사건번호 패턴으로 판례/헌재결정례를 구분한다."""
    if re.search(r"헌[마바가나라]", case_no):
        return TARGET_DETC
    if re.search(r"[다두누구부]", case_no):
        return TARGET_PREC
    return None


def _api_request_sync(path: str, params: dict) -> bytes | None:
    """국가법령정보센터 API에 동기 요청을 보낸다."""
    params = {**params, "OC": settings.law_go_kr_oc, "type": API_RESPONSE_TYPE}
    try:
        with httpx.Client(base_url=LAW_API_BASE_URL, timeout=15.0) as client:
            response = client.get(path, params=params)
            response.raise_for_status()
            return response.content
    except Exception as e:
        logger.warning("api_fallback_request_failed", error=str(e))
        return None


def _parse_prec_xml(raw: bytes) -> list[dict]:
    """판례 API 응답 XML을 파싱하여 결과로 변환한다."""
    try:
        root = etree.fromstring(raw)
    except etree.XMLSyntaxError:
        return []

    if root.tag == "PrecService":
        # 상세 조회 응답
        case_id = root.findtext("판례정보일련번호", "")
        if not case_id:
            return []
        payload = {
            "source_type": "precedent",
            "case_id": case_id,
            "case_no": root.findtext("사건번호", ""),
            "case_name": _clean_text(root.findtext("사건명")),
            "court": root.findtext("법원명", ""),
            "case_type": root.findtext("사건종류명", ""),
            "judgment_date": root.findtext("선고일자", ""),
            "judgment_type": root.findtext("판결유형", ""),
            "holding": _clean_text(root.findtext("판시사항")),
            "summary": _clean_text(root.findtext("판결요지")),
            "reasoning": _clean_text(root.findtext("판례내용")),
            "referenced_articles": _clean_text(root.findtext("참조조문")),
            "referenced_cases": _clean_text(root.findtext("참조판례")),
        }
        # 섹션별로 청크 분리
        results = []
        for section_key, section_name in [
            ("holding", "판시사항"),
            ("summary", "판결요지"),
            ("reasoning", "판례내용"),
        ]:
            text = payload.get(section_key, "")
            if text:
                header = f"[{payload['court']}] [{payload['judgment_date']}] [{payload['case_no']}] {payload['case_name']}"
                chunk_payload = {
                    **{k: v for k, v in payload.items() if k not in ("holding", "summary", "reasoning")},
                    "chunk_type": section_key,
                    "text": f"{header}\n\n[{section_name}]\n{text}",
                }
                results.append({"payload": chunk_payload, "score": 1.0})
        return results
    return []


def _parse_detc_xml(raw: bytes) -> list[dict]:
    """헌재결정례 API 응답 XML을 파싱하여 결과로 변환한다."""
    try:
        root = etree.fromstring(raw)
    except etree.XMLSyntaxError:
        return []

    if root.tag == "DetcService":
        decision_id = root.findtext("헌재결정례일련번호", "")
        if not decision_id:
            return []
        payload = {
            "source_type": "decision",
            "decision_id": decision_id,
            "case_no": root.findtext("사건번호", ""),
            "case_name": _clean_text(root.findtext("사건명")),
            "case_type": root.findtext("사건종류명", ""),
            "decision_date": root.findtext("종국일자", ""),
            "holding": _clean_text(root.findtext("판시사항")),
            "summary": _clean_text(root.findtext("결정요지")),
            "full_text": _clean_text(root.findtext("전문")),
            "referenced_articles": _clean_text(root.findtext("참조조문")),
            "referenced_cases": _clean_text(root.findtext("참조판례")),
        }
        results = []
        for section_key, section_name in [
            ("holding", "판시사항"),
            ("summary", "결정요지"),
            ("full_text", "전문"),
        ]:
            text = payload.get(section_key, "")
            if text:
                header = f"[헌법재판소] [{payload['decision_date']}] [{payload['case_no']}] {payload['case_name']}"
                chunk_payload = {
                    **{k: v for k, v in payload.items() if k not in ("holding", "summary", "full_text")},
                    "chunk_type": section_key,
                    "text": f"{header}\n\n[{section_name}]\n{text}",
                }
                results.append({"payload": chunk_payload, "score": 1.0})
        return results
    return []


def fetch_case_from_api(case_no: str) -> list[dict]:
    """사건번호로 국가법령정보센터 API에서 판례/결정례를 실시간 조회한다.

    Args:
        case_no: 사건번호 (예: "95다38677", "2018헌마123")

    Returns:
        검색 결과 리스트. 못 찾으면 빈 리스트.
    """
    target = _detect_target(case_no)
    if not target:
        # 양쪽 다 시도
        for t in [TARGET_PREC, TARGET_DETC]:
            results = _search_and_fetch(case_no, t)
            if results:
                return results
        return []

    return _search_and_fetch(case_no, target)


def _search_and_fetch(case_no: str, target: str) -> list[dict]:
    """특정 타겟에서 사건번호로 검색 후 상세 조회한다."""
    logger.info("api_fallback_search", case_no=case_no, target=target)

    # 1단계: 사건번호로 검색
    raw = _api_request_sync(LAW_API_SEARCH_PATH, {
        "target": target,
        "query": case_no,
        "display": 5,
        "page": 1,
    })
    if not raw:
        return []

    try:
        root = etree.fromstring(raw)
    except etree.XMLSyntaxError:
        return []

    # 검색 결과에서 사건번호가 일치하는 항목 찾기
    tag_map = {"prec": "prec", "detc": "detc"}
    id_field_map = {"prec": "판례일련번호", "detc": "헌재결정례일련번호"}
    case_no_field = "사건번호"

    item_tag = tag_map.get(target, target)
    id_field = id_field_map.get(target, "")

    matched_id = None
    for item in root.findall(item_tag):
        item_case_no = item.findtext(case_no_field, "")
        if case_no in item_case_no or item_case_no in case_no:
            matched_id = item.findtext(id_field, "")
            break

    if not matched_id:
        # 정확 매칭 실패 시 첫 번째 결과라도 사용
        items = root.findall(item_tag)
        if items:
            matched_id = items[0].findtext(id_field, "")

    if not matched_id:
        logger.info("api_fallback_not_found", case_no=case_no, target=target)
        return []

    # 2단계: 상세 조회
    logger.info("api_fallback_detail", case_no=case_no, item_id=matched_id)
    detail_raw = _api_request_sync(LAW_API_SERVICE_PATH, {
        "target": target,
        "ID": matched_id,
    })
    if not detail_raw:
        return []

    if target == TARGET_PREC:
        return _parse_prec_xml(detail_raw)
    elif target == TARGET_DETC:
        return _parse_detc_xml(detail_raw)
    return []
