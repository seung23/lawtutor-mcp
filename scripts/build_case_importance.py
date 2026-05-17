"""판례/결정례 중요도 데이터를 구축한다.

parsed 데이터에서 두 가지 시그널을 추출한다:
1. 피인용수 (citation_counts): 각 판례가 다른 판례에 몇 번 참조되었는지 역집계
2. 전원합의체 (full_court_cases): 전원합의체/전원재판부 판결 목록

결과는 data/case_importance.json으로 저장한다.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

# ---------------------------------------------------------------------------
# 경로
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PARSED_PREC_DIR = PROJECT_ROOT / "data" / "parsed" / "prec"
PARSED_DETC_DIR = PROJECT_ROOT / "data" / "parsed" / "detc"
OUTPUT_PATH = PROJECT_ROOT / "data" / "case_importance.json"

# ---------------------------------------------------------------------------
# 사건번호 추출 정규식
# ---------------------------------------------------------------------------
# 한국 사건번호 패턴: 2~4자리 연도 + 1~4자리 한글(사건유형) + 숫자(일련번호)
# 예: 83누699, 2003헌가17, 84감도65, 95다38677
CASE_NO_RE = re.compile(r"\d{2,4}[가-힣]{1,4}\d+")

# 전원합의체/전원재판부 판별 정규식
FULL_COURT_RE = re.compile(r"전원합의체|전원재판부")


def extract_case_numbers(text: str) -> list[str]:
    """참조판례 텍스트에서 사건번호를 추출한다."""
    if not text or not text.strip():
        return []
    return CASE_NO_RE.findall(text)


def is_full_court(texts: list[str]) -> bool:
    """텍스트 목록에서 전원합의체/전원재판부 여부를 판별한다."""
    for text in texts:
        if text and FULL_COURT_RE.search(text):
            return True
    return False


def process_precedents(
    prec_dir: Path,
) -> tuple[Counter[str], set[str], set[str]]:
    """판례 파일을 순회하며 인용 관계와 전원합의체를 추출한다.

    Returns:
        (citation_counter, full_court_set, all_case_nos)
        - citation_counter: {피인용 사건번호: 인용 횟수}
        - full_court_set: 전원합의체 사건번호 집합
        - all_case_nos: DB에 존재하는 모든 사건번호 집합
    """
    citation_counter: Counter[str] = Counter()
    full_court_set: set[str] = set()
    all_case_nos: set[str] = set()

    files = sorted(prec_dir.glob("*.json"))
    print(f"  판례 파일 수: {len(files)}")

    for f in files:
        with open(f, encoding="utf-8") as fh:
            data = json.load(fh)

        own_case_no = data.get("case_no", "")
        all_case_nos.add(own_case_no)

        # --- 피인용수: referenced_cases에서 사건번호 추출 ---
        referenced_text = data.get("referenced_cases", "") or ""
        cited_nos = extract_case_numbers(referenced_text)

        for cited_no in cited_nos:
            # 자기 자신을 인용한 경우 제외
            if cited_no != own_case_no:
                citation_counter[cited_no] += 1

        # --- 전원합의체 판별 ---
        text_fields = [
            data.get("case_name", ""),
            data.get("holding", ""),
            data.get("summary", ""),
            data.get("reasoning", ""),
        ]
        if is_full_court(text_fields):
            full_court_set.add(own_case_no)

    return citation_counter, full_court_set, all_case_nos


def process_decisions(
    detc_dir: Path,
) -> tuple[Counter[str], set[str], set[str]]:
    """헌재결정례 파일을 순회하며 인용 관계와 전원재판부를 추출한다.

    Returns:
        (citation_counter, full_court_set, all_case_nos)
    """
    citation_counter: Counter[str] = Counter()
    full_court_set: set[str] = set()
    all_case_nos: set[str] = set()

    files = sorted(detc_dir.glob("*.json"))
    print(f"  결정례 파일 수: {len(files)}")

    for f in files:
        with open(f, encoding="utf-8") as fh:
            data = json.load(fh)

        own_case_no = data.get("case_no", "")
        all_case_nos.add(own_case_no)

        # --- 피인용수: referenced_cases에서 사건번호 추출 ---
        referenced_text = data.get("referenced_cases", "") or ""
        cited_nos = extract_case_numbers(referenced_text)

        for cited_no in cited_nos:
            if cited_no != own_case_no:
                citation_counter[cited_no] += 1

        # --- 전원재판부 판별 ---
        text_fields = [
            data.get("case_name", ""),
            data.get("holding", ""),
            data.get("summary", ""),
            data.get("full_text", ""),
        ]
        if is_full_court(text_fields):
            full_court_set.add(own_case_no)

    return citation_counter, full_court_set, all_case_nos


def main() -> None:
    """메인 실행."""
    print("=" * 60)
    print("판례/결정례 중요도 데이터 구축")
    print("=" * 60)

    # --- 1. 판례 처리 ---
    print("\n[1/3] 판례 파일 처리 중...")
    prec_citations, prec_full_court, prec_case_nos = process_precedents(
        PARSED_PREC_DIR
    )

    # --- 2. 결정례 처리 ---
    print("\n[2/3] 결정례 파일 처리 중...")
    detc_citations, detc_full_court, detc_case_nos = process_decisions(
        PARSED_DETC_DIR
    )

    # --- 3. 통합 ---
    print("\n[3/3] 결과 통합 중...")

    # 피인용수: 판례→판례, 판례→결정례, 결정례→결정례, 결정례→판례 모두 합산
    total_citations: Counter[str] = Counter()
    total_citations.update(prec_citations)
    total_citations.update(detc_citations)

    # DB에 존재하는 사건번호만 필터링 (DB에 없는 사건번호의 피인용수는 의미 없음)
    all_known_case_nos = prec_case_nos | detc_case_nos
    filtered_citations = {
        case_no: count
        for case_no, count in total_citations.items()
        if case_no in all_known_case_nos
    }

    # 전원합의체: 판례 + 결정례 합산
    all_full_court = prec_full_court | detc_full_court

    # --- 통계 출력 ---
    print(f"\n{'='*60}")
    print("결과 요약")
    print(f"{'='*60}")
    print(f"  DB 사건번호 (판례): {len(prec_case_nos):,}")
    print(f"  DB 사건번호 (결정례): {len(detc_case_nos):,}")
    print(f"  총 인용 관계 (원본): {sum(total_citations.values()):,}건")
    print(f"  DB 매칭 인용 관계: {sum(filtered_citations.values()):,}건")
    print(f"  피인용 1회 이상 사건: {len(filtered_citations):,}건")
    print(f"  전원합의체/전원재판부: {len(all_full_court):,}건")

    # 피인용수 상위 20
    if filtered_citations:
        top20 = sorted(
            filtered_citations.items(), key=lambda x: x[1], reverse=True
        )[:20]
        print(f"\n  피인용수 상위 20:")
        for case_no, count in top20:
            fc_mark = " [전원]" if case_no in all_full_court else ""
            print(f"    {case_no}: {count}회{fc_mark}")

    # 피인용수 분포
    counts = list(filtered_citations.values())
    if counts:
        import statistics

        print(f"\n  피인용수 분포:")
        print(f"    최대: {max(counts)}")
        print(f"    평균: {statistics.mean(counts):.1f}")
        print(f"    중앙값: {statistics.median(counts):.0f}")
        print(f"    표준편차: {statistics.stdev(counts):.1f}")
        # 구간별 분포
        brackets = [(1, 1), (2, 5), (6, 10), (11, 50), (51, 100), (101, None)]
        for low, high in brackets:
            if high is None:
                n = sum(1 for c in counts if c >= low)
                label = f"{low}+"
            else:
                n = sum(1 for c in counts if low <= c <= high)
                label = f"{low}-{high}"
            print(f"    {label:>8}회: {n:,}건")

    # --- 저장 ---
    output = {
        "citation_counts": filtered_citations,
        "full_court_cases": sorted(all_full_court),
        "stats": {
            "total_prec_cases": len(prec_case_nos),
            "total_detc_cases": len(detc_case_nos),
            "total_citation_edges": sum(filtered_citations.values()),
            "cases_with_citations": len(filtered_citations),
            "full_court_count": len(all_full_court),
        },
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(output, fh, ensure_ascii=False, indent=2)

    print(f"\n  저장 완료: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
