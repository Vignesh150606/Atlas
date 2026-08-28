package com.atlas.ui.screens.chat

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.atlas.automation.AutomationToolRouter
import com.atlas.data.models.DeviceAction
import com.atlas.data.models.DeviceActionResultRequest
import com.atlas.data.models.MessageSender
import com.atlas.data.models.MessageStatus
import com.atlas.data.models.UiMessage
import com.atlas.data.repository.ChatRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class ChatUiState(
    val messages: List<UiMessage> = emptyList(),
    val inputText: String = "",
    val isLoading: Boolean = false,
    val error: String? = null,
    val conversationId: Int? = null,
    val backendConnected: Boolean = false,
    // Phase 10 (mission brief section 9): set instead of executing
    // immediately when a DeviceAction has requiresConfirmation=true.
    // ChatScreen observes this and shows a confirmation dialog; nothing
    // in AutomationToolRouter runs until confirmDeviceAction() is called.
    // "Never bypass confirmation merely because the user is using voice"
    // - see ConversationAudioController for the same gate on the voice path.
    val pendingConfirmation: DeviceAction? = null
)

@HiltViewModel
class ChatViewModel @Inject constructor(
    private val repository: ChatRepository,
    // Phase 8: Android Automation Foundation.
    private val automationToolRouter: AutomationToolRouter
) : ViewModel() {

    private val _uiState = MutableStateFlow(ChatUiState())
    val uiState: StateFlow<ChatUiState> = _uiState.asStateFlow()

    init {
        checkBackendHealth()
    }

    fun checkBackendHealth() {
        viewModelScope.launch {
            repository.checkHealth()
                .onSuccess { health ->
                    _uiState.update { it.copy(backendConnected = health.status == "healthy", error = null) }
                }
                .onFailure { err ->
                    _uiState.update { it.copy(backendConnected = false, error = "Backend offline: ${err.message}") }
                }
        }
    }

    fun onInputTextChanged(newText: String) {
        _uiState.update { it.copy(inputText = newText) }
    }

    fun sendMessage() {
        val text = uiState.value.inputText.trim()
        if (text.isEmpty() || uiState.value.isLoading) return

        val userMessage = UiMessage(
            sender = MessageSender.USER,
            text = text,
            status = MessageStatus.SENDING
        )
        _uiState.update { state ->
            state.copy(
                messages = state.messages + userMessage,
                inputText = "",
                isLoading = true,
                error = null
            )
        }

        dispatchMessage(userMessage)
    }

    /** Re-sends a message that previously failed, without duplicating it in the list. */
    fun retryMessage(messageId: String) {
        if (uiState.value.isLoading) return
        val target = uiState.value.messages.find {
            it.id == messageId && it.status == MessageStatus.FAILED
        } ?: return

        _uiState.update { state ->
            state.copy(
                messages = state.messages.map {
                    if (it.id == messageId) it.copy(status = MessageStatus.SENDING) else it
                },
                isLoading = true,
                error = null
            )
        }

        dispatchMessage(target)
    }

    private fun dispatchMessage(pendingMessage: UiMessage) {
        viewModelScope.launch {
            repository.sendMessage(pendingMessage.text, uiState.value.conversationId)
                .onSuccess { response ->
                    val assistantMessage = UiMessage(
                        sender = MessageSender.ATLAS,
                        text = response.response
                    )
                    _uiState.update { state ->
                        state.copy(
                            messages = state.messages.map {
                                if (it.id == pendingMessage.id) it.copy(status = MessageStatus.SENT) else it
                            } + assistantMessage,
                            conversationId = response.conversationId,
                            isLoading = false,
                            backendConnected = true
                        )
                    }
                    // Phase 8: this was the missing link - automationToolRouter
                    // was already injected above but never called, so a
                    // ChatResponse.device_action was silently dropped on the
                    // floor in text-chat mode (voice mode has the same fix in
                    // ConversationAudioController).
                    // Phase 10 (mission brief section 9): a confirmation-
                    // required action is staged, not executed - see
                    // confirmPendingDeviceAction()/cancelPendingDeviceAction().
                    response.deviceAction?.let { action ->
                        if (action.requiresConfirmation) {
                            _uiState.update { it.copy(pendingConfirmation = action) }
                        } else {
                            executeDeviceAction(action, response.conversationId)
                        }
                    }
                }
                .onFailure { err ->
                    _uiState.update { state ->
                        state.copy(
                            messages = state.messages.map {
                                if (it.id == pendingMessage.id) it.copy(status = MessageStatus.FAILED) else it
                            },
                            isLoading = false,
                            error = err.message ?: "Failed to get response from ATLAS"
                        )
                    }
                }
        }
    }

    /**
     * Phase 8: executes a ChatResponse.device_action locally via
     * AutomationToolRouter and reports the outcome back to the backend -
     * the "Android Tool -> Result -> Memory" leg of the mission's tool
     * diagram. Deliberately posted as a *separate* follow-up UiMessage
     * after the LLM's own reply, rather than editing/replacing it: the
     * LLM's text (e.g. "Sure, opening WhatsApp now") is written before the
     * action actually runs, so only this follow-up message reflects the
     * real, confirmed outcome.
     */
    private fun executeDeviceAction(action: DeviceAction, conversationId: Int) {
        viewModelScope.launch {
            val result = automationToolRouter.execute(action)
            val outcomeMessage = UiMessage(
                sender = MessageSender.ATLAS,
                text = (if (result.success) "\u2705 " else "\u26a0\ufe0f ") + result.summary
            )
            _uiState.update { state -> state.copy(messages = state.messages + outcomeMessage) }

            // Best-effort: the user has already seen the correct outcome
            // locally. If this call fails, only the backend's memory of the
            // action (used by future turns) goes stale - not worth
            // surfacing as a user-facing error on top of the automation
            // result they already saw.
            repository.reportDeviceAction(
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

    fun clearError() {
        _uiState.update { it.copy(error = null) }
    }

    /**
     * Phase 10 (mission brief section 9): the user tapped "Confirm" on
     * the dialog ChatScreen shows for uiState.pendingConfirmation. Only
     * now does AutomationToolRouter.execute() actually run - see
     * dispatchMessage's success handler for where execution was staged
     * instead of run immediately.
     */
    fun confirmPendingDeviceAction() {
        val action = uiState.value.pendingConfirmation ?: return
        val conversationId = uiState.value.conversationId ?: return
        _uiState.update { it.copy(pendingConfirmation = null) }
        executeDeviceAction(action, conversationId)
    }

    /** The user tapped "Cancel" - the action never runs, and this is
     * reported back to the backend (same endpoint as a real outcome) so
     * the conversation's memory of what happened stays accurate instead
     * of silently omitting that a confirmation was declined. */
    fun cancelPendingDeviceAction() {
        val action = uiState.value.pendingConfirmation ?: return
        val conversationId = uiState.value.conversationId
        _uiState.update {
            it.copy(
                pendingConfirmation = null,
                messages = it.messages + UiMessage(sender = MessageSender.ATLAS, text = "Okay, I won't do that.")
            )
        }
        if (conversationId != null) {
            viewModelScope.launch {
                repository.reportDeviceAction(
                    DeviceActionResultRequest(
                        conversationId = conversationId,
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
}
