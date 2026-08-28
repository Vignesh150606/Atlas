package com.atlas

import com.atlas.data.models.DeviceAction
import com.atlas.data.repository.VoiceRepository
import com.atlas.data.repository.VoiceSessionState
import com.atlas.ui.screens.voice.VoiceViewModel
import com.atlas.voice.VoiceState
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test

class FakeVoiceRepository : VoiceRepository {
    private val _sessionState = MutableStateFlow(VoiceSessionState())
    override val sessionState: StateFlow<VoiceSessionState> = _sessionState.asStateFlow()

    var micAvailable = true
    var startListeningCalled = false
    var stopListeningCalled = false
    var cancelCalled = false
    var interruptCalled = false
    var confirmCalled = false
    var cancelPendingCalled = false

    override fun isMicAvailable(): Boolean = micAvailable

    override fun setContinuousMode(enabled: Boolean) {
        _sessionState.update { it.copy(continuousMode = enabled) }
    }

    override fun startListening() {
        startListeningCalled = true
        _sessionState.update { it.copy(voiceState = VoiceState.LISTENING) }
    }

    override fun stopListening() {
        stopListeningCalled = true
    }

    override fun cancel() {
        cancelCalled = true
        _sessionState.update { it.copy(voiceState = VoiceState.IDLE, transcript = "", partialTranscript = "") }
    }

    override fun interruptSpeaking() {
        interruptCalled = true
        _sessionState.update { it.copy(voiceState = VoiceState.IDLE) }
    }

    override fun clearError() {
        _sessionState.update { it.copy(error = null) }
    }

    fun stagePendingConfirmation(action: DeviceAction) {
        _sessionState.update { it.copy(pendingConfirmation = action) }
    }

    override fun confirmPendingDeviceAction() {
        confirmCalled = true
        _sessionState.update { it.copy(pendingConfirmation = null) }
    }

    override fun cancelPendingDeviceAction() {
        cancelPendingCalled = true
        _sessionState.update { it.copy(pendingConfirmation = null) }
    }
}

// VoiceViewModel has no coroutines of its own (it's a thin delegate to a
// reactive repository StateFlow), so unlike ChatViewModelTest/
// MemoryViewModelTest this doesn't need Dispatchers.setMain or runTest.
class VoiceViewModelTest {

    private lateinit var fakeRepository: FakeVoiceRepository
    private lateinit var viewModel: VoiceViewModel

    @Before
    fun setUp() {
        fakeRepository = FakeVoiceRepository()
        viewModel = VoiceViewModel(fakeRepository)
    }

    @Test
    fun testInitialStateIsIdle() {
        assertEquals(VoiceState.IDLE, viewModel.uiState.value.voiceState)
    }

    @Test
    fun testStartListeningDelegatesToRepository() {
        viewModel.startListening()
        assertTrue(fakeRepository.startListeningCalled)
        assertEquals(VoiceState.LISTENING, viewModel.uiState.value.voiceState)
    }

    @Test
    fun testStopListeningDelegatesToRepository() {
        viewModel.stopListening()
        assertTrue(fakeRepository.stopListeningCalled)
    }

    @Test
    fun testCancelDelegatesToRepositoryAndResetsState() {
        viewModel.startListening()
        viewModel.cancel()
        assertTrue(fakeRepository.cancelCalled)
        assertEquals(VoiceState.IDLE, viewModel.uiState.value.voiceState)
    }

    @Test
    fun testInterruptSpeakingDelegatesToRepository() {
        viewModel.interruptSpeaking()
        assertTrue(fakeRepository.interruptCalled)
    }

    @Test
    fun testSetContinuousModeUpdatesState() {
        assertFalse(viewModel.uiState.value.continuousMode)
        viewModel.setContinuousMode(true)
        assertTrue(viewModel.uiState.value.continuousMode)
    }

    @Test
    fun testIsMicAvailableDelegatesToRepository() {
        fakeRepository.micAvailable = false
        assertFalse(viewModel.isMicAvailable())
    }

    @Test
    fun testClearErrorDelegatesToRepository() {
        viewModel.clearError()
        assertNull(viewModel.uiState.value.error)
    }

    // --- Phase 10: confirmation gating (mission brief section 9) -----------
    @Test
    fun testConfirmPendingDeviceActionDelegatesToRepository() {
        val action = DeviceAction(tool = "intent", module = "intent", action = "dial", args = mapOf("number" to "911"), requiresConfirmation = true)
        fakeRepository.stagePendingConfirmation(action)
        assertEquals(action, viewModel.uiState.value.pendingConfirmation)

        viewModel.confirmPendingDeviceAction()
        assertTrue(fakeRepository.confirmCalled)
        assertNull(viewModel.uiState.value.pendingConfirmation)
    }

    @Test
    fun testCancelPendingDeviceActionDelegatesToRepository() {
        val action = DeviceAction(tool = "clipboard", module = "clipboard", action = "write", requiresConfirmation = true)
        fakeRepository.stagePendingConfirmation(action)

        viewModel.cancelPendingDeviceAction()
        assertTrue(fakeRepository.cancelPendingCalled)
        assertNull(viewModel.uiState.value.pendingConfirmation)
    }
}
