"""데이터 수집 통합 스크립트.

사용법:
    # 전체 수집
    uv run python scripts/collect_all.py --target all

    # 특정 타겟만 수집
    uv run python scripts/collect_all.py --target law
    uv run python scripts/collect_all.py --target prec
    uv run python scripts/collect_all.py --target detc
    uv run python scripts/collect_all.py --target expc
"""

import argparse
import asyncio
import sys

import structlog

structlog.configure(
    processors=[
        structlog.dev.ConsoleRenderer(),
    ],
)
logger = structlog.get_logger()


async def collect_laws() -> None:
    """법령 데이터를 수집한다."""
    from lawtutor.collectors.law_collector import LawCollector

    async with LawCollector() as collector:
        results = await collector.collect_target_laws()
        logger.info("law_done", count=len(results))


async def collect_precedents(max_pages: int = 5) -> None:
    """판례 데이터를 수집한다."""
    from lawtutor.collectors.prec_collector import PrecCollector

    async with PrecCollector() as collector:
        results = await collector.collect_all(max_pages_per_keyword=max_pages)
        logger.info("prec_done", count=len(results))


async def collect_decisions(max_pages: int = 5) -> None:
    """헌재결정례 데이터를 수집한다."""
    from lawtutor.collectors.detc_collector import DetcCollector

    async with DetcCollector() as collector:
        results = await collector.collect_all(max_pages_per_keyword=max_pages)
        logger.info("detc_done", count=len(results))


async def collect_interpretations(max_pages: int = 5) -> None:
    """법령해석례 데이터를 수집한다."""
    from lawtutor.collectors.expc_collector import ExpcCollector

    async with ExpcCollector() as collector:
        results = await collector.collect_all(max_pages_per_keyword=max_pages)
        logger.info("expc_done", count=len(results))


TARGETS = {
    "law": collect_laws,
    "prec": collect_precedents,
    "detc": collect_decisions,
    "expc": collect_interpretations,
}


async def main(targets: list[str], max_pages: int) -> None:
    """선택된 타겟의 데이터를 수집한다."""
    for target in targets:
        logger.info("starting_collection", target=target)
        func = TARGETS[target]
        if target == "law":
            await func()
        else:
            await func(max_pages=max_pages)
        logger.info("finished_collection", target=target)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="국가법령정보센터 데이터 수집")
    parser.add_argument(
        "--target",
        choices=["all", *TARGETS.keys()],
        default="all",
        help="수집할 데이터 타겟 (기본: all)",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=5,
        help="키워드당 최대 수집 페이지 수 (기본: 5)",
    )
    args = parser.parse_args()

    if args.target == "all":
        target_list = list(TARGETS.keys())
    else:
        target_list = [args.target]

    try:
        asyncio.run(main(target_list, args.max_pages))
    except KeyboardInterrupt:
        logger.info("collection_interrupted")
        sys.exit(1)
