"""BGE-M3 임베딩 모델.

한국어 성능이 우수한 BAAI/bge-m3 모델을 사용한다.
CPU/GPU 자동 감지, 배치 처리를 지원한다.
dense + sparse(lexical) 하이브리드 벡터를 지원한다.
"""

from dataclasses import dataclass

import structlog

from lawtutor.config import settings
from lawtutor.constants import BGE_M3_VECTOR_DIM
from lawtutor.embeddings.base import BaseEmbedder

logger = structlog.get_logger()

# BGE-M3 임베딩 배치 크기
EMBED_BATCH_SIZE = 32


@dataclass
class HybridVectors:
    """dense + sparse 벡터 쌍."""

    dense: list[list[float]]
    sparse: list[dict[int, float]]


class BgeM3Embedder(BaseEmbedder):
    """BGE-M3 임베딩 모델 래퍼."""

    def __init__(self) -> None:
        """BGE-M3 모델을 로드한다. 첫 호출 시 ~2.5GB 다운로드."""
        logger.info(
            "loading_bge_m3",
            model=settings.bge_m3_model_path,
            device=settings.bge_m3_device,
        )
        from FlagEmbedding import BGEM3FlagModel

        self._model = BGEM3FlagModel(
            settings.bge_m3_model_path,
            use_fp16=(settings.bge_m3_device == "cuda"),
        )
        logger.info("bge_m3_loaded")

    @property
    def dimension(self) -> int:
        """임베딩 벡터 차원 (1024)."""
        return BGE_M3_VECTOR_DIM

    def embed(self, texts: list[str]) -> list[list[float]]:
        """텍스트 리스트를 배치로 임베딩한다 (dense only, 하위호환).

        Args:
            texts: 임베딩할 텍스트 리스트

        Returns:
            각 텍스트에 대한 1024차원 벡터 리스트
        """
        if not texts:
            return []

        result = self._model.encode(
            texts,
            batch_size=EMBED_BATCH_SIZE,
            max_length=8192,
        )
        return result["dense_vecs"].tolist()

    def embed_hybrid(self, texts: list[str]) -> HybridVectors:
        """텍스트 리스트를 dense + sparse로 임베딩한다.

        Args:
            texts: 임베딩할 텍스트 리스트

        Returns:
            HybridVectors (dense 벡터 + sparse lexical weights)
        """
        if not texts:
            return HybridVectors(dense=[], sparse=[])

        result = self._model.encode(
            texts,
            batch_size=EMBED_BATCH_SIZE,
            max_length=8192,
            return_sparse=True,
        )
        return HybridVectors(
            dense=result["dense_vecs"].tolist(),
            sparse=result["lexical_weights"],
        )

    def embed_query(self, query: str) -> list[float]:
        """단일 쿼리를 dense 임베딩한다.

        Args:
            query: 검색 쿼리

        Returns:
            1024차원 벡터
        """
        vectors = self.embed([query])
        return vectors[0]

    def embed_query_hybrid(self, query: str) -> tuple[list[float], dict[int, float]]:
        """단일 쿼리를 dense + sparse로 임베딩한다.

        Args:
            query: 검색 쿼리

        Returns:
            (dense 벡터, sparse lexical weights) 튜플
        """
        hybrid = self.embed_hybrid([query])
        return hybrid.dense[0], hybrid.sparse[0]
