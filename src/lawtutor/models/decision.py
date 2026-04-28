"""헌법재판소 결정례 데이터 모델."""

from pydantic import BaseModel, Field


class ConstitutionalDecision(BaseModel):
    """헌법재판소 결정례 모델."""

    decision_id: str = Field(description="헌재결정례일련번호")
    case_no: str = Field(description="사건번호 (예: 2012헌아146)")
    case_name: str = Field(default="", description="사건명")
    case_type: str = Field(default="", description="사건종류명 (예: 헌아)")
    case_type_code: str = Field(default="", description="사건종류코드")
    decision_date: str = Field(default="", description="종국일자 (YYYYMMDD)")

    holding: str = Field(default="", description="판시사항")
    summary: str = Field(default="", description="결정요지")
    full_text: str = Field(default="", description="전문")
    referenced_articles: str = Field(default="", description="참조조문")
    referenced_cases: str = Field(default="", description="참조판례")
    review_target: str = Field(default="", description="심판대상조문")
