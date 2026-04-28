"""임베딩 추상 인터페이스."""

from abc import ABC, abstractmethod


class BaseEmbedder(ABC):
    """임베딩 모델 추상 클래스."""

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """텍스트 리스트를 임베딩 벡터 리스트로 변환한다.

        Args:
            texts: 임베딩할 텍스트 리스트

        Returns:
            각 텍스트에 대한 임베딩 벡터 리스트
        """
        ...

    @abstractmethod
    def embed_query(self, query: str) -> list[float]:
        """단일 쿼리를 임베딩 벡터로 변환한다.

        Args:
            query: 검색 쿼리

        Returns:
            임베딩 벡터
        """
        ...

    @property
    @abstractmethod
    def dimension(self) -> int:
        """임베딩 벡터 차원."""
        ...
