"""검색 로직.

쿼리 → 임베딩 → Qdrant 검색 → 결과 반환 파이프라인.
"""

import structlog

from lawtutor.constants import (
    COLLECTION_LAWS,
    COLLECTION_PRECEDENTS,
    COLLECTION_DECISIONS,
    COLLECTION_INTERPRETATIONS,
    SEARCH_DEFAULT_TOP_K,
    SEARCH_MAX_TOP_K,
)
from lawtutor.embeddings.bge_m3 import BgeM3Embedder
from lawtutor.vector_store.client import VectorStore

logger = structlog.get_logger()


class Retriever:
    """벡터 검색 수행기."""

    def __init__(self, embedder: BgeM3Embedder, store: VectorStore) -> None:
        """Retriever를 초기화한다.

        Args:
            embedder: 임베딩 모델
            store: Qdrant 벡터 스토어
        """
        self.embedder = embedder
        self.store = store

    def _clamp_top_k(self, top_k: int) -> int:
        """top_k를 유효 범위로 제한한다."""
        return max(1, min(top_k, SEARCH_MAX_TOP_K))

    def search_laws(
        self,
        query: str,
        top_k: int = SEARCH_DEFAULT_TOP_K,
        law_name_filter: str | None = None,
        include_historical: bool = False,
    ) -> list[dict]:
        """법령 조문을 검색한다.

        Args:
            query: 검색 쿼리
            top_k: 반환할 결과 수
            law_name_filter: 특정 법령명으로 한정
            include_historical: 폐지/개정 조문 포함 여부

        Returns:
            검색 결과 리스트
        """
        top_k = self._clamp_top_k(top_k)
        vector = self.embedder.embed_query(query)

        filters: dict = {}
        if not include_historical:
            filters["is_active"] = True
        if law_name_filter:
            filters["law_name"] = law_name_filter

        results = self.store.search(COLLECTION_LAWS, vector, limit=top_k, filters=filters or None)
        if not results:
            logger.info("db_miss_trying_api_fallback", query=query, collection="laws")
            from lawtutor.retrieval.api_fallback import search_laws_from_api
            return search_laws_from_api(query, top_k, law_name_filter)
        return results

    def search_precedents(
        self,
        query: str,
        top_k: int = SEARCH_DEFAULT_TOP_K,
        court_filter: str | None = None,
    ) -> list[dict]:
        """판례를 검색한다.

        Args:
            query: 검색 쿼리
            top_k: 반환할 결과 수
            court_filter: 법원명 필터

        Returns:
            검색 결과 리스트
        """
        top_k = self._clamp_top_k(top_k)
        vector = self.embedder.embed_query(query)

        filters: dict = {}
        if court_filter:
            filters["court"] = court_filter

        results = self.store.search(COLLECTION_PRECEDENTS, vector, limit=top_k, filters=filters or None)
        if not results:
            logger.info("db_miss_trying_api_fallback", query=query, collection="precedents")
            from lawtutor.retrieval.api_fallback import search_precedents_from_api
            return search_precedents_from_api(query, top_k)
        return results

    def search_decisions(
        self,
        query: str,
        top_k: int = SEARCH_DEFAULT_TOP_K,
        case_type_filter: str | None = None,
    ) -> list[dict]:
        """헌재결정례를 검색한다.

        Args:
            query: 검색 쿼리
            top_k: 반환할 결과 수
            case_type_filter: 사건종류 필터

        Returns:
            검색 결과 리스트
        """
        top_k = self._clamp_top_k(top_k)
        vector = self.embedder.embed_query(query)

        filters: dict = {}
        if case_type_filter:
            filters["case_type"] = case_type_filter

        results = self.store.search(COLLECTION_DECISIONS, vector, limit=top_k, filters=filters or None)
        if not results:
            logger.info("db_miss_trying_api_fallback", query=query, collection="decisions")
            from lawtutor.retrieval.api_fallback import search_decisions_from_api
            return search_decisions_from_api(query, top_k)
        return results

    def search_interpretations(
        self,
        query: str,
        top_k: int = SEARCH_DEFAULT_TOP_K,
    ) -> list[dict]:
        """법령해석례를 검색한다.

        Args:
            query: 검색 쿼리
            top_k: 반환할 결과 수

        Returns:
            검색 결과 리스트
        """
        top_k = self._clamp_top_k(top_k)
        vector = self.embedder.embed_query(query)
        results = self.store.search(COLLECTION_INTERPRETATIONS, vector, limit=top_k)
        if not results:
            logger.info("db_miss_trying_api_fallback", query=query, collection="interpretations")
            from lawtutor.retrieval.api_fallback import search_interpretations_from_api
            return search_interpretations_from_api(query, top_k)
        return results

    def fetch_by_article(
        self,
        law_name: str,
        article_no: str,
    ) -> list[dict]:
        """법령명 + 조문번호로 정확한 조문을 조회한다.

        Args:
            law_name: 법령명 (예: 행정절차법)
            article_no: 조문번호 (예: 21)

        Returns:
            매칭되는 청크 리스트
        """
        # 조문번호 정확 매칭은 벡터 검색이 아닌 payload filter로
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        query_filter = Filter(must=[
            FieldCondition(key="law_name", match=MatchValue(value=law_name)),
            FieldCondition(key="article_no", match=MatchValue(value=article_no)),
            FieldCondition(key="is_active", match=MatchValue(value=True)),
        ])

        results = self.store._client.scroll(
            collection_name=COLLECTION_LAWS,
            scroll_filter=query_filter,
            limit=10,
            with_payload=True,
        )

        db_results = [
            {"payload": dict(point.payload), "score": 1.0}
            for point in results[0]
        ]

        if not db_results:
            logger.info("db_miss_trying_api_fallback", law_name=law_name, article_no=article_no)
            from lawtutor.retrieval.api_fallback import fetch_article_from_api
            return fetch_article_from_api(law_name, article_no)

        return db_results

    def fetch_by_case_no(self, case_no: str) -> list[dict]:
        """사건번호로 판례/결정례를 조회한다.

        DB에서 먼저 검색하고, 없으면 국가법령정보센터 API에서 실시간 조회한다.

        Args:
            case_no: 사건번호 (예: 2018두12345 또는 2018헌마123)

        Returns:
            매칭되는 청크 리스트
        """
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        # 1차: DB에서 검색
        for collection in [COLLECTION_PRECEDENTS, COLLECTION_DECISIONS]:
            query_filter = Filter(must=[
                FieldCondition(key="case_no", match=MatchValue(value=case_no)),
            ])

            try:
                results = self.store._client.scroll(
                    collection_name=collection,
                    scroll_filter=query_filter,
                    limit=10,
                    with_payload=True,
                )
                if results[0]:
                    return [
                        {"payload": dict(point.payload), "score": 1.0}
                        for point in results[0]
                    ]
            except Exception:
                continue

        # 2차: DB에 없으면 API 폴백
        logger.info("db_miss_trying_api_fallback", case_no=case_no)
        from lawtutor.retrieval.api_fallback import fetch_case_from_api
        return fetch_case_from_api(case_no)
