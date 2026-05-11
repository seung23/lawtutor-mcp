"""전체 데이터 수집 스크립트.

국가법령정보센터의 모든 데이터를 빈 쿼리 + 페이지네이션으로 수집한다.
기존 collect_all.py는 키워드 기반이라 일부만 수집되지만,
이 스크립트는 전체 목록을 페이지네이션하여 모든 데이터를 수집한다.

사용법:
    # 전체 수집 (4개 타겟 순차)
    uv run python scripts/collect_full.py --target all

    # 특정 타겟만
    uv run python scripts/collect_full.py --target prec
    uv run python scripts/collect_full.py --target detc
    uv run python scripts/collect_full.py --target expc
    uv run python scripts/collect_full.py --target law

    # 이미 수집된 ID 스킵 (이어받기)
    uv run python scripts/collect_full.py --target prec --resume
"""

import argparse
import asyncio
import sys
from pathlib import Path

import structlog

structlog.configure(
    processors=[
        structlog.dev.ConsoleRenderer(),
    ],
)
logger = structlog.get_logger()


def _find_existing_ids(raw_dir: Path, target: str) -> set[str]:
    """이미 수집된 detail XML의 ID를 추출한다."""
    ids: set[str] = set()
    target_dir = raw_dir / target
    if not target_dir.exists():
        return ids
    for date_dir in target_dir.iterdir():
        if not date_dir.is_dir():
            continue
        for f in date_dir.glob("detail_*.xml"):
            # detail_12345.xml → 12345
            stem = f.stem.replace("detail_", "")
            if stem:
                ids.add(stem)
    return ids


