"""API 폴백 모듈.

DB에 없는 법령/판례/헌재결정례/법령해석례를 국가법령정보센터 API에서 실시간 조회한다.
모든 MCP 도구에서 DB 조회 실패 시 사용한다.
"""

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
    TARGET_LAW,
    TARGET_PREC,
    TARGET_DETC,
    TARGET_EXPC,
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


# ===========================================================================
# 법령 조문 API 폴백
# ===========================================================================

def _normalize_article_no(article_no: str) -> str:
    """조문번호에서 '제', '조' 등을 제거하여 숫자만 남긴다."""
    return re.sub(r"[제조\s]", "", article_no).strip()


def _extract_article_text(article_el: etree._Element) -> str:
    """조문단위 엘리먼트에서 전체 텍스트를 추출한다."""
    parts: list[str] = []

    content = article_el.findtext("조문내용")
    if content:
        parts.append(_clean_text(content))

    for hang in article_el.findall("항"):
        hang_content = _clean_text(hang.findtext("항내용"))
        if hang_content:
            parts.append(hang_content)

        for ho in hang.findall("호"):
            ho_content = _clean_text(ho.findtext("호내용"))
            if ho_content:
                parts.append(f"  {ho_content}")
            for mok in ho.findall("목"):
                mok_content = _clean_text(mok.findtext("목내용"))
                if mok_content:
                    parts.append(f"    {mok_content}")

    return "\n".join(parts)


def _search_law_mst(law_name: str) -> str | None:
    """법령명으로 검색하여 법령일련번호(MST)를 반환한다."""
    raw = _api_request_sync(LAW_API_SEARCH_PATH, {
        "target": TARGET_LAW,
        "query": law_name,
        "display": 10,
        "page": 1,
    })
    if not raw:
        return None

    try:
        root = etree.fromstring(raw)
    except etree.XMLSyntaxError:
        return None

    # 정확 매칭 우선
    for item in root.findall("law"):
        api_name = item.findtext("법령명한글", "")
        if api_name == law_name:
            return item.findtext("법령일련번호", "") or None

    # 부분 매칭
    for item in root.findall("law"):
        api_name = item.findtext("법령명한글", "")
        if law_name in api_name or api_name in law_name:
            return item.findtext("법령일련번호", "") or None

    # 첫 번째 결과
    items = root.findall("law")
    if items:
        return items[0].findtext("법령일련번호", "") or None

    return None


def fetch_article_from_api(law_name: str, article_no: str) -> list[dict]:
    """법령명 + 조문번호로 국가법령정보센터 API에서 조문을 실시간 조회한다.

    Args:
        law_name: 법령명 (예: "행정절차법", "국가배상법")
        article_no: 조문번호 (예: "21", "2")

    Returns:
        검색 결과 리스트. 못 찾으면 빈 리스트.
    """
    logger.info("api_fallback_article", law_name=law_name, article_no=article_no)

    # 1단계: 법령 MST 찾기
    mst = _search_law_mst(law_name)
    if not mst:
        logger.info("api_fallback_law_not_found", law_name=law_name)
        return []

    # 2단계: 법령 상세 조회
    detail_raw = _api_request_sync(LAW_API_SERVICE_PATH, {
        "target": TARGET_LAW,
        "MST": mst,
    })
    if not detail_raw:
        return []

    try:
        root = etree.fromstring(detail_raw)
    except etree.XMLSyntaxError:
        return []

    if root.tag != "법령":
        return []

    info = root.find("기본정보")
    if info is None:
        return []

    api_law_name = _clean_text(info.findtext("법령명_한글"))
    effective_date = info.findtext("시행일자", "")
    normalized_target = _normalize_article_no(article_no)

    # 3단계: 해당 조문 찾기
    results = []
    for article_el in root.findall(".//조문단위"):
        if article_el.findtext("조문여부") != "조문":
            continue
        el_no = _clean_text(article_el.findtext("조문번호"))
        if not el_no:
            continue
        if _normalize_article_no(el_no) == normalized_target:
            article_title = _clean_text(article_el.findtext("조문제목"))
            article_text = _extract_article_text(article_el)

            header = f"[{api_law_name}] 제{el_no}조"
            if article_title:
                header += f"({article_title})"

            payload = {
                "source_type": "law",
                "law_mst": mst,
                "law_name": api_law_name,
                "article_no": el_no,
                "article_title": article_title,
                "effective_date": effective_date,
                "is_active": True,
                "text": f"{header}\n\n{article_text}",
            }
            results.append({"payload": payload, "score": 1.0})

    if not results:
        logger.info("api_fallback_article_not_found",
                     law_name=law_name, article_no=article_no)

    return results


