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
    """Search Korean law articles and statutes by semantic similarity (법령 조문 검색).

    USE THIS TOOL WHEN the user:
    - Asks about any legal provision, statute, or article (법령, 조문, 법조문, 규정)
    - Asks whether a specific legal principle is codified ("~에 대한 규정이 있나요?", "~을 명시한 조문")
    - Asks about legal concepts: 처분, 사전통지, 행정행위, 국가배상, 행정심판, 신뢰보호, 비례원칙, 부당결부금지, 평등원칙, 재량권, 기속행위, 공정력, 부관, 행정계획, 확약, 행정지도
    - Wants to know which law governs a situation ("이 경우 어떤 법이 적용되나요?")
    - Asks about requirements/요건, effects/효과, or exceptions/예외 of a legal provision
    - Compares provisions across different laws
    - Asks "~의 근거 규정", "~의 법적 근거", "법에 ~가 있나요?"

    Covers ALL Korean laws including: 행정기본법, 행정절차법, 행정소송법, 행정심판법, 국가배상법,
    행정대집행법, 정보공개법, 질서위반행위규제법, 정부조직법, 대한민국헌법, 국가공무원법,
    지방자치법, 민법, 형법, 각종 시행령/시행규칙 등 5,500+ 법령

    IMPORTANT: When uncertain whether a question needs law search or case search, use BOTH this tool
    AND search_precedent. Legal questions often require both statutory text and case law.

    Args:
        query: Natural language search query (Korean). e.g. "신뢰보호원칙 명시 규정", "국가배상 요건", "처분의 사전통지 의무"
        top_k: Number of results to return (default 5, increase to 10 for broad concepts)
        law_name_filter: Filter by specific law name (e.g. "행정기본법", "국가배상법"). Use when the user mentions a specific law.
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
    """Search Korean Supreme Court precedents and case law (대법원 판례 검색).

    USE THIS TOOL WHEN the user:
    - Asks about court cases, precedents, rulings, judgments (판례, 판결, 대법원, 판례법리)
    - Asks about legal principles established by courts (판시사항, 판결요지)
    - Asks "관련 판례가 있나요?", "판례에서 어떻게 판단했나요?"
    - Asks about how courts interpret a legal concept (처분성, 재량권 일탈남용, 신뢰보호, 비례원칙)
    - Describes a factual scenario and asks about legal outcomes ("이런 경우 위법한가요?")
    - Asks about 국가배상, 손해배상, 취소소송, 무효확인, 부작위위법확인
    - Asks about specific legal disputes or controversies
    - Wants to know how a legal principle applies in practice
    - Asks "~한 경우 판례 입장은?", "대법원은 ~에 대해 어떻게 보나요?"
    - Asks about exam-relevant topics: 처분성 인정/부정 사례, 원고적격, 협의의 소익, 사정판결

    This tool returns only Supreme Court (대법원) cases. For Constitutional Court
    decisions (위헌, 헌법소원), use search_constitutional_decision instead.

    Returns: 판시사항 (holdings), 판결요지 (summary), 판례내용 (reasoning) + metadata.

    Args:
        query: Natural language search query (Korean). e.g. "건축허가 거부처분 재량행위", "공무원 직무상 불법행위 국가배상"
        top_k: Number of results to return (default 5, increase to 10 for broad topics)
        court_filter: Filter by court name (default: "대법원")
    """
    start = time.time()
    retriever = get_retriever()
    # 기본적으로 대법원 판례만 반환 (사용자가 명시적으로 다른 법원 지정 시 해당 법원)
    effective_court_filter = court_filter if court_filter else "대법원"
    raw = retriever.search_precedents(query, top_k, effective_court_filter)

    filters = {"court": effective_court_filter}

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

    USE THIS TOOL WHEN the user:
    - Asks about Constitutional Court decisions (헌재결정, 헌법재판소, 헌재)
    - Asks about constitutionality review (위헌, 합헌, 헌법불합치, 한정합헌, 한정위헌)
    - Asks about fundamental rights issues (기본권 침해, 기본권 제한, 본질적 내용 침해)
    - Asks about constitutional complaints (헌법소원, 권리구제형, 위헌심사형)
    - Asks about constitutional principles: 과잉금지원칙, 비례원칙, 평등원칙, 신뢰보호원칙(헌법적 관점), 적법절차원칙, 명확성원칙, 포괄위임금지원칙
    - Asks about competence disputes (권한쟁의심판)
    - Asks "헌재는 ~에 대해 어떻게 판단했나요?", "~이 위헌인가요?"
    - Asks about 위헌법률심판, 탄핵심판
    - Discusses topics where constitutional vs. statutory interpretation matters

    Covers 37,800+ Constitutional Court decisions. For regular court cases (대법원 등),
    use search_precedent instead.

    Returns: 판시사항, 결정요지, 전문 + metadata (사건번호, 결정일, 사건유형).

    Args:
        query: Natural language search query (Korean). e.g. "직업의 자유 제한 비례원칙", "재산권 본질적 내용 침해"
        top_k: Number of results to return (default 5)
        case_type_filter: Case type (e.g. "헌마" for 헌법소원, "헌바" for 위헌소원, "헌가" for 위헌제청)
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
    """Search official legal interpretations by government agencies (법제처/행안부 등 유권해석례 검색).

    USE THIS TOOL WHEN the user:
    - Asks about practical/real-world application of legal provisions (실무 적용, 유권해석, 행정해석)
    - Asks "이 조문은 실무에서 어떻게 적용되나요?"
    - Asks about ambiguous provisions that need authoritative interpretation
    - Asks how government agencies interpret specific laws ("행정청은 이 조문을 어떻게 해석하나요?")
    - Asks about 질의회신, 법제처 해석, 유권해석
    - Wants to know the official government position on a legal question
    - Asks about specific administrative procedures and their practical requirements

    This differs from precedents (court interpretations) — these are executive branch interpretations
    that guide how laws are actually implemented by agencies.

    Covers 8,700+ interpretations. Returns: 질의요지, 회답, 이유 + metadata.

    Args:
        query: Natural language search query (Korean). e.g. "사전통지 생략 가능한 경우", "영업허가 취소 청문 필요 여부"
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
    """Fetch exact law article text by law name + article number (조문번호로 정확한 조문 원문 조회).

    USE THIS TOOL WHEN the user:
    - Specifies an exact article: "행정절차법 제21조", "국가배상법 제2조", "헌법 제29조"
    - Says "제N조를 보여줘", "N조 원문", "N조 전문"
    - Asks to read/cite a specific provision verbatim
    - Needs the full original text for comparison or analysis
    - References "제N조제N항" (use article number only, paragraphs are included in the result)

    This is a direct lookup (no vector search) — fast, precise, and returns the full article text.
    Use search_law for concept-based searches when article number is unknown.

    Args:
        law_name: Exact law name (e.g. "행정절차법", "국가배상법", "대한민국헌법", "행정기본법")
        article_no: Article number as string without "조" (e.g. "21", "2", "29", "12")
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
    """Fetch exact court case by case number (사건번호로 판례/헌재결정례 원문 직접 조회).

    USE THIS TOOL WHEN the user:
    - Mentions a specific case number: "95다38677", "2018두12345", "2018헌마123"
    - Says "~사건", "~판결 내용", "이 판례 찾아줘"
    - References any Korean case number format: [연도]+[다/두/누/부/헌마/헌바/헌가/헌라]+[번호]
    - Wants the full text (판시사항, 판결요지, 판례내용) of a known case

    This is a direct lookup (no vector search). Searches both Supreme Court precedents
    and Constitutional Court decisions. Use search_precedent or search_constitutional_decision
    when the case number is unknown.

    Args:
        case_no: Korean case number exactly as cited (e.g. "95다38677", "2018두12345", "2018헌마123", "2020헌바95")
    """
    start = time.time()
    retriever = get_retriever()
    raw = retriever.fetch_by_case_no(case_no)
    return format_results(
        raw, case_no, ["precedents", "decisions"],
        {"case_no": case_no}, start,
    ).model_dump()
