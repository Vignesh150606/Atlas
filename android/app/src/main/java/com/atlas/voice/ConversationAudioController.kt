package com.atlas.voice

import com.atlas.automation.AutomationToolRouter
import com.atlas.data.models.DeviceAction
import com.atlas.data.models.DeviceActionResultRequest
import com.atlas.data.repository.ChatRepository
import com.atlas.data.repository.VoiceRepository
import com.atlas.data.repository.VoiceSessionState
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Owns conversation-level voice policy: what happens when a final
 * transcript comes in (send it through the *existing* chat pipeline - no
 * duplicated intent/planner/retrieval logic here), and whether to
 * auto-resume listening after ATLAS finishes speaking (continuous mode) or
 * return to idle and wait for the next tap (push-to-talk).
 *
 * VoiceManager enforces the state machine; this class only ever asks it to
 * do things the state machine already allows.
 */
@Singleton
class ConversationAudioController @Inject constructor(
    private val voiceManager: VoiceManager,
    private val chatRepository: ChatRepository,
    // Phase 8: Android Automation Foundation - see handleDeviceAction().
    private val automationToolRouter: AutomationToolRouter
) : VoiceRepository {

    private val _sessionState = MutableStateFlow(VoiceSessionState())
    override val sessionState: StateFlow<VoiceSessionState> = _sessionState.asStateFlow()

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)

    private var conversationId: Int? = null
    private var previousVoiceState: VoiceState = VoiceState.IDLE

    init {
        scope.launch {
            voiceManager.state.collect { newState ->
                handleStateTransition(from = previousVoiceState, to = newState)
                previousVoiceState = newState
                _sessionState.update { it.copy(voiceState = newState) }
            }
        }
        scope.launch {
            voiceManager.events.collect { event -> handleEvent(event) }
        }
    }

    override fun isMicAvailable(): Boolean = voiceManager.isMicAvailable()

    override fun setContinuousMode(enabled: Boolean) {
        _sessionState.update { it.copy(continuousMode = enabled) }
    }

    override fun startListening() {
        _sessionState.update { it.copy(error = null, partialTranscript = "", outputRoute = voiceManager.currentOutputRoute()) }
        voiceManager.startListening()
    }

    override fun stopListening() {
        voiceManager.stopListening()
    }

    override fun cancel() {
        voiceManager.cancel()
        _sessionState.update {
            it.copy(transcript = "", partialTranscript = "", amplitude = 0f, error = null)
        }
    }

    override fun interruptSpeaking() {
        voiceManager.interruptSpeaking()
    }

    override fun clearError() {
        // Stabilization fix (Phase 8): must also reset VoiceManager's own
        // state machine, or the orb stays stuck in ERROR after Retry - see
        // the comment on VoiceManager.clearError() for the full story.
        voiceManager.clearError()
        _sessionState.update { it.copy(error = null) }
    }

    /** Phase 10: the user tapped "Confirm" on VoiceScreen's confirmation
     * dialog (same dialog ChatScreen uses - see ui/components). */
    override fun confirmPendingDeviceAction() {
        val action = _sessionState.value.pendingConfirmation ?: return
        val activeConversationId = conversationId ?: return
        _sessionState.update { it.copy(pendingConfirmation = null) }
        handleDeviceAction(action, activeConversationId)
    }

    /** The user tapped "Cancel" - spoken aloud (this is voice mode) and
     * reported back to the backend, same as the text-chat path in
     * ChatViewModel.cancelPendingDeviceAction(). */
    override fun cancelPendingDeviceAction() {
        val action = _sessionState.value.pendingConfirmation ?: return
        val activeConversationId = conversationId
        _sessionState.update { it.copy(pendingConfirmation = null) }
        voiceManager.speak("Okay, I won't do that.")
        if (activeConversationId != null) {
            scope.launch {
                chatRepository.reportDeviceAction(
                    DeviceActionResultRequest(
                        conversationId = activeConversationId,
                        tool = action.tool,
                        action = action.action,
                        success = false,
                        summary = "Cancelled by user before execution.",
                        details = emptyMap()
                    )
                )
            }
        }
    }

    private fun handleStateTransition(from: VoiceState, to: VoiceState) {
        // Natural turn-taking: only auto-resume listening if we just
        // finished *speaking* and continuous mode is on - not on every
        // arrival at IDLE (e.g. after cancel or an error reset, which also
        // land on IDLE but must not immediately restart listening).
        if (from == VoiceState.SPEAKING && to == VoiceState.IDLE) {
            if (_sessionState.value.pendingConfirmation != null) {
                // Phase 11 section 5: move into the dedicated state
                // instead of the plain branch below, so the orb/UI
                // reflect "waiting for your yes/no" and
                // VoiceManager.startListening() (valid from this state
                // too) is entered from a state that clearly marks what
                // the next transcript means. Still only auto-resumes
                // listening in continuous mode - push-to-talk keeps
                // requiring an explicit tap, same "nothing listens
                // without being asked" principle as everywhere else (see
                // VoiceScreen's handleOrbTap, which now handles a tap
                // from this state too). A push-to-talk user who doesn't
                // tap still has the on-screen ConfirmationDialog, which
                // renders regardless of voice state.
                voiceManager.enterAwaitingConfirmation()
                if (_sessionState.value.continuousMode) {
                    voiceManager.startListening()
                }
            } else if (_sessionState.value.continuousMode) {
                voiceManager.startListening()
            }
        }
    }

    private fun handleEvent(event: VoiceManagerEvent) {
        when (event) {
            is VoiceManagerEvent.TranscriptUpdated -> {
                if (event.isFinal) {
                    _sessionState.update { it.copy(transcript = event.text, partialTranscript = "") }
                    if (_sessionState.value.pendingConfirmation != null) {
                        // Phase 10 confirmation gating (mission brief section 9)
                        // must hold in voice mode too. Phase 11 section 5: now
                        // routes through a small deterministic classifier
                        // instead of always just re-prompting - see
                        // ConfirmationYesNoClassifier for why this isn't an
                        // LLM call. UNCLEAR re-prompts and stays in
                        // AWAITING_CONFIRMATION (handleStateTransition re-enters
                        // it after this speaks, since pendingConfirmation is
                        // still set) rather than guessing either way - the
                        // guard this comment used to describe (never silently
                        // dispatching a fresh chat message that could overwrite
                        // pendingConfirmation with a second action) still holds
                        // for exactly the same reason: only YES/NO below ever
                        // resolve the pending action, dispatchToChat is never
                        // reached from this branch at all.
                        when (ConfirmationYesNoClassifier.classify(event.text)) {
                            ConfirmationAnswer.YES -> confirmPendingDeviceAction()
                            ConfirmationAnswer.NO -> cancelPendingDeviceAction()
                            ConfirmationAnswer.UNCLEAR ->
                                voiceManager.speak("Sorry, was that a yes or a no? You can also check your screen.")
                        }
                    } else {
                        dispatchToChat(event.text)
                    }
                } else {
                    _sessionState.update { it.copy(partialTranscript = event.text) }
                }
            }
            is VoiceManagerEvent.AmplitudeChanged ->
                _sessionState.update { it.copy(amplitude = event.level) }
            is VoiceManagerEvent.ErrorOccurred ->
                _sessionState.update { it.copy(error = event.message) }
        }
    }

    private fun dispatchToChat(message: String) {
        scope.launch {
            chatRepository.sendMessage(message, conversationId)
                .onSuccess { response ->
                    conversationId = response.conversationId
                    _sessionState.update { it.copy(lastResponse = response.response) }

                    // Phase 8: this was the missing link - the voice
                    // pipeline received ChatResponse.device_action but had
                    // no code path that ever executed it (text-chat mode
                    // has the same fix in ChatViewModel).
                    // Phase 10 (mission brief section 9): a confirmation-
                    // required action is staged, not executed - see
                    // confirmPendingDeviceAction()/cancelPendingDeviceAction().
                    val deviceAction = response.deviceAction
                    when {
                        deviceAction != null && deviceAction.requiresConfirmation -> {
                            _sessionState.update { it.copy(pendingConfirmation = deviceAction) }
                            voiceManager.speak("That needs your confirmation. You can say yes or no, or check your screen.")
                        }
                        deviceAction != null -> handleDeviceAction(deviceAction, response.conversationId)
                        else -> voiceManager.speak(response.response)
                    }
                }
                .onFailure { err ->
                    val message = err.message ?: "Couldn't reach ATLAS."
                    voiceManager.reportProcessingError(message)
                    _sessionState.update { it.copy(error = message) }
                }
        }
    }

    /**
     * Phase 8: executes a device_action via AutomationToolRouter and
     * speaks the *actual, verified* outcome - the "Android Tool -> Result
     * -> ... -> Voice reply" leg of the mission's tool-architecture
     * diagram, and exactly the "Open WhatsApp -> LaunchAppTool -> Android
     * -> Success -> Voice reply" example it gives.
     *
     * Deliberately speaks the automation result instead of
     * response.response: the LLM's text was written *before* the action
     * ran (e.g. "Sure, opening WhatsApp"), so it can't reflect whether the
     * action actually succeeded. Speaking both back to back would either
     * be redundant or require sequencing two TTS utterances around
     * VoiceManager's auto-resume-listening transition in continuous mode
     * (handleStateTransition) - speaking only the confirmed result avoids
     * both problems and is more honest about what actually happened.
     */
    private fun handleDeviceAction(action: DeviceAction, conversationId: Int) {
        scope.launch {
            val result = automationToolRouter.execute(action)
            _sessionState.update { it.copy(lastResponse = result.summary) }
            voiceManager.speak(result.summary)

            // Best-effort: the user already heard the correct outcome: if
            // this call fails, only the backend's memory of the action
            // (used by future turns) goes stale, which isn't worth
            // interrupting the voice session to report.
            chatRepository.reportDeviceAction(
                DeviceActionResultRequest(
                    conversationId = conversationId,
                    tool = action.tool,
                    action = action.action,
                    success = result.success,
                    summary = result.summary,
                    details = result.details
                )
            )
        }
    }
}
