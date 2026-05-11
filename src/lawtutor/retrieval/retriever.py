"""검색 로직.

쿼리 → 임베딩 → Qdrant 검색 → 결과 반환 파이프라인.
법령 검색은 N-gram 타이틀 부스트 리랭킹을 적용한다.
"""

import structlog

from lawtutor.constants import (
    COLLECTION_LAWS,
    COLLECTION_PRECEDENTS,
    COLLECTION_DECISIONS,
    COLLECTION_INTERPRETATIONS,
    SEARCH_DEFAULT_TOP_K,
    SEARCH_MAX_TOP_K,
    RERANK_OVERFETCH_MULTIPLIER,
    RERANK_TITLE_BOOST_WEIGHT,
    RERANK_NGRAM_MIN,
    RERANK_NGRAM_MAX,
    LEGAL_SYNONYMS,
)
from lawtutor.embeddings.bge_m3 import BgeM3Embedder
from lawtutor.vector_store.client import VectorStore

logger = structlog.get_logger()


def _extract_ngrams(text: str, n_min: int, n_max: int) -> set[str]:
    """텍스트에서 n_min~n_max 길이의 문자 n-gram을 추출한다."""
    ngrams: set[str] = set()
    for n in range(n_min, n_max):
        for i in range(len(text) - n + 1):
            ngrams.add(text[i:i + n])
    return ngrams


def _expand_query_with_synonyms(query: str) -> str:
    """쿼리에 매칭되는 동의어를 붙여 확장한다.

    임베딩 벡터의 recall을 높이기 위해 사용한다.
    """
    expansions: list[str] = []
    for term, synonyms in LEGAL_SYNONYMS.items():
        if term in query:
            for syn in synonyms:
                if syn not in query and syn not in expansions:
                    expansions.append(syn)
    if expansions:
        return query + " " + " ".join(expansions)
    return query


def _get_synonym_titles(query: str) -> list[str]:
    """쿼리에 매칭되는 동의어 중 article_title 값을 반환한다."""
    titles: list[str] = []
    for term, synonyms in LEGAL_SYNONYMS.items():
        if term in query:
            titles.extend(synonyms)
    return list(set(titles))


def _build_match_ngrams(query: str) -> set[str]:
    """쿼리 + 동의어에서 타이틀 매칭용 n-gram을 추출한다."""
    targets = [query]
    for term, synonyms in LEGAL_SYNONYMS.items():
        if term in query:
            targets.extend(synonyms)
    all_ngrams: set[str] = set()
    for t in targets:
        all_ngrams |= _extract_ngrams(t, RERANK_NGRAM_MIN, RERANK_NGRAM_MAX)
    return all_ngrams


