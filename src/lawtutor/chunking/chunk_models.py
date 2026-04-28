"""청크 데이터 모델."""

from typing import Any

from pydantic import BaseModel, Field


class Chunk(BaseModel):
    """벡터 DB에 저장되는 청크 단위."""

    chunk_id: str = Field(description="청크 고유 ID")
    source_type: str = Field(description="데이터 출처 (law/precedent/decision/interpretation)")
    chunk_type: str = Field(default="", description="청크 유형 (article/paragraph/holding/summary 등)")
    text: str = Field(description="임베딩 대상 텍스트")
    metadata: dict[str, Any] = Field(default_factory=dict, description="검색 결과에 포함될 메타데이터")
