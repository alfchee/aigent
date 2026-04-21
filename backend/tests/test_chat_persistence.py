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
