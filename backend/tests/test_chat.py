

def test_인메모리_로그는_상한을_넘지_않는다():
    from app.chat import MAX_MEM_MESSAGES, ChatStore

    store = ChatStore()
    for i in range(MAX_MEM_MESSAGES + 20):
        store.append("c1", "user", str(i))
    kept = store.list("c1")
    assert len(kept) == MAX_MEM_MESSAGES
    assert kept[-1].text == str(MAX_MEM_MESSAGES + 19)


def test_없는_코스는_빈_목록이고_항목을_만들지_않는다():
    from app.chat import ChatStore

    store = ChatStore()
    assert store.list("nope") == []
    assert store._mem == {}
