"""Qdrant 벡터 DB 클라이언트.

컬렉션 생성, payload index 등록, upsert, 검색 기능을 제공한다.
dense + sparse 하이브리드 검색을 지원한다.
"""

import structlog
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    PointStruct,
    VectorParams,
    SparseVectorParams,
    SparseVector,
    Filter,
    FieldCondition,
    MatchValue,
    Prefetch,
    FusionQuery,
    Fusion,
)

from lawtutor.config import settings
from lawtutor.constants import BGE_M3_VECTOR_DIM, ALL_COLLECTIONS
from lawtutor.chunking.chunk_models import Chunk
from lawtutor.vector_store.schemas import COLLECTION_PAYLOAD_INDEXES

logger = structlog.get_logger()

# upsert 배치 크기
UPSERT_BATCH_SIZE = 100

# 하이브리드 검색 시 prefetch 배수 (dense/sparse 각각 limit * 이 값만큼 후보 가져옴)
HYBRID_PREFETCH_MULTIPLIER = 4


class VectorStore:
    """Qdrant 벡터 DB 래퍼."""

    def __init__(self) -> None:
        """Qdrant 클라이언트를 초기화한다."""
        self._client = QdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
            timeout=60,
        )
        logger.info("qdrant_connected", host=settings.qdrant_host, port=settings.qdrant_port)

    def create_collection(self, name: str, recreate: bool = False) -> None:
        """컬렉션을 생성한다 (dense + sparse named vectors).

        Args:
            name: 컬렉션 이름
            recreate: True이면 기존 컬렉션 삭제 후 재생성
        """
        if recreate and self._client.collection_exists(name):
            self._client.delete_collection(name)
            logger.info("collection_deleted", name=name)

        if not self._client.collection_exists(name):
            self._client.create_collection(
                collection_name=name,
                vectors_config={
                    "dense": VectorParams(
                        size=BGE_M3_VECTOR_DIM,
                        distance=Distance.COSINE,
                    ),
                },
                sparse_vectors_config={
                    "sparse": SparseVectorParams(),
                },
            )
            logger.info("collection_created", name=name)

            # payload index 등록
            if name in COLLECTION_PAYLOAD_INDEXES:
                for field, schema_type in COLLECTION_PAYLOAD_INDEXES[name].items():
                    self._client.create_payload_index(
                        collection_name=name,
                        field_name=field,
                        field_schema=schema_type,
                    )
                logger.info("payload_indexes_created", name=name)

    def create_all_collections(self, recreate: bool = False) -> None:
        """4개 컬렉션을 모두 생성한다.

        Args:
            recreate: True이면 기존 컬렉션 삭제 후 재생성
        """
        for name in ALL_COLLECTIONS:
            self.create_collection(name, recreate=recreate)

    def upsert_chunks(
        self,
        collection_name: str,
        chunks: list[Chunk],
        dense_vectors: list[list[float]],
        sparse_vectors: list[dict[int, float]],
        id_offset: int = 0,
    ) -> None:
        """청크와 벡터(dense + sparse)를 컬렉션에 upsert한다.

        Args:
            collection_name: 컬렉션 이름
            chunks: 청크 리스트
            dense_vectors: dense 임베딩 벡터 리스트
            sparse_vectors: sparse lexical weight 리스트
            id_offset: point ID 시작 오프셋 (배치 처리 시 중복 방지)
        """
        points = []
        for idx, (chunk, dense_vec, sparse_weights) in enumerate(
            zip(chunks, dense_vectors, sparse_vectors)
        ):
            indices = [int(k) for k in sparse_weights.keys()]
            values = list(sparse_weights.values())

            points.append(PointStruct(
                id=id_offset + idx,
                vector={
                    "dense": dense_vec,
                    "sparse": SparseVector(indices=indices, values=values),
                },
                payload={
                    "chunk_id": chunk.chunk_id,
                    "text": chunk.text,
                    "chunk_type": chunk.chunk_type,
                    **chunk.metadata,
                },
            ))

        # 배치 upsert
        for i in range(0, len(points), UPSERT_BATCH_SIZE):
            batch = points[i : i + UPSERT_BATCH_SIZE]
            self._client.upsert(collection_name=collection_name, points=batch)

        logger.info("upserted", collection=collection_name, count=len(points))

    def search(
        self,
        collection_name: str,
        query_vector: list[float],
        limit: int = 5,
        filters: dict | None = None,
        sparse_vector: dict[int, float] | None = None,
    ) -> list[dict]:
        """하이브리드 검색을 수행한다 (dense + sparse RRF fusion).

        sparse_vector가 제공되면 dense/sparse 각각 검색 후 RRF로 융합한다.
        제공되지 않으면 dense만으로 검색한다.

        Args:
            collection_name: 컬렉션 이름
            query_vector: dense 쿼리 벡터
            limit: 반환할 결과 수
            filters: 필터 조건 딕셔너리
            sparse_vector: sparse 쿼리 벡터 (없으면 dense-only)

        Returns:
            검색 결과 리스트 (payload + score)
        """
        query_filter = None
        if filters:
            conditions = [
                FieldCondition(key=k, match=MatchValue(value=v))
                for k, v in filters.items()
            ]
            query_filter = Filter(must=conditions)

        if sparse_vector:
            # 하이브리드: dense + sparse → RRF fusion
            sparse_indices = [int(k) for k in sparse_vector.keys()]
            sparse_values = list(sparse_vector.values())
            prefetch_limit = limit * HYBRID_PREFETCH_MULTIPLIER

            results = self._client.query_points(
                collection_name=collection_name,
                prefetch=[
                    Prefetch(
                        query=query_vector,
                        using="dense",
                        limit=prefetch_limit,
                        filter=query_filter,
                    ),
                    Prefetch(
                        query=SparseVector(
                            indices=sparse_indices,
                            values=sparse_values,
                        ),
                        using="sparse",
                        limit=prefetch_limit,
                        filter=query_filter,
                    ),
                ],
                query=FusionQuery(fusion=Fusion.RRF),
                limit=limit,
                with_payload=True,
            )
        else:
            # dense-only 폴백
            results = self._client.query_points(
                collection_name=collection_name,
                query=query_vector,
                using="dense",
                limit=limit,
                query_filter=query_filter,
                with_payload=True,
            )

        return [
            {
                "payload": dict(point.payload),
                "score": point.score,
            }
            for point in results.points
        ]

    def get_collection_info(self, name: str) -> dict:
        """컬렉션 정보를 반환한다."""
        info = self._client.get_collection(name)
        return {
            "name": name,
            "points_count": info.points_count,
            "status": info.status.value,
        }
