"""BGE-M3 임베딩 모델.

한국어 성능이 우수한 BAAI/bge-m3 모델을 사용한다.
CPU/GPU 자동 감지, 배치 처리를 지원한다.
"""

import structlog

from lawtutor.config import settings
from lawtutor.constants import BGE_M3_VECTOR_DIM
from lawtutor.embeddings.base import BaseEmbedder

logger = structlog.get_logger()

# BGE-M3 임베딩 배치 크기
EMBED_BATCH_SIZE = 32


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
        """텍스트 리스트를 배치로 임베딩한다.

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
        # dense_vecs는 numpy array
        return result["dense_vecs"].tolist()

    def embed_query(self, query: str) -> list[float]:
        """단일 쿼리를 임베딩한다.

        Args:
            query: 검색 쿼리

        Returns:
            1024차원 벡터
        """
        vectors = self.embed([query])
        return vectors[0]
