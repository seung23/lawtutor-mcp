"""대법원 판례 데이터 모델."""

from pydantic import BaseModel, Field


class Precedent(BaseModel):
    """대법원 판례 모델."""

    case_id: str = Field(description="판례일련번호")
    case_no: str = Field(description="사건번호 (예: 2025두35681)")
    case_name: str = Field(default="", description="사건명")
    court: str = Field(default="", description="법원명 (예: 대법원)")
    court_type_code: str = Field(default="", description="법원종류코드")
    case_type: str = Field(default="", description="사건종류명 (예: 일반행정)")
    judgment_date: str = Field(default="", description="선고일자 (YYYYMMDD)")
    judgment_type: str = Field(default="", description="판결유형 (기각/인용 등)")

    holding: str = Field(default="", description="판시사항")
    summary: str = Field(default="", description="판결요지")
    reasoning: str = Field(default="", description="판례내용 (이유)")
    referenced_articles: str = Field(default="", description="참조조문")
    referenced_cases: str = Field(default="", description="참조판례")
