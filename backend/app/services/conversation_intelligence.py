import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from app.utils.time import utc_now
from typing import Dict, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.message_repository import MessageRepository
from app.repositories.conversation_repository import ConversationRepository
from app.models.message import Message
from app.retrieval.retrieval_service import extract_keywords
from app.providers.base import ProviderMessage


@dataclass
class ConversationSummary:
    conversation_id: int
    message_count: int
    topics: List[str]
    first_message_preview: str
    last_message_preview: str
    generated_at: datetime


@dataclass
class SessionMetadata:
    conversation_id: int
    message_count: int
    created_at: Optional[datetime]
    last_active_at: Optional[datetime]
    dominant_topics: List[str] = field(default_factory=list)


def _preview(text: str, max_len: int = 80) -> str:
    text = text.strip()
    return text if len(text) <= max_len else text[: max_len - 1] + "…"


# --- Phase 9: follow-up detection -------------------------------------------
# A message that opens with one of these is very likely continuing the
# previous exchange rather than starting a new topic - "and remind me
# tomorrow too", "what about Tuesday?", "yes please", "that one".
_FOLLOW_UP_CUE_RE = re.compile(
    r"^(and|also|what about|how about|yes|yeah|yep|sure|ok|okay|"
    r"that one|this one|the (?:first|second|third|last) one)\b",
    re.IGNORECASE,
)
# A bare pronoun with nothing else concrete in a *short* message is a weak
# but real signal the message is referring back to something already said
# ("cancel it", "move that to Friday") rather than standing alone.
_BARE_PRONOUN_RE = re.compile(r"\b(it|that|this|them|those|these)\b", re.IGNORECASE)
_FOLLOW_UP_MAX_WORDS = 8

# --- Phase 9: ambiguous-command detection -----------------------------------
# Mirrors app/skills/reminder_skill.py / calendar_skill.py's own match()
# conditions: these are messages that clearly signal the *kind* of thing the
# user wants (a reminder, a calendar event) but are missing the one piece of
# information (what to remind them of / what the event is) those skills
# need to actually do anything - see MemoryExtractor.parse_reminder /
# parse_event, which return None for exactly these inputs, so neither the
# skill nor the extractor silently does something wrong; the gap is that
# nothing previously told the LLM *why* nothing happened, so it had to
# either invent an answer or ignore the ask.
_AMBIGUOUS_REMINDER_RE = re.compile(r"\bremind me to\b\s*[.!?]?\s*$", re.IGNORECASE)
_AMBIGUOUS_EVENT_RE = re.compile(
    r"\b(?:add (?:an )?event|schedule an event)\s*[:\-]?\s*[.!?]?\s*$", re.IGNORECASE
)


@dataclass
class FollowUpContext:
    is_follow_up: bool
    referenced_topics: List[str]
    hint: str


