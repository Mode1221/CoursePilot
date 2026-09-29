

def test_북마크_목록도_상한이_있다():
    from app.bookmarks import BookmarkStore

    store = BookmarkStore()
    for i in range(5):
        store.add("u-limit", f"c{i}")
    assert len(store.list_course_ids("u-limit", limit=2)) == 2
    assert len(store.list_course_ids("u-limit")) == 5
