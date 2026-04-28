"""국가법령정보센터 OPEN API 기본 클라이언트.

모든 collector는 이 클래스를 상속하여 사용한다.
API 인증, 재시도, 원본 저장 로직을 공통으로 제공한다.
"""

from pathlib import Path
from datetime import datetime

import httpx
from lxml import etree
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from lawtutor.config import settings
from lawtutor.constants import LAW_API_BASE_URL, API_RESPONSE_TYPE


class BaseCollector:
    """국가법령정보센터 OPEN API 비동기 HTTP 클라이언트 베이스."""

    def __init__(self, target: str) -> None:
        """BaseCollector를 초기화한다.

        Args:
            target: API 타겟 코드 (law, prec, detc, expc)
        """
        self.target = target
        self.oc = settings.law_go_kr_oc
        self.base_url = LAW_API_BASE_URL
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "BaseCollector":
        """비동기 컨텍스트 매니저 진입."""
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(30.0),
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, *args: object) -> None:
        """비동기 컨텍스트 매니저 종료."""
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        """활성 HTTP 클라이언트를 반환한다."""
        if self._client is None:
            raise RuntimeError("BaseCollector must be used as async context manager")
        return self._client

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.ConnectError)),
    )
    async def _request(self, path: str, params: dict[str, str | int]) -> bytes:
        """API 요청을 보내고 응답 바이트를 반환한다.

        OC 파라미터를 자동 주입하고, 실패 시 최대 3회 재시도한다.

        Args:
            path: API 엔드포인트 경로 (예: /DRF/lawSearch.do)
            params: 쿼리 파라미터 딕셔너리

        Returns:
            응답 본문 바이트
        """
        params = {**params, "OC": self.oc, "type": API_RESPONSE_TYPE}
        response = await self.client.get(path, params=params)
        response.raise_for_status()
        return response.content

    def _parse_xml(self, raw: bytes) -> etree._Element:
        """XML 바이트를 파싱하여 루트 Element를 반환한다.

        Args:
            raw: XML 응답 바이트

        Returns:
            lxml Element 루트 노드
        """
        return etree.fromstring(raw)

    def _save_raw(self, raw: bytes, filename: str) -> Path:
        """API 응답 원본을 data/raw/{target}/{date}/ 에 저장한다.

        Args:
            raw: 저장할 원본 바이트
            filename: 파일명 (확장자 포함)

        Returns:
            저장된 파일 경로
        """
        today = datetime.now().strftime("%Y%m%d")
        save_dir = settings.data_raw_dir / self.target / today
        save_dir.mkdir(parents=True, exist_ok=True)

        filepath = save_dir / filename
        filepath.write_bytes(raw)
        return filepath

    def _get_text(self, element: etree._Element, tag: str) -> str:
        """XML 엘리먼트에서 태그의 텍스트를 안전하게 추출한다.

        Args:
            element: 부모 엘리먼트
            tag: 찾을 태그명

        Returns:
            태그의 텍스트 내용. 태그가 없거나 텍스트가 없으면 빈 문자열.
        """
        child = element.find(tag)
        if child is not None and child.text:
            return child.text.strip()
        return ""

    def _get_int(self, element: etree._Element, tag: str, default: int = 0) -> int:
        """XML 엘리먼트에서 태그의 텍스트를 정수로 추출한다.

        Args:
            element: 부모 엘리먼트
            tag: 찾을 태그명
            default: 변환 실패 시 기본값

        Returns:
            정수값
        """
        text = self._get_text(element, tag)
        try:
            return int(text)
        except (ValueError, TypeError):
            return default
