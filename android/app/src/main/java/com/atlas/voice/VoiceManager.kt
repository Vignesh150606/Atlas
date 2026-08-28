package com.atlas.voice

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.launch
import javax.inject.Inject
import javax.inject.Singleton

sealed class VoiceManagerEvent {
    data class TranscriptUpdated(val text: String, val isFinal: Boolean) : VoiceManagerEvent()
    /** Normalized 0..1 microphone amplitude, for the orb to react to while listening. */
    data class AmplitudeChanged(val level: Float) : VoiceManagerEvent()
    data class ErrorOccurred(val message: String, val recoverable: Boolean) : VoiceManagerEvent()
}

/**
 * Wires SpeechToTextEngine + TextToSpeechEngine + AudioSessionManager
 * together behind the voice state machine. Deliberately has no opinion on
 * conversation-level policy (continuous mode, auto-restart after speaking,
 * push-to-talk vs tap-to-talk) - that belongs to ConversationAudioController,
 * which observes this class's state/events and decides what to do next.
 * VoiceManager only guarantees the state machine's invariants are honored.
 */
@Singleton
class VoiceManager @Inject constructor(
    private val speechToText: SpeechToTextEngine,
    private val textToSpeech: TextToSpeechEngine,
    private val audioSessionManager: AudioSessionManager
) {
    private val stateMachine = VoiceStateMachine()
    val state: StateFlow<VoiceState> = stateMachine.state

    private val _events = MutableSharedFlow<VoiceManagerEvent>(extraBufferCapacity = 16)
    val events: SharedFlow<VoiceManagerEvent> = _events.asSharedFlow()

    // Application-lifetime scope: this is a Singleton wired once via Hilt,
    // not a ViewModel, so it owns its own coroutine scope rather than
    // borrowing viewModelScope.
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)

    init {
        scope.launch { speechToText.events.collect { handleSttEvent(it) } }
        scope.launch { textToSpeech.events.collect { handleTtsEvent(it) } }
    }

    fun isMicAvailable(): Boolean = speechToText.isAvailable()

    fun currentOutputRoute(): AudioOutputRoute = audioSessionManager.currentOutputRoute()

    fun startListening() {
        if (stateMachine.current != VoiceState.IDLE && stateMachine.current != VoiceState.AWAITING_CONFIRMATION) return

        val focusGranted = audioSessionManager.requestFocus(onFocusLost = ::handleFocusLost)
        if (!focusGranted) {
            _events.tryEmit(VoiceManagerEvent.ErrorOccurred("Couldn't get audio focus.", recoverable = true))
            return
        }

        if (!stateMachine.transitionTo(VoiceState.LISTENING)) return
        speechToText.startListening()
    }

    /**
     * Phase 11 section 5: called by ConversationAudioController right
     * after ATLAS finishes speaking a confirmation heads-up for a staged
     * device action (i.e. exactly when handleTtsEvent.Completed has just
     * landed on IDLE). Only valid from IDLE, matching that - this isn't
     * a general-purpose "interrupt whatever's happening" call.
     */
    fun enterAwaitingConfirmation(): Boolean {
        if (stateMachine.current != VoiceState.IDLE) return false
        return stateMachine.transitionTo(VoiceState.AWAITING_CONFIRMATION)
    }

    fun stopListening() {
        if (stateMachine.current == VoiceState.LISTENING) {
            speechToText.stopListening()
        }
    }

    /** Hard reset from any state - the mission's "Cancel recording" action. */
    fun cancel() {
        speechToText.cancel()
        textToSpeech.stop()
        audioSessionManager.abandonFocus()
        stateMachine.reset()
    }

    /** Speaks a response. Must be called while PROCESSING (the normal flow) or already SPEAKING (queueing more). */
    fun speak(text: String, interrupt: Boolean = false) {
        if (stateMachine.current != VoiceState.PROCESSING && stateMachine.current != VoiceState.SPEAKING) return
        if (!stateMachine.transitionTo(VoiceState.SPEAKING)) return
        textToSpeech.speak(text, interrupt = interrupt)
    }

    /** Barge-in: user wants ATLAS to stop talking right now. */
    fun interruptSpeaking() {
        textToSpeech.stop()
        audioSessionManager.abandonFocus()
        stateMachine.transitionTo(VoiceState.IDLE)
    }

    /**
     * Phase 8 stabilization fix: the Voice screen's "Retry" action was
     * calling ConversationAudioController.clearError(), which only cleared
     * the *displayed* error text (VoiceSessionState.error) and never told
     * this class's own state machine to leave ERROR. Since
     * VoiceStateMachine.ALLOWED_TRANSITIONS has ERROR -> {} (only reachable
     * via the always-legal -> IDLE reset), nothing was resetting it, so the
     * orb stayed stuck on "Something went wrong" forever after the first
     * error - Cancel worked (it calls cancel(), which does reset the
     * machine) but Retry silently didn't. This is the dedicated, minimal
     * counterpart to cancel(): resets the machine without also touching
     * audio focus/engines that are already inert by the time we're in ERROR.
     */
    fun clearError() {
        if (stateMachine.current == VoiceState.ERROR) {
            stateMachine.reset()
        }
    }

    /**
     * Called by ConversationAudioController when the cognitive-pipeline
     * call itself fails (network error, bad response, etc) - VoiceManager
     * has no knowledge of that call, so it can't detect this on its own.
     */
    fun reportProcessingError(message: String) {
        if (stateMachine.current != VoiceState.PROCESSING) return
        audioSessionManager.abandonFocus()
        stateMachine.transitionTo(VoiceState.ERROR)
        _events.tryEmit(VoiceManagerEvent.ErrorOccurred(message, recoverable = true))
    }

    fun release() {
        speechToText.destroy()
        textToSpeech.shutdown()
        audioSessionManager.abandonFocus()
    }

    private fun handleFocusLost() {
        speechToText.cancel()
        textToSpeech.stop()
        stateMachine.reset()
        _events.tryEmit(VoiceManagerEvent.ErrorOccurred("Audio focus lost - voice session ended.", recoverable = true))
    }

    private fun handleSttEvent(event: SpeechToTextEvent) {
        when (event) {
            is SpeechToTextEvent.PartialResult ->
                _events.tryEmit(VoiceManagerEvent.TranscriptUpdated(event.text, isFinal = false))

            is SpeechToTextEvent.FinalResult -> {
                _events.tryEmit(VoiceManagerEvent.TranscriptUpdated(event.text, isFinal = true))
                stateMachine.transitionTo(VoiceState.PROCESSING)
            }

            is SpeechToTextEvent.RmsChanged -> {
                // SpeechRecognizer's onRmsChanged is roughly in the -2..10 dB
                // range in practice (not a calibrated absolute scale) -
                // normalize to 0..1 for the orb rather than exposing raw dB.
                val normalized = ((event.rmsDb + 2f) / 12f).coerceIn(0f, 1f)
                _events.tryEmit(VoiceManagerEvent.AmplitudeChanged(normalized))
            }

            is SpeechToTextEvent.Error -> {
                audioSessionManager.abandonFocus()
                stateMachine.transitionTo(VoiceState.ERROR)
                _events.tryEmit(VoiceManagerEvent.ErrorOccurred(event.message, event.recoverable))
            }

            SpeechToTextEvent.ReadyForSpeech,
            SpeechToTextEvent.BeginningOfSpeech,
            SpeechToTextEvent.EndOfSpeech -> {
                // No state transition needed - already LISTENING for all three.
            }
        }
    }

    private fun handleTtsEvent(event: TextToSpeechEvent) {
        when (event) {
            TextToSpeechEvent.Started -> {
                // Already transitioned to SPEAKING synchronously in speak().
            }
            TextToSpeechEvent.Completed -> {
                audioSessionManager.abandonFocus()
                stateMachine.transitionTo(VoiceState.IDLE)
            }
            is TextToSpeechEvent.Error -> {
                audioSessionManager.abandonFocus()
                stateMachine.transitionTo(VoiceState.ERROR)
                _events.tryEmit(VoiceManagerEvent.ErrorOccurred(event.message, recoverable = true))
            }
        }
    }
}
