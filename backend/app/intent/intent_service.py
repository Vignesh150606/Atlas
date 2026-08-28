import re
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Pattern, Tuple


class IntentType(str, Enum):
    MEMORY_UPDATE = "memory_update"
    MEMORY_CREATION = "memory_creation"
    MEMORY_SEARCH = "memory_search"
    MEMORY_DELETION = "memory_deletion"
    COMMAND = "command"
    TASK = "task"
    PLANNING = "planning"
    INFORMATION_LOOKUP = "information_lookup"
    QUESTION = "question"
    CONVERSATION = "conversation"
    GENERAL_CHAT = "general_chat"


@dataclass
class IntentResult:
    intent: IntentType
    confidence: float  # deterministic heuristic score in [0, 1], not a model probability
    matched_rule: Optional[str] = None

    def __repr__(self) -> str:
        return f"IntentResult({self.intent.value}, confidence={self.confidence}, rule={self.matched_rule!r})"


# Ordered most-specific-first: the first matching rule wins (for the single
# `classify()` result - see below). This ordering matters - e.g. "remember
# that I like jazz instead of rock" should classify as MEMORY_UPDATE, not
# MEMORY_CREATION, so update patterns are checked first.
#
# Phase 9: patterns were widened with additional paraphrasings of the same
# underlying intent (e.g. "jot down" alongside "make a note", "is there a"
# alongside "what is") - each addition is an alternative *within* the same
# rule, so it can only make an existing rule match more phrasings of the
# same intent, never change which rule wins for a message that already
# matched something. New synonyms were checked against every phrase used in
# tests/test_intent_service.py and tests/test_planner*.py before being added
# so no existing classification changes.
_RULES: List[Tuple[str, Pattern, IntentType, float]] = [
    ("explicit_update", re.compile(
        r"\b(actually|instead|correction|update my|change my|no longer|used to be|"
        r"that'?s (wrong|incorrect)|i meant to say|let me correct)\b", re.IGNORECASE
    ), IntentType.MEMORY_UPDATE, 0.85),

    ("explicit_deletion", re.compile(
        # Negative lookbehinds on "forget that" specifically: "don't forget
        # that X" / "never forget that X" mean the opposite of "forget that
        # X" (a reminder, not a deletion) - without this guard the deletion
        # rule would wrongly win over explicit_memory_creation below, since
        # it's checked first and "forget that" is a plain substring of both.
        r"\b((?<!don't )(?<!do not )(?<!dont )(?<!never )forget that|delete that|remove that memory|"
        r"that'?s not true anymore|you can forget|erase that|get rid of that memory)\b", re.IGNORECASE
    ), IntentType.MEMORY_DELETION, 0.85),

    ("explicit_memory_search", re.compile(
        r"\b(do you remember|did i tell you|what do you know about|have i mentioned|"
        r"what have i told you|do you recall|can you recall|what did i say about)\b",
        re.IGNORECASE,
    ), IntentType.MEMORY_SEARCH, 0.85),

    ("explicit_memory_creation", re.compile(
        r"\b(remember that|remember this|note that|make a note|please remember|keep in mind|"
        r"jot (down|that)|don'?t forget that|for future reference)\b",
        re.IGNORECASE,
    ), IntentType.MEMORY_CREATION, 0.9),

    ("self_disclosure", re.compile(
        r"^(i am|i'm|my name is|i live|i work|i have a|my favorite|i like|i love|i hate|i prefer)\b",
        re.IGNORECASE,
    ), IntentType.MEMORY_CREATION, 0.6),

    ("planning", re.compile(
        r"\b(help me plan|make a plan|schedule my|plan out|road ?map for|organi[sz]e my|"
        r"help me (figure out|map out)|put together a plan)\b", re.IGNORECASE
    ), IntentType.PLANNING, 0.8),

    ("task", re.compile(
        r"\b(task|todo|to-do|deadline|due (by|on|tomorrow|today)|remind me to|"
        r"don'?t let me forget to|i (need|have) to (?!plan)|add .*to my (list|tasks))\b", re.IGNORECASE
    ), IntentType.TASK, 0.75),

    ("command", re.compile(
        # Phase 8: added launch/call/dial/navigate so Android-automation
        # phrasings ("launch Spotify", "call Alice", "navigate to the
        # airport") classify as COMMAND like the pre-existing "open"/"start"
        # verbs already did, rather than falling through to CONVERSATION.
        r"^(set|create|add|delete|remove|update|calculate|compute|show me|list|open|start|stop|launch|call|dial|navigate)\b",
        re.IGNORECASE,
    ), IntentType.COMMAND, 0.7),

    ("information_lookup", re.compile(
        r"\b(what is|who is|when is|where is|how (much|many)|define|explain|"
        r"tell me about|is there an?|can you tell me|do you know)\b", re.IGNORECASE
    ), IntentType.INFORMATION_LOOKUP, 0.65),

    ("greeting_or_smalltalk", re.compile(
        r"^(hi|hello|hey|thanks|thank you|good (morning|afternoon|evening)|how are you|what'?s up)\b",
        re.IGNORECASE,
    ), IntentType.GENERAL_CHAT, 0.7),

    ("question_mark", re.compile(r"\?\s*$"), IntentType.QUESTION, 0.55),
]