def _title_boost_rerank(
    results: list[dict],
    query: str,
    top_k: int,
) -> list[dict]:
    """N-gram 타이틀 부스트로 법령 검색 결과를 리랭킹한다.

    article_title이 있는 결과에 대해, 쿼리(+동의어)의 n-gram이
    타이틀에 얼마나 매칭되는지 계산하여 score를 부스트한다.
    """
    if not results:
        return results

    match_ngrams = _build_match_ngrams(query)
    if not match_ngrams:
        return results[:top_k]

    for r in results:
        title = r["payload"].get("article_title", "")
        if not title:
            continue

        # 타이틀의 n-gram과 쿼리 n-gram의 교집합 비율
        title_ngrams = _extract_ngrams(title, RERANK_NGRAM_MIN, RERANK_NGRAM_MAX)
        if not title_ngrams:
            continue

        overlap = len(match_ngrams & title_ngrams)
        # match_ngrams 대비 매칭 비율로 부스트 (0~1 범위)
        boost = (overlap / len(match_ngrams)) * RERANK_TITLE_BOOST_WEIGHT
        r["score"] = r.get("score", 0) + boost

    results.sort(key=lambda r: r.get("score", 0), reverse=True)
    return results[:top_k]


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

    def _hybrid_search(
        self,
        collection: str,
        query: str,
        top_k: int,
        filters: dict | None = None,
    ) -> list[dict]:
        """하이브리드 검색 공통 로직 (dense + sparse RRF)."""
        top_k = self._clamp_top_k(top_k)
        dense_vec, sparse_vec = self.embedder.embed_query_hybrid(query)
        return self.store.search(
            collection, dense_vec, limit=top_k,
            filters=filters or None, sparse_vector=sparse_vec,
        )

    def _search_by_title(
        self,
        collection: str,
        title_values: list[str],
        filters: dict | None = None,
    ) -> list[dict]:
        """article_title 값으로 직접 필터 검색한다 (벡터 검색 보완용)."""
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        all_results: list[dict] = []
        for title_val in title_values:
            conditions = [FieldCondition(key="article_title", match=MatchValue(value=title_val))]
            if filters:
                for k, v in filters.items():
                    conditions.append(FieldCondition(key=k, match=MatchValue(value=v)))

            results = self.store._client.scroll(
                collection_name=collection,
                scroll_filter=Filter(must=conditions),
                limit=5,
                with_payload=True,
            )
            for point in results[0]:
                all_results.append({"payload": dict(point.payload), "score": 0.0})

        return all_results

    def _hybrid_search_with_rerank(
        self,
        collection: str,
        query: str,
        top_k: int,
        filters: dict | None = None,
    ) -> list[dict]:
        """하이브리드 검색 + 타이틀 부스트 리랭킹 (법령 전용).

        1. 동의어로 쿼리를 확장하여 임베딩
        2. top_k * N배 over-fetch
        3. 동의어에 매칭되는 article_title 직접 검색 결과를 병합
        4. N-gram 타이틀 부스트 리랭킹
        5. top_k개만 반환
        """
        top_k = self._clamp_top_k(top_k)
        overfetch_k = min(top_k * RERANK_OVERFETCH_MULTIPLIER, SEARCH_MAX_TOP_K)

        # 동의어 확장된 쿼리로 임베딩
        expanded_query = _expand_query_with_synonyms(query)
        dense_vec, sparse_vec = self.embedder.embed_query_hybrid(expanded_query)

        results = self.store.search(
            collection, dense_vec, limit=overfetch_k,
            filters=filters or None, sparse_vector=sparse_vec,
        )

        # 동의어 매칭되는 article_title 직접 검색 → 벡터 검색에 빠진 결과 보충
        synonym_titles = _get_synonym_titles(query)
        if synonym_titles:
            # 벡터 검색 결과의 최고 score를 base로 사용
            max_vector_score = max((r.get("score", 0) for r in results), default=0.5)
            title_results = self._search_by_title(collection, synonym_titles, filters)
            # 중복 제거 후 병합 (chunk_id 기준), 동의어 직접 매칭 결과에 높은 base score 부여
            existing_ids = {r["payload"].get("chunk_id") for r in results}
            for tr in title_results:
                if tr["payload"].get("chunk_id") not in existing_ids:
                    tr["score"] = max_vector_score
                    results.append(tr)
                    existing_ids.add(tr["payload"].get("chunk_id"))

        # 원본 쿼리 기준으로 타이틀 부스트 리랭킹
        return _title_boost_rerank(results, query, top_k)

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
        filters: dict = {}
        if not include_historical:
            filters["is_active"] = True
        if law_name_filter:
            filters["law_name"] = law_name_filter

        results = self._hybrid_search_with_rerank(COLLECTION_LAWS, query, top_k, filters)
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
        filters: dict = {}
        if court_filter:
            filters["court"] = court_filter

        results = self._hybrid_search(COLLECTION_PRECEDENTS, query, top_k, filters)
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
        filters: dict = {}
        if case_type_filter:
            filters["case_type"] = case_type_filter

        results = self._hybrid_search(COLLECTION_DECISIONS, query, top_k, filters)
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
        results = self._hybrid_search(COLLECTION_INTERPRETATIONS, query, top_k)
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
