from app.cooccurrence import CooccurrenceStore


def test_bump_and_affinity_symmetric():
    cs = CooccurrenceStore()
    cs.bump_course(["a", "b", "c"])  # 쌍: ab, ac, bc 각 +1
    assert cs.affinity("a", ["b"]) == 1.0
    assert cs.affinity("b", ["a"]) == 1.0  # 대칭
    assert cs.affinity("a", ["b", "c"]) == 2.0
    assert cs.affinity("a", ["a"]) == 0.0  # 자기 자신 제외


def test_bump_dedups_within_course():
    cs = CooccurrenceStore()
    cs.bump_course(["a", "a", "b"])  # 중복 a 제거 → ab 한 번만
    assert cs.affinity("a", ["b"]) == 1.0


def test_accumulates_over_courses():
    cs = CooccurrenceStore()
    cs.bump_course(["a", "b"])
    cs.bump_course(["a", "b"])
    assert cs.affinity("a", ["b"]) == 2.0


def test_affinity_는_여러_앵커를_합산한다():
    from app.cooccurrence import CooccurrenceStore

    store = CooccurrenceStore()
    store.bump_course(["a", "b", "c"])
    assert store.affinity("a", ["b", "c"]) == 2.0
    assert store.affinity("a", ["a"]) == 0.0
    assert store.affinity("a", []) == 0.0
