"""검색 결과 → MCP 응답 포매터."""

import time

from lawtutor.models.search import SearchResponse, SearchResult


def format_results(
    raw_results: list[dict],
    query: str,
    collections_searched: list[str],
    filters_applied: dict | None = None,
    start_time: float | None = None,
) -> SearchResponse:
    """Qdrant 검색 결과를 MCP SearchResponse로 변환한다.

    Args:
        raw_results: Qdrant 검색 결과 리스트
        query: 원본 쿼리
        collections_searched: 검색한 컬렉션 목록
        filters_applied: 적용된 필터
        start_time: 검색 시작 시각 (time.time())

    Returns:
        MCP 응답 모델
    """
    results: list[SearchResult] = []
    for raw in raw_results:
        payload = raw["payload"]
        text = payload.pop("text", "")
        # chunk_id는 내부용이므로 메타데이터에서 제외
        payload.pop("chunk_id", None)
        payload.pop("chunk_type", None)

        results.append(SearchResult(
            content=text,
            metadata=payload,
            score=raw.get("score", 0.0),
        ))

    search_time_ms = int((time.time() - start_time) * 1000) if start_time else 0

    return SearchResponse(
        results=results,
        query=query,
        total_found=len(results),
        search_metadata={
            "collections_searched": collections_searched,
            "filters_applied": filters_applied or {},
            "search_time_ms": search_time_ms,
        },
    )
