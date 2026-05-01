"""LawTutor MCP 서버.

FastMCP를 사용하여 6개 검색 도구를 제공한다.
본 서버는 LLM이 아니다. 검색 결과를 구조화된 형태로 반환만 한다.
"""

import time

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from lawtutor.constants import MCP_SERVER_NAME, SEARCH_DEFAULT_TOP_K
from lawtutor.embeddings.bge_m3 import BgeM3Embedder
from lawtutor.retrieval.formatter import format_results
from lawtutor.retrieval.retriever import Retriever
from lawtutor.vector_store.client import VectorStore

# 싱글턴 인스턴스 (서버 기동 시 한 번만 생성)
_embedder: BgeM3Embedder | None = None
_retriever: Retriever | None = None


def get_retriever() -> Retriever:
    """Retriever 싱글턴을 반환한다."""
    global _embedder, _retriever
    if _retriever is None:
        _embedder = BgeM3Embedder()
        _store = VectorStore()
        _retriever = Retriever(_embedder, _store)
    return _retriever


# FastMCP 인스턴스
mcp = FastMCP(
    MCP_SERVER_NAME,
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=["lawtutor.dev", "localhost", "127.0.0.1"],
    ),
)


# ---------------------------------------------------------------------------
# Tool 1: search_law
# ---------------------------------------------------------------------------
@mcp.tool()
def search_law(
    query: str,
    top_k: int = SEARCH_DEFAULT_TOP_K,
    law_name_filter: str | None = None,
    include_historical: bool = False,
) -> dict:
    """한국 행정법/헌법 법령 조문을 RAG로 검색합니다.

    [사용 시점]
    - 사용자가 특정 법령의 조문 내용을 묻는 경우 ("행정절차법 제21조에 대해")
    - 법령 개념을 묻는 경우 ("처분의 사전통지란?")
    - 사례형 적용 질문 ("이 경우 어떤 조문이 적용되나?")

    [반환]
    top_k 개의 조문 청크. 각 청크는 본문 + 메타데이터(법령명, 조문번호, 시행일, 현행 여부 등).

    [참고]
    판례 질문에는 search_precedent를, 헌재결정례에는 search_constitutional_decision을 사용하세요.

    Args:
        query: 검색 쿼리
        top_k: 반환할 결과 수 (기본 5)
        law_name_filter: 특정 법령명으로 한정 (예: "행정절차법")
        include_historical: True이면 폐지/개정 조문도 포함 (기본 False)
    """
    start = time.time()
    retriever = get_retriever()
    raw = retriever.search_laws(query, top_k, law_name_filter, include_historical)

    filters = {}
    if not include_historical:
        filters["is_active"] = True
    if law_name_filter:
        filters["law_name"] = law_name_filter

    return format_results(raw, query, ["laws"], filters, start).model_dump()


# ---------------------------------------------------------------------------
# Tool 2: search_precedent
# ---------------------------------------------------------------------------
@mcp.tool()
def search_precedent(
    query: str,
    top_k: int = SEARCH_DEFAULT_TOP_K,
    court_filter: str | None = None,
) -> dict:
    """한국 행정법 관련 대법원 판례를 검색합니다.

    [사용 시점]
    - 판례 질문 ("처분성이 인정된 판례는?")
    - 판례 비교 질문 ("X판례와 Y판례의 차이는?")
    - 사례 적용 질문 ("이 경우 관련 판례가 있나?")

    [반환]
    top_k 개의 판례 청크. 각 청크는 판시사항/판결요지/이유 중 하나 + 메타데이터(사건번호, 법원, 선고일 등).

    Args:
        query: 검색 쿼리
        top_k: 반환할 결과 수 (기본 5)
        court_filter: 법원명 필터 (예: "대법원")
    """
    start = time.time()
    retriever = get_retriever()
    raw = retriever.search_precedents(query, top_k, court_filter)

    filters = {}
    if court_filter:
        filters["court"] = court_filter

    return format_results(raw, query, ["precedents"], filters, start).model_dump()


