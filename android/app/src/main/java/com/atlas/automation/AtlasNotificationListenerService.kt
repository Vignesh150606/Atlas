package com.atlas.automation

import android.content.pm.PackageManager
import android.service.notification.StatusBarNotification
import dagger.hilt.android.AndroidEntryPoint
import javax.inject.Inject

/**
 * Phase 8: Android Automation Foundation - Notification Listener module.
 * Phase 10: category filtering/routing (mission brief section 10) - see
 * NotificationCategorizer.kt.
 *
 * Implements observe / summarize / group notifications using only the
 * official android.service.notification.NotificationListenerService API.
 * Read-only: this service never dismisses, clicks, or replies to
 * notifications - it only reads what's currently posted, on request, when
 * a device tool asks for it. There is no background polling or logging;
 * see docs/Phase8_KnownLimitations.md for why that boundary is deliberate.
 * Phase 10 doesn't change this: categorization happens in-memory on the
 * same on-request read, never persisted or sent anywhere on its own.
 */
@AndroidEntryPoint
class AtlasNotificationListenerService : android.service.notification.NotificationListenerService() {

    @Inject
    lateinit var bridge: NotificationBridgeImpl

    override fun onListenerConnected() {
        super.onListenerConnected()
        bridge.attach(this)
    }

    override fun onListenerDisconnected() {
        bridge.detach(this)
        super.onListenerDisconnected()
    }

    override fun onDestroy() {
        bridge.detach(this)
        super.onDestroy()
    }

    // Deliberately no onNotificationPosted/onNotificationRemoved handling:
    // this module is pull-based (read the current snapshot on request via
    // activeNotifications), not a background observer that logs every
    // notification as it arrives - see class doc comment.

    fun listNotifications(appFilter: String?, category: NotificationCategory? = null): AutomationResult {
        val infos = currentNotifications(appFilter, category)
        if (infos.isEmpty()) {
            return AutomationResult.ok(noNotificationsMessage(appFilter, category))
        }
        val summary = infos.joinToString("; ") { formatOne(it) }
        return AutomationResult.ok(summary, details = mapOf("count" to infos.size.toString()))
    }

    fun summarizeNotifications(appFilter: String?, category: NotificationCategory? = null): AutomationResult {
        val infos = currentNotifications(appFilter, category)
        if (infos.isEmpty()) {
            return AutomationResult.ok(noNotificationsMessage(appFilter, category))
        }
        // Phase 10: promotional noise doesn't get the same full preview
        // treatment as everything else - named and counted, not read out
        // item by item. Only applies when the caller hasn't already
        // filtered down to a specific category (asking for promotional
        // notifications specifically should still show them).
        val (promotional, everythingElse) = if (category == null) {
            infos.partition { it.category == NotificationCategory.PROMOTIONAL }
        } else {
            emptyList<NotificationInfo>() to infos
        }

        val byApp = everythingElse.groupBy { it.appLabel }
        val mainSummary = if (everythingElse.isEmpty()) {
            ""
        } else if (byApp.size == 1) {
            val (app, list) = byApp.entries.first()
            "You have ${list.size} notification${if (list.size == 1) "" else "s"} from $app: " +
                list.take(3).joinToString("; ") { it.title ?: it.text ?: "(no preview)" }
        } else {
            "You have ${everythingElse.size} notifications: " +
                byApp.entries.joinToString(", ") { (app, list) -> "$app (${list.size})" }
        }
        val promotionalNote = if (promotional.isNotEmpty()) {
            (if (mainSummary.isEmpty()) "" else " ") + "(+${promotional.size} promotional notification${if (promotional.size == 1) "" else "s"} not shown)"
        } else ""

        return AutomationResult.ok(
            (mainSummary + promotionalNote).ifBlank { noNotificationsMessage(appFilter, category) },
            details = mapOf("count" to infos.size.toString())
        )
    }

    fun groupNotifications(): AutomationResult {
        val infos = currentNotifications(null, null)
        if (infos.isEmpty()) {
            return AutomationResult.ok("You have no active notifications.")
        }
        val groups = infos.groupBy { it.packageName }.map { (pkg, list) ->
            NotificationGroup(packageName = pkg, appLabel = list.first().appLabel, notifications = list)
        }
        val summary = groups.joinToString("; ") { "${it.appLabel}: ${it.notifications.size}" }
        return AutomationResult.ok(summary, details = mapOf("group_count" to groups.size.toString()))
    }

    private fun currentNotifications(appFilter: String?, category: NotificationCategory?): List<NotificationInfo> {
        val filterLower = appFilter?.trim()?.lowercase()
        return try {
            activeNotifications
                .map { it.toNotificationInfo() }
                .filter { info ->
                    filterLower == null ||
                        info.appLabel.lowercase().contains(filterLower) ||
                        info.packageName.lowercase().contains(filterLower)
                }
                .filter { info -> category == null || info.category == category }
                .sortedByDescending { it.postTimeMillis }
        } catch (e: SecurityException) {
            // Listener not actually connected/granted despite bridge thinking
            // it is (e.g. permission revoked mid-session) - fail safe.
            emptyList()
        }
    }

    private fun StatusBarNotification.toNotificationInfo(): NotificationInfo {
        val extras = notification.extras
        val title = extras?.getCharSequence("android.title")?.toString()
        val text = extras?.getCharSequence("android.text")?.toString()
        return NotificationInfo(
            packageName = packageName,
            appLabel = appLabel(packageName),
            title = title,
            text = text,
            postTimeMillis = postTime,
            category = NotificationCategorizer.categorize(packageName, title, text)
        )
    }

    private fun appLabel(packageName: String): String {
        return try {
            val pm: PackageManager = applicationContext.packageManager
            pm.getApplicationLabel(pm.getApplicationInfo(packageName, 0)).toString()
        } catch (e: PackageManager.NameNotFoundException) {
            packageName
        }
    }

    private fun noNotificationsMessage(appFilter: String?, category: NotificationCategory?): String = when {
        appFilter != null -> "No notifications from '$appFilter' right now."
        category != null -> "No ${category.name.lowercase()} notifications right now."
        else -> "You have no active notifications."
    }

    /** Single-line "AppLabel: preview" rendering of one notification, used
     * by [listNotifications]. Reuses the same title-then-text-then-placeholder
     * fallback [summarizeNotifications] already applies per-item, so the two
     * "read a notification back" paths stay textually consistent instead of
     * drifting into two different formats for the same data. */
    private fun formatOne(info: NotificationInfo): String {
        val preview = info.title ?: info.text ?: "(no preview)"
        return "${info.appLabel}: $preview"
    }
}
