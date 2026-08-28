package com.atlas.proactive

import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.os.Build

/**
 * Phase 11 section 2. Separate from any channel automation/notification
 * *reading* might use (NotificationCategorizer only reads other apps'
 * notifications - see automation/ - it doesn't post ATLAS's own), so a
 * user muting one doesn't silently mute the other.
 */
object ProactiveNotifications {
    const val CHANNEL_ID = "atlas_proactive_suggestions"
    const val NOTIFICATION_ID = 4171 // arbitrary, stable across runs so a
    // later notify() call updates/replaces the previous one instead of
    // stacking a new one every ~30 minutes.

    fun ensureChannel(context: Context) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "Proactive Suggestions",
                NotificationManager.IMPORTANCE_DEFAULT
            ).apply {
                description = "Reminders, tasks, and routines ATLAS notices without being asked"
            }
            context.getSystemService(NotificationManager::class.java)?.createNotificationChannel(channel)
        }
    }
}
