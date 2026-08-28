package com.atlas.ui.screens.permissions

import androidx.lifecycle.ViewModel
import com.atlas.automation.PermissionStatusChecker
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import javax.inject.Inject

data class PermissionCenterUiState(
    val accessibilityEnabled: Boolean = false,
    val notificationListenerEnabled: Boolean = false,
    val microphoneGranted: Boolean = false,
    // Phase 8 mission scope explicitly lists Overlay as "(future)" - always
    // false here; there is no automation module or system settings screen
    // to enable it yet. Kept in state now so the UI row and its "Coming
    // soon" treatment don't need to change shape when it's implemented.
    val overlayEnabled: Boolean = false,
    // Phase 11 section 2: covers the periodic Proactive Suggestions check
    // (see proactive/ProactiveSuggestionsWorker.kt) actually being able to
    // post its notification, not the background check itself running -
    // that runs regardless (it's WorkManager, not tied to this
    // permission), it just can't surface anything if this is denied.
    val notificationsGranted: Boolean = false
)

/**
 * Phase 8: Android Automation Foundation - Permission Center.
 *
 * Deliberately has no logic beyond "ask PermissionStatusChecker, expose the
 * result" - status computation lives there (and is unit-testable there)
 * precisely so this ViewModel doesn't need Robolectric/instrumentation to
 * test the one thing it actually owns: refreshing on demand. See
 * PermissionCenterViewModelTest.
 */
@HiltViewModel
class PermissionCenterViewModel @Inject constructor(
    private val statusChecker: PermissionStatusChecker
) : ViewModel() {

    private val _uiState = MutableStateFlow(PermissionCenterUiState())
    val uiState: StateFlow<PermissionCenterUiState> = _uiState.asStateFlow()

    init {
        refresh()
    }

    /**
     * Re-reads permission status from the platform. Must be called when the
     * screen resumes (not just on first composition) - the whole point of
     * this screen is the user bouncing to system Settings and back, and
     * none of these three permissions can be requested with a single
     * in-app runtime prompt the way, say, camera access can.
     */
    fun refresh() {
        _uiState.update {
            it.copy(
                accessibilityEnabled = statusChecker.isAccessibilityServiceEnabled(),
                notificationListenerEnabled = statusChecker.isNotificationListenerEnabled(),
                microphoneGranted = statusChecker.isMicrophoneGranted(),
                notificationsGranted = statusChecker.isNotificationPermissionGranted()
            )
        }
    }

    /** Called directly after the in-app RECORD_AUDIO permission dialog
     * result comes back, so the row updates immediately instead of waiting
     * for the next onResume (which won't even fire, since no other Activity
     * was launched for a plain runtime-permission dialog). */
    fun onMicrophonePermissionResult(granted: Boolean) {
        _uiState.update { it.copy(microphoneGranted = granted) }
    }

    /** Same reasoning as onMicrophonePermissionResult, for
     * POST_NOTIFICATIONS (Phase 11 section 2). */
    fun onNotificationPermissionResult(granted: Boolean) {
        _uiState.update { it.copy(notificationsGranted = granted) }
    }
}
