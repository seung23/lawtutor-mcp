"""법령해석례 데이터 모델."""

from pydantic import BaseModel, Field


class LegalInterpretation(BaseModel):
    """법령해석례 모델."""

    interpretation_id: str = Field(description="법령해석례일련번호")
    title: str = Field(default="", description="안건명")
    case_no: str = Field(default="", description="안건번호 (예: 14-0801)")
    interpretation_date: str = Field(default="", description="해석일자 (YYYYMMDD)")

    interpreting_agency: str = Field(default="", description="해석기관명 (예: 법제처)")
    requesting_agency: str = Field(default="", description="질의기관명")

    question: str = Field(default="", description="질의요지")
    answer: str = Field(default="", description="회답")
    reasoning: str = Field(default="", description="이유")
