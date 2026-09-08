from app.pipeline.edit import MATCH_INDEX, parse_edit


def test_remove_by_category():
    cmd = parse_edit("카페 빼줘")
    assert cmd.action == "remove"
    assert cmd.index == MATCH_INDEX
    assert cmd.match == "cafe"


def test_replace_by_category():
    cmd = parse_edit("술집 다른 곳으로")
    assert cmd.action == "replace"
    assert cmd.index == MATCH_INDEX
    assert cmd.match == "bar"


def test_ordinal_still_wins():
    cmd = parse_edit("2번 카페 빼줘")
    assert cmd.index == 1
    assert cmd.match == ""


def test_unrelated_text_is_none():
    assert parse_edit("성수동 저녁 코스 만들어줘").action == "none"
