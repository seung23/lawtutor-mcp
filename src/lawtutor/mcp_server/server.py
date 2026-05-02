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
    """Search Korean administrative/constitutional law articles and statutes (법령 조문 검색).

    Use this tool when the user asks about:
    - Legal provisions, statutes, or articles (법령, 조문, 법조문)
    - Legal concepts like "처분", "사전통지", "행정행위", "국가배상", "행정심판"
    - Which law applies to a specific situation
    - Comparing provisions across different laws (e.g. 헌법 vs 국가배상법)

    Covers: 행정절차법, 행정소송법, 행정심판법, 국가배상법, 행정기본법, 행정대집행법,
    정보공개법, 질서위반행위규제법, 정부조직법, 대한민국헌법 (+ 시행령/시행규칙)

    For court cases use search_precedent, for Constitutional Court use search_constitutional_decision.

    Args:
        query: Natural language search query (Korean). e.g. "국가배상청구권 요건", "처분의 사전통지"
        top_k: Number of results to return (default 5)
        law_name_filter: Filter by specific law name (e.g. "국가배상법", "행정절차법")
        include_historical: If True, include repealed/amended articles (default False)
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
    """Search Korean Supreme Court precedents / case law on administrative law (판례 검색).

    Use this tool when the user asks about:
    - Court cases, precedents, rulings, judgments (판례, 판결, 대법원)
    - Legal principles established by courts (판시사항, 판결요지)
    - Case-based legal analysis ("이 경우 관련 판례가 있나?")
    - Comparing court decisions
    - Specific legal issues like 국가배상, 처분성, 행정소송, 공무원 책임
    - Real-world legal scenarios that need case law support

    Returns case chunks with: 판시사항 (holdings), 판결요지 (summary), 이유 (reasoning),
    plus metadata (사건번호, 법원, 선고일).

    Args:
        query: Natural language search query (Korean). e.g. "국가배상 군인연금 사망보상금", "공무원 자가용 직무수행 배상책임"
        top_k: Number of results to return (default 5)
        court_filter: Filter by court name (e.g. "대법원")
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
    """Search Korean Constitutional Court decisions (헌법재판소 결정례 검색).

    Use this tool when the user asks about:
    - Constitutional Court decisions (헌재결정, 헌법재판소)
    - Constitutionality reviews (위헌, 합헌, 헌법불합치)
    - Fundamental rights (기본권) issues
    - Constitutional complaints (헌법소원)

    Returns decision chunks with: 판시사항, 결정요지, 전문 + metadata.

    Args:
        query: Natural language search query (Korean). e.g. "기본권 침해 판단 기준", "위헌심사 비례원칙"
        top_k: Number of results to return (default 5)
        case_type_filter: Case type filter (e.g. "헌마", "헌바", "헌가")
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
    """Search official legal interpretations by the Ministry of Government Legislation (법제처 유권해석례 검색).

    Use this tool when the user asks about:
    - Practical application of legal provisions (실무 적용, 유권해석)
    - Ambiguous legal provisions that need authoritative interpretation
    - How government agencies should apply specific laws

    Returns interpretation chunks with: 질의요지, 회답, 이유 + metadata.

    Args:
        query: Natural language search query (Korean). e.g. "행정절차법 처분 사전통지 실무 적용"
        top_k: Number of results to return (default 5)
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
    """Fetch exact law article by law name and article number (조문번호로 정확한 조문 직접 조회).

    Use this tool when:
    - The user specifies an exact article number: "행정절차법 제21조", "국가배상법 제2조", "헌법 제29조"
    - You need the full original text of a specific provision
    - Comparing specific articles across different laws

    This is a direct lookup (no vector search), so it's fast and precise.

    Args:
        law_name: Name of the law (e.g. "행정절차법", "국가배상법", "대한민국헌법")
        article_no: Article number as string (e.g. "21", "2", "29")
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
    """Fetch exact court case by case number (사건번호로 판례/헌재결정례 직접 조회).

    Use this tool when:
    - The user specifies a case number: "95다38677", "2018두12345", "2018헌마123"
    - You need the full text of a specific court decision
    - Any reference to a Korean case number format (YY/YYYY + 다/두/헌마/헌바/헌가 + digits)

    This is a direct lookup (no vector search). Searches both Supreme Court precedents
    and Constitutional Court decisions.

    Args:
        case_no: Korean case number (e.g. "95다38677", "2018두12345", "2018헌마123")
    """
    start = time.time()
    retriever = get_retriever()
    raw = retriever.fetch_by_case_no(case_no)
    return format_results(
        raw, case_no, ["precedents", "decisions"],
        {"case_no": case_no}, start,
    ).model_dump()
