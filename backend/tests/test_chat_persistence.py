from app.core.chat_persistence import ChatPersistence, ChatPersistenceConfig


def test_chat_persistence_save_and_list(tmp_path):
    db_file = tmp_path / "chat_messages.db"
    store = ChatPersistence(ChatPersistenceConfig(db_path=str(db_file)))
    store.save_message(
        message_id="m1",
        session_id="s1",
        conversation_id="c1",
        role="user",
        text="hola",
        created_at=1000,
        meta={"a": 1},
    )
    store.save_message(
        message_id="m2",
        session_id="s1",
        conversation_id="c1",
        role="assistant",
        text="respuesta",
        created_at=2000,
        meta={"b": 2},
    )
    items = store.list_messages(session_id="s1", conversation_id="c1", limit=10)
    assert len(items) == 2
    assert items[0]["id"] == "m1"
    assert items[1]["id"] == "m2"
    assert items[0]["meta"]["a"] == 1


def test_chat_persistence_pagination(tmp_path):
    db_file = tmp_path / "chat_messages_page.db"
    store = ChatPersistence(ChatPersistenceConfig(db_path=str(db_file)))
    for idx in range(5):
        store.save_message(
            message_id=f"m{idx}",
            session_id="s2",
            conversation_id="c2",
            role="user",
            text=f"msg-{idx}",
            created_at=1000 + idx,
            meta={},
        )
    page = store.list_messages(session_id="s2", conversation_id="c2", before_created_at=1004, limit=2)
    assert [item["id"] for item in page] == ["m2", "m3"]