async def collect_full_prec(resume: bool = False) -> None:
    """판례 전체를 수집한다."""
    from lawtutor.collectors.prec_collector import PrecCollector
    from lawtutor.config import settings

    seen_ids: set[str] = set()
    if resume:
        seen_ids = _find_existing_ids(settings.data_raw_dir, "prec")
        logger.info("resume_mode", existing=len(seen_ids))

    async with PrecCollector() as collector:
        # 1단계: 전체 건수 확인
        _, total = await collector.search_precedents("", display=1, page=1)
        logger.info("prec_total", total=total)

        display = 100
        total_pages = (total // display) + 1
        collected = 0
        skipped = 0

        for page in range(1, total_pages + 1):
            try:
                results, _ = await collector.search_precedents("", display=display, page=page)
            except Exception as e:
                logger.warning("page_failed", page=page, error=str(e))
                await asyncio.sleep(5)
                continue

            if not results:
                break

            for result in results:
                prec_id = result["판례일련번호"]
                if not prec_id or prec_id in seen_ids:
                    skipped += 1
                    continue

                seen_ids.add(prec_id)
                try:
                    await collector.fetch_precedent_detail(prec_id)
                    collected += 1
                except Exception as e:
                    logger.warning("detail_failed", prec_id=prec_id, error=str(e))

                await asyncio.sleep(0.3)

            if page % 50 == 0:
                logger.info("prec_progress", page=page, total_pages=total_pages,
                            collected=collected, skipped=skipped)
            await asyncio.sleep(0.2)

        logger.info("prec_collection_complete", collected=collected, skipped=skipped)


async def collect_full_detc(resume: bool = False) -> None:
    """헌재결정례 전체를 수집한다."""
    from lawtutor.collectors.detc_collector import DetcCollector
    from lawtutor.config import settings

    seen_ids: set[str] = set()
    if resume:
        seen_ids = _find_existing_ids(settings.data_raw_dir, "detc")
        logger.info("resume_mode", existing=len(seen_ids))

    async with DetcCollector() as collector:
        _, total = await collector.search_decisions("", display=1, page=1)
        logger.info("detc_total", total=total)

        display = 100
        total_pages = (total // display) + 1
        collected = 0
        skipped = 0

        for page in range(1, total_pages + 1):
            try:
                results, _ = await collector.search_decisions("", display=display, page=page)
            except Exception as e:
                logger.warning("page_failed", page=page, error=str(e))
                await asyncio.sleep(5)
                continue

            if not results:
                break

            for result in results:
                detc_id = result["헌재결정례일련번호"]
                if not detc_id or detc_id in seen_ids:
                    skipped += 1
                    continue

                seen_ids.add(detc_id)
                try:
                    await collector.fetch_decision_detail(detc_id)
                    collected += 1
                except Exception as e:
                    logger.warning("detail_failed", detc_id=detc_id, error=str(e))

                await asyncio.sleep(0.3)

            if page % 50 == 0:
                logger.info("detc_progress", page=page, total_pages=total_pages,
                            collected=collected, skipped=skipped)
            await asyncio.sleep(0.2)

        logger.info("detc_collection_complete", collected=collected, skipped=skipped)


async def collect_full_expc(resume: bool = False) -> None:
    """법령해석례 전체를 수집한다."""
    from lawtutor.collectors.expc_collector import ExpcCollector
    from lawtutor.config import settings

    seen_ids: set[str] = set()
    if resume:
        seen_ids = _find_existing_ids(settings.data_raw_dir, "expc")
        logger.info("resume_mode", existing=len(seen_ids))

    async with ExpcCollector() as collector:
        _, total = await collector.search_interpretations("", display=1, page=1)
        logger.info("expc_total", total=total)

        display = 100
        total_pages = (total // display) + 1
        collected = 0
        skipped = 0

        for page in range(1, total_pages + 1):
            try:
                results, _ = await collector.search_interpretations("", display=display, page=page)
            except Exception as e:
                logger.warning("page_failed", page=page, error=str(e))
                await asyncio.sleep(5)
                continue

            if not results:
                break

            for result in results:
                expc_id = result["법령해석례일련번호"]
                if not expc_id or expc_id in seen_ids:
                    skipped += 1
                    continue

                seen_ids.add(expc_id)
                try:
                    await collector.fetch_interpretation_detail(expc_id)
                    collected += 1
                except Exception as e:
                    logger.warning("detail_failed", expc_id=expc_id, error=str(e))

                await asyncio.sleep(0.3)

            if page % 10 == 0:
                logger.info("expc_progress", page=page, total_pages=total_pages,
                            collected=collected, skipped=skipped)
            await asyncio.sleep(0.2)

        logger.info("expc_collection_complete", collected=collected, skipped=skipped)


async def collect_full_law(resume: bool = False) -> None:
    """법령 전체를 수집한다."""
    from lawtutor.collectors.law_collector import LawCollector
    from lawtutor.config import settings

    seen_ids: set[str] = set()
    if resume:
        seen_ids = _find_existing_ids(settings.data_raw_dir, "law")
        logger.info("resume_mode", existing=len(seen_ids))

    async with LawCollector() as collector:
        results = await collector.search_laws("", display=1, page=1)
        # 법령 검색은 totalCnt를 별도로 반환하지 않으므로 직접 확인
        from lawtutor.constants import LAW_API_SEARCH_PATH
        raw = await collector._request(LAW_API_SEARCH_PATH, {
            "target": "law", "query": "", "display": 1, "page": 1,
        })
        root = collector._parse_xml(raw)
        total = collector._get_int(root, "totalCnt")
        logger.info("law_total", total=total)

        display = 100
        total_pages = (total // display) + 1
        collected = 0
        skipped = 0

        for page in range(1, total_pages + 1):
            try:
                results = await collector.search_laws("", display=display, page=page)
            except Exception as e:
                logger.warning("page_failed", page=page, error=str(e))
                await asyncio.sleep(5)
                continue

            if not results:
                break

            for result in results:
                mst = result["법령일련번호"]
                if not mst or mst in seen_ids:
                    skipped += 1
                    continue

                seen_ids.add(mst)
                try:
                    await collector.fetch_law_detail(mst)
                    collected += 1
                except Exception as e:
                    logger.warning("detail_failed", mst=mst, error=str(e))

                await asyncio.sleep(0.3)

            if page % 10 == 0:
                logger.info("law_progress", page=page, total_pages=total_pages,
                            collected=collected, skipped=skipped)
            await asyncio.sleep(0.2)

        logger.info("law_collection_complete", collected=collected, skipped=skipped)


TARGETS = {
    "law": collect_full_law,
    "prec": collect_full_prec,
    "detc": collect_full_detc,
    "expc": collect_full_expc,
}


async def main(targets: list[str], resume: bool) -> None:
    """선택된 타겟의 데이터를 전체 수집한다."""
    for target in targets:
        logger.info("starting_full_collection", target=target)
        await TARGETS[target](resume=resume)
        logger.info("finished_full_collection", target=target)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="국가법령정보센터 전체 데이터 수집")
    parser.add_argument(
        "--target",
        choices=["all", *TARGETS.keys()],
        default="all",
        help="수집할 데이터 타겟 (기본: all)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="이미 수집된 파일 스킵 (이어받기 모드)",
    )
    args = parser.parse_args()

    if args.target == "all":
        target_list = list(TARGETS.keys())
    else:
        target_list = [args.target]

    try:
        asyncio.run(main(target_list, args.resume))
    except KeyboardInterrupt:
        logger.info("collection_interrupted")
        sys.exit(1)
