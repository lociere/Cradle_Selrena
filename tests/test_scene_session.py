from selrena.domain.conversation.scene_session import ConversationSession, SceneSessionRuntime


def test_conversation_session_compacts_old_history() -> None:
    session = ConversationSession(scene_id="scene-a")
    for index in range(6):
        role = "user" if index % 2 == 0 else "assistant"
        session.append_message(role=role, content=f"message-{index}")

    session.compact_history(
        trigger_count=5,
        keep_recent_count=2,
        max_summary_chars=200,
    )

    recent_messages = session.get_recent_messages(limit=10)
    assert len(recent_messages) == 2
    assert recent_messages[0].content == "message-4"
    assert recent_messages[1].content == "message-5"
    assert "message-0" in session.summary_text
    assert "message-3" in session.summary_text


def test_scene_session_runtime_clears_memory_and_session() -> None:
    runtime = SceneSessionRuntime(scene_id="scene-b", short_term_max_length=4)
    runtime.session.append_message(role="user", content="hello")
    runtime.short_term_memory.add(role="user", content="hello", importance=0.5)

    runtime.clear()

    assert runtime.session.summary_text == ""
    assert runtime.session.get_recent_messages(limit=10) == []
    assert runtime.short_term_memory.get_context(limit=10) == []