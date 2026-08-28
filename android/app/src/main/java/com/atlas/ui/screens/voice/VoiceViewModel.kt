package com.atlas.ui.screens.voice

import androidx.lifecycle.ViewModel
import com.atlas.data.repository.VoiceRepository
import com.atlas.data.repository.VoiceSessionState
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.StateFlow
import javax.inject.Inject

@HiltViewModel
class VoiceViewModel @Inject constructor(
    private val repository: VoiceRepository
) : ViewModel() {

    val uiState: StateFlow<VoiceSessionState> = repository.sessionState

    fun isMicAvailable(): Boolean = repository.isMicAvailable()

    fun setContinuousMode(enabled: Boolean) = repository.setContinuousMode(enabled)

    fun startListening() = repository.startListening()

    fun stopListening() = repository.stopListening()

    fun cancel() = repository.cancel()

    fun interruptSpeaking() = repository.interruptSpeaking()

    fun clearError() = repository.clearError()

    // Phase 10 (mission brief section 9): see VoiceSessionState.pendingConfirmation.
    fun confirmPendingDeviceAction() = repository.confirmPendingDeviceAction()

    fun cancelPendingDeviceAction() = repository.cancelPendingDeviceAction()
}
