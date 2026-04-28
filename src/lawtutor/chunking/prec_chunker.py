"""판례/헌재결정례/법령해석례 청킹.

판례: 판시사항/판결요지/판례내용 섹션별 분할
헌재결정례: 판시사항/결정요지/전문 섹션별 분할
법령해석례: 질의요지+회답+이유를 하나로 묶거나 분할
"""

from lawtutor.chunking.chunk_models import Chunk
from lawtutor.models.precedent import Precedent
from lawtutor.models.decision import ConstitutionalDecision
from lawtutor.models.interpretation import LegalInterpretation
from lawtutor.constants import PREC_CHUNK_MAX_LENGTH


def _build_prec_header(case_no: str, case_name: str, court: str, judgment_date: str) -> str:
    """판례/결정례 헤더 텍스트를 생성한다."""
    date_str = ""
    if judgment_date and len(judgment_date) == 8:
        date_str = f"{judgment_date[:4]}.{judgment_date[4:6]}.{judgment_date[6:8]}"
    parts = [p for p in [court, date_str, case_no, case_name] if p]
    return " ".join(parts)


def _split_long_text(text: str, max_length: int) -> list[str]:
    """긴 텍스트를 max_length 이하로 분할한다."""
    if len(text) <= max_length:
        return [text]

    chunks: list[str] = []
    paragraphs = text.split("\n")
    current = ""

    for para in paragraphs:
        if len(current) + len(para) + 1 > max_length and current:
            chunks.append(current.strip())
            current = ""
        current += f"\n{para}"

    if current.strip():
        chunks.append(current.strip())

    return chunks if chunks else [text]


def chunk_precedent(prec: Precedent) -> list[Chunk]:
    """판례를 섹션별 청크로 분할한다.

    Args:
        prec: Precedent 모델

    Returns:
        Chunk 리스트
    """
    chunks: list[Chunk] = []
    header = _build_prec_header(prec.case_no, prec.case_name, prec.court, prec.judgment_date)

    base_metadata = {
        "source_type": "precedent",
        "case_id": prec.case_id,
        "case_no": prec.case_no,
        "case_name": prec.case_name,
        "court": prec.court,
        "judgment_date": prec.judgment_date,
        "judgment_type": prec.judgment_type,
        "case_type": prec.case_type,
        "referenced_articles": prec.referenced_articles,
    }

    sections = [
        ("holding", "판시사항", prec.holding),
        ("summary", "판결요지", prec.summary),
        ("reasoning", "판례내용", prec.reasoning),
    ]

    for section_key, section_name, content in sections:
        if not content:
            continue

        full_text = f"{header}\n[{section_name}]\n{content}"
        parts = _split_long_text(full_text, PREC_CHUNK_MAX_LENGTH)

        for i, part in enumerate(parts):
            suffix = f"_{i+1}" if len(parts) > 1 else ""
            chunks.append(Chunk(
                chunk_id=f"prec_{prec.case_id}_{section_key}{suffix}",
                source_type="precedent",
                chunk_type=section_key,
                text=part,
                metadata=base_metadata,
            ))

    return chunks


def chunk_decision(decision: ConstitutionalDecision) -> list[Chunk]:
    """헌재결정례를 섹션별 청크로 분할한다.

    Args:
        decision: ConstitutionalDecision 모델

    Returns:
        Chunk 리스트
    """
    chunks: list[Chunk] = []
    header = _build_prec_header(decision.case_no, decision.case_name, "헌법재판소", decision.decision_date)

    base_metadata = {
        "source_type": "decision",
        "decision_id": decision.decision_id,
        "case_no": decision.case_no,
        "case_name": decision.case_name,
        "case_type": decision.case_type,
        "decision_date": decision.decision_date,
        "referenced_articles": decision.referenced_articles,
        "review_target": decision.review_target,
    }

    sections = [
        ("holding", "판시사항", decision.holding),
        ("summary", "결정요지", decision.summary),
        ("full_text", "전문", decision.full_text),
    ]

    for section_key, section_name, content in sections:
        if not content:
            continue

        full_text = f"{header}\n[{section_name}]\n{content}"
        parts = _split_long_text(full_text, PREC_CHUNK_MAX_LENGTH)

        for i, part in enumerate(parts):
            suffix = f"_{i+1}" if len(parts) > 1 else ""
            chunks.append(Chunk(
                chunk_id=f"detc_{decision.decision_id}_{section_key}{suffix}",
                source_type="decision",
                chunk_type=section_key,
                text=part,
                metadata=base_metadata,
            ))

    return chunks


def chunk_interpretation(interp: LegalInterpretation) -> list[Chunk]:
    """법령해석례를 청크로 변환한다.

    해석례는 짧은 편이므로 질의+회답+이유를 하나로 묶는다.
    길면 분할한다.

    Args:
        interp: LegalInterpretation 모델

    Returns:
        Chunk 리스트
    """
    parts: list[str] = [interp.title]
    if interp.question:
        parts.append(f"[질의요지]\n{interp.question}")
    if interp.answer:
        parts.append(f"[회답]\n{interp.answer}")
    if interp.reasoning:
        parts.append(f"[이유]\n{interp.reasoning}")

    full_text = "\n\n".join(parts)

    base_metadata = {
        "source_type": "interpretation",
        "interpretation_id": interp.interpretation_id,
        "title": interp.title,
        "case_no": interp.case_no,
        "interpretation_date": interp.interpretation_date,
        "interpreting_agency": interp.interpreting_agency,
        "requesting_agency": interp.requesting_agency,
    }

    text_parts = _split_long_text(full_text, PREC_CHUNK_MAX_LENGTH)
    chunks: list[Chunk] = []

    for i, part in enumerate(text_parts):
        suffix = f"_{i+1}" if len(text_parts) > 1 else ""
        chunks.append(Chunk(
            chunk_id=f"expc_{interp.interpretation_id}{suffix}",
            source_type="interpretation",
            chunk_type="interpretation",
            text=part,
            metadata=base_metadata,
        ))

    return chunks
