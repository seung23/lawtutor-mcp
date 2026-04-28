"""법령 조문 데이터 모델."""

from pydantic import BaseModel, Field


class LawArticle(BaseModel):
    """법령 조문 단위 모델."""

    law_id: str = Field(description="법령ID (예: 001362)")
    law_mst: str = Field(description="법령일련번호 (예: 239291)")
    law_name: str = Field(description="법령명 (예: 행정절차법)")
    law_type: str = Field(default="", description="법령구분 (법률/대통령령/부령)")
    ministry: str = Field(default="", description="소관부처")

    article_no: str = Field(description="조문번호 (예: 21)")
    article_title: str = Field(default="", description="조문 제목 (예: 처분의 사전 통지)")
    article_content: str = Field(description="조문 본문 (항/호/목 포함 전체 텍스트)")

    effective_date: str = Field(default="", description="시행일자 (YYYYMMDD)")
    promulgation_date: str = Field(default="", description="공포일자 (YYYYMMDD)")
    promulgation_no: str = Field(default="", description="공포번호")
    is_active: bool = Field(default=True, description="현행 여부")
    revision_type: str = Field(default="", description="제개정구분 (전부개정/일부개정 등)")


class LawMeta(BaseModel):
    """법령 기본정보 (파싱 시 공통 메타데이터)."""

    law_id: str = Field(description="법령ID")
    law_mst: str = Field(description="법령일련번호")
    law_name: str = Field(description="법령명")
    law_type: str = Field(default="", description="법령구분")
    ministry: str = Field(default="", description="소관부처")
    effective_date: str = Field(default="", description="시행일자")
    promulgation_date: str = Field(default="", description="공포일자")
    promulgation_no: str = Field(default="", description="공포번호")
    is_active: bool = Field(default=True, description="현행 여부")
    revision_type: str = Field(default="", description="제개정구분")


class ParsedLaw(BaseModel):
    """파싱된 법령 전체 (메타 + 조문 리스트)."""

    meta: LawMeta
    articles: list[LawArticle]
