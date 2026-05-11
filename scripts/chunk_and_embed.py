"""청킹 + 임베딩 + Qdrant 인덱싱 통합 스크립트.

사용법:
    # 전체 인덱싱 (컬렉션 재생성)
    uv run python scripts/chunk_and_embed.py --recreate

    # 법령만 인덱싱
    uv run python scripts/chunk_and_embed.py --target law

    # 컬렉션 상태 확인
    uv run python scripts/chunk_and_embed.py --check
"""

import argparse
import json
from pathlib import Path

import structlog

from lawtutor.config import settings

structlog.configure(processors=[structlog.dev.ConsoleRenderer()])
logger = structlog.get_logger()


def load_and_chunk_laws() -> list:
    """parsed 법령 JSON을 로드하고 청킹한다."""
    from lawtutor.models.law import ParsedLaw
    from lawtutor.chunking.law_chunker import chunk_law

    parsed_dir = settings.data_parsed_dir / "law"
    if not parsed_dir.exists():
        logger.warning("no_parsed_dir", path=str(parsed_dir))
        return []

    all_chunks = []
    for json_path in parsed_dir.glob("*.json"):
        data = json.loads(json_path.read_text(encoding="utf-8"))
        parsed = ParsedLaw.model_validate(data)
        chunks = chunk_law(parsed)
        all_chunks.extend(chunks)
        logger.info("chunked_law", name=parsed.meta.law_name, chunks=len(chunks))

    return all_chunks


def load_and_chunk_precedents() -> list:
    """parsed 판례 JSON을 로드하고 청킹한다."""
    from lawtutor.models.precedent import Precedent
    from lawtutor.chunking.prec_chunker import chunk_precedent

    parsed_dir = settings.data_parsed_dir / "prec"
    if not parsed_dir.exists():
        return []

    all_chunks = []
    for json_path in parsed_dir.glob("*.json"):
        data = json.loads(json_path.read_text(encoding="utf-8"))
        prec = Precedent.model_validate(data)
        chunks = chunk_precedent(prec)
        all_chunks.extend(chunks)

    logger.info("chunked_precedents", total=len(all_chunks))
    return all_chunks


def load_and_chunk_decisions() -> list:
    """parsed 헌재결정례 JSON을 로드하고 청킹한다."""
    from lawtutor.models.decision import ConstitutionalDecision
    from lawtutor.chunking.prec_chunker import chunk_decision

    parsed_dir = settings.data_parsed_dir / "detc"
    if not parsed_dir.exists():
        return []

    all_chunks = []
    for json_path in parsed_dir.glob("*.json"):
        data = json.loads(json_path.read_text(encoding="utf-8"))
        decision = ConstitutionalDecision.model_validate(data)
        chunks = chunk_decision(decision)
        all_chunks.extend(chunks)

    logger.info("chunked_decisions", total=len(all_chunks))
    return all_chunks


def load_and_chunk_interpretations() -> list:
    """parsed 법령해석례 JSON을 로드하고 청킹한다."""
    from lawtutor.models.interpretation import LegalInterpretation
    from lawtutor.chunking.prec_chunker import chunk_interpretation

    parsed_dir = settings.data_parsed_dir / "expc"
    if not parsed_dir.exists():
        return []

    all_chunks = []
    for json_path in parsed_dir.glob("*.json"):
        data = json.loads(json_path.read_text(encoding="utf-8"))
        interp = LegalInterpretation.model_validate(data)
        chunks = chunk_interpretation(interp)
        all_chunks.extend(chunks)

    logger.info("chunked_interpretations", total=len(all_chunks))
    return all_chunks


COLLECTION_LOADERS = {
    "laws": load_and_chunk_laws,
    "precedents": load_and_chunk_precedents,
    "decisions": load_and_chunk_decisions,
    "interpretations": load_and_chunk_interpretations,
}


INDEX_BATCH_SIZE = 5000


def index_collection(collection_name: str, recreate: bool = False) -> None:
    """컬렉션을 인덱싱한다 (dense + sparse 하이브리드).

    메모리 절약을 위해 INDEX_BATCH_SIZE 단위로 임베딩 → upsert를 반복한다.
    """
    from lawtutor.embeddings.bge_m3 import BgeM3Embedder
    from lawtutor.vector_store.client import VectorStore

    # 1. 청킹
    loader = COLLECTION_LOADERS[collection_name]
    chunks = loader()
    if not chunks:
        logger.warning("no_chunks", collection=collection_name)
        return

    logger.info("total_chunks", collection=collection_name, count=len(chunks))

    # 2. 컬렉션 생성
    embedder = BgeM3Embedder()
    store = VectorStore()
    store.create_collection(collection_name, recreate=recreate)

    # 3. 배치 단위로 임베딩 → upsert (메모리 절약)
    total = len(chunks)
    upserted = 0

    for batch_start in range(0, total, INDEX_BATCH_SIZE):
        batch_end = min(batch_start + INDEX_BATCH_SIZE, total)
        batch_chunks = chunks[batch_start:batch_end]
        batch_texts = [c.text for c in batch_chunks]

        logger.info("batch_embedding", batch=f"{batch_start}-{batch_end}", total=total)
        hybrid = embedder.embed_hybrid(batch_texts)

        store.upsert_chunks(
            collection_name, batch_chunks, hybrid.dense, hybrid.sparse,
            id_offset=batch_start,
        )
        upserted += len(batch_chunks)
        logger.info("batch_upserted", upserted=upserted, total=total)

    info = store.get_collection_info(collection_name)
    logger.info("indexing_complete", **info)


def check_collections() -> None:
    """모든 컬렉션 상태를 확인한다."""
    from lawtutor.vector_store.client import VectorStore

    store = VectorStore()
    for name in COLLECTION_LOADERS:
        try:
            info = store.get_collection_info(name)
            logger.info("collection_status", **info)
        except Exception as e:
            logger.warning("collection_not_found", name=name, error=str(e))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="청킹 + 임베딩 + Qdrant 인덱싱")
    parser.add_argument(
        "--target",
        choices=["all", *COLLECTION_LOADERS.keys()],
        default="all",
        help="인덱싱할 컬렉션 (기본: all)",
    )
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="기존 컬렉션 삭제 후 재생성",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="컬렉션 상태 확인만",
    )
    args = parser.parse_args()

    if args.check:
        check_collections()
    else:
        if args.target == "all":
            targets = list(COLLECTION_LOADERS.keys())
        else:
            targets = [args.target]

        for target in targets:
            logger.info("indexing_start", target=target)
            index_collection(target, recreate=args.recreate)