class ConversationIntelligenceService:
    """Deterministic conversation-level intelligence: topic detection,
    summarization, session metadata, and context rollover for long
    conversations.

    Deliberately heuristic/keyword-based rather than LLM-generated - this
    keeps it testable without a live provider and avoids an extra LLM round
    trip on every turn just to maintain bookkeeping. An LLM-generated
    abstractive summary is a reasonable future upgrade, not a requirement
    this phase needs.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.message_repo = MessageRepository(db)
        self.conversation_repo = ConversationRepository(db)

    @staticmethod
    def detect_topics(messages: List[Message], top_n: int = 5) -> List[str]:
        counter: Counter = Counter()
        for m in messages:
            counter.update(extract_keywords(m.content, max_keywords=10))
        return [word for word, _ in counter.most_common(top_n)]

    async def summarize(self, conversation_id: int) -> Optional[ConversationSummary]:
        messages = await self.message_repo.get_by_conversation(conversation_id, limit=1000)
        if not messages:
            return None
        return ConversationSummary(
            conversation_id=conversation_id,
            message_count=len(messages),
            topics=self.detect_topics(messages),
            first_message_preview=_preview(messages[0].content),
            last_message_preview=_preview(messages[-1].content),
            generated_at=utc_now(),
        )

    async def get_session_metadata(self, conversation_id: int) -> Optional[SessionMetadata]:
        conversation = await self.conversation_repo.get(conversation_id)
        if not conversation:
            return None
        messages = await self.message_repo.get_by_conversation(conversation_id, limit=1000)
        return SessionMetadata(
            conversation_id=conversation_id,
            message_count=len(messages),
            created_at=conversation.created_at,
            last_active_at=messages[-1].created_at if messages else conversation.created_at,
            dominant_topics=self.detect_topics(messages),
        )

    async def get_history_with_rollover(
        self, conversation_id: int, max_messages: int
    ) -> Tuple[List[ProviderMessage], Optional[str]]:
        """Like ConversationService.get_history_for_provider, but for
        conversations that exceed max_messages: instead of silently dropping
        the older messages, produces a short rollover note summarizing what
        was dropped (topics + count) so that context isn't lost entirely,
        just compressed.

        Returns (recent_messages_as_provider_messages, rollover_note_or_None).
        """
        all_messages = await self.message_repo.get_by_conversation(conversation_id, limit=1000)
        if len(all_messages) <= max_messages:
            recent = all_messages
            rollover_note = None
        else:
            dropped = all_messages[:-max_messages]
            recent = all_messages[-max_messages:]
            topics = self.detect_topics(dropped)
            topic_str = ", ".join(topics) if topics else "general conversation"
            rollover_note = (
                f"Earlier in this conversation ({len(dropped)} earlier messages, "
                f"not shown in full): topics discussed included {topic_str}."
            )

        provider_messages = [
            {"role": m.role, "content": m.content} for m in recent if m.role in ("user", "assistant")
        ]
        return provider_messages, rollover_note

    @staticmethod
    def detect_follow_up(
        current_message: str, recent_provider_messages: List[ProviderMessage]
    ) -> Optional[FollowUpContext]:
        """Phase 9 / "better follow-up handling": is `current_message` very
        likely continuing the last 1-2 turns rather than a fresh, standalone
        ask? If so, returns the recent turns' dominant topics and a short
        hint PromptBuilder can surface to the LLM (see
        PromptBuilder._format_conversation_hints) - e.g. so "yes, tomorrow
        works" isn't answered as if it arrived with no context at all.

        Works off the same provider-message dicts ChatService already has
        in hand from get_history_with_rollover (no extra DB query needed for
        this - Message ORM objects aren't required since we only need
        `.content` text for keyword extraction).

        Deliberately conservative: requires either an explicit follow-up
        cue word/phrase at the start of the message, or a bare pronoun in a
        short message - a long, fully-formed new question is never flagged,
        even if it happens to contain "it" somewhere.
        """
        text = current_message.strip()
        if not text or not recent_provider_messages:
            return None

        word_count = len(text.split())
        starts_with_cue = bool(_FOLLOW_UP_CUE_RE.match(text))
        has_bare_pronoun = word_count <= _FOLLOW_UP_MAX_WORDS and bool(_BARE_PRONOUN_RE.search(text))
        if not (starts_with_cue or has_bare_pronoun):
            return None

        recent_text = " ".join(m["content"] for m in recent_provider_messages[-2:])
        topics = extract_keywords(recent_text, max_keywords=5)
        if not topics:
            return None

        hint = f"This message appears to follow up on the recent discussion of: {', '.join(topics)}."
        return FollowUpContext(is_follow_up=True, referenced_topics=topics, hint=hint)

    @staticmethod
    def detect_ambiguous_command(message: str) -> Optional[str]:
        """Phase 9 / "better ambiguity resolution": recognizes a specific,
        real gap - a message that names the *kind* of ask (reminder,
        calendar event) but leaves out the one detail that ask needs (see
        this module's _AMBIGUOUS_REMINDER_RE/_AMBIGUOUS_EVENT_RE comment for
        the full rationale). Returns a short instruction for the LLM to ask
        a clarifying question, or None if the message isn't one of these
        specific known-ambiguous shapes.

        This is intentionally narrow rather than a generic
        "is this message vague" classifier - a made-up general ambiguity
        score would be unreliable and unexplainable; this only fires for
        cases we can point to a concrete missing piece of information for.
        """
        text = message.strip()
        if _AMBIGUOUS_REMINDER_RE.search(text):
            return "The user asked to be reminded of something but didn't say what - ask what they'd like to be reminded to do, don't guess."
        if _AMBIGUOUS_EVENT_RE.search(text):
            return "The user asked to add a calendar event but didn't say what the event is - ask for the event details, don't guess."
        return None
