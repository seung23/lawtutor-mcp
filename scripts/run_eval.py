"""평가 실행 스크립트.

사용법:
    uv run python scripts/run_eval.py
    uv run python scripts/run_eval.py --eval-set data/eval/eval_set_v1.jsonl
    uv run python scripts/run_eval.py --top-k 10
    uv run python scripts/run_eval.py --compare-with data/eval_results/20260501_120000.json
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

from lawtutor.config import PROJECT_ROOT
from lawtutor.constants import SEARCH_DEFAULT_TOP_K
from lawtutor.embeddings.bge_m3 import BgeM3Embedder
from lawtutor.evaluation.eval_set import EvalItem, load_eval_set
from lawtutor.evaluation.metrics import (
    compute_aggregate_metrics,
    metadata_integrity_rate,
    reciprocal_rank,
    retrieval_recall_at_k,
)
from lawtutor.retrieval.retriever import Retriever
from lawtutor.vector_store.client import VectorStore

# 도구명 → Retriever 메서드 + 필수 메타데이터 필드 매핑
TOOL_CONFIG: dict[str, dict] = {
    "search_law": {
        "method": "search_laws",
        "required_meta": ["law_name", "article_no", "effective_date"],
    },
    "search_precedent": {
        "method": "search_precedents",
        "required_meta": ["case_no", "court"],
    },
    "search_constitutional_decision": {
        "method": "search_decisions",
        "required_meta": ["case_no"],
    },
    "search_legal_interpretation": {
        "method": "search_interpretations",
        "required_meta": [],
    },
    "fetch_article_by_number": {
        "method": "fetch_by_article",
        "required_meta": ["law_name", "article_no"],
    },
    "fetch_case_by_number": {
        "method": "fetch_by_case_no",
        "required_meta": ["case_no"],
    },
}


def _parse_article_ref(ref: str) -> tuple[str, str]:
    """'행정절차법 제21조' 형태에서 법령명과 조문번호를 추출한다."""
    match = re.match(r"(.+?)\s*제(\d+)조", ref)
    if match:
        return match.group(1), match.group(2)
    return ref, ""


def _call_tool(
    retriever: Retriever,
    item: EvalItem,
    top_k: int,
) -> list[dict]:
    """평가 항목의 도구를 호출하고 결과를 반환한다."""
    tool = item.tool
    config = TOOL_CONFIG.get(tool)
    if not config:
        print(f"  [WARN] 알 수 없는 도구: {tool}")
        return []

    method_name = config["method"]

    if tool == "fetch_article_by_number" and item.expected_articles:
        law_name, article_no = _parse_article_ref(item.expected_articles[0])
        return retriever.fetch_by_article(law_name, article_no)

    if tool == "fetch_case_by_number" and item.expected_case_nos:
        return retriever.fetch_by_case_no(item.expected_case_nos[0])

    method = getattr(retriever, method_name)
    return method(item.question, top_k)


def _format_result_for_metrics(raw_result: dict) -> dict:
    """Qdrant 검색 결과를 메트릭 함수가 기대하는 형태로 변환한다."""
    payload = raw_result.get("payload", {})
    return {
        "metadata": payload,
        "score": raw_result.get("score", 0.0),
    }


def run_evaluation(
    eval_path: Path,
    top_k: int,
) -> dict:
    """전체 평가를 실행한다."""
    print(f"평가셋 로드: {eval_path}")
    items = load_eval_set(eval_path)
    print(f"  총 {len(items)}개 항목\n")

    print("모델 및 벡터 스토어 초기화...")
    embedder = BgeM3Embedder()
    store = VectorStore()
    retriever = Retriever(embedder, store)
    print("  초기화 완료\n")

    per_item_results: list[dict] = []
    details: list[dict] = []

    for i, item in enumerate(items, start=1):
        config = TOOL_CONFIG.get(item.tool, {})
        required_meta = config.get("required_meta", [])

        print(f"[{i}/{len(items)}] {item.question}")
        print(f"  도구: {item.tool}")

        raw_results = _call_tool(retriever, item, top_k)
        results = [_format_result_for_metrics(r) for r in raw_results]

        recall = retrieval_recall_at_k(
            results, item.expected_articles, item.expected_case_nos,
        )
        rr = reciprocal_rank(
            results, item.expected_articles, item.expected_case_nos,
        )
        integrity = metadata_integrity_rate(results, required_meta)

        print(f"  결과: {len(results)}건 | recall={recall:.2f} | RR={rr:.2f} | integrity={integrity:.2f}")

        per_item_results.append({
            "recall": recall,
            "rr": rr,
            "integrity": integrity,
        })

        details.append({
            "question": item.question,
            "tool": item.tool,
            "category": item.category,
            "difficulty": item.difficulty,
            "num_results": len(results),
            "recall": recall,
            "rr": rr,
            "integrity": integrity,
            "expected_articles": item.expected_articles,
            "expected_case_nos": item.expected_case_nos,
        })

    aggregate = compute_aggregate_metrics(per_item_results)

    # 콘솔 요약
    print("\n" + "=" * 60)
    print("평가 결과 요약")
    print("=" * 60)
    print(f"  총 항목 수:          {aggregate['total_items']}")
    print(f"  Recall@{top_k}:          {aggregate['recall_at_k']:.4f}")
    print(f"  MRR:                 {aggregate['mrr']:.4f}")
    print(f"  메타데이터 무결성:   {aggregate['metadata_integrity']:.4f}")
    print(f"  목표 (recall@5):     0.8000")
    print("=" * 60)

    if aggregate["recall_at_k"] >= 0.8:
        print("  --> 목표 달성!")
    else:
        print(f"  --> 목표 미달 (차이: {0.8 - aggregate['recall_at_k']:.4f})")

    return {
        "timestamp": datetime.now().isoformat(),
        "eval_set": str(eval_path),
        "top_k": top_k,
        "aggregate": aggregate,
        "details": details,
    }


def main() -> None:
    """평가를 실행한다."""
    parser = argparse.ArgumentParser(description="LawTutor 검색 평가")
    parser.add_argument(
        "--eval-set",
        type=Path,
        default=PROJECT_ROOT / "data" / "eval" / "eval_set_v1.jsonl",
        help="평가셋 파일 경로",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=SEARCH_DEFAULT_TOP_K,
        help=f"검색 결과 수 (기본 {SEARCH_DEFAULT_TOP_K})",
    )
    parser.add_argument(
        "--compare-with",
        type=Path,
        default=None,
        help="이전 평가 결과와 비교",
    )
    args = parser.parse_args()

    if not args.eval_set.exists():
        print(f"평가셋 파일 없음: {args.eval_set}")
        sys.exit(1)

    report = run_evaluation(args.eval_set, args.top_k)

    # 결과 저장
    results_dir = PROJECT_ROOT / "data" / "eval_results"
    results_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = results_dir / f"{timestamp}.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n결과 저장: {output_path}")

    # 이전 결과와 비교
    if args.compare_with and args.compare_with.exists():
        with open(args.compare_with, encoding="utf-8") as f:
            prev = json.load(f)
        prev_agg = prev["aggregate"]
        curr_agg = report["aggregate"]

        print(f"\n비교 ({args.compare_with.name} → 현재):")
        for key in ["recall_at_k", "mrr", "metadata_integrity"]:
            diff = curr_agg[key] - prev_agg[key]
            sign = "+" if diff >= 0 else ""
            print(f"  {key}: {prev_agg[key]:.4f} → {curr_agg[key]:.4f} ({sign}{diff:.4f})")


if __name__ == "__main__":
    main()
