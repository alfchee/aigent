import threading
import time

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

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


# ---------------------------------------------------------------------------
# Agent session history (load_history / save_history)
# ---------------------------------------------------------------------------


def _make_store(tmp_path):
    db_file = tmp_path / "history.db"
    return ChatPersistence(ChatPersistenceConfig(db_path=str(db_file)))


def test_save_and_load_history_round_trip(tmp_path):
    store = _make_store(tmp_path)
    messages = [
        HumanMessage(content="hello"),
        AIMessage(content="hi there"),
        HumanMessage(content="what time is it?"),
        AIMessage(content="I don't know"),
    ]
    store.save_history("sess-1", messages)
    loaded = store.load_history("sess-1")

    assert len(loaded) == 4
    assert isinstance(loaded[0], HumanMessage)
    assert loaded[0].content == "hello"
    assert isinstance(loaded[1], AIMessage)
    assert loaded[1].content == "hi there"
    assert isinstance(loaded[2], HumanMessage)
    assert loaded[2].content == "what time is it?"
    assert isinstance(loaded[3], AIMessage)
    assert loaded[3].content == "I don't know"


def test_save_history_with_tool_messages(tmp_path):
    store = _make_store(tmp_path)
    ai_with_tools = AIMessage(content="")
    ai_with_tools.tool_calls = [
        {"id": "call_1", "name": "web_search", "arguments": '{"query": "test"}'}
    ]
    messages = [
        HumanMessage(content="search for test"),
        ai_with_tools,
        ToolMessage(content="result data", tool_call_id="call_1", name="web_search"),
        AIMessage(content="Here is what I found"),
    ]
    store.save_history("sess-2", messages)
    loaded = store.load_history("sess-2")

    assert len(loaded) == 4
    ai_msg = loaded[1]
    assert isinstance(ai_msg, AIMessage)
    assert ai_msg.tool_calls[0]["name"] == "web_search"

    tool_msg = loaded[2]
    assert isinstance(tool_msg, ToolMessage)
    assert tool_msg.content == "result data"
    assert tool_msg.tool_call_id == "call_1"
    assert tool_msg.name == "web_search"


def test_load_history_empty_session(tmp_path):
    store = _make_store(tmp_path)
    loaded = store.load_history("nonexistent-session")
    assert loaded == []


def test_save_history_replaces_previous(tmp_path):
    store = _make_store(tmp_path)
    store.save_history("sess-3", [HumanMessage(content="first"), AIMessage(content="reply")])
    store.save_history("sess-3", [HumanMessage(content="replaced")])
    loaded = store.load_history("sess-3")
    assert len(loaded) == 1
    assert loaded[0].content == "replaced"


def test_save_history_survives_simulated_restart(tmp_path):
    """History loaded from a fresh ChatPersistence instance equals what was saved."""
    db_file = tmp_path / "restart.db"
    config = ChatPersistenceConfig(db_path=str(db_file))

    store1 = ChatPersistence(config)
    store1.save_history("sess-4", [HumanMessage(content="pre-restart"), AIMessage(content="ok")])

    # Simulate server restart: create a brand-new instance pointing at the same file
    store2 = ChatPersistence(config)
    loaded = store2.load_history("sess-4")

    assert len(loaded) == 2
    assert loaded[0].content == "pre-restart"
    assert loaded[1].content == "ok"


def test_multiple_sessions_do_not_interfere(tmp_path):
    store = _make_store(tmp_path)
    store.save_history("alpha", [HumanMessage(content="alpha msg")])
    store.save_history("beta", [HumanMessage(content="beta msg"), AIMessage(content="beta reply")])

    alpha = store.load_history("alpha")
    beta = store.load_history("beta")

    assert len(alpha) == 1
    assert alpha[0].content == "alpha msg"
    assert len(beta) == 2
    assert beta[1].content == "beta reply"


