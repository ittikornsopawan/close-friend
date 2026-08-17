def conversation_messages_key(conversation_id: str) -> str:
    """Redis key for a conversation's message list, shared by app/api (writer/reader)
    and app/worker (reader/updater) so the two never drift apart."""
    return f"cf:conv:{conversation_id}:messages"
