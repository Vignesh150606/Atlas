package com.atlas.automation

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Phase 8: Android Automation Foundation - Notification Listener module.
 *
 * Same seam pattern as AccessibilityBridge (see its doc comment for why):
 * AtlasNotificationListenerService is OS-managed, so it attaches/detaches
 * itself here rather than being constructor-injected anywhere.
 */
/**
 * Phase 8: Android Automation Foundation - Notification Listener module.
 * Phase 10: `category` param added to list/summarize - see
 * NotificationCategorizer.kt and AtlasNotificationListenerService.
 *
 * Same seam pattern as AccessibilityBridge (see its doc comment for why):
 * AtlasNotificationListenerService is OS-managed, so it attaches/detaches
 * itself here rather than being constructor-injected anywhere.
 */
interface NotificationBridge {
    val isConnected: StateFlow<Boolean>

    suspend fun list(appFilter: String? = null, category: NotificationCategory? = null): AutomationResult
    suspend fun summarize(appFilter: String? = null, category: NotificationCategory? = null): AutomationResult
    suspend fun group(): AutomationResult
}

@Singleton
class NotificationBridgeImpl @Inject constructor() : NotificationBridge {

    @Volatile
    private var service: AtlasNotificationListenerService? = null

    private val _isConnected = MutableStateFlow(false)
    override val isConnected: StateFlow<Boolean> = _isConnected.asStateFlow()

    internal fun attach(instance: AtlasNotificationListenerService) {
        service = instance
        _isConnected.value = true
    }

    internal fun detach(instance: AtlasNotificationListenerService) {
        if (service === instance) {
            service = null
            _isConnected.value = false
        }
    }

    override suspend fun list(appFilter: String?, category: NotificationCategory?): AutomationResult =
        service?.listNotifications(appFilter, category) ?: disconnected()

    override suspend fun summarize(appFilter: String?, category: NotificationCategory?): AutomationResult =
        service?.summarizeNotifications(appFilter, category) ?: disconnected()

    override suspend fun group(): AutomationResult =
        service?.groupNotifications() ?: disconnected()

    private fun disconnected(): AutomationResult = AutomationResult.failed(
        "Notification access isn't enabled, so ATLAS can't see your notifications. Enable it from Permission Center to use this."
    )
}