# ===========================================================================
# search_* API 폴백 (키워드 검색)
# ===========================================================================

def _fetch_details_batch(
    target: str,
    item_ids: list[str],
    parser_fn,
    max_items: int = 3,
) -> list[dict]:
    """여러 건의 상세 정보를 일괄 조회한다."""
    results: list[dict] = []
    for item_id in item_ids[:max_items]:
        detail_raw = _api_request_sync(LAW_API_SERVICE_PATH, {
            "target": target,
            "ID": item_id,
        })
        if detail_raw:
            results.extend(parser_fn(detail_raw))
    return results


def search_precedents_from_api(query: str, top_k: int = 3) -> list[dict]:
    """키워드로 판례를 API 검색한다.

    Args:
        query: 검색 쿼리
        top_k: 최대 결과 수

    Returns:
        검색 결과 리스트.
    """
    logger.info("api_fallback_search_prec", query=query)
    raw = _api_request_sync(LAW_API_SEARCH_PATH, {
        "target": TARGET_PREC,
        "query": query,
        "display": min(top_k, 5),
        "page": 1,
    })
    if not raw:
        return []

    try:
        root = etree.fromstring(raw)
    except etree.XMLSyntaxError:
        return []

    item_ids = [
        item.findtext("판례일련번호", "")
        for item in root.findall("prec")
        if item.findtext("판례일련번호", "")
    ]

    return _fetch_details_batch(TARGET_PREC, item_ids, _parse_prec_xml, max_items=min(top_k, 3))


def search_decisions_from_api(query: str, top_k: int = 3) -> list[dict]:
    """키워드로 헌재결정례를 API 검색한다.

    Args:
        query: 검색 쿼리
        top_k: 최대 결과 수

    Returns:
        검색 결과 리스트.
    """
    logger.info("api_fallback_search_detc", query=query)
    raw = _api_request_sync(LAW_API_SEARCH_PATH, {
        "target": TARGET_DETC,
        "query": query,
        "display": min(top_k, 5),
        "page": 1,
    })
    if not raw:
        return []

    try:
        root = etree.fromstring(raw)
    except etree.XMLSyntaxError:
        return []

    item_ids = [
        item.findtext("헌재결정례일련번호", "")
        for item in root.findall("detc")
        if item.findtext("헌재결정례일련번호", "")
    ]

    return _fetch_details_batch(TARGET_DETC, item_ids, _parse_detc_xml, max_items=min(top_k, 3))


def _parse_expc_xml(raw: bytes) -> list[dict]:
    """법령해석례 API 응답 XML을 파싱하여 결과로 변환한다."""
    try:
        root = etree.fromstring(raw)
    except etree.XMLSyntaxError:
        return []

    if root.tag != "ExpcService":
        return []

    interp_id = root.findtext("법령해석례일련번호", "")
    if not interp_id:
        return []

    title = _clean_text(root.findtext("안건명"))
    case_no = root.findtext("안건번호", "")
    interp_date = root.findtext("해석일자", "")
    question = _clean_text(root.findtext("질의요지"))
    answer = _clean_text(root.findtext("회답"))
    reasoning = _clean_text(root.findtext("이유"))

    header = f"[법령해석례] [{interp_date}] [{case_no}] {title}"

    sections: list[tuple[str, str, str]] = []
    if question:
        sections.append(("question", "질의요지", question))
    if answer:
        sections.append(("answer", "회답", answer))
    if reasoning:
        sections.append(("reasoning", "이유", reasoning))

    results = []
    for section_key, section_name, text in sections:
        chunk_payload = {
            "source_type": "interpretation",
            "interpretation_id": interp_id,
            "title": title,
            "case_no": case_no,
            "interpretation_date": interp_date,
            "chunk_type": section_key,
            "text": f"{header}\n\n[{section_name}]\n{text}",
        }
        results.append({"payload": chunk_payload, "score": 1.0})

    return results


