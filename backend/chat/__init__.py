"""Chat memory module (Path C feature 3).

Public surface:
    router — FastAPI APIRouter mounted in api.py
    Helpers used by POST /chat:
        ensure_conversation_for_user, persist_user_turn,
        persist_assistant_turn, conversation_history_for_model
"""

from backend.chat.conversations import (
    ChatConversation,
    ChatMessage,
    conversation_history_for_model,
    ensure_conversation_for_user,
    persist_assistant_turn,
    persist_user_turn,
    router,
)

__all__ = [
    "router",
    "ChatConversation",
    "ChatMessage",
    "conversation_history_for_model",
    "ensure_conversation_for_user",
    "persist_user_turn",
    "persist_assistant_turn",
]
