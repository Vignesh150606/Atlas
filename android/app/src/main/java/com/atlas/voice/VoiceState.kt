package com.atlas.voice

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * The states the voice pipeline can be in. Mirrors the mission's
 * Idle -> Listening -> Processing -> Speaking -> Idle cycle, plus Error
 * (entered from any state when STT/TTS/the backend call fails) and,
 * since Phase 11 section 5, AwaitingConfirmation (entered after ATLAS
 * speaks a confirmation heads-up for a staged device action, so the
 * next final transcript can be routed to a yes/no classifier instead of
 * an ordinary new command - see ConversationAudioController's
 * pendingConfirmation guard, added in the Phase 10 bug-fix pass, which
 * this state complements rather than replaces).
 */
enum class VoiceState {
    IDLE,
    LISTENING,
    PROCESSING,
    SPEAKING,
    ERROR,
    AWAITING_CONFIRMATION
}

/**
 * Enforces the voice pipeline's valid state transitions so nothing further
 * up the stack (VoiceManager, ConversationAudioController) can accidentally
 * put the UI in a nonsensical state (e.g. "speaking" while also
 * "listening"). A transition that isn't in [ALLOWED_TRANSITIONS] is
 * rejected outright rather than silently coerced.
 *
 * IDLE is reachable from every state - that's the deliberate "cancel /
 * reset" escape hatch the mission's Cancel/Retry actions need, rather than
 * requiring a specific state to cancel from.
 */
class VoiceStateMachine(initial: VoiceState = VoiceState.IDLE) {

    private val _state = MutableStateFlow(initial)
    val state: StateFlow<VoiceState> = _state.asStateFlow()

    val current: VoiceState
        get() = _state.value

    /** Returns true if the transition was applied, false if it was rejected as invalid. */
    fun transitionTo(target: VoiceState): Boolean {
        val from = _state.value
        if (target == VoiceState.IDLE || ALLOWED_TRANSITIONS[from]?.contains(target) == true) {
            _state.value = target
            return true
        }
        return false
    }

    fun reset() {
        _state.value = VoiceState.IDLE
    }

    companion object {
        private val ALLOWED_TRANSITIONS: Map<VoiceState, Set<VoiceState>> = mapOf(
            // Phase 11 section 5: AWAITING_CONFIRMATION added alongside
            // LISTENING as a valid target from IDLE - entered right after
            // the confirmation heads-up finishes speaking (TTS completion
            // always lands on IDLE first, generically - see
            // VoiceManager.handleTtsEvent - then ConversationAudioController
            // decides whether to move on into AWAITING_CONFIRMATION).
            VoiceState.IDLE to setOf(VoiceState.LISTENING, VoiceState.AWAITING_CONFIRMATION),
            VoiceState.LISTENING to setOf(VoiceState.PROCESSING, VoiceState.ERROR),
            VoiceState.PROCESSING to setOf(VoiceState.SPEAKING, VoiceState.ERROR),
            // SPEAKING -> SPEAKING permits a second utterance to replace or
            // queue after an already-speaking prompt (for example, the
            // verified result of a just-confirmed device action). VoiceManager
            // documents and uses this as the normal speaking-while-speaking
            // path; SPEAKING -> LISTENING remains the continuous-conversation
            // turn-taking path.
            VoiceState.SPEAKING to setOf(VoiceState.SPEAKING, VoiceState.LISTENING, VoiceState.ERROR),
            VoiceState.ERROR to emptySet(),
            // LISTENING (to hear the confirm/cancel answer - a plain
            // final transcript, handled exactly like any other, just
            // routed differently by ConversationAudioController's
            // pendingConfirmation guard) or ERROR (e.g. an STT failure
            // while waiting). Reaching IDLE from here - e.g. the user
            // cancels without answering - is the generic escape hatch
            // above, not listed per-state.
            VoiceState.AWAITING_CONFIRMATION to setOf(VoiceState.LISTENING, VoiceState.ERROR),
        )
    }
}