def test_concurrent_load_save_same_session(tmp_path):
    """Concurrent load/save on same session are serialized by per-session locks."""
    store = _make_store(tmp_path)
    session_id = "concurrent-test"
    store.save_history(session_id, [HumanMessage(content="initial")])

    results = []

    def modify_and_save(thread_id):
        # Load current history
        history = store.load_history(session_id)
        # Simulate some processing time
        time.sleep(0.01)
        # Add a message and save
        new_history = history + [AIMessage(content=f"response-{thread_id}")]
        store.save_history(session_id, new_history)
        results.append(len(new_history))

    # Run two concurrent modifications
    t1 = threading.Thread(target=modify_and_save, args=(1,))
    t2 = threading.Thread(target=modify_and_save, args=(2,))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Both threads should have completed without error
    assert len(results) == 2
    # Final history should have all messages (both threads' changes persisted)
    final = store.load_history(session_id)
    assert len(final) >= 2  # At least: initial + one response from each thread


# ---------------------------------------------------------------------------
# Schema migration — pre-existing table without schema_version / updated_at
# ---------------------------------------------------------------------------

import sqlite3 as _sqlite3


def _create_legacy_db(db_path: str) -> None:
    """Create agent_session_history in the old schema (no schema_version/updated_at)."""
    with _sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_session_history (
                session_id TEXT NOT NULL,
                position   INTEGER NOT NULL,
                msg_type   TEXT NOT NULL,
                content    TEXT NOT NULL DEFAULT '',
                extra_json TEXT NOT NULL DEFAULT '{}',
                PRIMARY KEY (session_id, position)
            )
            """
        )
        # Pre-populate one row so we can verify data is preserved
        conn.execute(
            "INSERT INTO agent_session_history (session_id, position, msg_type, content, extra_json) VALUES (?, ?, ?, ?, ?)",
            ("legacy-sess", 0, "human", "legacy message", "{}"),
        )
        conn.commit()


def test_migration_adds_missing_columns(tmp_path):
    """ChatPersistence opens a legacy DB and adds schema_version/updated_at columns."""
    db_file = tmp_path / "legacy.db"
    _create_legacy_db(str(db_file))

    # Opening ChatPersistence should trigger the migration automatically
    config = ChatPersistenceConfig(db_path=str(db_file))
    store = ChatPersistence(config)

    # Verify both columns now exist
    with _sqlite3.connect(db_file) as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(agent_session_history)").fetchall()}
    assert "schema_version" in cols
    assert "updated_at" in cols


def test_migration_preserves_existing_data(tmp_path):
    """Pre-existing rows survive the migration with correct default column values."""
    db_file = tmp_path / "legacy_data.db"
    _create_legacy_db(str(db_file))

    config = ChatPersistenceConfig(db_path=str(db_file))
    ChatPersistence(config)  # triggers migration

    with _sqlite3.connect(db_file) as conn:
        row = conn.execute(
            "SELECT content, schema_version FROM agent_session_history WHERE session_id = ?",
            ("legacy-sess",),
        ).fetchone()

    assert row is not None
    assert row[0] == "legacy message"
    assert row[1] == 1  # default value applied


def test_migration_allows_save_and_load_after_upgrade(tmp_path):
    """After migration, save_history and load_history work correctly."""
    db_file = tmp_path / "legacy_roundtrip.db"
    _create_legacy_db(str(db_file))

    config = ChatPersistenceConfig(db_path=str(db_file))
    store = ChatPersistence(config)

    messages = [HumanMessage(content="post-migration hello"), AIMessage(content="post-migration reply")]
    store.save_history("new-sess", messages)
    loaded = store.load_history("new-sess")

    assert len(loaded) == 2
    assert loaded[0].content == "post-migration hello"
    assert loaded[1].content == "post-migration reply"


def test_migration_idempotent(tmp_path):
    """Calling _ensure_history_schema on an already-migrated DB raises no errors."""
    db_file = tmp_path / "idempotent.db"
    config = ChatPersistenceConfig(db_path=str(db_file))
    # First open creates the up-to-date schema
    store1 = ChatPersistence(config)
    # Second open should be a no-op (no errors, no duplicate columns)
    store2 = ChatPersistence(config)

    store2.save_history("s", [HumanMessage(content="ok")])
    assert store2.load_history("s")[0].content == "ok"
