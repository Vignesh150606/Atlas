package com.atlas.data.repository

import com.atlas.data.models.DeviceAction
import com.atlas.voice.AudioOutputRoute
import com.atlas.voice.VoiceState
import kotlinx.coroutines.flow.StateFlow

data class VoiceSessionState(
    val voiceState: VoiceState = VoiceState.IDLE,
    val transcript: String = "",
    val partialTranscript: String = "",
    val amplitude: Float = 0f,
    val lastResponse: String = "",
    val error: String? = null,
    val continuousMode: Boolean = false,
    val outputRoute: AudioOutputRoute = AudioOutputRoute.SPEAKER,
    // Phase 10 (mission brief section 9): "Never bypass confirmation
    // merely because the user is using voice" - set instead of executing
    // immediately when a DeviceAction has requiresConfirmation=true.
    // VoiceScreen observes this and shows the same ConfirmationDialog
    // ChatScreen does; nothing runs until confirmPendingDeviceAction() is
    // called. Voice-native "just say yes" confirmation (interpreting the
    // next transcript as a yes/no) is deferred - see
    // docs/Phase10_KnownLimitations.md - a screen tap is required for now.
    val pendingConfirmation: DeviceAction? = null
)

/**
 * The ViewModel-facing contract for voice mode. [ConversationAudioController]
 * is the real implementation; tests use a fake implementing this same
 * interface, exactly like ChatRepository/MemoryRepository/KnowledgeRepository.
 */
interface VoiceRepository {
    val sessionState: StateFlow<VoiceSessionState>

    fun isMicAvailable(): Boolean
    fun setContinuousMode(enabled: Boolean)
    fun startListening()
    fun stopListening()
    fun cancel()
    fun interruptSpeaking()
    fun clearError()
    // Phase 10: see VoiceSessionState.pendingConfirmation above.
    fun confirmPendingDeviceAction()
    fun cancelPendingDeviceAction()
}
