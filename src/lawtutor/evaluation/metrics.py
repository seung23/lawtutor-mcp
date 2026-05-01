"""검색 평가 메트릭.

본 시스템은 LLM이 없으므로 검색 정확도 위주로 평가한다.
- Retrieval Recall@K: 정답 문서가 상위 K개에 포함된 비율
- MRR (Mean Reciprocal Rank): 첫 정답 문서의 순위 역수 평균
- 메타데이터 무결성 비율: 필수 메타데이터 필드가 모두 존재하는 비율
"""


def retrieval_recall_at_k(
    retrieved: list[dict],
    expected_articles: list[str],
    expected_case_nos: list[str],
) -> float:
    """상위 K개 검색 결과에 정답이 포함된 비율을 계산한다.

    Args:
        retrieved: 검색된 결과 리스트 (각 결과는 metadata dict 포함)
        expected_articles: 정답 조문 리스트 (예: ["행정절차법 제21조"])
        expected_case_nos: 정답 사건번호 리스트

    Returns:
        recall 값 (0.0 ~ 1.0). 정답이 없으면 1.0 (해당 없음).
    """
    expected = set()
    for art in expected_articles:
        expected.add(("article", art))
    for case_no in expected_case_nos:
        expected.add(("case_no", case_no))

    if not expected:
        return 1.0  # 정답이 명시되지 않은 경우 recall 측정 불가

    found = set()
    for result in retrieved:
        meta = result.get("metadata", {})
        # 조문 매칭: "{법령명} 제{조문번호}조"
        law_name = meta.get("law_name", "")
        article_no = meta.get("article_no", "")
        if law_name and article_no:
            article_key = f"{law_name} 제{article_no}조"
            if ("article", article_key) in expected:
                found.add(("article", article_key))

        # 사건번호 매칭
        case_no = meta.get("case_no", "")
        if case_no and ("case_no", case_no) in expected:
            found.add(("case_no", case_no))

    return len(found) / len(expected)


def reciprocal_rank(
    retrieved: list[dict],
    expected_articles: list[str],
    expected_case_nos: list[str],
) -> float:
    """첫 정답 결과의 순위 역수를 계산한다.

    Args:
        retrieved: 검색된 결과 리스트
        expected_articles: 정답 조문 리스트
        expected_case_nos: 정답 사건번호 리스트

    Returns:
        1/rank (첫 정답의 순위 역수). 정답이 없으면 1.0.
        매칭 결과 없으면 0.0.
    """
    expected_arts = {art for art in expected_articles}
    expected_cases = {cn for cn in expected_case_nos}

    if not expected_arts and not expected_cases:
        return 1.0

    for i, result in enumerate(retrieved, start=1):
        meta = result.get("metadata", {})

        law_name = meta.get("law_name", "")
        article_no = meta.get("article_no", "")
        if law_name and article_no:
            article_key = f"{law_name} 제{article_no}조"
            if article_key in expected_arts:
                return 1.0 / i

        case_no = meta.get("case_no", "")
        if case_no and case_no in expected_cases:
            return 1.0 / i

    return 0.0


def metadata_integrity_rate(
    retrieved: list[dict],
    required_fields: list[str],
) -> float:
    """검색 결과의 메타데이터 무결성 비율을 계산한다.

    Args:
        retrieved: 검색된 결과 리스트
        required_fields: 반드시 존재해야 하는 메타데이터 필드 리스트

    Returns:
        무결성 비율 (0.0 ~ 1.0). 결과가 없으면 1.0.
    """
    if not retrieved:
        return 1.0

    complete_count = 0
    for result in retrieved:
        meta = result.get("metadata", {})
        if all(meta.get(field) for field in required_fields):
            complete_count += 1

    return complete_count / len(retrieved)


def compute_aggregate_metrics(
    per_item_results: list[dict],
) -> dict:
    """전체 평가 항목의 집계 메트릭을 계산한다.

    Args:
        per_item_results: 각 항목별 메트릭 딕셔너리 리스트
            각 항목: {"recall": float, "rr": float, "integrity": float}

    Returns:
        집계 메트릭 딕셔너리
    """
    n = len(per_item_results)
    if n == 0:
        return {
            "recall_at_k": 0.0,
            "mrr": 0.0,
            "metadata_integrity": 0.0,
            "total_items": 0,
        }

    avg_recall = sum(r["recall"] for r in per_item_results) / n
    avg_rr = sum(r["rr"] for r in per_item_results) / n
    avg_integrity = sum(r["integrity"] for r in per_item_results) / n

    return {
        "recall_at_k": round(avg_recall, 4),
        "mrr": round(avg_rr, 4),
        "metadata_integrity": round(avg_integrity, 4),
        "total_items": n,
    }
