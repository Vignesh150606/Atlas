package com.atlas.voice

enum class ConfirmationAnswer { YES, NO, UNCLEAR }

/**
 * Phase 11 section 5. Deliberately not an LLM call - matches this
 * codebase's existing heuristic-over-model philosophy for anything that
 * can be handled deterministically (see e.g. NotificationCategorizer,
 * app/nlp/datetime_parser.py on the backend). A confirm/cancel decision
 * for an already-staged, potentially consequential device action should
 * be an easily-auditable rule, not a probabilistic one.
 *
 * Matches on the *start* of the (trimmed, lowercased) utterance rather
 * than scanning anywhere within it: short, direct answers like "yes",
 * "yeah do it", "no, cancel that" are the expected shape of an answer to
 * a direct yes/no question, and anchoring to the start avoids false
 * positives from a "no" or "yes" appearing later in an unrelated,
 * longer sentence. Anything that doesn't clearly start with a
 * recognized phrase - including an utterance that matches neither list,
 * or the pathological case of matching both - returns UNCLEAR rather
 * than guessing, so the caller re-prompts (or the user can always fall
 * back to the on-screen ConfirmationDialog either way).
 */
object ConfirmationYesNoClassifier {

    private val YES_PHRASES = listOf(
        "yes", "yeah", "yep", "yup", "sure", "confirm", "confirmed",
        "do it", "go ahead", "please do", "affirmative", "correct", "okay", "ok"
    )
    private val NO_PHRASES = listOf(
        "no", "nope", "nah", "cancel", "don't", "do not", "stop",
        "never mind", "negative", "wait"
    )

    fun classify(rawText: String): ConfirmationAnswer {
        val text = rawText.trim().lowercase()
        if (text.isEmpty()) return ConfirmationAnswer.UNCLEAR

        val matchesYes = startsWithAny(text, YES_PHRASES)
        val matchesNo = startsWithAny(text, NO_PHRASES)

        return when {
            matchesYes && !matchesNo -> ConfirmationAnswer.YES
            matchesNo && !matchesYes -> ConfirmationAnswer.NO
            else -> ConfirmationAnswer.UNCLEAR
        }
    }

    private fun startsWithAny(text: String, phrases: List<String>): Boolean =
        phrases.any { phrase ->
            text == phrase || text.startsWith("$phrase ") || text.startsWith("$phrase,") || text.startsWith("$phrase.")
        }
}
