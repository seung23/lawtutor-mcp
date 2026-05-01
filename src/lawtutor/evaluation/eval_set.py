"""평가셋 데이터 모델 및 로더."""

import json
from pathlib import Path

from pydantic import BaseModel


class EvalItem(BaseModel):
    """평가셋 개별 항목.

    Attributes:
        question: 평가 질문
        category: 카테고리 (행정법, 헌법 등)
        difficulty: 난이도 (하, 중, 상)
        tool: 호출되어야 할 MCP 도구명
        expected_articles: 정답에 포함되어야 할 조문 (법령명 제N조 형태)
        expected_case_nos: 정답에 포함되어야 할 사건번호
    """

    question: str
    category: str
    difficulty: str
    tool: str
    expected_articles: list[str] = []
    expected_case_nos: list[str] = []


def load_eval_set(path: Path) -> list[EvalItem]:
    """JSONL 파일에서 평가셋을 로드한다.

    Args:
        path: 평가셋 JSONL 파일 경로

    Returns:
        EvalItem 리스트
    """
    items: list[EvalItem] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            items.append(EvalItem.model_validate_json(line))
    return items


def save_eval_item(path: Path, item: EvalItem) -> None:
    """평가 항목을 JSONL 파일에 추가한다.

    Args:
        path: 평가셋 JSONL 파일 경로
        item: 추가할 평가 항목
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(item.model_dump_json(ensure_ascii=False) + "\n")