# ---------------------------------------------------------------------------
# Tool 3: search_constitutional_decision
# ---------------------------------------------------------------------------
@mcp.tool()
def search_constitutional_decision(
    query: str,
    top_k: int = SEARCH_DEFAULT_TOP_K,
    case_type_filter: str | None = None,
) -> dict:
    """헌법재판소 결정례를 검색합니다.

    [사용 시점]
    - 헌법 질문 ("기본권 침해 여부 판단 기준은?")
    - 위헌/합헌 여부 질문
    - 기본권 사건 검색

    [반환]
    top_k 개의 결정례 청크. 각 청크는 판시사항/결정요지/전문 중 하나 + 메타데이터.

    Args:
        query: 검색 쿼리
        top_k: 반환할 결과 수 (기본 5)
        case_type_filter: 사건종류 필터 (예: "헌마", "헌바")
    """
    start = time.time()
    retriever = get_retriever()
    raw = retriever.search_decisions(query, top_k, case_type_filter)

    filters = {}
    if case_type_filter:
        filters["case_type"] = case_type_filter

    return format_results(raw, query, ["decisions"], filters, start).model_dump()


# ---------------------------------------------------------------------------
# Tool 4: search_legal_interpretation
# ---------------------------------------------------------------------------
@mcp.tool()
def search_legal_interpretation(
    query: str,
    top_k: int = SEARCH_DEFAULT_TOP_K,
) -> dict:
    """정부 부처(법제처)의 법령 유권해석례를 검색합니다.

    [사용 시점]
    - 행정 실무 해석 질문 ("이 조문의 실무 적용은?")
    - 법령 적용이 모호한 영역의 질문

    [반환]
    top_k 개의 해석례 청크. 각 청크는 질의요지/회답/이유 + 메타데이터.

    Args:
        query: 검색 쿼리
        top_k: 반환할 결과 수 (기본 5)
    """
    start = time.time()
    retriever = get_retriever()
    raw = retriever.search_interpretations(query, top_k)
    return format_results(raw, query, ["interpretations"], None, start).model_dump()


# ---------------------------------------------------------------------------
# Tool 5: fetch_article_by_number
# ---------------------------------------------------------------------------
@mcp.tool()
def fetch_article_by_number(
    law_name: str,
    article_no: str,
) -> dict:
    """법령명과 조문번호로 정확한 조문을 직접 조회합니다.

    [사용 시점]
    - 사용자가 조문번호를 알고 있을 때 ("행정절차법 제21조 알려줘")
    - 정확한 조문 원문이 필요할 때

    [반환]
    해당 조문 청크 또는 빈 결과.

    Args:
        law_name: 법령명 (예: "행정절차법")
        article_no: 조문번호 (예: "21")
    """
    start = time.time()
    retriever = get_retriever()
    raw = retriever.fetch_by_article(law_name, article_no)
    return format_results(
        raw, f"{law_name} 제{article_no}조", ["laws"],
        {"law_name": law_name, "article_no": article_no}, start,
    ).model_dump()


# ---------------------------------------------------------------------------
# Tool 6: fetch_case_by_number
# ---------------------------------------------------------------------------
@mcp.tool()
def fetch_case_by_number(
    case_no: str,
) -> dict:
    """사건번호로 정확한 판례 또는 헌재결정례를 직접 조회합니다.

    [사용 시점]
    - 사용자가 사건번호를 알고 있을 때 ("2018두12345 판결 알려줘")
    - 정확한 판례/결정례 원문이 필요할 때

    [반환]
    해당 사건의 모든 청크(판시사항, 판결요지, 이유 등) 또는 빈 결과.

    Args:
        case_no: 사건번호 (예: "2018두12345" 또는 "2018헌마123")
    """
    start = time.time()
    retriever = get_retriever()
    raw = retriever.fetch_by_case_no(case_no)
    return format_results(
        raw, case_no, ["precedents", "decisions"],
        {"case_no": case_no}, start,
    ).model_dump()
