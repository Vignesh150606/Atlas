package com.atlas

import com.atlas.automation.PermissionStatusChecker
import com.atlas.ui.screens.permissions.PermissionCenterViewModel
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test

private class FakePermissionStatusChecker : PermissionStatusChecker {
    var accessibilityEnabled = false
    var notificationListenerEnabled = false
    var microphoneGranted = false
    var notificationPermissionGranted = false

    override fun isAccessibilityServiceEnabled(): Boolean = accessibilityEnabled
    override fun isNotificationListenerEnabled(): Boolean = notificationListenerEnabled
    override fun isMicrophoneGranted(): Boolean = microphoneGranted
    override fun isNotificationPermissionGranted(): Boolean = notificationPermissionGranted
}

class PermissionCenterViewModelTest {

    private lateinit var checker: FakePermissionStatusChecker
    private lateinit var viewModel: PermissionCenterViewModel

    @Before
    fun setUp() {
        checker = FakePermissionStatusChecker()
    }

    @Test
    fun testInitialStateReflectsCheckerAtConstructionTime() {
        checker.accessibilityEnabled = true
        checker.notificationListenerEnabled = false
        checker.microphoneGranted = true

        viewModel = PermissionCenterViewModel(checker)

        val state = viewModel.uiState.value
        assertTrue(state.accessibilityEnabled)
        assertFalse(state.notificationListenerEnabled)
        assertTrue(state.microphoneGranted)
    }

    @Test
    fun testOverlayIsAlwaysFalseSinceItIsNotImplementedYet() {
        viewModel = PermissionCenterViewModel(checker)
        assertFalse(viewModel.uiState.value.overlayEnabled)
    }

    @Test
    fun testRefreshPicksUpChangesMadeInSystemSettings() {
        viewModel = PermissionCenterViewModel(checker)
        assertFalse(viewModel.uiState.value.accessibilityEnabled)

        // Simulates the user having gone to system Accessibility Settings
        // and enabled it, then returned to the app.
        checker.accessibilityEnabled = true
        viewModel.refresh()

        assertTrue(viewModel.uiState.value.accessibilityEnabled)
    }

    @Test
    fun testRefreshCanAlsoReflectAPermissionBeingRevoked() {
        checker.notificationListenerEnabled = true
        viewModel = PermissionCenterViewModel(checker)
        assertTrue(viewModel.uiState.value.notificationListenerEnabled)

        checker.notificationListenerEnabled = false
        viewModel.refresh()

        assertFalse(viewModel.uiState.value.notificationListenerEnabled)
    }

    @Test
    fun testOnMicrophonePermissionResultUpdatesStateImmediately() {
        viewModel = PermissionCenterViewModel(checker)
        assertFalse(viewModel.uiState.value.microphoneGranted)

        viewModel.onMicrophonePermissionResult(true)

        assertTrue(viewModel.uiState.value.microphoneGranted)
    }

    @Test
    fun testOnMicrophonePermissionResultCanReflectDenial() {
        checker.microphoneGranted = true
        viewModel = PermissionCenterViewModel(checker)

        viewModel.onMicrophonePermissionResult(false)

        assertFalse(viewModel.uiState.value.microphoneGranted)
    }

    @Test
    fun testInitialStateReflectsNotificationPermissionAtConstructionTime() {
        checker.notificationPermissionGranted = true
        viewModel = PermissionCenterViewModel(checker)
        assertTrue(viewModel.uiState.value.notificationsGranted)
    }

    @Test
    fun testOnNotificationPermissionResultUpdatesStateImmediately() {
        viewModel = PermissionCenterViewModel(checker)
        assertFalse(viewModel.uiState.value.notificationsGranted)

        viewModel.onNotificationPermissionResult(true)

        assertTrue(viewModel.uiState.value.notificationsGranted)
    }
}
