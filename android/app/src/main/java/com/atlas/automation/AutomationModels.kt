package com.atlas.automation

/**
 * Phase 8: Android Automation Foundation.
 *
 * Outcome of executing a single com.atlas.data.models.DeviceAction locally.
 * This is the Android-side counterpart of the backend's ToolResult - see
 * app/tools/device_tools.py's module doc comment for the full round trip:
 * Planner -> ToolRouter -> ChatResponse.device_action -> (this class,
 * produced here) -> POST /chat/device-result -> Memory.
 */
data class AutomationResult(
    val success: Boolean,
    /** Short human-readable outcome, spoken by TTS in voice mode and shown
     * in chat in text mode, e.g. "Opened WhatsApp." or "No app matching
     * 'Foo' was found." */
    val summary: String,
    /** Optional structured extra data (e.g. now-playing track info) folded
     * into the memory entry the backend creates from this result. */
    val details: Map<String, String> = emptyMap()
) {
    companion object {
        fun ok(summary: String, details: Map<String, String> = emptyMap()) =
            AutomationResult(success = true, summary = summary, details = details)

        fun failed(summary: String) = AutomationResult(success = false, summary = summary)
    }
}

/** A single installed, launchable app - what AppManager searches over. */
data class AppInfo(
    val packageName: String,
    val label: String
)

/** A single active notification, as exposed by the Notification Listener module. */
data class NotificationInfo(
    val packageName: String,
    val appLabel: String,
    val title: String?,
    val text: String?,
    val postTimeMillis: Long,
    // Phase 10: see NotificationCategorizer.kt - computed once when the
    // StatusBarNotification is read, not re-derived at every use site.
    val category: NotificationCategory = NotificationCategory.UNKNOWN
)

/** A group of notifications from the same app, for the "group" action. */
data class NotificationGroup(
    val packageName: String,
    val appLabel: String,
    val notifications: List<NotificationInfo>
)
