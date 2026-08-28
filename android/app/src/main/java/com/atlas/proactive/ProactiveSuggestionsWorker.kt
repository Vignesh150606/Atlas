package com.atlas.proactive

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import androidx.hilt.work.HiltWorker
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.atlas.R
import com.atlas.data.local.ProactiveSuggestionTracker
import com.atlas.data.models.ProactiveSuggestionDto
import com.atlas.data.repository.PersonalAssistantRepository
import dagger.assisted.Assisted
import dagger.assisted.AssistedInject

/**
 * Phase 11 section 2. GET /briefing/suggestions has existed since Phase
 * 10 (backend-verified) but nothing on Android ever called it - this is
 * that missing call, run periodically (see ProactiveSuggestionsScheduler,
 * ~every 30 minutes) rather than on any user action.
 *
 * Posts at most one notification per run (a single suggestion, or a
 * grouped summary for several), and only for suggestions not already
 * surfaced (ProactiveSuggestionTracker) - a stable, unchanged set of
 * suggestions produces no notification on repeat cycles, per the Phase
 * 10 mission brief's "no battery drain, no notification spam"
 * constraint referenced in this phase's brief.
 */
@HiltWorker
class ProactiveSuggestionsWorker @AssistedInject constructor(
    @Assisted context: Context,
    @Assisted params: WorkerParameters,
    private val repository: PersonalAssistantRepository,
    private val tracker: ProactiveSuggestionTracker
) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        val fetched = repository.getProactiveSuggestions().getOrNull()
            ?: return Result.retry() // network/server issue - let WorkManager back off and retry, not a hard failure

        val newKeys = tracker.diffAndUpdate(current = fetched.suggestions.map(::suggestionKey).toSet())
        if (newKeys.isEmpty()) return Result.success()

        val newSuggestions = fetched.suggestions.filter { suggestionKey(it) in newKeys }
        postNotification(newSuggestions)
        return Result.success()
    }

    private fun postNotification(newSuggestions: List<ProactiveSuggestionDto>) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            ContextCompat.checkSelfPermission(applicationContext, Manifest.permission.POST_NOTIFICATIONS)
            != PackageManager.PERMISSION_GRANTED
        ) {
            // Not granted (see Settings > Permission Center > Proactive
            // Suggestions). The check above still ran and the tracker
            // still updated - this run is still a success, it just has
            // nothing it's allowed to show for it.
            return
        }

        ProactiveNotifications.ensureChannel(applicationContext)

        val builder = NotificationCompat.Builder(applicationContext, ProactiveNotifications.CHANNEL_ID)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setAutoCancel(true)
            .setContentText(newSuggestions.first().message)

        if (newSuggestions.size == 1) {
            builder.setContentTitle("ATLAS")
        } else {
            val inboxStyle = NotificationCompat.InboxStyle()
            newSuggestions.forEach { inboxStyle.addLine(it.message) }
            builder
                .setContentTitle("ATLAS \u2014 ${newSuggestions.size} new suggestions")
                .setStyle(inboxStyle)
        }

        NotificationManagerCompat.from(applicationContext).notify(ProactiveNotifications.NOTIFICATION_ID, builder.build())
    }

    private fun suggestionKey(s: ProactiveSuggestionDto): String =
        "${s.suggestionType}:${s.relatedType ?: "-"}:${s.relatedId ?: "-"}"
}
