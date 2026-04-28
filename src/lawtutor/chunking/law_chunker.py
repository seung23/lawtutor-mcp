"""법령 청킹.

조(條) 단위로 청킹한다.
- 조 전체가 LAW_CHUNK_MAX_LENGTH 이하면 하나의 청크
- 초과하면 항(項) 단위로 분할
"""

from lawtutor.chunking.chunk_models import Chunk
from lawtutor.models.law import LawArticle, ParsedLaw
from lawtutor.constants import LAW_CHUNK_MAX_LENGTH


def _build_article_header(article: LawArticle) -> str:
    """조문 헤더 텍스트를 생성한다."""
    title_part = f" ({article.article_title})" if article.article_title else ""
    return f"{article.law_name} 제{article.article_no}조{title_part}"


def chunk_law(parsed: ParsedLaw) -> list[Chunk]:
    """파싱된 법령을 청크 리스트로 변환한다.

    Args:
        parsed: ParsedLaw 모델

    Returns:
        Chunk 리스트
    """
    chunks: list[Chunk] = []

    for article in parsed.articles:
        header = _build_article_header(article)
        full_text = f"{header}\n{article.article_content}"

        base_metadata = {
            "source_type": "law",
            "law_id": article.law_id,
            "law_mst": article.law_mst,
            "law_name": article.law_name,
            "law_type": article.law_type,
            "ministry": article.ministry,
            "article_no": article.article_no,
            "article_title": article.article_title,
            "effective_date": article.effective_date,
            "promulgation_date": article.promulgation_date,
            "is_active": article.is_active,
        }

        if len(full_text) <= LAW_CHUNK_MAX_LENGTH:
            chunks.append(Chunk(
                chunk_id=f"law_{article.law_mst}_art{article.article_no}",
                source_type="law",
                chunk_type="article",
                text=full_text,
                metadata=base_metadata,
            ))
        else:
            # 항 단위로 분할
            paragraphs = article.article_content.split("\n")
            current_text = header
            para_idx = 0

            for line in paragraphs:
                if len(current_text) + len(line) + 1 > LAW_CHUNK_MAX_LENGTH and current_text != header:
                    para_idx += 1
                    chunks.append(Chunk(
                        chunk_id=f"law_{article.law_mst}_art{article.article_no}_p{para_idx}",
                        source_type="law",
                        chunk_type="paragraph",
                        text=current_text,
                        metadata=base_metadata,
                    ))
                    current_text = header

                current_text += f"\n{line}"

            # 마지막 남은 텍스트
            if current_text != header:
                para_idx += 1
                chunks.append(Chunk(
                    chunk_id=f"law_{article.law_mst}_art{article.article_no}_p{para_idx}",
                    source_type="law",
                    chunk_type="paragraph" if para_idx > 1 else "article",
                    text=current_text,
                    metadata=base_metadata,
                ))

    return chunks
