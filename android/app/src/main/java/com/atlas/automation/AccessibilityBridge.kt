package com.atlas.automation

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Phase 8: Android Automation Foundation.
 *
 * AccessibilityService instances are created and destroyed by the OS, not
 * by Hilt's object graph, so nothing else in the app can hold a direct,
 * always-valid reference to "the" running AtlasAccessibilityService. This
 * singleton is the seam: AtlasAccessibilityService attaches itself here in
 * onServiceConnected() and detaches in onDestroy()/onInterrupt(); every
 * other class (AutomationToolRouter, AndroidAppManager for foreground-app
 * detection) depends on this interface instead of the Service directly, so
 * they stay constructible and testable even when no accessibility service
 * is connected (isConnected = false, every action fails cleanly instead of
 * NPE-ing).
 */
interface AccessibilityBridge {
    val isConnected: StateFlow<Boolean>

    /** Best-effort last foreground app package, updated from window-state
     * change events. Used by AppManager for foreground-app detection
     * without requiring the separate PACKAGE_USAGE_STATS permission. */
    val foregroundPackage: StateFlow<String?>

    suspend fun click(target: String): AutomationResult
    suspend fun longClick(target: String): AutomationResult
    suspend fun scroll(direction: String): AutomationResult
    suspend fun typeText(target: String, text: String): AutomationResult
    suspend fun back(): AutomationResult
    suspend fun home(): AutomationResult
    suspend fun recents(): AutomationResult
    suspend fun openNotifications(): AutomationResult
    suspend fun readScreen(): AutomationResult
}

@Singleton
class AccessibilityBridgeImpl @Inject constructor() : AccessibilityBridge {

    // The currently attached service, or null if the user hasn't granted /
    // enabled the Accessibility Service (see Permission Center).
    @Volatile
    private var service: AtlasAccessibilityService? = null

    private val _isConnected = MutableStateFlow(false)
    override val isConnected: StateFlow<Boolean> = _isConnected.asStateFlow()

    private val _foregroundPackage = MutableStateFlow<String?>(null)
    override val foregroundPackage: StateFlow<String?> = _foregroundPackage.asStateFlow()

    internal fun attach(instance: AtlasAccessibilityService) {
        service = instance
        _isConnected.value = true
    }

    internal fun detach(instance: AtlasAccessibilityService) {
        if (service === instance) {
            service = null
            _isConnected.value = false
        }
    }

    internal fun onForegroundPackageChanged(packageName: String) {
        _foregroundPackage.value = packageName
    }

    private fun requireService(): AtlasAccessibilityService? = service

    override suspend fun click(target: String): AutomationResult =
        requireService()?.performClick(target) ?: disconnected()

    override suspend fun longClick(target: String): AutomationResult =
        requireService()?.performLongClick(target) ?: disconnected()

    override suspend fun scroll(direction: String): AutomationResult =
        requireService()?.performScroll(direction) ?: disconnected()

    override suspend fun typeText(target: String, text: String): AutomationResult =
        requireService()?.performTypeText(target, text) ?: disconnected()

    override suspend fun back(): AutomationResult =
        requireService()?.performGlobalAction(GlobalNavAction.BACK) ?: disconnected()

    override suspend fun home(): AutomationResult =
        requireService()?.performGlobalAction(GlobalNavAction.HOME) ?: disconnected()

    override suspend fun recents(): AutomationResult =
        requireService()?.performGlobalAction(GlobalNavAction.RECENTS) ?: disconnected()

    override suspend fun openNotifications(): AutomationResult =
        requireService()?.performGlobalAction(GlobalNavAction.NOTIFICATIONS) ?: disconnected()

    override suspend fun readScreen(): AutomationResult =
        requireService()?.performReadScreen() ?: disconnected()

    private fun disconnected(): AutomationResult = AutomationResult.failed(
        "The Accessibility Service isn't enabled, so ATLAS can't interact with the screen. Enable it from Permission Center to use this."
    )
}

internal enum class GlobalNavAction { BACK, HOME, RECENTS, NOTIFICATIONS }
