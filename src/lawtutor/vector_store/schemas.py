"""Qdrant 컬렉션 스키마 정의.

컬렉션별 payload index 설정을 정의한다.
"""

from qdrant_client.models import PayloadSchemaType

# 컬렉션별 payload index 설정 (ARCHITECTURE.md 5.3절)
COLLECTION_PAYLOAD_INDEXES: dict[str, dict[str, PayloadSchemaType]] = {
    "laws": {
        "is_active": PayloadSchemaType.BOOL,
        "source_type": PayloadSchemaType.KEYWORD,
        "law_name": PayloadSchemaType.KEYWORD,
        "effective_date": PayloadSchemaType.KEYWORD,
    },
    "precedents": {
        "source_type": PayloadSchemaType.KEYWORD,
        "court": PayloadSchemaType.KEYWORD,
        "judgment_date": PayloadSchemaType.KEYWORD,
        "case_type": PayloadSchemaType.KEYWORD,
    },
    "decisions": {
        "source_type": PayloadSchemaType.KEYWORD,
        "case_type": PayloadSchemaType.KEYWORD,
        "decision_date": PayloadSchemaType.KEYWORD,
    },
    "interpretations": {
        "source_type": PayloadSchemaType.KEYWORD,
        "interpretation_date": PayloadSchemaType.KEYWORD,
    },
}
