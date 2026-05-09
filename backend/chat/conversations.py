"""Chat memory: conversations + messages persisted to Postgres app schema.

Routes (all auth-required, user-scoped):
    GET    /chat/conversations           — list this user's 10 most recent
    GET    /chat/conversations/{id}      — full message history (404 if not theirs)
    DELETE /chat/conversations/{id}      — soft-fail 404 if not theirs

The ORM models mirror ``backend/postgres/app_schema.sql``. POST /chat keeps
its handler in api.py (rate limiting + chat_handler invocation live there),
but uses the persistence helpers exported from this module so the storage
layer stays in one place.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import (
    DateTime, ForeignKey, String, Text, delete as sa_delete, func, select,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, Session, mapped_column

from backend.auth.security import AppUser, get_current_user
from backend.postgres.db import Base, session_scope


router = APIRouter(prefix="/chat", tags=["chat"])


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LIST_LIMIT = 10                # "last 10 conversations per user" per the handoff
TITLE_MAX_CHARS = 60           # auto-title from first 60 chars of user message


# ---------------------------------------------------------------------------
# ORM models — mirror app_schema.sql
# ---------------------------------------------------------------------------

class ChatConversation(Base):
    __tablename__ = "chat_conversations"

    id:         Mapped[uuid.UUID]      = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    user_id:    Mapped[uuid.UUID]      = mapped_column(PG_UUID(as_uuid=True), ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False)
    title:      Mapped[Optional[str]]  = mapped_column(String(255))
    created_at: Mapped[datetime]       = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime]       = mapped_column(DateTime(timezone=True), nullable=False)


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id:                 Mapped[uuid.UUID]      = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    conversation_id:    Mapped[uuid.UUID]      = mapped_column(PG_UUID(as_uuid=True), ForeignKey("chat_conversations.id", ondelete="CASCADE"), nullable=False)
    role:               Mapped[str]            = mapped_column(String(20), nullable=False)
    content:            Mapped[str]            = mapped_column(Text, nullable=False)
    data_sources_used:  Mapped[Optional[list]] = mapped_column(JSONB)
    created_at:         Mapped[datetime]       = mapped_column(DateTime(timezone=True), nullable=False)


# ---------------------------------------------------------------------------
# Pydantic response shapes
# ---------------------------------------------------------------------------

class ConversationSummary(BaseModel):
    id: str
    title: Optional[str] = None
    updated_at: datetime
    message_count: int


class ConversationListResponse(BaseModel):
    conversations: list[ConversationSummary]


class ChatMessageOut(BaseModel):
    id: str
    role: str
    content: str
    data_sources_used: Optional[list] = None
    created_at: datetime


class ConversationDetailResponse(BaseModel):
    id: str
    title: Optional[str] = None
    created_at: datetime
    messages: list[ChatMessageOut]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _conversation_404(conversation_id: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"error": {
            "code": "conversation_not_found",
            "message": f"No conversation exists with ID '{conversation_id}'.",
            "status": 404,
        }},
    )


def _parse_uuid_or_404(conversation_id: str) -> uuid.UUID:
    """Bad UUIDs become 404 (not 422) so we don't leak the format detail."""
    try:
        return uuid.UUID(conversation_id)
    except (ValueError, TypeError, AttributeError):
        raise _conversation_404(conversation_id)


def _auto_title(message: str) -> str:
    """Derive a conversation title from the first user message.

    Strip newlines + collapse whitespace so a multi-line paste doesn't yield
    a title with a literal "\\n", and clamp to TITLE_MAX_CHARS with a single-
    char ellipsis so the column stays readable.
    """
    flat = " ".join((message or "").split())
    if not flat:
        return "New conversation"
    return flat[:TITLE_MAX_CHARS - 1] + "…" if len(flat) > TITLE_MAX_CHARS else flat


def _get_owned_conversation(s: Session, conv_id: uuid.UUID, user_id: uuid.UUID) -> ChatConversation:
    """Fetch the conversation; 404 if missing or owned by a different user.

    The "different user" case must NOT distinguish itself from "not found" —
    otherwise we leak conversation existence across users.
    """
    conv = s.get(ChatConversation, conv_id)
    if conv is None or conv.user_id != user_id:
        raise _conversation_404(str(conv_id))
    return conv


# ---------------------------------------------------------------------------
# Persistence helpers — also called from POST /chat in api.py
# ---------------------------------------------------------------------------