# Clauses are split on these deterministic conjunctions/separators so a
# compound message ("remind me to call John and what's my next class") is
# classified per-clause rather than as one blended guess. Deliberately a
# short, unambiguous list - splitting on bare commas would fragment normal
# sentences ("my favorite foods are pizza, sushi, and ramen").
_CLAUSE_SPLIT_RE = re.compile(r"\band then\b|\bthen also\b|\band also\b|;|(?<=[a-z])\.\s+(?=[A-Z])|\band\b", re.IGNORECASE)


class IntentService:
    """Deterministic intent classification - no LLM call involved.

    Rules are checked in priority order (see _RULES); the first match wins.
    If nothing matches, falls back to CONVERSATION for longer statements or
    GENERAL_CHAT for very short ones, both with low confidence, since we
    genuinely don't know and shouldn't overstate certainty.
    """

    @staticmethod
    def classify(message: str) -> IntentResult:
        """Single top intent for a whole message - unchanged Phase 1-8
        behavior, kept as the primary entry point every existing caller
        (Planner, ChatService, tests) already depends on."""
        text = message.strip()
        if not text:
            return IntentResult(IntentType.GENERAL_CHAT, confidence=0.3, matched_rule="empty_message")

        for rule_name, pattern, intent, confidence in _RULES:
            if pattern.search(text):
                return IntentResult(intent, confidence=confidence, matched_rule=rule_name)

        # No rule matched - fall back based on message shape rather than guessing wildly.
        word_count = len(text.split())
        if word_count <= 3:
            return IntentResult(IntentType.GENERAL_CHAT, confidence=0.4, matched_rule="fallback_short")
        return IntentResult(IntentType.CONVERSATION, confidence=0.4, matched_rule="fallback_default")

    @classmethod
    def classify_all(cls, message: str) -> List[IntentResult]:
        """Phase 9: every distinct intent detectable in a message, not just
        the single highest-priority one - for compound/multi-intent
        messages like "remind me to call John and remember that I like
        tea" (TASK + MEMORY_CREATION).

        `classify_all(message)[0]` is always identical to `classify(message)`
        - this is additive, not a replacement, so nothing that already calls
        `classify()` needs to change.

        Two passes, both deterministic:
        1. Whole-message: every _RULES entry that matches anywhere in the
           text (not just the first), in priority order, deduplicated by
           intent type (first/highest-priority match per type kept). This
           alone catches most real compound messages, since the rules use
           `.search()` rather than being anchored to clause boundaries.
        2. Clause split: the message is also split on light conjunctions
           ("and", "; ", sentence boundaries) and each clause classified
           with a single `classify()` pass, to catch the same intent type
           appearing twice for two different things (e.g. two separate
           tasks) that pass 1's dedup-by-type would otherwise collapse into
           one result.
        """
        text = message.strip()
        if not text:
            return [IntentResult(IntentType.GENERAL_CHAT, confidence=0.3, matched_rule="empty_message")]

        # Pass 1: whole-message, every rule, dedup by intent type.
        whole_message_matches: List[IntentResult] = []
        seen_intents: Set[IntentType] = set()
        for rule_name, pattern, intent, confidence in _RULES:
            if intent in seen_intents:
                continue
            if pattern.search(text):
                whole_message_matches.append(IntentResult(intent, confidence=confidence, matched_rule=rule_name))
                seen_intents.add(intent)

        if not whole_message_matches:
            return [cls.classify(text)]

        # Pass 2: per-clause, to surface a second occurrence of an intent
        # type already captured above (e.g. two TASK clauses) that pass 1
        # would otherwise merge into a single result.
        clauses = [c.strip(" .!?") for c in _CLAUSE_SPLIT_RE.split(text) if c and c.strip(" .!?")]
        if len(clauses) > 1:
            for clause in clauses:
                if len(clause.split()) < 2:
                    continue  # too short to reliably classify on its own
                clause_result = cls.classify(clause)
                already_present = any(
                    r.intent == clause_result.intent and r.matched_rule == clause_result.matched_rule
                    for r in whole_message_matches
                )
                if not already_present and clause_result.matched_rule not in ("fallback_short", "fallback_default", "empty_message"):
                    whole_message_matches.append(clause_result)

        return whole_message_matches

    @classmethod
    def is_multi_intent(cls, message: str) -> bool:
        """Convenience check: does this message carry more than one
        distinct, separable ask? Used by the Planner/Conversation
        Intelligence layer to decide whether a response should address
        multiple asks rather than just the primary one.

        `question_mark` is deliberately excluded when something more
        specific also matched: it's the lowest-confidence, least specific
        rule in _RULES (effectively "this happens to end in a question
        mark"), so almost every lookup phrased as a question would
        otherwise register as "multi-intent" against itself - that's a
        surface-level property of the sentence, not a second, separable ask.
        """
        results = cls.classify_all(message)
        significant = [r for r in results if r.matched_rule != "question_mark"]
        return len(significant) > 1