def search_interpretations_from_api(query: str, top_k: int = 3) -> list[dict]:
    """키워드로 법령해석례를 API 검색한다.

    Args:
        query: 검색 쿼리
        top_k: 최대 결과 수

    Returns:
        검색 결과 리스트.
    """
    logger.info("api_fallback_search_expc", query=query)
    raw = _api_request_sync(LAW_API_SEARCH_PATH, {
        "target": TARGET_EXPC,
        "query": query,
        "display": min(top_k, 5),
        "page": 1,
    })
    if not raw:
        return []

    try:
        root = etree.fromstring(raw)
    except etree.XMLSyntaxError:
        return []

    item_ids = [
        item.findtext("법령해석례일련번호", "")
        for item in root.findall("expc")
        if item.findtext("법령해석례일련번호", "")
    ]

    return _fetch_details_batch(TARGET_EXPC, item_ids, _parse_expc_xml, max_items=min(top_k, 3))


def search_laws_from_api(
    query: str,
    top_k: int = 5,
    law_name_filter: str | None = None,
) -> list[dict]:
    """키워드로 법령 조문을 API 검색한다.

    법령명 필터가 있으면 해당 법령의 전 조문을 가져와 키워드 매칭한다.
    필터가 없으면 검색 결과 상위 법령들의 조문에서 키워드 매칭한다.

    Args:
        query: 검색 쿼리
        top_k: 최대 결과 수
        law_name_filter: 특정 법령명 필터

    Returns:
        검색 결과 리스트.
    """
    logger.info("api_fallback_search_law", query=query, law_name_filter=law_name_filter)

    search_query = law_name_filter or query
    raw = _api_request_sync(LAW_API_SEARCH_PATH, {
        "target": TARGET_LAW,
        "query": search_query,
        "display": 5,
        "page": 1,
    })
    if not raw:
        return []

    try:
        root = etree.fromstring(raw)
    except etree.XMLSyntaxError:
        return []

    mst_list = [
        item.findtext("법령일련번호", "")
        for item in root.findall("law")
        if item.findtext("법령일련번호", "")
    ]

    results: list[dict] = []
    query_keywords = query.split()

    for mst in mst_list[:2]:
        detail_raw = _api_request_sync(LAW_API_SERVICE_PATH, {
            "target": TARGET_LAW,
            "MST": mst,
        })
        if not detail_raw:
            continue

        try:
            law_root = etree.fromstring(detail_raw)
        except etree.XMLSyntaxError:
            continue

        if law_root.tag != "법령":
            continue

        info = law_root.find("기본정보")
        if info is None:
            continue

        api_law_name = _clean_text(info.findtext("법령명_한글"))
        effective_date = info.findtext("시행일자", "")

        for article_el in law_root.findall(".//조문단위"):
            if article_el.findtext("조문여부") != "조문":
                continue

            el_no = _clean_text(article_el.findtext("조문번호"))
            if not el_no:
                continue

            article_title = _clean_text(article_el.findtext("조문제목"))
            article_text = _extract_article_text(article_el)
            full_text = f"{article_title} {article_text}"

            # 키워드 매칭: 하나라도 포함되면 결과에 추가
            if any(kw in full_text for kw in query_keywords):
                header = f"[{api_law_name}] 제{el_no}조"
                if article_title:
                    header += f"({article_title})"

                payload = {
                    "source_type": "law",
                    "law_mst": mst,
                    "law_name": api_law_name,
                    "article_no": el_no,
                    "article_title": article_title,
                    "effective_date": effective_date,
                    "is_active": True,
                    "text": f"{header}\n\n{article_text}",
                }
                results.append({"payload": payload, "score": 0.8})

            if len(results) >= top_k:
                break

        if len(results) >= top_k:
            break

    return results[:top_k]
