package com.atlas.data.local

import android.content.Context
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Phase 11 section 2: tracks which proactive-suggestion keys have
 * already been surfaced to the user, so ProactiveSuggestionsWorker's
 * periodic check doesn't re-notify for the same thing every cycle.
 *
 * A suggestion's key (see ProactiveSuggestionsWorker.suggestionKey)
 * incorporates suggestion_type, which the backend itself changes when a
 * reminder's state changes in a way that matters (e.g.
 * "due_soon_reminder" -> "overdue_reminder" - see
 * app/services/proactive_suggestion_service.py) - so a genuine,
 * meaningful state change naturally produces a new key and is treated
 * as new on purpose, without this class needing to know anything about
 * what a "meaningful change" means for any particular suggestion type.
 */
@Singleton
class ProactiveSuggestionTracker @Inject constructor(@ApplicationContext context: Context) {

    private val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    /**
     * Returns the subset of `current` not already known, then updates
     * the known set to exactly `current` - so a suggestion that
     * disappears (e.g. its reminder gets completed) is forgotten, and
     * would be treated as new again if it ever reappeared.
     */
    fun diffAndUpdate(current: Set<String>): Set<String> {
        val known = prefs.getStringSet(KEY_SEEN, emptySet()) ?: emptySet()
        val newOnes = current - known
        prefs.edit().putStringSet(KEY_SEEN, current).apply()
        return newOnes
    }

    companion object {
        private const val PREFS_NAME = "atlas_proactive_suggestions"
        private const val KEY_SEEN = "seen_suggestion_keys"
    }
}
