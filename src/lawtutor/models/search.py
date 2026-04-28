"""MCP 도구 응답 모델.

모든 search/fetch 도구가 공통으로 사용하는 응답 구조.
"""

from typing import Any

from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    """단일 검색 결과."""

    content: str = Field(description="조문 또는 판례 본문 텍스트")
    metadata: dict[str, Any] = Field(description="출처 메타데이터")
    score: float = Field(default=0.0, description="검색 유사도 점수")


class SearchResponse(BaseModel):
    """MCP 도구 응답."""

    results: list[SearchResult] = Field(default_factory=list)
    query: str = Field(default="", description="원본 쿼리")
    total_found: int = Field(default=0, description="전체 검색 결과 수")
    search_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="검색 메타데이터 (컬렉션, 필터, 소요시간 등)",
    )
