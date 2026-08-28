import pytest
from app.intent.intent_service import IntentService, IntentType


@pytest.mark.parametrize("message,expected", [
    ("Remember that I have a dentist appointment on Friday", IntentType.MEMORY_CREATION),
    ("Actually, my favorite color is green now, not blue", IntentType.MEMORY_UPDATE),
    ("Do you remember what I said about my project?", IntentType.MEMORY_SEARCH),
    ("Forget that I told you about my old job", IntentType.MEMORY_DELETION),
    ("I have a Math class at 9am", IntentType.MEMORY_CREATION),
    ("Help me plan my week", IntentType.PLANNING),
    ("Show me my recent memories", IntentType.COMMAND),
    ("What is the capital of France?", IntentType.INFORMATION_LOOKUP),
    ("Hello there!", IntentType.GENERAL_CHAT),
    ("Is it going to rain tomorrow?", IntentType.QUESTION),
])
def test_intent_classification(message, expected):
    result = IntentService.classify(message)
    assert result.intent == expected


def test_intent_result_has_confidence_and_rule():
    result = IntentService.classify("Remind me to submit the report")
    assert 0.0 < result.confidence <= 1.0
    assert result.matched_rule is not None


def test_empty_message_does_not_crash():
    result = IntentService.classify("")
    assert result.intent == IntentType.GENERAL_CHAT


def test_ambiguous_statement_falls_back_to_conversation():
    result = IntentService.classify("The weather has been strange lately around here")
    assert result.intent == IntentType.CONVERSATION
    assert result.confidence < 0.5


def test_update_takes_priority_over_creation():
    """'instead' should route to MEMORY_UPDATE even though the sentence also
    reads like a self-disclosure statement."""
    result = IntentService.classify("I like tea instead of coffee now")
    assert result.intent == IntentType.MEMORY_UPDATE


# --- Phase 9: paraphrase coverage -----------------------------------------
# New synonyms added to existing rules; each of the original parametrized
# cases above must keep passing unchanged (verified by the full suite run),
# these just add phrasings the pre-Phase-9 patterns didn't recognize.
@pytest.mark.parametrize("message,expected", [
    ("Jot down that the wifi password is atlas123", IntentType.MEMORY_CREATION),
    ("Don't forget that my flight is at 6am", IntentType.MEMORY_CREATION),
    ("Can you recall what my favorite band is?", IntentType.MEMORY_SEARCH),
    ("That's actually incorrect, I moved in March not April", IntentType.MEMORY_UPDATE),
    ("Don't let me forget to renew my passport", IntentType.TASK),
    ("Is there a way to reset my password?", IntentType.INFORMATION_LOOKUP),
])
def test_paraphrased_intent_classification(message, expected):
    result = IntentService.classify(message)
    assert result.intent == expected


# --- Phase 9: multi-intent detection --------------------------------------
def test_classify_all_first_result_matches_classify():
    """classify_all()[0] must always equal classify() - additive, not a
    behavioral replacement for any existing caller."""
    messages = [
        "Remember that I have a dentist appointment on Friday",
        "Hello there!",
        "What is the capital of France?",
        "",
    ]
    for message in messages:
        assert IntentService.classify_all(message)[0] == IntentService.classify(message)


def test_classify_all_detects_two_distinct_intents():
    results = IntentService.classify_all("remind me to call John and remember that I like tea")
    intents = {r.intent for r in results}
    assert IntentType.TASK in intents
    assert IntentType.MEMORY_CREATION in intents
    assert len(results) >= 2


def test_classify_all_single_intent_message_returns_one_result():
    results = IntentService.classify_all("Hello there!")
    assert len(results) == 1
    assert results[0].intent == IntentType.GENERAL_CHAT


def test_classify_all_empty_message_returns_single_fallback():
    results = IntentService.classify_all("")
    assert len(results) == 1
    assert results[0].intent == IntentType.GENERAL_CHAT


def test_is_multi_intent_true_for_compound_message():
    assert IntentService.is_multi_intent(
        "help me plan my week and remind me to call the dentist"
    ) is True


def test_is_multi_intent_false_for_plain_question():
    """A lookup phrased as a question also matches the generic
    question_mark rule, but that's a surface property of the sentence, not
    a second separable ask - must not register as multi-intent."""
    assert IntentService.is_multi_intent("What is the capital of France?") is False


def test_is_multi_intent_false_for_single_clause():
    assert IntentService.is_multi_intent("Remind me to submit the report") is False