def ensure_conversation_for_user(
    s: Session,
    *,
    user_id: uuid.UUID,
    conversation_id: Optional[str],
    first_message: str,
) -> ChatConversation:
    """Resolve the conversation for a chat turn.

    - If conversation_id is provided: validate ownership, return it. 404 if
      it doesn't exist or belongs to someone else.
    - If conversation_id is absent: create a new conversation with an
      auto-generated title from the first message.
    """
    now = datetime.now().astimezone()  # tz-aware via local tz

    if conversation_id:
        conv_uuid = _parse_uuid_or_404(conversation_id)
        return _get_owned_conversation(s, conv_uuid, user_id)

    conv = ChatConversation(
        id=uuid.uuid4(),
        user_id=user_id,
        title=_auto_title(first_message),
        created_at=now,
        updated_at=now,
    )
    s.add(conv)
    s.flush()
    return conv


def persist_user_turn(s: Session, conversation_id: uuid.UUID, content: str) -> ChatMessage:
    msg = ChatMessage(
        id=uuid.uuid4(),
        conversation_id=conversation_id,
        role="user",
        content=content,
        data_sources_used=None,
        created_at=datetime.now().astimezone(),
    )
    s.add(msg)
    s.flush()
    return msg


def persist_assistant_turn(
    s: Session,
    conversation_id: uuid.UUID,
    content: str,
    data_sources_used: Optional[list] = None,
) -> ChatMessage:
    msg = ChatMessage(
        id=uuid.uuid4(),
        conversation_id=conversation_id,
        role="assistant",
        content=content,
        data_sources_used=list(data_sources_used) if data_sources_used else None,
        created_at=datetime.now().astimezone(),
    )
    s.add(msg)
    s.flush()
    return msg


def conversation_history_for_model(s: Session, conversation_id: uuid.UUID) -> list[dict]:
    """Return the prior turns as [{role, content}], oldest-first, for feeding
    into the chat handler's ``history`` parameter."""
    stmt = (
        select(ChatMessage.role, ChatMessage.content)
        .where(ChatMessage.conversation_id == conversation_id)
        .order_by(ChatMessage.created_at.asc())
    )
    return [{"role": r, "content": c} for r, c in s.execute(stmt).all()]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/conversations", response_model=ConversationListResponse)
def list_conversations(user: AppUser = Depends(get_current_user)):
    """Return the signed-in user's last LIST_LIMIT conversations, newest first.

    message_count is computed in SQL via LEFT JOIN + GROUP BY so the response
    stays a single round-trip even with many conversations.
    """
    with session_scope() as s:
        stmt = (
            select(
                ChatConversation,
                func.count(ChatMessage.id).label("message_count"),
            )
            .outerjoin(ChatMessage, ChatMessage.conversation_id == ChatConversation.id)
            .where(ChatConversation.user_id == user.id)
            .group_by(ChatConversation.id)
            .order_by(ChatConversation.updated_at.desc())
            .limit(LIST_LIMIT)
        )
        rows = s.execute(stmt).all()

        return ConversationListResponse(
            conversations=[
                ConversationSummary(
                    id=str(conv.id),
                    title=conv.title,
                    updated_at=conv.updated_at,
                    message_count=int(count or 0),
                )
                for conv, count in rows
            ]
        )


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailResponse)
def get_conversation(
    conversation_id: str,
    user: AppUser = Depends(get_current_user),
):
    conv_uuid = _parse_uuid_or_404(conversation_id)
    with session_scope() as s:
        conv = _get_owned_conversation(s, conv_uuid, user.id)
        msg_stmt = (
            select(ChatMessage)
            .where(ChatMessage.conversation_id == conv.id)
            .order_by(ChatMessage.created_at.asc())
        )
        messages = list(s.scalars(msg_stmt))

        return ConversationDetailResponse(
            id=str(conv.id),
            title=conv.title,
            created_at=conv.created_at,
            messages=[
                ChatMessageOut(
                    id=str(m.id),
                    role=m.role,
                    content=m.content,
                    data_sources_used=m.data_sources_used,
                    created_at=m.created_at,
                )
                for m in messages
            ],
        )


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conversation_id: str,
    user: AppUser = Depends(get_current_user),
):
    """Cascade deletes the conversation's messages via the FK ON DELETE CASCADE
    declared in app_schema.sql."""
    conv_uuid = _parse_uuid_or_404(conversation_id)
    with session_scope() as s:
        # Ownership check — 404 covers both "no such id" and "wrong user".
        _get_owned_conversation(s, conv_uuid, user.id)
        s.execute(
            sa_delete(ChatConversation).where(ChatConversation.id == conv_uuid)
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
