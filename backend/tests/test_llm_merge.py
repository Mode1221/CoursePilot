"""LLM 결과와 규칙 파서 결과 병합 규칙."""
from app.pipeline.llm import _to_constraints


def test_규칙_키워드가_LLM_결과에_묻히지_않는다():
    c = _to_constraints({"keywords": ["조용한"]}, "내일 비 온대 홍대에서 놀자")
    assert "실내" in c.keywords
    assert "조용한" in c.keywords


def test_LLM이_준_방문개수를_쓴다():
    c = _to_constraints({"stop_count": 2}, "성수동에서 놀자")
    assert c.stop_count == 2


def test_LLM이_준_제외조건을_쓴다():
    c = _to_constraints({"exclude_keywords": ["술집"]}, "성수동에서 놀자")
    assert c.exclude_keywords == ["술집"]
