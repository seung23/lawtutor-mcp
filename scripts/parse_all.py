"""파싱 통합 스크립트.

data/raw/ 의 XML 원본을 파싱하여 data/parsed/ 에 JSON으로 저장한다.

사용법:
    uv run python scripts/parse_all.py
    uv run python scripts/parse_all.py --target law
"""

import argparse
import json
from pathlib import Path

import structlog

from lawtutor.config import settings

structlog.configure(processors=[structlog.dev.ConsoleRenderer()])
logger = structlog.get_logger()


def parse_laws() -> None:
    """법령 raw XML을 파싱하여 JSON으로 저장한다."""
    from lawtutor.parsers.law_parser import parse_law_detail

    raw_dir = settings.data_raw_dir / "law"
    out_dir = settings.data_parsed_dir / "law"
    out_dir.mkdir(parents=True, exist_ok=True)

    detail_files = list(raw_dir.rglob("detail_*.xml"))
    logger.info("parsing_laws", file_count=len(detail_files))

    for xml_path in detail_files:
        result = parse_law_detail(xml_path)
        if result is None:
            logger.warning("parse_failed", path=str(xml_path))
            continue

        out_path = out_dir / f"{result.meta.law_mst}.json"
        out_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        logger.info("parsed_law", name=result.meta.law_name, articles=len(result.articles))


def parse_precedents() -> None:
    """판례 raw XML을 파싱하여 JSON으로 저장한다."""
    from lawtutor.parsers.prec_parser import parse_precedent_detail

    raw_dir = settings.data_raw_dir / "prec"
    out_dir = settings.data_parsed_dir / "prec"
    out_dir.mkdir(parents=True, exist_ok=True)

    detail_files = list(raw_dir.rglob("detail_*.xml"))
    logger.info("parsing_precedents", file_count=len(detail_files))

    parsed_count = 0
    for xml_path in detail_files:
        result = parse_precedent_detail(xml_path)
        if result is None:
            continue

        out_path = out_dir / f"{result.case_id}.json"
        out_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        parsed_count += 1

    logger.info("parsed_precedents", count=parsed_count)


def parse_decisions() -> None:
    """헌재결정례 raw XML을 파싱하여 JSON으로 저장한다."""
    from lawtutor.parsers.detc_parser import parse_decision_detail

    raw_dir = settings.data_raw_dir / "detc"
    out_dir = settings.data_parsed_dir / "detc"
    out_dir.mkdir(parents=True, exist_ok=True)

    detail_files = list(raw_dir.rglob("detail_*.xml"))
    logger.info("parsing_decisions", file_count=len(detail_files))

    parsed_count = 0
    for xml_path in detail_files:
        result = parse_decision_detail(xml_path)
        if result is None:
            continue

        out_path = out_dir / f"{result.decision_id}.json"
        out_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        parsed_count += 1

    logger.info("parsed_decisions", count=parsed_count)


def parse_interpretations() -> None:
    """법령해석례 raw XML을 파싱하여 JSON으로 저장한다."""
    from lawtutor.parsers.expc_parser import parse_interpretation_detail

    raw_dir = settings.data_raw_dir / "expc"
    out_dir = settings.data_parsed_dir / "expc"
    out_dir.mkdir(parents=True, exist_ok=True)

    detail_files = list(raw_dir.rglob("detail_*.xml"))
    logger.info("parsing_interpretations", file_count=len(detail_files))

    parsed_count = 0
    for xml_path in detail_files:
        result = parse_interpretation_detail(xml_path)
        if result is None:
            continue

        out_path = out_dir / f"{result.interpretation_id}.json"
        out_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        parsed_count += 1

    logger.info("parsed_interpretations", count=parsed_count)


TARGETS = {
    "law": parse_laws,
    "prec": parse_precedents,
    "detc": parse_decisions,
    "expc": parse_interpretations,
}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="raw XML → parsed JSON 변환")
    parser.add_argument(
        "--target",
        choices=["all", *TARGETS.keys()],
        default="all",
        help="파싱할 데이터 타겟 (기본: all)",
    )
    args = parser.parse_args()

    if args.target == "all":
        target_list = list(TARGETS.keys())
    else:
        target_list = [args.target]

    for target in target_list:
        logger.info("starting_parse", target=target)
        TARGETS[target]()
        logger.info("finished_parse", target=target)
